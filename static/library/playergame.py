from constants import *
import random
import utils

class PlayerGame(dict):
	def __init__(self, username=None):
		self.username = username
		self.sid = None
		self.role = None
		self.character = None
		self.characterOptions = None
		self.lives = None
		self.lifeLimit = None
		self.jailStatus = 0 # 0 = not jailed, 1 = has the card but hasn't drawn for it yet
		self.cardsInHand = list()
		self.cardsInPlay = list()
		self.specialCards = list()

		dict.__init__(self)

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return str(self.username)

	def __eq__(self, other):
		if not isinstance(other, PlayerGame):
			return False

		return self.username == other.username

	def __ne__(self, other):
		if not isinstance(other, PlayerGame):
			return True

		return self.username != other.username

	# def __ne__(self, other):
	# 	return (other is None) or self.username != other.username

	def addCardToHand(self, card):
		utils.logPlayer("addCardToHand(): {} adding {} ({}) to hand.".format(self.username, card.getDeterminerString(), card.uid))
		self.cardsInHand.append(card)

	def addCardToInPlay(self, card):
		utils.logPlayer("addCardToInPlay(): {} putting {} ({}) in play.".format(self.username, card.getDeterminerString(), card.uid))
		self.cardsInPlay.append(card)

	def getRidOfCard(self, card):
		for cardList in [self.cardsInHand, self.cardsInPlay, self.specialCards]:
			if card in cardList:
				utils.logPlayer("getRidOfCard(): {} discarding card {}.".format(self.username, card.uid))
				cardList.remove(card)
				return

		utils.logError("getRidOfCard(): Failed to discard card {} for {}.".format(card.uid, self.username))

	def getCardTypeFromHand(self, cardName):
		cards = [c for c in self.cardsInHand if c.name == cardName]

		if self.character.name == CALAMITY_JANET and cardName in [BANG, MANCATO]:
			cards += [c for c in self.cardsInHand if c.name == (MANCATO if cardName == BANG else BANG)]

		return cards

	def isAlive(self):
		return self.lives > 0

	def countBariles(self):
		amount = self.getBlueCardAmounts(BARILE, JOURDONNAIS)
		utils.logPlayer("countBariles(): {} has a barile amount of {}.".format(self.username, amount))
		return amount

	def getMustangDistance(self): # Others view you at distance +1.
		amount = self.getBlueCardAmounts(MUSTANG, PAUL_REGRET)
		utils.logPlayer("getMustangDistance(): {} has a mustang amount of {}.".format(self.username, amount))
		return amount

	def getScopeDistance(self): # You view others at distance -1.
		amount = self.getBlueCardAmounts(SCOPE, ROSE_DOOLAN)
		utils.logPlayer("getScopeDistance(): {} has a scope amount of {}.".format(self.username, amount))
		return amount

	def hasBangLimit(self):
		return self.character.name != WILLY_THE_KID and not any([c.name == VOLCANIC for c in self.cardsInPlay])

	def getBlueCardAmounts(self, cardName, characterName):
		return (1 if cardName in [c.name for c in self.cardsInPlay] else 0) + (1 if self.character.name == characterName else 0)

	def getGunRange(self):
		# Assuming only 1 gun is allowed in play at a time.
		gun = utils.getObjectFromList(lambda card: card.cardtype == GUN_CARD, self.cardsInPlay)
		
		if gun == None:
			utils.logPlayer("getGunRange(): {} has no gun, so range is 1.".format(self.username))
			return 1 # The default range is 1 for the Colt .45.
		else:
			utils.logPlayer("getGunRange(): {} has {} in play, so range is {}.".format(self.username, gun.getDeterminerString(), gun.range))
			return gun.range

	def gainOneLife(self):
		utils.logPlayer("gainOneLife(): {} going from {} to {} lives.".format(self.username, self.lives, min(self.lives + 1, self.lifeLimit)))
		self.lives = min(self.lives + 1, self.lifeLimit)

	def loseOneLife(self):
		utils.logPlayer("loseOneLife(): {} going from {} to {} lives.".format(self.username, self.lives, self.lives - 1))
		self.lives -= 1

	def getCardsOnTable(self):
		return self.cardsInPlay + self.specialCards

	def countExcessCards(self):
		return max(len(self.cardsInHand) - self.lives, 0)

	def panico(self, card=None): # The card parameter would only be used if a specific card from in-play is being taken.
		if card == None:
			if len(self.cardsInHand) == 0:
				utils.logError("{} is getting Panico'd or Cat Balou'd with no card parameter given, but has no cards in hand.".format(self.username))
				return None

			card = random.choice(self.cardsInHand)
			self.getRidOfCard(card)
			utils.logPlayer("{} ({}) randomly losing {} (UID: {}) from hand.".format(self.character.name, self.username, card.getDeterminerString(), card.uid))
			return card
		
		else:
			self.getRidOfCard(card)
			utils.logPlayer("{} ({}) lost on-the-table {} (UID: {}) because of a Panico/Cat Balou.".format(self.character.name, self.username, card.getDeterminerString(), card.uid))
			return card

	def getLogString(self):
		return "{} ({})".format(self.character.name, self.username)