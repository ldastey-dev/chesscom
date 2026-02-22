import os
from datetime import datetime, timezone

import pandas as pd

import utils


def get_club_members(club):
    url = f'https://api.chess.com/pub/club/{club}/members'

    response = utils.request_handler(url, headers=utils.headers)

    data = response.json()

    return data.get('weekly', []) + data.get('monthly', []) + data.get('all_time', [])


def get_member_joined_club(club, username):
    url = f'https://api.chess.com/pub/club/{club}/members'

    response = utils.request_handler(url, headers=utils.headers)

    data = response.json()
    all_members = data.get('weekly', []) + data.get('monthly', []) + data.get('all_time', [])

    for member in all_members:
        if member.get('username') == username:
            joined_timestamp = member.get('joined', 0)
            return datetime.fromtimestamp(joined_timestamp, tz=timezone.utc).strftime('%d/%m/%Y')

    return []


def get_member_info(username, club):
    url = f'https://api.chess.com/pub/player/{username}/stats'

    response = utils.request_handler(url, headers=utils.headers)

    stats_data = response.json()

    # Get standard chess daily stats
    chess_stats = stats_data.get('chess_daily', {})
    chess_rating = chess_stats.get('last', {}).get('rating', 0)
    timeout_percent = chess_stats.get('record', {}).get('timeout_percent', 0)

    # Get Chess960 daily stats
    chess960_stats = stats_data.get('chess960_daily', {})
    chess960_rating = chess960_stats.get('last', {}).get('rating', 'Unrated') if chess960_stats else 'Unrated'

    url = f'https://api.chess.com/pub/player/{username}'

    response = utils.request_handler(url, headers=utils.headers)

    profile = response.json()

    name = profile.get('name', '')
    title = profile.get('title', '')
    last_online = datetime.fromtimestamp(profile.get('last_online', 0), tz=timezone.utc).strftime('%d/%m/%Y')
    joined = datetime.fromtimestamp(profile.get('joined', 0), tz=timezone.utc).strftime('%d/%m/%Y')

    return {
        'FIDE Title': title,
        'Username': username,
        'Name': name,
        'Joined Chess.com': joined,
        'Joined Club': get_member_joined_club(club, username),
        'Last Online': last_online,
        'Daily Rating': chess_rating,
        'Chess960 Rating': chess960_rating,
        'Timeout Percentage': timeout_percent
    }


@utils.calculate_execution_time
def main(club):
    results = []

    members = get_club_members(club)

    for member in members:
        results.append(get_member_info(member.get('username'), club))

    df = pd.DataFrame(results)

    file = utils.get_unique_filename('output', 'Club Member Summary Report', 'xlsx')
    df.to_excel(file, index=False, sheet_name='Club Member Summary Report')
    utils.print_line(f'Excel file created: {file}')


if __name__ == "__main__":
    try:
        main(os.getenv('CLUB_REF'))
    except Exception as e:
        utils.print_line(f'Error: {e}')
