var socket;
var username;

var OK_MSG = "OK";
var INFO_MODAL = "#info_modal";
var INFO_MODAL_TEXT = "#infoModalText";
var INFO_MODAL_IMAGES = "#infoModalImages";
var QUESTION_MODAL = "#question_modal"
var TOP_HALF = "#topHalfDiv"
var BOTTOM_HALF = "#bottomHalfDiv"
var CARDS_IN_HAND_DIV = "#cardsInHandDiv"
var CARDS_IN_PLAY_DIV = "#cardsInPlayDiv";
var DISCARD_DIV = "#discardCardDiv";
var WAITING_FOR_SPAN = "#waitingForSpan";
var LOBBY_USERNAMES = "#lobby_usernames";
var SOCKET_TIME_DIFFERENCE = 500; // Half a second.

var cardsAreBlurred = false;
var clickingOnPlayer = false;
var keysPressed = {};
var healthAnimationCounter = 0;
var lastCardUid = -1;
var previousSocketTime = new Date().getTime();

$(document).ready(function(){

	if (!(navigator.userAgent.search("Chrome") >= 0)) {
		alert("Using Chrome is strongly encouraged for this game. Other browsers may experience rendering issues.");
	}

	if (location.protocol !== 'http:') {
	    location.replace(`http:${location.href.substring(location.protocol.length)}`);
	}

	username = $("#username").text();
	window.history.pushState({}, '', '/');

	// Connect to the socket server.
	if (username.length > 0) {
		socket = io.connect('http://' + document.domain + ':' + location.port + '/', { forceNew: true, transports: ['websocket'] });
		socket.emit('connected', username);

		setInterval(function() { socket.emit('connected', username); }, 5000);

		socket.on('disconnect', function () {
			socket.emit('connected', username);
			setTimeout(function() {
				socket.emit('rejoin_game', username);
			}, 250);
		});

		/* Socket functions for showing the modals. */

		socket.on('show_info_modal', function(data) {
			if (isNullOrUndefined($(INFO_MODAL).html())) { // Undefined if the message was received before the page was rendered.
				setTimeout(function() {
					var html = data.html;
					socket.emit('info_modal_undefined', username, html);
				}, 500);
			}
			else {
				showInfoModal(data.html);
			}
		});

		socket.on('show_question_modal', function(data) {
			// Close the waiting modal if it's currently open, as it will block the question modal.
			if (waitingModalIsOpen()) {
				closeInfoModal();
			}

			if (isNullOrUndefined($(QUESTION_MODAL).html())) { // Undefined if the message was received before the page was rendered.
				setTimeout(function() {
					var option1 = data.option1;
					var option2 = data.option2;
					var option3 = data.option3;
					var option4 = data.option4;
					var option5 = data.option5;
					var option6 = data.option6;
					var option7 = data.option7;
					var html = data.html;
					var question = data.question;
					socket.emit('question_modal_undefined', username, option1, option2, option3, option4, option5, option6, option7, html, question);
				}, 500);
			}
			else
			{
				// Close the waiting modal if it's open.
				if ($(INFO_MODAL).is(':visible')) {
					if ($(INFO_MODAL_TEXT).text().indexOf('Waiting') > -1) {
						$(INFO_MODAL).modal('hide');
						$(INFO_MODAL).html('');
					}
				}

				var question = data.question;
				var d = {};

				d[data.option1] = function() { socket.emit('question_modal_answered', username, question, data.option1); $( this ).dialog( "close" ); };
				d[data.option2] = function() { socket.emit('question_modal_answered', username, question, data.option2); $( this ).dialog( "close" ); };
				if (!isNullOrUndefined(data.option3)) { d[data.option3] = function() { socket.emit('question_modal_answered', username, question, data.option3); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(data.option4)) { d[data.option4] = function() { socket.emit('question_modal_answered', username, question, data.option4); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(data.option5)) { d[data.option5] = function() { socket.emit('question_modal_answered', username, question, data.option5); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(data.option6)) { d[data.option6] = function() { socket.emit('question_modal_answered', username, question, data.option6); $( this ).dialog( "close" ); }; }
				if (!isNullOrUndefined(data.option7)) { d[data.option7] = function() { socket.emit('question_modal_answered', username, question, data.option7); $( this ).dialog( "close" ); }; }

				$(QUESTION_MODAL).css("display", "block");
				$(QUESTION_MODAL).html(data.html)
				$(QUESTION_MODAL).dialog({
					dialogClass: "no-close",
					resizable: false,
					autoResize: true,
					height: "auto",
					width: "auto",
					minHeight: 0,
					modal: true,
					buttons: d,
					open: function(event, ui) {
						$(this).dialog('widget').position({ my: "center", at: "center", of: window });
					}
		    	});

		    	$(".ui-dialog-buttonset button").each(function() {
					$(this).addClass("bang-button-question");
				});
			}
		});

		socket.on('show_waiting_modal', function(data) {
			showInfoModal(data.html);
		});

		/* Socket functions for waiting in the lobby. */

		socket.on('lobby_player_update', function(data) {
			var players = data.usernames;
			var lobby_players_list_string = '';

			// Update the list of players for people who are already in the lobby.
			var listTag;
			for (var i = 0; i < players.length; i++) {
				if (i == 0) {
					listTag = "<li style='color: red;'>"
				}
				else {
					listTag = "<li>"
				}
				lobby_players_list_string = lobby_players_list_string + listTag + players[i].toString() + '</li>';
			}
			$(LOBBY_USERNAMES).html(lobby_players_list_string);
		});

		socket.on('show_start_button', function(data) {
			$("#start_button").css("display", "block");
		});

		socket.on('hide_start_button', function(data) {
			$("#start_button").css("display", "none");
		});

		socket.on('reload_lobby', function(data) {
			loadHtml(data.html);
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
			loadPlayPage(data);
		});

		socket.on('update_action', function(data) {
			var usernameList = [];
			$(".playerInfoColumn h2").each(function(index, elem) {
				usernameList.push($(this).text());
			});

			// Indent updates that are during a turn.
			var startTag = "<li>";
			if (!data.update.includes("started their turn")) {
				startTag = "<li " + "style='margin-left: 25px;'" + ">"
			}
			else { // Add a line break between each player's turn.
				if ($("#updateActionList li").length > 0) {
					startTag = "<br>" + startTag;
				}
			}

			// Make player usernames red.
			var redSpan = "<span style='color: red;'>";

			if (!data.update.includes("won the game")) {
				var wordsInUpdate = data.update.split(' ');
				var updateHtml = startTag;

				for (var i = 0; i < wordsInUpdate.length; i++) {
					if (usernameList.includes(wordsInUpdate[i])
						|| usernameList.includes(wordsInUpdate[i].replace("'s", ''))
						|| usernameList.includes(wordsInUpdate[i].replace(".", ''))
						|| usernameList.includes(wordsInUpdate[i].replace(",", ''))) {
						updateHtml += (redSpan + wordsInUpdate[i] + "</span>");
					}
					else {
						updateHtml += wordsInUpdate[i];
					}
					updateHtml += ' ';
				}
				$("#updateActionList").append(updateHtml + "</li>");
			}
			else {
				$("#updateActionList").append(startTag + redSpan + data.update + "</span>" + "</li>");
			}
			
			// Automatically keep the list of updates scrolled to the bottom.
			var updateList = document.getElementById("updateActionList");
		    if (!isNullOrUndefined(updateList)) { updateList.scrollIntoView(false); }

			if ((/played a(n?) (Bang|Duello|Indians|Gatling)/.test(data.update) == false || (data.update.includes(" avoid"))) && !data.update.includes("won the game")) {
				socket.emit('request_player_list', username);
			}
		});

		socket.on('blur_card_selection', function(data) {
			addBlurToCards(data.cardNames);
		});

		socket.on('update_card_hand', function(data) {
			createCardHand(data.cardInfo);
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

			// Shrink any usernames that don't fit above the player's card.
			$(".player-list-usernames").each(function() {
			    while ($(this).width() > $(this).parent().width() * 0.8) {
			        $(this).css('font-size', (parseInt($(this).css('font-size')) - 1) + "px" );
			    }
			});

			setupTooltip();
		});

		socket.on('health_animation', function(data) {
			setTimeout(function() {
				healthAnimationCounter++;
				var playerDiv = $('#player_div_' + data.username);
				var divTop = playerDiv.offset().top;
				var divPosTop = divTop - $(window).scrollTop();
				var divLeft = playerDiv.offset().left;
				var divPosLeft = divLeft - $(window).scrollLeft();
				var animationColor = data.healthChange < 0 ? "red" : "limegreen";

				$("body").append('<span id="player_damage_span_' + (data.username + healthAnimationCounter.toString()) + '" style="font-size: 35px; font-style: italic; color: ' + animationColor +
									'; z-index: 200; position: absolute; top: ' + divPosTop.toString() + '; left: ' + (divPosLeft + (playerDiv.width() / 2)).toString() + ' "></span>');
				var playerDamageSpan = $("#player_damage_span_" + (data.username + healthAnimationCounter.toString()));
				playerDamageSpan.text((data.healthChange > 0 ? "+" : "") + data.healthChange.toString());
				playerDamageSpan.animate({
					top: "-25px",
					opacity: 0.5
			  }, 5000, function() { playerDamageSpan.remove()});
			}, 500); // Wait for half a second in case the player's position changes.
		});

		socket.on('discard_click', function(data) {
			addDiscardClickFunctions();
		});

		socket.on('game_over', function(data) {
			if (questionModalIsOpen()) { $(QUESTION_MODAL).dialog( "close" );	}
			showInfoModal(data.html);

			// Remove the click function for the player's cards if applicable.
			$(CARDS_IN_HAND_DIV).find("img").each(function() {
				$(this).attr("onClick", ""); 
			});

			// Replace the question mark with a button for returning to the lobby.
			$("#questionmark").hide();
			$("#return-to-lobby-button").css("display", "block");
		});

		socket.on('create_click_on_players', function(data) {
			clickingOnPlayer = true;

			// Handle the player reloading the page.
			if (lastCardUid == 0 && data.lastCardUid != 0) {
				lastCardUid = data.lastCardUid;
				setTimeout(function() {
					setPlayerClicks(data.clickType);
				}, 500);
			}
			else {
				setPlayerClicks(data.clickType);
			}

			if (data.clickType == "targeted_card_player_click") {
				setCardOpacity(true, lastCardUid);
			}
		});
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
	socket.emit('start_button_clicked', username);
}

function leaveLobby() {
	socket.emit('leave_lobby', username);
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

function loadPlayPage(data) {
	loadHtml(data.html);
	createCardHand(data.cardInfo);
	setupTooltip();
	$("body").css("overflow", "hidden");
}

function showInfoModal(html) {
	// Do nothing if the question modal is already open.
	if (questionModalIsOpen()) { return; }

	// If the incoming info modal is for Kit Carlson, the current info modal needs to be closed if it's open.
	if (html.includes("Drawing Cards") && html.includes("Kit Carlson")) {
		closeInfoModal();
	}

	// If the modals can be combined, just combine them.
	var eitherModalIsWaiting = waitingModalIsOpen() || html.includes("Waiting");
	var eitherModalIsEmporio = emporioModalIsOpen() || (html.includes("Emporio</h"));
	if ($(INFO_MODAL).is(':visible') && !eitherModalIsWaiting && !eitherModalIsEmporio) {
		var newModalElements = $(html);
		var element = $(INFO_MODAL_TEXT, newModalElements);
		if (html.includes("<img")) {
			var imageDiv = $(INFO_MODAL_IMAGES, newModalElements);
			$(imageDiv[0]).appendTo(element);
		}
		$(INFO_MODAL_TEXT).prepend(element[0].innerHTML + '<br/><br/>');
	}

	// Otherwise, load the new HTML into the modal and display it.
	else {
		if ($(INFO_MODAL).is(':visible') && html.includes("Waiting")) {
			var element = $(INFO_MODAL_TEXT);
			var textToAppend = "<br/><br/>" + element[0].innerHTML;
			html = html.replace("</p>", textToAppend + "</p>");
		}

		closeInfoModal();
		$(INFO_MODAL).html(html);
		$(INFO_MODAL).modal('show');

		$(INFO_MODAL).draggable({
		    handle: ".modal-header"
		}); 

		$(INFO_MODAL).css({top: "20%", left: 0});
	}

	if (cardsAreBlurred) {
		setCardOpacity(true, lastCardUid);
	}
}

function playCard(uid) {
	if (!cardsAreBlurred && !clickingOnPlayer) {
		if (new Date().getTime() - previousSocketTime >= SOCKET_TIME_DIFFERENCE) {
			socket.emit('validate_card_choice', username, uid);
			lastCardUid = uid;
			updatePreviousSocketTime();
		}
	}
}

function playBlurCard(uid) {
	if (new Date().getTime() - previousSocketTime >= SOCKET_TIME_DIFFERENCE) {
		socket.emit('blur_card_played', username, uid);
		cardsAreBlurred = false;
		updatePreviousSocketTime();
	}
}

function discardCard(uid) {
	if (new Date().getTime() - previousSocketTime >= SOCKET_TIME_DIFFERENCE) {
		socket.emit('discarding_card', username, uid);
		updatePreviousSocketTime();
	}
}

function addBlurToCards(cardNames) {
	$(CARDS_IN_HAND_DIV).find("img").each(function() {
		var cardName = $(this).attr("alt").split(' ')[0];
		var uid = $(this).attr("alt").split(' ')[1];
		
		if (!cardNames.includes(cardName)) {
			$(this).css("opacity", 0.25);
			$(this).css("z-index", 5);
		}
		else {
			$(this).attr("onClick", "playBlurCard(" + uid + ")" ); 
		}
	});
	
	cardsAreBlurred = true;
}

function removeBlurFromCards() {
	$(CARDS_IN_HAND_DIV).find("img").each(function() {
		$(this).css("opacity", 1);
		$(this).removeAttr("onClick"); // If the player is the current player, the click function will be reset by the new cards.
	});
	
	cardsAreBlurred = false;
}

function pickEmporioCard(uid) {
	socket.emit('emporio_card_picked', username, uid);
}

function pickKitCarlsonCard(uid) {
	socket.emit('kit_carlson_card_picked', username, uid);
	closeInfoModal()
}

function setupTooltip() {
	$('a[data-toggle="tooltip"]').tooltip({
	    animated: 'fade',
	    placement: 'top',
	    html: true,
	});

	$('img[data-toggle="tooltip"]').tooltip({
	    animated: 'fade',
	    placement: 'left',
	    html: true,
	});
}

function addDiscardClickFunctions() {
	$(CARDS_IN_HAND_DIV).find("img").each(function() {
		var cardName = $(this).attr("alt").split(' ')[0];
		var uid = $(this).attr("alt").split(' ')[1];

		$(this).attr("onClick", "discardCard(" + uid + ")" );
	});
}

function setPlayerClicks(clickType='') {
	$(".playerInfoColumn").each(function(index, elem) {
		var opponentUsername = $(this).attr("id").substring("player_div_".length);
		if (opponentUsername != username) {
			$(this).attr("onClick", clickType == '' ? '' : "playerClickedOn('" + opponentUsername + "', '" + clickType + "')");
		}
	});
}

function setCardOpacity(add, uid=-1) {
	var cardId = '#hand_card_' + uid.toString();
	var zindexDifference = 100;

	if (add && $(cardId).length) {
		cardsAreBlurred = true;

		$(cardId).css("zIndex", (parseInt($(cardId).css("zIndex")) + zindexDifference).toString());

		$(CARDS_IN_HAND_DIV + " img").each(function() {
			if ($(this).attr("id") != cardId.substring(1)) {
				$(this).css("opacity", 0.25);
			}
		});
	}
	else
	{
		cardsAreBlurred = false;

		$(cardId).css("zIndex", (parseInt($(cardId).css("zIndex")) - zindexDifference).toString());
		
		$(CARDS_IN_HAND_DIV + " img").each(function() {
			$(this).css("opacity", 1);
		});
	}
}

function questionModalIsOpen() {
	return !(isNullOrUndefined($(QUESTION_MODAL).html())) && $(QUESTION_MODAL).is(':visible');
}

function infoModalIsOpen() {
	return !(isNullOrUndefined($(INFO_MODAL).html())) && $(INFO_MODAL).html() != '';
}

function waitingModalIsOpen() {
	return !(isNullOrUndefined($(INFO_MODAL).html())) && $(INFO_MODAL).html().includes("Waiting");
}

function emporioModalIsOpen() {
	return !(isNullOrUndefined($(INFO_MODAL).html())) && $(INFO_MODAL).html().includes("Emporio</h4>") &&
			!($(INFO_MODAL).html().includes("Everyone is done") || $(INFO_MODAL).html().includes("You picked up"));
}

function kitCarlsonModalIsOpen() {
	return !(isNullOrUndefined($(INFO_MODAL).html())) && $(INFO_MODAL).html().includes("Kit Carlson");
}

function closeInfoModal() {
	$(INFO_MODAL).modal('hide');
	$(INFO_MODAL).html('');
}

function createCardHand(cardInfo) {
	lastCardUid = 0;
	var minimumCardsForOverlap = 4;
	var numberOfCards = cardInfo.length;

	var cardsInHandSpanId = "cardsInHandSpan";
	$(CARDS_IN_HAND_DIV).html("<span id='" + cardsInHandSpanId + "' class='centered centered_text'></span>");

	if (numberOfCards > 0) {
		if (numberOfCards >= minimumCardsForOverlap) {
			var cardWidth = Math.floor($(CARDS_IN_HAND_DIV).outerWidth() / numberOfCards);
			var overlapWidth = Math.floor(cardWidth / 5);
			var cardsWidth = (2 * (cardWidth - overlapWidth)) + ((numberOfCards - 2) * (cardWidth - overlapWidth - overlapWidth));
		}
		else {
			var cardWidth = Math.floor($(CARDS_IN_HAND_DIV).outerWidth() / minimumCardsForOverlap);
			var overlapWidth = -25;
			var cardsWidth = (numberOfCards * cardWidth) + ((numberOfCards - 1) * Math.abs(overlapWidth));
		}
		
		var bufferWidth = Math.floor(($(CARDS_IN_HAND_DIV).outerWidth() - cardsWidth) / (numberOfCards >= minimumCardsForOverlap ? 4 : 2));
		var cardWidthPercent = (cardWidth * 100) / $(CARDS_IN_HAND_DIV).outerWidth();
		var overlapWidthPercent = (overlapWidth * 100) / $(CARDS_IN_HAND_DIV).outerWidth();
		var imageLeftXPercent = (bufferWidth * 100) / $(CARDS_IN_HAND_DIV).outerWidth();

		for (var i = 0; i < numberOfCards; i++) {
			var url = "static/images/cards/actions/" + cardInfo[i].uid.toString() + ".jpg";
			var zoom_size = numberOfCards >= minimumCardsForOverlap ? (numberOfCards >= minimumCardsForOverlap * 2 ? "2" : "1_5") : "1_2"
			var img = $('<img id="hand_card_' + cardInfo[i].uid.toString() + '" class="zoom_hover_' + zoom_size + '">');
			img.attr('src', url);
			img.attr('alt', cardInfo[i].name + " " + cardInfo[i].uid.toString())
			
			if (cardInfo[i].isCurrentPlayer) {
				img.attr('onclick', "playCard(" + cardInfo[i].uid.toString() + ")");
			}

			img.css({"position": "absolute", "max-width": cardWidthPercent.toString() + '%', "z-index": 10+i, "margin-left": imageLeftXPercent + "%"});

			img.appendTo(CARDS_IN_HAND_DIV);
			setImageAfterLoading(img);

			imageLeftXPercent += (cardWidthPercent - overlapWidthPercent);
		}
	}

	var usernameText = "<span style='color: red;'>" + username + "</span>, ";
	var cardText = cardInfo.length > 0 ? "your current hand is:" : "you have no cards in your hand."
	$("#" + cardsInHandSpanId).html(usernameText + cardText);
	$("#" + cardsInHandSpanId).css("margin-top", "3%");
	$("#" + cardsInHandSpanId).addClass("play-text-header");
}

function setImageAfterLoading(img){
	window.setTimeout(function() {
	    if (img.outerHeight() != 0) {
			var marginTop = Math.floor(($(CARDS_IN_HAND_DIV).outerHeight() - img.outerHeight()) / 4);
			img.css("bottom", marginTop.toString() + "px");
			img.show();
	    }
	    else {
	    	img.hide();
			setImageAfterLoading(img);
	    }
	}, 100);
}

function returnToLobby() {
	socket.emit('return_to_lobby', username);
}

function rejoinGame() {
	socket.emit('rejoin_game', username);
}

function playerClickedOn(targetName, clickType) {
	if (new Date().getTime() - previousSocketTime >= (SOCKET_TIME_DIFFERENCE / 2)) {
		socket.emit('player_clicked_on', username, targetName, clickType);
		clickingOnPlayer = false;
		updatePreviousSocketTime();
	}
}

function updatePreviousSocketTime() {
	previousSocketTime = new Date().getTime();
}

/* Key press functions to enable players to send messages to the server using keyboard strokes. */

$(document).keydown(function (e) {
	var isRepeating = !!keysPressed[e.which];

	if (!isRepeating) {
	    keysPressed[e.which] = true;
	    var numKeys = Object.keys(keysPressed).length;

	    if (numKeys == 2) {
		    if (16 in keysPressed) {
			    if (e.which == 69) { // Shift-E, to end the turn.
			    	socket.emit('ending_turn', username);
			    }

			    else if (e.which == 67) { // Shift-C, to cancel the current action.
			    	socket.emit('cancel_current_action', username);
			    	lastCardUid = 0;
		    		setCardOpacity(false);
		    		clickingOnPlayer = false;
		    		setPlayerClicks();
			    }

			    else if (e.which == 83) { // Shift-S, to trigger a special ability when applicable.
			    	socket.emit('use_special_ability', username);
			    }
			}
		}

		if (numKeys == 1) {
			if (13 in keysPressed) { // Enter, to close the info modal if it's open.
				if ($(QUESTION_MODAL).is(':visible')) {
					e.preventDefault();
				}

				if (!waitingModalIsOpen() && !emporioModalIsOpen() && !kitCarlsonModalIsOpen()) {
					closeInfoModal();
				}
			}
		}
	}
});

$(document).keyup(function (e) {
    delete keysPressed[e.which];
});