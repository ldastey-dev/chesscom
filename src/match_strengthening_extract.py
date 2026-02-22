import os
from datetime import datetime, timezone

import pandas as pd
import requests
from openpyxl.styles import Font

import utils

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
    Get chess statistics for a user including both daily and Chess960 ratings

    Args:
        username (str): Chess.com username

    Returns:
        dict: User's chess stats with both daily and chess960 ratings
    """
    try:
        response_data = call_chess_api(f'player/{username}/stats')

        # Get standard chess daily stats
        daily_stats = response_data.get('chess_daily', {})
        daily_rating = daily_stats.get('last', {}).get('rating', 'Unrated') if daily_stats else 'Unrated'

        # Get Chess960 daily stats
        chess960_stats = response_data.get('chess960_daily', {})
        chess960_rating = chess960_stats.get('last', {}).get('rating', 'Unrated') if chess960_stats else 'Unrated'

        return {
            'daily': daily_stats,
            'chess960': chess960_stats,
            'daily_rating': daily_rating,
            'chess960_rating': chess960_rating,
            'timeout_percent': daily_stats.get('record', {}).get('timeout_percent', 0)
        }

    except Exception as e:
        utils.print_line(f'Error getting stats for {username}: {e}')
        return {
            'daily': {},
            'chess960': {},
            'daily_rating': 'Unrated',
            'chess960_rating': 'Unrated',
            'timeout_percent': 0
        }


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


def get_match_variant(match_id):
    """
    Determine the chess variant for a given match

    Args:
        match_id (str): ID of the match

    Returns:
        str: 'chess960' or 'chess' based on match settings
    """
    try:
        match_data = call_chess_api(f'match/{match_id}')
        settings = match_data.get('settings', {})

        # Check for Chess960 indicators in the match settings
        rules = settings.get('rules', '').lower()
        variant = settings.get('variant', '').lower()

        # Chess960 can be indicated by 'chess960' in rules or variant fields
        if 'chess960' in rules or 'chess960' in variant or '960' in rules:
            return 'chess960'

        # Default to standard chess
        return 'chess'

    except Exception as e:
        utils.print_line(f'Warning: Could not determine match variant for {match_id}: {e}')
        utils.print_line('Defaulting to standard chess')
        return 'chess'


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
        daily_rating = stats['daily_rating']

        if isinstance(daily_rating, int) and daily_rating <= max_rating:
            member['daily_rating'] = daily_rating
            member['last_online'] = get_last_online(username)
            member['timeout_percent'] = stats['timeout_percent']

            eligible_members.append(member)

    return eligible_members


def get_eligible_members_by_variant(club, max_rating, variant='chess'):
    """
    Get list of club members eligible for a match based on variant and rating

    Args:
        club (str): Club reference/ID
        max_rating (int): Maximum rating threshold
        variant (str): 'chess' or 'chess960'

    Returns:
        list: List of eligible members with their variant-specific data
    """
    try:
        club_data = call_chess_api(f'club/{club}/members')

        eligible_members = []
        all_members = club_data.get('weekly', []) + club_data.get('monthly', []) + club_data.get('all_time', [])

        # Remove duplicates by username
        unique_members = {member.get('username', '').lower(): member for member in all_members}

        for _username_lower, member in unique_members.items():
            username = member.get('username', '')

            try:
                stats = get_stats(username)

                # Get the appropriate rating based on variant
                if variant == 'chess960':
                    variant_rating = stats['chess960_rating']
                    # Only include if they have a numeric Chess960 rating within the limit
                    if isinstance(variant_rating, int) and variant_rating <= max_rating:
                        member['daily_rating'] = stats['daily_rating']
                        member['chess960'] = variant_rating
                        member['last_online'] = get_last_online(username)
                        member['timeout_percent'] = stats['timeout_percent']
                        eligible_members.append(member)
                    elif variant_rating == 'Unrated':
                        # Include unrated Chess960 players for visibility
                        member['daily_rating'] = stats['daily_rating']
                        member['chess960'] = 'Unrated'
                        member['last_online'] = get_last_online(username)
                        member['timeout_percent'] = stats['timeout_percent']
                        eligible_members.append(member)
                else:
                    # Standard chess variant
                    variant_rating = stats['daily_rating']
                    if isinstance(variant_rating, int) and variant_rating <= max_rating:
                        member['daily_rating'] = variant_rating
                        member['chess960'] = stats['chess960_rating']
                        member['last_online'] = get_last_online(username)
                        member['timeout_percent'] = stats['timeout_percent']
                        eligible_members.append(member)

            except Exception as e:
                utils.print_line(f'Error processing member {username}: {e}')
                continue

        return eligible_members

    except Exception as e:
        utils.print_line(f'Error getting eligible members for variant {variant}: {e}')
        return []


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
    Collect and process data for eligible players based on match variant

    Args:
        club (str): Club reference/ID
        match_id (str): ID of the match

    Returns:
        list: List of dictionaries containing player data with variant info
    """
    try:
        results = []

        # Detect match variant first
        variant = get_match_variant(match_id)
        utils.print_line(f'Detected match variant: {variant.upper()}')

        # Get match data
        max_rating = get_match_rating_max(match_id)
        members = get_eligible_members_by_variant(club, max_rating, variant)
        match_participants = get_match_participants(match_id)

        for member in members:
            username = member.get('username', '')
            signed_up = 'Yes' if username.lower() in match_participants else 'No'

            results.append({
                'Username': username,
                'Daily Rating': member.get('daily_rating'),
                'Chess960 Rating': member.get('chess960'),
                'Variant': variant.upper(),
                'Last Online': member.get('last_online'),
                'Timeout Percentage': member.get('timeout_percent'),
                'Signed Up': signed_up
            })

        utils.print_line(f'Found {len(results)} eligible players for {variant.upper()} match')
        return results

    except Exception as e:
        utils.print_line(f'Error in get_eligible_players_data: {e}')
        return []


