import eventlet
eventlet.monkey_patch()

from engineio.payload import Payload
from flask import Flask, request, render_template, make_response, redirect, url_for, session, abort, send_from_directory, jsonify
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from pathlib import Path
from signal import signal, SIGINT
from threading import Lock
import os
import random
import sys
import time
import traceback


# Import local modules.
from static.library import jinjafunctions
from static.library import utils
from static.library.constants import *
from static.library.gameplay import Gameplay
from static.library.playergame import PlayerGame

def handler(signal_received, frame):
    # Catch CTRL-C in order to separate sessions in the log.
    for func in [utils.logServer, utils.logPlayer, utils.logGameplay]:
	    func("Exiting game with CTRL-C.\n\n\n")
    sys.exit(0)

def _default(self, obj):
	return getattr(obj.__class__, "to_json", _default.default)(obj)

# Validate whether enough time has passed since the previous socket message from a given user to consider a new one valid.
# This is useful for avoiding things like accidental double-clicks.
def validResponse(username, responseInfo):
	global SOCKET_MESSAGE_TIMESTAMPS

	with lock:
		if username not in SOCKET_MESSAGE_TIMESTAMPS:
			SOCKET_MESSAGE_TIMESTAMPS[username] = time.time()
			SOCKET_MESSAGE_HISTORY[username] = responseInfo
			return True
		else:
			previousTime, previousInfo = SOCKET_MESSAGE_TIMESTAMPS[username], SOCKET_MESSAGE_HISTORY[username]

			SOCKET_MESSAGE_TIMESTAMPS[username] = time.time()
			SOCKET_MESSAGE_HISTORY[username] = responseInfo
			minTimeDifference = 1 if responseInfo not in [ENDING_TURN, CANCEL_CURRENT_ACTION] else 2

			if responseInfo != previousInfo or time.time() - previousTime >= minTimeDifference:
				return True
			else:
				utils.logServer("Not enough time has passed since {}'s last socket message ({}) for {}. Ignoring this one.".format(username, time.time() - previousTime, responseInfo))
				return False

def processGameSocketMessage(game, f):
	gameJson = utils.saveGameToJson(game)

	try:
		tuples = f()
		emitTuples(tuples)

	except Exception as e:
		LOBBY_GAME_DICT[game.lobbyNumber] = utils.loadGameFromJson(gameJson) # Revert the game state so that it's not potentially stuck in limbo.
		utils.logError(traceback.format_exc())
		utils.logGameplay("Exception caught in gameplay processing. Reverting the game state.")

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
			utils.logServer("Sleeping for {} seconds while emitting tuples.".format(args))
			time.sleep(int(args))
		
		else:
			emit(modalEmitString, args, recipient)

def getGameForPlayer(username):
	if username in USER_LOBBY_DICT:
		lobby = USER_LOBBY_DICT[username]

		if lobby not in LOBBY_GAME_DICT:
			LOBBY_GAME_DICT[lobby] = utils.loadGame(lobby)
		
		return LOBBY_GAME_DICT[lobby]

# Server setup
Payload.max_decode_packets = 200
app = Flask(__name__, static_url_path='/static', template_folder='templates')
app.secret_key = 'secretkey1568486123168'
socketio = SocketIO(app, async_mode="eventlet", async_handlers=False, cors_allowed_origins="*", always_connect=True, ping_timeout=45, ping_interval=15)

lock = Lock()

USER_LOBBY_DICT = dict()
LOBBY_GAME_DICT = dict()
LOBBIES_WAITING = set()
SOCKET_MESSAGE_TIMESTAMPS = dict()
SOCKET_MESSAGE_HISTORY = dict()
CONNECTED_USERS = dict()

#################### Socket IO functions ####################

@socketio.on(CONNECTED)
def userConnected(username):
	if username not in CONNECTED_USERS:
		utils.logServer("Received socket message '{}' from {}.".format(CONNECTED, username))
	
	CONNECTED_USERS[username] = request.sid

	if username in USER_LOBBY_DICT:
		game = getGameForPlayer(username)
		game.players[username].sid = request.sid

	socketio.emit(KEEP_ALIVE, dict(), room=request.sid)

