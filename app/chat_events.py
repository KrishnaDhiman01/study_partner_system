from flask import session, current_app, request
from flask_socketio import emit, join_room, leave_room
from . import socketio
from .models import db, User, Message, StudyGroup
import traceback

def is_logged_in_socket():
    return 'user_id' in session and session.get('user_id') is not None

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if not user_id:
        current_app.logger.info(f"Unauthenticated Socket.IO connection attempt from SID: {request.sid}. Disconnecting.")
        emit('error', {'message': 'Authentication required for chat.'}, room=request.sid)
        return False
    else:
        user = User.query.get(user_id)
        user_name = getattr(user, 'name', 'Unknown User')
        join_room(f'user_room_{user_id}')
        current_app.logger.info(f"Client connected: SID={request.sid}, UserID={user_id}, Name='{user_name}'. Joined user_room_{user_id}.")
        emit('connection_status', {
            'status': 'connected', 
            'authenticated': True, 
            'user_id': user_id, 
            'user_name': user_name
        }, room=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'N/A')
    current_app.logger.info(f"Client disconnected: SID={request.sid}, UserID={user_id}, Name='{user_name}'")

@socketio.on('join_room')
def handle_join_room(data):
    if not is_logged_in_socket():
        emit('error', {'message': 'Authentication required to join rooms.'}, room=request.sid)
        return

    room_name = data.get('room')
    user_id = session['user_id']
    user_name = session.get('user_name', 'Anonymous')

    if not room_name:
        emit('error', {'message': 'Room name not provided.'}, room=request.sid)
        return

    is_allowed = False
    target_id_for_history = None 
    chat_type_for_history = None

    if room_name.startswith('user_'):
        try:
            ids_str = room_name.split('_')[1:]
            participant_ids = [int(id_str) for id_str in ids_str]
            if user_id in participant_ids and len(participant_ids) == 2:
                is_allowed = True
                target_id_for_history = participant_ids[1] if user_id == participant_ids[0] else participant_ids[0]
                chat_type_for_history = 'user'
        except (IndexError, ValueError) as e:
            current_app.logger.warning(f"Error parsing user room name '{room_name}': {e}")
            is_allowed = False
            
    elif room_name.startswith('group_'):
        try:
            group_id_str = room_name.split('_')[1]
            group_id = int(group_id_str)
            user = User.query.get(user_id)
            group = StudyGroup.query.get(group_id)
            if user and group and user in group.members:
                is_allowed = True
                target_id_for_history = group_id
                chat_type_for_history = 'group'
        except (IndexError, ValueError) as e:
            current_app.logger.warning(f"Error parsing group room name '{room_name}': {e}")
            is_allowed = False
        except Exception as e:
            current_app.logger.error(f"DB Error checking group membership for room {room_name}: {e}")
            is_allowed = False

    if is_allowed:
        join_room(room_name)
        current_app.logger.info(f"User '{user_name}' (ID: {user_id}, SID: {request.sid}) joined chat room: {room_name}")
        emit('room_joined', {'room': room_name, 'message': f"You have joined '{room_name}'."}, room=request.sid)
        socketio.emit('user_joined', {'user_name': user_name, 'room': room_name}, room=room_name, skip_sid=request.sid)

        try:
            message_history_query = None
            limit = 50

            if chat_type_for_history == 'user' and target_id_for_history:
                ids = sorted([user_id, target_id_for_history])
                message_history_query = Message.query.filter(
                    Message.group_id.is_(None),
                    ((Message.sender_id == ids[0]) & (Message.recipient_id == ids[1])) |
                    ((Message.sender_id == ids[1]) & (Message.recipient_id == ids[0]))
                )
            elif chat_type_for_history == 'group' and target_id_for_history:
                message_history_query = Message.query.filter_by(group_id=target_id_for_history)

            if message_history_query:
                 recent_messages = message_history_query.options(db.joinedload(Message.author))\
                                                     .order_by(Message.timestamp.desc()).limit(limit).all()
                 recent_messages.reverse()

                 history_data = [{
                     'sender_id': msg.sender_id,
                     'sender_name': getattr(msg.author, 'name', 'System'),
                     'content': msg.content,
                     'room': room_name, 
                     'timestamp': msg.timestamp.isoformat() + "Z",
                     'message_id': msg.id
                 } for msg in recent_messages]
                 emit('message_history', {'room': room_name, 'history': history_data}, room=request.sid)
                 current_app.logger.info(f"Sent {len(history_data)} historical messages to SID {request.sid} for room {room_name}")
            else:
                current_app.logger.warning(f"Message history query not formed for room {room_name}, type {chat_type_for_history}")

        except Exception as e:
             current_app.logger.error(f"Error fetching/sending history for room {room_name}: {e}\n{traceback.format_exc()}")
             emit('error', {'message': 'Could not load message history.'}, room=request.sid)
    else:
        current_app.logger.warning(f"User '{user_name}' (ID: {user_id}) denied access to room: {room_name}")
        emit('error', {'message': f"Access denied to room '{room_name}'. You may not be a member or the room is invalid."}, room=request.sid)

