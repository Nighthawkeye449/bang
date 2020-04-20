from card import Card, GunCard
from character import Character
from flask import Markup, render_template
from pathlib import Path
import constants
import datetime
import inspect
import json
import numbers
import re

def log(msg, file):
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
	s = "".join([c if not c.isspace() else ' ' for c in s.strip()]) # Replace all forms of whitespace with regular spaces.
	s = "_".join(capitalizeWords(s).split())
	s = "".join([char for char in s if char.isalpha() or char.isdigit() or char == '_']) # Remove all non-essential characters.
	return s

def getLocalFilePath(path=""):
	pathToRoot = "\\".join(str(Path(__file__).parent.absolute()).split("\\")[:-2])
	return "{}/{}".format(pathToRoot, path)

def getObjectFromList(function, l):
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
	return "a{} {}".format("n" if isVowel(name[0]) else "", convertRawNameToDisplay(name))

def isVowel(c):
	return c.lower() in ['a', 'e', 'i', 'o', 'u']

def getReverseFormat(formatString, s):
	formatString = formatString.replace("(", "\(").replace(")", "\)").replace("?", "\?")
	r = formatString.replace("{}", "(.*)")
	match = re.search(r, s)
	logGameplay("Result for reverse format of {} using string \"{}: {}\"".format(formatString, s, None if match == None else list(match.groups())))
	return None if match == None else list(match.groups())

def createPlayPageTuple(player, html):
	return createEmitTuples(constants.RELOAD_PLAY_PAGE, {'html': html}, recipients=[player])[0]

def getCardsInHandTemplate(player, isCurrentPlayer):
	return Markup(render_template('cards_in_hand.html', player=player, isCurrentPlayer=isCurrentPlayer))

def getCardsInPlayTemplate(player):
	return Markup(render_template('cards_in_play.html', player=player))

def getPlayerInfoListTemplate(playerInfoList):
	return Markup(render_template('player_info_list.html', playerInfoList=playerInfoList))

def createCardsDrawnTuple(player, description, cardsDrawn, startingTurn=True):
	cardsDrawnImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardsDrawn))
	data = {'html': render_template('/modals/cards_drawn.html', player=player, startingTurn=startingTurn, cardsDrawnImagesTemplate=cardsDrawnImagesTemplate, description=Markup(description))}

	return createEmitTuples(constants.SHOW_INFO_MODAL, data, [player])[0]

def createCardOptionsQuestion(self, player, options, question):
	return createQuestionTuples(question, options, recipients=[player])

# Tuples to show information in players' information modals.
def createInfoTuples(text, header=None, recipients=[], cards=None):
	logGameplay("Making info tuples for {} with text \"{}\"{}".format([r.username for r in recipients], text, " and cards {}".format([c.name for c in cards]) if cards != None else ""))
	cardImagesTemplate = None if cards == None else Markup(render_template('/modals/card_images.html', cards=cards))
	data = {'html': render_template('/modals/info.html', text=text, header=header, cardsTemplate=cardImagesTemplate)}

	return createEmitTuples(constants.SHOW_INFO_MODAL, data, recipients)

# Tuple to ask a player a question with the question modal.
def createQuestionTuple(recipient, question, options, cardsDrawn=None):
	logGameplay("Making question tuple for {} with question \"{}\" and options {}".format(recipient.username, question, options))
	cardsDrawnImagesTemplate = None if cardsDrawn == None else Markup(render_template('/modals/card_images.html', cards=cardsDrawn))
	data = {'html': render_template('/modals/question.html', question=question, cardsDrawnImagesTemplate=cardsDrawnImagesTemplate), 'question': question}
	for i, option in enumerate(options, start=1):
		data['option{}'.format(i)] = option

	return createEmitTuples(constants.SHOW_QUESTION_MODAL, data, [recipient])[0]

# Tuple to show an un-closeable waiting modal for a player.
def createWaitingModalTuple(player, text):
	data = {'html': render_template('/modals/waiting.html', text=text)}
	return createEmitTuples(constants.SHOW_WAITING_MODAL, data, [player])[0]

# Tuples to update players' action screens.
def createUpdateTuple(updateString):
	return createEmitTuples(constants.UPDATE_ACTION, {'update': updateString}, list())[0]

# Tuples to blur all but certain types of card in a player's hand.
def createCardBlurTuples(player, cardName, msg=None):
	if player.character.name == constants.CALAMITY_JANET and cardName in [constants.BANG, constants.MANCATO]:
		cardNames = [constants.BANG, constants.MANCATO]
	else:
		cardNames = [cardName]

	msg = constants.CLICK_ON_CARD if msg == None else msg

	return createInfoTuples(msg, recipients=[player]) + createEmitTuples(constants.BLUR_CARD_SELECTION, {'cardNames': cardNames}, recipients=[player])