@socketio.on(LEAVE_LOBBY)
def leaveLobby(username):
	game = getGameForPlayer(username)
	sid = game.players[username].sid
	lobby = USER_LOBBY_DICT[username]
	
	if not game.started:
		game.removePlayer(username)
		del USER_LOBBY_DICT[username]

	# Delete this lobby entirely if all the players have left.
	if len([u for u in USER_LOBBY_DICT if USER_LOBBY_DICT[u] == lobby]) == 0:
		del LOBBY_GAME_DICT[lobby]

	else:
		sorted_usernames = sorted(game.players.keys())

		# Broadcast the updated list of players to everybody else in this lobby.
		tuples = [(LOBBY_PLAYER_UPDATE, {'usernames': sorted_usernames}, p) for p in game.players.values()]

		if len(game.players) < 4 or (game.started and not all([name in USER_LOBBY_DICT for name in game.players])):
			tuples.append((HIDE_START_BUTTON, dict(), game.playerOrder[0]))
		else:
			tuples.append((SHOW_START_BUTTON, dict(), game.playerOrder[0]))

		emitTuples(tuples)

	# Reload the pick lobby page for the player who left.
	socketio.emit(RELOAD_LOBBY, {'html': render_template("pick_lobby.html", username=username)}, room=sid)


@socketio.on(START_BUTTON_CLICKED)
def startGame(username):
	lobby = USER_LOBBY_DICT[username]
	tuples = []
	utils.logServer("Received socket message '{}' from {}. Preparing game for setup in lobby {}.".format(START_BUTTON_CLICKED, username, lobby))

	game = LOBBY_GAME_DICT[lobby]
	if game.lobbyNumber in LOBBIES_WAITING:
		LOBBIES_WAITING.remove(game.lobbyNumber)

	# The game is starting for the first time, so players need to choose characters.
	if not game.started:
		tuples = game.prepareForSetup()

	# The game is being reloaded, so go straight to the play page.
	else:
		tuples = game.getStartGameTuples(reloadingGame=True)

	if tuples:
		emitTuples(tuples)

@socketio.on(SET_CHARACTER)
def setCharacter(username, character):
	utils.logServer("Received socket message '{}' from {}: {}.".format(SET_CHARACTER, username, character))
	tuples = []
	game = getGameForPlayer(username)

	with lock:
		game.assignCharacter(username, character)
		unassigned_players_remaining = [u for u in game.players if game.players[u].character == None]

		if len(unassigned_players_remaining) > 0:
			emit('character_was_set', {'players_remaining': unassigned_players_remaining})

		else:
			# Start the game for the players by loading their main play screens and info modals.
			tuples = game.getStartGameTuples()

	if tuples:
		emitTuples(tuples)

@socketio.on(INFO_MODAL_UNDEFINED)
def waitForInfoModal(username, html):
	utils.logServer("Info modal load failed for {}. Trying again.".format(username))
	
	game = getGameForPlayer(username)
	tup = (SHOW_INFO_MODAL, {'html': html}, game.players[username])

	emit(*tup)

@socketio.on(QUESTION_MODAL_UNDEFINED)
# 7 options because the most for any question would be listing 6 other player's usernames + "Never mind".
def waitForQuestionModal(username, option1, option2, option3, option4, option5, option6, option7, html, question):
	utils.logServer("Question modal load failed for {}. Trying again.".format(username))

	game = getGameForPlayer(username)
	tup = (SHOW_QUESTION_MODAL, {'option1': option1, 'option2': option2, 'option3': option3, 'option4': option4, 'option5': option5, 'option6': option6, 'option7': option7, 'html': html, 'question': question}, game.players[username])

	emit(*tup)

@socketio.on(VALIDATE_CARD_CHOICE)
def cardWasPlayed(username, uid):
	if validResponse(username, (VALIDATE_CARD_CHOICE, uid)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(VALIDATE_CARD_CHOICE, username, uid))
		
		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.validateCardChoice(username, uid))

