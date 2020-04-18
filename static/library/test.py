from card import Card, GunCard
from character import Character
from constants import *
from flask import Flask, render_template
from flask_testing import TestCase
from gameplay import Gameplay, loadCards
from html import unescape
from playergame import PlayerGame

import jinjafunctions
import json
import unittest

game = Gameplay()
players = {'A': PlayerGame('A'), 'B': PlayerGame('B'), 'C': PlayerGame('C'), 'D': PlayerGame('D'), 'E': PlayerGame('E'), 'F': PlayerGame('F'), 'G': PlayerGame('G')}
sortedPlayers = [players[username] for username in sorted(players)]

CARD_PLAYED_TUPLES = {UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION}
WAITING_FOR_RESPONSE_TUPLES = {SHOW_QUESTION_MODAL, SHOW_WAITING_MODAL}
BLUR_CARD_TUPLES = {SHOW_INFO_MODAL, BLUR_CARD_SELECTION}
PLAYER_TOOK_DAMAGE_TUPLES = {SHOW_INFO_MODAL, UPDATE_PLAYER_LIST, UPDATE_ACTION}

def setDefaults(uid=None, numPlayers=7):
    global game

    players['A'].role = SHERIFF
    players['A'].character = loadCharacter(SID_KETCHUM)
    players['A'].lives = players['A'].character.num_lives + 1
    players['A'].lifeLimit = players['A'].character.num_lives + 1

    players['B'].role = OUTLAW
    players['B'].character = loadCharacter(SID_KETCHUM)
    players['B'].lives = players['B'].character.num_lives
    players['B'].lifeLimit = players['B'].character.num_lives

    players['C'].role = OUTLAW
    players['C'].character = loadCharacter(SID_KETCHUM)
    players['C'].lives = players['C'].character.num_lives
    players['C'].lifeLimit = players['C'].character.num_lives

    players['D'].role = RENEGADE
    players['D'].character = loadCharacter(SID_KETCHUM)
    players['D'].lives = players['D'].character.num_lives
    players['D'].lifeLimit = players['D'].character.num_lives

    players['E'].role = VICE
    players['E'].character = loadCharacter(SID_KETCHUM)
    players['E'].lives = players['E'].character.num_lives
    players['E'].lifeLimit = players['E'].character.num_lives

    players['F'].role = OUTLAW
    players['F'].character = loadCharacter(SID_KETCHUM)
    players['F'].lives = players['F'].character.num_lives
    players['F'].lifeLimit = players['F'].character.num_lives

    players['G'].role = VICE
    players['G'].character = loadCharacter(SID_KETCHUM)
    players['G'].lives = players['G'].character.num_lives
    players['G'].lifeLimit = players['G'].character.num_lives

    for p in players.values():
        p.cardsInHand = list()
        p.cardsInPlay = list()
        p.specialCards = list()
        p.jailStatus = 0

    alivePlayers = list(sortedPlayers)[:numPlayers]

    game.started = True
    game.preparedForSetup = True
    game.players = {p.username: p for p in alivePlayers}
    game.playerOrder = list(alivePlayers)
    game.currentTurn = 1
    game.sheriffUsername = 'A'
    game.drawingToStartTurn = False
    game.drawPile = list(game.allCards)
    game.discardPile = list()
    game.currentCard = None
    game.discardingCards = False
    game.bangedThisTurn = False
    game.emporioOptions = list()
    game.duelPair = list()
    game.unansweredQuestions = dict()

    if uid != None: self.currentCard = self.getCardByUid(uid)

def loadCharacter(name):
    characterList = list()
    with open(utils.getLocalFilePath("../json/characters.json")) as p:
        characterDict = json.load(p)
        characterList.extend([Character(**characterDict[c]) for c in characterDict])

    return utils.getObjectFromList(lambda c: c.name == name, characterList)

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
def setPlayerCardsInHand(playerCardDict):
    for username in playerCardDict:
        players[username].cardsInHand = [game.getCardByUid(uid) for uid in playerCardDict[username]]

def setPlayerCardsInPlay(playerCardDict):
    for username in playerCardDict:
        players[username].cardsInPlay = [game.getCardByUid(uid) for uid in playerCardDict[username]]

def setPlayerSpecialCards(playerCardDict):
    for username in playerCardDict:
        players[username].specialCards = [game.getCardByUid(uid) for uid in playerCardDict[username]]

def setPlayerLives(playerLifeDict):
    for username in playerLifeDict:
        players[username].lives = playerLifeDict[username]

def setPlayerCharacter(username, character):
    players[username].character = loadCharacter(character)

def getCardsOfASuit(suit, n):
    return [c for c in game.allCards if c.suit == suit][:n]

def getEmitTypes(tuples):
    return {t[0] for t in tuples if t[0] != SLEEP}

def countEmitTypes(tuples, countDict):
    for emitType in countDict:
        if len([t for t in tuples if t[0] == emitType]) != countDict[emitType]:
            return False

    return True

def countEmitTypeToRecipient(tuples, emitType, recipient):
    return len([t for t in tuples if t[0] == emitType and t[2] == recipient])

