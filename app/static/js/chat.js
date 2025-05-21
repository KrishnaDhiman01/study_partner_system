const messagesArea = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const chatHeader = document.querySelector('.chat-header');

let socket = null;
let initialHistoryLoaded = false;

function scrollToBottom() {
    if (messagesArea) {
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }
}

function displayMessage(data, isHistory = false) {
    if (!messagesArea) return;

    if (data.message_id && document.getElementById(`msg-${data.message_id}`)) {
        console.log("Skipping duplicate message ID:", data.message_id);
        return;
    }

    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    if (data.message_id) {
        msgDiv.id = `msg-${data.message_id}`;
    }

    const senderSpan = document.createElement('span');
    senderSpan.classList.add('sender');

    if (data.sender_id === CURRENT_USER_ID) {
        msgDiv.classList.add('sent');
        senderSpan.textContent = 'You';
    } else {
        msgDiv.classList.add('received');
        senderSpan.textContent = data.sender_name || 'Unknown User';
    }

    const contentP = document.createElement('p');
    contentP.textContent = data.content;

    const timeSpan = document.createElement('span');
    timeSpan.classList.add('timestamp');
    timeSpan.dataset.timestamp = data.timestamp;
    try {
        const msgDate = new Date(data.timestamp);
        timeSpan.textContent = msgDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        timeSpan.title = msgDate.toLocaleString();
    } catch (e) {
        timeSpan.textContent = 'Invalid time';
    }

    msgDiv.appendChild(senderSpan);
    msgDiv.appendChild(contentP);
    msgDiv.appendChild(timeSpan);

    const initialStatus = messagesArea.querySelector('.status-message.placeholder');
    if (initialStatus) {
        initialStatus.remove();
    }

    if (isHistory) {
        messagesArea.insertBefore(msgDiv, messagesArea.firstChild);
    } else {
        messagesArea.appendChild(msgDiv);
    }

    if (!isHistory || messagesArea.scrollHeight - messagesArea.scrollTop < messagesArea.clientHeight + 150) {
         scrollToBottom();
    }
}

function displayStatusMessage(message, isPlaceholder = false) {
     if (!messagesArea) return;
     const statusDiv = document.createElement('div');
     statusDiv.classList.add('status-message');
     if (isPlaceholder) {
         statusDiv.classList.add('placeholder');
     }
     statusDiv.textContent = message;
     messagesArea.appendChild(statusDiv);
     scrollToBottom();
}

function sendMessage() {
    const messageContent = messageInput.value.trim();
    if (messageContent && ROOM_NAME && socket && socket.connected) {
        socket.emit('send_message', {
            room: ROOM_NAME,
            message: messageContent
        });
        messageInput.value = '';
        messageInput.focus();
    } else if (!socket || !socket.connected) {
        displayStatusMessage("Connection lost. Cannot send message.");
    } else if (!ROOM_NAME) {
         console.error("Cannot send message: Room name not defined.");
    }
}

function setupSocketIO() {
    if (!io) { console.error("Socket.IO client library not loaded."); displayStatusMessage("Error loading chat."); return; }

    socket = io({ transports: ['websocket'] });

    socket.on('connect', () => {
        console.log('Socket connected:', socket.id);
        if (chatHeader) chatHeader.style.borderColor = 'lightgreen';
        if (ROOM_NAME) {
            console.log(`Attempting to join room: ${ROOM_NAME}`);
            socket.emit('join_room', { room: ROOM_NAME });
        } else {
            console.error("Room name missing."); displayStatusMessage("Error: Chat room missing.");
        }
    });

    socket.on('disconnect', (reason) => {
        console.log('Socket disconnected:', reason);
        if (chatHeader) chatHeader.style.borderColor = 'lightcoral';
        displayStatusMessage(`Disconnected: ${reason}. Retrying...`);
    });

    socket.on('connect_error', (err) => {
        console.error('Socket Connection Error:', err);
        if (chatHeader) chatHeader.style.borderColor = 'lightcoral';
        displayStatusMessage(`Connection Failed: ${err.message}`);
    });

    socket.on('connection_status', (data) => {
        console.log('Server Connection Status:', data);
        if (!data.authenticated) {
            displayStatusMessage('Authentication error.');
            if(messageInput) messageInput.disabled = true;
            if(sendButton) sendButton.disabled = true;
        }
    });

    socket.on('room_joined', (data) => {
        console.log(`Joined Room: ${data.room}`);
        displayStatusMessage(data.message);
        if(messageInput) messageInput.disabled = false;
        if(sendButton) sendButton.disabled = false;
        messageInput?.focus();
        initialHistoryLoaded = false;
        messagesArea.innerHTML = '';
        displayStatusMessage("Loading message history...", true);
    });

    socket.on('message_history', (data) => {
        if (data.room === ROOM_NAME) {
            console.log(`Received history for room ${data.room}:`, data.history);
            const placeholder = messagesArea.querySelector('.status-message.placeholder');
            if (placeholder) placeholder.remove();

            if (data.history && data.history.length > 0) {
                data.history.forEach(msgData => {
                    displayMessage(msgData, true);
                });
                console.log("Message history loaded.");
            } else {
                 displayStatusMessage("No previous messages found.", true);
            }
            initialHistoryLoaded = true;
        }
    });

    socket.on('room_left', (data) => { console.log(`Left Room: ${data.room}`); displayStatusMessage(data.message);});
    socket.on('user_joined', (data) => { displayStatusMessage(`${data.user_name || 'Someone'} joined.`); });
    socket.on('user_left', (data) => { displayStatusMessage(`${data.user_name || 'Someone'} left.`); });
    socket.on('receive_message', (data) => { displayMessage(data); });
    socket.on('error', (data) => { console.error('Server Error:', data.message); displayStatusMessage(`Error: ${data.message}`); });
}

document.addEventListener('DOMContentLoaded', () => {
    if (typeof CURRENT_USER_ID === 'undefined' || CURRENT_USER_ID === null) {
        displayStatusMessage("Error: Cannot initiate chat. User not identified."); return;
    }
    if (typeof ROOM_NAME === 'undefined' || !ROOM_NAME) {
         displayStatusMessage("Error: Cannot initiate chat. Room not identified."); return;
    }
    if (sendButton && messageInput) {
        sendButton.addEventListener('click', sendMessage);
        messageInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); }
        });
    } else { console.error("Chat input or send button not found."); }

    setupSocketIO();
});
