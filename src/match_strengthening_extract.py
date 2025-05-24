import os
import utils
import requests
import pandas as pd
from datetime import datetime, timezone
from openpyxl.styles import Font


# Environment variables
MATCH_ID = os.getenv('MATCH_ID')
CLUB_REF = os.getenv('CLUB_REF')
CLUB_NAME = os.getenv('CLUB_NAME')
BASE_URL = 'https://api.chess.com/pub'


# Generic function to call Chess.com API
def call_chess_api(endpoint):
    """
    Generic function to call Chess.com API endpoints
    
    Args:
        endpoint (str): API endpoint path (without the base URL)
        
    Returns:
        dict: JSON response data or empty dict if request fails
    """
    url = f"{BASE_URL}/{endpoint}"
    
    try:
        response = utils.request_handler(url, utils.headers)
        return response.json()
    except requests.HTTPError as e:
        utils.print_line(f'API error for endpoint {endpoint}: {e}')
        return {}


# Returns a user's stats which include daily rating and timeout percentage
def get_stats(username):
    """
    Get chess statistics for a user
    
    Args:
        username (str): Chess.com username
        
    Returns:
        dict: User's daily chess stats
    """
    response_data = call_chess_api(f'player/{username}/stats')
    return response_data.get('chess_daily', {})


# Returns the date of the last online activity of a user
def get_last_online(username):
    """
    Get the date of user's last online activity
    
    Args:
        username (str): Chess.com username
        
    Returns:
        str: Formatted date of last online activity
    """
    response_data = call_chess_api(f'player/{username}')
    last_online = response_data.get('last_online', 0)
    
    return datetime.fromtimestamp(last_online, tz=timezone.utc).strftime('%d/%m/%Y')


# Returns the maximum rating allowed for a given match
def get_match_rating_max(match_id):
    """
    Get maximum rating allowed for a match
    
    Args:
        match_id (str): ID of the match
        
    Returns:
        int: Maximum rating allowed or None
    """
    match_data = call_chess_api(f'match/{match_id}')
    return match_data.get('settings', {}).get('max_rating', None)


# Returns a list of all club members with a rating up to max_rating
def get_eligible_members(club, max_rating):
    """
    Get list of club members eligible for a match based on rating
    
    Args:
        club (str): Club reference/ID
        max_rating (int): Maximum rating threshold
        
    Returns:
        list: List of eligible members with their data
    """
    club_data = call_chess_api(f'club/{club}/members')
    
    eligible_members = []
    all_members = club_data.get('weekly', []) + club_data.get('monthly', []) + club_data.get('all_time', [])
    
    for member in all_members:
        username = member.get('username', '')

        stats = get_stats(username)
        rating = stats.get('last', {}).get('rating', 0)

        if rating <= max_rating:
            member['daily_rating'] = rating
            member['last_online'] = get_last_online(username)
            member['timeout_percent'] = stats.get('record', {}).get('timeout_percent', 0)

            eligible_members.append(member)

    return eligible_members


# Returns the list of already signed up members for the match 
def get_match_participants(match_id):
    """
    Get list of users already signed up for a match
    
    Args:
        match_id (str): ID of the match
        
    Returns:
        list: Lowercase usernames of participants
    """
    match_data = call_chess_api(f'match/{match_id}')
    
    # Optimized to use list comprehension - O(n) where n is total player count
    # Find our club's team and extract all player usernames at once
    club_name_lower = CLUB_NAME.lower()
    all_participants = [
        player.get('username', '').lower()
        for _, team_data in match_data.get('teams', {}).items()
        if team_data.get('name', '').lower() == club_name_lower
        for player in team_data.get('players', [])
    ]

    return all_participants


def get_eligible_players_data(club, match_id):
    """
    Collect and process data for eligible players
    
    Args:
        club (str): Club reference/ID
        match_id (str): ID of the match
        
    Returns:
        list: List of dictionaries containing player data
    """
    results = []
    max_rating = get_match_rating_max(match_id)
    members = get_eligible_members(club, max_rating)
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
    
    return results


def create_excel_report(data, report_name='Match Eligibility'):
    """
    Create an Excel report from the provided data
    
    Args:
        data (list): List of dictionaries containing player data
        report_name (str): Name for the Excel file
        
    Returns:
        str: Path to the created Excel file
    """
    df = pd.DataFrame(data)
    file = utils.get_unique_filename('output', report_name, 'xlsx')
    
    # Create Excel file with pandas
    with pd.ExcelWriter(file, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f'{report_name} Data')
        
        # Access the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets[f'{report_name} Data']
        
        # Add hyperlinks to the Username column
        for row_num, username in enumerate(df['Username'], start=2):  # Start at row 2 (skip header)
            cell = worksheet.cell(row=row_num, column=1)  # Username is in column 1
            cell.value = username
            cell.hyperlink = f'https://www.chess.com/member/{username}'
            cell.font = Font(color="0000FF", underline="single")  # Blue, underlined text

    utils.print_line(f"Excel file created: {file}")
    return file


@utils.calculate_execution_time
def main(club, match_id):
    """
    Main function that orchestrates data collection and report generation
    
    Args:
        club (str): Club reference/ID
        match_id (str): ID of the match
    """
    # Get data
    player_data = get_eligible_players_data(club, match_id)
    
    # Generate report
    create_excel_report(player_data, 'Match Eligibility')


if __name__ == "__main__":
    match_id = MATCH_ID

    if match_id is None:
        match_id = input("Enter the match ID: ")

    main(CLUB_REF, match_id)