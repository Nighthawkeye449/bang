import eventlet
eventlet.monkey_patch()

from flask import Flask, request, render_template, make_response, redirect, url_for, session, abort, send_from_directory, jsonify
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from signal import signal, SIGINT
from threading import Lock
import json
import os
import random
import sys
import time


# Import local modules.
from static.library import jinjafunctions
from static.library import utils
from static.library.constants import *
from static.library.gameplay import Gameplay
from static.library.playergame import PlayerGame

def handler(signal_received, frame):
    # Catch CTRL-C in order to separate sessions in the log.
    for func in [utils.logServer, utils.logPlayer, utils.logGameplay]:
	    func("Exiting game with CTRL-C.")
	    func("\n\n\n")
    sys.exit(0)

def _default(self, obj):
	return getattr(obj.__class__, "to_json", _default.default)(obj)

_default.default = json.JSONEncoder().default
json.JSONEncoder.default = _default

def saveGame(game):
	with open(JSON_GAME_PATH, 'w') as file:
		json.dump(game, file, indent=4, sort_keys=True)
	with open(JSON_GAME_PATH.replace(".json", "_backup.json"), 'w') as file:
		json.dump(game, file, indent=4, sort_keys=True)

def createDefaultGame():
	game = {
			"site_variables" : {
				"ip" : "127.0.0.1",
				"port" : 9999
			},
			"debug": {
				"logging" : True,
				"cookie_expiration_days" : 7
			},
			"gp": Gameplay(),
		}
	
	saveGame(game)
	return game

def resetGame():
	if os.path.exists(JSON_GAME_PATH):
		os.remove(JSON_GAME_PATH)
	return createDefaultGame()

def loadGame():
	try:
		with open(JSON_GAME_PATH, 'r') as game_file:
			game = json.load(game_file)
			game['gp'] = Gameplay(**game['gp'])
	except FileNotFoundError:
		utils.logServer("No JSON file found - creating a new one.")
		game = createDefaultGame()
	return game

# Validate whether enough time has passed since the previous socket message from a given user to consider a new one valid.
# This is useful for avoiding things like accidental double-clicks.
def validResponseTime(username):
	global SOCKET_MESSAGE_TIMESTAMPS

	if username not in SOCKET_MESSAGE_TIMESTAMPS:
		SOCKET_MESSAGE_TIMESTAMPS[username] = time.time()
		return True
	else:
		if time.time() - SOCKET_MESSAGE_TIMESTAMPS[username] >= 1:
			SOCKET_MESSAGE_TIMESTAMPS[username] = time.time()
			return True
		else:
			utils.logServer("Not enough time has passed since {}'s last socket message ({}). Ignoring this one.".format(username, time.time() - SOCKET_MESSAGE_TIMESTAMPS[username]))
			return False

def emit(emitString, args=None, recipient=None):
	if args != None and recipient != None:
		socketio.emit(emitString, args, room=recipient.sid)
		if emitString != UPDATE_PLAYER_LIST:
			utils.logServer("Emitted socket message '{}' to {} with args {}.".format(emitString, recipient.username, args))
	elif args != None:
		socketio.emit(emitString, args)
		utils.logServer("Emitted socket message '{}' to everybody with args {}.".format(emitString, args))
	else:
		socketio.emit(emitString)
		utils.logServer("Emitted socket message '{}' to everybody.".format(emitString))

def emitTuples(tuples):
	for (modalEmitString, args, recipient) in utils.consolidateTuples(tuples):
		if modalEmitString == SLEEP:
			time.sleep(int(args))
			utils.logServer("Sleeping for {} seconds while emitting tuples.".format(args))
		else:
			emit(modalEmitString, args, recipient)


JSON_GAME_PATH = utils.getLocalFilePath("game.json")

# Server setup
app = Flask(__name__, static_url_path='/static', template_folder='templates')
app.secret_key = 'secretkey1568486123168'
socketio = SocketIO(app)

lock = Lock()

userLobbyDic = {}
lobbyGameDic = {}

SOCKET_MESSAGE_TIMESTAMPS = dict()

#################### Socket IO functions ####################

@socketio.on(KEEP_ALIVE)
def keepAlive(username):
	socketio.emit(KEEP_ALIVE, dict(), room=request.sid)

@socketio.on(CONNECTED)
def connectUsernameToSid(username):
	utils.logServer("Received socket message '{}' from {}.".format(CONNECTED, username))
	with lock:
		game['gp'].players[username] = PlayerGame(username)
		game['gp'].players[username].sid = request.sid

