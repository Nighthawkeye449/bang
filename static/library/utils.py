from static.library import constants
from static.library.card import Card, GunCard
from static.library.character import Character
from flask import Markup, render_template
from pathlib import Path
import datetime
import inspect
import json
import jsonpickle
import numbers
import os
import psycopg2
import random
import re

def saveGameToJson(game):
	return jsonpickle.encode(game)

def loadGameFromJson(json):
	return jsonpickle.decode(json)

def getDatabaseConnection():
	try:
		database_url = os.environ['DATABASE_URL']
	except KeyError:
		database_url = "postgres://nnotnxproibrzj:e68985ec9425d74ea8537f086331b59e036a0a9ac557fe3c30da6de71baf4e48@ec2-54-165-36-134.compute-1.amazonaws.com:5432/d9smgukkf0nq7q"

	return psycopg2.connect(database_url, sslmode='require')

def saveGame(game):
	conn = getDatabaseConnection()
	cur = conn.cursor()

	gameJson = saveGameToJson(game)

	sql = "INSERT INTO saved_games (lobbyNumber, gameJson, timestamp) VALUES (%s, %s, %s)"
	cur.execute(sql, (game.lobbyNumber, gameJson, datetime.datetime.now()))
	conn.commit()
	cur.close()
	conn.close()

	logServer("Saved game state for lobby {} to database.".format(game.lobbyNumber))

def loadGame(lobbyNumber):
	conn = getDatabaseConnection()
	cur = conn.cursor()

	sql = "SELECT gameJson FROM saved_games WHERE lobbyNumber = {} ORDER BY timestamp DESC LIMIT 1".format(lobbyNumber)
	cur.execute(sql)

	results = cur.fetchall()
	cur.close()
	conn.close()

	if len(results) == 0:
		logError("Unable to get saved game data for lobby number {}. Returning null.".format(lobbyNumber))
		return None

	return loadGameFromJson(results[0][0])

def loadGames():
	conn = getDatabaseConnection()
	cur = conn.cursor()

	sql = "SELECT lobbyNumber, gameJson FROM saved_games WHERE lobbyNumber >= 1000 ORDER BY timestamp DESC"
	cur.execute(sql)

	results = cur.fetchall()
	cur.close()
	conn.close()

	lobbyDict = dict()
	for result in results:
		lobbyNumber, gameJson = result
		if lobbyNumber not in lobbyDict:
			lobbyDict[lobbyNumber] = loadGameFromJson(gameJson)

	return {lobbyNumber: lobbyDict[lobbyNumber] for lobbyNumber in lobbyDict if not lobbyDict[lobbyNumber].gameOver}

def deleteGame(lobbyNumber):
	conn = getDatabaseConnection()
	cur = conn.cursor()

	sql = "DELETE * FROM saved_games WHERE lobbyNumber = {}".format(lobbyNumber)
	cur.execute(sql)
	conn.commit()
	cur.close()
	conn.close()

	logServer("Saved game state for lobby {} to database.".format(game.lobbyNumber))

def log(msg, file):
	if "html" not in msg:
		print("{}: {}".format(file.upper(), msg))
	else:
		with open(getLocalFilePath("./logs/{}.txt".format(file)), 'a+') as f:
			time = datetime.datetime.today().strftime("%d-%B-%Y %H:%M:%S")
			stack = [s[3] for s in inspect.stack()[:6]]

			usefulStack = []
			for s in stack:
				if '<' not in s and s[0].isalpha():
					usefulStack.append(s)
				else:
					break

			stackString = ("{} -> " * len(usefulStack)).format(*usefulStack[::-1]) # Show the last few methods on the stack to help debug.
			
			f.write("{}: {}\n\t\t\t\t\t\t\t\t{}\n".format(time, stackString, msg))

def logServer(msg):
	log(msg, "server")

def logPlayer(msg):
	log(msg, "player")

def logGameplay(msg):
	log(msg, "gameplay")	

def logError(msg):
	log("ERROR: {}".format(msg), "error")

def resetLogs():
	for file in ["server", "player", "gameplay", "error"]:
		path = getLocalFilePath("./logs/{}.txt".format(file))
		with open(path, "w") as f:
			f.truncate(0)

