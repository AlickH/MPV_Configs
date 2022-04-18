#!/opt/homebrew/bin/python3
"""
This Python script is responsible for executing the web requests.
Each request is dictated by the flag received.

TODO: Add the ability to refresh token
"""
import re
import sys
import os
import json
import pytz
import requests
from time import sleep
from datetime import date, datetime


def write_json(data):
    with open(os.path.dirname(os.path.abspath(__file__)) + '/config.json', 'w') as outfile:
        json.dump(data, outfile, indent=4)

def clean_name(name):
    result = name.replace('.', ' ')
    result = result.replace('_', ' ')
    result = result.replace("Dont", "").replace("Cant", "")
    result = re.sub(r'\(.*\)|-|\[.*\]', '', result)
    result = re.sub(r'([1-9][0-9]{3})', '', result)
    result = re.sub('[A-Z]', lambda x: " " + x.group(0), result)
    return result.lstrip()

def hello(flags, configs):
    """
    This function is called as an initial setup. It creates a 15 second delay before responding, so no scrobble happens
    by mistake.
     - Checks if the client_id and client_secret have already been set (if not, exits as 10)
     - Checks if the access_token has already been set (if not, exits as 11)
     - Checks if there is a need to refresh the token (automaticly refreshes and exits as 0)
    """
    sleep(1)
    if 'client_id' not in configs or 'client_secret' not in configs or len(configs['client_id']) != 64 or len(configs['client_secret']) != 64:
        sys.exit(10)
    if 'access_token' not in configs or len(configs['access_token']) != 64:
        sys.exit(11)
    else:
        sys.exit(0)

def code(flags, configs):
    res = requests.post('https://api.trakt.tv/oauth/device/code', json={'client_id': configs['client_id']})
    configs['device_code'] = res.json()['device_code']
    write_json(configs)
    print(res.json()['user_code'])

def auth(flags, configs):
    res = requests.post('https://api.trakt.tv/oauth/device/token', json={
        'client_id': configs['client_id'],
        'client_secret': configs['client_secret'],
        'code': configs['device_code'],
    })
    res_json = res.json()
    if 'access_token' in res_json:
        configs['access_token'] = res_json['access_token']
        configs['refresh_token'] = res_json['refresh_token']
        del configs['device_code']
        configs['today'] = str(date.today())
        res = requests.get('https://api.trakt.tv/users/settings', headers={
            'trakt-api-key': configs['client_id'],
            'Authorization': 'Bearer ' + configs['access_token'],
            'trakt-api-version': '2'
        })
        if res.status_code != 200:
            sys.exit(-1)
        configs['user_slug'] = res.json()['user']['ids']['slug']
        write_json(configs) 
        sys.exit(0)
    sys.exit(-1)

def media_info(flags):
    media = flags[2]
    percent_pos = flags[3][0:5]
    pause = flags[4]
    return media, percent_pos, pause
    
def query(flags, configs):
    media = media_info(flags)[0]
    infos = re.search(r'(.+)S([0-9]+).*E([0-9]+).*', media, re.IGNORECASE)
    if infos is not None and len(infos.groups()) == 3:
        name = infos.group(1)
        season_id = infos.group(2)
        ep_id = infos.group(3)
        __query_search_ep(name, season_id, ep_id, configs)
    infos = re.search(r'(.+)([1-9][0-9]{3}).*', media, re.IGNORECASE)
    if infos is not None and len(infos.groups()) == 2:
        name = infos.group(1)
        movie_year = infos.group(2)
        __query_movie(name, movie_year, configs)