@socketio.on(QUESTION_MODAL_ANSWERED)
def questionModalAnswered(username, question, answer):
	if validResponse(username, (QUESTION_MODAL_ANSWERED, question, answer)):
		utils.logServer("Received socket message '{}' from {}: {} -> {}.".format(QUESTION_MODAL_ANSWERED, username, question, answer))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processQuestionResponse(username, question, answer))

@socketio.on(BLUR_CARD_PLAYED)
def playBlurCard(username, uid):
	if validResponse(username, (BLUR_CARD_PLAYED, uid)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(BLUR_CARD_PLAYED, username, uid))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processBlurCardSelection(username, int(uid)))

@socketio.on(EMPORIO_CARD_PICKED)
def pickEmporioCard(username, uid):
	if validResponse(username, (EMPORIO_CARD_PICKED, uid)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(EMPORIO_CARD_PICKED, username, uid))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processEmporioCardSelection(username, int(uid)))

@socketio.on(CLAUS_THE_SAINT_CARD_PICKED)
def pickEmporioCard(username, uid):
	if validResponse(username, (CLAUS_THE_SAINT_CARD_PICKED, uid)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(CLAUS_THE_SAINT_CARD_PICKED, username, uid))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processClausTheSaintCardSelection(username, int(uid)))

@socketio.on(KIT_CARLSON_CARD_PICKED)
def pickKitCarlsonCard(username, uid):
	if validResponse(username, (KIT_CARLSON_CARD_PICKED, uid)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(KIT_CARLSON_CARD_PICKED, username, uid))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processKitCarlsonCardSelection(username, int(uid)))

@socketio.on(PLAYER_CLICKED_ON)
def playerClickedOn(username, targetName, clickType):
	if validResponse(username, (PLAYER_CLICKED_ON, targetName, clickType)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(PLAYER_CLICKED_ON, username, (targetName, clickType)))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processPlayerClickedOn(username, targetName, clickType))

@socketio.on(ABILITY_CARD_CLICKED_ON)
def playerClickedOn(username, uid, clickType):
	if validResponse(username, (ABILITY_CARD_CLICKED_ON, uid, clickType)):
		utils.logServer("Received socket message '{}' from {}: {}.".format(ABILITY_CARD_CLICKED_ON, username, (uid, clickType)))

		game = getGameForPlayer(username)

		with lock:
			processGameSocketMessage(game, lambda: game.processAbilityCardClickedOn(username, uid, clickType))

@socketio.on(ENDING_TURN)
def endingTurn(username):
	if validResponse(username, ENDING_TURN):
		utils.logServer("Received socket message '{}' from {}.".format(ENDING_TURN, username))

		game = getGameForPlayer(username)
		
		with lock:
			processGameSocketMessage(game, lambda: game.startNextTurn(username))

@socketio.on(CANCEL_CURRENT_ACTION)
def cancelEndingTurn(username):
	if validResponse(username, CANCEL_CURRENT_ACTION):
		utils.logServer("Received socket message '{}' from {}.".format(CANCEL_CURRENT_ACTION, username))

		game = getGameForPlayer(username)
		
		with lock:
			processGameSocketMessage(game, lambda: game.cancelCurrentAction(username))

@socketio.on(DISCARDING_CARD)
def discardingCard(username, uid):
	if validResponse(username, (DISCARDING_CARD, uid)):
		utils.logServer("Received socket message '{}' from {} for {}.".format(DISCARDING_CARD, username, uid))

		game = getGameForPlayer(username)
		
		with lock:
			processGameSocketMessage(game, lambda: game.playerDiscardingCard(username, int(uid)))

@socketio.on(USE_SPECIAL_ABILITY)
def specialAbility(username):
	if validResponse(username, USE_SPECIAL_ABILITY):
		utils.logServer("Received socket message '{}' from {}.".format(USE_SPECIAL_ABILITY, username))
		
		game = getGameForPlayer(username)
		
		with lock:
			processGameSocketMessage(game, lambda: game.useSpecialAbility(username))

@socketio.on(REQUEST_PLAYER_LIST)
def requestPlayerList(username):
	game = getGameForPlayer(username)
	
	with lock:
		tuples = game.getPlayerList(username)
	
	emitTuples(tuples)

