from datetime import datetime, timezone
import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.extensions import db
from app.models import ChatConversation, ChatMessage, User


chat_bp = Blueprint('chat', __name__)


def _current_user():
    return db.session.get(User, uuid.UUID(get_jwt_identity()))


@chat_bp.get('/conversations')
@jwt_required()
def list_conversations():
    claims = get_jwt()
    user_id = uuid.UUID(get_jwt_identity())

    if claims.get('role') == 'admin':
        conversations = ChatConversation.query.order_by(ChatConversation.last_message_at.desc().nullslast()).all()
    else:
        conversations = ChatConversation.query.filter_by(user_id=user_id).order_by(ChatConversation.last_message_at.desc().nullslast()).all()

    return jsonify({'items': [conversation.to_dict(include_last_message=True) for conversation in conversations]})


@chat_bp.post('/conversations')
@jwt_required()
def create_or_get_conversation():
    user = _current_user()
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    payload = request.get_json(silent=True) or {}
    opening_message = (payload.get('message') or '').strip()

    if user.role == 'admin':
        target_user_id = payload.get('user_id')
        if not target_user_id:
            return jsonify({'error': 'user_id es obligatorio para un admin'}), 400
        target_user_uuid = uuid.UUID(target_user_id)
        conversation = ChatConversation.query.filter_by(user_id=target_user_uuid).first()
        if not conversation:
            conversation = ChatConversation(user_id=target_user_uuid, assigned_admin_id=user.id)
            db.session.add(conversation)
            db.session.flush()
    else:
        conversation = ChatConversation.query.filter_by(user_id=user.id).first()
        if not conversation:
            first_admin = User.query.filter_by(role='admin').order_by(User.created_at.asc()).first()
            conversation = ChatConversation(user_id=user.id, assigned_admin_id=first_admin.id if first_admin else None)
            db.session.add(conversation)
            db.session.flush()

    if opening_message:
        message = ChatMessage(
            conversation_id=conversation.id,
            sender_user_id=user.id,
            sender_role='admin' if user.role == 'admin' else 'user',
            content=opening_message,
            is_read=False,
        )
        conversation.last_message_at = datetime.now(timezone.utc)
        db.session.add(message)

    db.session.commit()
    return jsonify({'conversation': conversation.to_dict(include_last_message=True)}), 201


@chat_bp.get('/conversations/<uuid:conversation_id>/messages')
@jwt_required()
def list_messages(conversation_id):
    user = _current_user()
    conversation = ChatConversation.query.filter_by(id=conversation_id).first()
    if not conversation:
        return jsonify({'error': 'Conversación no encontrada'}), 404

    if user.role != 'admin' and conversation.user_id != user.id:
        return jsonify({'error': 'No tienes acceso a esta conversación'}), 403

    messages = ChatMessage.query.filter_by(conversation_id=conversation_id).order_by(ChatMessage.created_at.asc()).all()
    return jsonify({'items': [message.to_dict() for message in messages]})


@chat_bp.post('/conversations/<uuid:conversation_id>/messages')
@jwt_required()
def send_message(conversation_id):
    user = _current_user()
    conversation = ChatConversation.query.filter_by(id=conversation_id).first()
    if not conversation:
        return jsonify({'error': 'Conversación no encontrada'}), 404

    if user.role != 'admin' and conversation.user_id != user.id:
        return jsonify({'error': 'No tienes acceso a esta conversación'}), 403

    payload = request.get_json(silent=True) or {}
    content = (payload.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'El contenido es obligatorio'}), 400

    if user.role == 'admin' and conversation.assigned_admin_id is None:
        conversation.assigned_admin_id = user.id

    message = ChatMessage(
        conversation_id=conversation.id,
        sender_user_id=user.id,
        sender_role='admin' if user.role == 'admin' else 'user',
        content=content,
        is_read=False,
    )
    conversation.last_message_at = datetime.now(timezone.utc)
    db.session.add(message)
    db.session.commit()

    return jsonify({'message': message.to_dict()}), 201


@chat_bp.patch('/conversations/<uuid:conversation_id>/read')
@jwt_required()
def mark_conversation_read(conversation_id):
    user = _current_user()
    conversation = ChatConversation.query.filter_by(id=conversation_id).first()
    if not conversation:
        return jsonify({'error': 'Conversación no encontrada'}), 404

    if user.role != 'admin' and conversation.user_id != user.id:
        return jsonify({'error': 'No tienes acceso a esta conversación'}), 403

    sender_role_to_mark = 'user' if user.role == 'admin' else 'admin'
    updated = (
        ChatMessage.query.filter_by(conversation_id=conversation_id, sender_role=sender_role_to_mark, is_read=False)
        .update({'is_read': True}, synchronize_session=False)
    )
    db.session.commit()

    return jsonify({'updated': updated})
