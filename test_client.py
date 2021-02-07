import json
import requests
import socketio

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

@sio.event
def match_response(data):
    print('message received with ', data)
    

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
joined_match = False
while not joined_match:
    create_or_join = input('Would you like to:\n C) Create a match\n J) Join an existing match\n')
    if create_or_join == 'C':
        print('Alright, creating a match')
        pload = {'user_data': user_data, 'is_public': False }
        r = make_request('post', 'create_match', pload)
        if r.status_code == 200:
            current_match = r.json()['data']
            joined_match = True

    elif create_or_join == 'J':
        match_id = input('Type the match number you''d like to join: ')
        pload = {'id': match_id }
        r = make_request('get', 'get_match', pload)
        if r.status_code == 200:
            current_match = r.json()['data']
            joined_match = True
        else:
            print('Match "{match_id}" not found')

    else:
        print('Please, choose between C or J')

pload = {'user_data': user_data, 'match_data': current_match, 'is_player': True}
r = make_request('post', 'join_match', pload)
if r.status_code == 200:
    print(r.json())
    match_user = r.json()['data']
    print(match_user)
    match_users_list = [ match_user ]

    pload = {'user_data': user_data, 'match_users_data': match_users_list, 'match_data': current_match }
    sio.emit('join', json.dumps(pload))

    print(f'Joined match number {current_match["id"]}')
else:
    print('Match "{match_id}" not found')

# I'm in a room now!

sio.wait()
