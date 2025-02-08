import os
import utils
import requests
import pandas as pd
from datetime import datetime, timezone


# Environment variables
MATCH_ID = os.getenv('MATCH_ID')
CLUB_REF = os.getenv('CLUB_REF')
CLUB_NAME = os.getenv('CLUB_NAME')


# Returns a user's stats which include daily rating and timeout percentage
def get_stats(username):
    url = f'https://api.chess.com/pub/player/{username}/stats'

    try:
        response = utils.request_handler(url, utils.headers)
    except requests.HTTPError as e:
        print(f'Unable to retrieve stats for user: {username}\n')
        print(f'Stack Trace: {e}\n')
        return {}

    return response.json().get('chess_daily', {})


# Returns the date of the last online activity of a user
def get_last_online(username):
    url = f'https://api.chess.com/pub/player/{username}'
    
    response = utils.request_handler(url, utils.headers)
    
    last_online = response.json().get('last_online', 0)
    return datetime.fromtimestamp(last_online, tz=timezone.utc).strftime('%d/%m/%Y')


# Returns the maximum rating allowed for a given match
def get_match_rating_max(match_id):
    url = f"https://api.chess.com/pub/match/{match_id}"

    response = utils.request_handler(url, utils.headers)

    data = response.json()
    return data.get('settings', {}).get('max_rating', None)


# Returns a list of all club members with a rating up to max_rating
def get_eligible_members(club, max_rating):
    url = f"https://api.chess.com/pub/club/{club}/members"

    response = utils.request_handler(url, utils.headers)

    eligible_members = []
    data = response.json()

    all_members = data.get('weekly', []) + data.get('monthly', []) + data.get('all_time', [])
    for member in all_members:
        username = member.get('username', '')

        stats = get_stats(username)
        rating = stats.get('last', {}).get('rating', 0)
        timeout_percent = stats.get('record', {}).get('timeout_percent', 0)

        if rating <= max_rating:
            member['daily_rating'] = rating
            member['last_online'] = get_last_online(username)
            member['timeout_percent'] = timeout_percent

            eligible_members.append(member)

    return eligible_members


# Returns the list of already signed up members for the match 
def get_match_participants(match_id):
    url = f"https://api.chess.com/pub/match/{match_id}"
    
    response = utils.request_handler(url, utils.headers)

    all_participants = []
    data = response.json()

    for _, team_data in data.get('teams', {}).items():
        if team_data.get('name', '').lower() == CLUB_NAME.lower():
            for player in team_data.get('players', []):
                all_participants.append(player.get('username', '').lower())

    return all_participants


@utils.calculate_execution_time
def main(club, match_id):
    results = []

    members = get_eligible_members(club, get_match_rating_max(match_id))
    match_participants = get_match_participants(match_id)

    for member in members:
        username = member.get('username', '')
        signed_up = 'Yes' if username.lower() in match_participants else 'No'

        results.append({
            'Username': username,
            'Daily Rating': member.get('daily_rating'),
            'Last Online': member.get('last_online'),
            'Timeout Percentage': member.get('timeout_percent'),
            'Signed Up': signed_up
        })
    
    df = pd.DataFrame(results)

    file = utils.get_unique_filename('output', 'Match Eligibility', 'xlsx')
    df.to_excel(file, index=False)


if __name__ == "__main__":
    utils.install_requirements()

    match_id = MATCH_ID

    if match_id is None:
        match_id = input("Enter the match ID: ")

    main(CLUB_REF, match_id)