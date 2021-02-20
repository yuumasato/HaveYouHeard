import json
from queue import Queue
import requests
import select
import socketio
import sys
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

    def add_question(self, question, print_now):
        self.question = question
        if print_now:
            self.go_print()

    def clear_question(self):
        self.question = None

class GameData:
    def __init__(self):
        self.users_data = {}
        self.match_users_data = {}
        self.current_match = {}
        self.my_user_data = None
        self.my_match_user_data = None

        self.game_started = False

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

    def display_match(self):
        print_queue.put(f'======= Match number {self.current_match["id"]}')
        print_queue.put(f'======= Status: {self.current_match["status"]}')
        for match_user in self.match_users_data.values():
            self.display_match_user(match_user)


class HyH(socketio.ClientNamespace):

    def __init__(self, sio, gd, printer):
        self.screen = self.get_data
        self.gd = gd
        self.display = printer

        self.sio = sio
        self.sio.connect('http://192.168.0.187:5000/socket-io/')
        #self.sio.connect('https://haveyouheard.rj.r.appspot.com/socket.io/')

    def run(self):
        while self.screen:
            self.screen = self.screen()

    def get_data(self):
        while True:
            username = ""
            while username == "":
                self.display.add_question('Type your user name: ', True)
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
        got_matched = False
        while not got_matched:
            self.display.add_question('Would you like to:\n c) Create a match\n j) Join an existing match', True)
            create_or_join = input()
            self.display.clear_question()
            if create_or_join == 'c':
                print_queue.put('Alright, creating a match')
                self.display.go_print()
                pload = {'user_data': self.gd.my_user_data, 'is_public': False }
                r = make_request('post', 'create_match', pload)
                if r.status_code == 200:
                    self.gd.current_match = r.json()['data']

            elif create_or_join == 'j':
                self.display.add_question('Type the match number you''d like to join:', True)
                match_id = input()
                self.display.clear_question()
                pload = {'id': match_id }
                r = make_request('get', 'get_match', pload)
                if r.status_code == 200:
                    self.gd.current_match = r.json()['data']
                else:
                    print_queue.put(f'Match "{match_id}" not found')
                    continue
                self.display.go_print()

            else:
                print_queue.put('Please, choose between C or J')
                self.display.go_print()
                continue

            # Socket join the match
            pload = {'user_data': self.gd.my_user_data, 'match_data': self.gd.current_match, 'is_player': True}
            r = make_request('post', 'join_match', pload)
            if r.status_code == 200:
                match_user = r.json()['data']
                match_users_list = [ match_user ]

                pload = {'user_data': self.gd.my_user_data, 'match_users_data': match_users_list, 'match_data': self.gd.current_match }
                self.sio.emit('join', json.dumps(pload))
                got_matched = True
            else:
                print_queue.put(f'Could not join match "{match_id}"')
        return self.match_lobby

    def match_lobby(self):
        game_started = False
        while not game_started:
            # Hanging in the Lobby
            input_ready, _, _ = select.select([sys.stdin], [], [], 0.5)
            if input_ready:
                ready = sys.stdin.readline()
                self.display.clear_question()
                if self.gd.my_match_user_data is not None and ready == '\n':
                    self.gd.my_match_user_data['ready'] = not self.gd.my_match_user_data['ready']
                    self.emit_user_readiness()
                else:
                    pass
            if self.gd.game_started:
                return self.selecting_chars

    def emit_user_readiness(self):
        data = {'match_user_data': self.gd.my_match_user_data, 'match_data': self.gd.current_match }
        pload = {'action': 'user_ready', 'data': data }
        self.sio.emit('match_event', json.dumps(pload))

    def selecting_chars(self):
        print_queue.put('Selecting Characters')
        printer.go_print()


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
def disconnect():
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

        old_current_match = gd.current_match
        gd.current_match = match_data

    elif action == 'user_ready':
        #print(f'received {action}')
        #print_queue.put(f'message received with {data}')

        match_data = data['data']['match_data']

        old_current_match = gd.current_match
        gd.current_match = match_data
        match_user_ready = data['data']['match_user_data']
        gd.match_users_data[match_user_ready['id']] = match_user_ready

    if gd.current_match['status'] == 'finding_users':
        if old_current_match.get('status', '') == 'starting_game':
            print_queue.put('Start cancelled!')
        if not gd.my_match_user_data or gd.my_match_user_data['ready'] == False:
            printer.add_question('Ready? (Enter)', False)
        else:
            printer.add_question('Not ready? (Enter)', False)
        gd.display_match()
        printer.go_print()
    elif gd.current_match['status'] == 'starting_game':
        printer.add_question('Not ready? (Enter)', False)
        # Start count down
        print('Count down', flush=True)
        for i in range(5, -1, -1):
            if gd.current_match['status'] == 'starting_game':
                print(f'{i}', end=' ', flush=True)
                time.sleep(1)
            elif gd.current_match['status'] == 'finding_users':
                break
        if gd.current_match['status'] == 'starting_game':
            # Emit status
            print('Starting...', flush=True)
            data = {'match_data': gd.current_match }
            pload = {'action': 'check_match_status', 'data': data }
            sio.emit('user_event', json.dumps(pload))

@sio.event
def user_response(data):
    action = data['action']

    print(f'received {action}')
    if action == 'check_match_status':
        status = data['data']['status']
        if status == 'starting_game':
            printer.clear_question()
            gd.game_started = True



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
    http_uri = 'http://192.168.0.187:5000/'
    #http_uri = 'https://haveyouheard-game.herokuapp.com/'
    headers = {'Content-Type': 'application/json'}

    if method == 'get':
        r = requests.get(http_uri+url_slug, headers=headers, data=json.dumps(data))
    elif method == 'post':
        r = requests.post(http_uri+url_slug, headers=headers, data=json.dumps(data))

    return r


printer.start()
game = HyH(sio, gd, printer)
game.run()
