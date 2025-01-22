import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv


load_dotenv()


# Environment variables
MATCH_ID = os.getenv('MATCH_ID')
CLUB_REF = os.getenv('CLUB_REF')
CLUB_NAME = os.getenv('CLUB_NAME')


# Need to set a User-Agent or the API will return 403 Forbidden
# Could use anything but chose a Chrome user agent to fly below the radar
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
}


# Decoration wrapper to calculate total execution time
def calculate_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        print(
            f"Execution time: "
            f"\n{(end_time - start_time):.2f} seconds"
            f"\n{(end_time - start_time)/60:.2f} minutes"
        )

        return result
    return wrapper


# Wrap external calls with retry and error handling 
def request_handler(url, headers=None, retries=3, backoff_factor=0.3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            
            response.raise_for_status()
            return response
        except (ConnectionError, requests.HTTPError, requests.Timeout) as e:
            if attempt < retries - 1:
                sleep_time = backoff_factor * (2 ** attempt)
                time.sleep(sleep_time)
            else:
                raise e


# Returns a user's stats which include daily rating and timeout percentage
def get_stats(username):
    url = f"https://api.chess.com/pub/player/{username}/stats"

    response = request_handler(url, headers, 3, 0.3)

    return response.json().get('chess_daily', {})


# Returns the date of the last online activity of a user
def get_last_online(username):
    url = f"https://api.chess.com/pub/player/{username}"
    
    response = request_handler(url, headers, 3, 0.3)
    
    last_online = response.json().get('last_online', 0)
    return datetime.utcfromtimestamp(last_online).strftime('%d/%m/%Y')


# Returns the maximum rating allowed for a given match
def get_match_rating_max(match_id):
    url = f"https://api.chess.com/pub/match/{match_id}"

    response = request_handler(url, headers, 3, 0.3)

    data = response.json()
    return data.get('settings', {}).get('max_rating', None)


# Returns a list of all club members with a rating up to max_rating
def get_eligible_members(club, max_rating):
    url = f"https://api.chess.com/pub/club/{club}/members"

    response = request_handler(url, headers, 3, 0.3)

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
    
    response = request_handler(url, headers, 3, 0.3)

    all_participants = []
    data = response.json()
    
    # Need and assignment for the side data during unpacking of the response
    # or this fails with a runtime error. _ as a placeholder is sufficient
    for _, team_data in data.get('teams', {}).items():
        if team_data.get('name', '').lower() == CLUB_NAME.lower():
            for player in team_data.get('players', []):
                all_participants.append(player.get('username', '').lower())

    return all_participants


@calculate_execution_time
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

    os.makedirs('output', exist_ok=True) 
    df.to_excel(f"output/Match Eligibility.xlsx", index=False)


if __name__ == "__main__":
    match_id = MATCH_ID

    if match_id is None:
        match_id = input("Enter the match ID: ")

    main(CLUB_REF, match_id)