import os, uuid
from functools import wraps
from flask import session, flash, redirect, url_for
from models import db, ProductModel

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_product_image(file, upload_folder):
    if file and file.filename != '' and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex[:12]}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        return f"/static/uploads/products/{filename}"
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Access denied.')
            return redirect(url_for('admin.admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

def login_required_page(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login.')
            return redirect(url_for('frontend.login_page'))
        return f(*args, **kwargs)
    return decorated_function

def get_common_context():
    return {
        'cart_count': len(session.get('cart', [])),
        'username': session.get('username'),
        'role': session.get('role', 'user')
    }

def get_cart_details():
    cart = session.get('cart', [])
    detailed_cart = []
    total = 0
    for item in cart:
        product = db.session.get(ProductModel, item['id'])
        if product:
            item_total = product.price * item['quantity']
            total += item_total
            detailed_cart.append({
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "category": product.category,
                "image_url": product.image_url,
                "quantity": item['quantity'],
                "total": item_total
            })
    return detailed_cart, total
