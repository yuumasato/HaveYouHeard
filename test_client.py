import json
from queue import Queue
import requests
import socketio
import threading
import time

COLORS = {
        'EB5757': '9', # red
        'F2994A': '208', # orange
        'F2C94C': '214', # yellow
        '219653': '35', # green
        '65C3C9': '6', # acqua
        '2F80ED': '33' # sky blue
        }


sio = socketio.Client()

class DisplayUpdater(threading.Thread):
    def __init__(self, output_queue, print_event, *args, **kwargs):
        self.output = output_queue
        self.question = None
        self.can_print = print_event
        super().__init__(*args, **kwargs)

    def run(self):
        while True:
            self.can_print.wait()
            while not self.output.empty():
                try:
                    print(self.output.get(block=False))
                except queue.Empty:
                    pass
            if self.question:
                print(self.question)

            self.can_print.clear()

    def go_print(self):
        self.can_print.set()

    def add_question(self, question):
        self.question = question
        self.go_print()

    def clear_question(self):
        self.question = None

class GameData:
    def __init__(self):
        self.users_data = {}
        self.match_users_data = {}
        self.current_match = None
        self.my_user_data = None
        self.my_match_user_data = None

    def load_users_data(self, users_json):
        for user in users_json:
            self.users_data[user['id']] = user
        # Do I need to rewrite always rewrite my_user_data?

    def load_match_users_data(self, match_users_json):
        for match_user in match_users_json:
            self.match_users_data[match_user['id']] = match_user
            if match_user['id_user'] == self.my_user_data['id']:
                self.my_match_user_data = match_user;

    def display_match_user(self, match_user):
        user = self.users_data[match_user["id_user"]]
        if match_user['ready']:
            print_queue.put(f'\t\u001b[48;5;{COLORS[match_user["color"]]}m{user["username"]}\u001b[0m')
        else:
            print_queue.put(f'\t\u001b[38;5;{COLORS[match_user["color"]]}m{user["username"]}\u001b[0m')

    def display_all_match_users(self):
        for match_user in self.match_users_data.values():
            self.display_match_user(match_user)


class HyH(socketio.ClientNamespace):

    def __init__(self, sio, gd, printer):
        self.screen = self.get_data
        self.gd = gd
        self.display = printer

        self.sio = sio
        self.sio.connect('http://localhost:5000')
        #self.sio.connect('https://haveyouheard-game.herokuapp.com/socket.io/')

    def run(self):
        while self.screen:
            self.screen = self.screen()

    def get_data(self):
        while True:
            self.display.add_question('Type your user name: ')
            username = input()
            self.display.clear_question()

            pload = { 'username': username, 'country': 'Brazil' }
            r = make_request('post', 'add_user', pload)
            if r.status_code == 200:
                self.gd.my_user_data = r.json()['data']
                print_queue.put(f'User "{self.gd.my_user_data["username"]}" added successfully. ({self.gd.my_user_data["id"]})\n')
                self.display.go_print()
                return self.get_matched
            else:
                print_queue.put(f'Error adding user "{self.gd.my_user_data["username"]}". (error code: {r.status_code})\n')
                self.display.go_print()

    def get_matched(self):
        ## Create or find match
        match_info_received = False
        while not match_info_received:
            self.display.add_question('Would you like to:\n c) Create a match\n j) Join an existing match')
            create_or_join = input()
            self.display.clear_question()
            if create_or_join == 'c':
                print_queue.put('Alright, creating a match')
                self.display.go_print()
                pload = {'user_data': self.gd.my_user_data, 'is_public': False }
                r = make_request('post', 'create_match', pload)
                if r.status_code == 200:
                    self.gd.current_match = r.json()['data']
                    match_info_received = True

            elif create_or_join == 'j':
                self.display.add_question('Type the match number you''d like to join:')
                match_id = input()
                self.display.clear_question()
                pload = {'id': match_id }
                r = make_request('get', 'get_match', pload)
                if r.status_code == 200:
                    self.gd.current_match = r.json()['data']
                    match_info_received = True
                else:
                    print_queue.put(f'Match "{match_id}" not found')
                self.display.go_print()

            else:
                print_queue.put('Please, choose between C or J')
                self.display.go_print()
        return self.match_lobby

    def match_lobby(self):
        pload = {'user_data': self.gd.my_user_data, 'match_data': self.gd.current_match, 'is_player': True}
        r = make_request('post', 'join_match', pload)
        if r.status_code == 200:
            print_queue.put(r.json())
            self.display.go_print()
            match_user = r.json()['data']
            match_users_list = [ match_user ]

            pload = {'user_data': self.gd.my_user_data, 'match_users_data': match_users_list, 'match_data': self.gd.current_match }
            self.sio.emit('join', json.dumps(pload))
        else:
            print_queue.put(f'Could not join match "{match_id}"')
            return self.get_matched
        while self.gd.current_match['status'] == 'finding_users':
            if self.gd.my_match_user_data['ready']:
                self.display.add_question('Still ready? (y/n)')
            elif:
                self.display.add_question('Are you ready? (y/n)')
            ready = input()
            self.display.clear_question()
            if ready == 'y':
                self.gd.my_match_user_data['ready'] = True
                self.emit_user_readiness()
            elif ready == 'n':
                self.gd.my_match_user_data['ready'] = False
                self.emit_user_readiness()

    def emit_user_readiness(self):
        data = {'match_user_data': self.gd.my_match_user_data, 'match_data': self.gd.current_match }
        pload = {'action': 'user_ready', 'data': data }
        self.sio.emit('match_event', json.dumps(pload))


print_queue = Queue()
print_event = threading.Event()
printer = DisplayUpdater(print_queue, print_event)

gd = GameData()


@sio.event
def connect():
    print_queue.put('connection established')
    printer.go_print()
@sio.event
def my_message(data):
    #print('message received with ', data)
    #sio.emit('my response', {'response': 'my response'})
    pass

@sio.event
def disconnect(self):
    print_queue.put('disconnected from server')
    printer.go_print()

@sio.event
def match_response(data):

    action = data['action']

    if action == 'join_match':
        match_data = data['data']['match_data']
        users_data_raw = data['data']['users_data']
        match_users_data_raw = data['data']['match_users_data']

        gd.load_users_data(users_data_raw)
        gd.load_match_users_data(match_users_data_raw)
        gd.current_match = match_data

        print_queue.put(f'======= Match number {gd.current_match["id"]}')
        print_queue.put(f'======= Status: {gd.current_match["status"]}')
        gd.display_all_match_users()
        printer.go_print()

        # Auto send user ready
        #self._user_is_ready()
    elif action == 'user_ready':
        print_queue.put(f'message received with {data}')
        match_user_ready = data['data']['match_user_data']
        gd.match_users_data[match_user_ready['id']] = match_user_ready

        gd.display_all_match_users()
        printer.go_print()

input_queue = Queue()
class InputHandler(threading.Thread):
    def __init__(self, q):
        self.queue = q
        self.ask = False
        super().__init__(*args, **kwargs)

    def run(self):
            if self.question:
                user_input = input(self.question)
            else:
                time.sleep(1)

def make_request(method, url_slug, data):
    http_uri = 'http://localhost:5000/'
    #http_uri = 'http://haveyouheard-game.herokuapp.com:5000/'
    headers = {'Content-Type': 'application/json'}

    if method == 'get':
        r = requests.get(http_uri+url_slug, headers=headers, data=json.dumps(data))
    elif method == 'post':
        r = requests.post(http_uri+url_slug, headers=headers, data=json.dumps(data))

    return r


printer.start()
game = HyH(sio, gd, printer)
game.run()
