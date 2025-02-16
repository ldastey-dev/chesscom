import os
import utils
import pandas as pd
from datetime import datetime


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
            return datetime.fromtimestamp(joined_timestamp).strftime('%d/%m/%Y')

    return []


def get_member_info(username, club):
    url = f'https://api.chess.com/pub/player/{username}/stats'

    response = utils.request_handler(url, headers=utils.headers)

    stats = response.json().get('chess_daily', {})
    rating = stats.get('last', {}).get('rating', 0)
    timeout_percent = stats.get('record', {}).get('timeout_percent', 0)

    url = f'https://api.chess.com/pub/player/{username}'

    response = utils.request_handler(url, headers=utils.headers)

    profile = response.json()

    name = profile.get('name', '')
    title = profile.get('title', '')
    last_online = datetime.fromtimestamp(profile.get('last_online', 0)).strftime('%d/%m/%Y')
    joined = datetime.fromtimestamp(profile.get('joined', 0)).strftime('%d/%m/%Y')

    return {
        'FIDE Title': title,
        'Username': username,
        'Name': name,
        'Joined Chess.com': joined,
        'Joined Club': get_member_joined_club(club, username),
        'Last Online': last_online,
        'Daily Rating': rating,
        'Timeout Percentage': timeout_percent
    }


@utils.calculate_execution_time
def main(club):
    results = []

    members = get_club_members(club)

    for member in members:
        results.append(get_member_info(member.get('username'), club))

    df = pd.DataFrame(results)

    file = utils.get_unique_filename('output', 'Club Member Report', 'xlsx')
    df.to_excel(file, index=False, sheet_name='Club Member Report')
    print(f'Excel file created: {file}\n\r')


if __name__ == "__main__":
    try:
        main(os.getenv('CLUB_REF'))
    except Exception as e:
        print(f'Error: {e}\n\r')
