from static.library.constants import *
from static.library.playergame import PlayerGame
from static.library import utils
from flask import Markup, render_template

import random

class Gameplay(dict):
	def __init__(self):
		self.lobbyNumber = None
		self.players = dict() # players[username] = PlayerGame()
		self.playerOrder = list() # Current player should always be at index 0.
		self.allCards = utils.loadCards()
		self.drawPile = list(self.allCards)
		self.discardPile = list()
		self.started = False
		self.gameOver = False
		self.remainingRoles = None
		self.characters = None
		self.remainingCharacters = None
		self.currentTurn = 0
		self.currentCard = None
		self.sheriffUsername = None
		self.dynamiteStartTurn = None
		self.dynamiteUsername = None
		self.drawingToStartTurn = True
		self.discardingCards = False
		self.bangedThisTurn = False
		self.emporioOptions = list()
		self.duelPair = list()
		self.updatesList = list() # A list of all updates throughout the game, which will be pulled whenever reloading the play page.
		self.infoTupleDict = dict()
		self.unansweredQuestions = dict()
		self.playersWaitingFor = list()
		self.specialAbilityCards = {SID_KETCHUM: None, SLAB_THE_KILLER: None, KIT_CARLSON: None}

		dict.__init__(self)

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return str(vars(self))

	def addPlayer(self, username, sid):
		p = PlayerGame(username, sid)
		
		self.players[username] = p
		self.playerOrder.append(p)

	def removePlayer(self, username):
		self.playerOrder.remove(self.players[username])
		del self.players[username]

	def prepareForSetup(self):
		self.started = True
		num_players = len(self.players)

		self.characters = utils.loadCharacters()
		self.remainingCharacters = list(self.characters)

		if num_players == 4: self.remainingRoles = [SHERIFF, OUTLAW, OUTLAW, RENEGADE]
		elif num_players == 5: self.remainingRoles = [SHERIFF, VICE, OUTLAW, OUTLAW, RENEGADE]
		elif num_players == 6: self.remainingRoles = [SHERIFF, VICE, OUTLAW, OUTLAW, OUTLAW, RENEGADE]
		else: self.remainingRoles = [SHERIFF, VICE, VICE, OUTLAW, OUTLAW, OUTLAW, RENEGADE]

		random.shuffle(self.playerOrder)
		random.shuffle(self.remainingCharacters)
		random.shuffle(self.remainingRoles)
		random.shuffle(self.drawPile)

		for username in self.players:
			self.assignNewPlayer(username)

		# Make sure the sheriff starts the game.
		self.rotatePlayerOrder()

		utils.logGameplay("Successfully prepared for setup.")

		return [(START_GAME, dict(), p) for p in self.players.values()]

	def assignNewPlayer(self, username):
		player = self.players[username]

		if len(self.remainingRoles) == 0 or len(self.remainingCharacters) < 2:
			utils.logError("Trying to pop element from empty list for {}.".format(player.username))
		else:
			player.role = self.remainingRoles.pop()
			player.characterOptions = [self.remainingCharacters.pop(), self.remainingCharacters.pop()]
			utils.logGameplay("Assigned {} to a role of {} with character options of {}.".format(player.username, player.role, [c.name for c in player.characterOptions]))

		if player.role == SHERIFF:
			self.sheriffUsername = player.username

	def assignCharacter(self, username, c):
		character = self.getCharacterByName(c)
		player = self.players[username]
		player.character = character
		
		# Assign the player's initial number of lives.
		player.lifeLimit = character.numLives + (1 if self.sheriffUsername == username else 0)
		player.lives = player.lifeLimit

		# Deal out however many cards the player should start with.
		self.drawCardsForPlayer(player, player.lives)

		utils.logGameplay("Assigned {} to a character of {} with an initial hand of {}.".format(player.username, c, [card.name for card in player.cardsInHand]))

	def getCharacterByName(self, c):
		return utils.getUniqueItem(lambda character: character.name == c, self.characters)

	def getStartGameTuples(self):
		utils.logGameplay("Initial player order will be: {}. STARTING GAME.".format([u.username for u in self.playerOrder]))

		return [(RELOAD_PLAY_PAGE, {'html': self.renderPlayPageForPlayer(p.username), 'cardInfo': p.getCardInfo(p == self.playerOrder[0])}, p) for p in self.playerOrder] \
				 + [(SLEEP, 0.5, None)] + [t for t in self.startNextTurn(self.getCurrentPlayerName()) if t[0] != SLEEP]

	def getPlayerReloadingTuples(self, username, gameOver=False):
		player = self.players[username]
		emitTuples = []

		emitTuples.append((RELOAD_PLAY_PAGE, {'html': self.renderPlayPageForPlayer(username), 'cardInfo': player.getCardInfo(player == self.playerOrder[0])}, player))
		emitTuples.append((SLEEP, 0.5, None))
		emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
		emitTuples.append(utils.createCardsInPlayTuple(player))

		emitTuples += [utils.createUpdateTupleForPlayer(update, player) for update in self.updatesList]

		if not gameOver:
			if username in self.unansweredQuestions:
				questionTup = self.unansweredQuestions[username]
				emitTuples += [utils.createQuestionTuple(player, questionTup[0], questionTup[1], cardsDrawn=questionTup[2])]
			elif username in self.infoTupleDict:
				emitTuples.append(self.infoTupleDict[username])

		return emitTuples

	def rotatePlayerOrder(self):
		self.playerOrder = self.playerOrder[1:] + self.playerOrder[:1]

		# During game setup, rotate until the Sheriff starts.
		if self.currentTurn == 0:
			if self.playerOrder[0].role != SHERIFF:
				self.rotatePlayerOrder()
		# In-game, keep rotating until a non-eliminated player starts.
		else:
			if not self.playerOrder[0].isAlive():
				self.rotatePlayerOrder()

	def getCurrentPlayerName(self):
		return self.playerOrder[0].username

	def getTopDiscardCard(self):
		return self.discardPile[-1] if len(self.discardPile) > 0 else None

	def advanceTurn(self):
		if self.currentTurn > 0:
			self.rotatePlayerOrder()
		self.currentTurn += 1
		self.bangedThisTurn = False
		self.drawingToStartTurn = True

	def startNextTurn(self, username):
		if username == None or username not in self.players:
			utils.logError("Unrecognized username {} passed in for starting next turn.".format(username, self.players.keys()))
			return []
		elif username != self.getCurrentPlayerName():
			utils.logError("{} shouldn't be able to end the current turn (the current player is {}).".format(username, self.getCurrentPlayerName()))
			return []
		elif self.currentCard != None or not self.currentCardCanBeReset():
			utils.logGameplay("{} tried to end their turn but the current card ({}) is still being processed.".format(username, self.currentCard))
			return [self.createInfoTuple("You can't end your turn while the {} is still being played!".format(self.currentCard.getDisplayName()), self.players[username])]

		emitTuples = []

		player = self.playerOrder[0]
		cardsTooMany = 0 if player.jailStatus == 1 else player.countExcessCards()
		
		# self.discardingCards will be False if the player just triggered the end of his/her turn, so have him/her discard cards as required.
		if self.currentTurn > 0 and cardsTooMany > 0:
			emitTuples.extend(utils.createDiscardClickTuples(player))

			if cardsTooMany > 0:
				clickString = "Click on cards in your hand to discard them." if cardsTooMany > 1 else "Click on a card in your hand to discard it."

				if not self.discardingCards:
					clickString += " Press Shift-C to cancel."

				text = "You need to discard {} card{}! {}".format(cardsTooMany, "s" if cardsTooMany > 1 else "", clickString)
				emitTuples.append(self.createInfoTuple(text, player))

			self.discardingCards = True

		else: # The player doesn't need to discard or is done, so move on to the next player.
			self.discardingCards = False

			if self.currentTurn > 0 and self.playerOrder[0].jailStatus == 0:
				emitTuples.extend(self.createUpdates("{} ended their turn.".format(self.getCurrentPlayerName())))
			
			self.playerOrder[0].jailStatus = 0 # A player should never end his/her turn in jail.
			
			# Rotate to the next alive player and set up for the new turn.
			self.advanceTurn()
			utils.logGameplay("Starting the next turn. The new current player is {}.".format(self.getCurrentPlayerName()))
			player = self.playerOrder[0]
			emitTuples.extend(self.createUpdates("{} started their turn.".format(player.username)))

			drawTuples = self.processSpecialCardDraw(player)
			# If the dynamite exploded, load the player info early so that the health animation shows up above the correct player.
			if any([t[0] == HEALTH_ANIMATION and t[1]['healthChange'] == -3 for t in drawTuples]):
				emitTuples.extend([utils.createPlayerInfoListTuple(self.playerOrder, p) for p in self.playerOrder])
				emitTuples.append((SLEEP, 0.2, None))

			# If the player is:
			# 	- Lucky Duke and did a "draw!" at the start of his turn
			# 	- still in jail
			#	- eliminated
			# skip/end their turn and return here.
			if (player.character.name == LUCKY_DUKE and len(drawTuples) > 0) or player.jailStatus == 1 or not player.isAlive():
				return emitTuples + drawTuples

			emitTuples.extend(self.getTuplesForNewTurn(drawTuples=drawTuples))

		utils.logGameplay("Returning the following tuples for the start of a new turn: {}".format(emitTuples))

		return emitTuples

	def getTuplesForNewTurn(self, drawTuples=[]):
		emitTuples = []

		# Generate all the tuples to update every player's screen for the new turn.
		for p in self.playerOrder:
			emitTuples.append(utils.createCardCarouselTuple(p, p == self.playerOrder[0]))
			emitTuples.append(utils.createCardsInPlayTuple(p))

		emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))

		# If there was a "draw!" that didn't return yet, add those tuples in here.
		if len(drawTuples) > 0:
			emitTuples.extend(drawTuples)

		for p in self.playerOrder:
			emitTuples.extend(self.makeCardDrawModalTuples(p))

		emitTuples.extend([utils.createPlayerInfoListTuple(self.playerOrder, p) for p in self.playerOrder])

		return emitTuples

	def cancelCurrentAction(self, username):
		emitTuples = []
		player = self.players[username]

		if player != self.playerOrder[0]:
			return []

		if self.discardingCards:
			if "discarded" not in self.updatesList[-1]:
				self.discardingCards = False
				emitTuples.append(self.createInfoTuple("You canceled discarding.", player))
				emitTuples.append(utils.createCardCarouselTuple(player, True))
			else:
				emitTuples.append(self.createInfoTuple("You've already discarded, so you can't cancel anymore.", player))
		else:
			if self.currentCard == None:
				utils.logError("{} is canceling, but isn't discarding and the current card is set to None.".format(player.getLogString()))
				return []

			emitTuples.append(self.createInfoTuple("You canceled your {}.".format(self.currentCard.getDisplayName()), player))
			self.currentCard = None

		return emitTuples

	def createUpdates(self, updateString):
		self.updatesList.append(updateString)
		return utils.createUpdateTuples(updateString, self.players.values())

	def createInfoTuple(self, text, player, header=None, cards=None):
		self.infoTupleDict[player.username] = utils.createInfoTuple(text, player, header, cards)
		return self.infoTupleDict[player.username]

	def createCardsDrawnTuple(self, player, description, cardsDrawn, startingTurn=True):
		self.infoTupleDict[player.username] = utils.createCardsDrawnTuple(player, description, cardsDrawn, startingTurn=startingTurn)
		return self.infoTupleDict[player.username]

	def addQuestion(self, player, question, options, cardsDrawn=None):
		if player.username in self.unansweredQuestions:
			utils.logError("{} is getting asked \"{}\" before answering \"{}\".".format(question, self.unansweredQuestions[player.username]))
			return None

		self.unansweredQuestions[player.username] = (question, options, cardsDrawn)
		self.playersWaitingFor.append(player.username)
		return utils.createQuestionTuple(player, question, options, cardsDrawn=cardsDrawn)

	def getDynamiteCard(self):
		return utils.getUniqueItem(lambda c: c.name == DYNAMITE, self.allCards)

	def getCardByUid(self, uid):
		return utils.getUniqueItem(lambda c: c.uid == int(uid), self.allCards)

	def drawOneCard(self):
		card = self.drawPile.pop()

		# Reshuffle the draw pile once it's empty.
		if len(self.drawPile) == 0:
			utils.logGameplay("Reshuffling the draw pile. It will now have {} cards.".format(len(self.discardPile)))
			self.drawPile = list(self.discardPile)
			self.discardPile = list()

			missingCards = [c for c in self.allCards if c not in self.drawPile and all([c not in (p.cardsInHand + p.getCardsOnTable()) for p in self.getAlivePlayers()])]
			if len(missingCards) > 0:
				utils.logError("There were missing cards while reshuffling: {}. Adding them back".format(missingCards))
				self.drawPile += missingCards

			random.shuffle(self.drawPile)

		return card

	# Useful for "draw!", after which cards always need to be discarded.
	def drawAndDiscardOneCard(self):
		card = self.drawOneCard()
		self.discardPile.append(card)
		return card

	def drawCardsForPlayer(self, player, n=1):
		card = self.drawOneCard()
		player.addCardToHand(card)
		utils.logGameplay("Drew {} (UID: {}) into the hand of {}. The draw pile has {} cards left.".format(card.getDeterminerString(), card.uid, player.username, len(self.drawPile)))

		if n > 1:
			self.drawCardsForPlayer(player, n-1)

	def drawCardsForPlayerTurn(self, player, extraInfo=''):
		if player.character.name == BLACK_JACK:
			self.drawCardsForPlayer(player, 2)
			if player.cardsInHand[-1].suit in [HEART, DIAMOND]: # Black Jack gets to draw one more if the second card is a heart or diamond.
				self.drawCardsForPlayer(player)
				result = player.cardsInHand[-3:]
			else:
				result = player.cardsInHand[-2:]
		
		elif player.character.name == KIT_CARLSON:
			result = []
			for _ in range(3):
				result.append(self.drawOneCard())
		
		elif player.character.name == JESSE_JONES: # For Jesse Jones, extraInfo will either be empty or the username of the player to draw from.
			if extraInfo:
				opponent = self.players[extraInfo]
				player.addCardToHand(opponent.panico())
				utils.logGameplay("{} drew {} ({}) from the hand of {}.".format(player.getLogString(), player.cardsInHand[-1].getDeterminerString(), player.cardsInHand[-1].uid, opponent.username))
				self.drawCardsForPlayer(player)
			else:
				self.drawCardsForPlayer(player, 2)
			
			result = player.cardsInHand[-2:]
		
		elif player.character.name == PEDRO_RAMIREZ: # For Pedro Ramirez, extraInfo will be non-empty if the discard pile should be used for the first card.
			if extraInfo:
				player.addCardToHand(self.discardPile.pop())
				self.drawCardsForPlayer(player)
			else:
				self.drawCardsForPlayer(player, 2)
			
			result = player.cardsInHand[-2:]
		
		else:
			# Default case.
			self.drawCardsForPlayer(player, 2)
			result = player.cardsInHand[-2:]

		utils.logGameplay("Drew {} cards for {}.".format(len(result), player.username))
		return result

	def getDiscardTuples(self, card):
		return utils.createDiscardTuples(card, self.players.values())

	def discardCard(self, player, card):
		player.getRidOfCard(card)
		self.discardPile.append(card)
		utils.logGameplay("Adding {} (UID: {}) to the discard pile.".format(card.getDeterminerString(), card.uid))

	def playerDiscardingCard(self, username, uid):
		player = self.players[username]
		card = self.getCardByUid(uid)
		emitTuples = []

		if uid not in {c.uid for c in player.cardsInHand + player.getCardsOnTable()}:
			utils.logError("{} is trying to discard {} (UID: {}) but doesn't have it in their possession.".format(player.getLogString(), card.name, uid))
			return []

		if player.character.name != SID_KETCHUM or self.specialAbilityCards[SID_KETCHUM] == None:
			if player.countExcessCards() == 0:
				utils.logError("{} tried to discard a card but is already at/under the limit.".format(player.getLogString()))
				return []

			self.discardCard(player, card)

			emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
			emitTuples.extend(self.createUpdates("{} discarded {}.".format(username, card.getDeterminerString())))
			emitTuples.append(utils.createCardCarouselTuple(player, True))

			excessCards = player.countExcessCards()
			if excessCards == 0:
				utils.logGameplay("{} discarded a card and now has 0 excess cards. Ending their turn.".format(player.getLogString()))
				emitTuples.extend(self.startNextTurn(player.username))
			else:
				utils.logGameplay("{} discarded a card but still has {} excess card(s). Enabling discard click again.".format(player.getLogString(), excessCards))
				emitTuples.extend(utils.createDiscardClickTuples(player))

		# Process Sid Ketchum discarding cards for his special ability here.
		else:
			self.specialAbilityCards[SID_KETCHUM].append(card)

			if len(self.specialAbilityCards[SID_KETCHUM]) == 1:
				# Temporarily remove the card from the hand to show an updated hand in the UI.
				player.getRidOfCard(card)

				emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

				player.cardsInHand.append(card) # Re-insert the card because it properly gets discarded later.

				emitTuples.extend(utils.createDiscardClickTuples(player))

			else: # Both cards have been selected, so actually discard them and gain the life.
				emitTuples = self.processSidKetchumAbility(player)

		return emitTuples

	# Check whether the user should even have the option of playing this card right now.
	# If it's a targeted card, also return question modal information listing all alive opponents as choices...
	# ...instead of filtering here; validate target choices separately so that that information can be shown in a modal too.
	def validateCardChoice(self, username, uid):
		card = self.getCardByUid(int(uid))

		if card == None:
			utils.logError("Received request to play card with UID {}. UID not recognized.".format(uid))
			return []
		
		elif username != self.getCurrentPlayerName():
			utils.logError("Received request to play a card from {}, but it's currently {}'s turn.".format(username, self.getCurrentPlayerName()))
			return []

		elif self.drawingToStartTurn:
			utils.logError("{} is trying to play a card but isn't done drawing cards yet.".format(username))
			return []
		
		utils.logServer("Received socket message from {} to play {} (UID: {}) (current card: {}).".format(username, card.getDisplayName(), uid, self.currentCard))

		player = self.players[username]
		emitTuples = []
		targetName = None
		aliveOpponents = self.getAliveOpponents(username)

		if card not in player.cardsInHand:
			utils.logError("{} tried to play {} ({}) but doesn't have it in his/her hand.".format(username, card.getDeterminerString(), uid))
			return []

		# If the card clicking erroneously somehow allows the player to play a card while s/he's discarding, just discard from here.
		elif self.discardingCards:
			utils.logError("{} is discarding but entered card validation anyway. Discarding card {} from here.".format(player.getLogString(), uid))
			return self.playerDiscardingCard(username, uid)

		elif self.currentCard != None:
			return [self.createInfoTuple("Slow down! We're still waiting for your {} to get finished.".format(self.currentCard.getDisplayName()), player)]

		
		if self.isEffectiveBang(player, card.name):
			if self.bangedThisTurn and player.hasBangLimit():
				response = "You've already played a Bang this turn!"
			else:
				validTargets = self.getAllValidTargetsForCard(player, BANG)
				if len(validTargets) == 0:
					response = "There's nobody in range for a Bang right now!"
				else:
					response = OK_MSG
					utils.logGameplay("Adding player clicks for {} for Bang.".format(username))
					emitTuples = utils.createClickOnPlayersTuples(player, "Click on the player you want to shoot.", TARGETED_CARD_PLAYER_CLICK)

		elif card.name == MANCATO:
			response = "You can't play a Mancato right now!"

		elif card.name in [PANICO, CAT_BALOU]:
			validTargets = self.getAllValidTargetsForCard(player, card.name)
			if len(validTargets) == 0:
				response = "There's nobody in range for {} right now!".format(card.getDeterminerString())
			else:
				response = OK_MSG
				emitTuples = utils.createClickOnPlayersTuples(player, "Click on the player whose cards you want to target.", TARGETED_CARD_PLAYER_CLICK)

		elif card.name == DUELLO:
			response = OK_MSG

			if len(aliveOpponents) == 1: # If there's only 1 alive opponent left, automatically play the Duello against him/her.
				targetName = aliveOpponents[0].username
			else:
				emitTuples = utils.createClickOnPlayersTuples(player, "Click on the player you want to duel.", TARGETED_CARD_PLAYER_CLICK)

		elif card.name == BIRRA:
			if len(self.getAlivePlayers()) == 2:
				response = "You can't use Birras when it's 1-v-1!"
			elif player.lives == player.lifeLimit:
				response = ALREADY_MAX_LIVES
			else:
				response = OK_MSG

		elif card.name == SALOON:
			if all([p.lives == p.lifeLimit for p in self.getAlivePlayers()]):
				response = "You can't play a Saloon right now - no one would gain a life!"
			else:
				response = OK_MSG

		elif card.cardtype in [BLUE_CARD, GUN_CARD]:
			if card.name in [c.name for c in player.cardsInPlay]:
				response = "You already have {} in play!".format(card.getDeterminerString())
			elif card.cardtype == GUN_CARD and GUN_CARD in [c.cardtype for c in player.cardsInPlay]:
				response = OK_MSG
				currentGun = utils.getUniqueItem(lambda c: c.cardtype == GUN_CARD, player.cardsInPlay)
				emitTuples = [self.addQuestion(player, QUESTION_REPLACE_GUN, [REPLACE_GUN.format(currentGun.getDisplayName(), card.getDisplayName()), NEVER_MIND])]
			elif len(player.cardsInPlay) == 2:
				response = OK_MSG
				emitTuples = [self.addQuestion(player, QUESTION_IN_PLAY, ["Replace the {}".format(c.getQuestionString()) for c in player.cardsInPlay] + [NEVER_MIND])]
			else:
				response = OK_MSG

		elif card.name == PRIGIONE:
			validTargets = self.getAllValidTargetsForCard(player, PRIGIONE)
			if len(validTargets) > 0:
				response = OK_MSG
				emitTuples = utils.createClickOnPlayersTuples(player, "Click on the player you want to put in jail.", TARGETED_CARD_PLAYER_CLICK)

			else:
				response = "You can't jail anyone right now!"

		else: # Any cards not listed should always default to OK and with no question to ask.
			response = OK_MSG
		
		utils.logGameplay("Response for {} playing {} right now: \"{}\".".format(username, card.getDeterminerString(), response))

		if response == OK_MSG:
			self.currentCard = card

			if len(emitTuples) == 0: # If there are no messages/questions to emit, the card can just be played without any more processing.
				return self.playCurrentCard(player, targetName)
			else:
				return emitTuples

		else:
			return [self.createInfoTuple(response, player, header="Invalid Card")]

	# Function to process what happens next when a card is actually put down and played (given a valid target, if applicable).
	def playCurrentCard(self, player, targetName=None):
		emitTuples = []
		card = self.currentCard

		if self.currentCard == None:
			utils.logError("{} is trying to play the current card, but the current card is None.".format(player.username))
			return []

		utils.logGameplay("{} playing {}{}.".format(player.username, card.getDeterminerString(), " against {}".format(targetName) if targetName else ""))

		# If the card isn't a blue card, it should go on top of the discard pile after being played.
		if card.cardtype == REGULAR_CARD:
			self.discardCard(player, card)
			emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
		
		# Otherwise, the player needs to get rid of it from their hand, but it won't go on the discard pile yet.
		else:
			player.getRidOfCard(card)

		# Make sure the card is removed from the player's hand in the UI.
		emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

		# Handle Suzy Lafayette's ability for when she's the current player.
		# The exception is a duel - in that case, the card shouldn't be drawn until after the duel ends.
		if card.name != DUELLO and player.character.name == SUZY_LAFAYETTE:
			emitTuples.extend(self.processSuzyLafayetteAbility(player))

		# Checking that these are valid moves has already been done in the validateCardChoice and validateTargetChoice methods.
		if targetName == None:
			if card.cardtype in [BLUE_CARD, GUN_CARD]:
				player.cardsInPlay.append(card)
				emitTuples.append(utils.createCardsInPlayTuple(player))
				emitTuples.extend(self.createUpdates("{} put {} in play.".format(player.username, card.getDeterminerString())))

			elif card.name == DYNAMITE:
				player.specialCards.append(card)
				self.dynamiteUsername = player.username
				self.dynamiteStartTurn = self.currentTurn + 1

				text = "{} played the dynamite!".format(player.username)
				emitTuples.extend([self.createInfoTuple(text, p) for p in self.getAliveOpponents(player.username)])
				emitTuples.extend(self.createUpdates(text))

			elif card.name == BIRRA:
				player.gainOneLife()
				emitTuples.extend(self.createUpdates("{} played a Birra and now has {} lives.".format(player.username, player.lives)))
				emitTuples.extend(utils.createHealthAnimationTuples(player.username, 1, self.playerOrder))

			if card.name == SALOON:
				for p in self.getAlivePlayers():
					if p.lives != p.lifeLimit:
						emitTuples.extend(utils.createHealthAnimationTuples(p.username, 1, self.playerOrder))
					
					p.gainOneLife() # Will automatically limit the player to his/her maximum lives.

				emitTuples.extend(self.createUpdates("{} played a Saloon.".format(player.username)))

			elif card.name in [DILIGENZA, WELLS_FARGO]:
				numCards = 3 if card.name == WELLS_FARGO else 2
				self.drawCardsForPlayer(player, numCards)
				emitTuples.extend(self.createUpdates("{} played {} and drew {} cards.".format(player.username, card.getDeterminerString(), numCards)))
				emitTuples.append(utils.createCardCarouselTuple(player, True))
				emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
				emitTuples.append(self.createCardsDrawnTuple(player, "You drew {} cards for {}:".format(numCards, card.getDisplayName()), player.cardsInHand[-numCards:], startingTurn=False))

			elif card.name == EMPORIO:
				# Get one card option for each non-eliminated player and show all players the choices.
				self.emporioOptions = list()
				for _ in range(len(self.getAlivePlayers())):
					self.emporioOptions.append(self.drawOneCard())
				
				emitTuples.extend(self.createUpdates("{} played an Emporio!".format(player.username)))

				if len({c.name for c in self.emporioOptions}) > 1:
					utils.logGameplay("Initial options for Emporio for {}: {}".format([p.username for p in self.getAlivePlayers()], [c.uid for c in self.emporioOptions]))
					self.playersWaitingFor.append(player.username)

					emporioTuples = utils.createEmporioTuples(self.getAlivePlayers(), self.emporioOptions, player)
					for t in emporioTuples:
						self.infoTupleDict[t[2].username] = t
						emitTuples.extend(emporioTuples)

				else:
					utils.logGameplay("All intial options for Emporio are the same. Distributing 1 card to each player automatically.")
					emitTuples.extend(self.processEmporioAutomatic(self.getAlivePlayers()[0]))

			elif card.name in [GATLING, INDIANS]:
				emitTuples.extend(self.processBangGatlingIndians(player, card.name))

		else:
			target = self.players[targetName]

			if self.isEffectiveBang(player, card.name):
				emitTuples.extend(self.processBangGatlingIndians(player, BANG, target))

			elif card.name in [PANICO, CAT_BALOU]:
				emitTuples.extend(self.processPanicoCatBalou(player, target, card.name))

			elif card.name == DUELLO:
				self.duelPair = [player, target]
				
				emitTuples.extend(self.createUpdates("{} played a Duello against {}.".format(player.username, targetName)))
				emitTuples.append(utils.createWaitingModalTuple(player, WAITING_DUELLO_REACTION.format(target.username)))

				if len(target.getCardTypeFromHand(BANG)) == 0: # Automatically count the Duello as a win if the target doesn't have any Bangs.
					emitTuples.append((SLEEP, AUTOMATIC_SLEEP_DURATION, None))
					emitTuples.extend(self.processDuelloResponse(target, LOSE_A_LIFE))
				else:
					emitTuples.append(self.addQuestion(target, QUESTION_DUELLO_REACTION.format(player.username), [PLAY_A_BANG, LOSE_A_LIFE]))

			elif card.name == PRIGIONE:
				target.jailStatus = 1
				target.specialCards.append(card)

				emitTuples.append(self.createInfoTuple("{} just put you in jail!".format(player.username), target))
				emitTuples.extend(self.createUpdates("{} put {} in jail.".format(player.username, target.username)))

		if self.currentCardCanBeReset():
			self.currentCard = None

		if self.gameOver:
			emitTuples = [t for t in emitTuples if t[0] != SLEEP] # Don't include any SLEEPs once the game is over.

		return emitTuples

	def getAllValidTargetsForCard(self, player, cardName):
		if self.isEffectiveBang(player, cardName):
			validTargets = [target for target in self.getAliveOpponents(player.username) if self.targetIsInRange(player, target)] 
		
		elif cardName == PANICO:
			validTargets = [target for target in self.getAliveOpponents(player.username) if self.targetIsInRange(player, target, bang=False) and len(target.cardsInHand + target.getCardsOnTable()) >= 1] 

		elif cardName == CAT_BALOU:
			validTargets = [target for target in self.getAliveOpponents(player.username) if len(target.cardsInHand) + len(target.getCardsOnTable()) >= 1] 

		elif cardName == PRIGIONE:
			validTargets = [target for target in self.getAliveOpponents(player.username) if target.role != SHERIFF and target.jailStatus == 0]

		else:
			utils.logError("Shouldn't be attempting to get valid targets for {}.".format(cardName))
			return []

		utils.logGameplay("The valid targets for {} for {} are {}".format(player.username, cardName, [t.username for t in validTargets]))
		return validTargets

	def validateTargetChoice(self, player, target, card=None): # Check whether this specific target is valid for the given user.
		if card == None:
			card = self.currentCard

		utils.logGameplay("Checking whether {} playing {}{} is valid.".format(player.username, card.getDeterminerString(), " against {}".format(target.username) if target.username else ""))

		if not target.isAlive():
			utils.logGameplay("{} tried to play {} against {}, who is already eliminated.".format(player.getLogString(), card.getDeterminerString(), target.getLogString()))
			result = "{} isn't in the game anymore!".format(target.username)

		elif self.isEffectiveBang(player, card.name):
			result = self.targetIsInRange(player, target)
			utils.logGameplay("Result for whether {} is in range of {} for a Bang: {}".format(target.username, player.username, result))
			if result:
				result = OK_MSG
			else:
				result = "{} is out of range for a Bang.".format(target.username)

		elif card.name == PANICO:
			utils.logGameplay("Result for whether {} is in range of {} for a Bang: {}".format(target.username, player.username, self.targetIsInRange(player, target, bang=False)))
			if self.targetIsInRange(player, target, bang=False):
				if len(target.cardsInHand + target.getCardsOnTable()) == 0:
					result = "{} has no cards to steal!".format(target.username)
				else:
					result = OK_MSG
			else:
				result = "{} is out of range for a Panico.".format(target.username)

		elif card.name == CAT_BALOU:
			result = OK_MSG if len(target.cardsInHand + target.getCardsOnTable()) > 0 else "{} has no cards to discard!".format(target.username)

		elif card.name == PRIGIONE:
			if target in self.getAllValidTargetsForCard(player, PRIGIONE):
				result = OK_MSG
			elif target.role == SHERIFF:
				result = "You can't jail the sheriff!"
			elif target.jailStatus == 1:
				result = "{} is already in jail!".format(target.username)

		else: # Any cards not listed should always default to OK.
			result = OK_MSG

		utils.logGameplay("Return message for {} playing {}{}: \"{}\".".format(player.username, card.getDeterminerString(), " against {}".format(target.username) if target.username else "", result))
		
		return result

	def targetIsInRange(self, player, target, bang=True):
		effectiveDistance = self.calculateEffectiveDistance(player, target)
		return effectiveDistance <= (player.getGunRange() if bang else 1)

	# Get the effective distance between 2 players after factoring in eliminated opponents, scopes, and mustangs.
	def calculateEffectiveDistance(self, player, target):
		targetIndex = self.getAlivePlayers().index(target)
		baseDistance = min(targetIndex, len(self.getAlivePlayers()) - targetIndex)
		result = baseDistance - player.getScopeDistance() + target.getMustangDistance()

		utils.logGameplay("Calculated an effective distance of {} from {} to {}.".format(result, player.username, target.username))
		return result

	def advanceDynamite(self):
		currentPlayer, nextPlayer = self.getAlivePlayers()[:2]
		utils.logGameplay("Advancing the dynamite from {} to {}.".format(currentPlayer.username, nextPlayer.username))

		self.dynamiteUsername = self.getAlivePlayers()[1].username
		dynamiteCard = self.getDynamiteCard()
		currentPlayer.getRidOfCard(dynamiteCard)
		nextPlayer.specialCards.append(dynamiteCard)

		return nextPlayer

	def isEffectiveBang(self, player, cardName):
		isBang = cardName == BANG or (player != None and player.character.name == CALAMITY_JANET and cardName == MANCATO)
		utils.logGameplay("Checking effective Bang: {} and {} -> {}".format(player, cardName, isBang))
		return isBang

	def makeCardDrawModalTuples(self, player):
		opponents = [p for p in self.playerOrder[1:]]
		emitTuples = []

		# For the player whose turn it currently is.
		if player == self.playerOrder[0]:

			# If the character isn't Jesse Jones/Kit Carlson/Pedro Ramirez, you can always just draw from the deck.
			if player.character.name not in [JESSE_JONES, KIT_CARLSON, PEDRO_RAMIREZ]:
				cardsDrawn = self.drawCardsForPlayerTurn(player)
				description = "You drew {}.".format(utils.convertCardsDrawnToString(cardsDrawn))
				self.drawingToStartTurn = False

				if player.character.name == BLACK_JACK:
					if len(cardsDrawn) == 3:
						description = description[:-1] + " because the {} is a {}.".format(cardsDrawn[1].getDisplayName(), cardsDrawn[1].suit)
					updateString = "{} drew {} cards. The second card was {}.".format(player.username, len(cardsDrawn), cardsDrawn[1].getDeterminerString())
				else:
					updateString = DREW_2_CARDS.format(player.username)

				emitTuples.append(self.createCardsDrawnTuple(player, description, cardsDrawn))
				emitTuples.extend(self.createUpdates(updateString))

			else:
				if player.character.name == JESSE_JONES:
					# Jesse Jones can only use her special ability if anyone has cards to draw from.
					playersToDrawFrom = self.getPlayersWithCardsInHand(player.username)
					if len(playersToDrawFrom) == 0:
						cardsDrawn = self.drawCardsForPlayerTurn(player)
						description = "You drew {} from the deck (nobody has cards to draw from).".format(utils.convertCardsDrawnToString(cardsDrawn))
						self.drawingToStartTurn = False

						emitTuples.append(self.createCardsDrawnTuple(player, description, cardsDrawn))
						emitTuples.extend(self.createUpdates(DREW_2_CARDS.format(player.username)))

					else:
						return [self.addQuestion(player, QUESTION_JESSE_JONES, [FROM_ANOTHER_PLAYER, FROM_THE_DECK])]

				elif player.character.name == KIT_CARLSON:
					cardsDrawn = self.drawCardsForPlayerTurn(player)
					self.specialAbilityCards[KIT_CARLSON] = list(cardsDrawn)
					kitTuple = utils.createKitCarlsonTuple(player, cardsDrawn)
					self.infoTupleDict[player.username] = kitTuple
					return [kitTuple]
				
				elif player.character.name == PEDRO_RAMIREZ:
					# Pedro Ramirez can only use his special ability if there are any cards in the discard pile.
					if len(self.discardPile) == 0:
						cardsDrawn = self.drawCardsForPlayerTurn(player)
						description = "You drew {} from the deck (the discard pile is empty right now).".format(utils.convertCardsDrawnToString(cardsDrawn))
						self.drawingToStartTurn = False
						
						emitTuples.append(self.createCardsDrawnTuple(player, description, cardsDrawn))
						emitTuples.extend(self.createUpdates(DREW_2_CARDS.format(player.username)))

					else:
						return [self.addQuestion(player, QUESTION_PEDRO_RAMIREZ, [FROM_DISCARD, FROM_THE_DECK])]

			emitTuples.append(utils.createCardCarouselTuple(player, True))
			return emitTuples

		# For players who aren't currently on their turn. It's only used once so there's no utils function for this.
		else:
			return [(SHOW_INFO_MODAL, {'html': render_template('/modals/other_player_turn.html', turn=self.getCurrentPlayerName())}, player)]

	def processQuestionResponse(self, username, question, answer):
		player = self.players[username]
		currentPlayer = self.playerOrder[0]
		utils.logGameplay("Received modal response \"{}\" from {}{}.".format(answer, player.getLogString(), "" if self.currentCard == None else " (card being played: {})".format(self.currentCard.name)))
		emitTuples = []

		if username not in self.unansweredQuestions:
			utils.logError("{} shouldn't be answering a question.".format(username))
			return []
		
		if question != self.unansweredQuestions[username][0]:
			utils.logError("Received a response from {} for \"{}\", but their saved question is \"{}\"".format(username, question, self.unansweredQuestions[username]))
			return [] 

		# This player has answered his/her question, so s/he is no longer holding up the game.
		del self.unansweredQuestions[username]
		self.playersWaitingFor.remove(player.username)

		# If the player said "Never mind", just cancel the current card.
		if answer == NEVER_MIND:
			self.currentCard = None
			return []

		# Handle the responses for characters who have special start-of-turn draws. 
		if self.drawingToStartTurn:
			if player.character.name in [JESSE_JONES, PEDRO_RAMIREZ]:
				emitTuples = self.processAbilityQuestionResponse(username, question, answer)
			else:
				utils.logError("{} shouldn't be answering a modal question while drawing for cards to start the turn.".format(player.getLogString()))

		else:
			# # Handle a player answering which opponent to target for the current card.
			# if answer in self.players:
			# 	target = self.players[answer]

			# 	if player != currentPlayer:
			# 		utils.logError("{} answered a question targeting someone ({}), but the current player is {}.".format(player.getLogString(), answer, currentPlayer.getLogString()))
			# 		return []
			# 	if player.username == target.username:
			# 		utils.logError("{} is targeting himself/herself for {}.".format(player.getLogString(), self.currentCard.name))
			# 		return []

			# 	response = self.validateTargetChoice(player, target)
			# 	if response == OK_MSG:
			# 		return self.playCurrentCard(player, targetName=target.username)
			# 	else:
			# 		return [self.createInfoTuple(response, player, header="Invalid Target")] # Don't re-open the question modal so that the player can play another card if s/he wants to.

			# Handle Lucky Duke choosing one of 2 cards for "draw!".
			if player.character.name == LUCKY_DUKE and question == QUESTION_LUCKY_DUKE.format(self.currentCard.getDisplayName()):
				emitTuples = self.processAbilityQuestionResponse(username, question, answer)

			# Handle responses for players in a Duello.
			elif any([utils.getReverseFormat(formatString, question) != None for formatString in [QUESTION_DUELLO_REACTION, QUESTION_DUELLO_BANG_REACTION]]):
				emitTuples = self.processDuelloResponse(player, answer)

			# Handle responses for players playing a Cat Balou or Panico.
			elif any([utils.getReverseFormat(formatString, question) != None for formatString in [QUESTION_PANICO_CARDS, QUESTION_CAT_BALOU_CARDS, QUESTION_CARD_ON_TABLE]]):
				if utils.getReverseFormat(QUESTION_PANICO_CARDS, question) != None:
					target = self.players[utils.getReverseFormat(QUESTION_PANICO_CARDS, question)[0]]
				elif utils.getReverseFormat(QUESTION_CAT_BALOU_CARDS, question) != None:
					target = self.players[utils.getReverseFormat(QUESTION_CAT_BALOU_CARDS, question)[0]]
				else:
					targetName, cardName = utils.getReverseFormat(QUESTION_CARD_ON_TABLE, question)
					target = self.players[targetName]
					hasCardOnTableChosen = True
				
				if answer == FROM_THEIR_HAND:
					selectedCard = selectedCard = target.panico()
				else:
					name, value, suit = utils.getCardNameValueSuitFromAnswer(answer)
					cardChosen = utils.getUniqueItem(lambda card: (name, suit, value) == (card.name, card.suit, card.value), target.getCardsOnTable())
					selectedCard = target.panico(cardChosen)

				return self.processPanicoCatBalou(player, target, self.currentCard.name, selectedCard=selectedCard, fromTheTable=(answer != FROM_THEIR_HAND))
				
			# Handle responses for how a player wants to react to Bang/Indians/Gatling.
			elif question in [q.format(currentPlayer.username) for q in [QUESTION_BANG_REACTION, QUESTION_INDIANS_REACTION, QUESTION_GATLING_REACTION, QUESTION_SLAB_BARILE_ONE, QUESTION_SLAB_BARILE_TWO]] \
					or utils.getReverseFormat(QUESTION_BARILE_MANCATO, question) != None:
				if answer == LOSE_A_LIFE:
					emitTuples = self.processPlayerTakingDamage(player)
				elif answer in [PLAY_A_MANCATO, PLAY_TWO_MANCATOS, PLAY_A_BANG]:
					requiredCardName = MANCATO if MANCATO in answer.lower() else BANG
					requiredCardsInHand = player.getCardTypeFromHand(requiredCardName)

					if answer == PLAY_TWO_MANCATOS:
						emitTuples = self.processSlabTheKillerAbility(player)

					else:
						self.playersWaitingFor.append(player.username)

						# If the player only has 1 required card, just play it automatically.
						if len(requiredCardsInHand) == 1:
							card = requiredCardsInHand[0]
							emitTuples.append((SLEEP, 0.5, None))
							emitTuples.extend(self.processBlurCardSelection(player.username, requiredCardsInHand[-1].uid))

						# Otherwise, blur the non-playable cards for the user and have him/her choose the playable one to use.
						else:
							emitTuples = utils.createCardBlurTuples(player, requiredCardName)

				else:
					utils.logError("Answer by {} for reacting to an attacking card doesn't match any expected option: {}.".format(username, answer))

			# Handle the case where a player wants to play a new blue card but already has 2 cards in play.
			elif question == QUESTION_IN_PLAY:
				answer = answer.replace("Replace the ", "")
				name, value, suit = utils.getCardNameValueSuitFromAnswer(answer)
				cardToDiscard = utils.getUniqueItem(lambda card: (name, suit, value) == (card.name, card.suit, card.value), player.cardsInPlay)
				emitTuples.extend(self.replaceInPlayCard(player, cardToDiscard))

			# Handle player deciding what to do when a gun is already in play.
			elif question == QUESTION_REPLACE_GUN:
				if utils.getReverseFormat(REPLACE_GUN, answer) != None: # Meaning to replace the current gun.
					inPlayGun = utils.getUniqueItem(lambda card: card.cardtype == GUN_CARD, player.cardsInPlay)
					emitTuples.extend(self.replaceInPlayCard(player, inPlayGun))
				else:
					self.currentCard = None

		return emitTuples

	def processPanicoCatBalou(self, player, target, cardName, selectedCard=None, fromTheTable=False):
		emitTuples = []

		if selectedCard != None:
			if selectedCard.name == DYNAMITE:
				self.dynamiteUsername = ""
				self.dynamiteStartTurn = self.currentTurn + 1
			elif selectedCard.name == PRIGIONE:
				target.jailStatus = 0

			utils.logGameplay("{} played a {} to make {} lose {}.".format(player.username, cardName, target.username, selectedCard.getDeterminerString()))
			if cardName == PANICO:
				player.addCardToHand(selectedCard)
				
				stolenCardString = selectedCard.getDisplayName() if not fromTheTable else "your {}".format(selectedCard.getDisplayName())
				emitTuples.append(self.createInfoTuple("{} played a Panico and stole {} from you!".format(player.username, selectedCard.getDeterminerString()), target, cards=[selectedCard]))
				
				emitTuples.append(self.createInfoTuple("You stole {} from {}!".format(selectedCard.getDeterminerString(), target.username), player, cards=[selectedCard]))
				
				stolenCardString = "a card" if not fromTheTable else "their {}".format(selectedCard.getDisplayName())
				emitTuples.extend(self.createUpdates("{} played a Panico on {} and stole {}.".format(player.username, target.username, stolenCardString)))
			else:
				self.discardPile.append(selectedCard)
				emitTuples.extend(self.getDiscardTuples(selectedCard))

				discardCardString = selectedCard.getDisplayName() if not fromTheTable else "your {}".format(selectedCard.getDisplayName())
				emitTuples.append(self.createInfoTuple("{} played a Cat Balou and made you discard {}!".format(player.username, discardCardString), target, cards=[selectedCard]))

				discardCardString = "a {}".format(selectedCard.getDisplayName()) if not fromTheTable else "{} {}".format("their" if selectedCard.name != DYNAMITE else "the", selectedCard.getDisplayName())
				emitTuples.append(self.createInfoTuple("You forced {} to discard {}!".format(target.username, discardCardString), player, cards=[selectedCard]))
				emitTuples.extend(self.createUpdates("{} played a Cat Balou on {}, who had to discard {}.".format(player.username, target.username, discardCardString)))
			
			self.currentCard = None
			emitTuples.append(utils.createCardCarouselTuple(player, True))
			emitTuples.append(utils.createCardsInPlayTuple(target))
			emitTuples.append(utils.createCardCarouselTuple(target, False))

			if target.character.name == SUZY_LAFAYETTE:
				emitTuples.extend(self.processSuzyLafayetteAbility(target))

		else:
			if len(target.cardsInHand) > 0 and len(target.getCardsOnTable()) == 0: # Have to steal from the hand.
				selectedCard = target.panico()
				emitTuples = self.processPanicoCatBalou(player, target, cardName, selectedCard=selectedCard, fromTheTable=False)
			elif len(target.getCardsOnTable()) == 1 and len(target.cardsInHand) == 0: # Have to steal the player's only card on the table.
				selectedCard = target.panico(target.getCardsOnTable()[0])
				emitTuples = self.processPanicoCatBalou(player, target, cardName, selectedCard=selectedCard, fromTheTable=True)
			elif len(target.getCardsOnTable()) >= 2 and len(target.cardsInHand) == 0: # Have to steal from what's on the table.
				options = [c.getQuestionString() for c in target.getCardsOnTable()]
				emitTuples = [self.addQuestion(player, QUESTION_CARD_ON_TABLE.format(target.username, utils.convertRawNameToDisplay(cardName)), options)]
			else:
				question = QUESTION_PANICO_CARDS if cardName == PANICO else QUESTION_CAT_BALOU_CARDS
				options = [FROM_THEIR_HAND] + [c.getQuestionString() for c in target.getCardsOnTable()]
				emitTuples = [self.addQuestion(player, question.format(target.username), options)]

		return emitTuples

	def processDuelloResponse(self, player, answer=None, card=None):
		emitTuples = []

		attacker = [p for p in self.duelPair if p != player][0]

		if card != None: # A card will be passed in if we've already gotten a response about which card to play (or if there's only 1 option).
			self.discardCard(player, card)
			effectiveDisplayName = "Bang" if (player.character.name != CALAMITY_JANET or card.name != MANCATO) else MANCATO_AS_BANG
			emitTuples = self.createUpdates("{} responded by playing a {}.".format(player.username, effectiveDisplayName))
			emitTuples.extend(self.getDiscardTuples(card))
			emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

			emitTuples.append(utils.createWaitingModalTuple(player, WAITING_DUELLO_REACTION.format(attacker.username)))

			if len(attacker.getCardTypeFromHand(BANG)) > 0:
				emitTuples.append(self.addQuestion(attacker, QUESTION_DUELLO_BANG_REACTION.format(player.username), [PLAY_A_BANG, LOSE_A_LIFE]))
			
			# Automatically take the hit if the next player doesn't have any Bangs to respond with.
			else:
				emitTuples.append((SLEEP, AUTOMATIC_SLEEP_DURATION, None))
				
				emitTuples.extend(self.processPlayerTakingDamage(attacker, attacker=player))

				for dueller in self.duelPair:
					if dueller.isAlive() and dueller.character.name == SUZY_LAFAYETTE:
						emitTuples.extend(self.processSuzyLafayetteAbility(dueller)) # Now that the duel is over, Suzy Lafayette can use her ability.

				self.duelPair = list()

		else:
			if answer == LOSE_A_LIFE:
				emitTuples.extend(self.processPlayerTakingDamage(player, attacker=attacker))

				for dueller in self.duelPair:
					if dueller.isAlive() and dueller.character.name == SUZY_LAFAYETTE:
						emitTuples.extend(self.processSuzyLafayetteAbility(dueller)) # Now that the duel is over, Suzy Lafayette can use her ability.

				self.duelPair = list()

			elif answer == PLAY_A_BANG:
				bangsInHand = player.getCardTypeFromHand(BANG)
				if len(bangsInHand) == 1: # If the player only has 1 Bang, automatically play it.
					emitTuples.extend(self.processDuelloResponse(player, card=bangsInHand[0]))
				else:
					self.playersWaitingFor.append(player.username)
					emitTuples = utils.createCardBlurTuples(player, BANG)

			else:
				utils.logError("Answer by {} for reacting to a Duello doesn't match any expected option: {}.".format(player.username, answer))

		return emitTuples

	# Function to process the effects of a player taking damage once it's definitive that s/he will do so.
	def processPlayerTakingDamage(self, player, damage=1, attacker=None):
		emitTuples = []
		opponents = self.getAliveOpponents(player.username)
		stayedAliveWithBirras = 0

		if attacker != None and player.username == attacker.username:
			utils.logError("{} shouldn't be able to damage himself/herself.".format(player.getLogString()))
			return []

		utils.logGameplay("Processing {} taking {} damage{}.".format(player.getLogString(), damage, "" if attacker == None else " from {}".format(attacker.username)))
		
		for _ in range(damage):
			player.loseOneLife()

		lostLivesString = "a life" if damage == 1 else "{} lives".format(damage)

		if self.isEffectiveBang(attacker, self.currentCard.name): cardEffectString = "hit by {}'s Bang".format(self.getCurrentPlayerName())
		elif self.currentCard.name == INDIANS: cardEffectString = "hit by {}'s Indians".format(self.getCurrentPlayerName())
		elif self.currentCard.name == GATLING: cardEffectString = "hit by {}'s Gatling".format(self.getCurrentPlayerName())
		elif self.currentCard.name == DUELLO: cardEffectString = "defeated in the Duello"
		elif self.currentCard.name == DYNAMITE: cardEffectString = "hit by the exploding dynamite"
		else:
			utils.logError("{} shouldn't be able to lose a life to {} being played by {}.".format(player.getLogString(), self.currentCard.name, attacker.username if attacker != None else 'None'))
			return []

		# Meaning the player is taking damage from dynamite.
		if damage == 3:
			self.discardCard(player, self.getDynamiteCard()) # The dynamite always has to get discarded when it explodes.
			emitTuples.extend(self.getDiscardTuples(self.getDynamiteCard()))

		# Meaning the player is taking damage from an attacking card.
		else:
			attacker = attacker if attacker != None else self.playerOrder[0]

		# Handle the player potentially being eliminated.
		if not player.isAlive():
			requiredBirras = abs(player.lives) + 1
			birrasInHand = player.getCardTypeFromHand(BIRRA)
			if len(birrasInHand) < requiredBirras or len(self.getAlivePlayers()) == 1: # Without enough Birras, or if it's 1-v-1, the player is eliminated.
				player.lives = 0
				aliveCount = len(self.getAlivePlayers())
				isGameOverResult = self.checkGameOver()
				
				updateText = "{} was {} and has been eliminated.".format(player.username, cardEffectString)
				emitTuples.extend(self.createUpdates(updateText))
				
				if isGameOverResult != '':
					emitTuples.extend([t for p in self.playerOrder for t in self.getPlayerReloadingTuples(p.username, gameOver=True)])
					emitTuples.extend([utils.createGameOverTuple(p, isGameOverResult) for p in self.playerOrder])
					emitTuples.extend(self.createUpdates(isGameOverResult))

				else: # Emit message to everybody that the player died.
					deadPlayerText = "You were {}! You've been eliminated! Better luck next time.".format(cardEffectString)
					otherPlayersText = "{} was {} and has been eliminated!".format(player.username, cardEffectString)

					emitTuples.append(self.createInfoTuple(deadPlayerText, player, header="Game Over!"))
					emitTuples.extend([self.createInfoTuple(otherPlayersText, p) for p in self.playerOrder if p != player])

					if player == self.playerOrder[0]:
						emitTuples.append((END_YOUR_TURN, dict(), player))

					# Discard Dynamite first if applicable.
					if self.getDynamiteCard() in player.specialCards:
						self.discardCard(player, self.getDynamiteCard())

					# If Vulture Sam is one of the game's alive players, use his special ability.
					vultureSam = utils.getUniqueItem(lambda p: p.character.name == VULTURE_SAM, self.getAlivePlayers())
					vultureSamSheriffException = vultureSam != None and vultureSam == attacker and vultureSam.role == SHERIFF and player.role == VICE
					if not vultureSamSheriffException and vultureSam != None and vultureSam != player:
						vultureSam.cardsInHand.extend(player.cardsInHand + player.getCardsOnTable())
						
						emitTuples.append((SLEEP, 0.5, None))
						emitTuples.append(self.createInfoTuple("You got all of {}'s cards because they were eliminated!".format(player.username), vultureSam))
						emitTuples.extend(self.createUpdates("{} got all of {}'s cards using Vulture Sam's ability.".format(vultureSam.username, player.username)))
						emitTuples.append(utils.createCardCarouselTuple(vultureSam, vultureSam == self.playerOrder[0]))
					
					# Otherwise, just normally discard all of the player's cards.
					else:
						self.discardPile.extend(player.cardsInHand + player.getCardsOnTable())

					player.cardsInHand = []
					player.cardsInPlay = []
					player.specialCards = []
					player.jailStatus = 0

					emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
					emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
					emitTuples.append(utils.createCardsInPlayTuple(player))

					# Handle the cases where eliminating a player has a penalty or reward.
					duelloException = self.currentCard.name == DUELLO and player == self.playerOrder[0] # If the instigator is an Outlaw and loses a Duel, the other player shouldn't draw anything.
					sheriffEliminatedVice = attacker != None and attacker.role == SHERIFF and player.role == VICE
					attackerEliminatedOutlaw = attacker != None and player.role == OUTLAW
					if not duelloException and (sheriffEliminatedVice or attackerEliminatedOutlaw):
						if sheriffEliminatedVice:
							for c in attacker.cardsInPlay + attacker.cardsInHand:
								self.discardCard(attacker, c)

							infoText = "You eliminated one of your Vices, so you had to discard all your cards!"
							updateText = "{} discarded all their cards for eliminating a Vice as the Sheriff.".format(attacker.username)

						else:
							self.drawCardsForPlayer(attacker, 3)

							infoText = "You drew 3 cards for eliminating an Outlaw!"
							updateText = "{} drew 3 cards for eliminating an Outlaw.".format(attacker.username)

						emitTuples.append(self.createInfoTuple(infoText, attacker))
						emitTuples.extend(self.createUpdates(updateText))
						emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
						emitTuples.append(utils.createCardCarouselTuple(attacker, attacker == self.playerOrder[0]))

			else: # With enough Birras, the player stays in the game. Play as many as necessary to bring the player back to 1 life.
				player.lives = 1
				stayedAliveWithBirras = requiredBirras

				for birra in birrasInHand[:requiredBirras]:
					self.discardCard(player, birra)
				
				emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
				emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

				if player.character.name == SUZY_LAFAYETTE:
					emitTuples.extend(self.processSuzyLafayetteAbility(player))

				# Update the player's info modal and update everyone else's action screen.
				birraString = "a Birra" if requiredBirras == 1 else "{} Birras".format(requiredBirras)

				emitTuples.append(self.createInfoTuple("You were {} and almost died, but were saved by {}!".format(cardEffectString, birraString), player))
				emitTuples.extend(self.createUpdates("{} was {} but stayed alive by playing {}.".format(player.username, cardEffectString, birraString)))

				if attacker != None:
					emitTuples.append(self.createInfoTuple("{} took the hit but stayed alive by playing {}.".format(player.username, birraString), attacker))

				utils.logGameplay("{} played {}".format(player.username, birraString))

		# Otherwise, just take the player's lives and move on.
		else:
			text = "You were {}, so you've lost {}{} You're down to {} now.".format(cardEffectString, lostLivesString, "!" if "lives" in lostLivesString else ".", player.lives)
			emitTuples.append(self.createInfoTuple(text, player))

			if attacker != None:
				emitTuples.append(self.createInfoTuple("{} took the hit and is down to {} now.".format(player.username, "{} {}".format(player.lives, "lives" if player.lives > 1 else "life")), attacker))

			updateText = "{} was {}{}.".format(player.username, cardEffectString, "" if damage == 1 else " and lost {}".format(lostLivesString))
			emitTuples.extend(self.createUpdates(updateText))


		# If the player is still alive and has a character ability triggered by taking damage, process that here.
		if player.isAlive():
			if player.character.name == BART_CASSIDY: # Bart Cassidy draws a new card for every life point he's lost.
				self.drawCardsForPlayer(player, damage)

				cardString = player.cardsInHand[-1].getDeterminerString() if damage == 1 else "{} cards".format(damage)
				utils.logGameplay("{} drawing {} cards(s) because they {}".format(player.getLogString(), cardString, lostLivesString))

				emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
				emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
				emitTuples.append(self.createInfoTuple("You drew {} because you lost {}!".format(cardString, lostLivesString), player))
				emitTuples.extend(self.createUpdates("{} drew {} using Bart Cassidy's ability.".format(player.username, "a card" if damage == 1 else "{} cards".format(damage))))

			elif player.character.name == EL_GRINGO and self.playerOrder[0] != player and attacker != None: # El Gringo draws a card from the player's hand anytime a player deals him damage.
				if len(attacker.cardsInHand) > 0:
					stolenCard = attacker.panico()

					utils.logGameplay("{} stealing {} from the hand of {} for dealing him damage.".format(player.getLogString(), stolenCard, attacker.getLogString()))
					
					player.addCardToHand(stolenCard)
					emitTuples.append(self.createInfoTuple("You stole {} from {}'s hand because they made you lose a life!".format(stolenCard.getDeterminerString(), attacker.username), player))
					emitTuples.append(self.createInfoTuple("{} stole {} from your hand because you made them lose a life!".format(player.username, stolenCard.getDeterminerString()), attacker))
					emitTuples.extend(self.createUpdates("{} stole a card from {}'s hand using El Gringo's ability.".format(player.username, attacker.username)))
					emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
					emitTuples.append(utils.createCardCarouselTuple(attacker, attacker == self.playerOrder[0]))

					if attacker.character.name == SUZY_LAFAYETTE:
						emitTuples.extend(self.processSuzyLafayetteAbility(attacker))

				else:
					emitTuples.append(self.createInfoTuple("{} has no cards, so you couldn't use El Gringo's ability to steal anything.".format(attacker.username), player))

		if not self.gameOver:
			emitTuples.extend(utils.createHealthAnimationTuples(player.username, -damage, self.playerOrder))
			if stayedAliveWithBirras > 0:
				emitTuples.append((SLEEP, 0.5, None))
				emitTuples.extend(utils.createHealthAnimationTuples(player.username, stayedAliveWithBirras, self.playerOrder))

		# Only reset the current card once its effects are finished, i.e. once every player has finished reacting to everything.
		if self.currentCardCanBeReset():
			self.currentCard = None
		
		utils.logGameplay("Processed {} losing {}. Will return the following emitTuples: {}.".format(player.username, lostLivesString, [(t[0], t[2] if len(t)==3 else 'everybody') for t in emitTuples]))
		return emitTuples

	def checkGameOver(self):
		alivePlayers = self.getAlivePlayers()
		sheriffIsAlive = self.players[self.sheriffUsername].isAlive()
		renegadeIsAlive = any([p.role == RENEGADE for p in alivePlayers])
		numAliveOutlaws = len([p for p in alivePlayers if p.role == OUTLAW])

		if not sheriffIsAlive:
			self.gameOver = True
			if renegadeIsAlive and len(alivePlayers) == 1: return "The Renegade has won the game!"
			else: return "The Outlaws have won the game!"
		else:
			if not renegadeIsAlive and numAliveOutlaws == 0:
				self.gameOver = True
				return "The Sheriff and his Vices have won the game!"
			else:
				return '' # Indicates the game is not over.

	def currentCardCanBeReset(self):
		canBeReset = len(self.unansweredQuestions) == 0 and len(self.playersWaitingFor) == 0

		if not canBeReset:
			utils.logGameplay("Card {} can't be reset yet. {} {}".format(self.currentCard.uid, self.unansweredQuestions, self.playersWaitingFor))

		# If the card can be reset here, i.e. the card is done being played, save the current game state.
		if canBeReset:
			utils.logGameplay("Card {} CAN be reset.".format(self.currentCard))
			utils.saveGame(self)

		return canBeReset

	# Function to handle responses for the character abilities that require a question.
	def processAbilityQuestionResponse(self, username, question, answer):
		emitTuples = []
		player = self.players[username]

		utils.logGameplay("Beginning to process ability question response for {}.".format(player.getLogString()))

		if player.character.name == JESSE_JONES: # Answering the question of whether to draw from a player or the deck.
			if answer == FROM_ANOTHER_PLAYER:
				playersToDrawFrom = self.getPlayersWithCardsInHand(username)
				if len(playersToDrawFrom) > 1:
					emitTuples.extend(utils.createClickOnPlayersTuples(player, "Click on the player whose hand you want to draw from.", JESSE_JONES_CLICK))
				
				# There's only 1 player Jesse Jones can draw from, so automatically draw from that player's hand.
				else:
					emitTuples.extend(self.processJesseJonesDrawingFromPlayer(username, playersToDrawFrom[0].username, automatic=True))

			elif answer == FROM_THE_DECK:
				cardsDrawn = self.drawCardsForPlayerTurn(player)
				description = "You drew {} from the deck.".format(utils.convertCardsDrawnToString(cardsDrawn))
				self.drawingToStartTurn = False
				
				emitTuples.append(self.createCardsDrawnTuple(player, description, cardsDrawn))
				emitTuples.append(utils.createCardCarouselTuple(player, True))
				emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
				emitTuples.extend(self.createUpdates(DREW_2_CARDS.format(username)))

		elif player.character.name == PEDRO_RAMIREZ:
			if answer in [FROM_DISCARD, FROM_THE_DECK]:
				cardsDrawn = self.drawCardsForPlayerTurn(player, extraInfo=('' if answer == FROM_THE_DECK else FROM_DISCARD))
				if answer == FROM_DISCARD:
					description = "You drew {} from the discard pile and {} from the deck.".format(cardsDrawn[-2].getDeterminerString(), cardsDrawn[-1].getDeterminerString())
					emitTuples.extend(self.createUpdates("{} drew {} from the discard pile and 1 card from the deck.".format(username, cardsDrawn[-2].getDeterminerString())))
				else:
					description = "You drew {} from the deck.".format(utils.convertCardsDrawnToString(cardsDrawn))
					emitTuples.extend(self.createUpdates(DREW_2_CARDS.format(username)))

				self.drawingToStartTurn = False

				emitTuples.append(self.createCardsDrawnTuple(player, description, player.cardsInHand[-2:]))
				emitTuples.append(utils.createCardCarouselTuple(player, True))
				emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))

			else:
				utils.logError("Option of \"{}\" was selected by {}, which doesn't match any expected options.".format(answer, player.getLogString()))
				self.drawingToStartTurn = False
				return []

		elif player.character.name == LUCKY_DUKE:
			self.playersWaitingFor.remove(player.username)

			cardName, value, suit = utils.getCardNameValueSuitFromAnswer(answer)
			
			# Both cards get discarded, but we force the one that Lucky Duke picked to get discarded second so it's on top.
			if (cardName, value, suit) in [(c.name, c.value, c.suit) for c in self.drawPile[-2:]]:
				if (cardName, value, suit) == (self.drawPile[-1].name, self.drawPile[-1].value, self.drawPile[-1].suit):
					cardDrawn = self.drawPile[-1]
					self.discardPile.append(self.drawPile.pop(-2))
				else:
					cardDrawn = self.drawPile[-2]
					self.discardPile.append(self.drawPile.pop(-1))

				if self.currentCard.name == DYNAMITE:
					emitTuples.extend(self.processDynamiteDraw(player))

					if player.isAlive():
						if player.jailStatus == 1:
							self.currentCard = player.getPrigione()
							self.drawingToStartTurn = False
							emitTuples.append((SLEEP, 0.5, None))
							emitTuples.append(self.createLuckyDukeTuple(player))
						else:
							emitTuples.extend(self.getTuplesForNewTurn())

				elif self.currentCard.name == PRIGIONE:
					emitTuples.extend(self.processPrigioneDraw(player))
					if player.jailStatus == 0: # Meaning the player drew and got out of jail.
						emitTuples.extend(self.getTuplesForNewTurn())

				elif self.currentCard.name in [BANG, GATLING]:
					emitTuples.extend(self.processBarileDraw(player))

				else:
					utils.logError("Lucky Duke ({}) shouldn't be doing \"draw!\" when the current card is {}.".format(player.username, self.currentCard.name))

			else:
				utils.logError("Lucky Duke picked a card ({}, {}) for \"draw!\" that shouldn't be an option.".format(cardName, suit))

		utils.logGameplay("processAbilityQuestionResponse() for ({}, {}, {}) tuples: {}".format(username, question, answer, emitTuples))
		return emitTuples

	def processKitCarlsonCardSelection(self, username, uid):
		emitTuples = []
		player = self.players[username]

		discardedCard = self.getCardByUid(uid)
		self.drawPile.append(discardedCard)

		for c in self.specialAbilityCards[KIT_CARLSON]:
			if c != discardedCard:
				player.addCardToHand(c)

		emitTuples.append(utils.createCardCarouselTuple(player, True))
		emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
		emitTuples.extend(self.createUpdates(DREW_2_CARDS.format(username)))

		self.specialAbilityCards[KIT_CARLSON] = None
		self.drawingToStartTurn = False
		
		return emitTuples

	# Function to process a player's choice when s/he had to pick a card from his/her hand in response to the current card.
	def processBlurCardSelection(self, username, uid):
		player = self.players[username]
		currentPlayer = self.playerOrder[0]
		selectedCard = self.getCardByUid(uid)
		emitTuples = []

		if selectedCard not in player.cardsInHand:
			utils.logError("{} played {} ({}) but doesn't have that card in his/her hand.".format(player.getLogString(), selectedCard.getDeterminerString(), uid))
			return []

		if self.currentCard.name != DUELLO and username == self.getCurrentPlayerName():
			utils.logError("{} played a blurred card in a non-duel even though it's currently his/her turn.".format(username))
			return []

		if selectedCard.name not in [BANG, MANCATO]:
			utils.logError("{} responded to the current card ({}) by playing {}.".format(player.getLogString(), self.currentCard.name, selectedCard.name))
			return []

		if player.username not in self.playersWaitingFor:
			utils.logError("{} selected a blurred card but isn't in the set of players being waited for ({})".format(player.getLogString(), self.playersWaitingFor))
			return []

		self.playersWaitingFor.remove(player.username)

		if self.currentCard.name == DUELLO:
			emitTuples = self.processDuelloResponse(player, card=selectedCard)

		elif self.currentCard.name in [BANG, GATLING] or (currentPlayer.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO):
			self.discardCard(player, selectedCard)

			if player.character.name == SUZY_LAFAYETTE:
				emitTuples.extend(self.processSuzyLafayetteAbility(player))
			
			effectiveName = utils.convertRawNameToDisplay(GATLING if self.currentCard.name == GATLING else BANG)
			if (currentPlayer.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO):
				effectiveName = MANCATO_AS_BANG
			effectiveReactionDisplayName = "Mancato" if (player.character.name != CALAMITY_JANET or selectedCard.name != BANG) else BANG_AS_MANCATO

			if self.specialAbilityCards[SLAB_THE_KILLER] == None:
				emitTuples.append(self.createInfoTuple("{} played a {} to avoid your {}!".format(player.username, effectiveReactionDisplayName, effectiveName), currentPlayer))
				emitTuples.extend(self.createUpdates("{} played a {} and avoided {}'s {}.".format(player.username, effectiveReactionDisplayName, currentPlayer.username, effectiveName)))
				emitTuples.append(utils.createCardCarouselTuple(player, False))
				emitTuples.extend(self.getDiscardTuples(selectedCard))
			
			# Handle a player discarding 1 of multiple Mancatos in response to Slab the Killer here.
			else:
				emitTuples.append(utils.createCardCarouselTuple(player, False))
				emitTuples.extend(self.getDiscardTuples(selectedCard))

				self.specialAbilityCards[SLAB_THE_KILLER].append(selectedCard)

				# Has only discarded 1 so far.
				if len(self.specialAbilityCards[SLAB_THE_KILLER]) == 1:
					self.playersWaitingFor.append(player.username)
					emitTuples.extend(utils.createCardBlurTuples(player, MANCATO, msg=CLICK_ON_CARD.format("second Mancato")))
				
				# Has discarded both, so the Bang is fully avoided.
				else:
					if all([c.name == MANCATO for c in self.specialAbilityCards[SLAB_THE_KILLER]]):
						effectiveReactionDisplayName = "2 Mancatos"
					elif all([c.name == BANG for c in self.specialAbilityCards[SLAB_THE_KILLER]]):
						effectiveReactionDisplayName = "2 Bangs (as Mancatos)"
					else:
						effectiveReactionDisplayName = "a Mancato and a Bang (as a Mancato)"

					emitTuples.append(self.createInfoTuple("{} played {} to avoid your Bang!".format(player.username, effectiveReactionDisplayName), currentPlayer))
					emitTuples.extend(self.createUpdates("{} played {} and avoided {}'s Bang.".format(player.username, effectiveReactionDisplayName, currentPlayer.username)))

					self.specialAbilityCards[SLAB_THE_KILLER] = None

			if self.currentCardCanBeReset() and self.specialAbilityCards[SLAB_THE_KILLER] == None:
				self.currentCard = None

		elif self.currentCard.name == INDIANS:
			self.discardCard(player, selectedCard)

			if player.character.name == SUZY_LAFAYETTE:
				emitTuples.extend(self.processSuzyLafayetteAbility(player))

			effectiveReactionDisplayName = "Bang" if (player.character.name != CALAMITY_JANET or selectedCard.name != MANCATO) else MANCATO_AS_BANG
			
			emitTuples.append(self.createInfoTuple("{} played a {} to avoid your Indians!".format(player.username, effectiveReactionDisplayName), currentPlayer))
			emitTuples.extend(self.createUpdates("{} played a {} and avoided {}'s Indians.".format(player.username, effectiveReactionDisplayName, currentPlayer.username)))
			emitTuples.append(utils.createCardCarouselTuple(player, False))
			emitTuples.extend(self.getDiscardTuples(selectedCard))

			if self.currentCardCanBeReset():
				self.currentCard = None

		return emitTuples

	def processEmporioCardSelection(self, username, uid):
		utils.logGameplay("Received request from {} to draw UID {} for Emporio.".format(username, uid))
		player = self.players[username]
		card = self.getCardByUid(uid)
		emitTuples = []

		if card not in self.emporioOptions:
			utils.logError("{} was selected as {}'s choice for Emporio, but the options are {}".format(uid, username, [c.uid for c in self.emporioOptions]))
			return []

		if player.username not in self.playersWaitingFor:
			utils.logError("{} chose a card for Emporio but isn't in the set of players waiting for ({})".format(player.getLogString(), self.playersWaitingFor))
			return []

		self.playersWaitingFor.remove(player.username)

		self.emporioOptions.remove(card)
		player.addCardToHand(card)

		emitTuples = self.createUpdates(PICKED_UP_FROM_EMPORIO.format(username, card.getDeterminerString()))
		emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

		nextPlayer = self.getAlivePlayers()[self.getAlivePlayers().index(player) + 1] # Should never be possible to get an index error here.
		
		if len(self.emporioOptions) == 1:
			card = self.emporioOptions.pop()
			nextPlayer.addCardToHand(card)
			emitTuples.append(utils.createCardCarouselTuple(nextPlayer, nextPlayer == self.playerOrder[0]))
			emitTuples.extend(self.createUpdates(PICKED_UP_FROM_EMPORIO.format(nextPlayer.username, card.getDeterminerString())))
			emitTuples.append(self.createInfoTuple("You picked up the last Emporio card:", nextPlayer, cards=[card]))
			emitTuples.extend([self.createInfoTuple("Everyone is done picking an Emporio card.", p) for p in self.playerOrder if p != nextPlayer])

			self.currentCard = None
		
		elif len({card.name for card in self.emporioOptions}) == 1: # Every remaining card is the same, so just distribute them automatically.
			automaticPlayers = self.getAlivePlayers()[(self.getAlivePlayers().index(player) + 1):]
			emitTuples.extend([self.createInfoTuple("Everyone is done picking an Emporio card.", p) for p in self.playerOrder if p not in automaticPlayers])
			emitTuples.extend(self.processEmporioAutomatic(nextPlayer))
		
		else:
			self.playersWaitingFor.append(nextPlayer.username)
			
			emporioTuples = utils.createEmporioTuples(self.playerOrder, self.emporioOptions, nextPlayer)
			for t in emporioTuples:
				self.infoTupleDict[t[2].username] = t
			emitTuples.extend(emporioTuples)

		return emitTuples

	def processEmporioAutomatic(self, nextPlayer):
		emitTuples = []
		playerIndex = self.getAlivePlayers().index(nextPlayer)

		while self.emporioOptions:
			card = self.emporioOptions.pop()
			nextPlayer.addCardToHand(card)

			emitTuples.append(utils.createCardCarouselTuple(nextPlayer, nextPlayer == self.playerOrder[0]))
			emitTuples.extend(self.createUpdates(PICKED_UP_FROM_EMPORIO.format(nextPlayer.username, card.getDeterminerString())))
			emitTuples.append(self.createInfoTuple("You automatically picked up {} from Emporio since all the cards left were the same.".format(card.getDeterminerString()), nextPlayer, cards=[card]))
			
			if self.emporioOptions:
				playerIndex += 1
				nextPlayer = self.getAlivePlayers()[playerIndex]

		self.currentCard = None

		return emitTuples

	def resetCardClickFunctions(self, username):
		player = self.players[username]
		return ((RESET_CARD_CLICK_FUNCTIONS, { 'isCurrent': player == self.playerOrder[0] }, player))

	def replaceInPlayCard(self, player, cardToReplace):
		emitTuples = []

		cardIndex = player.cardsInPlay.index(cardToReplace)
		self.discardCard(player, cardToReplace)
		player.getRidOfCard(self.currentCard)
		player.cardsInPlay.append(self.currentCard)

		if player.character.name == SUZY_LAFAYETTE:
			emitTuples.extend(self.processSuzyLafayetteAbility(player))

		if cardIndex == 0 and len(player.cardsInPlay) == 2: # If need be, flip the order of the player's in-play cards to keep them in the same position.
			player.cardsInPlay = player.cardsInPlay[::-1]
		
		emitTuples.append(utils.createCardCarouselTuple(player, True))
		emitTuples.append(utils.createCardsInPlayTuple(player))
		emitTuples.extend(self.getDiscardTuples(cardToReplace))
		emitTuples.extend(self.createUpdates("{} discarded {} and put {} in play.".format(player.username, cardToReplace.getDeterminerString(), self.currentCard.getDeterminerString())))

		self.currentCard = None

		return emitTuples

	def getPlayersWithCardsInHand(self, usernameToExclude=''):
		# If usernameToExclude has the default empty value, this will just check everybody.
		players = [p for p in self.playerOrder if p.username != usernameToExclude and len(p.cardsInHand) > 0]
		utils.logGameplay("Players with cards in hand{}: {}".format(" (excluding {})".format(usernameToExclude) if usernameToExclude else "", [p.username for p in players]))
		return players

	def getQuestionModalWithOpponents(self, player, question, opponents=None):
		if opponents == None:
			opponents = self.getAliveOpponents(player.username)
		return self.addQuestion(player, question, [p.username for p in opponents] + [NEVER_MIND])

	def getAlivePlayers(self):
		players = [p for p in self.playerOrder if p.isAlive()]
		utils.logGameplay("Alive players: {}".format([p.username for p in players]))
		return players

	def getAliveOpponents(self, username):
		opponents = [p for p in self.getAlivePlayers() if p.username != username]
		utils.logGameplay("Alive opponents of {}: {}".format(username, [p.username for p in opponents]))
		return opponents

	def processSpecialCardDraw(self, player):
		emitTuples = []

		if self.getDynamiteCard() in player.specialCards and self.dynamiteStartTurn <= self.currentTurn:
			self.currentCard = self.getDynamiteCard()

			if player.character.name != LUCKY_DUKE:
				emitTuples.extend(self.processDynamiteDraw(player))
			else:
				self.drawingToStartTurn = False
				return [self.createLuckyDukeTuple(player)]

		if player.isAlive() and player.jailStatus == 1:
			self.currentCard = player.getPrigione()

			if player.character.name != LUCKY_DUKE:
				emitTuples.extend(self.processPrigioneDraw(player))
			else:
				self.drawingToStartTurn = False
				return [self.createLuckyDukeTuple(player)]

		return emitTuples

	def processDynamiteDraw(self, player):
		drawnCard = self.drawAndDiscardOneCard()
		emitTuples = self.getDiscardTuples(self.getTopDiscardCard())

		if drawnCard.suit == SPADE and '2' <= drawnCard.value <= '9': # Can't compare ints b/c of face-card values.
			utils.logGameplay("The dynamite exploded on {}.".format(player.getLogString()))
			self.dynamiteUsername = ""
			return self.processPlayerTakingDamage(player, 3)
		else:
			utils.logGameplay("The dynamite didn't explode on {}.".format(player.getLogString()))
			nextPlayer = self.advanceDynamite()
			emitTuples = [self.createInfoTuple("Phew! The dynamite didn't explode on you!", player)]
			emitTuples.append(self.createInfoTuple("The dynamite didn't explode on {}, so you'll have it next turn!".format(player.username), nextPlayer))
			emitTuples.extend(self.createUpdates("The dynamite didn't explode on {}, so now {} has it.".format(player.username, nextPlayer.username)))

		self.currentCard = None
		self.drawingToStartTurn = True

		return emitTuples

	def processPrigioneDraw(self, player):
		drawnCard = self.drawAndDiscardOneCard()
		self.discardCard(player, player.getPrigione())
		emitTuples = self.getDiscardTuples(self.getTopDiscardCard())

		if drawnCard.suit == HEART:
			utils.logGameplay("{} drew a heart for Prigione, so s/he gets out of jail and will play this turn.".format(player.getLogString()))
			
			self.drawingToStartTurn = True
			player.jailStatus = 0
			emitTuples = [self.createInfoTuple("You drew a heart, so you got out of jail!", player)]
			emitTuples.extend(self.createUpdates("{} drew a heart, so they get to play this turn.".format(player.username)))
		
		else:
			utils.logGameplay("{} didn't draw a heart for Prigione, so s/he stays in jail and will not play this turn.".format(player.getLogString()))
			
			emitTuples = [self.createInfoTuple("You drew a {}, so you're stuck in jail for this turn!".format(drawnCard.suit), player)]
			emitTuples.extend(self.createUpdates("{} drew a {}, so they're stuck in jail for this turn.".format(player.username, drawnCard.suit)))
			emitTuples.append((END_YOUR_TURN, dict(), player))

		self.currentCard = None

		return emitTuples

	# Function to process "draw!" for Barile when a player is shot at.
	def processBarileDraw(self, player):
		emitTuples = []

		drawnCard = self.drawAndDiscardOneCard()
		currentPlayer = self.playerOrder[0]

		utils.logGameplay("Processing barile draw for {} against {}: {}.".format(player.getLogString(), self.currentCard.getDeterminerString(), drawnCard.suit))

		# If he needs it and can do so, draw a 2nd card for Jourdonnais.
		if player.character.name == JOURDONNAIS and player.countBariles() == 2 and drawnCard.suit != HEART:
			jourdonnaisTriedTwice = True
			drawnCard = self.drawAndDiscardOneCard()
		else:
			jourdonnaisTriedTwice = False

		effectiveDisplayName = self.currentCard.getDisplayName()
		if player.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO:
			effectiveDisplayName = MANCATO_AS_BANG

		if currentPlayer.character.name != SLAB_THE_KILLER or self.currentCard.name != BANG:
			if drawnCard.suit == HEART:
				utils.logGameplay("{} drew a heart and will avoid the {}".format(player.getLogString(), effectiveDisplayName))
				emitTuples = [self.createInfoTuple("You drew a heart for Barile {}and avoided {}'s {}!".format("on your second card " if jourdonnaisTriedTwice else "", currentPlayer.username, effectiveDisplayName), player)]
				emitTuples.append(self.createInfoTuple("{} drew a heart for Barile and avoided your {}!".format(player.username, effectiveDisplayName), currentPlayer))
				emitTuples.extend(self.createUpdates("{} drew a heart for Barile and avoided {}'s {}.".format(player.username, currentPlayer.username, effectiveDisplayName)))

				# If the card was a Bang and the player avoided it, reset the current card.
				if self.currentCard.name == BANG:
					self.currentCard = None

			else:
				utils.logGameplay("{} didn't draw a heart for Barile against the {}".format(player.getLogString(), effectiveDisplayName))
				emitTuples = self.createUpdates("{} tried to avoid the {} with a Barile but didn't draw a heart{}.".format(player.username, effectiveDisplayName, " either time" if jourdonnaisTriedTwice else ""))
				
				# The Barile wasn't a heart, so check if a Mancato can still be played to avoid the attack. Otherwise, automatically take the hit.
				if self.currentCard.name == BANG: emitTuples.append(utils.createWaitingModalTuple(currentPlayer, "{} didn't draw a heart for Barile against {}. Waiting for them to react...".format(player.username, self.currentCard.getDisplayName())))
				if len(player.getCardTypeFromHand(MANCATO)) > 0:
					emitTuples.append(self.addQuestion(player, QUESTION_BARILE_MANCATO.format(currentPlayer.username, effectiveDisplayName), [PLAY_A_MANCATO, LOSE_A_LIFE]))
				else:
					emitTuples.append(self.createInfoTuple("You didn't draw a heart for Barile.", player))
					emitTuples.append((SLEEP, AUTOMATIC_SLEEP_DURATION, None))
					emitTuples.extend(self.processPlayerTakingDamage(player, attacker=currentPlayer))
		
		# Handle the case where Slab the Killer used a Bang, so either 1 or 2 Mancatos still need to be played.
		else:
			mancatosInHand = player.getCardTypeFromHand(MANCATO)

			emitTuples.append(utils.createWaitingModalTuple(currentPlayer, "{} {} a Heart for Barile. Waiting for them to react...".format(player.username, "didn't draw" if drawnCard.suit != HEART else "drew")))

			if drawnCard.suit == HEART:
				utils.logGameplay("{} drew a heart but still needs to play a Mancato to avoid the Bang".format(player.getLogString()))
				emitTuples.extend(self.createUpdates("{} drew a heart for Barile.".format(player.username)))
				requiredMancatos = 1
			else:
				utils.logGameplay("{} didn't draw a heart, so they stil need to play 2 Mancatos to avoid the Bang".format(player.getLogString()))
				emitTuples.extend(self.createUpdates("{} didn't draw a heart{}.".format(player.username, " either time" if jourdonnaisTriedTwice else "")))
				requiredMancatos = 2
			
			if len(mancatosInHand) >= requiredMancatos:
				question = (QUESTION_SLAB_BARILE_ONE if requiredMancatos == 1 else QUESTION_SLAB_BARILE_TWO).format(currentPlayer.username)
				emitTuples.append(self.addQuestion(player, question, [PLAY_A_MANCATO if requiredMancatos == 1 else PLAY_TWO_MANCATOS, LOSE_A_LIFE]))
			else:
				emitTuples.append((SLEEP, AUTOMATIC_SLEEP_DURATION, None))
				emitTuples.extend(self.processPlayerTakingDamage(player, attacker=currentPlayer))

		return emitTuples

	# Try Bariles first, then ask players who can avoid the card if they want to, then process taking damage.
	# The cardName will already have been converted to BANG from MANCATO for Calamity Janet.
	def processBangGatlingIndians(self, player, cardName, target=None):
		requiredCard = MANCATO if cardName in [BANG, GATLING] else BANG
		question = {BANG: QUESTION_BANG_REACTION, INDIANS: QUESTION_INDIANS_REACTION, GATLING: QUESTION_GATLING_REACTION}[cardName].format(player.username)
		option = PLAY_A_MANCATO if cardName in [BANG, GATLING] else PLAY_A_BANG
		
		opponents = [target] if target != None else self.getAliveOpponents(player.username)

		effectiveDisplayName = utils.getDeterminerString(cardName)
		if player.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO:
			effectiveDisplayName = effectiveDisplayName.replace("Bang", MANCATO_AS_BANG)

		emitTuples = self.createUpdates("{} played {}{}.".format(player.username, effectiveDisplayName, '' if cardName != BANG else ' against {}'.format(target.username)))
		currentCard = self.currentCard

		if cardName == BANG:
			self.bangedThisTurn = True

		for opp in opponents:
			self.currentCard = currentCard # Resetting this is necessary for the case where more than 1 opponent takes damage.

			# Trying Bariles first.
			if cardName in [BANG, GATLING] and opp.countBariles() > 0:
				if opp.character.name == LUCKY_DUKE:
					emitTuples.append(self.createLuckyDukeTuple(opp))
					if cardName == BANG: emitTuples.append(utils.createWaitingModalTuple(player, "Waiting for {} (Lucky Duke) to choose a card for \"draw!\"...".format(opp.username)))
				else:
					emitTuples.extend(self.processBarileDraw(opp))
			
			# Then try giving the option of playing a Mancato/Bang in response.
			elif len(opp.getCardTypeFromHand(requiredCard)) >= (2 if cardName == BANG and player.character.name == SLAB_THE_KILLER else 1):
				if cardName == BANG and player.character.name == SLAB_THE_KILLER:
					option = PLAY_TWO_MANCATOS
				
				emitTuples.append(self.addQuestion(opp, question, [option, LOSE_A_LIFE]))
				if cardName == BANG: emitTuples.append(utils.createWaitingModalTuple(player, "Waiting for {} to decide how to react to {}...".format(opp.username, utils.convertRawNameToDisplay(cardName))))
			
			# Otherwise, there's no choice, so automatically take the damage.
			else:
				if cardName == BANG: emitTuples.append(utils.createWaitingModalTuple(player, "Waiting for {} to decide how to react to {}...".format(opp.username, utils.convertRawNameToDisplay(cardName))))
				emitTuples.append((SLEEP, AUTOMATIC_SLEEP_DURATION, None))
				emitTuples.extend(self.processPlayerTakingDamage(opp, attacker=player))

		self.currentCard = None if self.currentCardCanBeReset() else currentCard

		utils.logGameplay("Processed {} playing {}. Returning the following tuples: {}".format(player.getLogString(), cardName, emitTuples))
		return emitTuples

	def createLuckyDukeTuple(self, player):
		self.playersWaitingFor.append(player.username)
		options = [self.drawOneCard(), self.drawOneCard()]
		self.drawPile += options # Re-insert these cards into the draw pile because they'll get re-drawn and properly discarded after receiving Lucky Duke's selection.
		return self.addQuestion(player, QUESTION_LUCKY_DUKE.format(self.currentCard.getDisplayName()), [c.getQuestionString() for c in options])

	def processJesseJonesDrawingFromPlayer(self, username, opponentName, automatic=False):
		emitTuples = []
		player = self.players[username]
		opponent = self.players[opponentName]
		
		if not opponent.isAlive():
			return [self.createInfoTuple("{} isn't in the game anymore!".format(opponentName), player)]
		elif len(opponent.cardsInHand) == 0:
			return [self.createInfoTuple("{} doesn't have any cards to draw from!".format(opponentName), player)]
		elif opponentName == username:
			return []

		cardsDrawn = self.drawCardsForPlayerTurn(player, opponentName)
		stolenCard = cardsDrawn[0]
		description = "You {}drew {} from {}'s hand and {} from the deck.".format("automatically " if automatic else "", stolenCard.getDeterminerString(), opponentName, cardsDrawn[1].getDeterminerString())
		self.drawingToStartTurn = False

		if opponent.character.name == SUZY_LAFAYETTE:
			emitTuples.extend(self.processSuzyLafayetteAbility(opponent))
		
		emitTuples.append(self.createCardsDrawnTuple(player, description, cardsDrawn))
		emitTuples.append(utils.createCardCarouselTuple(player, True))
		emitTuples.append(utils.createCardCarouselTuple(opponent, False))
		emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
		emitTuples.append(self.createInfoTuple("{} drew {} from your hand using Jesse Jones's ability!".format(player.username, stolenCard.getDeterminerString()), opponent))
		emitTuples.extend(self.createUpdates("{} drew a card from {}'s hand using Jesse Jones's ability.".format(player.username, opponentName)))

		return emitTuples

	def renderPlayPageForPlayer(self, username):
		player = self.players[username]
		utils.logGameplay("Rendering playing page for {}.".format(username))
		return render_template('play.html',
			player=player,
			cardsInPlayTemplate=utils.getCardsInPlayTemplate(player),
			playerInfoList=self.playerOrder,
			playerInfoListTemplate=utils.getPlayerInfoListTemplate(self.playerOrder),
			discardUidString='' if len(self.discardPile) == 0 else str(self.getTopDiscardCard().uid))

	def useSpecialAbility(self, username):
		player = self.players[username]

		if player.character.name == SID_KETCHUM:
			return self.processSidKetchumAbility(player)
		else:
			utils.logGameplay("Received request from {} to use special ability, but it's not applicable.".format(player.getLogString()))
			return []

	def processSidKetchumAbility(self, player):
		utils.logGameplay("Processing Sid Ketchum's ability for {}.".format(player.getLogString()))

		emitTuples = []

		if player.username in self.unansweredQuestions or player.username in self.playersWaitingFor:
			return []

		elif player == self.playerOrder[0] and self.discardingCards:
			return [self.createInfoTuple("You can't use your ability right now.", player)]

		elif player.lives == player.lifeLimit:
			return [self.createInfoTuple(ALREADY_MAX_LIVES, player)]
		
		elif len(player.cardsInHand) < 2:
			return [self.createInfoTuple("You don't have enough cards to use your special ability right now.", player)]

		elif self.specialAbilityCards[SID_KETCHUM] != None or len(player.cardsInHand) == 2:
			if self.specialAbilityCards[SID_KETCHUM] != None:
				if len(self.specialAbilityCards[SID_KETCHUM]) != 2:
					utils.logError("An invalid number of cards ({}) was given for {} to use his special ability.".format(self.specialAbilityCards[SID_KETCHUM], player.getLogString()))
					return []
				if not all([c in player.cardsInHand for c in self.specialAbilityCards[SID_KETCHUM]]):
					utils.logError("The cards {} were given for {} to use his special ability, but at least 1 doesn't match his current hand ({}).".format(self.specialAbilityCards[SID_KETCHUM], player.getLogString(), player.cardsInHand))
					return []

			for c in list(self.specialAbilityCards[SID_KETCHUM] if self.specialAbilityCards[SID_KETCHUM] != None else player.cardsInHand):
				self.discardCard(player, c)
			
			player.gainOneLife()
			self.specialAbilityCards[SID_KETCHUM] = None
			self.playersWaitingFor.remove(player.username)

			emitTuples.append(self.createInfoTuple("You've discarded 2 cards and gained a life.", player))
			emitTuples.extend(self.createUpdates("{} used Sid Ketchum's ability to discard 2 cards and gain a life.".format(player.username)))
			emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
			emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
			emitTuples.extend(utils.createHealthAnimationTuples(player.username, 1, self.playerOrder))

		# In this case, the player can discard 2 cards but needs to choose which 2 to discard.
		else:
			self.specialAbilityCards[SID_KETCHUM] = [] # Change this from None to indicate that the process of using the ability is ongoing.
			self.playersWaitingFor.append(player.username)
			emitTuples.append(self.createInfoTuple(SID_KETCHUM_INFO, player))
			emitTuples.extend(utils.createDiscardClickTuples(player))

		utils.logGameplay("Returning the following the tuples for {} for Sid Ketchum's ability: {}".format(player.getLogString(), emitTuples))
		return emitTuples

	def processSlabTheKillerAbility(self, player):
		utils.logGameplay("Processing Slab the Killer's ability for {}.".format(player.getLogString()))

		emitTuples = []
		self.specialAbilityCards[SLAB_THE_KILLER] = []
		mancatosInHand = player.getCardTypeFromHand(MANCATO)

		self.playersWaitingFor.append(player.username)

		# If the player only has 2 Mancatos, just play them automatically.
		if len(mancatosInHand) == 2:
			emitTuples = [self.createInfoTuple("You automatically played your last 2 Mancatos.", player)]

			self.processBlurCardSelection(player.username, mancatosInHand[0].uid) # Don't bother emitting the intermediate results.

			emitTuples.extend(self.processBlurCardSelection(player.username, mancatosInHand[1].uid))

		# Otherwise, blur the non-Mancatos for the user and have him/her choose which ones to use.
		else:
			emitTuples = utils.createCardBlurTuples(player, MANCATO, msg=CLICK_ON_CARD.format("first Mancato"))

		utils.logGameplay("Returning the following the tuples for {} for Slab the Killer's ability: {}".format(player.getLogString(), emitTuples))
		return emitTuples

	def processSuzyLafayetteAbility(self, player):
		emitTuples = []

		if player.character.name == SUZY_LAFAYETTE and len(player.cardsInHand) == 0:
			utils.logGameplay("Processing Suzy Lafayette's ability for {}.".format(player.getLogString()))
			self.drawCardsForPlayer(player)

			emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
			emitTuples.extend(self.getDiscardTuples(self.getTopDiscardCard()))
			emitTuples.append(self.createInfoTuple("You drew a card using Suzy Lafayette's ability!", player))
			emitTuples.extend(self.createUpdates("{} drew a card using Suzy Lafayette's ability.".format(player.username)))

			utils.logGameplay("Returning the following the tuples for {} for Suzy Lafayette's ability: {}".format(player.getLogString(), emitTuples))
		
		return emitTuples

	def processPlayerClickedOn(self, username, targetName, clickType):
		emitTuples = []
		player = self.players[username]
		target = self.players[targetName]

		if player.username == target.username:
			utils.logError("{} is targeting himself/herself for {}.".format(player.getLogString(), self.currentCard.name if self.currentCard != None else 'None'))
			return []
		elif player != self.playerOrder[0]:
			utils.logError("{} did an on-player click ({} against {}), but the current player is {}.".format(player.getLogString(), clickType, targetName, self.playerOrder[0].getLogString()))
			return []

		if clickType == JESSE_JONES_CLICK:
			return self.processJesseJonesDrawingFromPlayer(username, targetName)
		else:
			response = self.validateTargetChoice(player, target)
			if response == OK_MSG:
				return self.playCurrentCard(player, targetName=target.username)
			else:
				return [self.createInfoTuple(response, player, header="Invalid Target")] # Don't re-open the question modal so that the player can play another card if s/he wants to.

	def getPlayerList(self, username):
		if not self.gameOver:
			return [utils.createPlayerInfoListTuple(self.playerOrder, self.players[username])]
		else:
			return []