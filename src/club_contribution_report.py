import os
import time 
import utils
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()


# Environment variables
CLUB_REF = os.getenv('CLUB_REF')
CLUB_NAME = os.getenv('CLUB_NAME')
DATA_ANALYSIS_YEAR = os.getenv('DATA_ANALYSIS_YEAR')


# Returns a list of all club members 
def get_all_club_members():
    url = f'https://api.chess.com/pub/club/{CLUB_REF}/members'

    response = utils.request_handler(url, headers=utils.headers)

    members = response.json().get('weekly', []) + response.json().get('monthly', []) + response.json().get('all_time', [])
    
    return members


# Returns the daily rating for a member
def get_member_daily_rating(username):
    url = f'https://api.chess.com/pub/player/{username}/stats'

    response = utils.request_handler(url, headers=utils.headers)
    
    stats = response.json()
    
    return stats.get('chess_daily', {}).get('last', {}).get('rating', 'N/A')


# Returns the last online date for a member
def get_member_last_online(username):
    url = f'https://api.chess.com/pub/player/{username}'

    response = utils.request_handler(url, headers=utils.headers)
    
    profile = response.json()
    last_online = profile.get('last_online', 0)
    
    return datetime.fromtimestamp(last_online).strftime('%d/%m/%Y')


def get_timeout_percentage(username):
    url = f'https://api.chess.com/pub/player/{username}/stats'

    response = utils.request_handler(url, headers=utils.headers)
    
    stats = response.json().get('chess_daily', {})
    timeout_percent = stats.get('record', {}).get('timeout_percent', 0)
    
    return timeout_percent


# Returns the date a member joined the club
def get_chesscom_joined_date(username):
    url = f'https://api.chess.com/pub/player/{username}'

    response = utils.request_handler(url, headers=utils.headers)
    
    profile = response.json()
    joined_date = profile.get('joined', 0)
    
    return datetime.fromtimestamp(joined_date).strftime('%d/%m/%Y')


def get_member_joined_club(club, username):
    url = f'https://api.chess.com/pub/club/{club}/members'

    response = utils.request_handler(url, headers=utils.headers)
    
    data = response.json()
    all_members = data.get('weekly', []) + data.get('monthly', []) + data.get('all_time', [])
    
    for member in all_members:
        if member.get('username') == username:
            joined_timestamp = member.get('joined', 0)
            
            return datetime.fromtimestamp(joined_timestamp).strftime('%d/%m/%Y')


# Returns all matches for the club in a given year
def get_all_club_matches_in_year(year):
    url = f'https://api.chess.com/pub/club/{CLUB_REF}/matches'

    response = utils.request_handler(url, headers=utils.headers)
    
    all_matches = response.json().get('finished', [])
    matches_in_year = [match for match in all_matches if time.gmtime(match['start_time']).tm_year >= int(year)]
    
    return matches_in_year


# Returns match data listing participants and results 
def get_match_data(url):
    response = utils.request_handler(url, headers=utils.headers)


    match_data = response.json()
    participants = {}
    teams = match_data.get('teams', {})
    team_scotland = None

    if teams.get('team1', {}).get('name') == CLUB_NAME:
        team_scotland = teams.get('team1', {})
    elif teams.get('team2', {}).get('name') == CLUB_NAME:
        team_scotland = teams.get('team2', {})

    if team_scotland:
        for player in team_scotland.get('players', []):
            username = player['username']
            result_white = player.get('played_as_white', 'in progress')
            result_black = player.get('played_as_black', 'in progress')
            
            participants[username] = {
                'result_white': result_white, 'result_black': result_black
            }

    return participants


# Calculate the participation percentage for a member against club matches
def calculate_participation_percentage(matches_played, matches_participated):
    if matches_played == 0:
        return 0
    return round((matches_participated / matches_played) * 100, 2)


# Export the data to an Excel file
def export_to_excel(members_data, matches_data, filename='output/default.xlsx'):
    df_members = pd.DataFrame(members_data)
    df_matches = pd.DataFrame(matches_data)
    
    with pd.ExcelWriter(filename) as writer:
        df_members.to_excel(writer, sheet_name='Member Metrics', index=False)
        df_matches.to_excel(writer, sheet_name='Match Data', index=False)


@utils.calculate_execution_time
def main():
    # members = [{'username': 'leighdastey'}, {'username': 'andrewmoulden'}, 
    #     {'username': 'jules64'}, {'username': 'supermashedpotato'}]  # Test users  
    members = get_all_club_members()

    # Fetch all matches first
    matches = get_all_club_matches_in_year(DATA_ANALYSIS_YEAR)
    total_matches = len(matches)
    
    # Pre-process all match data in one go
    all_match_data = {}
    matches_data = []
    for match in matches:
        match_name = match['name']
        match_url = match['@id']
        match_info = {'Match Name': match_name, 'Match URL': match_url}
        
        # Get match data once per match
        match_data = get_match_data(match_url)
        all_match_data[match_url] = match_data
        matches_data.append(match_info)
    
    # Process member data separately from match iteration
    members_data = []
    for member in members:
        username = member['username']
        matches_participated = 0
        timeouts = 0
        
        # Fill in match data for this member
        for i, match in enumerate(matches):
            match_url = match['@id']
            match_data = all_match_data[match_url]
            
            if username in match_data:
                matches_participated += 1
                result_white = match_data[username]['result_white']
                result_black = match_data[username]['result_black']
                
                # Add results to match_info
                matches_data[i][f"{username}_white"] = result_white
                matches_data[i][f"{username}_black"] = result_black
                
                # Check for timeouts
                if result_white == 'timeout':
                    timeouts += 1
                if result_black == 'timeout':
                    timeouts += 1
            else:
                matches_data[i][f"{username}_white"] = 'not played'
                matches_data[i][f"{username}_black"] = 'not played'
        
        # Collate member data for export
        member_data = {
            'Username': username,
            'Daily Rating': get_member_daily_rating(username),
            'Joined Chess.com': get_chesscom_joined_date(username),
            'Joined Club': get_member_joined_club(CLUB_REF, username),
            'Last Online': get_member_last_online(username),
            'Timeout Percentage': get_timeout_percentage(username),
            'Club Timeouts': timeouts,
            'Total Matches': total_matches,
            'Participation %': calculate_participation_percentage(
                total_matches, matches_participated)
        }
        members_data.append(member_data)

    file = utils.get_unique_filename('output', f'{CLUB_NAME} Club Contribution Report {DATA_ANALYSIS_YEAR}', 'xlsx')
    export_to_excel(members_data, matches_data, file)
    print(f'Data exported to {file} ... program executed successfully\n\r')


if __name__ == "__main__":
    main()