def loadCards():
	cardList = list()
	with open(getLocalFilePath("./static/json/cards.json")) as p:
		cardDict = json.load(p)
		uid = 1

		for cardName in cardDict:
			for suitValue in cardDict[cardName]['suitValues']:
				t = cardDict[cardName]['cardtype']
				if t == constants.GUN_CARD:
					cardList.append(GunCard(cardName, uid, constants.GUN_CARD, cardDict[cardName]['requiresTarget'], cardDict[cardName]['range'], suitValue))
				else:
					cardList.append(Card(cardName, uid, t, cardDict[cardName]['requiresTarget'], suitValue))
				
				uid += 1

	return cardList

def loadCharacters(includeExtras=False):
	filePaths = [getLocalFilePath("static/json/characters.json")]
	if includeExtras:
		filePaths.append(getLocalFilePath("static/json/characters_extra.json"))

	characterList = list()
	for filePath in filePaths:
		with open(filePath) as p:
			characterDict = json.load(p)
			characterList.extend([Character(**characterDict[c]) for c in characterDict]) # Load the JSON directly into Character objects.

	return characterList

def getListOfConstants():
	return [item for item in dir(constants) if not item.startswith("__")]

def isEmptyOrNull(obj):
	return obj == None or str(obj).strip() == ''

def cleanUsernameInput(s):
	# If the username is already all letters, just capitalize the first letter.
	if s.isalpha():
		return s[0].capitalize() + s[1:]

	s = s.replace('_', ' ') # Temporarily replace all underscores with regular spaces.
	s = "".join([c if not c.isspace() else ' ' for c in s.strip()]) # Replace all forms of whitespace with regular spaces.
	s = "_".join(capitalizeWords(s).split())
	s = "".join([char for char in s if char.isalpha() or char.isdigit() or char == '_']) # Remove all non-essential characters.
	return s.strip("_")[:40] # Limit usernames to 40 characters.

def getLocalFilePath(path=""):
	pathToRoot = "\\".join(str(Path(__file__).parent.absolute()).split("\\")[:-2])
	return "{}{}{}".format(pathToRoot, "/" if len(pathToRoot) > 0 else "", path)

def getUniqueItem(function, l):
	filtered = list(filter(function, l))

	return None if len(filtered) != 1 else filtered[0]

def capitalizeWords(s):
	return " ".join([word.lower().capitalize() for word in s.split()])

def convertRawNameToDisplay(s):
	return capitalizeWords(s.replace("_", " "))

def convertDisplayNameToRaw(s):
	return "_".join([word.lower() for word in s.split()])

def convertCardSuitResponseToRaw(answer):
	parenIndex = answer.index('(')
	return (convertDisplayNameToRaw(answer[:parenIndex - 1]), answer[parenIndex+1:][:-1])

def convertCardsDrawnToString(cards):
	if len(cards) == 2:
		return "{} and {}".format(*[c.getDeterminerString() for c in cards])
	else:
		return "{}, {}, and {}".format(*[c.getDeterminerString() for c in cards])

def getDeterminerString(name):
	return "{} {}".format("an" if isVowel(name[0]) else "a", convertRawNameToDisplay(name))

def isVowel(c):
	return c.lower() in ['a', 'e', 'i', 'o', 'u']

def getReverseFormat(formatString, s):
	formatString = formatString.replace("(", "\(").replace(")", "\)").replace("?", "\?")
	r = formatString.replace("{}", "(.*)")
	match = re.search(r, s)
	logGameplay("Result for reverse format of {} using string \"{}: {}\"".format(formatString, s, None if match == None else list(match.groups())))
	return None if match == None else list(match.groups())

def getCardNameValueSuitFromAnswer(answer):
	name, value, suit = getReverseFormat(constants.QUESTION_CARD_FORMAT, answer)
	return (convertDisplayNameToRaw(name), value, suit)

def getCardsInPlayTemplate(player):
	return Markup(render_template('cards_in_play.html', player=player))

def getPlayerInfoListTemplate(playerInfoList, playersWaitingFor=list()):
	return Markup(render_template('player_info_list.html', playerInfoList=playerInfoList, playersWaitingFor=playersWaitingFor))

def createClickOnPlayersTuple(player, clickType, lastCardUid=0):
	return (constants.CREATE_CLICK_ON_PLAYERS, {'clickType': clickType, 'lastCardUid': lastCardUid}, player)

