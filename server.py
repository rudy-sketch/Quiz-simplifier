import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
import json
import random
import copy
import threading
from datetime import datetime
import secrets
import time

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'une_cle_secrete_par_defaut')
app.config['UPLOAD_FOLDER'] = '.'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- GESTION DES FICHIERS DE DONNÉES (JSON) ---
CONFIG_FILE = 'config.json'
QUESTIONS_SIMPLES_FILE = 'questions_simples.json'
QUESTIONS_INTRUS_FILE = 'questions_intrus.json'
QUESTIONS_ESTIMATION_FILE = 'questions_estimation.json'
HISTORY_FILE = 'game_history.json'
CHANGELOG_FILE = 'changelog.json'
STATS_FILE = 'player_stats.json'

CONFIG = {}
QUESTION_BANK = {}
GAME_HISTORY = []
CHANGELOG_ENTRIES = []
PLAYER_STATS = {}
json_lock = threading.Lock()

def load_data():
    """Charge toutes les données depuis les fichiers JSON."""
    global CONFIG, QUESTION_BANK, GAME_HISTORY, CHANGELOG_ENTRIES, PLAYER_STATS
    with json_lock:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: CONFIG = json.load(f)
            if 'game_modes_enabled' not in CONFIG:
                CONFIG['game_modes_enabled'] = {"simple": True, "buzzer": True, "intrus": True, "estimation": True}
            if 'points_config' not in CONFIG:
                CONFIG['points_config'] = {"simple": 10, "buzzer": 10, "intrus": 50, "estimation_perfect": 150, "estimation_close": 100}
            if 'music_default_on' not in CONFIG: CONFIG['music_default_on'] = False
            print("Fichier de configuration chargé.")
        except (FileNotFoundError, json.JSONDecodeError):
            CONFIG = {
                "game_title": "Quiz Night Arena", "admin_password": "admin",
                "qr_logo_path": "/static/img/logo.png", "tts_default_on": False,
                "game_modes": {"simple": "Le Remue-Méninges", "buzzer": "Le Massacre à la Sonnette", "intrus": "Stop ou la Gaffe"},
                "easter_eggs": {"tyson": True, "lorie": True, "corine": True, "oceane": True, "dimitri": True, "jc": True, "marie": True},
                "active_themes": {"simples": [], "intrus": []},
                "game_rules": {"questions_per_player_simple": 2, "questions_total_buzzer": 5, "questions_per_player_intrus": 1, "questions_total_estimation": 5},
                "music_default_on": False,
                "game_modes_enabled": {"simple": True, "buzzer": True, "intrus": True, "estimation": True},
                "points_config": {"simple": 10, "buzzer": 10, "intrus": 50, "estimation_perfect": 150, "estimation_close": 100}
            }
            save_config()
        
        try:
            with open(QUESTIONS_SIMPLES_FILE, 'r', encoding='utf-8') as f: QUESTION_BANK['questions_simples'] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): QUESTION_BANK['questions_simples'] = {}
        try:
            with open(QUESTIONS_INTRUS_FILE, 'r', encoding='utf-8') as f: QUESTION_BANK['questions_intrus'] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): QUESTION_BANK['questions_intrus'] = []
        try:
            with open(QUESTIONS_ESTIMATION_FILE, 'r', encoding='utf-8') as f: QUESTION_BANK['questions_estimation'] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): QUESTION_BANK['questions_estimation'] = []
        print("Banques de questions chargées.")

        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f: GAME_HISTORY = json.load(f)
            print("Historique des parties chargé.")
        except (FileNotFoundError, json.JSONDecodeError):
            GAME_HISTORY = []; save_history()

        try:
            with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f: CHANGELOG_ENTRIES = json.load(f)
            print("Fichier de nouveautés chargé.")
        except (FileNotFoundError, json.JSONDecodeError):
            CHANGELOG_ENTRIES = []
            save_changelog()
            
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f: PLAYER_STATS = json.load(f)
            if not isinstance(PLAYER_STATS, dict):
                PLAYER_STATS = {}
                save_stats()
            print("Fichier de statistiques chargé.")
        except (FileNotFoundError, json.JSONDecodeError):
            PLAYER_STATS = {}
            save_stats()

def save_config():
    with json_lock:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(CONFIG, f, indent=4, ensure_ascii=False)
        print("Fichier de configuration sauvegardé.")

def save_questions(q_type):
    with json_lock:
        filename = QUESTIONS_SIMPLES_FILE
        if q_type == 'questions_intrus':
            filename = QUESTIONS_INTRUS_FILE
        elif q_type == 'questions_estimation':
            filename = QUESTIONS_ESTIMATION_FILE
        
        data = QUESTION_BANK.get(q_type, [])
        if q_type == 'questions_simples':
            data = QUESTION_BANK.get(q_type, {})

        with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Banque de questions '{q_type}' sauvegardée.")

def save_history():
    with json_lock:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f: json.dump(GAME_HISTORY, f, indent=4, ensure_ascii=False)
        print("Historique des parties sauvegardé.")

