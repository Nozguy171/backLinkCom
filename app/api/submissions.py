import json
import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.constants import SUBMISSION_TYPES
from app.extensions import db
from app.models import Submission, Supplier, User
from app.utils.uploads import save_uploaded_document


submissions_bp = Blueprint("submissions", __name__)


EDITABLE_STATUSES = {"pending", "in_review", "approved", "rejected"}


def _normalize_special_request_data(raw_data: dict) -> dict:
    data = raw_data or {}

    return {
        "request_kind": (data.get("request_kind") or "").strip().lower(),
        "product_name": (data.get("product_name") or "").strip(),
        "specifications": (data.get("specifications") or "").strip(),
        "quantity": (data.get("quantity") or "").strip(),
        "attachment_url": (data.get("attachment_url") or "").strip() or None,
        "admin_comment": (data.get("admin_comment") or "").strip() or None,
        "rejection_reason": (data.get("rejection_reason") or "").strip() or None,
    }


def _resolve_supplier_uuid(raw_supplier_id):
    if not raw_supplier_id:
        return None

    try:
        supplier_uuid = uuid.UUID(str(raw_supplier_id))
    except ValueError:
        raise ValueError("supplier_id inválido")

    supplier = db.session.get(Supplier, supplier_uuid)
    if not supplier:
        raise ValueError("Proveedor no encontrado")

    return supplier_uuid


@submissions_bp.post("/submissions")
@jwt_required()
def create_submission():
    user = db.session.get(User, uuid.UUID(get_jwt_identity()))
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    is_form = bool(request.content_type and "multipart/form-data" in request.content_type)

    if is_form:
        submission_type = (request.form.get("submission_type") or "").strip().lower()
        supplier_id = request.form.get("supplier_id")
        notes = (request.form.get("notes") or "").strip() or None

        data = {
            "request_kind": (request.form.get("request_kind") or "").strip().lower(),
            "product_name": (request.form.get("product_name") or "").strip(),
            "specifications": (request.form.get("specifications") or "").strip(),
            "quantity": (request.form.get("quantity") or "").strip(),
        }

        attachment = request.files.get("attachment")
        if attachment and attachment.filename:
            data["attachment_url"] = save_uploaded_document(attachment, "special_requests")
    else:
        payload = request.get_json(silent=True) or {}
        submission_type = (payload.get("submission_type") or "").strip().lower()
        supplier_id = payload.get("supplier_id")
        notes = (payload.get("notes") or "").strip() or None
        data = payload.get("data") or {}

    if submission_type not in SUBMISSION_TYPES:
        return jsonify({"error": "submission_type inválido"}), 400

    data = _normalize_special_request_data(data)

    if not data["request_kind"]:
        return jsonify({"error": "request_kind es obligatorio"}), 400

    if data["request_kind"] not in {"new_product", "custom_spec"}:
        return jsonify({"error": "request_kind inválido"}), 400

    if not data["product_name"]:
        return jsonify({"error": "product_name es obligatorio"}), 400

    if not data["specifications"]:
        return jsonify({"error": "specifications es obligatorio"}), 400

    if not data["quantity"]:
        return jsonify({"error": "quantity es obligatorio"}), 400

    try:
        supplier_uuid = _resolve_supplier_uuid(supplier_id)
    except ValueError as exc:
        message = str(exc)
        return jsonify({"error": message}), 400 if "inválido" in message else 404

    submission = Submission(
        user_id=user.id,
        supplier_id=supplier_uuid,
        submission_type=submission_type,
        status="pending",
        data=data,
        notes=notes,
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify({"submission": submission.to_dict()}), 201


@submissions_bp.get("/submissions")
@jwt_required()
def list_submissions():
    claims = get_jwt()
    user_id = uuid.UUID(get_jwt_identity())

    submission_type = (request.args.get("submission_type") or "").strip().lower()
    status = (request.args.get("status") or "").strip().lower()

    query = Submission.query

    if claims.get("role") != "admin":
        query = query.filter_by(user_id=user_id)

    if submission_type:
        query = query.filter_by(submission_type=submission_type)

    if status:
        query = query.filter_by(status=status)

    items = query.order_by(Submission.created_at.desc()).all()
    return jsonify({"items": [item.to_dict() for item in items]})


@submissions_bp.get("/submissions/<uuid:submission_id>")
@jwt_required()
def get_submission(submission_id):
    claims = get_jwt()
    user_id = uuid.UUID(get_jwt_identity())
    item = Submission.query.filter_by(id=submission_id).first()
    if not item:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    if claims.get("role") != "admin" and item.user_id != user_id:
        return jsonify({"error": "No tienes acceso a esta solicitud"}), 403

    return jsonify({"submission": item.to_dict()})


@submissions_bp.patch("/submissions/<uuid:submission_id>")
@jwt_required()
def update_submission(submission_id):
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Solo un administrador puede actualizar solicitudes"}), 403

    item = Submission.query.filter_by(id=submission_id).first()
    if not item:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    payload = request.get_json(silent=True) or {}
    new_status = (payload.get("status") or "").strip().lower()
    admin_comment = (payload.get("admin_comment") or "").strip() or None
    rejection_reason = (payload.get("rejection_reason") or "").strip() or None

    if new_status not in EDITABLE_STATUSES:
        return jsonify({"error": "status inválido"}), 400

    if new_status == "rejected" and not rejection_reason:
        return jsonify({"error": "rejection_reason es obligatorio al rechazar"}), 400

    current_data = item.data or {}
    next_data = {
        **current_data,
        "admin_comment": admin_comment,
        "rejection_reason": rejection_reason,
    }

    item.status = new_status
    item.data = next_data

    db.session.commit()
    return jsonify({"submission": item.to_dict()})