from __future__ import annotations

import re
import time
import uuid
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _detect_card_brand(card_number: str) -> str:
    digits = _only_digits(card_number)

    if re.match(r"^4", digits):
      return "visa"

    if re.match(r"^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))", digits):
      return "mastercard"

    if re.match(r"^3[47]", digits):
      return "amex"

    return "desconocida"


def _luhn_is_valid(card_number: str) -> bool:
    digits = _only_digits(card_number)
    if not digits:
        return False

    total = 0
    reverse_digits = digits[::-1]

    for index, digit_char in enumerate(reverse_digits):
        digit = int(digit_char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return total % 10 == 0


def _user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "company": user.company,
        "phone": user.phone,
    }


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    email = _normalize_email(data.get("email", ""))
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"message": "Correo y contraseña son obligatorios."}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"message": "Credenciales inválidas."}), 401

    user.last_login = datetime.now(UTC)
    db.session.commit()

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )

    return jsonify(
        {
            "message": "Inicio de sesión exitoso.",
            "access_token": access_token,
            "user": _user_payload(user),
        }
    ), 200

@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = _normalize_email(data.get("email", ""))
    password = data.get("password", "")
    company = (data.get("company") or "").strip() or None
    phone = (data.get("phone") or "").strip() or None

    payment = data.get("payment") or {}
    card_name = (payment.get("card_name") or "").strip()
    card_number = _only_digits(payment.get("card_number", ""))
    expiry_month = str(payment.get("expiry_month", "")).strip()
    expiry_year = str(payment.get("expiry_year", "")).strip()
    cvv = _only_digits(payment.get("cvv", ""))

    if not name or not email or not password:
        return jsonify({"message": "Nombre, correo y contraseña son obligatorios."}), 400

    if len(password) < 6:
        return jsonify({"message": "La contraseña debe tener al menos 6 caracteres."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Ese correo ya está registrado."}), 409

    if not card_name or not card_number or not expiry_month or not expiry_year or not cvv:
        return jsonify({"message": "Completa los datos de pago."}), 400

    if len(card_number) < 13:
        return jsonify({"message": "Ingresa un número de tarjeta válido."}), 400

    if not expiry_month.isdigit() or int(expiry_month) < 1 or int(expiry_month) > 12:
        return jsonify({"message": "Mes de vencimiento inválido."}), 400

    if not expiry_year.isdigit():
        return jsonify({"message": "Año de vencimiento inválido."}), 400

    if len(expiry_year) == 2:
        expiry_year = f"20{expiry_year}"
    elif len(expiry_year) != 4:
        return jsonify({"message": "Año de vencimiento inválido."}), 400

    if len(cvv) not in (3, 4):
        return jsonify({"message": "CVV inválido."}), 400

    brand = _detect_card_brand(card_number)
    if brand == "desconocida":
        brand = "tarjeta"

    time.sleep(1.8)

    user = User(
        name=name,
        email=email,
        role="user",
        company=company,
        phone=phone,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    payment_reference = f"LCM-{int(time.time())}"
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )

    return jsonify(
        {
            "message": "Cuenta creada correctamente.",
            "access_token": access_token,
            "user": _user_payload(user),
            "payment": {
                "status": "approved",
                "reference": payment_reference,
                "brand": brand,
                "last4": card_number[-4:],
            },
        }
    ), 201


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = uuid.UUID(str(get_jwt_identity()))
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"message": "Usuario no encontrado."}), 404

    return jsonify({"user": _user_payload(user)}), 200


@auth_bp.patch("/me")
@jwt_required()
def update_me():
    user_id = uuid.UUID(str(get_jwt_identity()))
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"message": "Usuario no encontrado."}), 404

    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = _normalize_email(data.get("email", ""))
    company = (data.get("company") or "").strip() or None
    phone = (data.get("phone") or "").strip() or None
    password = (data.get("password") or "").strip()

    if not name:
        return jsonify({"message": "El nombre es obligatorio."}), 400

    if not email:
        return jsonify({"message": "El correo es obligatorio."}), 400

    existing = User.query.filter(User.email == email, User.id != user.id).first()
    if existing:
        return jsonify({"message": "Ese correo ya está en uso."}), 409

    user.name = name
    user.email = email
    user.company = company
    user.phone = phone

    if password:
        if len(password) < 6:
            return jsonify({"message": "La contraseña debe tener al menos 6 caracteres."}), 400
        user.set_password(password)

    db.session.commit()

    return jsonify({
        "message": "Perfil actualizado correctamente.",
        "user": _user_payload(user),
    }), 200