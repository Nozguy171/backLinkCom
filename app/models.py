
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.constants import (
    CHAT_SENDER_ROLES,
    SUBMISSION_STATUSES,
    SUBMISSION_TYPES,
    USER_ROLES,
    VIDEO_SECTION_TYPES,
)
from app.extensions import db


UTC_NOW = lambda: datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, onupdate=UTC_NOW, nullable=True)


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    company = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)

    conversations = db.relationship("ChatConversation", foreign_keys="ChatConversation.user_id", back_populates="user", lazy=True)
    assigned_conversations = db.relationship("ChatConversation", foreign_keys="ChatConversation.assigned_admin_id", back_populates="assigned_admin", lazy=True)
    sent_messages = db.relationship("ChatMessage", back_populates="sender", lazy=True)
    submissions = db.relationship("Submission", back_populates="user", lazy=True)
    favorites = db.relationship("Favorite", back_populates="user", lazy=True)

    @validates("role")
    def validate_role(self, _key, value):
        value = (value or "").strip().lower()
        if value not in USER_ROLES:
            raise ValueError(f"Rol inválido: {value}")
        return value

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "company": self.company,
            "avatar_url": self.avatar_url,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, unique=True)
    icon = db.Column(db.String(100))
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    supplier_links = db.relationship("SupplierCategory", back_populates="category", cascade="all, delete-orphan")
    products = db.relationship("Product", back_populates="category")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "icon": self.icon,
            "description": self.description,
            "display_order": self.display_order,
            "is_active": self.is_active,
        }


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    logo_url = db.Column(db.Text)
    banner_url = db.Column(db.Text)
    location = db.Column(db.String(255))
    rating = db.Column(db.Numeric(2, 1), default=0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    years_in_business = db.Column(db.Integer, nullable=True)
    employee_count = db.Column(db.String(50), nullable=True)
    coverage = db.Column(db.String(50), default="national", nullable=False)
    address = db.Column(db.Text)
    website = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, onupdate=UTC_NOW, nullable=False)

    category_links = db.relationship("SupplierCategory", back_populates="supplier", cascade="all, delete-orphan")
    products = db.relationship("Product", back_populates="supplier", cascade="all, delete-orphan")
    promotions = db.relationship("Promotion", back_populates="supplier")
    videos = db.relationship("Video", back_populates="supplier")
    submissions = db.relationship("Submission", back_populates="supplier")
    favorites = db.relationship("Favorite", back_populates="supplier")

    def to_dict(self, include_categories=False, include_products=False):
        data = {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "logo_url": self.logo_url,
            "banner_url": self.banner_url,
            "location": self.location,
            "coverage": self.coverage,
            "address": self.address,
            "website": self.website,
            "email": self.email,
            "phone": self.phone,
            "is_verified": self.is_verified,
            "is_featured": self.is_featured,
            "is_active": self.is_active,
            "products_count": len(self.products or []),
        }

        if include_categories:
            data["categories"] = [link.category.to_dict() for link in self.category_links if link.category]

        if include_products:
            data["products"] = [product.to_dict() for product in self.products]

        return data