def __query_search_ep(name, season, ep, configs):
    res = requests.get(
        'https://api.trakt.tv/search/show',
        params={'query': clean_name(name)},
        headers={'trakt-api-key': configs['client_id'], 'trakt-api-version': '2'}
    )
    if res.status_code != 200:
        sys.exit(-1)
    if len(res.json()) == 0:
        sys.exit(14)
    show_slug = res.json()[0]['show']['ids']['slug']
    show_trakt_id = res.json()[0]['show']['ids']['trakt']
    configs['show_slug'] = show_slug
    res = requests.get(
        'https://api.trakt.tv/shows/' + show_slug + '/seasons/' + season + '/episodes/' + ep,
        headers={'trakt-api-key': configs['client_id'], 'trakt-api-version': '2'}
    )
    if res.status_code != 200:
        sys.exit(-1)
    if len(res.json()) == 0:
        sys.exit(14)
    ep_trakt_id = res.json()['ids']['trakt']
    configs['trakt_id'] = ep_trakt_id
    write_json(configs)
    sys.exit(0)

def __query_movie(movie, year, configs):
    res = requests.get(
        'https://api.trakt.tv/search/movie',
        params={'query': clean_name(movie)},
        headers={'trakt-api-key': configs['client_id'], 'trakt-api-version': '2'}
    )
    if res.status_code != 200:
        sys.exit(-1)
    if len(res.json()) == 0:
        sys.exit(14)

    movie_trakt_id = res.json()[0]['movie']['ids']['trakt']
    configs['trakt_id'] = movie_trakt_id
    write_json(configs)
    sys.exit(0)

def scrobble(flags, configs):
    head = {
        'trakt-api-key': configs['client_id'],
        'trakt-api-version': '2',
        'Authorization': 'Bearer ' + configs['access_token']
    }
    media = media_info(flags)[0]
    position = media_info(flags)[1]
    pause = media_info(flags)[2]
    trakt_id = configs['trakt_id']
    show_slug = configs['show_slug']
    now = datetime.now(pytz.utc).isoformat() + 'Z'
    infos = re.search(r'(.+)S([0-9]+).*E([0-9]+).*', media, re.IGNORECASE)
    if infos is not None and len(infos.groups()) == 3:
        season_id = infos.group(2)
        ep_id = infos.group(3)
        scrobble_dict = {'progress': float(position),'action': 'scrobble','app_version': '2.0','episode': {'ids': {'trakt': trakt_id}}}
        scrobbled_dict = {'shows': [{'ids': {'trakt': trakt_id, 'slug': show_slug},'seasons': [{'number': int(season_id), 'episodes': [{'number': int(ep_id), 'watched_at': now}]}]}]}
    infos = re.search(r'(.+)([1-9][0-9]{3}).*', media, re.IGNORECASE)
    if infos is not None and len(infos.groups()) == 2:
        movie_year = infos.group(2)
        scrobble_dict = {'progress': float(position),'action': 'scrobble','app_version': '2.0','movie': {'year': movie_year,'ids': {'trakt': trakt_id}}}
        scrobbled_dict = {'movies': [{'ids': {'trakt': trakt_id},'watched_at': now}]}
    if float(position) < 95.0:
        if pause == "yes":
            pause_scrobble(head, scrobble_dict)
        elif pause == "no":
            start_scrobble(head, scrobble_dict)
        sys.exit(24)
    elif float(position) > 95.0:
        _scrobbled(head, scrobbled_dict)
        sys.exit(26)

def pause_scrobble(head, scrobble_dict):
    out = requests.post(
        'https://api.trakt.tv/scrobble/pause',
        headers=head,
        json=scrobble_dict
    )
    print("Pause.")
    
def start_scrobble(head, scrobble_dict):
    out = requests.post(
        'https://api.trakt.tv/scrobble/start',
        headers=head,
        json=scrobble_dict
    )
    print("Start.")
    
def _scrobbled(head, scrobbled_dict):
    out = requests.post(
        'https://api.trakt.tv/sync/history/',
        headers=head,
        json=scrobbled_dict
    )
    print("Success.")

def main():
    try:
        with open(os.path.dirname(os.path.abspath(__file__)) + '/config.json', 'r') as f:
            data = json.load(f)
    except:
        sys.exit(10)
    
    switch = {
        '--hello': hello,
        '--query': query,
        '--code': code,
        '--auth': auth,
        '--scrobble': scrobble
    }
    if sys.argv[1] in switch:
        switch[sys.argv[1]](sys.argv, data)
    else:
        sys.exit(-1)

if __name__ == "__main__":
    main()
    