from datetime import datetime
import json
import uuid
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from slugify import slugify
from sqlalchemy.orm import joinedload

from app.decorators import admin_required
from app.extensions import db
from app.models import (
    Category,
    ChatConversation,
    ChatMessage,
    Product,
    Promotion,
    Submission,
    Supplier,
    SupplierCategory,
    User,
    Video,
    VideoSection,
    VideoSectionLink,
)
from app.utils.uploads import save_uploaded_image, save_uploaded_video
admin_bp = Blueprint("admin", __name__)


def _safe_uuid(value, field_name="id"):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ValueError(f"{field_name} inválido")


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _parse_price(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise ValueError("price inválido")


def _parse_category_ids(raw_value):
    if raw_value is None:
        return []

    if isinstance(raw_value, list):
        return raw_value

    raw_text = str(raw_value).strip()
    if not raw_text:
        return []

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    return [item.strip() for item in raw_text.split(",") if item.strip()]


def _upsert_supplier_categories(supplier: Supplier, category_ids):
    supplier.category_links.clear()
    seen = set()

    for idx, raw_id in enumerate(category_ids or []):
        category_id = _safe_uuid(raw_id, "category_id")
        if category_id in seen:
            continue

        category = db.session.get(Category, category_id)
        if not category:
            raise ValueError(f"category_id no encontrado: {category_id}")

        supplier.category_links.append(
            SupplierCategory(
                category_id=category.id,
                is_primary=(idx == 0),
            )
        )
        seen.add(category_id)

    if not seen:
        raise ValueError("Debes seleccionar al menos una categoría")


def _build_supplier_slug(name: str, current_supplier_id=None):
    base_slug = slugify(name or "")[:255]
    if not base_slug:
        raise ValueError("name es obligatorio")

    candidate = base_slug
    counter = 2

    while True:
        existing = Supplier.query.filter_by(slug=candidate).first()
        if not existing or (current_supplier_id and existing.id == current_supplier_id):
            return candidate

        suffix = f"-{counter}"
        candidate = f"{base_slug[: 255 - len(suffix)]}{suffix}"
        counter += 1


def _get_supplier_primary_category_id(supplier: Supplier):
    links = list(supplier.category_links or [])
    if not links:
        raise ValueError("El proveedor no tiene categorías")

    links.sort(key=lambda link: (not link.is_primary, link.created_at or datetime.min))
    return links[0].category_id


def _parse_section_ids(raw_value):
    return _parse_category_ids(raw_value)


def _build_video_section_slug(name: str, current_section_id=None):
    base_slug = slugify(name or "")[:255]
    if not base_slug:
        raise ValueError("name es obligatorio")

    candidate = base_slug
    counter = 2

    while True:
        existing = VideoSection.query.filter_by(slug=candidate).first()
        if not existing or (current_section_id and existing.id == current_section_id):
            return candidate

        suffix = f"-{counter}"
        candidate = f"{base_slug[: 255 - len(suffix)]}{suffix}"
        counter += 1


def _sync_video_sections(video: Video, section_ids):
    video.section_links.clear()
    seen = set()

    for raw_id in section_ids or []:
        section_id = _safe_uuid(raw_id, "section_id")
        if section_id in seen:
            continue

        section = db.session.get(VideoSection, section_id)
        if not section:
            raise ValueError(f"section_id no encontrado: {section_id}")

        video.section_links.append(VideoSectionLink(section_id=section.id))
        seen.add(section_id)

    if not seen:
        raise ValueError("Debes seleccionar al menos una sección")


def _serialize_video_section(section: VideoSection):
    data = section.to_dict()
    data["videos_count"] = len(section.video_links or [])
    return data


def _title_from_uploaded_filename(filename: str):
    value = (filename or "").strip().replace("\\", "/").split("/")[-1]
    if "." in value:
        value = value.rsplit(".", 1)[0]
    value = value.strip()
    return value or "Video"

def _serialize_admin_user(user: User):
    conversation = None
    if user.conversations:
        conversation = user.conversations[0]

    messages = list(conversation.messages or []) if conversation else []
    last_message = None
    if messages:
        last_message = max(messages, key=lambda item: item.created_at or datetime.min)

    return {
        **user.to_dict(),
        "conversation_id": str(conversation.id) if conversation else None,
        "messages_count": len(messages),
        "unread_from_user_count": sum(
            1 for item in messages if item.sender_role == "user" and not item.is_read
        ),
        "last_message_at": (
            conversation.last_message_at.isoformat()
            if conversation and conversation.last_message_at
            else None
        ),
        "last_message_preview": (
            (last_message.content or "")[:120] if last_message else None
        ),
        "can_open_chat": user.role == "user",
    }

@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    return jsonify(
        {
            "users": User.query.count(),
            "suppliers": Supplier.query.count(),
            "categories": Category.query.count(),
            "products": Product.query.count(),
            "videos": Video.query.count(),
            "submissions_pending": Submission.query.filter_by(status="pending").count(),
            "submissions_total": Submission.query.count(),
            "promotions": Promotion.query.count(),
        }
    )


@admin_bp.get("/categories")
@admin_required
def admin_list_categories():
    items = Category.query.order_by(Category.display_order.asc(), Category.name.asc()).all()
    return jsonify({"items": [item.to_dict() for item in items]})


@admin_bp.post("/categories")
@admin_required
def admin_create_category():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    slug = (payload.get("slug") or slugify(name or ""))[:255]

    if not name or not slug:
        return jsonify({"error": "name es obligatorio"}), 400

    if Category.query.filter_by(slug=slug).first():
        return jsonify({"error": "Ese slug ya existe"}), 409

    item = Category(
        name=name,
        slug=slug,
        icon=(payload.get("icon") or "").strip() or None,
        description=(payload.get("description") or "").strip() or None,
        display_order=payload.get("display_order") or 0,
        is_active=bool(payload.get("is_active", True)),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"category": item.to_dict()}), 201