class SupplierCategory(db.Model):
    __tablename__ = "supplier_categories"
    __table_args__ = (db.UniqueConstraint("supplier_id", "category_id", name="uq_supplier_category"),)

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = db.Column(UUID(as_uuid=True), db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    category_id = db.Column(UUID(as_uuid=True), db.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    supplier = db.relationship("Supplier", back_populates="category_links")
    category = db.relationship("Category", back_populates="supplier_links")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = db.Column(UUID(as_uuid=True), db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    category_id = db.Column(UUID(as_uuid=True), db.ForeignKey("categories.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2))
    sku = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, onupdate=UTC_NOW, nullable=False)

    supplier = db.relationship("Supplier", back_populates="products")
    category = db.relationship("Category", back_populates="products")

    def to_dict(self):
        return {
            "id": str(self.id),
            "supplier_id": str(self.supplier_id),
            "category_id": str(self.category_id),
            "category_name": self.category.name if self.category else None,
            "name": self.name,
            "description": self.description,
            "image_url": self.image_url,
            "price": float(self.price) if self.price is not None else None,
            "sku": self.sku,
            "is_active": self.is_active,
        }


class Promotion(db.Model):
    __tablename__ = "promotions"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    subtitle = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.Text, nullable=False)
    link_url = db.Column(db.Text, nullable=True)
    badge_text = db.Column(db.String(100), nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    supplier = db.relationship("Supplier", back_populates="promotions")

    def to_dict(self):
        return {
            "id": str(self.id),
            "supplier_id": str(self.supplier_id) if self.supplier_id else None,
            "title": self.title,
            "subtitle": self.subtitle,
            "image_url": self.image_url,
            "link_url": self.link_url,
            "badge_text": self.badge_text,
            "display_order": self.display_order,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VideoSection(db.Model):
    __tablename__ = "video_sections"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    section_type = db.Column(db.String(20), nullable=False, default="clips")
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    video_links = db.relationship("VideoSectionLink", back_populates="section", cascade="all, delete-orphan")

    @validates("section_type")
    def validate_section_type(self, _key, value):
        value = (value or "").strip().lower()
        if value not in VIDEO_SECTION_TYPES:
            raise ValueError(f"Tipo de sección inválido: {value}")
        return value

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "section_type": self.section_type,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VideoSectionLink(db.Model):
    __tablename__ = "video_section_links"
    __table_args__ = (
        UniqueConstraint("video_id", "section_id", name="uq_video_section_link"),
    )

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("video_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    video = db.relationship("Video", back_populates="section_links")
    section = db.relationship("VideoSection", back_populates="video_links")


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    thumbnail_url = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.Text, nullable=False)
    duration = db.Column(db.String(20), nullable=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    supplier = db.relationship("Supplier", back_populates="videos")
    section_links = db.relationship("VideoSectionLink", back_populates="video", cascade="all, delete-orphan")

    def to_dict(self):
        sections = [link.section for link in self.section_links if link.section]
        sections.sort(key=lambda item: (item.display_order, (item.name or "").lower()))

        return {
            "id": str(self.id),
            "supplier_id": str(self.supplier_id) if self.supplier_id else None,
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "video_url": self.video_url,
            "duration": self.duration,
            "view_count": self.view_count,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "section_ids": [str(section.id) for section in sections],
            "sections": [section.to_dict() for section in sections],
        }
    


class ChatConversation(db.Model):
    __tablename__ = "chat_conversations"
    __table_args__ = (UniqueConstraint("user_id", name="uq_chat_conversation_user"),)

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_admin_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    last_message_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="conversations")
    assigned_admin = db.relationship("User", foreign_keys=[assigned_admin_id], back_populates="assigned_conversations")
    messages = db.relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")

    def to_dict(self, include_last_message=False):
        data = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "assigned_admin_id": str(self.assigned_admin_id) if self.assigned_admin_id else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user": self.user.to_dict() if self.user else None,
            "assigned_admin": self.assigned_admin.to_dict() if self.assigned_admin else None,
        }
        if include_last_message and self.messages:
            last_msg = sorted(self.messages, key=lambda m: m.created_at)[-1]
            data["last_message"] = last_msg.to_dict()
        return data

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(
        Uuid(as_uuid=True),
        db.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id = db.Column(
        Uuid(as_uuid=True),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sender_role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    is_edited = db.Column(db.Boolean, default=False, nullable=False)
    edited_at = db.Column(db.DateTime(timezone=True), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    conversation = db.relationship("ChatConversation", back_populates="messages")
    sender = db.relationship("User", back_populates="sent_messages")

    @validates("sender_role")
    def validate_sender_role(self, _key, value):
        value = (value or "").strip().lower()
        if value not in CHAT_SENDER_ROLES:
            raise ValueError(f"Rol de remitente inválido: {value}")
        return value

    def to_dict(self):
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "sender_user_id": str(self.sender_user_id) if self.sender_user_id else None,
            "sender_role": self.sender_role,
            "content": self.content,
            "is_read": self.is_read,
            "is_edited": self.is_edited,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sender": self.sender.to_dict() if self.sender else None,
        }

class Submission(db.Model, TimestampMixin):
    __tablename__ = "submissions"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    submission_type = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(40), nullable=False, default="pending", index=True)
    data = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.Text, nullable=True)

    user = db.relationship("User", back_populates="submissions")
    supplier = db.relationship("Supplier", back_populates="submissions")

    @validates("submission_type")
    def validate_submission_type(self, _key, value):
        value = (value or "").strip().lower()
        if value not in SUBMISSION_TYPES:
            raise ValueError(f"Tipo de submission inválido: {value}")
        return value

    @validates("status")
    def validate_status(self, _key, value):
        value = (value or "").strip().lower()
        if value not in SUBMISSION_STATUSES:
            raise ValueError(f"Status inválido: {value}")
        return value

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "supplier_id": str(self.supplier_id) if self.supplier_id else None,
            "submission_type": self.submission_type,
            "status": self.status,
            "data": self.data or {},
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "user": self.user.to_dict() if self.user else None,
            "supplier": self.supplier.to_dict(include_categories=True) if self.supplier else None,
        }


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "supplier_id", name="uq_favorite_user_supplier"),)

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    supplier_id = db.Column(Uuid(as_uuid=True), db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, nullable=False)

    user = db.relationship("User", back_populates="favorites")
    supplier = db.relationship("Supplier", back_populates="favorites")


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=UTC_NOW, onupdate=UTC_NOW, nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
