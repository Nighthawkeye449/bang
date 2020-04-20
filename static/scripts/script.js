var socket;
var username;

var OK_MSG = "OK";
var INFO_MODAL = "#info_modal";
var QUESTION_MODAL = "#question_modal"
var TOP_HALF = "#topHalfDiv"
var BOTTOM_HALF = "#bottomHalfDiv"
var CARD_CAROUSEL = "#cardsInHandCarousel"
var WAITING_FOR_SPAN = "#waitingForSpan"

var cardsAreBlurred = false;
var keysPressed = {};

$(document).ready(function(){
	
	// Connect to the socket server.
	username = document.getElementById("username").textContent;

	if (username.length > 0) {
		socket = io.connect('http://' + document.domain + ':' + location.port + '/', { forceNew: true });
		socket.emit('connected', username);

		/* Socket functions for showing the modals. */

		socket.on('show_info_modal', function(data) {
			if (isNullOrUndefined($(INFO_MODAL).html())) { // Undefined if the message was received before the page was rendered.
				var html = data.html;
				socket.emit("info_modal_undefined", username, html);
			}
			else {
				showInfoModal(data.html);
			}
		});

		socket.on('show_question_modal', function(data) {
			// Close the waiting modal if it's currently open, as it will block the question modal.
			if (waitingModalIsOpen()) {
				closeWaitingModal();
			}

			if (isNullOrUndefined($(QUESTION_MODAL).html())) { // Undefined if the message was received before the page was rendered.
				var option1 = data.option1;
				var option2 = data.option2;
				var option3 = data.option3;
				var option4 = data.option4;
				var option5 = data.option5;
				var option6 = data.option6;
				var html = data.html;
				var question = data.question;
				socket.emit("question_modal_undefined", username, option1, option2, option3, option4, option5, option6, html, question);
			}
			else
			{
				// Close the waiting modal if it's open.
				if ($(INFO_MODAL).is(':visible')) {
					if ($('#infoModalText').text().indexOf('Waiting') > -1) {
						$(INFO_MODAL).modal('hide');
						$(INFO_MODAL).html('');
					}
				}

				// 6 options because the most for any question would be listing 6 other player's usernames.
				var option1 = data.option1;
				var option2 = data.option2;
				var option3 = data.option3;
				var option4 = data.option4;
				var option5 = data.option5;
				var option6 = data.option6;

				var question = data.question;

				var d = {};
				d[option1] = function() { socket.emit("question_modal_answered", username, question, option1); $( this ).dialog( "close" ); };
				d[option2] = function() { socket.emit("question_modal_answered", username, question, option2); $( this ).dialog( "close" ); };
				if (!isNullOrUndefined(option3)) { d[option3] = function() { socket.emit("question_modal_answered", username, question, option3); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(option4)) { d[option4] = function() { socket.emit("question_modal_answered", username, question, option4); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(option5)) { d[option5] = function() { socket.emit("question_modal_answered", username, question, option5); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(option6)) { d[option6] = function() { socket.emit("question_modal_answered", username, question, option6); $( this ).dialog( "close" ); }; }

				$(QUESTION_MODAL).css("display", "block");
				$(QUESTION_MODAL).html(data.html)
				$(QUESTION_MODAL).dialog({
					dialogClass: "no-close",
					resizable: false,
					height: "auto",
					width: 700,
					modal: true,
					buttons: d
		    	});
			}
		});

		socket.on('show_waiting_modal', function(data) {
			showInfoModal(data.html);
			addBlurToFullScreen();
		});

		/* Socket functions for waiting in the lobby. */

		socket.on('new_player_in_lobby', function(data) {
			players = data.usernames;
			lobby_players_list_string = '';

			// Update the list of players for people who are already in the lobby.
			for (var i = 0; i < players.length; i++) {
				lobby_players_list_string = lobby_players_list_string + '<li>' + players[i].toString() + '</li>';
			}
			$('#lobby_usernames').html(lobby_players_list_string);

			// Once enough players are in the game, show the start button.
			if (players.length >= 4 && players.length <= 7) {
				$("#start_button").css("display", "block");
			}
		});

		socket.on('game_start_countdown', function(data) {
			$("#countdown_span").css("display", "block");
			$("#countdown_span").text(data.count)			
		});

		socket.on('start_game', function(data) {

			var xhr = new XMLHttpRequest();

			xhr.onreadystatechange = function() {
				if (xhr.readyState === 4) {
					loadHtml(xhr.response); // Force the new page to render because manually sending a POST request blocks it.
				}
			}

			xhr.open("POST", "/setup", true);
			xhr.setRequestHeader('Content-Type', 'application/json');
			xhr.send(JSON.stringify({
				'username': username
			}));
		});

		/* Socket functions for setup. */

		socket.on('character_was_set', function(data) {
			if (data.players_remaining.includes(username)) {
				var others_left = data.players_remaining.length - 1;
				if (others_left >= 0) {
					if (others_left == 0) {
						$(WAITING_FOR_SPAN).html("We're just waiting for you to pick a character now...");
					}
					else if (others_left == 1) {
						$(WAITING_FOR_SPAN).html("Waiting for you and 1 other player to pick a character...");
					}
					else {
						$(WAITING_FOR_SPAN).html("Waiting for you and " + others_left.toString() + " other players to pick a character...");
					}
				}
			}
			else {
				var others_left = data.players_remaining.length;
				if (others_left == 1) { $(WAITING_FOR_SPAN).html("We're still waiting for 1 more player..."); }
				else { $(WAITING_FOR_SPAN).html("We're still waiting for " + others_left.toString() + " players..."); }
			}
		});

		/* Socket functions for the play page. */

		socket.on('reload_play_page', function(data) {
			loadPlayPage(data.html);
		});

		socket.on('update_action', function(data) {
			$("#updateActionList").prepend("<li>" + data.update + "</li>");
		});

		socket.on('blur_card_selection', function(data) {
			addBlurToCards(data.cardNames);
		});

		socket.on('update_card_hand', function(data) {
			$("#cardsInHandCarouselInnerDiv").html("");
			$("#cardsInHandCarouselInnerDiv").html(data.html);
			setupCarousel();
		});

		socket.on('update_cards_in_play', function(data) {
			$("#cardsInPlayDiv").html("");
			$("#cardsInPlayDiv").html(data.html);
		});

		socket.on('update_discard_pile', function(data) {
			$("#discardCardImage").attr("src", data.path);
		});

		socket.on('end_your_turn', function(data) {
			socket.emit('ending_turn', username);
		});

		socket.on('update_player_list', function(data) {
			$(BOTTOM_HALF).html("");
			$(BOTTOM_HALF).html(data.html);
		});

		socket.on('discard_click', function(data) {
			addDiscardClickFunctions();
		})
	}
});

/* General functions */

function loadHtml(html) {
	document.body.innerHTML = "";
	window.document.write(html);
}

function isNullOrUndefined(obj) {
	return obj == null || obj == undefined;
}

function capitalizeWords(s) {
	return s
    .toLowerCase()
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function startButtonClick() {
	socket.emit('start_button_clicked');
}

function chooseCharacter(character, isOption1) {
	if (confirm("Are you sure you want to play as " + character + "?")) {
		$("#option1Card").removeAttr("onClick");
		$("#option2Card").removeAttr("onClick");
		
		if (isOption1) {
			$("#option2Card").css("display", "none");
		}
		else {
			$("#option1Card").css("display", "none");
		}

		$("#characterOptionsSpan").html("Your character is " + character + ".");
		socket.emit('set_character', username, character);
	}
}

function loadPlayPage(html) {
	loadHtml(html);
	setupCarousel();
}

function showInfoModal(html) {
	// If an info message arrives once the waiting modal is already open, the blurs on the play screen need to be removed here.
	removeBlurFromFullScreen();

	// If the modal is already open and standard, and the new modal is standard, just combine the text of the two.
	var eitherModalIncludesImg = ($(INFO_MODAL).html().includes("<img")) || (html.includes("<img"));
	var eitherModalIsWaiting = waitingModalIsOpen() || (html.includes("Waiting"));

	if ($(INFO_MODAL).is(':visible') && !eitherModalIncludesImg && !eitherModalIsWaiting) {
		var newModalElements = $(html);
		var element = $('#infoModalText', newModalElements);
		$("#infoModalText").prepend(element[0].innerText + '<br/><br/>');
	}

	// Otherwise, load the new HTML into the modal and display it.
	else {
		closeInfoModal();
		$(INFO_MODAL).html(html);
		$(INFO_MODAL).modal('show');
	}
}

function playCard(uid) {
	if (!cardsAreBlurred) {	socket.emit('validate_card_choice', username, uid); }
}

function playBlurCard(uid) {
	socket.emit('blur_card_played', username, uid);
	removeBlurFromCards();
}

function discardCard(uid) {
	socket.emit('discarding_card', username, uid);
}

function addBlurToCards(cardNames) {
	$(CARD_CAROUSEL).find("img").each(function() {
		var cardName = $(this).attr("alt").split(' ')[0];
		var uid = $(this).attr("alt").split(' ')[1];
		
		if (!cardNames.includes(cardName)) {
			$(this).addClass("blur");
		}
		else {
			$(this).attr("onClick", "playBlurCard(" + uid + ")" ); 
		}
	});
	
	cardsAreBlurred = true;
}

function removeBlurFromCards() {
	$(CARD_CAROUSEL).find("img").each(function() {
		$(this).removeClass("blur");
		$(this).removeAttr("onClick"); // If the player is the current player, the click function will be reset by the new card carousel.
	});
	
	cardsAreBlurred = false;
}

function addBlurToFullScreen() {
	$(TOP_HALF).addClass("blur");
	$(BOTTOM_HALF).addClass("blur");
}
 
function removeBlurFromFullScreen() {
	$(TOP_HALF).removeClass("blur");
	$(BOTTOM_HALF).removeClass("blur");
}

function pickEmporioCard(uid) {
	socket.emit('emporio_card_picked', username, uid);
}

function setupCarousel() {
	$(CARD_CAROUSEL).carousel({
	  interval: false
	});

	$('.carousel-inner').css('overflow', 'visible');

	$('.carousel .item').each(function(){
	  var next = $(this).next();
	  if (!next.length) {
	    next = $(this).siblings(':first');
	  }
	  next.children(':first-child').clone().appendTo($(this));
	  
	  if (next.next().length>0) {
	    next.next().children(':first-child').clone().appendTo($(this));
	  }
	  else {
	  	$(this).siblings(':first').children(':first-child').clone().appendTo($(this));
	  }
	});
}

function addDiscardClickFunctions(add=true) {
	$(CARD_CAROUSEL).find("img").each(function() {
		var cardName = $(this).attr("alt").split(' ')[0];
		var uid = $(this).attr("alt").split(' ')[1];

		if (add) {
			$(this).attr("onClick", "discardCard(" + uid + ")" );
		}
		else {
			$(this).removeAttr("onClick");
		}
	});
}

function waitingModalIsOpen() {
	return $(INFO_MODAL).html().includes("Waiting");
}

function closeInfoModal() {
	$(INFO_MODAL).modal('hide');
	$(INFO_MODAL).html('');
}

function closeWaitingModal() {
	removeBlurFromFullScreen();
	closeInfoModal();
}

/* Key press functions to enable players to send messages to the server using keyboard strokes. */

$(document).keydown(function (e) {
    keysPressed[e.which] = true;

    if (16 in keysPressed && 69 in keysPressed) { // Shift-E, to end the turn.
    	socket.emit('ending_turn', username);
    }

    else if (16 in keysPressed && 83 in keysPressed) { // Shift-S, to trigger a special ability when applicable.
    	socket.emit('use_special_ability', username);
    }
});

$(document).keyup(function (e) {
    delete keysPressed[e.which];
});