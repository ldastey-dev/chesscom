import os
from datetime import datetime, timezone

import pandas as pd
import requests

import utils


def fetch_club_members(club):
    url = f'https://api.chess.com/pub/club/{club}/members'

    response = requests.get(url, headers=utils.headers)

    if response.status_code == 200:
        data = response.json()
        return data.get('weekly', []) + data.get('monthly', []) + data.get('all_time', [])
    return []


def fetch_member_info(username, club):
    url = f'https://api.chess.com/pub/player/{username}/stats'

    response = requests.get(url, headers=utils.headers)

    if response.status_code == 200:
        stats = response.json().get('chess_daily', {})
        rating = stats.get('last', {}).get('rating', 0)
        timeout_percent = stats.get('record', {}).get('timeout_percent', 0)
    else:
        rating = 0
        timeout_percent = 0

    url = f'https://api.chess.com/pub/player/{username}'

    response = requests.get(url, headers=utils.headers)

    if response.status_code == 200:
        profile = response.json()

        name = profile.get('name', '')
        title = profile.get('title', '')
        last_online = datetime.fromtimestamp(profile.get('last_online', 0), tz=timezone.utc).strftime('%d/%m/%Y')
        joined = datetime.fromtimestamp(profile.get('joined', 0), tz=timezone.utc).strftime('%d/%m/%Y')
    else:
        name = ''
        title = ''
        last_online = ''
        joined = ''

    return {
        'FIDE Title': title,
        'Username': username,
        'Name': name,
        'Sourced Club': club,
        'Daily Rating': rating,
        'Timeout Percentage': timeout_percent,
        'Last Online': last_online,
        'Joined Chess.com': joined
    }


@utils.calculate_execution_time
def main(clubs, exclusion_club):
    all_members = set()
    for club in clubs:
        members = fetch_club_members(club)
        all_members.update((member['username'], club) for member in members)

    exclusion_members = set(
        member['username'] for member in fetch_club_members(exclusion_club)
    )
    eligible_members = {
        username for username, club in all_members if username not in exclusion_members
    }

    results = []
    for username, club in all_members:
        if username in eligible_members:
            member_info = fetch_member_info(username, club)
            results.append(member_info)

    seen = set()
    deduped_results = []
    for result in results:
        if result['Username'] not in seen:
            deduped_results.append(result)
            seen.add(result['Username'])

    df = pd.DataFrame(deduped_results)

    file = utils.get_unique_filename('output', 'Member Prospects', 'xlsx')
    df.to_excel(file, index=False, sheet_name='Member Prospects')
    utils.print_line(f'Excel file created: {file}')


if __name__ == "__main__":
    exclusion_club = 'team-scotland'
    clubs = os.getenv('LIST_OF_CLUBS').split(',')

    try:
        main(clubs, exclusion_club)
    except Exception as e:
        utils.print_line(f"Error: {e}")