# Tuples to show Emporio options and let the next player up pick by clicking on the card.
def createEmporioTuples(alivePlayers, cardsLeft, playerPicking):
	emitTuples = []
	data = dict()

	for p in alivePlayers:
		if p == playerPicking:
			cardImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardsLeft, clickable=True))
			text = "Click on a card to choose it:"
		else:
			cardImagesTemplate = Markup(render_template('/modals/card_images.html', cards=cardsLeft))
			text = "{} is currently picking a card:".format(playerPicking.username)

		data = {'html': render_template('/modals/info.html', text=text, header="Emporio", cardsTemplate=cardImagesTemplate)}		

		emitTuples.extend(createEmitTuples(constants.SHOW_INFO_MODAL, dict(data), recipients=[p]))

	return emitTuples

# Tuple to update a given player's cards-in-hand carousel.
def createCardCarouselTuple(player, isCurrentPlayer):
	return createEmitTuples(constants.UPDATE_CARD_HAND, {'html': getCardsInHandTemplate(player, isCurrentPlayer)}, recipients=[player])[0]

# Tuple to update the images for a player's cards in play.
def createCardsInPlayTuple(player):
	return createEmitTuples(constants.UPDATE_CARDS_IN_PLAY, {'html': getCardsInPlayTemplate(player)}, recipients=[player])[0]

# Tuple to update the image of the top discard card for everybody.
def createDiscardTuple(discardTop):
	return createEmitTuples(constants.UPDATE_DISCARD_PILE, {'path': constants.CARD_IMAGES_PATH.format(discardTop.uid if discardTop != None else constants.FLIPPED_OVER)}, recipients=[])[0]

# Tuple to update the player order/lives/etc. for everybody.
def createPlayerInfoListTuple(playerInfoList):
	return createEmitTuples(constants.UPDATE_PLAYER_LIST, {'html': getPlayerInfoListTemplate(playerInfoList)}, recipients=[])[0]

def createDiscardClickTuple(player):
	return createEmitTuples(constants.DISCARD_CLICK, dict(), recipients=[player])[0]

# Returns tuples that are processed by the server and emitted via socket.
def createEmitTuples(emitString, data, recipients=[]):
	emitTuples = []

	if recipients == []:
		emitTuples = [(emitString, data, None)]
	else:
		for r in recipients:
			emitTuples.append( (emitString, data, r) )

	logServer("Created {} emit tuples for {}: {}".format(emitString, [p.username for p in recipients], emitTuples))

	return emitTuples

def consolidateTuples(tuples):
	logServer("Checking tuples for consolidation: {}".format(tuples))

	# If there are SLEEPs in the tuples, consolidate by removing consecutive ones.
	if any([tup[0] == constants.SLEEP for tup in tuples]):
		for i in range(len(tuples) - 2, -1, -1):
			if tuples[i][0] == constants.SLEEP and tuples[i+1][0] == constants.SLEEP:
				tuples.pop(i+1)
				tuples[i][1] = max(tuples[i][1], 1) # Set the remaining sleep to 1 second at most.
		
		logServer("Consolidated SLEEPS in the tuples: {}".format(tuples))
	
	# If there are multiple waiting messages for the current player, combine them into one general waiting message.
	# Also, if there are any info tuples for that player, they come before the waiting messages this way.
	waitingModalTuples = [tup for tup in tuples if tup[0] == constants.SHOW_WAITING_MODAL]
	if len(waitingModalTuples) > 0:
		tuples = [tup for tup in tuples if tup not in waitingModalTuples] # Will move the info tuples ahead.
		
		tuples.append((constants.SLEEP, 0.2, None)) # Add a slight SLEEP to make sure the waiting message arrives last.
		if len(waitingModalTuples) == 1:
			tuples.append(waitingModalTuples[0])
		else:
			tuples.append(createWaitingModalTuple(waitingModalTuples[0][2], "Waiting for {} players...".format(len(waitingModalTuples))))

		logServer("Consolidated waiting/info messages: {}".format(tuples))

	# If a player got multiple updates to his/her card carousel, just use the last (i.e. most updated) one.
	carouselDict = dict()
	for t in tuples:
		if t[0] == constants.UPDATE_CARD_HAND:
			carouselDict[t[2].username] = t # Overwrite any older version.

	tuples = [t for t in tuples if t[0] != constants.UPDATE_CARD_HAND or t in carouselDict.values()]

	return tuples

	