@socketio.on('leave_room')
def handle_leave_room(data):
    if not is_logged_in_socket(): return

    room_name = data.get('room')
    user_id = session['user_id']
    user_name = session.get('user_name', 'Anonymous')

    if not room_name: return

    leave_room(room_name)
    current_app.logger.info(f"User '{user_name}' (ID: {user_id}, SID: {request.sid}) left room: {room_name}")
    socketio.emit('user_left', {'user_name': user_name, 'room': room_name}, room=room_name, skip_sid=request.sid)

@socketio.on('send_message')
def handle_send_message(data):
    if not is_logged_in_socket():
        emit('error', {'message': 'Authentication required to send messages.'}, room=request.sid)
        return

    room_name = data.get('room')
    message_content = data.get('message', '').strip()
    user_id = session['user_id']
    sender_name = session.get('user_name', 'Anonymous')

    if not room_name or not message_content:
        emit('error', {'message': 'Missing room name or message content.'}, room=request.sid)
        return

    recipient_id, group_id_for_msg, is_valid_target = None, None, False
    
    if room_name.startswith('user_'):
        try:
            ids_str = room_name.split('_')[1:]
            participant_ids = [int(id_str) for id_str in ids_str]
            if user_id in participant_ids and len(participant_ids) == 2:
                recipient_id = participant_ids[1] if user_id == participant_ids[0] else participant_ids[0]
                is_valid_target = True
        except (IndexError, ValueError): pass
            
    elif room_name.startswith('group_'):
        try:
            group_id_str = room_name.split('_')[1]
            group_id_for_msg = int(group_id_str)
            user = User.query.get(user_id)
            group = StudyGroup.query.get(group_id_for_msg)
            if user and group and user in group.members:
                is_valid_target = True
        except (IndexError, ValueError): pass
        except Exception as e: current_app.logger.error(f"DB error checking group membership for send_message in {room_name}: {e}")

    if not is_valid_target:
        emit('error', {'message': 'Invalid recipient or group for message.'}, room=request.sid)
        current_app.logger.warning(f"Invalid target for message from user {user_id} to room {room_name}.")
        return

    try:
        new_msg = Message(
            sender_id=user_id, 
            recipient_id=recipient_id,
            group_id=group_id_for_msg,
            content=message_content
        )
        db.session.add(new_msg)
        db.session.commit()

        timestamp_iso = new_msg.timestamp.isoformat() + "Z"
        message_data = {
            'sender_id': user_id, 
            'sender_name': sender_name, 
            'content': message_content, 
            'room': room_name,
            'timestamp': timestamp_iso,
            'message_id': new_msg.id
        }
        socketio.emit('receive_message', message_data, room=room_name)
        current_app.logger.info(f"Message (ID: {new_msg.id}) by user {user_id} sent to room {room_name}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving/sending message: {e}\n{traceback.format_exc()}")
        emit('error', {'message': 'Error sending message. Please try again.'}, room=request.sid)