@admin_bp.get("/suppliers")
@admin_required
def admin_list_suppliers():
    items = Supplier.query.order_by(Supplier.created_at.desc()).all()
    return jsonify({"items": [item.to_dict(include_categories=True) for item in items]})


@admin_bp.get("/suppliers/<uuid:supplier_id>")
@admin_required
def admin_get_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return jsonify({"error": "Proveedor no encontrado"}), 404

    return jsonify({"supplier": supplier.to_dict(include_categories=True, include_products=True)})


@admin_bp.post("/suppliers")
@admin_required
def admin_create_supplier():
    name = (request.form.get("name") or "").strip()

    if not name:
        return jsonify({"error": "name es obligatorio"}), 400

    try:
        slug = _build_supplier_slug(name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        category_ids = _parse_category_ids(request.form.get("category_ids"))
    except Exception:
        return jsonify({"error": "category_ids inválido"}), 400

    supplier = Supplier(
        name=name,
        slug=slug,
        description=(request.form.get("description") or "").strip() or None,
        logo_url=None,
        banner_url=None,
        location=(request.form.get("location") or "").strip() or None,
        rating=0,
        review_count=0,
        years_in_business=None,
        employee_count=None,
        coverage=(request.form.get("coverage") or "national").strip().lower() or "national",
        address=(request.form.get("address") or "").strip() or None,
        website=(request.form.get("website") or "").strip() or None,
        email=(request.form.get("email") or "").strip() or None,
        phone=(request.form.get("phone") or "").strip() or None,
        is_verified=_parse_bool(request.form.get("is_verified"), False),
        is_featured=_parse_bool(request.form.get("is_featured"), False),
        is_active=_parse_bool(request.form.get("is_active"), True),
    )

    logo = request.files.get("logo")

    try:
        if logo and logo.filename:
            supplier.logo_url = save_uploaded_image(logo, "suppliers")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.add(supplier)
    db.session.flush()

    try:
        _upsert_supplier_categories(supplier, category_ids)
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({"supplier": supplier.to_dict(include_categories=True, include_products=True)}), 201


@admin_bp.patch("/suppliers/<uuid:supplier_id>")
@admin_required
def admin_update_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return jsonify({"error": "Proveedor no encontrado"}), 404

    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name es obligatorio"}), 400

    try:
        category_ids = _parse_category_ids(request.form.get("category_ids"))
    except Exception:
        return jsonify({"error": "category_ids inválido"}), 400

    try:
        supplier.slug = _build_supplier_slug(name, supplier.id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    supplier.name = name
    supplier.description = (request.form.get("description") or "").strip() or None
    supplier.location = (request.form.get("location") or "").strip() or None
    supplier.coverage = (request.form.get("coverage") or "national").strip().lower() or "national"
    supplier.address = (request.form.get("address") or "").strip() or None
    supplier.website = (request.form.get("website") or "").strip() or None
    supplier.email = (request.form.get("email") or "").strip() or None
    supplier.phone = (request.form.get("phone") or "").strip() or None
    supplier.is_featured = _parse_bool(request.form.get("is_featured"), supplier.is_featured)
    supplier.is_active = _parse_bool(request.form.get("is_active"), supplier.is_active)

    remove_logo = _parse_bool(request.form.get("remove_logo"), False)
    logo = request.files.get("logo")

    if remove_logo:
        supplier.logo_url = None

    try:
        if logo and logo.filename:
            supplier.logo_url = save_uploaded_image(logo, "suppliers")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        _upsert_supplier_categories(supplier, category_ids)
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({"supplier": supplier.to_dict(include_categories=True, include_products=True)}), 200


@admin_bp.delete("/suppliers/<uuid:supplier_id>")
@admin_required
def admin_delete_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return jsonify({"error": "Proveedor no encontrado"}), 404

    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"message": "Proveedor eliminado correctamente."}), 200


