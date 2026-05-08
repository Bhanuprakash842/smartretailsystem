import uuid
from flask import Blueprint, request, jsonify, session, current_app
from flask_jwt_extended import jwt_required
from models import db, ProductModel, OrderModel, OrderItemModel, ProductCreate, CheckoutRequest
from utils import save_product_image, get_cart_details

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/items', methods=['GET'])
def get_items():
    category = request.args.get('category')
    search = request.args.get('search')
    query = ProductModel.query
    if category: query = query.filter(ProductModel.category.ilike(category))
    if search: query = query.filter((ProductModel.name.ilike(f'%{search}%')) | (ProductModel.description.ilike(f'%{search}%')))
    return jsonify([{"id": p.id, "name": p.name, "description": p.description, "price": p.price, "category": p.category, "stock": p.stock, "image_url": p.image_url} for p in query.all()])

@api_bp.route('/items', methods=['POST'])
@jwt_required()
def add_item():
    try:
        data = ProductCreate(**request.json)
        new_product = ProductModel(name=data.name, description=data.description, price=data.price, category=data.category, image_url=data.image_url)
        db.session.add(new_product)
        db.session.commit()
        return jsonify({"id": new_product.id, "name": new_product.name, "message": "Product created"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@api_bp.route('/items/<int:item_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_item_api(item_id):
    product = db.session.get(ProductModel, item_id)
    if not product: return jsonify({"error": "Item not found"}), 404
    try:
        if request.is_json:
            data = ProductCreate(**request.json)
            product.name = data.name
            product.description = data.description
            product.price = data.price
            product.category = data.category
            if data.image_url: product.image_url = data.image_url
        else:
            if 'name' in request.form: product.name = request.form.get('name')
            if 'description' in request.form: product.description = request.form.get('description')
            if 'price' in request.form: product.price = float(request.form.get('price'))
            if 'category' in request.form: product.category = request.form.get('category')
            file = request.files.get('image')
            img_url = save_product_image(file, current_app.config['UPLOAD_FOLDER'])
            if img_url: product.image_url = img_url
        db.session.commit()
        return jsonify({"message": "Product updated"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@api_bp.route('/items/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_item(item_id):
    product = db.session.get(ProductModel, item_id)
    if not product: return jsonify({"error": "Item not found"}), 404
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Item deleted"}), 200

@api_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    item_id = request.json.get('product_id')
    product = db.session.get(ProductModel, item_id)
    if not product: return jsonify({"error": "Product not found"}), 404
    if 'cart' not in session: session['cart'] = []
    cart = session['cart']
    found = False
    for c_item in cart:
        if c_item['id'] == item_id:
            c_item['quantity'] += 1
            found = True
            break
    if not found: cart.append({"id": product.id, "quantity": 1})
    session['cart'] = cart
    session.modified = True
    return jsonify({"message": "Added to cart", "cart_count": len(session['cart'])})

@api_bp.route('/cart/remove', methods=['POST'])
def remove_from_cart():
    item_id = request.json.get('product_id')
    if 'cart' not in session: return jsonify({"error": "Cart is empty"}), 400
    session['cart'] = [item for item in session['cart'] if item['id'] != item_id]
    session.modified = True
    return jsonify({"message": "Removed from cart", "cart_count": len(session['cart'])})

@api_bp.route('/checkout', methods=['POST'])
def checkout():
    detailed_cart, total = get_cart_details()
    if not detailed_cart: return jsonify({"error": "Cart is empty"}), 400
    try:
        data = CheckoutRequest(**request.json)
        order_uid = str(uuid.uuid4())
        new_order = OrderModel(order_uid=order_uid, user_id=session.get('user_id'), total=total, status='Processing', payment_method=data.payment_method, address=data.address)
        db.session.add(new_order)
        db.session.flush()
        for item in detailed_cart:
            order_item = OrderItemModel(order_id=new_order.id, product_id=item['id'], product_name=item['name'], price=item['price'], quantity=item['quantity'])
            db.session.add(order_item)
            product = db.session.get(ProductModel, item['id'])
            if product: product.stock = max(0, product.stock - item['quantity'])
        db.session.commit()
        session['cart'] = []
        session.modified = True
        return jsonify({"message": "Order processed", "order": {"order_id": order_uid, "total": total, "status": "Processing"}})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