def createCardsDrawnTuple(player, description, cardsDrawn, startingTurn=True):
	cardsDrawnImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardsDrawn))
	data = {'html': render_template('/modals/cards_drawn.html', player=player, startingTurn=startingTurn, cardsDrawnImagesTemplate=cardsDrawnImagesTemplate, description=Markup(description))}

	return createEmitTuples(constants.SHOW_INFO_MODAL, data, [player])[0]

def createGameOverTuple(player, msg):
	data = {'html': render_template('/modals/info.html', text=msg, header="Game Over!")}

	return createEmitTuples(constants.GAME_OVER, data, [player])[0]

# Tuples to show information in players' information modals.
def createInfoTuple(text, player, header=None, cards=None):
	logGameplay("Making info tuples for {} with text \"{}\"{}".format(player.getLogString(), text, " and cards {}".format([c.name for c in cards]) if cards != None else ""))
	cardImagesTemplate = None if cards == None else Markup(render_template('/modals/card_images.html', cards=cards))
	data = {'html': render_template('/modals/info.html', text=text, header=header, cardsTemplate=cardImagesTemplate)}

	return createEmitTuples(constants.SHOW_INFO_MODAL, data, recipients=[player])[0]

# Tuple to ask a player a question with the question modal.
def createQuestionTuple(player, question, options, cardsDrawn=None):
	logGameplay("Making question tuple for {} with question \"{}\" and options {}".format(player.username, question, options))
	cardsDrawnImagesTemplate = None if cardsDrawn == None else Markup(render_template('/modals/card_images.html', cards=cardsDrawn))
	data = {'html': render_template('/modals/question.html', question=question, cardsDrawnImagesTemplate=cardsDrawnImagesTemplate), 'question': question}
	for i, option in enumerate(options, start=1):
		data['option{}'.format(i)] = option

	return createEmitTuples(constants.SHOW_QUESTION_MODAL, data, [player])[0]

# Tuple to show an unclosable waiting modal for a player.
def createWaitingModalTuple(player, text):
	data = {'html': render_template('/modals/unclosable.html', text=text, playerIsDead=(not player.isAlive()))}
	return createEmitTuples(constants.SHOW_WAITING_MODAL, data, [player])[0]

# Tuples to update players' action screens.
def createUpdateTuples(updateString, gamePlayers):
	return createEmitTuples(constants.UPDATE_ACTION, {'update': updateString}, [p for p in gamePlayers])

# Tuple to update a single player's screen.
def createUpdateTupleForPlayer(updateString, player):
	return createEmitTuples(constants.UPDATE_ACTION, {'update': updateString}, [player])[0]

# Tuples to blur all but certain types of card in a player's hand.
def createCardBlurTuples(player, cardName, msg=None):
	if player.character.name == constants.CALAMITY_JANET and cardName in [constants.BANG, constants.MANCATO]:
		cardNames = [constants.BANG, constants.MANCATO]
	else:
		cardNames = [cardName]

	msg = constants.CLICK_ON_CARD.format(convertRawNameToDisplay(cardName) if len(cardNames) == 1 else "card") if msg == None else msg

	return [createInfoTuple(msg, player)] + createEmitTuples(constants.BLUR_CARD_SELECTION, {'cardNames': cardNames}, recipients=[player])

# Tuples to show Emporio options and let the next player up pick by clicking on the card.
def createEmporioTuples(alivePlayers, cardsLeft, playerPicking):
	emitTuples = []
	data = dict()

	for p in alivePlayers:
		if p == playerPicking:
			cardImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardsLeft, clickFunction="pickEmporioCard"))
			text = "Click on a card to choose it:"
		else:
			cardImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardsLeft))
			text = "{} is choosing a card:".format(playerPicking.username)

		data = {'html': render_template('/modals/unclosable.html', text=text, header="Emporio", cardsTemplate=cardImagesTemplate, playerIsDead=(not p.isAlive()))}		

		emitTuples.extend(createEmitTuples(constants.SHOW_INFO_MODAL, dict(data), recipients=[p]))

	return emitTuples

def createKitCarlsonTuple(player, cardChoices):
	cardImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardChoices, clickFunction="pickKitCarlsonCard"))
	text = "Kit Carlson, click the card you want to put back on the draw pile:"
	data = {'html': render_template('/modals/unclosable.html', text=text, header="Drawing Cards", cardsTemplate=cardImagesTemplate, playerIsDead=False)}		

	return createEmitTuples(constants.SHOW_INFO_MODAL, dict(data), recipients=[player])[0]

