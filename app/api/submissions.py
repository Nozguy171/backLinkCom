import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.constants import SUBMISSION_TYPES
from app.extensions import db
from app.models import Submission, Supplier, User


submissions_bp = Blueprint('submissions', __name__)


@submissions_bp.post('/submissions')
@jwt_required()
def create_submission():
    user = db.session.get(User, uuid.UUID(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    payload = request.get_json(silent=True) or {}
    submission_type = (payload.get('submission_type') or '').strip().lower()
    supplier_id = payload.get('supplier_id')
    data = payload.get('data') or {}
    notes = (payload.get('notes') or '').strip() or None

    if submission_type not in SUBMISSION_TYPES:
        return jsonify({'error': 'submission_type inválido'}), 400
    if not isinstance(data, dict) or not data:
        return jsonify({'error': 'data debe ser un objeto JSON con contenido'}), 400

    supplier_uuid = None
    if supplier_id:
        supplier_uuid = uuid.UUID(supplier_id)
        supplier = db.session.get(Supplier, supplier_uuid)
        if not supplier:
            return jsonify({'error': 'Proveedor no encontrado'}), 404

    submission = Submission(
        user_id=user.id,
        supplier_id=supplier_uuid,
        submission_type=submission_type,
        status='pending',
        data=data,
        notes=notes,
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify({'submission': submission.to_dict()}), 201


@submissions_bp.get('/submissions')
@jwt_required()
def list_submissions():
    claims = get_jwt()
    user_id = uuid.UUID(get_jwt_identity())

    if claims.get('role') == 'admin':
        items = Submission.query.order_by(Submission.created_at.desc()).all()
    else:
        items = Submission.query.filter_by(user_id=user_id).order_by(Submission.created_at.desc()).all()

    return jsonify({'items': [item.to_dict() for item in items]})


@submissions_bp.get('/submissions/<uuid:submission_id>')
@jwt_required()
def get_submission(submission_id):
    claims = get_jwt()
    user_id = uuid.UUID(get_jwt_identity())
    item = Submission.query.filter_by(id=submission_id).first()
    if not item:
        return jsonify({'error': 'Solicitud no encontrada'}), 404

    if claims.get('role') != 'admin' and item.user_id != user_id:
        return jsonify({'error': 'No tienes acceso a esta solicitud'}), 403

    return jsonify({'submission': item.to_dict()})