@socketio.on(LEAVE_LOBBY)
def leaveLobby(username):
	sid = game['gp'].players[username].sid
	
	del game['gp'].players[username]
	sorted_usernames = sorted(game['gp'].players.keys())

	# Broadcast the updated list of players to everybody else in this lobby.
	emit(LOBBY_PLAYER_UPDATE, {'usernames': sorted_usernames}, None)

	# Reload the pick lobby page for the player who left.
	socketio.emit(RELOAD_LOBBY, {'html': render_template("pick_lobby.html", username=username)}, room=sid)


@socketio.on(START_BUTTON_CLICKED)
def startGame():
	utils.logServer("Received socket message '{}'. Preparing game for setup.".format(START_BUTTON_CLICKED))
	with lock:
		if not game['gp'].preparedForSetup:
			game['gp'].prepareForSetup()

	emit(START_GAME)

@socketio.on(SET_CHARACTER)
def setCharacter(username, character):
	utils.logServer("Received socket message '{}' from {}: {}.".format(SET_CHARACTER, username, character))
	tuples = []

	with lock:
		game['gp'].assignCharacter(username, character)
		unassigned_players_remaining = [u for u in game['gp'].players if game['gp'].players[u].character == None]

		if len(unassigned_players_remaining) > 0:
			emit('character_was_set', {'players_remaining': unassigned_players_remaining})

		else:
			# Start the game for the players by loading their main play screens and info modals.
			tuples = game['gp'].finalizeSetup()

	if tuples:
		emitTuples(tuples)

@socketio.on(CARD_WAS_DISCARDED)
def cardWasDiscarded(username, uid):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}: {}.".format(CARD_WAS_DISCARDED, username, uid))
		with lock:
			card = game['gp'].getCardByUid(uid)

			utils.logServer("Discarding {} ({}) by {}.".format(card.name, uid, username))
			player = game['gp'].players[username]
			game['gp'].discardCard(player, card)

@socketio.on(VALIDATE_CARD_CHOICE)
def cardWasPlayed(username, uid):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}: {}.".format(VALIDATE_CARD_CHOICE, username, uid))
		with lock:
			card = game['gp'].getCardByUid(int(uid))

			if card == None:
				utils.logError("Received request to play card with UID {}. UID not recognized.".format(uid))
			elif username != game['gp'].getCurrentPlayerName():
				utils.logError("Received request to play a card from {}, but it's currently {}'s turn.".format(username, game['gp'].getCurrentPlayerName()))
			else:
				utils.logServer("Received socket message from {} to play {} (UID: {}).".format(username, card.name, uid))
				emitTuples(game['gp'].validateCardChoice(username, uid))

@socketio.on(INFO_MODAL_UNDEFINED)
def waitForInfoModal(username, html):
	utils.logServer("Info modal load failed for {}. Waiting 1/100 of a second and trying again.".format(username))
	time.sleep(0.01)
	emit(SHOW_INFO_MODAL, {'html': html}, recipient=game['gp'].players[username])

@socketio.on(QUESTION_MODAL_UNDEFINED)
def waitForQuestionModal(username, option1, option2, option3, option4, option5, option6, html, question):
	utils.logServer("Question modal load failed for {}. Waiting 1/100 of a second and trying again.".format(username))
	time.sleep(0.01)
	emit(SHOW_QUESTION_MODAL, {'option1': option1, 'option2': option2, 'option3': option3, 'option4': option4, 'option5': option5, 'option6': option6, 'html': html, 'question': question}, recipient=game['gp'].players[username])

@socketio.on(QUESTION_MODAL_ANSWERED)
def questionModalAnswered(username, question, answer):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}: {} -> {}.".format(QUESTION_MODAL_ANSWERED, username, question, answer))
		emitTuples(game['gp'].processQuestionResponse(username, question, answer))

@socketio.on(BLUR_CARD_PLAYED)
def playBlurCard(username, uid):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}: {}.".format(BLUR_CARD_PLAYED, username, uid))
		emitTuples(game['gp'].processBlurCardSelection(username, int(uid)))

@socketio.on(EMPORIO_CARD_PICKED)
def pickEmporioCard(username, uid):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}: {}.".format(EMPORIO_CARD_PICKED, username, uid))
		emitTuples(game['gp'].processEmporioCardSelection(username, int(uid)))

@socketio.on(ENDING_TURN)
def endingTurn(username):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}.".format(ENDING_TURN, username))
		emitTuples(game['gp'].startNextTurn(username))

@socketio.on(DISCARDING_CARD)
def discardingCard(username, uid):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}.".format(DISCARDING_CARD, username))
		emitTuples(game['gp'].playerDiscardingCard(username, int(uid)))