@socketio.on(DISCONNECT)
def playerDisconnect():
	sid = request.sid
	if sid in CONNECTED_USERS.values():
		username = [u for u in CONNECTED_USERS if CONNECTED_USERS[u] == sid][0]
		utils.logServer("Received socket message '{}' from {} (SID {}).".format(DISCONNECT, username, sid))
		
		del CONNECTED_USERS[username]

		# If this is the last player disconnecting from his/her lobby and the game is over, just delete the lobby entirely.
		if username in USER_LOBBY_DICT and USER_LOBBY_DICT[username] in LOBBY_GAME_DICT:
			game = getGameForPlayer(username)
			if game.started and game.lobbyNumber not in LOBBIES_WAITING and len([u for u in game.players if u in CONNECTED_USERS]) == 0:
				lobby = USER_LOBBY_DICT[username]
				utils.logServer("Last user in lobby {} was disconnected. Removing the game.".format(lobby))

				for u in game.players:
					if u in USER_LOBBY_DICT:
						del USER_LOBBY_DICT[u]

				# Delete the game from the database if the game is over.
				if game.gameOver:
					del LOBBY_GAME_DICT[lobby]
					utils.deleteGame(lobby)
				else:
					LOBBY_GAME_DICT[lobby] = utils.loadGame(lobby) # Reset the game to the save state.

	else:
		utils.logServer("SID {} didn't match any current users.".format(sid))

@socketio.on(RETURN_TO_LOBBY)
def returnToPickLobby(username):
	if username in USER_LOBBY_DICT and username in CONNECTED_USERS:
		game = getGameForPlayer(username)
		del USER_LOBBY_DICT[username]
		emit(RELOAD_LOBBY, {'html': render_template("pick_lobby.html", username=username)}, game.players[username])

@socketio.on(REJOIN_GAME)
def rejoinGame(username):
	game = getGameForPlayer(username)
	with lock:
		tuples = game.getPlayerReloadingTuples(username)

	emitTuples(tuples)

#################### App routes ####################

@app.route("/", methods = ['POST', 'GET'])
def homePage():
	# The method will be POST if the text box for username has been submitted.
	if request.method == 'POST':
		if 'name' not in request.form or utils.isEmptyOrNull(request.form['name']):
			utils.logServer("A player attempted to join with an invalid username. Reloading home page.")
			return render_template('home.html')
		
		# Add this new player if the username is valid.
		username = utils.cleanUsernameInput(request.form['name'])
		validResult = checkUsernameValidity(username)
		if validResult != '':
			return render_template('home.html', warning_msg=validResult)
		else:
			if username in USER_LOBBY_DICT and USER_LOBBY_DICT[username] in LOBBY_GAME_DICT and USER_LOBBY_DICT[username] not in LOBBIES_WAITING:
				return render_template("rejoin_game.html", username=username)

			else:
				return render_template("pick_lobby.html", username=username)

	return render_template('home.html')

