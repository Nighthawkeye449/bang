from static.library import utils
from static.library.constants import QUESTION_CARD_FORMAT, DYNAMITE
import json

'''
UID mapping:
	1-25 = bang
	26-37 = mancato
	38-41 = panico
	42-47 = birra
	48-49 = emporio
	50-53 = cat balou
	54 = gatling
	55-57 = duello
	58-59 = indians
	60 = saloon
	61-62 = diligenza
	63 = wells fargo
	64-65 = barile
	66 = scope
	67-68 = mustang
	69-71 = prigione
	72 = dynamite
	73-74 = volcanic
	75-77 = schofield
	78 = remington
	79 = rev carabine
	80 = winchester
'''
class Card(dict):
	def __init__(self, name, uid, cardtype, requiresTarget, suitValue):
		self.name = name
		self.uid = uid
		self.cardtype = cardtype
		self.requiresTarget = requiresTarget
		self.value, self.suit = suitValue.split()

		dict.__init__(self)

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return str(vars(self))

	def __eq__(self, other):
		if not isinstance(other, Card):
			return False

		return self.uid == other.uid

	def __ne__(self, other):
		if not isinstance(other, Card):
			return True

		return self.uid != other.uid

	def getDisplayName(self):
		return utils.convertRawNameToDisplay(self.name)

	def getDeterminerString(self):
		if self.name == DYNAMITE:
			return "the Dynamite"
		else:
			return utils.getDeterminerString(self.name)

	def getQuestionString(self):
		return QUESTION_CARD_FORMAT.format(self.getDisplayName(), self.value, self.suit)

class GunCard(Card):
	def __init__(self, name, uid, cardtype, requiresTarget, gunRange, suitValue):
		self.name = name
		self.uid = uid
		self.cardtype = cardtype
		self.requiresTarget = requiresTarget
		self.range = gunRange
		self.value, self.suit = suitValue.split()

		dict.__init__(self)