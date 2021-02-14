import json
import requests
import socketio
from types import SimpleNamespace

COLORS = {
        'EB5757': '9', # red
        'F2994A': '208', # orange
        'F2C94C': '214', # yellow
        '219653': '35', # green
        '65c3c9': '6', # acqua
        '2F80ED': '33' # sky blue
        }
sio = socketio.Client()

@sio.event
def connect():
    print('connection established')

@sio.event
def my_message(data):
    print('message received with ', data)
    #sio.emit('my response', {'response': 'my response'})

@sio.event
def disconnect():
    print('disconnected from server')

users_data = {}
def load_users_data(users_json):
    global users_data
    for user in users_json:
        users_data[user['id']] = user

@sio.event
def match_response(data):
    global users_data
    print('message received with ', data)
    action = data['action']

    if action == 'join_match':
        match_data = data['data']['match_data']
        users_data_raw = data['data']['users_data']
        match_users_data = data['data']['match_users_data']

        load_users_data(users_data_raw)
        print(f'======= Joined match number {current_match["id"]}')
        for match_user in match_users_data:
            user = users_data[match_user["id_user"]]
            print(f'\t\u001b[38;5;{COLORS[match_user["color"]]}m{user["username"]}\u001b[0m')
    

sio.connect('http://localhost:5000')

def make_request(method, url_slug, data):
    http_uri = 'http://localhost:5000/'
    headers = {'Content-Type': 'application/json'}

    if method == 'get':
        r = requests.get(http_uri+url_slug, headers=headers, data=json.dumps(data))
    elif method == 'post':
        r = requests.post(http_uri+url_slug, headers=headers, data=json.dumps(data))

    return r

username = input('Type your user name: ')

pload = { 'username': username, 'country': 'Brazil' }
r = make_request('post', 'add_user', pload)
if r.status_code == 200:
    user_data = r.json()['data']
    print(f'User "{user_data["username"]}" added successfully. ({user_data["id"]})\n')

## Create or join match
match_info_received = False
while not match_info_received:
    create_or_join = input('Would you like to:\n C) Create a match\n J) Join an existing match\n')
    if create_or_join == 'C':
        print('Alright, creating a match')
        pload = {'user_data': user_data, 'is_public': False }
        r = make_request('post', 'create_match', pload)
        if r.status_code == 200:
            current_match = r.json()['data']
            match_info_received = True

    elif create_or_join == 'J':
        match_id = input('Type the match number you''d like to join: ')
        pload = {'id': match_id }
        r = make_request('get', 'get_match', pload)
        if r.status_code == 200:
            current_match = r.json()['data']
            match_info_received = True
        else:
            print('Match "{match_id}" not found')

    else:
        print('Please, choose between C or J')
print(f'Match info: {current_match}')

pload = {'user_data': user_data, 'match_data': current_match, 'is_player': True}
r = make_request('post', 'join_match', pload)
if r.status_code == 200:
    print(r.json())
    match_user = r.json()['data']
    print(match_user)
    match_users_list = [ match_user ]

    pload = {'user_data': user_data, 'match_users_data': match_users_list, 'match_data': current_match }
    sio.emit('join', json.dumps(pload))
else:
    print('Match "{match_id}" not found')

# I'm in a room now!

sio.wait()
