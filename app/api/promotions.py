from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import or_

from app.models import Promotion


promotions_bp = Blueprint('promotions', __name__)


@promotions_bp.get('/promotions')
def list_promotions():
    now = datetime.now(timezone.utc)
    items = (
        Promotion.query.filter(Promotion.is_active.is_(True))
        .filter(or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now))
        .filter(or_(Promotion.ends_at.is_(None), Promotion.ends_at >= now))
        .order_by(Promotion.display_order.asc(), Promotion.created_at.desc())
        .all()
    )
    return jsonify({'items': [item.to_dict() for item in items]})