class TestGameplay(TestCase):

    def create_app(self):
        app = Flask(__name__, template_folder=utils.getLocalFilePath('../../templates'))
        app.config['TESTING'] = True

        # Set to 0 to have the OS pick the port.
        app.config['LIVESERVER_PORT'] = 0

        app.jinja_env.filters['convertNameToPath'] = jinjafunctions.convertNameToPath

        return app




    # ''' Bang tests. '''

    # # Bang against an in-range opponent who has no Mancatos given multiple opponents.
    # def testBang1(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1]})
        
    #     self.assertEqual(game.validateCardChoice('A', 1)[0][0], SHOW_QUESTION_MODAL)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'B')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_PLAYER_LIST})
    #     self.assertTrue(countEmitTypes(tuples, {UPDATE_ACTION: 2}))
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Bang successfully against an in-range opponent who has a Mancato given multiple opponents.
    # def testBang2(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1], 'B': [26]})

    #     game.validateCardChoice('A', 1)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'B')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_QUESTION_MODAL, SHOW_WAITING_MODAL})
    #     self.assertTrue(countEmitTypes(tuples, {SHOW_QUESTION_MODAL: 1, SHOW_WAITING_MODAL: 1, UPDATE_ACTION: 1}))
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_WAITING_MODAL, players['A']), 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_BANG_REACTION.format('A'), LOSE_A_LIFE)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_PLAYER_LIST})
    #     self.assertTrue(countEmitTypes(tuples, {UPDATE_ACTION: 1}))
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Bang successfully against only alive opponent who has no Mancatos.
    # def testBang3(self):
    #     setDefaults(numPlayers=3)
    #     setPlayerCardsInHand({'A': [1]})
    #     setPlayerLives({'B': 0}) # To also test shooting against someone who wasn't initally in range.
        
    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertEqual(getEmitTypes(tuples), CARD_PLAYED_TUPLES | PLAYER_TOOK_DAMAGE_TUPLES)
    #     self.assertTrue(countEmitTypes(tuples, {SHOW_INFO_MODAL: 3}))
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['C']), 1)

    #     self.assertEqual(players['C'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Bang successfully against only alive opponent who has 1 Mancato.
    # def testBang4(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1], 'B': [26]})

    #     game.validateCardChoice('A', 1)
        
    #     tuples = game.processQuestionResponse('B', QUESTION_BANG_REACTION.format('A'), LOSE_A_LIFE)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_PLAYER_LIST})
    #     self.assertTrue(countEmitTypes(tuples, {UPDATE_ACTION: 1}))
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Bang successfully against only alive opponent who has multiple Mancatos.
    # def testBang5(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1], 'B': [26, 27]})

    #     game.validateCardChoice('A', 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_BANG_REACTION.format('A'), LOSE_A_LIFE)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_PLAYER_LIST})
    #     self.assertTrue(countEmitTypes(tuples, {UPDATE_ACTION: 1}))
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Try using Bang twice with the default limit of 1.
    # def testBang6(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1, 2]})

    #     game.validateCardChoice('A', 1)
        
    #     tuples = game.validateCardChoice('A', 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("already played a Bang" in tuples[0][1]['html'])

    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(2)])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Try using Bang against an out-of-range opponent.
    # def testBang7(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1]})

    #     game.validateCardChoice('A', 1)

    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'C')
    #     self.assertEqual(len(tuples), 1)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertTrue("C is out of range" in tuples[0][1]['html'])

    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(1)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertTrue(game.currentCard == None)

    # # Try using Bang when there's nobody in range.
    # def testBang8(self):
    #     setDefaults(numPlayers=3)
    #     setPlayerCardsInHand({'A': [1]})
    #     setPlayerCardsInPlay({'B': [67],'C': [68]})

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertEqual(len(tuples), 1)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertTrue("nobody in range" in tuples[0][1]['html'])

    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(1)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertTrue(game.currentCard == None)




    # ''' Gatling and Indians tests. '''

    # # Gatling and Indians where nobody can avoid it.
    # def testGatlingIndiansWithNobodyAvoiding(self):
    #     for attackingUid in [54, 58]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         opponents = list(players.values())[1:]

    #         tuples = game.validateCardChoice('A', attackingUid)
    #         playerAInfoTexts = [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_PLAYER_LIST, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})
    #         for opponent in opponents:
    #             self.assertTrue(any(["{} took the hit".format(opponent.username) in infoText for infoText in playerAInfoTexts]))
    #             self.assertTrue("you've lost a life" in unescape([t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == opponent][0]))

    #         for opponent in opponents:
    #             self.assertEqual(opponent.lives, 3)

    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid)])
    #         self.assertTrue(game.currentCard == None)

    # # Gatling and Indians where all players can avoid it and all do.
    # def testGatlingIndiansWithEverybodyAvoiding(self):
    #     for attackingUid in [54, 58]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         question = (QUESTION_GATLING_REACTION if attackingUid == 54 else QUESTION_INDIANS_REACTION).format('A')
    #         answer = PLAY_A_MANCATO if attackingUid == 54 else PLAY_A_BANG
    #         cardName = (MANCATO if attackingUid == 54 else BANG).capitalize()
    #         opponents = list(players.values())[1:]

    #         opponentCardUids = [c.uid for c in game.allCards if c.name == cardName.lower()][:len(players) - 1]
    #         for i, opponent in enumerate(opponents):
    #             setPlayerCardsInHand({opponent.username: [opponentCardUids[i]]})

    #         tuples = utils.consolidateTuples(game.validateCardChoice('A', attackingUid))
    #         waitingModalTuple = [t for t in tuples if t[0] == SHOW_WAITING_MODAL][0]
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, SHOW_WAITING_MODAL, SHOW_QUESTION_MODAL, UPDATE_ACTION})
    #         self.assertTrue(countEmitTypes(tuples, {SHOW_WAITING_MODAL: 1}))
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_WAITING_MODAL, players['A']), 1)
    #         self.assertTrue("Waiting for {} players...".format(len(players) - 1) in waitingModalTuple[1]['html'])

    #         for opponent in opponents:
    #             tuples = game.processQuestionResponse(opponent.username, question, answer)
    #             self.assertTrue("You automatically played your only {}".format(cardName) in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == opponent][0])
    #             self.assertTrue("{} played a {} to avoid".format(opponent.username, cardName) in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])

    #         for opponent in opponents:
    #             self.assertEqual(opponent.lives, 4)
    #             self.assertEqual(opponent.cardsInHand, [])

    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid)] + [game.getCardByUid(uid) for uid in opponentCardUids])
    #         self.assertTrue(game.currentCard == None)

    # # Gatling and Indians where all players can avoid it, but only some choose to.
    # def testGatlingIndiansWithSomeAvoiding(self):
    #     for attackingUid in [54, 58]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         question = (QUESTION_GATLING_REACTION if attackingUid == 54 else QUESTION_INDIANS_REACTION).format('A')
    #         answer = PLAY_A_MANCATO if attackingUid == 54 else PLAY_A_BANG
    #         cardName = (GATLING if attackingUid == 54 else INDIANS).capitalize()
    #         opponents = list(players.values())[1:]
    #         numOpponentsAvoiding = 3

    #         opponentCardUids = [c.uid for c in game.allCards if c.name == (MANCATO if attackingUid == 54 else BANG)][:len(players) - 1]
    #         for i, opponent in enumerate(opponents):
    #             setPlayerCardsInHand({opponent.username: [opponentCardUids[i]]})

    #         game.validateCardChoice('A', attackingUid)

    #         for opponent in opponents[:numOpponentsAvoiding]:
    #             game.processQuestionResponse(opponent.username, question, answer)

    #         for opponent in opponents[numOpponentsAvoiding:]:
    #             tuples = game.processQuestionResponse(opponent.username, question, LOSE_A_LIFE)
    #             self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_ACTION, UPDATE_PLAYER_LIST})
    #             self.assertTrue("You were hit by the {}".format(cardName) in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == opponent][0])
    #             self.assertTrue("{} took the hit".format(opponent.username) in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])

    #         for i, opponent in enumerate(opponents):
    #             if i < numOpponentsAvoiding:
    #                 self.assertEqual(opponent.lives, 4)
    #                 self.assertEqual(opponent.cardsInHand, [])
    #             else:
    #                 self.assertEqual(opponent.lives, 3)
    #                 self.assertEqual(opponent.cardsInHand, [game.getCardByUid(opponentCardUids[i])])

    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid)] + [game.getCardByUid(uid) for uid in opponentCardUids[:numOpponentsAvoiding]])
    #         self.assertTrue(game.currentCard == None)

    # # Gatling and Indians where the target has multiple of the required card and needs to pick one.
    # def testGatlingIndiansWithMultipleRequiredCards(self):
    #     for attackingUid in [54, 58]:
    #         setDefaults(numPlayers=2)
    #         requiredCardUids = [26, 27] if attackingUid == 54 else [1, 2]
    #         setPlayerCardsInHand({'A': [attackingUid], 'B': requiredCardUids})
    #         question = (QUESTION_GATLING_REACTION if attackingUid == 54 else QUESTION_INDIANS_REACTION).format('A')
    #         answer = PLAY_A_MANCATO if attackingUid == 54 else PLAY_A_BANG
    #         cardName = (MANCATO if attackingUid == 54 else BANG).capitalize()

    #         game.validateCardChoice('A', attackingUid)

    #         tuples = game.processQuestionResponse('B', question, answer)
    #         self.assertEqual(getEmitTypes(tuples), BLUR_CARD_TUPLES)
    #         self.assertTrue("Click on the card in your hand" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])
    #         self.assertTrue(all([t[2] == players['B'] for t in tuples]))

    #         tuples = game.processBlurCardSelection('B', requiredCardUids[1])
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, SHOW_INFO_MODAL, UPDATE_ACTION})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)
    #         self.assertTrue("B played a {} to avoid".format(cardName) in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])

    #         self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(requiredCardUids[0])])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid), game.getCardByUid(requiredCardUids[1])])
    #         self.assertEqual(game.currentCard, None)




    # ''' Duello tests. '''

    # # Duello where the target is picked from options and has no Bangs.
    # def testDuelloNoBangs(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [55]})

    #     tuples = game.validateCardChoice('A', 55)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_QUESTION_MODAL})
    #     for opponent in [player for player in players.values() if player.username != 'A']:
    #         self.assertTrue(opponent.username in tuples[0][1].values())

    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_DUEL, 'D')
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_PLAYER_LIST, UPDATE_DISCARD_PILE, UPDATE_ACTION})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['D']), 1)

    #     self.assertEqual(players['D'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55)])
    #     self.assertEqual(game.currentCard, None)
        
    # # Duello where the target is the only one left and has no Bangs.
    # def testDuelloOneOpponentWithNoBangs(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [55]})

    #     tuples = game.validateCardChoice('A', 55)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_PLAYER_LIST, UPDATE_DISCARD_PILE, UPDATE_ACTION})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("B took the hit" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55)])
    #     self.assertEqual(game.currentCard, None)

    # # Duello where the target could respond with a Bang but chooses not to play it.
    # def testDuelloOneOpponentWithNoBangs(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [55], 'B': [1]})

    #     tuples = game.validateCardChoice('A', 55)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_QUESTION_MODAL, SHOW_WAITING_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_WAITING_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), LOSE_A_LIFE)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_PLAYER_LIST, UPDATE_ACTION})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("B took the hit" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55)])
    #     self.assertEqual(game.currentCard, None)

    # # Duello where the target has 1 Bang and plays it, and the player has none.
    # def testDuelloWithBangAndOpponentWithoutBang(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [55], 'B': [1]})

    #     tuples = game.validateCardChoice('A', 55)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_QUESTION_MODAL, SHOW_WAITING_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})

    #     tuples = game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_PLAYER_LIST, UPDATE_ACTION, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 2)
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertTrue(any(["A took the hit" in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['A'].lives, 4)
    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55), game.getCardByUid(1)])
    #     self.assertEqual(game.currentCard, None)

    # # Duello where the target has 1 Bang and plays it, and the player has 1 Bang but chooses not to play it.
    # def testDuelloWithBangAndOpponentWithBang(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1, 55], 'B': [2]})

    #     game.validateCardChoice('A', 55)

    #     tuples = game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, SHOW_QUESTION_MODAL, SHOW_WAITING_MODAL, UPDATE_ACTION, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_WAITING_MODAL, players['B']), 1)
    #     self.assertTrue([t[1]['question'] for t in tuples if t[0] == SHOW_QUESTION_MODAL and t[2] == players['A']][0] == QUESTION_DUELLO_BANG_REACTION.format('B'))

    #     tuples = game.processQuestionResponse('A', QUESTION_DUELLO_BANG_REACTION.format('B'), LOSE_A_LIFE)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_ACTION, UPDATE_PLAYER_LIST})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertTrue(any(["A took the hit" in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['A'].lives, 4)
    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(1)])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55), game.getCardByUid(2)])
    #     self.assertEqual(game.currentCard, None)

    # # Duello where the target has 1 Bang and plays it, and the player has 1 Bang and plays it.
    # def testDuelloWithBangAndOpponentWithBang2(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1, 55], 'B': [2]})

    #     game.validateCardChoice('A', 55)

    #     game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), PLAY_A_BANG)

    #     tuples = game.processQuestionResponse('A', QUESTION_DUELLO_BANG_REACTION.format('B'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), PLAYER_TOOK_DAMAGE_TUPLES | CARD_PLAYED_TUPLES)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertTrue(any(["B took the hit" in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]))
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])

    #     self.assertEqual(players['A'].lives, 5)
    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55), game.getCardByUid(2), game.getCardByUid(1)])
    #     self.assertEqual(game.currentCard, None)

    # # Duello where the target and player each have multiple Bangs and the opponent loses by running out first.
    # def testDuelloWhereOpponentRunsOutFirst(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1, 2, 55], 'B': [3, 4]})

    #     game.validateCardChoice('A', 55)

    #     tuples = game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), BLUR_CARD_TUPLES)
    #     self.assertTrue("Click on the card in your hand" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])
    #     self.assertTrue(all([t[2] == players['B'] for t in tuples]))

    #     tuples = game.processBlurCardSelection('B', 3)
    #     self.assertEqual(getEmitTypes(tuples), WAITING_FOR_RESPONSE_TUPLES | CARD_PLAYED_TUPLES)

    #     tuples = game.processQuestionResponse('A', QUESTION_DUELLO_BANG_REACTION.format('B'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), BLUR_CARD_TUPLES)
    #     self.assertTrue("Click on the card in your hand" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertTrue(all([t[2] == players['A'] for t in tuples]))

    #     tuples = game.processBlurCardSelection('A', 1)
    #     self.assertEqual(getEmitTypes(tuples), WAITING_FOR_RESPONSE_TUPLES | CARD_PLAYED_TUPLES)

    #     game.processQuestionResponse('B', QUESTION_DUELLO_BANG_REACTION.format('A'), PLAY_A_BANG)

    #     tuples = game.processQuestionResponse('A', QUESTION_DUELLO_BANG_REACTION.format('B'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), PLAYER_TOOK_DAMAGE_TUPLES | CARD_PLAYED_TUPLES)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertTrue(any(["B took the hit" in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]))
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])

    #     self.assertEqual(players['A'].lives, 5)
    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55), game.getCardByUid(3), game.getCardByUid(1), game.getCardByUid(4), game.getCardByUid(2)])
    #     self.assertEqual(game.currentCard, None)

    # # Duello where the target and player each have multiple Bangs and the player loses by running out first.
    # def testDuelloWherePlayerRunsOutFirst(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [1, 2, 55], 'B': [3, 4, 5]})

    #     game.validateCardChoice('A', 55)

    #     game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), PLAY_A_BANG)
    #     game.processBlurCardSelection('B', 3)

    #     game.processQuestionResponse('A', QUESTION_DUELLO_BANG_REACTION.format('B'), PLAY_A_BANG)
    #     game.processBlurCardSelection('A', 1)

    #     game.processQuestionResponse('B', QUESTION_DUELLO_BANG_REACTION.format('A'), PLAY_A_BANG)
    #     game.processBlurCardSelection('B', 4)

    #     game.processQuestionResponse('A', QUESTION_DUELLO_BANG_REACTION.format('B'), PLAY_A_BANG)
        
    #     tuples = game.processQuestionResponse('B', QUESTION_DUELLO_BANG_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertEqual(getEmitTypes(tuples), PLAYER_TOOK_DAMAGE_TUPLES | CARD_PLAYED_TUPLES)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 2)
    #     self.assertTrue("You were defeated in the Duello" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertTrue(any(["A took the hit" in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['A'].lives, 4)
    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55), game.getCardByUid(3), game.getCardByUid(1), game.getCardByUid(4), game.getCardByUid(2), game.getCardByUid(5)])
    #     self.assertEqual(game.currentCard, None)




    # ''' Mancato tests. '''

    # # Mancato successfully with only one in hand against a Bang and Gatling.
    # def testMancato1(self):
    #     for (attackingUid, question) in [(1, QUESTION_BANG_REACTION), (54, QUESTION_GATLING_REACTION)]:
    #         setDefaults(numPlayers=2)
    #         setPlayerCardsInHand({'A': [attackingUid], 'B': [26]})

    #         game.validateCardChoice('A', attackingUid)

    #         tuples = game.processQuestionResponse('B', question.format('A'), PLAY_A_MANCATO)
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)

    #         self.assertEqual(players['B'].lives, 4)
            
    #         self.assertEqual(players['A'].cardsInHand, [])
    #         self.assertEqual(players['B'].cardsInHand, [])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid), game.getCardByUid(26)])
    #         self.assertTrue(game.currentCard == None)

    # # Mancato successfully with 2+ in hand against a Bang and Gatling.
    # def testMancato2(self):
    #     for (attackingUid, question) in [(1, QUESTION_BANG_REACTION), (54, QUESTION_GATLING_REACTION)]:
    #         setDefaults(numPlayers=2)
    #         setPlayerCardsInHand({'A': [attackingUid], 'B': [26, 27]})

    #         game.validateCardChoice('A', attackingUid)

    #         game.processQuestionResponse('B', question.format('A'), PLAY_A_MANCATO)

    #         tuples = game.processBlurCardSelection('B', 27)
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE})
            
    #         self.assertEqual(players['B'].lives, 4)

    #         self.assertEqual(players['A'].cardsInHand, [])
    #         self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(26)])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid), game.getCardByUid(27)])
    #         self.assertTrue(game.currentCard == None)



    # ''' Birra tests. '''

    # # Try using Birra when already at the life limit.
    # def testBirra1(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [42]})

    #     tuples = game.validateCardChoice('A', 42)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("already have your maximum" in tuples[0][1]['html'])

    #     self.assertEqual(players['A'].lives, 5)
        
    #     self.assertEqual(game.discardPile, [])
    #     self.assertTrue(game.currentCard == None)

    # # Successfully use 1 Birra.
    # def testBirra2(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [42]})
    #     setPlayerLives({'A': 3})

    #     tuples = game.validateCardChoice('A', 42)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_ACTION, UPDATE_DISCARD_PILE, UPDATE_CARD_HAND})
    #     self.assertTrue("A played a Birra" in utils.getObjectFromList(lambda tup: tup[0] == UPDATE_ACTION, tuples)[1]['update'])
        
    #     self.assertEqual(players['A'].lives, 4)
        
    #     self.assertEqual(game.discardPile, [game.getCardByUid(42)])
    #     self.assertTrue(game.currentCard == None)

    # # Successfully use multiple Birras.
    # def testBirra3(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [42, 43]})
    #     setPlayerLives({'A': 2})

    #     game.validateCardChoice('A', 42)
    #     self.assertEqual(players['A'].lives, 3)

    #     game.validateCardChoice('A', 43)
    #     self.assertEqual(players['A'].lives, 4)

    #     self.assertEqual(game.discardPile, [game.getCardByUid(42), game.getCardByUid(43)])
    #     self.assertTrue(game.currentCard == None)

    # # Use Birra when shot dead and only have 1 Birra left.
    # def testBirra4(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1], 'B': [42]})
    #     setPlayerLives({'B': 1})

    #     game.validateCardChoice('A', 1)
    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'B')
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_PLAYER_LIST})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)

    #     self.assertEqual(players['B'].lives, 1)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1), game.getCardByUid(42)])
    #     self.assertTrue(game.currentCard == None)

    # # Use Birra when shot dead and have multiple Birras left.
    # def testBirra5(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1], 'B': [42, 43]})
    #     setPlayerLives({'B': 1})

    #     game.validateCardChoice('A', 1)
    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'B')
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_PLAYER_LIST})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)

    #     self.assertEqual(players['B'].lives, 1)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(43)])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1), game.getCardByUid(42)])
    #     self.assertTrue(game.currentCard == None)

    # # Use multiple Birras when killed by dynamite.
    # def testBirra6(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [42, 43, 44]})
    #     setPlayerLives({'A': 1})
    #     game.currentCard = game.getDynamiteCard()

    #     tuples = game.processPlayerTakingDamage(players['A'], 3)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_PLAYER_LIST})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)

    #     self.assertEqual(players['A'].lives, 1)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getDynamiteCard(), game.getCardByUid(42), game.getCardByUid(43), game.getCardByUid(44)])
    #     self.assertTrue(game.currentCard == None)

    # # Try to use Birra in a 1-on-1.
    # def testBirra7(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCardsInHand({'A': [42]})
    #     setPlayerLives({'A': 3})

    #     tuples = game.validateCardChoice('A', 42)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("can't use Birras when it's 1-v-1" in unescape(tuples[0][1]['html']))

    #     self.assertEqual(players['A'].lives, 3)
        
    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(42)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertTrue(game.currentCard == None)




    # ''' Saloon tests. '''

    # # Everybody has the maximum number of lives.
    # def testSaloon1(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [60]})

    #     tuples = game.validateCardChoice('A', 60)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("nobody would gain a life" in tuples[0][1]['html'])

    #     self.assertTrue(all([p.lives == p.lifeLimit for p in players.values()]))
        
    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(60)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertTrue(game.currentCard == None)

    # # Only the player can gain a life.
    # def testSaloon2(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [60]})
    #     setPlayerLives({'A': 4})

    #     tuples = game.validateCardChoice('A', 60)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})

    #     self.assertTrue(players['A'].lives, 5)
        
    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(60)])
    #     self.assertTrue(game.currentCard == None)

    # # Several players can gain a life, including the player.
    # def testSaloon3(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [60]})
    #     setPlayerLives({'A': 4, 'C': 2, 'F': 1})

    #     tuples = game.validateCardChoice('A', 60)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})

    #     self.assertTrue(players['A'].lives, 5)
    #     self.assertTrue(players['C'].lives, 3)
    #     self.assertTrue(players['F'].lives, 2)
        
    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(60)])
    #     self.assertTrue(game.currentCard == None)

    # # Several players can gain a life, excluding the player.
    # def testSaloon4(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [60]})
    #     setPlayerLives({'B': 3, 'C': 2, 'F': 1})

    #     tuples = game.validateCardChoice('A', 60)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})

    #     self.assertTrue(players['A'].lives, 5)
    #     self.assertTrue(players['B'].lives, 4)
    #     self.assertTrue(players['C'].lives, 3)
    #     self.assertTrue(players['F'].lives, 2)
        
    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(60)])
    #     self.assertTrue(game.currentCard == None)

    # # Everybody can gain a life.
    # def testSaloon5(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [60]})
    #     setPlayerLives({p.username: p.lifeLimit - 1 for p in players.values()})

    #     tuples = game.validateCardChoice('A', 60)
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})

    #     self.assertTrue(all([p.lives == p.lifeLimit for p in players.values()]))
        
    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(60)])
    #     self.assertTrue(game.currentCard == None)




    # # ''' Panico and Cat Balou tests. '''

    # # Successful Panico and Cat Balou against a 1-away player who has 1 card in hand.
    # def testStealInHand1(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid], 'B': [1]})

    #         game.validateCardChoice('A', cardUid)
            
    #         tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 2)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)

    #         self.assertEqual(players['B'].cardsInHand, [])
    #         if cardUid == 38:
    #             self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(1)])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid)])
    #         else:
    #             self.assertEqual(players['A'].cardsInHand, [])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid), game.getCardByUid(1)])

    #         self.assertTrue(game.currentCard == None)

    # # Successful Panico and Cat Balou against a 1-away player who has multiple cards in hand.
    # def testStealInHand2(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid], 'B': [1, 2]})

    #         game.validateCardChoice('A', cardUid)
            
    #         tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 2)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)

    #         cardStolen = game.getCardByUid(1) if players['B'].cardsInHand[0].uid == 2 else game.getCardByUid(2)
    #         cardNotStolen = game.getCardByUid(2) if players['B'].cardsInHand[0].uid == 2 else game.getCardByUid(1)

    #         self.assertEqual(players['B'].cardsInHand, [cardNotStolen])
    #         if cardUid == 38:
    #             self.assertTrue(players['A'].cardsInHand, [cardStolen])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid)])
    #         else:
    #             self.assertEqual(players['A'].cardsInHand, [])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid), cardStolen])

    #         self.assertTrue(game.currentCard == None)

    # # Successful Panico and Cat Balou against a 1-away player who has 1 card in play.
    # def testStealInPlay1(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid]})
    #         setPlayerCardsInPlay({'B': [78]})

    #         game.validateCardChoice('A', cardUid)
            
    #         tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 2)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)

    #         self.assertEqual(players['B'].cardsInPlay, [])
    #         if cardUid == 38:
    #             self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(78)])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid)])
    #         else:
    #             self.assertEqual(players['A'].cardsInHand, [])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid), game.getCardByUid(78)])

    #         self.assertTrue(game.currentCard == None)

    # # Successful Panico and Cat Balou against a 1-away player who has 2 cards in play.
    # def testStealInPlay2(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid]})
    #         setPlayerCardsInPlay({'B': [65, 78]})

    #         game.validateCardChoice('A', cardUid)
            
    #         game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')

    #         discardSet = set() if cardUid == 38 else {UPDATE_DISCARD_PILE}
    #         tuples = game.processQuestionResponse('A', QUESTION_CARD_ON_TABLE.format('B', 'Panico' if cardUid == 38 else 'Cat Balou'), game.getCardByUid(65).getQuestionString())
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL} | discardSet)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)

    #         self.assertEqual(players['B'].cardsInPlay, [game.getCardByUid(78)])
    #         if cardUid == 38:
    #             self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(65)])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid)])
    #         else:
    #             self.assertEqual(players['A'].cardsInHand, [])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid), game.getCardByUid(65)])

    #         self.assertTrue(game.currentCard == None)

    # # Succesful Panico and Cat Balou against a 1-away player who has 2 cards in play and is in jail, taking the jail card.
    # def testStealInPlayAndSpecialCard(self):
    #     self.assertTrue(False)

    # # Successful Panico and Cat Balou against 1-away player who has both a card in hand and in play, taking the card in hand.
    # def testStealInHandAndInPlay1(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid], 'B': [1]})
    #         setPlayerCardsInPlay({'B': [78]})

    #         game.validateCardChoice('A', cardUid)
            
    #         game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')

    #         question = (QUESTION_PANICO_CARDS if cardUid == 38 else QUESTION_CAT_BALOU_CARDS).format('B')
    #         discardSet = set() if cardUid == 38 else {UPDATE_DISCARD_PILE}

    #         tuples = game.processQuestionResponse('A', question, FROM_THEIR_HAND)
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL} | discardSet)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)

    #         self.assertEqual(players['B'].cardsInHand, [])
    #         self.assertEqual(players['B'].cardsInPlay, [game.getCardByUid(78)])
    #         if cardUid == 38:
    #             self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(1)])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid)])
    #         else:
    #             self.assertEqual(players['A'].cardsInHand, [])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid), game.getCardByUid(1)])

    #         self.assertTrue(game.currentCard == None)

    # # Successful Panico and Cat Balou against 1-away player who has both a card in hand and in play, taking the card in play.
    # def testStealInHandAndInPlay2(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid], 'B': [1]})
    #         setPlayerCardsInPlay({'B': [78]})

    #         game.validateCardChoice('A', cardUid)
            
    #         game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')

    #         question = (QUESTION_PANICO_CARDS if cardUid == 38 else QUESTION_CAT_BALOU_CARDS).format('B')
    #         discardSet = set() if cardUid == 38 else {UPDATE_DISCARD_PILE}

    #         tuples = game.processQuestionResponse('A', question, FROM_THE_TABLE)
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL} | discardSet)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)

    #         self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(1)])
    #         self.assertEqual(players['B'].cardsInPlay, [])
    #         if cardUid == 38:
    #             self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(78)])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid)])
    #         else:
    #             self.assertEqual(players['A'].cardsInHand, [])
    #             self.assertEqual(game.discardPile, [game.getCardByUid(cardUid), game.getCardByUid(78)])

    #         self.assertTrue(game.currentCard == None)

    # # Unsuccessful Panico against a 2-away player.
    # def testPanicoNotInRange(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [38], 'B': [1], 'C': [2]})

    #     game.validateCardChoice('A', 38)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'C')
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertTrue("is out of range" in tuples[0][1]['html'])

    #     self.assertTrue(game.currentCard == None)

    # # Successful Cat Balou against a 2-away player.
    # def testCatBalouLongRange(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [50], 'C': [1]})

    #     game.validateCardChoice('A', 50)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'C')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['C']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['C']), 1)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['C'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(50), game.getCardByUid(1)])
    #     self.assertTrue(game.currentCard == None)

    # # Unsuccessful Panico and Cat Balou when all opponents are card-less.
    # def testStealNobodyInRange(self):
    #     for cardUid in [38, 50]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [cardUid]})

    #         tuples = game.validateCardChoice('A', cardUid)
    #         self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #         self.assertTrue("nobody in range" in tuples[0][1]['html'])

    #         self.assertTrue(game.currentCard == None)




    # ''' Mustang and Scope tests. '''

    # # Unsuccessful Bang and Panico against a 1-away player who has a Mustang equipped.
    # def testMustang(self):
    #     for attackingUid in [1, 38]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         setPlayerCardsInPlay({'B': [67]})
    #         setPlayerCardsInPlay({'G': [2]}) # Needed so that Panico is considered valid.
    #         question = QUESTION_WHO_TO_SHOOT if attackingUid == 1 else QUESTION_WHOSE_CARDS

    #         game.validateCardChoice('A', attackingUid)
            
    #         tuples = game.processQuestionResponse('A', question, 'B')
    #         self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #         self.assertTrue("is out of range" in tuples[0][1]['html'])

    #         self.assertEqual(players['B'].lives, 4)

    #         self.assertTrue(game.currentCard == None)

    # # Successful Bang against a 2-away player by having a Scope equipped.
    # def testScopeAgainstBang(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1]})
    #     setPlayerCardsInPlay({'A': [66]})

    #     game.validateCardChoice('A', 1)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'C')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_PLAYER_LIST})

    #     self.assertTrue(game.currentCard == None)

    # # Successful Panico against a 2-away player by having a Scope equipped.
    # def testScopeAgainstPanico(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [38], 'C': [2]})
    #     setPlayerCardsInPlay({'A': [66]})

    #     game.validateCardChoice('A', 38)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'C')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})

    #     self.assertTrue(game.currentCard == None)

    # # Unsuccessful Bang and Pancico with a Scope equipped against a 2-away player who has a Mustang equipped.
    # def testOutOfRangeScopeAgainstMustang(self):
    #     for attackingUid in [1, 38]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         setPlayerCardsInPlay({'A': [66], 'C': [67]})
    #         setPlayerCardsInPlay({'G': [2]}) # Needed so that Panico is considered valid.
    #         question = QUESTION_WHO_TO_SHOOT if attackingUid == 1 else QUESTION_WHOSE_CARDS

    #         game.validateCardChoice('A', attackingUid)
    #         tuples = game.processQuestionResponse('A', question, 'C')
            
    #         self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #         self.assertTrue("is out of range" in tuples[0][1]['html'])

    #         self.assertTrue(game.currentCard == None)

    # # Successful Bang with a Scope equipped against a 1-away player who has a Mustang equipped.
    # def testInRangeScopeAgainstMustangWithBang(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [1]})
    #     setPlayerCardsInPlay({'A': [66], 'B': [67]})

    #     game.validateCardChoice('A', 1)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_SHOOT, 'B')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL, UPDATE_PLAYER_LIST})

    #     self.assertTrue(game.currentCard == None)

    # # Successful Panico with a Scope equipped against a 1-away player who has a Mustang equipped.
    # def testInRangeScopeAgainstMustangWithPanico(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [38]})
    #     setPlayerCardsInPlay({'A': [66], 'B': [67]})

    #     game.validateCardChoice('A', 38)
        
    #     tuples = game.processQuestionResponse('A', QUESTION_WHOSE_CARDS, 'B')
    #     self.assertEqual(getEmitTypes(tuples), {UPDATE_DISCARD_PILE, UPDATE_CARD_HAND, UPDATE_ACTION, SHOW_INFO_MODAL})

    #     self.assertTrue(game.currentCard == None)




    # ''' Barile tests. '''

    # # Successfully draw a heart against a Bang and a Gatling.
    # def testSuccessfulBariles(self):
    #     heartCard = getCardsOfASuit(HEART, 1)[0]
    #     for attackingUid in [1, 54]:
    #         setDefaults(numPlayers=2)
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         setPlayerCardsInPlay({'B': [64]})
    #         game.drawPile.append(heartCard)

    #         tuples = game.validateCardChoice('A', attackingUid)
    #         self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_CARD_HAND})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2 if attackingUid == 1 else 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertTrue("B drew a heart for Barile and avoided your" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][-1])
    #         self.assertTrue("You drew a heart for Barile and avoided the" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])

    #         self.assertEqual(players['B'].lives, 4)

    #         self.assertEqual(players['A'].cardsInHand, [])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid), heartCard])
    #         self.assertTrue(game.currentCard == None)

    # # Unsuccessfuly draw a heart against a Bang and a Gatling.
    # def testUnsuccessfulBariles(self):
    #     nonHeartCard = getCardsOfASuit(SPADE, 1)[0]
    #     for attackingUid in [1, 54]:
    #         setDefaults(numPlayers=2)
    #         setPlayerCardsInHand({'A': [attackingUid]})
    #         setPlayerCardsInPlay({'B': [64]})
    #         game.drawPile.append(nonHeartCard)

    #         tuples = game.validateCardChoice('A', attackingUid)
    #         self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_PLAYER_LIST, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_CARD_HAND})
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2 if attackingUid == 1 else 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 2)
    #         self.assertTrue("B took the hit" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][-1])
    #         self.assertTrue("You didn't draw a heart" in unescape([t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0]))
    #         self.assertTrue("you've lost a life" in unescape([t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][1]))

    #         self.assertEqual(players['B'].lives, 3)

    #         self.assertEqual(players['A'].cardsInHand, [])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(attackingUid), nonHeartCard])
    #         self.assertTrue(game.currentCard == None)

    # # Have 2 players both successfully draw a Barile against a Gatling.
    # def test2SuccessfulBariles(self):
    #     heartCards = getCardsOfASuit(HEART, 2)
    #     setDefaults(numPlayers=3)
    #     setPlayerCardsInHand({'A': [54]})
    #     setPlayerCardsInPlay({'B': [64], 'C': [65]})
    #     game.drawPile.extend(heartCards)

    #     tuples = game.validateCardChoice('A', 54)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_CARD_HAND})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['C']), 1)
    #     self.assertTrue("B drew a heart for Barile and avoided your" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertTrue("C drew a heart for Barile and avoided your" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][1])
    #     self.assertTrue("You drew a heart for Barile and avoided the" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])
    #     self.assertTrue("You drew a heart for Barile and avoided the" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['C']][0])

    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(54)] + heartCards[::-1])
    #     self.assertTrue(game.currentCard == None)

    # # Have 2 players successfully and unsuccessfuly draw a Barile against a Gatling.
    # def testSuccessfulAndUnsuccessfulBariles(self):
    #     heartCard = getCardsOfASuit(HEART, 1)[0]
    #     nonHeartCard = getCardsOfASuit(SPADE, 1)[0]
    #     setDefaults(numPlayers=3)
    #     setPlayerCardsInHand({'A': [54]})
    #     setPlayerCardsInPlay({'B': [64], 'C': [65]})
    #     game.drawPile.extend([heartCard, nonHeartCard])

    #     tuples = game.validateCardChoice('A', 54)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_PLAYER_LIST, UPDATE_DISCARD_PILE, UPDATE_ACTION, UPDATE_CARD_HAND})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['C']), 1)
    #     self.assertTrue("B took the hit" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])
    #     self.assertTrue("C drew a heart for Barile and avoided your" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][1])
    #     self.assertTrue("You didn't draw a heart" in unescape([t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0]))
    #     self.assertTrue("you've lost a life" in unescape([t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][1]))
    #     self.assertTrue("You drew a heart for Barile and avoided the" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['C']][0])

    #     self.assertEqual(players['B'].lives, 3)
    #     self.assertEqual(players['C'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(54), nonHeartCard, heartCard])
    #     self.assertTrue(game.currentCard == None)

    # # Have a player unsuccessfully draw a Barile against a Bang and Gatling but still avoid it by using a Mancato.
    # def testUnsuccessfulBarileWithMancato(self):
    #     self.assertTrue(False)




    # ''' Diligenza and Wells Fargo tests. '''

    # def testDiligenzaAndWellsFargo(self):
    #     for uid in [61, 63]:
    #         setDefaults()
    #         setPlayerCardsInHand({'A': [uid]})
    #         game.drawPile = [game.getCardByUid(drawUid) for drawUid in [10, 20, 30, 40]]
    #         originalDrawPile = list(game.drawPile)
    #         numCards = 2 if uid == 61 else 3

    #         tuples = game.validateCardChoice('A', uid)
    #         self.assertEqual(getEmitTypes(tuples), {UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, SHOW_INFO_MODAL, UPDATE_ACTION})
    #         self.assertTrue("You drew {} cards".format(numCards) in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL][0])

    #         self.assertEqual(players['A'].cardsInHand, originalDrawPile[::-1][:numCards])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(uid)])
    #         self.assertEqual(game.drawPile, originalDrawPile[:4-numCards])
    #         self.assertTrue(game.currentCard == None)




    # ''' Emporio tests. '''

    # # Test Emporio with 7 different cards (i.e. no automatic selections).
    # def testEmporioWithNoAutomaticSelections(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [48]})
    #     game.drawPile = [game.getCardByUid(uid) for uid in [1,2,30,40,50,60,70,80]]
    #     expectedEmporioOptions = game.drawPile[1:][::-1]
    #     expectedCardsInHand = list(expectedEmporioOptions)

    #     tuples = game.validateCardChoice('A', 48)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)

    #     self.assertEqual(game.drawPile, [game.getCardByUid(1)])
    #     self.assertEqual(game.emporioOptions, expectedEmporioOptions)

    #     for player in players.values():
    #         self.assertTrue(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, player), 1)

    #     for player in list(players.values())[:-1]:
    #         tuples = game.processEmporioCardSelection(player.username, expectedEmporioOptions.pop(0).uid)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, player), 1)

    #     self.assertTrue("You picked up the last Emporio card" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == list(players.values())[-1]][0])

    #     for i, player in enumerate(players.values()):
    #         self.assertEqual(player.cardsInHand, [expectedCardsInHand[i]])

    #     self.assertEqual(game.emporioOptions, [])
    #     self.assertTrue(game.currentCard == None)

    # # Test Emporio with 7 of the same card (i.e. with all automatic selections).
    # def testEmporioWithAllAutomaticSelections(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [48]})
    #     game.drawPile = [game.getCardByUid(uid) for uid in range(1, 2 + len(players))] # All Bangs.

    #     tuples = game.validateCardChoice('A', 48)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})

    #     self.assertEqual(game.drawPile, [game.getCardByUid(1)])
    #     self.assertEqual(game.emporioOptions, [])

    #     for player in players.values():
    #         self.assertTrue(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, player), 1)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, player), 2 if player.username == 'A' else 1)
    #         self.assertTrue("You automatically picked up" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == player][0])
            
    #         self.assertEqual(len(player.cardsInHand), 1)
    #         self.assertEqual(player.cardsInHand[0].name, BANG)

    #     self.assertTrue(game.currentCard == None)

    # # Test Emporio where the last few cards, but not all, are the same (i.e. with some automatic selections).
    # def testEmporioWithSomeAutomaticSelections(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [48]})
    #     game.drawPile = [game.getCardByUid(uid) for uid in [1,2,3,4,50,60,70,80]]
    #     numUniqueCards = len([c for c in game.drawPile if c.name != BANG])
    #     expectedEmporioOptions = game.drawPile[1:][::-1]
    #     expectedCardsInHand = expectedEmporioOptions[:numUniqueCards] + expectedEmporioOptions[numUniqueCards:][::-1]

    #     tuples = game.validateCardChoice('A', 48)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL, UPDATE_CARD_HAND, UPDATE_DISCARD_PILE, UPDATE_ACTION})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)

    #     self.assertEqual(game.drawPile, [game.getCardByUid(1)])
    #     self.assertEqual(game.emporioOptions, expectedEmporioOptions)

    #     for player in list(players.values())[:numUniqueCards]:
    #         tuples = game.processEmporioCardSelection(player.username, expectedEmporioOptions.pop(0).uid)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, player), 1)

    #     for player in list(players.values())[numUniqueCards:]:
    #         self.assertTrue("You automatically picked up" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == player][0])

    #     for i, player in enumerate(players.values()):
    #         self.assertEqual(player.cardsInHand, [expectedCardsInHand[i]])

    #     self.assertEqual(game.emporioOptions, [])
    #     self.assertTrue(game.currentCard == None)




    # ''' Gun tests. '''

    # # Verifying valid targets for every gun.
    # def testGunRanges(self):
    #     setDefaults()

    #     for (uid, expectedRange) in [(None, 1), (73, 1), (75, 2), (78, 3), (79, 4), (80, 5)]:
    #         if uid != None:
    #             setPlayerCardsInPlay({'A': [uid]})

    #         validTargets = game.getAllValidTargetsForCard(players['A'], BANG)
    #         expectedValidTargets = game.playerOrder[1:1+expectedRange] + game.playerOrder[1:][::-1][:expectedRange]

    #         self.assertEqual({p.username for p in validTargets}, {p.username for p in expectedValidTargets})

    # # Bang twice with a Volcanic in play.
    # def testVolcanicBangs(self):
    #     setDefaults(numPlayers=2)
    #     gunUids = [1, 2]
    #     setPlayerCardsInHand({'A': gunUids})
    #     setPlayerCardsInPlay({'A': [73]})

    #     expectedLives = 4
    #     expectedCardsInHand = [game.getCardByUid(uid) for uid in gunUids]
    #     expectedDiscard = []
    #     for uid in gunUids:
    #         expectedLives -= 1
    #         expectedDiscard.append(game.getCardByUid(uid))
    #         expectedCardsInHand.pop(0)

    #         tuples = game.validateCardChoice('A', uid)
    #         self.assertEqual(getEmitTypes(tuples), CARD_PLAYED_TUPLES | PLAYER_TOOK_DAMAGE_TUPLES)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 2)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)

    #         self.assertEqual(players['B'].lives, expectedLives)

    #         self.assertEqual(players['A'].cardsInHand, expectedCardsInHand)
    #         self.assertEqual(game.discardPile, expectedDiscard)
    #         self.assertTrue(game.currentCard == None)


    # ''' Prigione tests. '''

    # # Successfully playing a Prigione against a non-jailed player.
    # def testPrigioneAgainstNonJailedPlayer(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [69]})

    #     tuples = game.validateCardChoice('A', 69)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_QUESTION_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['A']), 1)
    #     self.assertEqual(tuples[0][1]['question'], QUESTION_WHO_TO_JAIL)

    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_JAIL, 'D')
    #     self.assertEqual(getEmitTypes(tuples), (CARD_PLAYED_TUPLES - {UPDATE_DISCARD_PILE}) | {SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['D']), 1)
    #     self.assertTrue("A just put you in jail" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['D']][0])

    #     self.assertEqual(players['D'].jailStatus, 1)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['D'].specialCards, [game.getCardByUid(69)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertEqual(game.currentCard, None)

    # # Unsuccessfully playing a Prigione against a jailed player.
    # def testPrigioneAgainstNonJailedPlayer(self):
    #     setDefaults()
    #     setPlayerCardsInHand({'A': [69]})
    #     setPlayerSpecialCards({'D': [70]})
    #     players['D'].jailStatus = 1

    #     game.validateCardChoice('A', 69)

    #     tuples = game.processQuestionResponse('A', QUESTION_WHO_TO_JAIL, 'D')
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['A']), 1)
    #     self.assertTrue("D is already in jail" in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']][0])

    #     self.assertEqual(players['D'].jailStatus, 1)

    #     self.assertEqual(players['A'].cardsInHand, [game.getCardByUid(69)])
    #     self.assertEqual(players['D'].specialCards, [game.getCardByUid(70)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertEqual(game.currentCard, None)

    # # Unsuccessfully playing a Prigione against the Sheriff.
    # def testPrigioneAgainstNonJailedPlayer(self):
    #     setDefaults()
    #     game.rotatePlayerOrder()
    #     setPlayerCardsInHand({'B': [69]})

    #     game.validateCardChoice('B', 69)

    #     tuples = game.processQuestionResponse('B', QUESTION_WHO_TO_JAIL, 'A')
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_INFO_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertTrue("You can't jail the sheriff" in unescape([t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0]))

    #     self.assertEqual(players['A'].jailStatus, 0)
        
    #     self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(69)])
    #     self.assertEqual(game.discardPile, [])
    #     self.assertEqual(game.currentCard, None)




    # ''' Character special ability tests. '''

    # # Bart Cassidy: Draw from the deck after taking damage.
    # def testBartCassidy(self):
    #     setDefaults()
    #     setPlayerCharacter('B', BART_CASSIDY)
    #     setPlayerCardsInHand({'A': [54]})
    #     cardToDraw = game.drawPile[-1]

    #     tuples = game.validateCardChoice('A', 54)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)
    #     self.assertTrue(any(["You drew a card because you lost a life" in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['B'].lives, 3)
    #     self.assertEqual(players['B'].cardsInHand, [cardToDraw])
    #     self.assertEqual(game.currentCard, None)

    # # Black Jack: Draw a third card when the second one is a heart and diamond, with everyone seeing the second.
    # def testBlackJack1(self):
    #     for suit in [HEART, DIAMOND]:
    #         setDefaults()
    #         setPlayerCharacter('B', BLACK_JACK)
    #         suitCard = getCardsOfASuit(suit, 1)[0]
    #         game.drawPile[-2] = suitCard
    #         expectedCardsDrawn = game.drawPile[-3:][::-1]
    #         expectedUpdate = "B (Black Jack) drew 3 cards. The second card was {}.".format(suitCard.getDeterminerString())
    #         expectedInfo = "You drew {}, {}, and {} because the {} is a {}".format(*[c.getDeterminerString() for c in expectedCardsDrawn], suitCard.getDisplayName(), suit)

    #         tuples = game.startNextTurn('A')
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertTrue(expectedInfo in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])
    #         self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #         self.assertEqual(players['B'].cardsInHand, expectedCardsDrawn)
    #         self.assertEqual(game.currentCard, None)

    # # Black Jack: Draw two cards normally when the second one is a club or spade, with everyone seeing the second.
    # def testBlackJack2(self):
    #     for suit in [CLUB, SPADE]:
    #         setDefaults()
    #         setPlayerCharacter('B', BLACK_JACK)
    #         suitCard = getCardsOfASuit(suit, 1)[0]
    #         game.drawPile[-2] = suitCard
    #         expectedCardsDrawn = game.drawPile[-2:][::-1]
    #         expectedUpdate = "B (Black Jack) drew 2 cards. The second card was {}.".format(suitCard.getDeterminerString())
    #         expectedInfo = "You drew {} and {}".format(*[c.getDeterminerString() for c in expectedCardsDrawn])

    #         tuples = game.startNextTurn('A')
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #         self.assertTrue(expectedInfo in [t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']][0])
    #         self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #         self.assertEqual(players['B'].cardsInHand, expectedCardsDrawn)
    #         self.assertEqual(game.currentCard, None)

    # # Calamity Janet: Use a Mancato as an attacking Bang.
    # def testCalamityJanetMancato1(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('A', CALAMITY_JANET)
    #     setPlayerCardsInHand({'A': [26]})
    #     expectedUpdate = "A played a {} against B.".format(MANCATO_AS_BANG)

    #     tuples = game.validateCardChoice('A', 26)
    #     self.assertEqual([t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION][0], expectedUpdate)

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(26)])
    #     self.assertEqual(game.currentCard, None)

    # # Calamity Janet: Use a Mancato as an attacking Bang where the target chooses from one of several cards with which to respond.
    # def testCalamityJanetMancato2(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('A', CALAMITY_JANET)
    #     setPlayerCardsInHand({'A': [26], 'B': [27, 28]})
    #     expectedUpdate = "B played a Mancato and avoided A's {}.".format(MANCATO_AS_BANG)

    #     game.validateCardChoice('A', 26)

    #     game.processQuestionResponse('B', QUESTION_BANG_REACTION.format('A'), PLAY_A_BANG)

    #     tuples = game.processBlurCardSelection('B', 27)
    #     self.assertEqual([t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION][0], expectedUpdate)

    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(28)])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(26), game.getCardByUid(27)])
    #     self.assertEqual(game.currentCard, None)

    # # Calamity Janet: Use a Mancato in response to an Indians.
    # def testCalamityJanetMancato3(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', CALAMITY_JANET)
    #     setPlayerCardsInHand({'A': [58], 'B': [26]})
    #     expectedUpdate = "B played a {} and avoided A's Indians.".format(MANCATO_AS_BANG)

    #     game.validateCardChoice('A', 58)
        
    #     tuples = game.processQuestionResponse('B', QUESTION_INDIANS_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertEqual([t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION][0], expectedUpdate)

    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(58), game.getCardByUid(26)])
    #     self.assertEqual(game.currentCard, None)

    # # Calamity Janet: Use a Mancato in a Duello.
    # def testCalamityJanetMancato4(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', CALAMITY_JANET)
    #     setPlayerCardsInHand({'A': [55], 'B': [26]})
    #     expectedUpdate = "B responded in the duel with A by playing a {}.".format(MANCATO_AS_BANG)

    #     game.validateCardChoice('A', 55)
        
    #     tuples = game.processQuestionResponse('B', QUESTION_DUELLO_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['A'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(55), game.getCardByUid(26)])
    #     self.assertEqual(game.currentCard, None)

    # # Calamity Janet: Use a Bang as a Mancato in response to a Bang.
    # def testCalamityJanetBang1(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', CALAMITY_JANET)
    #     setPlayerCardsInHand({'A': [1], 'B': [2]})
    #     expectedUpdate = "B played a {} and avoided A's Bang.".format(BANG_AS_MANCATO)

    #     game.validateCardChoice('A', 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_BANG_REACTION.format('A'), PLAY_A_BANG)
    #     self.assertEqual([t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION][0], expectedUpdate)

    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1), game.getCardByUid(2)])
    #     self.assertEqual(game.currentCard, None)

    # # Calamity Janet: Use a Bang as a Mancato in response to a Gatling.
    # def testCalamityJanetBang2(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', CALAMITY_JANET)
    #     setPlayerCardsInHand({'A': [54], 'B': [1]})
    #     expectedUpdate = "B played a {} and avoided A's Gatling.".format(BANG_AS_MANCATO)

    #     game.validateCardChoice('A', 54)
        
    #     tuples = game.processQuestionResponse('B', QUESTION_GATLING_REACTION.format('A'), PLAY_A_MANCATO)
    #     self.assertEqual([t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION][0], expectedUpdate)

    #     self.assertEqual(players['B'].lives, 4)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(54), game.getCardByUid(1)])
    #     self.assertEqual(game.currentCard, None)

    # # El Gringo: Steal from a player's hand after taking damage from his/her Bang.
    # def testElGringoAgainstBang(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', EL_GRINGO)
    #     setPlayerCardsInHand({'A': [1, 2]})
    #     expectedAttackerInfo = "B stole a Bang from your hand"
    #     expectedElGringoInfo = "You stole a Bang from A's hand"
    #     expectedUpdate = "B stole a card from A's hand using El Gringo's ability."

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 2)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)
    #     self.assertTrue(any([expectedAttackerInfo in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]))
    #     self.assertTrue(any([expectedElGringoInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(2)])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertEqual(game.currentCard, None)

    # # El Gringo: Steal from a player's hand after taking damage from his/her Gatling and Indians.
    # def testElGringoAgainstGatlingIndians(self):
    #     for uid in [54, 58]:
    #         setDefaults()
    #         setPlayerCharacter('B', EL_GRINGO)
    #         setPlayerCardsInHand({'A': [1, uid]})
    #         expectedAttackerInfo = "B stole a Bang from your hand"
    #         expectedElGringoInfo = "You stole a Bang from A's hand"
    #         expectedUpdate = "B stole a card from A's hand using El Gringo's ability."

    #         tuples = game.validateCardChoice('A', uid)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 2)
    #         self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 1)
    #         self.assertTrue(any([expectedAttackerInfo in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]))
    #         self.assertTrue(any([expectedElGringoInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #         self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #         self.assertEqual(players['B'].lives, 3)

    #         self.assertEqual(players['A'].cardsInHand, [])
    #         self.assertEqual(players['B'].cardsInHand, [game.getCardByUid(1)])
    #         self.assertEqual(game.discardPile, [game.getCardByUid(uid)])
    #         self.assertEqual(game.currentCard, None)

    # El Gringo: Steal from a player's hand after taking damage from his/her Duello.
    # def testElGringoAgainstDuello(self):
    #     self.assertTrue(False)

    # # El Gringo: Don't steal anything from a player's hand after taking damage if s/he has no cards to steal.
    # def testElGringoUnsuccessful(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', EL_GRINGO)
    #     setPlayerCardsInHand({'A': [1]})
    #     expectedElGringoInfo = "A has no cards, so you couldn't use El Gringo's ability to steal anything"

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['A']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, UPDATE_CARD_HAND, players['B']), 0)
    #     self.assertTrue(any([expectedElGringoInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['B'].lives, 3)

    #     self.assertEqual(players['A'].cardsInHand, [])
    #     self.assertEqual(players['B'].cardsInHand, [])
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)])
    #     self.assertEqual(game.currentCard, None)

    # # Jesse Jones: Draw one card from a player's hand and one from the deck.
    # def testJesseJonesUsingAbility(self):
    #     setDefaults()
    #     setPlayerCharacter('B', JESSE_JONES)
    #     setPlayerCardsInHand({'C': [1], 'D': [2]})
    #     expectedJesseJonesInfo = "You drew a Bang from D's hand and {} from the deck".format(game.drawPile[-1].getDeterminerString())
    #     expectedOpponentInfo = "B drew a Bang from your hand using Jesse Jones's ability"
    #     expectedUpdate = "B drew a card from D's hand using Jesse Jones's ability."
    #     expectedCardsDrawn = [game.getCardByUid(2), game.drawPile[-1]]

    #     tuples = game.startNextTurn('A')
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_JESSE_JONES, FROM_ANOTHER_PLAYER)
    #     self.assertEqual(getEmitTypes(tuples), {SHOW_QUESTION_MODAL})
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 1)
    #     self.assertEqual({val for val in tuples[0][1].values() if val in players}, {'C', 'D'})

    #     tuples = game.processQuestionResponse('B', QUESTION_WHOSE_HAND, 'D')
    #     self.assertTrue(any([expectedJesseJonesInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(any([expectedOpponentInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['D']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].cardsInHand, expectedCardsDrawn)
    #     self.assertEqual(players['D'].cardsInHand, [])
    #     self.assertEqual(game.currentCard, None)

    # # Jesse Jones: Draw one card from the hand of the only player with cards and one from the deck.
    # def testJesseJonesUsingAbilityAutomaticOpponent(self):
    #     setDefaults()
    #     setPlayerCharacter('B', JESSE_JONES)
    #     setPlayerCardsInHand({'D': [2]})
    #     expectedJesseJonesInfo = "You automatically drew a Bang from D's hand and {} from the deck".format(game.drawPile[-1].getDeterminerString())
    #     expectedOpponentInfo = "B drew a Bang from your hand using Jesse Jones's ability"
    #     expectedUpdate = "B drew a card from D's hand using Jesse Jones's ability."
    #     expectedCardsDrawn = [game.getCardByUid(2), game.drawPile[-1]]

    #     tuples = game.startNextTurn('A')
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_JESSE_JONES, FROM_ANOTHER_PLAYER)
    #     self.assertTrue(any([expectedJesseJonesInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(any([expectedOpponentInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['D']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].cardsInHand, expectedCardsDrawn)
    #     self.assertEqual(players['D'].cardsInHand, [])
    #     self.assertEqual(game.currentCard, None)

    # # Jesse Jones: Draw both cards normally from the deck by choice.
    # def testJesseJonesNotUsingAbilityByChoice(self):
    #     setDefaults()
    #     setPlayerCharacter('B', JESSE_JONES)
    #     setPlayerCardsInHand({'C': [1], 'D': [2]})
    #     expectedJesseJonesInfo = "You drew {} and {} from the deck".format(game.drawPile[-1].getDeterminerString(), game.drawPile[-2].getDeterminerString())
    #     expectedCardsDrawn = game.drawPile[-2:][::-1]

    #     tuples = game.startNextTurn('A')
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 1)

    #     tuples = game.processQuestionResponse('B', QUESTION_JESSE_JONES, FROM_THE_DECK)
    #     self.assertTrue(any([expectedJesseJonesInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['B'].cardsInHand, expectedCardsDrawn)
    #     self.assertEqual(game.currentCard, None)

    # # Jesse Jones: Draw both cards normally because nobody has a card to steal.
    # def testJesseJonesNotUsingAbilityHavingNoChoice(self):
    #     setDefaults()
    #     setPlayerCharacter('B', JESSE_JONES)
    #     expectedJesseJonesInfo = "you were forced to draw 2 cards from the deck".format()
    #     expectedCardsDrawn = game.drawPile[-2:][::-1]

    #     tuples = game.startNextTurn('A')
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_INFO_MODAL, players['B']), 1)
    #     self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 0)
    #     self.assertTrue(any([expectedJesseJonesInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #     self.assertEqual(players['B'].cardsInHand, expectedCardsDrawn)
    #     self.assertEqual(game.currentCard, None)

    # # Jourdonnais: Draw once against a Bang without having a Barile in play and get a heart.
    # def testJourdonnaisWithoutBarileSuccess(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', JOURDONNAIS)
    #     setPlayerCardsInHand({'A': [1]})
    #     expectedAttackerInfo = "B drew a heart for Barile and avoided your Bang"
    #     expectedJourdonnaisInfo = "You drew a heart for Barile"
    #     expectedUpdate = "B drew a heart for Barile and avoided A's Bang."
    #     cardToDraw = getCardsOfASuit(HEART, 1)[0]
    #     game.drawPile.append(cardToDraw)

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertTrue(any([expectedAttackerInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]))
    #     self.assertTrue(any([expectedJourdonnaisInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].lives, 4)
    #     self.assertEqual(game.currentCard, None)

    # # Jourdonnais: Draw once against a Bang without having a Barile in play and don't get a heart.
    # def testJourdonnaisWithoutBarileFailure(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', JOURDONNAIS)
    #     setPlayerCardsInHand({'A': [1]})
    #     expectedJourdonnaisInfo = "You didn't draw a heart"
    #     expectedUpdate = "B tried to avoid the Bang with a Barile but didn't draw a heart."
    #     cardToDraw = getCardsOfASuit(SPADE, 1)[0]
    #     game.drawPile.append(cardToDraw)

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertTrue(any([expectedJourdonnaisInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].lives, 3)
    #     self.assertEqual(game.currentCard, None)

    # # Jourdonnais: Draw twice against a Bang with a Barile in play when the first card isn't a heart, getting a heart on the second card.
    # def testJourdonnaisWithBarileSuccess(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', JOURDONNAIS)
    #     setPlayerCardsInHand({'A': [1]})
    #     setPlayerCardsInPlay({'B': [64]})
    #     expectedAttackerInfo = "B drew a heart for Barile and avoided your Bang"
    #     expectedJourdonnaisInfo = "You drew a heart for Barile on your second card and avoided the Bang"
    #     expectedUpdate = "B drew a heart for Barile and avoided A's Bang."
    #     cardsToDraw = [getCardsOfASuit(HEART, 1)[0], getCardsOfASuit(CLUB, 1)[0]]
    #     game.drawPile.extend(cardsToDraw)

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertTrue(any([expectedAttackerInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['A']]))
    #     self.assertTrue(any([expectedJourdonnaisInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].lives, 4)
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)] + cardsToDraw[::-1])
    #     self.assertEqual(game.currentCard, None)

    # # Jourdonnais: Draw twice against a Bang with a Barile in play when the first card isn't a heart, failing both times.
    # def testJourdonnaisWithBarileFailure(self):
    #     setDefaults(numPlayers=2)
    #     setPlayerCharacter('B', JOURDONNAIS)
    #     setPlayerCardsInHand({'A': [1]})
    #     setPlayerCardsInPlay({'B': [64]})
    #     expectedJourdonnaisInfo = "You didn't draw a heart against A's Bang either time"
    #     expectedUpdate = "B tried to avoid the Bang with a Barile but didn't draw a heart either time."
    #     cardsToDraw = [getCardsOfASuit(DIAMOND, 1)[0], getCardsOfASuit(SPADE, 1)[0]]
    #     game.drawPile.extend(cardsToDraw)

    #     tuples = game.validateCardChoice('A', 1)
    #     self.assertTrue(any([expectedJourdonnaisInfo in unescape(t[1]['html']) for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))
    #     self.assertTrue(expectedUpdate in [t[1]['update'] for t in tuples if t[0] == UPDATE_ACTION])

    #     self.assertEqual(players['B'].lives, 3)
    #     self.assertEqual(game.discardPile, [game.getCardByUid(1)] + cardsToDraw[::-1])
    #     self.assertEqual(game.currentCard, None)

    # # Kit Carlson: Choose two of the first three cards and put the third back on the draw pile in every combination.
    # def testKitCarlson(self):
    #     for cardIndex in range(0, 3):
    #         setDefaults()
    #         setPlayerCharacter('B', KIT_CARLSON)
    #         expectedOptions = game.drawPile[-3:][::-1]
    #         expectedKitCarlsonInfo = "You drew {} and {} and put {} back on the draw pile".format(*[c.getDeterminerString() for (i, c) in enumerate(expectedOptions) if i != cardIndex], expectedOptions[cardIndex].getDeterminerString())

    #         tuples = game.startNextTurn('A')
    #         self.assertEqual(countEmitTypeToRecipient(tuples, SHOW_QUESTION_MODAL, players['B']), 1)
    #         self.assertTrue([c.getQuestionString() in [t[1].values() for t in tuples if t[0] == SHOW_QUESTION_MODAL and t[2] == players['B']] for c in expectedOptions])

    #         tuples = game.processQuestionResponse('B', QUESTION_KIT_CARLSON, expectedOptions[cardIndex].getQuestionString())
    #         self.assertTrue(any([expectedKitCarlsonInfo in t[1]['html'] for t in tuples if t[0] == SHOW_INFO_MODAL and t[2] == players['B']]))

    #         self.assertEqual(players['B'].cardsInHand, [c for (i, c) in enumerate(expectedOptions) if i != cardIndex])
    #         self.assertEqual(game.drawPile[-1], expectedOptions[cardIndex])
    #         self.assertEqual(game.discardPile, [])
    #         self.assertEqual(game.currentCard, None)

    # Lucky Duke: Successfully "draw!" by choosing the useful option.

    # Lucky Duke: Unsuccessfully "draw!" by not getting a useful choice.

    # Paul Regret: Be out of range for a 1-range Bang without a Mustang in play.

    # Paul Regret: Be in range for a 2-range Bang without a Mustang in play.

    # Paul Regret: Be out of range for a 2-range Bang with a Mustang in play.

    # Pedro Ramirez: Draw one card from the discard pile and one from the deck.

    # Pedro Ramirez: Draw both cards from the deck.

    # Rose Doolan: Successfully Bang a 2-away player without a Scope in play.

    # Rose Doolan: Unsuccessfully Bang a 3-away player without a Scope in play.

    # Rose Doolan. Successfully Bang a 3-away player with a Scope in play.

    # Sid Ketchum: Successfully discard two cards to regain one life point.

    # Sid Ketchum: Successfully discard four cards to regain two life points.

    # Sid Ketchum: Unsuccessfully try to discard two cards with none/one in hand.

    # Slab the Killer: Successfully Bang against a target who only has one Mancato.

    # Slab the Killer: Unsuccessfully Bang against a target who has two Mancatos and plays both.

    # Slab the Killer: Successfully Bang against a target who has two Mancatos but doesn't play them.

    # Slab the Killer: Successfully Bang against a target who draws a heart for "draw!".

    # Slab the Killer: Unsuccessfully Bang against a target who both draws a heart for "draw!" and plays a Mancato.

    # Slab the Killer: Successfully avoid his Gatling using only 1 Mancato.

    # Suzy Lafayette: Draw a card as soon as last card was played in turn.

    # Suzy Lafayette: Draw a card after playing last card from hand in response to an attacking card.

    # Suzy Lafayette: Wait until after a Duello is finished to draw a new card.

    # Suzy Lafayette: Draw a card after having last one stolen by a Cat Balou / Panico.

    # Suzy Lafayette: Draw a card after playing a Birra to stay alive.

    # Suzy Lafayette: Draw a card after having last one stolen by El Gringo.

    # Suzy Lafayette: Don't draw a card after discarding final card at the end of turn.

    # Vulture Sam: Take all the cards from a player's hand and from in front of him/her when s/he gets eliminated.

    # Willy the Kid: Successfully play two Bangs in one turn.
    



    ''' Drawing cards to start the turn tests. '''

    # Drawing for dynamite only (both success and failure).

    # Drawing for jail only (both success and failure).

    # Drawing for dynamite and jail (all 4 combinations of success and failure).




    ''' Having cards in play tests. '''

    # Unsuccessfully putting down a duplicate card type.

    # Choosing to replace one in-play card with another when 2 are down.

    # Choosing not to replace one in-play card with another when 2 are down.

    # Choosing to replace an in-play gun with a new one.

    # Choosing to keep an in-play gun instead of playing a new one.




    ''' Game setup tests. '''

    # All characters assigned are unique.

    # All players have the correct number of cards and lives to begin with.




    ''' Discarding cards to end the turn tests. '''

    # Too many cards and discards enough at once.

    # Too many cards but doesn't discard enough the first time.

    # Few enough cards and doesn't discard anything.

    # Few enough cards but discards some anyway.





    ''' Players getting eliminated tests. '''

    # Rotating player order skips a player who was just eliminated.

    # Valid targets properly account for eliminated players.

    # Eliminated player's cards go to the discard pile.

    # Whoever eliminates an Outlaw takes their cards.

    # When an Outlaw loses via their own Duello, their cards just go to the discard.

    # When the Sheriff eliminates a Vice, he loses all his cards.

    # If Vulture Sam is Sheriff and eliminates a Vice, he gains the Vice's cards before losing all of his own.



    ''' Game ending scenario tests. '''

    # Sheriff vs. outlaw, sheriff. vs renegade, etc.




    ''' Miscellaneous tests. '''

    # Drawing 2 cards from a draw pile with 1 card left.


if __name__ == '__main__':
    unittest.main()