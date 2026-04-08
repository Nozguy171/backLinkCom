import uuid

from flask import Blueprint, jsonify, request

from app.models import Product, Supplier


suppliers_bp = Blueprint('suppliers', __name__)


@suppliers_bp.get('/suppliers')
def list_suppliers():
    q = (request.args.get('q') or '').strip()
    featured = (request.args.get('featured') or '').strip().lower()

    query = Supplier.query.filter_by(is_active=True)

    if featured == 'true':
        query = query.filter_by(is_featured=True)

    if q:
        search = f'%{q}%'
        query = query.filter(
            Supplier.name.ilike(search)
            | Supplier.description.ilike(search)
            | Supplier.location.ilike(search)
        )

    items = query.order_by(Supplier.is_featured.desc(), Supplier.created_at.desc()).all()
    return jsonify({'items': [item.to_dict(include_categories=True) for item in items]})


@suppliers_bp.get('/suppliers/<uuid:supplier_id>')
def get_supplier(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, is_active=True).first()
    if not supplier:
        return jsonify({'error': 'Proveedor no encontrado'}), 404

    data = supplier.to_dict(include_categories=True)
    data['products'] = [product.to_dict() for product in supplier.products if product.is_active]
    return jsonify({'supplier': data})


@suppliers_bp.get('/suppliers/slug/<slug>')
def get_supplier_by_slug(slug):
    supplier = Supplier.query.filter_by(slug=slug, is_active=True).first()
    if not supplier:
        return jsonify({'error': 'Proveedor no encontrado'}), 404

    data = supplier.to_dict(include_categories=True)
    data['products'] = [product.to_dict() for product in supplier.products if product.is_active]
    return jsonify({'supplier': data})


@suppliers_bp.get('/suppliers/<uuid:supplier_id>/products')
def list_products(supplier_id):
    supplier = Supplier.query.filter_by(id=supplier_id, is_active=True).first()
    if not supplier:
        return jsonify({'error': 'Proveedor no encontrado'}), 404

    products = Product.query.filter_by(supplier_id=supplier_id, is_active=True).order_by(Product.created_at.desc()).all()
    return jsonify({'items': [product.to_dict() for product in products]})