@socketio.on(USE_SPECIAL_ABILITY)
def specialAbility(username):
	if validResponseTime(username):
		utils.logServer("Received socket message '{}' from {}.".format(USE_SPECIAL_ABILITY, username))
		emitTuples(game['gp'].useSpecialAbility(username))

@socketio.on(REQUEST_PLAYER_LIST)
def requestPlayerList(username):
	with lock:
		tuples = game['gp'].getPlayerList(username)
	emitTuples(tuples)

#################### App routes ####################

@app.route("/", methods = ['POST', 'GET'])
def homePage():
	with lock:
		# The method will be POST if the text box for username has been submitted.
		if request.method == 'POST':
			if 'name' not in request.form or utils.isEmptyOrNull(request.form['name']):
				utils.logServer("A player attempted to join with an invalid username. Reloading home page.")
				return render_template('home.html')
			
			# Add this new player if the username is valid.
			username = utils.cleanUsernameInput(request.form['name'])
			if not checkUsernameValidity(username):
				return render_template('home.html', warning_msg="Sorry, that username is invalid! Try something else.")
			else:
				utils.logServer("Adding new username {}.".format(username))
				return render_template("pick_lobby.html", username=username)

	return render_template('home.html')

@app.route("/lobby", methods=['POST'])
def lobby():

	username = request.form['username']

	if not utils.isEmptyOrNull(request.form['lobby_number']):
		if not request.form['lobby_number'] in lobbyGameDic:
			return render_template('pick_lobby.html', warning_msg="Sorry, that lobby couldn't be found.")

		if request.form['lobby_number'] in lobbyGameDic:
			return render_template('lobby.html', usernames=sorted_usernames, username=username, lobbyNumber=request.form['lobby_number'])

	# is this the right way to request from the button?
	if request.form['submit-button']:
		lobbyNumber = random.randint(1111,9999)
		while lobbyNumber in lobbyGameDic:
			lobbyNumber = random.randint(1111,9999)
		lobbyGameDic[lobbyNumber] = resetGame()
		userLobbyDic[username] = lobbyNumber #link the username to the lobby number

	sorted_usernames = sorted(game['gp'].players.keys())
	
	# Broadcast the updated list of players to everybody in this lobby.
	emit(LOBBY_PLAYER_UPDATE, {'usernames': sorted_usernames}, None)

	utils.logServer("Rendering lobby for {}".format(username))
	return render_template('lobby.html', usernames=sorted_usernames, username=username, lobbyNumber=userLobbyDic[username])

@app.route("/setup", methods = ['POST', 'GET'])
def setup():
	username = request.json['username']
	utils.logServer("Received request for '/setup' from {}".format(username))

	with lock:
		game['gp'].assignNewPlayer(username)

	# Wait until the Sheriff has been assigned so that his/her name can be rendered too.
	while True:
		time.sleep(0.2) # Check every 200 milliseconds.
		with lock:
			if game['gp'].sheriffUsername:
				utils.logServer("Sheriff has been assigned. Rendering setup page for {}.".format(username))
				return render_template('setup.html',
					role=game['gp'].players[username].role,
					option1=game['gp'].players[username].characterOptions[0],
					option2=game['gp'].players[username].characterOptions[1],
					sheriff=game['gp'].sheriffUsername if game['gp'].sheriffUsername != username else None,
					numOtherPlayers=len(game['gp'].players) - 1)

#################### App route for POST calls that query information instead of rendering full pages ####################

@app.route("/synchronousPost", methods = ['POST'])
def synchronousPost():
	username = request.json['username']
	uid = int(request.json['uid'])
	path = request.json['path']

def checkUsernameValidity(username):
	if len(username) == 0:
		utils.logServer("A player's username was empty after filtering out characters. Rendering home page with warning message.")
		return False
	elif username in game['gp'].players: # If the username is taken, just display an error message and let the user try again.
		utils.logServer("A player attempted to join with username {}, which is already taken. Rendering home page with warning message.".format(username))
		return False
	elif username.upper() in utils.getListOfConstants():
		utils.logServer("A player attempted to join with username {}, which matches a constant. Rendering home page with warning message.".format(username))
		return False
	elif all([c.isdigit() for c in username]):
		utils.logServer("A player attempted to join with a digit-only username. Rendering home page with warning message.")
		return False

	return True

# Start Server
if __name__ == '__main__':

	utils.resetLogs()

	signal(SIGINT, handler)

	app.jinja_env.filters['convertNameToPath'] = jinjafunctions.convertNameToPath

	socketio.run(app, debug=True, host="0.0.0.0", port=os.environ.get('PORT'))