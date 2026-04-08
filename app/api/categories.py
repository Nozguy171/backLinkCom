from flask import Blueprint, jsonify

from app.models import Category


categories_bp = Blueprint('categories', __name__)


@categories_bp.get('/categories')
def list_categories():
    items = Category.query.filter_by(is_active=True).order_by(Category.display_order.asc(), Category.name.asc()).all()
    return jsonify({'items': [item.to_dict() for item in items]})
