from card import Card, GunCard
from character import Character
from constants import *
from flask import Markup, render_template
import json
import random
import utils

class Gameplay(dict):
	def __init__(self):
		self.started = False
		self.preparedForSetup = False
		self.remainingRoles = None
		self.characters = None
		self.remainingCharacters = None
		self.players = dict() # players[username] = PlayerGame()
		self.playerOrder = list() # Current player should always be at index 0.
		self.currentTurn = None
		self.allCards = loadCards()
		self.drawPile = list(self.allCards)
		self.discardPile = list()
		self.currentCard = None
		self.sheriffUsername = None
		self.dynamiteStartTurn = None
		self.dynamiteUsername = None
		self.drawingToStartTurn = True
		self.discardingCards = False
		self.dynamiteState = 0 # 0 = no dynamite, 1 = dynamite was played but is still inactive, 2 = dynamite was played and is active
		self.bangedThisTurn = False
		self.emporioOptions = list()
		self.duelPair = list()
		self.updatesList = list() # A list of all updates throughout the game, which will be pulled whenever reloading the play page.
		self.unansweredQuestions = dict()

		dict.__init__(self)

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return str(vars(self))

	def prepareForSetup(self):
		self.started = True
		num_players = len(self.players)

		self.characters = loadCharacters()
		self.remainingCharacters = list(self.characters)
		random.shuffle(self.remainingCharacters)

		if num_players == 4: self.remainingRoles = [SHERIFF, OUTLAW, OUTLAW, RENEGADE]
		elif num_players == 5: self.remainingRoles = [SHERIFF, VICE, OUTLAW, OUTLAW, RENEGADE]
		elif num_players == 6: self.remainingRoles = [SHERIFF, VICE, OUTLAW, OUTLAW, OUTLAW, RENEGADE]
		else: self.remainingRoles = [SHERIFF, VICE, VICE, OUTLAW, OUTLAW, OUTLAW, RENEGADE]

		random.shuffle(self.remainingRoles)
		random.shuffle(self.drawPile)

		self.preparedForSetup = True
		utils.logGameplay("Successfully prepared for setup.")

	def assignNewPlayer(self, player):
		if len(self.remainingRoles) == 0 or len(self.remainingCharacters) < 2:
			utils.logError("Trying to pop element from empty list for {}.".format(player.username))
		else:
			player.role = self.remainingRoles.pop()
			player.characterOptions = [self.remainingCharacters.pop(), self.remainingCharacters.pop()]
			utils.logGameplay("Assigned {} to a role of {} with character options of {}.".format(player.username, player.role, [c.name for c in player.characterOptions]))

		if player.role == SHERIFF:
			self.sheriffUsername = player.username
			player.characterOptions[1] = [c for c in self.characters if c.name == JESSE_JONES][0] # TODO: Delete this eventually!

		self.playerOrder.append(player)

	def assignCharacter(self, username, c):
		character = self.getCharacter(c)
		player = self.players[username]
		player.character = character
		
		# Assign the player's initial number of lives.
		player.lives = character.num_lives + (1 if self.sheriffUsername == username else 0)
		player.lifeLimit = player.lives

		# Deal out however many cards the player should start with.
		self.drawCardsForPlayer(player, player.lives)

		utils.logGameplay("Assigned {} to a character of {} with an initial hand of {}.".format(player.username, c, [card.name for card in player.cardsInHand]))

	def getCharacter(self, c):
		return utils.getObjectFromList(lambda obj: obj.name == c, self.characters)

	def finalizeSetup(self):
		random.shuffle(self.playerOrder)

		# Make sure the sheriff starts the game.
		while self.playerOrder[0].role != SHERIFF:
			self.rotatePlayerOrder()

		self.currentTurn = 0

		utils.logGameplay("Initial player order will be: {}. STARTING GAME.".format([u.username for u in self.playerOrder]))

		return self.startNextTurn(self.getCurrentPlayerName())

	def rotatePlayerOrder(self):
		self.playerOrder = self.playerOrder[1:] + self.playerOrder[:1]
		if not self.playerOrder[0].isAlive(): # Keep rotating until a non-eliminated player starts.
			self.rotatePlayerOrder()

	def getCurrentPlayerName(self):
		return self.playerOrder[0].username

	def getTopDiscardCard(self):
		return self.discardPile[-1]

	def advanceTurn(self):
		if self.currentTurn > 0:
			self.rotatePlayerOrder()
		self.currentTurn += 1
		self.bangedThisTurn = False
		self.drawingToStartTurn = True

		if self.dynamiteUsername == self.getCurrentPlayerName(): # If both apply, dynamite needs to be drawn for before jail.
			self.currentCard = self.getDynamiteCard()
		elif self.playerOrder[0].jailStatus == 1:
			self.currentCard = utils.getObjectFromList(lambda card: card.name == PRIGIONE, self.playerOrder[0].specialCards)
		else:
			self.currentCard = None

	def startNextTurn(self, username):
		if username == None or username not in self.players:
			utils.logError("Unrecognized username passed into startNextTurn().")
			return []
		elif username != self.getCurrentPlayerName():
			utils.logError("{} shouldn't be able to end the current turn (the current player is {}).".format(username, self.getCurrentPlayerName()))
			return []

		emitTuples = []

		player = self.playerOrder[0]
		cardsTooMany = player.countExcessCards()
		
		# self.discardingCards will be False if the player just triggered the end of his/her turn, so have him/her discard cards as required.
		if self.currentTurn > 0 and cardsTooMany > 0:
			self.discardingCards = True
			emitTuples.append(utils.createDiscardClickTuple(player))

			if cardsTooMany > 0:
				text = "You {}need to discard {} card{}! Click on cards in your hand to discard them. Press Shift-E once you're finished.".format("still " if self.discardingCards else "", cardsTooMany, "s" if cardsTooMany > 1 else "")
				emitTuples.extend(utils.createInfoTuples(text, recipients=[player]))

		else: # The player is done discarding, so move on to the next player.
			self.discardingCards = False

			if self.playerOrder[0].jailStatus == 0: emitTuples.append(self.appendUpdate("{} ended their turn.".format(self.getCurrentPlayerName())))
			self.playerOrder[0].jailStatus = 0 # A player should never end his/her turn in jail.
			
			self.advanceTurn()
			utils.logGameplay("Starting the next turn. The new current player is {}.".format(self.getCurrentPlayerName()))
			player = self.playerOrder[0]

			emitTuples.append((SLEEP, 0.5, None)) # Pause for half a second in between every turn.
			drawTuples = self.processSpecialCardDraw(player)

			# If the player is still in jail at this point, skip their turn and go on to the next player.
			if player.jailStatus == 1:
				return emitTuples + drawTuples + [(END_YOUR_TURN, dict(), player)]

			emitTuples.append(utils.createPlayerInfoListTuple(self.playerOrder))

			for p in self.playerOrder:
				emitTuples.append(utils.createPlayPageTuple(p, self.renderPlayPageForPlayer(p)))

			if len(drawTuples) > 0: # If there was a "draw!", add those tuples in here and add a pause so that the modals don't clash.
				emitTuples.append((SLEEP, 1, None))
				emitTuples.extend(drawTuples)

			for p in self.playerOrder:
				emitTuples.extend(self.makeCardDrawModalTuples(p))

		return emitTuples

	def appendUpdate(self, updateString):
		self.updatesList.append(updateString)
		return utils.createUpdateTuple(updateString)

	def addQuestion(self, player, question, options, cardsDrawn=None):
		if player.username in self.unansweredQuestions:
			utils.logError("{} is getting asked \"{}\" before answering \"{}\".".format(question, self.unansweredQuestions[player.username]))
			return None

		self.unansweredQuestions[player.username] = question
		return utils.createQuestionTuple(player, question, options, cardsDrawn=cardsDrawn)

	def getDynamiteCard(self):
		return utils.getObjectFromList(lambda c: c.name == DYNAMITE, self.allCards)

	def getCardByUid(self, uid):
		return utils.getObjectFromList(lambda c: c.uid == int(uid), self.allCards)

	def drawOneCard(self):
		card = self.drawPile.pop()

		# Reshuffle the draw pile once it's empty.
		if len(self.drawPile) == 0:
			utils.logGameplay("Reshuffling the draw pile. It will now have {} cards.".format(len(self.discardPile)))
			self.drawPile = list(self.discardPile)
			self.discardPile = list()
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
			self.drawCardsForPlayer(player, 3)
			result = player.cardsInHand[-3:]
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

	def discardCard(self, player, card):
		player.getRidOfCard(card)
		self.discardPile.append(card)
		utils.logGameplay("Adding {} (UID: {}) to the discard pile.".format(card.getDeterminerString(), card.uid))

	def playerDiscardingCard(self, username, uid):
		player = self.players[username]
		card = self.getCardByUid(uid)
		self.discardCard(player, card)
		emitTuples = []

		if player.countExcessCards() == 0:
			emitTuples.append((END_YOUR_TURN, dict(), player))

		emitTuples.append(utils.createDiscardTuple(self.getTopDiscardCard()))
		emitTuples.append(self.appendUpdate("{} discarded {}.".format(username, card.getDeterminerString())))
		emitTuples.append(utils.createCardCarouselTuple(player, True))
		emitTuples.append(utils.createDiscardClickTuple(player))

		return emitTuples

	# Check whether the user should even have the option of playing this card right now.
	# If it's a targeted card, also return question modal information listing all alive opponents as choices...
	# ...instead of filtering here; validate target choices separately so that that information can be shown in a modal too.
	def validateCardChoice(self, username, uid):
		player = self.players[username]
		card = self.getCardByUid(uid)
		emitTuples = []
		targetName = None
		aliveOpponents = self.getAliveOpponents(username)

		if card not in player.cardsInHand:
			utils.logError("{} tried to play {} ({}) but doesn't have it in his/her hand.".format(username, card.getDeterminerString(), uid))
			return []

		if self.currentCard != None:
			return utils.createInfoTuples("Slow down! We're still waiting for your {} to get finished.".format(self.currentCard.getDisplayName()), recipients=[player])

		if self.isEffectiveBang(player, card.name):
			if self.bangedThisTurn and player.hasBangLimit():
				response = "You've already played a Bang this turn!"
			else:
				validTargets = self.getAllValidTargetsForCard(player, BANG)
				if len(validTargets) == 0:
					response = "There's nobody in range for a Bang right now!"
				else:
					response = OK_MSG
					if len(aliveOpponents) > 1:
						emitTuples = [self.getQuestionModalWithAliveOpponents(player, QUESTION_WHO_TO_SHOOT)]
						utils.logGameplay("Adding modal question data for {} for Bang validation.".format(username))
					else: # If there's only 1 opponent left, automatically play the Bang against him/her.
						if validTargets[0] != aliveOpponents[0]:
							utils.logError("There should only be 1 opponent alive to be the Bang target, but alive opponents are {} and valid targets are {}.".format(aliveOpponents, validTargets))
							return []

						target = validTargets[0]
						text = "You automatically played the {} against {}, the only player alive.".format(card.getDisplayName(), target.username)
						self.currentCard = card

						emitTuples = utils.createInfoTuples(text, recipients=[player])
						emitTuples.extend(self.playCurrentCard(player, target.username))
						return emitTuples

		elif card.name == MANCATO:
			response = "You can't play a Mancato right now!"

		elif card.name in [PANICO, CAT_BALOU]:
			validTargets = self.getAllValidTargetsForCard(player, card.name)
			if len(validTargets) == 0:
				response = "There's nobody in range for {} right now!".format(card.getDeterminerString())
			else:
				response = OK_MSG
				if len(aliveOpponents) == 1: # If there's only 1 alive opponent left, automatically play the Panico/Cat Balou against him/her.
					targetName = aliveOpponents[0].username
				else:
					emitTuples = [self.getQuestionModalWithAliveOpponents(player, QUESTION_WHOSE_CARDS)]

		elif card.name == DUELLO:
			response = OK_MSG

			if len(aliveOpponents) == 1: # If there's only 1 alive opponent left, automatically play the Duello against him/her.
				targetName = aliveOpponents[0].username
			else:
				emitTuples = [self.getQuestionModalWithAliveOpponents(player, QUESTION_WHO_TO_DUEL)]

			

		elif card.name == BIRRA:
			if len(self.getAlivePlayers()) == 2:
				response = "You can't use Birras when it's 1-v-1!"
			elif player.lives == player.lifeLimit:
				response = "You already have your maximum number of lives!"
			else:
				response = OK_MSG

		elif card.name == SALOON:
			if all([p.lives == p.lifeLimit for p in self.getAlivePlayers()]):
				response = "You can't play a Saloon right now because nobody would gain a life!"
			else:
				response = OK_MSG

		elif card.cardtype in [BLUE_CARD, GUN_CARD]:
			if card.name in [c.name for c in player.cardsInPlay]:
				response = "You already have {} in play!".format(card.getDeterminerString())
			elif card.cardtype == GUN_CARD and GUN_CARD in [c.cardtype for c in player.cardsInPlay]:
				response = OK_MSG
				emitTuples = [self.addQuestion(player, QUESTION_REPLACE_GUN, [KEEP_GUN, REPLACE_GUN])]
			elif len(player.cardsInPlay) == 2:
				response = OK_MSG
				emitTuples = [self.addQuestion(player, QUESTION_IN_PLAY, [KEEP_CURRENT_CARDS, REPLACE_A_CARD])]
			else:
				response = OK_MSG

		elif card.name == PRIGIONE:
			validTargets = self.getAllValidTargetsForCard(player, PRIGIONE)
			if len(validTargets) > 0:
				response = OK_MSG
				if len(aliveOpponents) == 1: # If there's only 1 alive opponent left, automatically jail him/her.
					targetName = aliveOpponents[0].username
				else:
					emitTuples = [self.getQuestionModalWithAliveOpponents(player, QUESTION_WHO_TO_JAIL)]
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
			return utils.createInfoTuples(response, header="Invalid Card", recipients=[player])

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
			emitTuples.append(utils.createDiscardTuple(self.getTopDiscardCard()))
		
		# Otherwise, the player needs to get rid of it from their hand, but it won't go on the discard pile yet.
		else:
			player.getRidOfCard(card)

		# Make sure the card is removed from the player's hand in the UI.
		emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

		# Checking that these are valid moves has already been done in the validateCardChoice and validateTargetChoice methods.
		if targetName == None:
			if card.cardtype in [BLUE_CARD, GUN_CARD]:
				player.cardsInPlay.append(card)
				emitTuples.append(utils.createCardCarouselTuple(player, True))
				emitTuples.append(utils.createCardsInPlayTuple(player))
				emitTuples.append(self.appendUpdate("{} put {} in play.".format(player.username, card.getDeterminerString())))
				self.currentCard = None

			elif card.name == DYNAMITE:
				player.specialCards.append(card)
				self.dynamiteUsername = player.username
				self.dynamiteStartTurn = self.currentTurn + 1

				text = "{} played a dynamite!".format(player.username)
				emitTuples.extend(utils.createInfoTuples(text, recipients=self.getAliveOpponents(player.username)))
				emitTuples.append(self.appendUpdate(text))
				self.currentCard = None

			elif card.name == BIRRA:
				player.gainOneLife()
				emitTuples.append(self.appendUpdate("{} played a Birra and now has {} lives.".format(player.username, player.lives)))
				self.currentCard = None

			if card.name == SALOON:
				for u in self.players:
					self.players[u].gainOneLife()

				emitTuples.append(self.appendUpdate("{} played a Saloon!".format(player.username)))
				self.currentCard = None

			elif card.name in [DILIGENZA, WELLS_FARGO]:
				numCards = 3 if card.name == WELLS_FARGO else 2
				self.drawCardsForPlayer(player, numCards)
				emitTuples.append(self.appendUpdate("{} played {} and drew {} cards.".format(player.username, card.getDeterminerString(), numCards)))
				emitTuples.append(utils.createCardCarouselTuple(player, True))
				emitTuples.append(utils.createCardsDrawnTuple(player, "You drew {} cards for {}:".format(numCards, card.getDisplayName()), player.cardsInHand[-numCards:], startingTurn=False))
				self.currentCard = None

			elif card.name == EMPORIO:
				# Get one card option for each non-eliminated player and show all players the choices.
				self.emporioOptions = list()
				for _ in range(len(self.getAlivePlayers())):
					self.emporioOptions.append(self.drawOneCard())
				
				emitTuples.append(self.appendUpdate("{} played an Emporio!".format(player.username)))

				if len({c.name for c in self.emporioOptions}) > 1:
					utils.logGameplay("Initial options for Emporio for {}: {}".format([p.username for p in self.getAlivePlayers()], [c.uid for c in self.emporioOptions]))
					emitTuples.extend(utils.createEmporioTuples(self.getAlivePlayers(), self.emporioOptions, player))
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
				if len(target.getCardTypeFromHand(BANG)) == 0: # Automatically count the Duello as a win if the target doesn't have any Bangs.
					emitTuples.append((SLEEP, 1, None))
					emitTuples.extend(self.processDuelloResponse(target, LOSE_A_LIFE))
				else:
					emitTuples.append(self.addQuestion(target, QUESTION_DUELLO_REACTION.format(player.username), [PLAY_A_BANG, LOSE_A_LIFE]))
					emitTuples.append(utils.createWaitingModalTuple(player, WAITING_DUELLO_REACTION.format(target.username)))
					emitTuples.append(self.appendUpdate("{} challenged {} to a duel.".format(player.username, targetName)))

			elif card.name == PRIGIONE:
				target.jailStatus = 1
				target.specialCards.append(card)
				emitTuples.extend(utils.createInfoTuples("{} just put you in jail!".format(player.username), recipients=[target]))
				emitTuples.append(self.appendUpdate("{} just put {} in jail.".format(player.username, target.username)))
				self.currentCard = None

		return emitTuples

	def getAllValidTargetsForCard(self, player, cardName):
		if self.isEffectiveBang(player, cardName):
			validTargets = [target for target in self.getAliveOpponents(player.username) if self.targetIsInRange(player, target)] 
		
		elif cardName == PANICO:
			validTargets = [target for target in self.getAliveOpponents(player.username) if self.targetIsInRange(player, target, bang=False) and len(target.cardsInHand + target.cardsInPlay) >= 1] 

		elif cardName == CAT_BALOU:
			validTargets = [target for target in self.getAliveOpponents(player.username) if len(target.cardsInHand) + len(target.cardsInPlay) >= 1] 

		elif cardName == PRIGIONE:
			validTargets = [target for target in self.getAliveOpponents(player.username) if target.role != SHERIFF and target.jailStatus == 0]

		else:
			utils.logError("Shouldn't be attempting to get valid targets for {}.".format(cardName))
			return []

		utils.logGameplay("The valid targets for {} for {} are {}".format(player.username, cardName, [t.username for t in validTargets]))
		return validTargets

	def validateTargetChoice(self, player, target, card=None): # Check whether this specific target is valid for the given user.
		if card == None: card = self.currentCard

		utils.logGameplay("Checking whether {} playing {}{} is valid.".format(player.username, card.getDeterminerString(), " against {}".format(target.username) if target.username else ""))

		if self.isEffectiveBang(player, card.name):
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
		
		if result != OK_MSG:
			utils.logGameplay("Resetting current card ({}) to None.".format(self.currentCard.getDisplayName()))
			self.currentCard = None

		return result

	def targetIsInRange(self, player, target, bang=True):
		effectiveDistance = self.calculateEffectiveDistance(player, target)
		return effectiveDistance <= (player.getGunRange() if bang else 1)

	# Get the effective distance between 2 players after factoring in eliminated opponents, scopes, and mustangs.
	def calculateEffectiveDistance(self, player, target):
		targetIndex = [u.username for u in self.getAlivePlayers()].index(target.username)
		baseDistance = min(targetIndex, len(self.players) - targetIndex)
		result = baseDistance - player.getScopeDistance() + target.getMustangDistance()

		utils.logGameplay("Calculated an effective distance of {} from {} to {}.".format(result, player.username, target.username))
		return result

	def advanceDynamite(self):
		currentPlayer, nextPlayer = self.getAlivePlayers()[:2]
		utils.logGameplay("Advancing the dynamite from {} to {}.".format(currentPlayer.username, nextPlayer.username))

		self.dynamiteUsername = self.getAlivePlayers()[1]
		dynamiteCard = self.getDynamiteCard()
		currentPlayer.getRidOfCard(dynamiteCard)
		nextPlayer.specialCards.append(dynamiteCard)

		return nextPlayer

	def isEffectiveBang(self, player, cardName):
		return cardName == BANG or (player.character.name == CALAMITY_JANET and cardName == MANCATO)

	def makeCardDrawModalTuples(self, player):
		opponents = [p for p in self.playerOrder[1:]]
		emitTuples = []

		# For the player whose turn it currently is.
		if player == self.playerOrder[0]:

			if player.jailStatus == 1:
				emitTuples.extend(utils.createInfoTuples("You can't draw this turn since you're in jail.", recipients=[player]))

			# If the character isn't Jesse Jones/Kit Carlson/Pedro Ramirez, you can always just draw from the deck.
			elif player.character.name not in [JESSE_JONES, KIT_CARLSON, PEDRO_RAMIREZ]:
				cardsDrawn = self.drawCardsForPlayerTurn(player)
				description = "You drew {}.".format(utils.convertCardsDrawnToString(cardsDrawn))
				self.drawingToStartTurn = False

				if player.character.name == BLACK_JACK:
					if len(cardsDrawn) == 3:
						description = description[:-1] + " because the {} is a {}.".format(cardsDrawn[1].getDisplayName(), cardsDrawn[1].suit)
					updateString = "{} (Black Jack) drew {} cards. The second card was {}.".format(player.username, len(cardsDrawn), cardsDrawn[1].getDeterminerString())
				else:
					updateString = DREW_2_CARDS.format(player.username)

				emitTuples.append(utils.createCardsDrawnTuple(player, description, cardsDrawn))
				emitTuples.append(self.appendUpdate(updateString))
				return emitTuples

			else:
				if player.character.name == JESSE_JONES:
					# Jesse Jones can only use her special ability if anyone has cards to draw from.
					playersToDrawFrom = self.getPlayersWithCardsInHand(player.username)
					if len(playersToDrawFrom) == 0:
						cardsDrawn = self.drawCardsForPlayerTurn(player)
						description = "You drew {} (you were forced to draw 2 cards from the deck because no other players have cards to draw from).".format(utils.convertCardsDrawnToString(cardsDrawn))
						self.drawingToStartTurn = False

						emitTuples.append(utils.createCardsDrawnTuple(player, description, cardsDrawn))
						emitTuples.append(self.appendUpdate(DREW_2_CARDS.format(player.username)))
						return emitTuples

					else:
						return [self.addQuestion(player, QUESTION_JESSE_JONES, [FROM_ANOTHER_PLAYER, FROM_THE_DECK])]

				elif player.character.name == KIT_CARLSON:
					cardsDrawn = self.drawCardsForPlayerTurn(player)
					options = [c.getQuestionString() for c in cardsDrawn]
					question = QUESTION_KIT_CARLSON

					return [self.addQuestion(player, question, options, cardsDrawn=cardsDrawn)]
				
				elif player.character.name == PEDRO_RAMIREZ:
					# Pedro Ramirez can only use his special ability if there are any cards in the discard pile.
					if len(self.discardPile) == 0:
						cardsDrawn = self.drawCardsForPlayerTurn(player)
						description = "You drew {} (you were forced to draw 2 cards from the deck because the discard pile is empty right now).".format(utils.convertCardsDrawnToString(cardsDrawn))
						self.drawingToStartTurn = False
						
						emitTuples.append(utils.createCardsDrawnTuple(player, description, cardsDrawn))
						emitTuples.append(self.appendUpdate(DREW_2_CARDS.format(player.username)))

					else:
						return [self.addQuestion(player, QUESTION_PEDRO_RAMIREZ, [FROM_DISCARD, FROM_THE_DECK])]

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
		
		if question != self.unansweredQuestions[username]:
			utils.logError("Received a response from {} for \"{}\", but their saved question is \"{}\"".format(username, question, self.unansweredQuestions[username]))
			return [] 

		del self.unansweredQuestions[username] # This player has answered his/her question, so it can be discarded.
		
		# Handle the responses for characters who have special start-of-turn draws. 
		if self.drawingToStartTurn:
			if player.character.name in [JESSE_JONES, KIT_CARLSON, PEDRO_RAMIREZ]:
				emitTuples = self.processAbilityQuestionResponse(username, question, answer)
			else:
				utils.logError("{} shouldn't be answering a modal question while drawing for cards to start the turn.".format(player.getLogString()))

		else:
			# Handle a player answering which opponent to target for the current card.
			if answer in self.players:
				target = self.players[answer]

				if player != currentPlayer:
					utils.logError("{} answered a question targeting someone ({}), but the current player is {}.".format(player.getLogString(), answer, currentPlayer.getLogString()))
					return []
				if player.username == target.username:
					utils.logError("{} is targeting himself/herself for {}.".format(player.getLogString(), self.currentCard.name))
					return []

				response = self.validateTargetChoice(player, target)
				if response == OK_MSG:
					return self.playCurrentCard(player, targetName=target.username)
				else:
					return utils.createInfoTuples(response, header="Invalid Target", recipients=[player]) # Don't re-open the question modal so that the player can play another card if s/he wants to.

			# Handle Lucky Duke choosing one of 2 cards for "draw!".
			elif player.character.name == LUCKY_DUKE and question == QUESTION_LUCKY_DUKE.format(self.currentCard.getDisplayName()):
				emitTuples = self.processAbilityQuestionResponse(username, question, answer)

			# Handle responses for players in a Duello.
			elif any([utils.getReverseFormat(formatString, question) != None for formatString in [QUESTION_DUELLO_REACTION, QUESTION_DUELLO_BANG_REACTION]]):
				emitTuples = self.processDuelloResponse(player, answer)

			# Handle responses for players playing a Cat Balou or Panico.
			elif any([utils.getReverseFormat(formatString, question) != None for formatString in [QUESTION_PANICO_CARDS, QUESTION_CAT_BALOU_CARDS, QUESTION_CARD_ON_TABLE]]):
				hasCardOnTableChosen = False

				if utils.getReverseFormat(QUESTION_PANICO_CARDS, question) != None:
					target = self.players[utils.getReverseFormat(QUESTION_PANICO_CARDS, question)[0]]
					cardName = PANICO
				elif utils.getReverseFormat(QUESTION_CAT_BALOU_CARDS, question) != None:
					target = self.players[utils.getReverseFormat(QUESTION_CAT_BALOU_CARDS, question)[0]]
					cardName = CAT_BALOU
				else:
					targetName, cardName = utils.getReverseFormat(QUESTION_CARD_ON_TABLE, question)
					cardName = utils.convertDisplayNameToRaw(cardName)
					target = self.players[targetName]
					hasCardOnTableChosen = True

				# If we know or can figure out the selected card already, just process the result here.
				if answer == FROM_THEIR_HAND or (answer == FROM_THE_TABLE and len(target.cardsInPlay) == 1) or hasCardOnTableChosen:
					if answer == FROM_THE_TABLE and len(target.getCardsOnTable()) == 1:
						selectedCard = target.panico(target.getCardsOnTable()[0])
					elif hasCardOnTableChosen: # The answer should match the QUESTION_CARD_FORMAT format.
						name, value, suit = utils.getReverseFormat(QUESTION_CARD_FORMAT, answer)
						name = utils.convertDisplayNameToRaw(name)
						cardChosen = utils.getObjectFromList(lambda card: (name, suit, value) == (card.name, card.suit, card.value), target.getCardsOnTable())
						selectedCard = target.panico(cardChosen)
					else:
						selectedCard = target.panico()

					return self.processPanicoCatBalou(player, target, cardName, selectedCard)
				
				# Otherwise, ask the player which of the target's cards on the table s/he wants to select.
				else:
					return [self.addQuestion(player, QUESTION_CARD_ON_TABLE.format(target.username, self.currentCard.getDisplayName()), [c.getQuestionString() for c in target.getCardsOnTable()])]

			# Handle responses for how a player wants to react to Bang/Indians/Gatling.
			elif question in [q.format(currentPlayer.username) for q in [QUESTION_BANG_REACTION, QUESTION_INDIANS_REACTION, QUESTION_GATLING_REACTION, QUESTION_BARILE_MANCATO, QUESTION_SLAB_BARILE_ONE, QUESTION_SLAB_BARILE_TWO]]:
				if answer == LOSE_A_LIFE:
					emitTuples = self.processPlayerTakingDamage(player)
				elif answer in [PLAY_A_MANCATO, PLAY_TWO_MANCATOS, PLAY_A_BANG]:
					requiredCardName = MANCATO if MANCATO in answer.lower() else BANG
					requiredCardsInHand = player.getCardTypeFromHand(requiredCardName)

					# If the player only has 1 required card to play, automatically play it.
					if len(requiredCardsInHand) == 1:
						card = requiredCardsInHand[0]
						emitTuples = utils.createInfoTuples("You automatically played your only {} left.".format(card.getDisplayName()), recipients=[player])
						emitTuples.append((SLEEP, 0.5, None))
						emitTuples.extend(self.processBlurCardSelection(player.username, card.uid))

					# Otherwise, blur the non-playable cards for the user and have him/her choose the playable one to use.
					else:
						emitTuples = utils.createCardBlurTuples(player, requiredCardName)

				else:
					utils.logError("Answer by {} for reacting to an attacking card doesn't match any expected option: {}.".format(username, answer))

			# Handle the case where a player wants to play a new blue card but already has 2 cards in play.
			elif question in [QUESTION_IN_PLAY, QUESTION_CARD_IN_PLAY]:
				if question == QUESTION_IN_PLAY:
					if answer == KEEP_CURRENT_CARDS:
						self.currentCard = None
					else:
						emitTuples = [self.addQuestion(player, QUESTION_CARD_IN_PLAY, [c.getQuestionString() for c in player.cardsInPlay])]
				
				else: # The answer should match the QUESTION_CARD_FORMAT format.
					name, value, suit = utils.getReverseFormat(QUESTION_CARD_FORMAT, answer)
					name = utils.convertDisplayNameToRaw(name)
					cardToDiscard = utils.getObjectFromList(lambda card: (name, suit, value) == (card.name, card.suit, card.value), player.cardsInPlay)
					emitTuples.extend(self.replaceInPlayCard(player, cardToDiscard))

			# Handle player deciding what to do when a gun is already in play.
			elif question == QUESTION_REPLACE_GUN:
				if answer == REPLACE_GUN:
					inPlayGun = utils.getObjectFromList(lambda card: card.cardtype == GUN_CARD, player.cardsInPlay)
					emitTuples.extend(self.replaceInPlayCard(player, inPlayGun))
				else:
					self.currentCard = None

		return emitTuples

	def processPanicoCatBalou(self, player, target, cardName, selectedCard=None):
		emitTuples = []

		if selectedCard != None:
			utils.logGameplay("{} played a {} to make {} lose {}.".format(player.username, cardName, target.username, selectedCard.getDeterminerString()))
			if cardName == PANICO:
				target.getRidOfCard(selectedCard)
				player.addCardToHand(selectedCard)
				emitTuples = utils.createInfoTuples("{} played a Panico and stole {} from you!".format(player.username, selectedCard.getDeterminerString()), recipients=[target], cards=[selectedCard])
				emitTuples.extend(utils.createInfoTuples("You stole {} from {}!".format(selectedCard.getDeterminerString(), target.username), recipients=[player], cards=[selectedCard]))
				emitTuples.append(self.appendUpdate("{} played a Panico on {} and stole a card.".format(player.username, target.username)))
			else:
				self.discardCard(target, selectedCard)
				emitTuples.append(utils.createDiscardTuple(selectedCard))
				emitTuples.extend(utils.createInfoTuples("{} played a Cat Balou and made you discard {}!".format(player.username, selectedCard.getDeterminerString()), recipients=[target], cards=[selectedCard]))
				emitTuples.extend(utils.createInfoTuples("You forced {} to discard {}!".format(target.username, selectedCard.getDeterminerString()), recipients=[player], cards=[selectedCard]))
				emitTuples.append(self.appendUpdate("{} played a Cat Balou on {}, who had to discard {}.".format(player.username, target.username, selectedCard.getDeterminerString())))
			
			self.currentCard = None
			emitTuples.append(utils.createCardCarouselTuple(player, True))
			emitTuples.append(utils.createCardCarouselTuple(target, False))

		else:
			if len(target.cardsInHand) > 0 and len(target.getCardsOnTable()) == 0: # Have to steal from the hand.
				selectedCard = target.panico()
				emitTuples = self.processPanicoCatBalou(player, target, cardName, selectedCard)
			elif len(target.getCardsOnTable()) == 1 and len(target.cardsInHand) == 0: # Have to steal the player's only card on the table.
				selectedCard = target.panico(target.cardsInPlay[0])
				emitTuples = self.processPanicoCatBalou(player, target, cardName, selectedCard)
			elif len(target.getCardsOnTable()) >= 2 and len(target.cardsInHand) == 0: # Have to steal from what's on the table.
				options = [c.getQuestionString() for c in target.getCardsOnTable()]
				emitTuples = [self.addQuestion(player, QUESTION_CARD_ON_TABLE.format(target.username, utils.convertRawNameToDisplay(cardName)), options)]
			else:
				question = QUESTION_PANICO_CARDS if cardName == PANICO else QUESTION_CAT_BALOU_CARDS
				options = [FROM_THEIR_HAND, FROM_THE_TABLE]
				emitTuples = [self.addQuestion(player, question.format(target.username), options)]

		return emitTuples

	def processDuelloResponse(self, player, answer=None, card=None):
		emitTuples = []

		attacker = [p for p in self.duelPair if p != player][0]

		if card != None: # A card will be passed in if we've already gotten a response about which card to play (or if there's only 1 option).
			self.discardCard(player, card)
			effectiveDisplayName = "Bang" if (player.character.name != CALAMITY_JANET or card.name != MANCATO) else MANCATO_AS_BANG
			emitTuples = [self.appendUpdate("{} responded in the duel with {} by playing a {}.".format(player.username, attacker.username, effectiveDisplayName))]
			emitTuples.append(utils.createDiscardTuple(card))
			emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

			if len(attacker.getCardTypeFromHand(BANG)) > 0:
				emitTuples.append(utils.createWaitingModalTuple(player, WAITING_DUELLO_REACTION.format(attacker.username)))
				emitTuples.append(self.addQuestion(attacker, QUESTION_DUELLO_BANG_REACTION.format(player.username), [PLAY_A_BANG, LOSE_A_LIFE]))
			
			# Handle the case where the next player doesn't have any Bangs to respond with.
			else:
				emitTuples.append((SLEEP, 1, None))
				emitTuples.extend(self.processPlayerTakingDamage(attacker, attacker=player))
				self.duelPair = list()

		else:
			if answer == LOSE_A_LIFE:
				emitTuples.extend(self.processPlayerTakingDamage(player, attacker=attacker))
				self.duelPair = list()

			elif answer == PLAY_A_BANG:
				bangsInHand = player.getCardTypeFromHand(BANG)
				if len(bangsInHand) == 1: # If the player only has 1 Bang, automatically play it.
					emitTuples = utils.createInfoTuples("You automatically played your only Bang left.", recipients=[player])
					emitTuples.extend(self.processDuelloResponse(player, card=bangsInHand[0]))
				else:
					emitTuples = utils.createCardBlurTuples(player, BANG)

			else:
				utils.logError("Answer by {} for reacting to a Duello doesn't match any expected option: {}.".format(player.username, answer))

		return emitTuples

	# Function to process the effects of a player taking damage once it's definitive that s/he will do so.
	def processPlayerTakingDamage(self, player, damage=1, attacker=None):
		emitTuples = []
		opponents = self.getAliveOpponents(player.username)

		if attacker != None and player.username == attacker.username:
			utils.logError("{} shouldn't be able to damage himself/herself.".format(player.getLogString()))
			return []
		
		player.loseOneLife()
		for _ in range(damage - 1):
			player.loseOneLife()

		lostLivesString = "a life" if damage == 1 else "{} lives".format(damage)

		if self.isEffectiveBang(player, self.currentCard.name): cardEffectString = "hit by the Bang"
		elif self.currentCard.name == INDIANS: cardEffectString = "hit by the Indians"
		elif self.currentCard.name == GATLING: cardEffectString = "hit by the Gatling"
		elif self.currentCard.name == DUELLO: cardEffectString = "defeated in the Duello"
		elif self.currentCard.name == DYNAMITE: cardEffectString = "hit by the exploding dynamite and lost 3 lives"
		else:
			utils.logError("{} shouldn't be able to lose a life with {} as the current card being played.".format(player.getLogString(), self.currentCard.name))
			return []

		# Meaning the player is taking damage from dynamite.
		if damage == 3:
			self.discardCard(player, self.getDynamiteCard())
			emitTuples.append(utils.createDiscardTuple(self.getDynamiteCard()))
			emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

		# Meaning the player is taking damage from an attacking card.
		else:
			attacker = attacker if attacker != None else self.playerOrder[0]

		if not player.isAlive():
			requiredBirras = abs(player.lives) + 1
			birrasInHand = player.getCardTypeFromHand(BIRRA)
			if len(birrasInHand) < requiredBirras: # Without enough Birras, the player is eliminated.
				aliveCount = len(self.getAlivePlayers())
				isGameOverResult = self.isGameOver()
				if isGameOverResult != '':
					emitTuples.extend(utils.createInfoTuples(isGameOverResult, header="Game Over"))

				else: # Emit message to everybody that the player died.
					deadPlayerText = "You were {}!! You've been eliminated! Better luck next time :(".format(cardEffectString)
					otherPlayersText = "{} was {} and has been eliminated! There are now {} players left.".format(player.username, cardEffectString, aliveCount)
					
					emitTuples.extend(utils.createInfoTuples(deadPlayerText, header="Your Game Is Over!", recipients=[player]))
					emitTuples.extend(utils.createInfoTuples(otherPlayersText, recipients=opponents))
					if player == self.playerOrder[0]:
						emitTuples.append((END_YOUR_TURN, dict(), player))

					# Discard Dynamite first if applicable.
					game.discardPile.extend([c for c in player.specialCards if c.name == DYNAMITE])
					player.specialCards = [c for c in player.specialCards if c.name != DYNAMITE]

					# If Vulture Sam is one of the game's other characters and is still alive, use his special ability.
					vultureSam = utils.getObjectFromList(lambda p: p.character.name == VULTURE_SAM, self.getAlivePlayers())
					if vultureSam != None and player != VULTURE_SAM:
						vultureSam.cardsInHand.extend(player.cardsInHand)
						vultureSam.cardsInHand.extend(player.cardsInPlay)
						vultureSam.cardsInHand.extend(player.specialCards)
						
						emitTuples.append(SLEEP, 1, None)
						emitTuples.extend(utils.createInfoTuples("All of {}'s cards were added to your hand!".format(player.username), recipients=[vultureSam]))
						emitTuples.append(self.appendUpdate("{} got all of {}'s cards because of Vulture Sam's ability.".format(vultureSam.username, player.username)))
						emitTuples.append(utils.createCardCarouselTuple(vultureSam, vultureSam == self.playerOrder[0]))
					
					# Otherwise, just normally discard all of the player's cards.
					else:
						game.discardPile.extend(player.cardsInHand)
						game.discardPile.extend(players.cardsInPlay)
						game.discardPile.extend(player.specialCards)

					player.cardsInHand = []
					player.cardsInPlay = []
					player.specialCards = []

					emitTuples.append(utils.createDiscardTuple(self.getTopDiscardCard()))
					emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

			else: # With enough Birras, the player stays in the game. Play as many as necessary to bring the player back to 1 life.
				player.lives = 1
				for birra in birrasInHand[:requiredBirras]:
					self.discardCard(player, birra)
				emitTuples.append(utils.createDiscardTuple(self.getTopDiscardCard()))
				emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

				# Update the player's info modal and update everyone else's action screen.
				birraString = "a Birra" if requiredBirras == 1 else "{} Birras".format(requiredBirras)

				emitTuples.extend(utils.createInfoTuples("You were {} and almost died, but were saved by {}!".format(cardEffectString, birraString), recipients=[player]))
				emitTuples.append(self.appendUpdate("{} was {} but stayed alive by playing {}.".format(player.username, cardEffectString, birraString)))

				if attacker != None:
					emitTuples.extend(utils.createInfoTuples("{} took the hit but stayed alive by playing {}.".format(player.username, birraString), recipients=[attacker]))

				utils.logGameplay("{} played {}".format(player.username, birraString))

		else:
			text = "You were {}, so you've lost {}{} You're down to {} now.".format(cardEffectString, lostLivesString, "!" if "lives" in lostLivesString else ".", player.lives)
			emitTuples.extend(utils.createInfoTuples(text, recipients=[player]))

			if attacker != None:
				emitTuples.extend(utils.createInfoTuples("{} took the hit and is down to {} now.".format(player.username, "{} {}".format(player.lives, "lives" if player.lives > 1 else "life")), recipients=[attacker]))

			updateText = "{} was {}.".format(player.username, cardEffectString)
			emitTuples.append(self.appendUpdate(updateText))

		# If the player is still alive and has a character ability triggered by taking damage, process that here.
		if player.isAlive():
			if player.character.name == BART_CASSIDY: # Bart Cassidy draws a new card for every life point he's lost.
				cardString = "a card" if damage == 1 else "{} cards".format(damage)
				utils.logGameplay("{} drawing {} because they {}".format(player.getLogString(), cardString, lostLivesString))
				
				self.drawCardsForPlayer(player, damage)

				emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
				emitTuples.extend(utils.createInfoTuples("You drew {} because you lost {}!".format(cardString, lostLivesString), recipients=[player]))
				emitTuples.append(self.appendUpdate("{} drew {} using Bart Cassidy's ability because they lost {}.".format(player.username, cardString, lostLivesString)))

			elif player.character.name == EL_GRINGO and self.playerOrder[0] != player and attacker != None: # El Gringo draws a card from the player's hand anytime a player deals him damage.
				if len(attacker.cardsInHand) > 0:
					utils.logGameplay("{} stealing from the hand of {} for dealing him damage.".format(player.getLogString, attacker.getLogString()))
					
					stolenCard = attacker.panico()
					player.addCardToHand(stolenCard)
					emitTuples.extend(utils.createInfoTuples("You stole {} from {}'s hand because they made you lose a life!".format(stolenCard.getDeterminerString(), attacker.username), recipients=[player]))
					emitTuples.extend(utils.createInfoTuples("{} stole {} from your hand because you made them lose a life!".format(player.username, stolenCard.getDeterminerString()), recipients=[attacker]))
					emitTuples.append(self.appendUpdate("{} stole a card from {}'s hand using El Gringo's ability.".format(player.username, attacker.username)))
					emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))
					emitTuples.append(utils.createCardCarouselTuple(attacker, attacker == self.playerOrder[0]))
				else:
					emitTuples.extend(utils.createInfoTuples("{} has no cards, so you couldn't use El Gringo's ability to steal anything.".format(attacker.username), recipients=[player]))

		emitTuples.append(utils.createPlayerInfoListTuple(self.playerOrder)) # Update each player's information on everyone's screen.

		# Only reset the current card once its effects are finished, i.e. once every player has responded to all questions on how to react.
		if len(self.unansweredQuestions) == 0:
			self.currentCard = None
		
		utils.logGameplay("Processed {} losing {}. Will return the following emitTuples: {}.".format(player.username, lostLivesString, [(t[0], t[2] if len(t)==3 else 'everybody') for t in emitTuples]))
		return emitTuples

	def isGameOver(self):
		alivePlayers = self.getAlivePlayers()
		sheriffIsAlive = self.players[self.sheriffUsername].isAlive()
		renegadeIsAlive = any([p.role == RENEGADE for p in alivePlayers])
		aliveOutlaws = len([p for p in alivePlayers if p.role == OUTLAW])

		if not sheriffIsAlive:
			if renegadeIsAlive and len(alivePlayers) == 1: return "The Renegade has won the game!"
			else: return "The Outlaws have won the game!"
		else:
			if not renegadeIsAlive and len(aliveOutlaws) == 0:
				return "The Sheriff and his Deputies have won the game!"
			else:
				return '' # Indicates the game is not over.

	# Function to handle responses for the character abilities that require a question.
	def processAbilityQuestionResponse(self, username, question, answer):
		emitTuples = []
		player = self.players[username]

		utils.logGameplay("Beginning to process ability question response for {}.".format(player.getLogString()))

		if player.character.name == JESSE_JONES:
			if question == QUESTION_JESSE_JONES:
				if answer == FROM_ANOTHER_PLAYER:
					playersToDrawFrom = self.getPlayersWithCardsInHand(username)
					if len(playersToDrawFrom) > 1:
						emitTuples.append(self.addQuestion(player, QUESTION_WHOSE_HAND, [p.username for p in playersToDrawFrom]))
					
					# There's only 1 player Jesse Jones can draw from, so automatically draw from that player's hand.
					else:
						emitTuples.extend(self.processJesseJonesDrawingFromPlayer(playersToDrawFrom[0].username, automatic=True))

				elif answer == FROM_THE_DECK:
					cardsDrawn = self.drawCardsForPlayerTurn(player)
					description = "You drew {} from the deck.".format(utils.convertCardsDrawnToString(cardsDrawn))
					self.drawingToStartTurn = False
					
					emitTuples.append(utils.createCardsDrawnTuple(player, description, cardsDrawn))
					emitTuples.append(utils.createCardCarouselTuple(player, True))
					emitTuples.append(self.appendUpdate(DREW_2_CARDS.format(username)))

			# If not the initial question, this must be answering which player to draw from.
			else:
				if answer in self.players:
					emitTuples.extend(self.processJesseJonesDrawingFromPlayer(answer))

				else:
					utils.logError("Option of \"{}\" was selected by {} for \"{}\", which doesn't match any expected options.".format(answer, player.getLogString(), question))
					self.drawingToStartTurn = False
					return []

		elif player.character.name == KIT_CARLSON: # Answer should be the card he wants to put back on the deck.
			cardName, value, suit = utils.getReverseFormat(QUESTION_CARD_FORMAT, answer)
			cardName = utils.convertDisplayNameToRaw(cardName)

			discardedCard = [c for c in player.cardsInHand[-3:] if c.name == cardName and c.value == value and c.suit == suit][0] # Can't use utils function for a unique card because there may be overlapping name-suit pairs.
			player.getRidOfCard(discardedCard)
			self.drawPile.append(discardedCard)

			description = "You drew {} and put {} back on the draw pile.".format(utils.convertCardsDrawnToString(player.cardsInHand[-2:]), discardedCard.getDeterminerString())
			emitTuples.append(utils.createCardsDrawnTuple(player, description, player.cardsInHand[-2:]))
			emitTuples.append(utils.createCardCarouselTuple(player, True))
			emitTuples.append(self.appendUpdate(DREW_2_CARDS.format(username)))

			self.drawingToStartTurn = False
			
		elif player.character.name == PEDRO_RAMIREZ:
			if answer in [FROM_DISCARD, FROM_THE_DECK]:
				cardsDrawn = self.drawCardsForPlayerTurn(player, extraInfo=('' if answer == FROM_THE_DECK else FROM_DISCARD))
				if answer == FROM_DISCARD:
					description = "You drew {} from the discard pile and {} from the deck.".format(cardsDrawn[-2].getDeterminerString(), cardsDrawn[-1].getDeterminerString())
					emitTuples.append(self.appendUpdate("{} drew {} from the discard pile and 1 card from the deck.".format(cardsDrawn[-2].getDeterminerString(), username)))
					emitTuples.append(utils.createDiscardTuple(self.getTopDiscardCard()))
				else:
					description = "You drew {} from the deck.".format(utils.convertCardsDrawnToString(cardsDrawn))
					emitTuples.append(self.appendUpdate(DREW_2_CARDS.format(username)))

				self.drawingToStartTurn = False

				emitTuples.append(utils.createCardsDrawnTuple(player, description, player.cardsInHand[-2:]))
				emitTuples.append(utils.createCardCarouselTuple(player, True))

			else:
				utils.logError("Option of \"{}\" was selected by {}, which doesn't match any expected options.".format(answer, player.getLogString()))
				self.drawingToStartTurn = False
				return []

		elif player.character.name == LUCKY_DUKE:
			cardName, value, suit = utils.getReverseFormat(QUESTION_CARD_FORMAT, answer)
			cardName = utils.convertDisplayNameToRaw(cardName)
			
			# Both cards get discarded, but we force the one that Lucky Duke picked to get discarded second so it's on top.
			if (cardName, value, suit) in [(c.name, c.value, c.suit) for c in self.drawPile[-2:]]:
				if (cardName, value, suit) == (self.drawPile[-1].name, self.drawPile[-1].value, self.drawPile[-1].suit):
					cardDrawn = self.drawPile[-1]
					self.discardPile.append(self.drawPile.pop(-2))
				else:
					cardDrawn = self.drawPile[-2]
					self.discardPile.append(self.drawPile.pop(-1))

				if self.currentCard.name == DYNAMITE:
					emitTuples.extend(self.processDynamiteDraw(player, cardDrawn))
					if player.isAlive() and player.jailStatus == 1:
						self.currentCard = utils.getObjectFromList(lambda card: card.name == PRIGIONE, player.specialCards)
						emitTuples.append((SLEEP, 1, None))
						emitTuples.append(self.createLuckyDukeTuple(player))
				elif self.currentCard.name == PRIGIONE: emitTuples.extend(self.processPrigioneDraw(player))
				elif self.currentCard.name in [BANG, GATLING]: emitTuples.extend(self.processBarileDraw(player))
				else:
					utils.logError("Lucky Duke ({}) shouldn't be doing \"draw!\" when the current card is {}.".format(player.username, self.currentCard.name))

			else:
				utils.logError("Lucky Duke picked a card ({}, {}) for \"draw!\" that shouldn't be an option.".format(cardName, suit))

		utils.logGameplay("processAbilityQuestionResponse() for ({}, {}, {}) tuples: {}".format(username, question, answer, emitTuples))
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

		if self.currentCard.name == DUELLO:
			emitTuples = self.processDuelloResponse(player, card=selectedCard)

		elif self.currentCard.name in [BANG, GATLING] or (currentPlayer.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO):
			self.discardCard(player, selectedCard)
			effectiveName = utils.convertRawNameToDisplay(GATLING if self.currentCard.name == GATLING else BANG)
			if (currentPlayer.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO):
				effectiveName = MANCATO_AS_BANG
			effectiveReactionDisplayName = "Mancato" if (player.character.name != CALAMITY_JANET or selectedCard.name != BANG) else BANG_AS_MANCATO

			emitTuples = utils.createInfoTuples("{} played a {} to avoid your {}!".format(player.username, effectiveReactionDisplayName, effectiveName), recipients=[currentPlayer])
			emitTuples.append(self.appendUpdate("{} played a {} and avoided {}'s {}.".format(player.username, effectiveReactionDisplayName, currentPlayer.username, effectiveName)))
			emitTuples.append(utils.createCardCarouselTuple(player, False))
			emitTuples.append(utils.createDiscardTuple(selectedCard))

			if len(self.unansweredQuestions) == 0:
				self.currentCard = None

		elif self.currentCard.name == INDIANS:
			self.discardCard(player, selectedCard)
			effectiveReactionDisplayName = "Bang" if (player.character.name != CALAMITY_JANET or selectedCard.name != MANCATO) else MANCATO_AS_BANG
			
			emitTuples = utils.createInfoTuples("{} played a {} to avoid your Indians!".format(player.username, effectiveReactionDisplayName), recipients=[currentPlayer])
			emitTuples.append(self.appendUpdate("{} played a {} and avoided {}'s Indians.".format(player.username, effectiveReactionDisplayName, currentPlayer.username)))
			emitTuples.append(utils.createCardCarouselTuple(player, False))
			emitTuples.append(utils.createDiscardTuple(selectedCard))

			if len(self.unansweredQuestions) == 0:
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

		self.emporioOptions.remove(card)
		player.addCardToHand(card)

		emitTuples = [self.appendUpdate(PICKED_UP_FROM_EMPORIO.format(username, card.getDeterminerString()))]
		emitTuples.append(utils.createCardCarouselTuple(player, player == self.playerOrder[0]))

		nextPlayer = self.getAlivePlayers()[self.getAlivePlayers().index(player) + 1] # Should never be possible to get an index error here.
		
		if len(self.emporioOptions) == 1:
			card = self.emporioOptions.pop()
			nextPlayer.addCardToHand(card)
			emitTuples.append(utils.createCardCarouselTuple(nextPlayer, nextPlayer == self.playerOrder[0]))
			emitTuples.append(self.appendUpdate(PICKED_UP_FROM_EMPORIO.format(nextPlayer.username, card.getDeterminerString())))
			emitTuples.extend(utils.createInfoTuples("You picked up the last Emporio card:", recipients=[nextPlayer], cards=[card]))
			emitTuples.extend(utils.createInfoTuples("Everyone is done picking an Emporio card.", recipients=[p for p in self.getAlivePlayers() if p != nextPlayer]))

			self.currentCard = None
		
		elif len({card.name for card in self.emporioOptions}) == 1: # Every remaining card is the same, so just distribute them automatically.
			emitTuples.extend(utils.createInfoTuples("Everyone is done picking an Emporio card.", recipients=[p for p in self.getAlivePlayers()[:self.getAlivePlayers().index(player) + 1]]))
			emitTuples.extend(self.processEmporioAutomatic(nextPlayer))
		
		else:
			emitTuples.extend(utils.createEmporioTuples(self.playerOrder, self.emporioOptions, nextPlayer))

		return emitTuples

	def processEmporioAutomatic(self, nextPlayer):
		emitTuples = []
		playerIndex = self.getAlivePlayers().index(nextPlayer)

		while self.emporioOptions:
			card = self.emporioOptions.pop()
			nextPlayer.addCardToHand(card)

			emitTuples.append(utils.createCardCarouselTuple(nextPlayer, nextPlayer == self.playerOrder[0]))
			emitTuples.append(self.appendUpdate(PICKED_UP_FROM_EMPORIO.format(nextPlayer.username, card.getDeterminerString())))
			emitTuples.extend(utils.createInfoTuples("You automatically picked up {} from Emporio since all the cards left were the same.".format(card.getDeterminerString()), recipients=[nextPlayer], cards=[card]))
			
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

		if cardIndex == 0 and len(player.cardsInPlay) == 2: # If need be, flip the order of the player's in-play cards to keep them in the same position.
			player.cardsInPlay = player.cardsInPlay[::-1]
		
		emitTuples.append(utils.createCardCarouselTuple(player, True))
		emitTuples.append(utils.createCardsInPlayTuple(player))
		emitTuples.append(utils.createDiscardTuple(cardToReplace))
		emitTuples.append(self.appendUpdate("{} discarded the {} and put {} in play.".format(player.username, cardToReplace.getDisplayName(), self.currentCard.getDeterminerString())))

		self.currentCard = None

		return emitTuples

	def getPlayersWithCardsInHand(self, usernameToExclude=''):
		# If usernameToExclude has the default empty value, this will just check everybody.
		players = [p for p in self.playerOrder if p.username != usernameToExclude and len(p.cardsInHand) > 0]
		utils.logGameplay("Players with cards in hand{}: {}".format(" (excluding {})".format(usernameToExclude) if usernameToExclude else "", [p.username for p in players]))
		return players

	def getQuestionModalWithAliveOpponents(self, player, question):
		aliveOpponents = self.getAliveOpponents(player.username)

		return self.addQuestion(player, question, [p.username for p in aliveOpponents])

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
			emitTuples.extend(self.processDynamiteDraw(player))
			emitTuples.append((SLEEP, 1, None))

		if player.isAlive() and player.jailStatus == 1:
			self.currentCard = utils.getObjectFromList(lambda card: card.name == PRIGIONE, player.specialCards)
			emitTuples.extend(self.processPrigioneDraw(player))

		return emitTuples

	def processDynamiteDraw(self, player, drawnCard=None):
		drawnCard = drawnCard if drawnCard != None else self.drawAndDiscardOneCard()
		emitTuples = [utils.createDiscardTuple(self.getTopDiscardCard())]

		if drawnCard.suit == SPADE and '2' <= drawnCard.value <= '9': # Can't compare ints b/c of face-card values.
			utils.logGameplay("The dynamite exploded on {}.".format(player.getLogString()))
			return self.processPlayerTakingDamage(player, 3)
		else:
			utils.logGameplay("The dynamite didn't explode on {}.".format(player.getLogString()))
			nextPlayer = self.advanceDynamite()
			emitTuples = utils.createInfoTuples("Phew! You survived the dynamite!", recipients=[player])
			emitTuples.extend(utils.createInfoTuples("{} survived the dynamite, so you'll have it next turn!".format(player.username), recipients=[nextPlayer]))
			emitTuples.append(self.appendUpdate("{} survived the dynamite, so now it moves on to {}.".format(player.username, nextPlayer.username)))

		return emitTuples

	def processPrigioneDraw(self, player, drawnCard=None):
		drawnCard = drawnCard if drawnCard != None else self.drawAndDiscardOneCard()
		emitTuples = [utils.createDiscardTuple(self.getTopDiscardCard())]

		if drawnCard.suit == HEART:
			utils.logGameplay("{} drew a heart for Prigione, so s/he gets out of jail and will play this turn.".format(player.getLogString()))
			self.jailStatus = 0
			player.specialCards = [c for c in player.specialCards if c.name != JAIL]
			emitTuples = utils.createInfoTuples("You drew a heart, so you got out of jail!", recipients=[player])
			emitTuples.append(self.appendUpdate("{} drew a heart, so they get to play this turn.".format(player.username)))
		else:
			utils.logGameplay("{} didn't draw a heart for Prigione, so s/he stays in jail and will not play this turn.".format(player.getLogString()))
			emitTuples = utils.createInfoTuples("You drew a {}, so you're stuck in jail for this turn!".format(drawnCard.suit), recipients=[player])
			emitTuples.append(self.appendUpdate("{} drew a {}, so they're stuck in jail for this turn.".format(player.username, drawnCard.suit)))
			emitTuples.append((SLEEP, 0.5, None))

		self.currentCard = None

		return emitTuples

	# Function to process "draw!" for Barile when a player is shot at.
	def processBarileDraw(self, player):
		emitTuples = []
		jourdonnaisTriedTwice = False

		drawnCard = self.drawAndDiscardOneCard()
		currentPlayer = self.playerOrder[0]

		utils.logGameplay("Processing barile draw for {} against {}: {}.".format(player.getLogString(), self.currentCard.getDeterminerString(), drawnCard.suit))

		# If he needs it and can do so, draw a 2nd card for Jourdonnais.
		if player.character.name == JOURDONNAIS and player.countBariles() == 2 and drawnCard.suit != HEART:
			jourdonnaisTriedTwice = True
			drawnCard = self.drawAndDiscardOneCard()

		effectiveDisplayName = self.currentCard.getDisplayName()
		if player.character.name == CALAMITY_JANET and self.currentCard.name == MANCATO:
			effectiveDisplayName = MANCATO_AS_BANG

		if currentPlayer.character.name != SLAB_THE_KILLER or self.currentCard.name != BANG:
			if drawnCard.suit == HEART:
				utils.logGameplay("{} drew a heart and will avoid the {}".format(player.getLogString(), effectiveDisplayName))
				emitTuples = utils.createInfoTuples("You drew a heart for Barile {}and avoided the {}!".format("on your second card " if jourdonnaisTriedTwice else "", effectiveDisplayName), recipients=[player])
				emitTuples.extend(utils.createInfoTuples("{} drew a heart for Barile and avoided your {}!".format(player.username, effectiveDisplayName), recipients=[currentPlayer]))
				emitTuples.append(self.appendUpdate("{} drew a heart for Barile and avoided {}'s {}.".format(player.username, currentPlayer.username, effectiveDisplayName)))
			else:
				utils.logGameplay("{} didn't draw a heart for Barile against the {}".format(player.getLogString(), effectiveDisplayName))
				emitTuples = [self.appendUpdate("{} tried to avoid the {} with a Barile but didn't draw a heart{}.".format(player.username, effectiveDisplayName, " either time" if jourdonnaisTriedTwice else ""))]
				
				# The Barile wasn't a heart, so check if a Mancato can still be played to avoid the attack.
				emitTuples.append(utils.createWaitingModalTuple(currentPlayer, "Waiting for {} to decide how to react to {} after not drawing a Heart for Barile...".format(player.username, self.currentCard.getDisplayName())))
				if len(player.getCardTypeFromHand(MANCATO)) > 0:
					emitTuples.append(self.addQuestion(player, QUESTION_BARILE_MANCATO, [PLAY_A_MANCATO, LOSE_A_LIFE]))
				else:
					emitTuples.append((SLEEP, 1, None))
					emitTuples.extend(processPlayerTakingDamage(player, attacker=currentPlayer))
		
		# Handle the case where Slab the Killer used a Bang, so either 1 or 2 Mancatos still need to be played.
		else:
			mancatosInHand = player.getCardTypeFromHand(MANCATO)

			emitTuples.append(utils.createWaitingModalTuple(currentPlayer, "Waiting for {} to decide how to react to Bang after {}drawing a Heart for Barile...".format(player.username, "not " if drawnCard.suit != HEART else "")))

			if drawnCard.suit == HEART:
				utils.logGameplay("{} drew a heart but still needs to play a Mancato to avoid the Bang".format(player.getLogString()))
				emitTuples.append(self.appendUpdate("{} drew a heart for Barile.".format(player.username)))
				requiredMancatos = 1
			else:
				utils.logGameplay("{} didn't draw a heart, so they stil need to play 2 Mancatos to avoid the Bang".format(player.getLogString()))
				emitTuples.append(self.appendUpdate("{} didn't draw a heart{}.".format(player.username, " either time" if jourdonnaisTriedTwice else "")))
				requiredMancatos = 2
			
			if len(mancatosInHand) >= requiredMancatos:
				emitTuples.append(self.addQuestion(player, QUESTION_SLAB_BARILE_ONE if requiredMancatos == 1 else QUESTION_SLAB_BARILE_TWO, [PLAY_A_MANCATO if requiredMancatos == 1 else PLAY_TWO_MANCATOS, LOSE_A_LIFE]))
			else:
				emitTuples.append((SLEEP, 1, None))
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

		emitTuples = [self.appendUpdate("{} played {}{}.".format(player.username, effectiveDisplayName, '' if cardName != BANG else ' against {}'.format(target.username)))]
		currentCard = self.currentCard

		if cardName == BANG:
			self.bangedThisTurn = True

		for opp in opponents:
			self.currentCard = currentCard # Resetting this is necessary for the case where more than 1 opponent takes damage.
			
			# Trying Bariles first.
			if cardName in [BANG, GATLING] and opp.countBariles() > 0:
				if opp.character.name == LUCKY_DUKE:
					emitTuples.append(self.createLuckyDukeTuple(opp))
					emitTuples.append(utils.createWaitingModalTuple(player, "Waiting for {} (Lucky Duke) to choose a card for \"draw!\"...".format(player.username)))
				else:
					emitTuples.extend(self.processBarileDraw(opp))
			
			# Then giving the option of playing a Mancato/Bang in response.
			elif len(opp.getCardTypeFromHand(requiredCard)) >= (2 if cardName == BANG and player.character.name == SLAB_THE_KILLER else 1):
				if cardName == BANG and player.character.name == SLAB_THE_KILLER:
					option = PLAY_TWO_MANCATOS
				
				emitTuples.append(self.addQuestion(opp, question, [option, LOSE_A_LIFE]))
				emitTuples.append(utils.createWaitingModalTuple(player, "Waiting for {} to decide how to react to {}...".format(opp.username, utils.convertRawNameToDisplay(cardName))))
			
			# Otherwise, there's no choice but to take the damage.
			else:
				emitTuples.extend(self.processPlayerTakingDamage(opp, attacker=player))

		self.currentCard = None if len(self.unansweredQuestions) == 0 else currentCard

		utils.logGameplay("Processed {} playing {}. Returning the following tuples: {}".format(player.getLogString(), cardName, emitTuples))
		return emitTuples

	def createLuckyDukeTuple(self, player):
		options = [self.drawOneCard(), self.drawOneCard()]
		self.drawPile += options # Re-insert these cards into the draw pile because they'll get re-drawn and properly discarded after receiving Lucky Duke's selection.
		return self.addQuestion(player, QUESTION_LUCKY_DUKE.format(self.currentCard.getDisplayName()), [c.getQuestionString() for c in options])

	def processJesseJonesDrawingFromPlayer(self, opponentName, automatic=False):
		emitTuples = []
		currentPlayer = self.playerOrder[0]
		opponent = self.players[opponentName]
		cardsDrawn = self.drawCardsForPlayerTurn(currentPlayer, opponentName)
		stolenCard = cardsDrawn[0]
		description = "You {}drew {} from {}'s hand and {} from the deck.".format("automatically " if automatic else "", stolenCard.getDeterminerString(), opponentName, cardsDrawn[1].getDeterminerString())
		self.drawingToStartTurn = False
		
		emitTuples.append(utils.createCardsDrawnTuple(currentPlayer, description, cardsDrawn))
		emitTuples.append(utils.createCardCarouselTuple(currentPlayer, True))
		emitTuples.append(utils.createCardCarouselTuple(opponent, False))
		emitTuples.extend(utils.createInfoTuples("{} drew {} from your hand using Jesse Jones's ability!".format(currentPlayer.username, stolenCard.getDeterminerString()), recipients=[opponent]))
		emitTuples.append(self.appendUpdate("{} drew a card from {}'s hand using Jesse Jones's ability.".format(currentPlayer.username, opponentName)))

		return emitTuples

	def renderPlayPageForPlayer(self, player):
		utils.logGameplay("Rendering playing page for {}.".format(player.username))
		return render_template('play.html',
			player=player,
			cardsInHandTemplate=utils.getCardsInHandTemplate(player, player.username == self.getCurrentPlayerName()),
			cardsInPlayTemplate=utils.getCardsInPlayTemplate(player),
			playerInfoList=self.playerOrder,
			playerInfoListTemplate=utils.getPlayerInfoListTemplate(self.playerOrder),
			discardUidString='' if len(self.discardPile) == 0 else str(self.getTopDiscardCard().uid))
		
def loadCards():
	cardList = list()
	with open(utils.getLocalFilePath("./static/json/cards.json")) as p:
		cardDict = json.load(p)
		uid = 1

		for cardName in cardDict:
			for suitValue in cardDict[cardName]['suitValues']:
				t = cardDict[cardName]['cardtype']
				if t == GUN_CARD:
					cardList.append(GunCard(cardName, uid, GUN_CARD, cardDict[cardName]['requiresTarget'], cardDict[cardName]['range'], suitValue))
				else:
					cardList.append(Card(cardName, uid, t, cardDict[cardName]['requiresTarget'], suitValue))
				
				uid += 1

	return cardList

def loadCharacters(includeExtras=False):
	filePaths = [utils.getLocalFilePath("static/json/characters.json")]
	if includeExtras:
		filePaths.append(utils.getLocalFilePath("static/json/characters_extra.json"))

	characterList = list()
	for filePath in filePaths:
		with open(filePath) as p:
			characterDict = json.load(p)
			characterList.extend([Character(**characterDict[c]) for c in characterDict]) # Load the JSON directly into Character objects.

	return characterList