def create_excel_report(data, report_name='Match Eligibility', variant='chess'):
    """
    Create an Excel report with variant-specific information

    Args:
        data (list): List of dictionaries containing player data
        report_name (str): Name for the Excel file
        variant (str): Chess variant type for report labeling

    Returns:
        str: Path to the created Excel file
    """
    try:
        if not data:
            utils.print_line('Warning: No data provided for Excel report')
            return None

        df = pd.DataFrame(data)

        file = utils.get_unique_filename('output', report_name, 'xlsx')

        # Create Excel file with pandas
        with pd.ExcelWriter(file, engine='openpyxl') as writer:
            sheet_name = f'{report_name} {variant.upper()} Data'
            df.to_excel(writer, index=False, sheet_name=sheet_name)

            worksheet = writer.sheets[sheet_name]

            # Add hyperlinks to the Username column
            for row_num, username in enumerate(df['Username'], start=2):  # Start at row 2 (skip header)
                cell = worksheet.cell(row=row_num, column=1)  # Username is in column 1
                cell.value = username
                cell.hyperlink = f'https://www.chess.com/member/{username}'
                cell.font = Font(color="0000FF", underline="single")  # Blue, underlined text

        utils.print_line(f"Excel file created: {file}")
        return file

    except Exception as e:
        utils.print_line(f'Error creating Excel report: {e}')
        return None


@utils.calculate_execution_time
def main(club, match_id):
    """
    Main function that orchestrates data collection and report generation

    Args:
        club (str): Club reference/ID
        match_id (str): ID of the match
    """
    try:
        # Detect variant first for reporting
        variant = get_match_variant(match_id)

        # Get data
        player_data = get_eligible_players_data(club, match_id)

        if player_data:
            # Generate report with variant information
            create_excel_report(player_data, 'Match Eligibility', variant)
        else:
            utils.print_line('No eligible players found for this match')

    except Exception as e:
        utils.print_line(f'Error in main function: {e}')


if __name__ == "__main__":
    match_id = MATCH_ID

    if match_id is None:
        match_id = input("Enter the match ID: ")

    main(CLUB_REF, match_id)