@admin_bp.post("/suppliers/<uuid:supplier_id>/products")
@admin_required
def admin_create_supplier_product(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return jsonify({"error": "Proveedor no encontrado"}), 404

    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"error": "El nombre del producto es obligatorio"}), 400

    description = (request.form.get("description") or "").strip() or None

    try:
        price = _parse_price(request.form.get("price"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    category_raw = (request.form.get("category_id") or "").strip()

    try:
        category_id = _safe_uuid(category_raw, "category_id") if category_raw else _get_supplier_primary_category_id(supplier)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Categoría no encontrada"}), 404

    product = Product(
        supplier_id=supplier.id,
        category_id=category.id,
        name=name,
        description=description,
        image_url=None,
        price=price,
        sku=None,
        is_active=True,
    )

    image = request.files.get("image")

    try:
        if image and image.filename:
            product.image_url = save_uploaded_image(image, "products")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.add(product)
    db.session.commit()
    return jsonify({"product": product.to_dict()}), 201


@admin_bp.patch("/products/<uuid:product_id>")
@admin_required
def admin_update_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Producto no encontrado"}), 404

    supplier = product.supplier
    if not supplier:
        return jsonify({"error": "Proveedor no encontrado para este producto"}), 404

    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"error": "El nombre del producto es obligatorio"}), 400

    product.name = name
    product.description = (request.form.get("description") or "").strip() or None

    try:
        product.price = _parse_price(request.form.get("price"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    category_raw = (request.form.get("category_id") or "").strip()
    try:
        category_id = _safe_uuid(category_raw, "category_id") if category_raw else (product.category_id or _get_supplier_primary_category_id(supplier))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({"error": "Categoría no encontrada"}), 404

    product.category_id = category.id

    remove_image = _parse_bool(request.form.get("remove_image"), False)
    image = request.files.get("image")

    if remove_image:
        product.image_url = None

    try:
        if image and image.filename:
            product.image_url = save_uploaded_image(image, "products")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({"product": product.to_dict()}), 200


@admin_bp.delete("/products/<uuid:product_id>")
@admin_required
def admin_delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Producto no encontrado"}), 404

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Producto eliminado correctamente."}), 200


@admin_bp.get("/video-sections")
@admin_required
def admin_list_video_sections():
    items = VideoSection.query.order_by(VideoSection.display_order.asc(), VideoSection.name.asc()).all()
    return jsonify({"items": [_serialize_video_section(item) for item in items]})


@admin_bp.post("/video-sections")
@admin_required
def admin_create_video_section():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip() or None

    if not name:
        return jsonify({"error": "El nombre de la sección es obligatorio"}), 400

    try:
        slug = _build_video_section_slug(name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    item = VideoSection(
        name=name,
        slug=slug,
        description=description,
        section_type=(payload.get("section_type") or "clips").strip().lower() or "clips",
        display_order=0,
        is_active=True,
    )

    db.session.add(item)
    db.session.commit()
    return jsonify({"section": _serialize_video_section(item)}), 201


@admin_bp.patch("/video-sections/<uuid:section_id>")
@admin_required
def admin_update_video_section(section_id):
    item = db.session.get(VideoSection, section_id)
    if not item:
        return jsonify({"error": "Sección no encontrada"}), 404

    payload = request.get_json(silent=True) or {}

    name = payload.get("name")
    if name is not None:
        name = str(name).strip()
        if not name:
            return jsonify({"error": "El nombre de la sección es obligatorio"}), 400
        item.name = name
        try:
            item.slug = _build_video_section_slug(name, item.id)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    if "description" in payload:
        item.description = (payload.get("description") or "").strip() or None

    if "is_active" in payload:
        item.is_active = _parse_bool(payload.get("is_active"), item.is_active)

    db.session.commit()
    return jsonify({"section": _serialize_video_section(item)}), 200


@admin_bp.delete("/video-sections/<uuid:section_id>")
@admin_required
def admin_delete_video_section(section_id):
    item = db.session.get(VideoSection, section_id)
    if not item:
        return jsonify({"error": "Sección no encontrada"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Sección eliminada correctamente."}), 200


@admin_bp.get("/videos")
@admin_required
def admin_list_videos():
    q = (request.args.get("q") or "").strip()
    section_raw = (request.args.get("section_id") or "").strip()

    query = Video.query

    if section_raw:
        try:
            section_id = _safe_uuid(section_raw, "section_id")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        query = query.join(VideoSectionLink, VideoSectionLink.video_id == Video.id).filter(
            VideoSectionLink.section_id == section_id
        )

    if q:
        search = f"%{q}%"
        query = query.filter(
            Video.title.ilike(search) |
            Video.description.ilike(search)
        )

    items = query.distinct().order_by(Video.display_order.asc(), Video.created_at.desc()).all()
    return jsonify({"items": [item.to_dict() for item in items]})


@admin_bp.post("/videos")
@admin_required
def admin_create_video():
    video_file = request.files.get("video")
    if not video_file or not video_file.filename:
        return jsonify({"error": "Debes subir un archivo de video"}), 400

    try:
        section_ids = _parse_section_ids(request.form.get("section_ids"))
    except Exception:
        return jsonify({"error": "section_ids inválido"}), 400

    title = (request.form.get("title") or "").strip() or _title_from_uploaded_filename(video_file.filename)
    description = (request.form.get("description") or "").strip() or None

    item = Video(
        supplier_id=None,
        title=title,
        description=description,
        thumbnail_url=None,
        video_url=None,
        duration=None,
        view_count=0,
        display_order=0,
        is_active=True,
    )

    try:
        item.video_url = save_uploaded_video(video_file, "videos")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.add(item)
    db.session.flush()

    try:
        _sync_video_sections(item, section_ids)
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({"video": item.to_dict()}), 201


@admin_bp.patch("/videos/<uuid:video_id>")
@admin_required
def admin_update_video(video_id):
    item = db.session.get(Video, video_id)
    if not item:
        return jsonify({"error": "Video no encontrado"}), 404

    title_raw = request.form.get("title")
    if title_raw is not None:
        title = title_raw.strip()
        if title:
            item.title = title

    if "description" in request.form:
        item.description = (request.form.get("description") or "").strip() or None

    section_ids_raw = request.form.get("section_ids")
    if section_ids_raw is not None:
        try:
            section_ids = _parse_section_ids(section_ids_raw)
            _sync_video_sections(item, section_ids)
        except ValueError as exc:
            db.session.rollback()
            return jsonify({"error": str(exc)}), 400

    replacement_video = request.files.get("video")
    if replacement_video and replacement_video.filename:
        try:
            item.video_url = save_uploaded_video(replacement_video, "videos")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if not title_raw:
            item.title = item.title or _title_from_uploaded_filename(replacement_video.filename)

    db.session.commit()
    return jsonify({"video": item.to_dict()}), 200


@admin_bp.delete("/videos/<uuid:video_id>")
@admin_required
def admin_delete_video(video_id):
    item = db.session.get(Video, video_id)
    if not item:
        return jsonify({"error": "Video no encontrado"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Video eliminado correctamente."}), 200

@admin_bp.get("/users")
@admin_required
def admin_list_users():
    q = (request.args.get("q") or "").strip()

    query = (
        User.query.options(
            joinedload(User.conversations).joinedload(ChatConversation.messages)
        )
        .order_by(User.created_at.desc())
    )

    if q:
        search = f"%{q}%"
        query = query.filter(
            User.name.ilike(search)
            | User.email.ilike(search)
            | User.company.ilike(search)
            | User.phone.ilike(search)
        )

    items = query.all()
    return jsonify({"items": [_serialize_admin_user(item) for item in items]})


@admin_bp.patch("/users/<uuid:user_id>")
@admin_required
def admin_update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    payload = request.get_json(silent=True) or {}

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    company = (payload.get("company") or "").strip() or None
    phone = (payload.get("phone") or "").strip() or None
    role = payload.get("role")
    password = (payload.get("password") or "").strip()

    if not name:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    if not email:
        return jsonify({"error": "El correo es obligatorio"}), 400

    existing = User.query.filter(User.email == email, User.id != user.id).first()
    if existing:
        return jsonify({"error": "Ya existe otro usuario con ese correo"}), 409

    current_admin_id = uuid.UUID(get_jwt_identity())

    if role is not None:
        role = str(role).strip().lower()
        if user.id == current_admin_id and role != "admin":
            return jsonify({"error": "No puedes quitarte el rol de admin a ti mismo"}), 400
        user.role = role

    user.name = name
    user.email = email
    user.company = company
    user.phone = phone

    if password:
        if len(password) < 6:
            return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400
        user.set_password(password)

    db.session.commit()

    refreshed = (
        User.query.options(
            joinedload(User.conversations).joinedload(ChatConversation.messages)
        )
        .filter_by(id=user.id)
        .first()
    )
    return jsonify({"user": _serialize_admin_user(refreshed)}), 200


@admin_bp.delete("/users/<uuid:user_id>")
@admin_required
def admin_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    current_admin_id = uuid.UUID(get_jwt_identity())
    if user.id == current_admin_id:
        return jsonify({"error": "No puedes eliminarte a ti mismo"}), 400

    if user.role == "admin":
        admins_count = User.query.filter_by(role="admin").count()
        if admins_count <= 1:
            return jsonify({"error": "No puedes eliminar al último administrador"}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Usuario eliminado correctamente."}), 200