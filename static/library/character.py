class Character(dict):
	def __init__(self, name, numLives, ability):
		self.name = name
		self.numLives = numLives
		self.ability = ability

		dict.__init__(self)

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return str(vars(self))

	def __eq__(self, other):
		if not isinstance(other, Character):
			return False

		return self.name == other.name

	def __ne__(self, other):
		if not isinstance(other, Character):
			return True

		return self.name != other.name