@app.route("/lobby", methods=['POST'])
def lobby():

	username = request.form['username']

	# Player is joining an existing lobby.
	if not utils.isEmptyOrNull(request.form['lobby_number']):
		lobbyNumber = request.form['lobby_number']

		if not lobbyNumber.isdigit():
			return render_template('pick_lobby.html', username=username, warning_msg="Sorry, that's in invalid lobby number.")
		else:
			lobbyNumber = int(lobbyNumber)
		
		if lobbyNumber not in LOBBY_GAME_DICT:
			return render_template('pick_lobby.html', username=username, warning_msg="Sorry, that lobby couldn't be found.")

		# Don't allow players to join a lobby for a game that's already started.
		elif LOBBY_GAME_DICT[lobbyNumber].started and username not in LOBBY_GAME_DICT[lobbyNumber].players:
			return render_template('pick_lobby.html', username=username, warning_msg="Sorry, that game has already started.")

		# Don't allow players to join a lobby if it's already full.
		elif len(LOBBY_GAME_DICT[lobbyNumber].players) == 7:
			return render_template('pick_lobby.html', username=username, warning_msg="Sorry, that lobby is already full.")

	# Player is joining a new lobby.
	else:
		lobbyNumber = None
		
		# Generate new lobby numbers until an unused one is made.
		while lobbyNumber == None or lobbyNumber in LOBBY_GAME_DICT:
			lobbyNumber = random.randint(1000, 9999)
		
		# Create a new game for this lobby.
		LOBBY_GAME_DICT[lobbyNumber] = Gameplay()
		LOBBY_GAME_DICT[lobbyNumber].lobbyNumber = lobbyNumber
	
	game = LOBBY_GAME_DICT[lobbyNumber]
	USER_LOBBY_DICT[username] = lobbyNumber
	LOBBIES_WAITING.add(lobbyNumber)

	if username not in game.players:
		game.addPlayer(username, CONNECTED_USERS[username] if username in CONNECTED_USERS else 0)
		username_order = [p.username for p in game.playerOrder]
		tuples = [(LOBBY_PLAYER_UPDATE, {'usernames': username_order}, p) for p in game.players.values()]
	else:
		game.players[username].sid = CONNECTED_USERS[username]
		username_order = [p.username for p in game.playerOrder if p.username in USER_LOBBY_DICT]
		tuples = [(LOBBY_PLAYER_UPDATE, {'usernames': username_order}, p) for p in game.players.values() if p.username in USER_LOBBY_DICT]

	if (not game.started and 4 <= len(game.players) <= 7) or (game.started and all([name in USER_LOBBY_DICT for name in game.players])):
		tuples.append((SHOW_START_BUTTON, dict(), game.playerOrder[0]))

	# Broadcast the updated list of players to everybody in this lobby.
	emitTuples(tuples)

	# Render the lobby page with all usernames for the new player.
	utils.logServer("Rendering lobby for {}".format(username))
	return render_template('lobby.html', usernames=username_order, username=username, lobbyNumber=USER_LOBBY_DICT[username])

@app.route("/setup", methods = ['POST', 'GET'])
def setup():
	username = request.json['username']
	utils.logServer("Received request for '/setup' from {}".format(username))

	game = getGameForPlayer(username)
	
	utils.logServer("Rendering setup page for {}.".format(username))
	return render_template('setup.html',
		playerOrderString=" -> ".join(["{}{}".format(p.username, "" if p != game.playerOrder[0] else " (Sheriff) ") for p in game.playerOrder]),
		role=game.players[username].role,
		option1=game.players[username].characterOptions[0],
		option2=game.players[username].characterOptions[1],
		numOtherPlayers=len(game.players) - 1)

def checkUsernameValidity(username):
	invalidMsg = "Sorry, that username is invalid! Try something else."
	usernameTakenMsg = "Sorry, that username is taken! Try something else."
	if len(username) == 0:
		utils.logServer("A player's username was empty after filtering out characters. Rendering home page with warning message.")
		return invalidMsg
	elif username.upper() in utils.getListOfConstants():
		utils.logServer("A player attempted to join with username {}, which matches a constant. Rendering home page with warning message.".format(username))
		return invalidMsg
	elif all([c.isdigit() for c in username]):
		utils.logServer("A player attempted to join with a digit-only username. Rendering home page with warning message.")
		return invalidMsg
	elif username in CONNECTED_USERS: # If the username is taken, just display an error message and let the user try again.
		utils.logServer("A player attempted to join with username {}, which is already taken. Rendering home page with warning message.".format(username))
		return usernameTakenMsg

	return ''

# Start Server
if __name__ == '__main__':

	utils.resetLogs()

	signal(SIGINT, handler)

	app.jinja_env.filters['convertNameToPath'] = jinjafunctions.convertNameToPath

	LOBBY_GAME_DICT = utils.loadGames()
	LOBBIES_WAITING |= set(LOBBY_GAME_DICT.keys())
	utils.logServer("Successfully loaded {} games from the database.".format(len(LOBBY_GAME_DICT)))

	socketio.run(app, debug=False, host="0.0.0.0", port=os.environ.get('PORT'))