# Tuple to update a given player's cards-in-hand carousel.
def createCardCarouselTuple(player, isCurrentPlayer):
	return createEmitTuples(constants.UPDATE_CARD_HAND, {'cardInfo': player.getCardInfo(isCurrentPlayer)}, recipients=[player])[0]

# Tuple to update the images for a player's cards in play.
def createCardsInPlayTuple(player):
	return createEmitTuples(constants.UPDATE_CARDS_IN_PLAY, {'html': getCardsInPlayTemplate(player)}, recipients=[player])[0]

# Tuple to update the image of the top discard card for everybody.
def createDiscardTuples(discardTop, gamePlayers):
	return createEmitTuples(constants.UPDATE_DISCARD_PILE, {'path': constants.CARD_IMAGES_PATH.format(discardTop.uid if discardTop != None else constants.FLIPPED_OVER)}, recipients=[p for p in gamePlayers])

# Tuple to update the player order/lives/etc. for everybody.
def createPlayerInfoListTuple(playerInfoList, player, playersWaitingFor=list()):
	return createEmitTuples(constants.UPDATE_PLAYER_LIST, {'html': getPlayerInfoListTemplate(playerInfoList, playersWaitingFor=playersWaitingFor)}, recipients=[p for p in playerInfoList] if player == None else [player])[0]

def createDiscardClickTuples(player):
	return [(constants.SLEEP, 0.2, None)] + createEmitTuples(constants.DISCARD_CLICK, dict(), recipients=[player])

def createHealthAnimationTuples(playerUsername, healthChange, players):
	return [(constants.HEALTH_ANIMATION, {'username': playerUsername, 'healthChange': healthChange}, p) for p in players]

def createSetPlayerOpacityTuples(currentUsername, players):
	return [(constants.SET_PLAYER_OPACITY, {'currentUsername': currentUsername}, p) for p in players]

# Returns tuples that are processed by the server and emitted via socket.
def createEmitTuples(emitString, data, recipients=[]):
	emitTuples = []

	for r in recipients:
		emitTuples.append((emitString, data, r))

	logServer("Created {} emit tuples for {}: {}".format(emitString, [p.username for p in recipients], emitTuples))

	return emitTuples

def consolidateTuples(tuples):
	if len(tuples) > 0:
		logServer("Checking tuples for consolidation: {}".format(tuples))

		# Remove any duplicates if there are any. Maintain the order and keep the newest versions.
		nonDuplicated = []
		for t in tuples[::-1]:
			if t[0] == constants.SLEEP or t not in nonDuplicated:
				nonDuplicated.append(t)

		if len(nonDuplicated) < len(tuples):
			logServer("Tuples after removing duplicates: {}".format(tuples))
		tuples = nonDuplicated[::-1]

		# If there are SLEEPs in the tuples, remove any extra SLEEPs that are for the automatic duration.
		automaticSleepTups = [t for t in tuples if t[0] == constants.SLEEP and t[1] == constants.AUTOMATIC_SLEEP_DURATION]
		if len(automaticSleepTups) > 0:
			temp = []
			addedAutomaticSleep = False
			for t in tuples:
				if t in automaticSleepTups:
					if not addedAutomaticSleep:
						addedAutomaticSleep = True
						temp.append(t)
					else:
						temp.append((constants.SLEEP, random.randint(10, 25) / 10, None)) # Add a random delay between 1 and 2.5 seconds so that the message timing seems more natural.
				else:
					temp.append(t)

			tuples = list(temp)
			logServer("Consolidated SLEEPS in the tuples: {}".format(tuples))

		# Remove any tuples that come after the game over tuples.
		temp = list(tuples)
		tuples = []
		gameIsOver = False
		for t in temp:
			tuples.append(t)
			
			if t[0] == constants.GAME_OVER:
				gameIsOver = True
			else:
				if gameIsOver and t[0] != constants.GAME_OVER:
					break

		if gameIsOver:
			tuples = [t for t in tuples if t[0] != constants.SHOW_QUESTION_MODAL]

		logServer("tuples after consolidating: {}".format(tuples))
	
	return tuples