def save_changelog():
    with json_lock:
        with open(CHANGELOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(CHANGELOG_ENTRIES, f, indent=4, ensure_ascii=False)
        print("Fichier de nouveautés sauvegardé.")

def save_stats():
    with json_lock:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(PLAYER_STATS, f, indent=4, ensure_ascii=False)
        print("Fichier de statistiques sauvegardé.")

# --- GESTION DE L'ÉTAT DU JEU ---
game_states = {}
admin_sids = set()

def get_dashboard_stats():
    simple_questions_data = QUESTION_BANK.get('questions_simples', {})
    simple_themes_count = len(simple_questions_data)
    simple_questions_count = sum(len(q_list) for q_list in simple_questions_data.values())
    intrus_questions_count = len(QUESTION_BANK.get('questions_intrus', []))
    active_rooms_count = len(game_states)
    total_players_count = sum(len([p for p in state['players'] if not p.get('is_disconnected')]) for state in game_states.values())
    
    return {
        "simple_themes_count": simple_themes_count,
        "simple_questions_count": simple_questions_count,
        "intrus_questions_count": intrus_questions_count,
        "active_rooms_count": active_rooms_count,
        "total_players_count": total_players_count,
    }

def create_new_game_state():
    return { "players": [], "game_started": False, "current_mode_key": None, "current_question_data": None, "current_player_index": -1, "questions_answered_in_mode": 0, "mode_question_count": 0, "info_text": "En attente des joueurs...", "buzzer_active": False, "buzzer_winner_sid": None, "buzzer_has_answered": [], "revealed_answers": [], "question_bank_session": copy.deepcopy(QUESTION_BANK), "stop_or_encore_state": {}, "host_sid": None }

def broadcast_to_admins():
    for sid in admin_sids:
        socketio.emit('update_admin_view', {
            'game_states': game_states, 
            'game_history': GAME_HISTORY,
            'dashboard_stats': get_dashboard_stats()
        }, room=sid)

def get_simplified_rooms():
    simplified = {}
    for room_id, state in game_states.items():
        simplified[room_id] = { "player_count": len([p for p in state['players'] if not p.get('is_disconnected')]), "is_started": state['game_started'] }
    return simplified

def broadcast_room_list():
    socketio.emit('update_room_list', {'rooms': get_simplified_rooms()})

def cleanup_disconnected_players():
    while True:
        with json_lock:
            for room_id, state in list(game_states.items()):
                original_player_count = len(state['players'])
                state['players'] = [p for p in state['players'] if not p.get('is_disconnected') or (time.time() - p.get('disconnected_at', 0)) < 300]
                if len(state['players']) < original_player_count:
                    print(f"Nettoyage des joueurs déconnectés dans la salle {room_id}")
                    socketio.emit('update_state', state, room=room_id)
                    broadcast_to_admins(); broadcast_room_list()
        socketio.sleep(60)

# --- ROUTES HTTP ---
def get_seasonal_theme():
    today = datetime.now()
    if today.month == 10 and 24 <= today.day <= 31: return "halloween"
    if today.month == 12: return "christmas"
    if (today.month == 3 and today.day >= 20) or (today.month == 4 and today.day <= 20): return "easter"
    return None

@app.route('/')
def main_screen(): 
    return render_template('index.html', 
                           game_title=CONFIG.get('game_title', 'Quiz Night Arena'), 
                           seasonal_theme=get_seasonal_theme(),
                           music_default_on=CONFIG.get('music_default_on', False))

@app.route('/player')
def player_controller(): return render_template('player.html', seasonal_theme=get_seasonal_theme())

@app.route('/admin')
def admin_panel(): return render_template('admin.html', game_title=CONFIG.get('game_title', 'Quiz Night Arena'), seasonal_theme=get_seasonal_theme())

@app.route('/changelog')
def changelog_page(): return render_template('changelog.html', game_title=CONFIG.get('game_title', 'Quiz Night Arena'), entries=CHANGELOG_ENTRIES)

@app.route('/history')
def history_page():
    return render_template('history.html', 
                           game_title=CONFIG.get('game_title', 'Quiz Night Arena'), 
                           history=GAME_HISTORY)

@app.route('/stats')
def stats_page():
    leaderboards = {
        "most_wins": sorted(PLAYER_STATS.values(), key=lambda x: x.get('wins', 0), reverse=True)[:5],
        "highest_score": sorted(PLAYER_STATS.values(), key=lambda x: x.get('total_score', 0), reverse=True)[:5],
        "specialist_simple": sorted(PLAYER_STATS.values(), key=lambda x: x.get('score_simple', 0), reverse=True)[:3],
        "specialist_buzzer": sorted(PLAYER_STATS.values(), key=lambda x: x.get('score_buzzer', 0), reverse=True)[:3],
        "specialist_intrus": sorted(PLAYER_STATS.values(), key=lambda x: x.get('score_intrus', 0), reverse=True)[:3]
    }
    return render_template('stats.html', game_title=CONFIG.get('game_title', 'Quiz Night Arena'), leaderboards=leaderboards)

# --- LOGIQUE DE JEU ---
def get_local_question(mode_key, session_bank):
    if mode_key == 'estimation':
        q_type = 'questions_estimation'
        bank = session_bank.get(q_type, [])
        if not bank:
            session_bank[q_type] = copy.deepcopy(QUESTION_BANK.get(q_type, []))
            bank = session_bank[q_type]
        if not bank: return None
        return bank.pop(random.randrange(len(bank)))

    q_type = 'questions_simples' if mode_key in ['simple', 'buzzer', 'sudden_death'] else 'questions_intrus'
    
    if q_type == 'questions_simples':
        bank = session_bank.get(q_type, {})
        active_simple_themes = CONFIG.get('active_themes', {}).get('simples', [])
        
        all_themes_in_bank = {theme: [q for q in questions if q.get('active', True)] for theme, questions in bank.items()}
        all_themes_in_bank = {theme: questions for theme, questions in all_themes_in_bank.items() if questions}

        available_themes = list(all_themes_in_bank.keys())
        if active_simple_themes:
            available_themes = [theme for theme in available_themes if theme in active_simple_themes]

        if not available_themes:
            session_bank[q_type] = copy.deepcopy(QUESTION_BANK.get(q_type, {}))
            bank = session_bank[q_type]
            all_themes_in_bank = {theme: [q for q in questions if q.get('active', True)] for theme, questions in bank.items()}
            all_themes_in_bank = {theme: questions for theme, questions in all_themes_in_bank.items() if questions}
            available_themes = list(all_themes_in_bank.keys())
            if active_simple_themes:
                available_themes = [theme for theme in available_themes if theme in active_simple_themes]
        
        if not available_themes: return None
        
        chosen_theme = random.choice(available_themes)
        questions_in_theme = all_themes_in_bank[chosen_theme]
        question = questions_in_theme.pop(random.randrange(len(questions_in_theme)))
        
        original_bank_questions = session_bank[q_type][chosen_theme]
        session_bank[q_type][chosen_theme] = [q for q in original_bank_questions if q != question]
        if not session_bank[q_type][chosen_theme]: del session_bank[q_type][chosen_theme]

        question['theme'] = chosen_theme
        return question

    else: # Intrus
        full_bank = session_bank.get(q_type, [])
        active_intrus_themes = CONFIG.get('active_themes', {}).get('intrus', [])
        
        bank = [q for q in full_bank if q.get('active', True)]
        
        if active_intrus_themes:
            bank = [q for q in bank if q.get('theme') in active_intrus_themes]
            
        if not bank:
            session_bank[q_type] = copy.deepcopy(QUESTION_BANK.get(q_type, []))
            full_bank = session_bank[q_type]
            bank = [q for q in full_bank if q.get('active', True)]
            if active_intrus_themes:
                bank = [q for q in bank if q.get('theme') in active_intrus_themes]
                
        if not bank: return None
        
        question_to_return = bank.pop(random.randrange(len(bank)))
        
        session_bank[q_type] = [q for q in session_bank[q_type] if q != question_to_return]
        
        return question_to_return

def get_next_player_index(state):
    active_players = [p for p in state['players'] if not p.get('is_disconnected')]
    if not active_players: return -1
    if state['current_player_index'] == -1: return state['players'].index(active_players[0])
    current_player_sid = state['players'][state['current_player_index']]['sid']
    current_idx_in_actives = next((i for i, p in enumerate(active_players) if p['sid'] == current_player_sid), -1)
    next_idx_in_actives = (current_idx_in_actives + 1) % len(active_players)
    next_player = active_players[next_idx_in_actives]
    return state['players'].index(next_player)

def start_next_mode(room_id):
    state = game_states.get(room_id)
    if not state: return
    
    enabled_modes_config = CONFIG.get('game_modes_enabled', {})
    full_order = ["simple", "buzzer", "intrus", "estimation"]
    game_modes_order = [mode for mode in full_order if enabled_modes_config.get(mode, False)]

    if not game_modes_order:
        game_modes_order = ["simple"]

    current_index = game_modes_order.index(state['current_mode_key']) if state['current_mode_key'] in game_modes_order else -1
    
    if current_index >= len(game_modes_order) - 1:
        end_game(room_id)
        return

    state['current_mode_key'] = game_modes_order[current_index + 1]
    
    state['questions_answered_in_mode'] = 0
    rules = CONFIG.get('game_rules', {})
    
    mode_configs = {
        "simple": (CONFIG['game_modes']['simple'], len(state['players']) * rules.get('questions_per_player_simple', 2), start_question_simple),
        "buzzer": (CONFIG['game_modes']['buzzer'], rules.get('questions_total_buzzer', 5), start_question_buzzer),
        "intrus": (CONFIG['game_modes']['intrus'], len(state['players']) * rules.get('questions_per_player_intrus', 1), start_question_intrus),
        "estimation": ("Le Thermomètre", rules.get('questions_total_estimation', 5), start_question_estimation)
    }
    
    name, count, task = mode_configs[state['current_mode_key']]
    state['info_text'] = f"Mode: {name}"
    state['mode_question_count'] = count

    if state['current_mode_key'] == 'buzzer':
        for p in state['players']: p['score_round'] = 0

    socketio.emit('show_mode_title', {'title': name}, room=room_id)
    socketio.sleep(3)
    socketio.start_background_task(task, room_id)

def start_question_simple(room_id):
    state = game_states.get(room_id)
    if not state: return
    state['questions_answered_in_mode'] += 1
    if state['questions_answered_in_mode'] > state['mode_question_count']: start_next_mode(room_id); return
    state['current_player_index'] = get_next_player_index(state)
    current_player = state['players'][state['current_player_index']]
    state['info_text'] = f"Au tour de {current_player['name']}"
    question_data = get_local_question('simple', state['question_bank_session'])
    if not question_data: state['info_text'] = "Plus de questions !"; socketio.emit('update_state', state, room=room_id); socketio.sleep(3); start_next_mode(room_id); return
    random.shuffle(question_data['reponses'])
    state['current_question_data'] = question_data
    socketio.emit('update_state', state, room=room_id)
    for p in state['players']:
        is_my_turn = p['sid'] == current_player['sid']
        socketio.emit('update_player_view', {'view': 'question', 'data': {'question': question_data, 'is_my_turn': is_my_turn}, 'state': state}, room=p['sid'])

def start_question_buzzer(room_id):
    state = game_states.get(room_id)
    if not state: return
    state['questions_answered_in_mode'] += 1
    if state['questions_answered_in_mode'] > state['mode_question_count']:
        winner = max(state['players'], key=lambda p: p.get('score_round', 0), default=None)
        if winner and winner.get('score_round', 0) > 0:
            winner['has_multiplier'] = True; state['info_text'] = f"{winner['name']} gagne le bonus Score x2 !"
        else: state['info_text'] = "Pas de bonus ce tour-ci."
        socketio.emit('update_state', state, room=room_id); socketio.sleep(3); start_next_mode(room_id); return
    state['info_text'] = f"Question Bonus {state['questions_answered_in_mode']}/{state['mode_question_count']}"
    state['buzzer_active'] = True; state['buzzer_winner_sid'] = None; state['buzzer_has_answered'] = []
    question_data = get_local_question('buzzer', state['question_bank_session'])
    if not question_data: state['info_text'] = "Plus de questions !"; socketio.emit('update_state', state, room=room_id); socketio.sleep(3); start_next_mode(room_id); return
    random.shuffle(question_data['reponses'])
    state['current_question_data'] = question_data
    socketio.emit('update_state', state, room=room_id)
    socketio.emit('update_player_view', {'view': 'buzzer', 'data': {'question': question_data}, 'state': state}, room=room_id)

def start_question_intrus(room_id):
    state = game_states.get(room_id)
    if not state: return
    state['questions_answered_in_mode'] += 1
    if state['questions_answered_in_mode'] > state['mode_question_count']: start_next_mode(room_id); return
    state['current_player_index'] = get_next_player_index(state)
    current_player = state['players'][state['current_player_index']]
    state['info_text'] = f"Stop ou la Gaffe : Au tour de {current_player['name']}"
    question_data = get_local_question('intrus', state['question_bank_session'])
    if not question_data: state['info_text'] = "Plus de questions !"; socketio.emit('update_state', state, room=room_id); socketio.sleep(3); start_next_mode(room_id); return
    random.shuffle(question_data['reponses'])
    state['current_question_data'] = question_data
    state['stop_or_encore_state'] = {'sid': current_player['sid'], 'points_accumulated': 0, 'revealed': []}
    socketio.emit('update_state', state, room=room_id)
    for p in state['players']:
        is_my_turn = p['sid'] == current_player['sid']
        socketio.emit('update_player_view', {'view': 'question', 'data': {'question': question_data, 'is_my_turn': is_my_turn, 'revealed': []}, 'state': state}, room=p['sid'])

def start_question_estimation(room_id):
    state = game_states.get(room_id)
    if not state: return

    state['questions_answered_in_mode'] += 1
    if state['questions_answered_in_mode'] > state['mode_question_count']:
        start_next_mode(room_id)
        return
    
    state['info_text'] = f"Estimation {state['questions_answered_in_mode']}/{state['mode_question_count']}"
    
    question_data = get_local_question('estimation', state['question_bank_session'])
    if not question_data:
        state['info_text'] = "Plus de questions !"; socketio.emit('update_state', state, room=room_id); socketio.sleep(3); start_next_mode(room_id); return
    
    state['current_question_data'] = question_data
    for p in state['players']:
        p['current_answer'] = None

    socketio.emit('update_state', state, room=room_id)
    socketio.emit('update_player_view', {'view': 'estimation', 'data': {'question': question_data}, 'state': state}, room=room_id)

def start_sudden_death(room_id, tied_players):
    state = game_states.get(room_id)
    if not state: return
    state['current_mode_key'] = 'sudden_death'; state['info_text'] = "ÉGALITÉ ! Mort Subite !"
    state['buzzer_active'] = True; state['buzzer_winner_sid'] = None; state['buzzer_has_answered'] = []
    state['players'] = [p for p in state['players'] if p['sid'] in [player['sid'] for player in tied_players]]
    question_data = get_local_question('sudden_death', state['question_bank_session'])
    state['current_question_data'] = question_data
    socketio.emit('show_mode_title', {'title': "MORT SUBITE"}, room=room_id)
    socketio.sleep(3)
    socketio.emit('update_state', state, room=room_id)
    for player in state['players']:
        socketio.emit('update_player_view', {'view': 'buzzer', 'data': {'question': question_data}, 'state': state}, room=player['sid'])

def end_game(room_id):
    state = game_states.get(room_id)
    if not state or not state['players']: return
    max_score = max(p['score'] for p in state['players'])
    winners = [p for p in state['players'] if p['score'] == max_score]
    if len(winners) > 1 and state['current_mode_key'] != 'sudden_death':
        start_sudden_death(room_id, winners)
        return
    state['game_started'] = False
    winner = max(state['players'], key=lambda p: p['score'], default=None)
    state['info_text'] = "Partie terminée !"

    for player_data in state['players']:
        name_key = player_data['name'].lower()
        if name_key not in PLAYER_STATS:
            PLAYER_STATS[name_key] = { 
                "name": player_data['name'], "games_played": 0, "wins": 0, 
                "total_score": 0, "best_score": 0, "score_simple": 0, 
                "score_buzzer": 0, "score_intrus": 0, "grand_slams": 0,
                "tacticien_wins": 0, "win_streak": 0, "max_win_streak": 0
            }
        
        stats = PLAYER_STATS[name_key]
        stats['games_played'] += 1
        stats['total_score'] += player_data['score']
        if player_data['score'] > stats.get('best_score', 0): stats['best_score'] = player_data['score']
        stats['score_simple'] = stats.get('score_simple', 0) + player_data.get('game_score_simple', 0)
        stats['score_buzzer'] = stats.get('score_buzzer', 0) + player_data.get('game_score_buzzer', 0)
        stats['score_intrus'] = stats.get('score_intrus', 0) + player_data.get('game_score_intrus', 0)

        if winner and player_data['sid'] == winner['sid']:
            stats['wins'] += 1
            current_streak = stats.get('win_streak', 0) + 1
            stats['win_streak'] = current_streak
            if current_streak > stats.get('max_win_streak', 0):
                stats['max_win_streak'] = current_streak
            if player_data.get('used_multiplier'):
                stats['tacticien_wins'] = stats.get('tacticien_wins', 0) + 1
        else:
            stats['win_streak'] = 0

    save_stats()
    
    game_result = {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"), "room_id": room_id,
        "winner": winner['name'] if winner else "Aucun",
        "players": sorted([{"name": p['name'], "score": p['score']} for p in state['players']], key=lambda x: x['score'], reverse=True)
    }
    GAME_HISTORY.insert(0, game_result)
    save_history()
    socketio.emit('end_game', {'winner': winner}, room=room_id)
    broadcast_to_admins()

# --- GESTIONNAIRES D'ÉVÉNEMENTS SOCKET.IO ---
@socketio.on('connect')
def handle_connect():
    print(f"Client connecté: {request.sid}")
    emit('update_room_list', {'rooms': get_simplified_rooms()})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client déconnecté: {request.sid}")
    if request.sid in admin_sids: admin_sids.remove(request.sid)
    for room, state in list(game_states.items()):
        player = next((p for p in state["players"] if p.get("sid") == request.sid), None)
        if player:
            if state['game_started']:
                player['is_disconnected'] = True; player['disconnected_at'] = time.time()
                print(f"Joueur {player['name']} marqué comme déconnecté.")
            else:
                state["players"].remove(player)
                if not state["players"]: del game_states[room]; print(f"Salle {room} supprimée.")
            socketio.emit('update_state', state, room=room)
            broadcast_to_admins(); broadcast_room_list(); break

@socketio.on('create_room_request')
def handle_create_room_request():
    room_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    while room_id in game_states: room_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    join_room(room_id)
    game_states[room_id] = create_new_game_state()
    game_states[room_id]['host_sid'] = request.sid
    print(f"Salle {room_id} créée par {request.sid}.")
    emit('room_created', {'room_id': room_id, 'config': CONFIG, 'state': game_states[room_id]})
    broadcast_room_list()
    broadcast_to_admins() 

@socketio.on('host_join_room')
def handle_host_join_room(data):
    room_id = data.get('room_id')
    if room_id in game_states:
        join_room(room_id)
        game_states[room_id]['host_sid'] = request.sid
        print(f"Hôte {request.sid} a rejoint l'affichage de la salle {room_id}.")
        emit('room_created', {'room_id': room_id, 'config': CONFIG, 'state': game_states[room_id]})

@socketio.on('join_game')
def handle_join_game(data):
    room_id = data.get('room_id'); player_name = data.get('name'); avatar_id = data.get('avatar_id')
    state = game_states.get(room_id)
    if not state: emit('error', {'message': 'Cette salle n\\\'existe pas.'}); return
    if state['game_started']: emit('error', {'message': 'La partie a déjà commencé.'}); return
    if len([p for p in state['players'] if not p.get('is_disconnected')]) >= 8: emit('error', {'message': 'La partie est pleine.'}); return
    
    player_name_lower = player_name.lower().strip()
    active_easter_eggs = CONFIG.get('easter_eggs', {})
    
    is_champion_tyson = player_name_lower == 'tyson' and active_easter_eggs.get('tyson', True)
    is_special_lorie = player_name_lower == 'lorie' and active_easter_eggs.get('lorie', True)
    is_seamstress_corine = player_name_lower == 'corine' and active_easter_eggs.get('corine', True)
    is_wrestler_oceane = player_name_lower == 'oceane' and active_easter_eggs.get('oceane', True)
    is_viking_dimitri = player_name_lower == 'dimitri' and active_easter_eggs.get('dimitri', True)
    is_boxer_jc = player_name_lower in ['jc', 'jean claude', 'jean-claude'] and active_easter_eggs.get('jc', True)
    is_groot_marie = player_name_lower == 'marie' and active_easter_eggs.get('marie', True)
    
    if is_champion_tyson:
        avatar_id = 12
        socketio.emit('champion_joined', {}, room=room_id)
        
    if is_wrestler_oceane: socketio.emit('play_sound', {'sound': 'wrestling-bell'}, room=room_id)
    if is_viking_dimitri: socketio.emit('play_sound', {'sound': 'war-horn'}, room=room_id)
    if is_boxer_jc: socketio.emit('play_sound', {'sound': 'rocky-theme'}, room=room_id)
    if is_groot_marie: socketio.emit('play_sound', {'sound': 'i-am-groot'}, room=room_id)

    colors = ['#3b82f6', '#ef4444', '#22c55e', '#eab308', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
    new_player = {
        "sid": request.sid, "name": player_name, "avatar_id": avatar_id, 
        "score": 0, "color": colors[len(state['players']) % len(colors)],
        "token": secrets.token_hex(16),
        "is_special": False,
        "is_champion_tyson": is_champion_tyson,
        "has_fart_button": is_special_lorie, "has_sewing_border": is_seamstress_corine,
        "has_sewing_button": is_seamstress_corine, "has_belt_border": is_wrestler_oceane,
        "has_chair_button": is_wrestler_oceane, "has_shield_border": is_viking_dimitri,
        "has_axe_button": is_viking_dimitri, "has_ring_border": is_boxer_jc,
        "has_punch_button": is_boxer_jc, "has_bark_border": is_groot_marie,
        "has_branch_button": is_groot_marie, "has_multiplier": False,
        "game_score_simple": 0, "game_score_buzzer": 0, "game_score_intrus": 0
    }
    state['players'].append(new_player)
    join_room(room_id)
    emit('joined_successfully', {'name': new_player['name'], 'color': new_player['color'], 'token': new_player['token'], 'room_id': room_id})
    socketio.emit('update_state', state, room=room_id)
    broadcast_to_admins(); broadcast_room_list()

@socketio.on('reconnect_player')
def handle_reconnect_player(data):
    token = data.get('token'); room_id = data.get('room_id')
    state = game_states.get(room_id)
    if state:
        player = next((p for p in state['players'] if p.get('token') == token), None)
        if player:
            player['sid'] = request.sid
            player['is_disconnected'] = False
            if 'disconnected_at' in player: del player['disconnected_at']
            join_room(room_id)
            print(f"Joueur {player['name']} reconnecté avec succès.")
            emit('reconnect_success', {'name': player['name'], 'color': player['color']})
            socketio.emit('update_state', state, room=room_id)
            broadcast_to_admins()
            if state['game_started']:
                mode = state['current_mode_key']
                current_player_index = state.get('current_player_index', -1)
                current_player = state['players'][current_player_index] if current_player_index != -1 else None
                view_data = {'state': state}
                if mode == 'simple':
                    is_my_turn = player['sid'] == current_player['sid'] if current_player else False
                    view_data['view'] = 'question'
                    view_data['data'] = {'question': state['current_question_data'], 'is_my_turn': is_my_turn}
                elif mode == 'buzzer' or mode == 'sudden_death':
                    if state.get('buzzer_winner_sid'):
                        winner = next((p for p in state['players'] if p['sid'] == state['buzzer_winner_sid']), None)
                        is_my_turn = player['sid'] == winner['sid'] if winner else False
                        if is_my_turn:
                             view_data['view'] = 'question'; view_data['data'] = {'question': state['current_question_data'], 'is_my_turn': True}
                        else:
                             view_data['view'] = 'wait'; view_data['data'] = {'message': f"{winner['name']} a buzzé !", 'question': state['current_question_data']}
                    else:
                        view_data['view'] = 'buzzer'; view_data['data'] = {'question': state['current_question_data']}
                elif mode == 'intrus':
                    is_my_turn = player['sid'] == current_player['sid'] if current_player else False
                    view_data['view'] = 'question'; view_data['data'] = {'question': state['current_question_data'], 'is_my_turn': is_my_turn, 'revealed': state['revealed_answers']}
                else: view_data['view'] = 'wait'; view_data['data'] = {'message': 'Reconnecté ! En attente...'}
                socketio.emit('update_player_view', view_data, room=request.sid)
            else: socketio.emit('update_player_view', {'view': 'wait', 'data': {'message': 'Reconnecté ! En attente du début...'}, 'state': state}, room=request.sid)
            return
    emit('reconnect_fail')

@socketio.on('start_game')
def handle_start_game(data):
    room_id = data.get('room_id')
    state = game_states.get(room_id)
    if not state or not state.get('players'): return
    state['game_started'] = True
    start_next_mode(room_id)
    broadcast_room_list()

@socketio.on('player_answer')
def handle_player_answer(data):
    room_id = data.get('room_id'); state = game_states.get(room_id)
    if not state or not state.get('current_question_data'): return
    player = next((p for p in state['players'] if p['sid'] == request.sid), None)
    if not player: return
    mode_key = state['current_mode_key']
    question = state['current_question_data']; answer_index = data.get('answer_index')
    if not isinstance(answer_index, int) or answer_index >= len(question['reponses']): return
    selected_answer = question['reponses'][answer_index]
    
    points_config = CONFIG.get('points_config', {})

    if mode_key == 'simple':
        is_correct = selected_answer['correcte']
        points = points_config.get('simple', 10)
        if player.get('has_multiplier') and data.get('use_multiplier'):
            points *= 2; player['has_multiplier'] = False
            player['used_multiplier'] = True 
            state['info_text'] = f"Score x2 ! Bonne réponse de {player['name']} !"
        else: state['info_text'] = f"Bonne réponse de {player['name']} !" if is_correct else f"Mauvaise réponse de {player['name']}..."
        
        if is_correct: 
            player['score'] += points
            player['game_score_simple'] = player.get('game_score_simple', 0) + points
        
        socketio.emit('answer_feedback', {'correct': is_correct}, room=player['sid'])
        correct_idx = next(i for i, ans in enumerate(question['reponses']) if ans['correcte'])
        socketio.emit('reveal_answer', {'correct_answer_index': correct_idx, 'player_choice_index': answer_index, 'is_correct': is_correct}, room=room_id)
        socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
        socketio.sleep(3); start_question_simple(room_id)
        
    elif mode_key == 'buzzer' or mode_key == 'sudden_death':
        is_correct = selected_answer['correcte']
        socketio.emit('answer_feedback', {'correct': is_correct}, room=player['sid'])
        
        if mode_key == 'sudden_death':
            if is_correct: end_game(room_id)
            else:
                player['score'] = -1
                state['info_text'] = f"{player['name']} est éliminé !"; socketio.emit('update_state', state, room=room_id); socketio.sleep(3)
                remaining_players = [p for p in state['players'] if p['score'] >= 0]
                if len(remaining_players) <= 1: end_game(room_id)
                else: start_sudden_death(room_id, remaining_players)
            return
            
        if is_correct:
            points = points_config.get('buzzer', 10)
            player['score_round'] = player.get('score_round', 0) + points
            player['game_score_buzzer'] = player.get('game_score_buzzer', 0) + points
            state['info_text'] = f"Bonne réponse de {player['name']} !"
            correct_idx = next(i for i, ans in enumerate(question['reponses']) if ans['correcte'])
            socketio.emit('reveal_answer', {'correct_answer_index': correct_idx, 'player_choice_index': answer_index, 'is_correct': True}, room=room_id)
            socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
            socketio.sleep(3); start_question_buzzer(room_id)
        else:
            state['info_text'] = f"{player['name']} s'est trompé ! Aux autres de buzzer !"
            state['buzzer_has_answered'].append(player['sid'])
            state['buzzer_active'] = True; state['buzzer_winner_sid'] = None
            active_players = [p for p in state['players'] if not p.get('is_disconnected')]
            if len(state['buzzer_has_answered']) >= len(active_players):
                state['info_text'] = "Personne n'a trouvé !"; correct_idx = next(i for i, ans in enumerate(question['reponses']) if ans['correcte'])
                socketio.emit('reveal_answer', {'correct_answer_index': correct_idx, 'player_choice_index': -1, 'is_correct': False}, room=room_id)
                socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
                socketio.sleep(3); start_question_buzzer(room_id)
            else:
                socketio.emit('update_state', state, room=room_id)
                socketio.emit('update_player_view', {'view': 'buzzer', 'data': {'question': state['current_question_data']}, 'state': state}, room=room_id)
                
    elif mode_key == 'intrus':
        is_intrus = selected_answer['intrus']
        soe_state = state['stop_or_encore_state']
        soe_state['revealed'].append(answer_index)
        socketio.emit('answer_feedback', {'correct': not is_intrus}, room=player['sid'])
        
        if is_intrus:
            state['info_text'] = f"Oh non ! {player['name']} a trouvé l'intrus."
            socketio.emit('reveal_answer', {'intrus_found': True, 'player_choice_index': answer_index}, room=room_id)
            socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
            socketio.sleep(3); start_question_intrus(room_id)
        else:
            base_points = points_config.get('intrus', 50)
            points = base_points * (len(soe_state['revealed']))
            if player.get('has_multiplier') and data.get('use_multiplier'):
                points *= 2; player['has_multiplier'] = False
                player['used_multiplier'] = True
            
            soe_state['points_accumulated'] = points
            socketio.emit('reveal_answer', {'intrus_found': False, 'player_choice_index': answer_index}, room=room_id)
            socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
            socketio.sleep(2)
            
            nombre_bonnes_reponses = len(question['reponses']) - 1
            if len(soe_state['revealed']) == nombre_bonnes_reponses:
                player['score'] += soe_state['points_accumulated']
                player['game_score_intrus'] = player.get('game_score_intrus', 0) + soe_state['points_accumulated']
                
                name_key = player['name'].lower()
                if name_key in PLAYER_STATS:
                    PLAYER_STATS[name_key]['grand_slams'] = PLAYER_STATS[name_key].get('grand_slams', 0) + 1
                    save_stats()

                state['info_text'] = f"Grand chelem ! {player['name']} valide {soe_state['points_accumulated']} points !"
                socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
                socketio.sleep(3)
                start_question_intrus(room_id)
            else: socketio.emit('update_player_view', {'view': 'stop_or_encore', 'data': soe_state, 'state': state}, room=player['sid'])

@socketio.on('player_stop_or_encore')
def handle_stop_or_encore(data):
    room_id = data.get('room_id'); state = game_states.get(room_id)
    if not state: return
    player = next((p for p in state['players'] if p['sid'] == request.sid), None)
    if not player: return
    choice = data.get('choice')
    soe_state = state['stop_or_encore_state']
    if choice == 'stop':
        points_won = soe_state.get('points_accumulated', 0)
        player['score'] += points_won
        player['game_score_intrus'] = player.get('game_score_intrus', 0) + points_won
        state['info_text'] = f"{player['name']} s'arrête et valide {points_won} points !"
        socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
        socketio.sleep(3); start_question_intrus(room_id)
    else: socketio.emit('update_player_view', {'view': 'question', 'data': {'question': state['current_question_data'], 'is_my_turn': True, 'revealed': soe_state['revealed']}, 'state': state}, room=player['sid'])

@socketio.on('player_buzz')
def handle_player_buzz(data):
    room_id = data.get('room_id'); state = game_states.get(room_id)
    if not state or not state['buzzer_active'] or request.sid in state.get('buzzer_has_answered', []): return
    state['buzzer_active'] = False; state['buzzer_winner_sid'] = request.sid
    winner = next(p for p in state['players'] if p['sid'] == request.sid)
    state['info_text'] = f"{winner['name']} a buzzé !"
    socketio.emit('update_state', state, room=room_id); broadcast_to_admins()
    for p in state['players']:
        is_my_turn = p['sid'] == winner['sid']
        if is_my_turn: socketio.emit('update_player_view', {'view': 'question', 'data': {'question': state['current_question_data'], 'is_my_turn': True}, 'state': state}, room=p['sid'])
        else: socketio.emit('update_player_view', { 'view': 'wait', 'data': {'message': f"{winner['name']} a buzzé !", 'question': state['current_question_data']}, 'state': state}, room=p['sid'])

@socketio.on('player_estimation')
def handle_player_estimation(data):
    room_id = data.get('room_id'); state = game_states.get(room_id)
    if not state: return
    
    player = next((p for p in state['players'] if p['sid'] == request.sid), None)
    if not player or player.get('current_answer') is not None:
        return

    try:
        player['current_answer'] = int(data.get('value'))
        socketio.emit('player_answered', {'sid': request.sid}, room=room_id)
    except (ValueError, TypeError):
        return

    active_players = [p for p in state['players'] if not p.get('is_disconnected')]
    if all(p.get('current_answer') is not None for p in active_players):
        reveal_estimation_results(room_id)

def reveal_estimation_results(room_id):
    state = game_states.get(room_id)
    if not state: return
    
    question = state['current_question_data']
    correct_answer = question['reponse']
    tolerance = question.get('tolerance', 0)
    points_config = CONFIG.get('points_config', {})
    
    for p in state['players']:
        if p.get('current_answer') is not None:
            diff = abs(p['current_answer'] - correct_answer)
            if diff == 0:
                p['score'] += points_config.get('estimation_perfect', 150)
            elif tolerance > 0 and diff <= tolerance:
                base_points = points_config.get('estimation_close', 100)
                p['score'] += max(10, base_points - int((diff / tolerance) * (base_points - 10)))
    
    state['info_text'] = f"La bonne réponse était : {correct_answer}"
    all_answers = [{'name': p['name'], 'answer': p['current_answer']} for p in state['players'] if p.get('current_answer') is not None]
    
    socketio.emit('reveal_estimation', {'question': question, 'all_answers': all_answers}, room=room_id)
    socketio.emit('update_state', state, room=room_id)
    broadcast_to_admins()
    
    socketio.sleep(8)
    start_question_estimation(room_id)

@socketio.on('play_fart_sound')
def handle_fart_sound(data):
    room_id = data.get('room_id')
    if room_id in game_states: socketio.emit('fart_sound_triggered', {}, room=room_id)

@socketio.on('play_sewing_effect')
def handle_sewing_effect(data):
    room_id = data.get('room_id')
    if room_id in game_states: socketio.emit('sewing_effect_triggered', {}, room=room_id)

@socketio.on('play_chair_effect')
def handle_chair_effect(data):
    room_id = data.get('room_id')
    if room_id in game_states: socketio.emit('chair_effect_triggered', {}, room=room_id)

@socketio.on('play_berserker_cry')
def handle_berserker_cry(data):
    room_id = data.get('room_id')
    if room_id in game_states: socketio.emit('berserker_cry_triggered', {}, room=room_id)

@socketio.on('play_punch_effect')
def handle_punch_effect(data):
    room_id = data.get('room_id')
    if room_id in game_states: socketio.emit('punch_effect_triggered', {}, room=room_id)

@socketio.on('play_branch_effect')
def handle_branch_effect(data):
    room_id = data.get('room_id')
    if room_id in game_states: socketio.emit('branch_effect_triggered', {}, room=room_id)

@socketio.on('player_reaction')
def handle_player_reaction(data):
    room_id = data.get('room_id'); state = game_states.get(room_id)
    if state:
        player = next((p for p in state['players'] if p['sid'] == request.sid), None)
        if player:
            socketio.emit('show_reaction', {
                'player_sid': request.sid,
                'player_name': player['name'],
                'emoji': data.get('emoji')
            }, room=room_id)

# --- GESTIONNAIRES ADMIN ---
@socketio.on('admin_login')
def handle_admin_login(data):
    if data.get('password') == CONFIG.get('admin_password', 'admin'):
        admin_sids.add(request.sid)
        emit('login_success', { 
            'questions': QUESTION_BANK, 
            'game_states': game_states, 
            'game_history': GAME_HISTORY, 
            'config': CONFIG, 
            'changelog': CHANGELOG_ENTRIES,
            'dashboard_stats': get_dashboard_stats()
        })
    else: emit('login_fail')

@socketio.on('admin_get_player_stats')
def handle_admin_get_player_stats(data):
    if request.sid not in admin_sids: return
    name_key = data.get('name', '').lower()
    stats = PLAYER_STATS.get(name_key)
    emit('admin_player_stats_response', {'stats': stats})

@socketio.on('admin_save_player_stats')
def handle_admin_save_player_stats(data):
    if request.sid not in admin_sids: return
    name_key = data.get('name', '').lower()
    new_stats = data.get('new_stats')
    if name_key in PLAYER_STATS and new_stats:
        for key, value in new_stats.items():
            PLAYER_STATS[name_key][key] = int(value) if isinstance(value, str) and value.isdigit() else value
        save_stats()
        emit('stats_saved_successfully')

@socketio.on('admin_save_config')
def handle_admin_save_config(data):
    if request.sid not in admin_sids: return
    new_config = data.get('config', {})
    for key, value in new_config.items():
        if key in CONFIG and isinstance(CONFIG[key], dict):
            CONFIG[key].update(value)
        else:
            CONFIG[key] = value
    save_config()
    emit('config_saved_successfully', {'new_config': CONFIG})

@socketio.on('admin_delete_history')
def handle_admin_delete_history(data):
    if request.sid not in admin_sids: return
    index = data.get('index')
    if 0 <= index < len(GAME_HISTORY):
        del GAME_HISTORY[index]
        save_history()
        for sid in admin_sids:
            socketio.emit('history_updated', {'history': GAME_HISTORY}, room=sid)

@socketio.on('admin_add_changelog')
def handle_admin_add_changelog(data):
    if request.sid not in admin_sids: return
    title = data.get('title'); content = data.get('content')
    if title and content:
        new_entry = { "id": secrets.token_hex(8), "date": datetime.now().strftime("%d/%m/%Y à %H:%M"), "title": title, "content": content }
        CHANGELOG_ENTRIES.insert(0, new_entry)
        save_changelog()
        for sid in admin_sids: socketio.emit('update_changelog', {'changelog': CHANGELOG_ENTRIES}, room=sid)

@socketio.on('admin_delete_changelog')
def handle_admin_delete_changelog(data):
    if request.sid not in admin_sids: return
    entry_id = data.get('id')
    global CHANGELOG_ENTRIES
    CHANGELOG_ENTRIES = [entry for entry in CHANGELOG_ENTRIES if entry.get('id') != entry_id]
    save_changelog()
    for sid in admin_sids: socketio.emit('update_changelog', {'changelog': CHANGELOG_ENTRIES}, room=sid)

@socketio.on('admin_update_changelog')
def handle_admin_update_changelog(data):
    if request.sid not in admin_sids: return
    entry_id = data.get('id'); new_title = data.get('title'); new_content = data.get('content')
    for entry in CHANGELOG_ENTRIES:
        if entry.get('id') == entry_id:
            entry['title'] = new_title
            entry['content'] = new_content
            break
    save_changelog()
    for sid in admin_sids: socketio.emit('update_changelog', {'changelog': CHANGELOG_ENTRIES}, room=sid)

@socketio.on('admin_move_changelog')
def handle_admin_move_changelog(data):
    if request.sid not in admin_sids: return
    index = data.get('index'); direction = data.get('direction')
    if direction == 'up' and index > 0:
        CHANGELOG_ENTRIES[index], CHANGELOG_ENTRIES[index - 1] = CHANGELOG_ENTRIES[index - 1], CHANGELOG_ENTRIES[index]
    elif direction == 'down' and index < len(CHANGELOG_ENTRIES) - 1:
        CHANGELOG_ENTRIES[index], CHANGELOG_ENTRIES[index + 1] = CHANGELOG_ENTRIES[index + 1], CHANGELOG_ENTRIES[index]
    save_changelog()
    for sid in admin_sids: socketio.emit('update_changelog', {'changelog': CHANGELOG_ENTRIES}, room=sid)

@socketio.on('add_question')
def handle_add_question(data):
    if request.sid not in admin_sids: return
    q_type = data.get('type')
    question_data = data.get('question')
    if not question_data: return
    
    question_data['active'] = True

    if q_type == 'questions_simples':
        theme = data.get('theme')
        if theme:
            if theme not in QUESTION_BANK['questions_simples']:
                QUESTION_BANK['questions_simples'][theme] = []
            QUESTION_BANK['questions_simples'][theme].append(question_data)
            save_questions('questions_simples')
            emit('update_questions', {'questions': QUESTION_BANK})
            broadcast_to_admins()

    elif q_type == 'questions_intrus':
        QUESTION_BANK['questions_intrus'].append(question_data)
        save_questions('questions_intrus')
        emit('update_questions', {'questions': QUESTION_BANK})
        broadcast_to_admins()

@socketio.on('delete_question')
def handle_delete_question(data):
    if request.sid not in admin_sids: return
    q_type = data.get('type'); theme = data.get('theme'); index = data.get('index')
    if q_type == 'questions_simples' and theme in QUESTION_BANK['questions_simples']:
        if 0 <= index < len(QUESTION_BANK['questions_simples'][theme]):
            del QUESTION_BANK['questions_simples'][theme][index]
            if not QUESTION_BANK['questions_simples'][theme]: del QUESTION_BANK['questions_simples'][theme]
            save_questions('questions_simples')
            emit('update_questions', {'questions': QUESTION_BANK})
            broadcast_to_admins()
    elif q_type == 'questions_intrus':
        if 0 <= index < len(QUESTION_BANK['questions_intrus']):
            del QUESTION_BANK['questions_intrus'][index]
            save_questions('questions_intrus')
            emit('update_questions', {'questions': QUESTION_BANK})
            broadcast_to_admins()

@socketio.on('admin_update_question')
def handle_admin_update_question(data):
    if request.sid not in admin_sids: return
    q_type = data.get('type')
    new_data = data.get('new_data')
    if not q_type or not new_data: return

    if q_type == 'questions_simples':
        theme = data.get('theme')
        index = data.get('index')
        if theme in QUESTION_BANK['questions_simples'] and 0 <= index < len(QUESTION_BANK['questions_simples'][theme]):
            new_data['active'] = QUESTION_BANK['questions_simples'][theme][index].get('active', True)
            QUESTION_BANK['questions_simples'][theme][index] = new_data
            save_questions('questions_simples')
            emit('update_questions', {'questions': QUESTION_BANK})

    elif q_type == 'questions_intrus':
        index = data.get('index')
        if 0 <= index < len(QUESTION_BANK['questions_intrus']):
            new_data['active'] = QUESTION_BANK['questions_intrus'][index].get('active', True)
            QUESTION_BANK['questions_intrus'][index] = new_data
            save_questions('questions_intrus')
            emit('update_questions', {'questions': QUESTION_BANK})

@socketio.on('admin_toggle_question_status')
def handle_admin_toggle_question_status(data):
    if request.sid not in admin_sids: return
    q_type = data.get('type')
    status = data.get('status')

    if q_type == 'questions_simples':
        theme = data.get('theme')
        index = data.get('index')
        if theme in QUESTION_BANK['questions_simples'] and 0 <= index < len(QUESTION_BANK['questions_simples'][theme]):
            QUESTION_BANK['questions_simples'][theme][index]['active'] = status
            save_questions('questions_simples')
            emit('update_questions', {'questions': QUESTION_BANK})

    elif q_type == 'questions_intrus':
        index = data.get('index')
        if 0 <= index < len(QUESTION_BANK['questions_intrus']):
            QUESTION_BANK['questions_intrus'][index]['active'] = status
            save_questions('questions_intrus')
            emit('update_questions', {'questions': QUESTION_BANK})

@socketio.on('get_player_stats')
def handle_get_player_stats(data):
    player_name = data.get('name', '').lower()
    stats = PLAYER_STATS.get(player_name)
    if stats:
        trophies = []
        
        if stats.get('wins', 0) >= 1: trophies.append("Première Victoire !")
        if stats.get('wins', 0) >= 10: trophies.append("Champion en Série")
        if stats.get('games_played', 0) >= 20: trophies.append("Vétéran du Quiz")
        if stats.get('best_score', 0) >= 500: trophies.append("Maître du Score")
        if stats.get('score_buzzer', 0) >= 100: trophies.append("Roi du Buzzer")
        if stats.get('score_intrus', 0) >= 500: trophies.append("Le Fin Limier")
        if stats.get('score_simple', 0) >= 1000: trophies.append("Le Cerveau")
        if stats.get('grand_slams', 0) >= 1: trophies.append("Grand Chelem !")
        if stats.get('tacticien_wins', 0) >= 1: trophies.append("Le Tacticien")
        if stats.get('games_played', 0) >= 50: trophies.append("Légende du Quiz")
        if stats.get('total_score', 0) >= 10000: trophies.append("Le Collectionneur")
        if stats.get('max_win_streak', 0) >= 3: trophies.append("Invincible")
        
        stats['trophies'] = trophies
        emit('player_stats_response', {'stats': stats})
    else:
        emit('player_stats_response', {'stats': None, 'message': 'Joueur non trouvé.'})

# --- DÉMARRAGE DU SERVEUR ---
if __name__ == '__main__':
    load_data()
    cleanup_thread = threading.Thread(target=cleanup_disconnected_players)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    try:
        print("Serveur en cours de démarrage...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"ERREUR CRITIQUE AU DÉMARRAGE: {e}")
        input("Appuyez sur Entrée pour fermer...")
