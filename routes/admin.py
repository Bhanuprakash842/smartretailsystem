import os
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, current_app
from werkzeug.security import check_password_hash
from models import db, ProductModel, UserModel, OrderModel
from utils import admin_required, get_common_context, save_product_image

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login_page():
    if request.method == 'POST':
        user = UserModel.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')) and user.role == 'admin':
            session.update({'username': user.username, 'user_id': user.id, 'role': 'admin'})
            return redirect(url_for('admin.admin_dashboard'))
        flash('Invalid admin credentials.')
    return render_template('admin/login.html')

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html',
        total_products=ProductModel.query.count(),
        total_users=UserModel.query.filter_by(role='user').count(),
        total_orders=OrderModel.query.count(),
        total_revenue=db.session.query(db.func.sum(OrderModel.total)).scalar() or 0,
        recent_orders=OrderModel.query.order_by(OrderModel.created_at.desc()).limit(5).all(),
        low_stock=ProductModel.query.filter(ProductModel.stock < 10).all(),
        categories=db.session.query(ProductModel.category, db.func.count(ProductModel.id)).group_by(ProductModel.category).all(),
        **get_common_context())

@admin_bp.route('/products')
@admin_required
def admin_products():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    query = ProductModel.query
    if search: query = query.filter(ProductModel.name.ilike(f'%{search}%'))
    if category: query = query.filter_by(category=category)
    return render_template('admin/products.html', products=query.order_by(ProductModel.created_at.desc()).all(), categories=sorted(list(set(p.category for p in ProductModel.query.all()))), search=search, selected_category=category, **get_common_context())

@admin_bp.route('/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        db.session.add(ProductModel(
            name=request.form.get('name'), price=float(request.form.get('price')), category=request.form.get('category'),
            description=request.form.get('description'), stock=int(request.form.get('stock', 0)),
            image_url=save_product_image(request.files.get('image'), current_app.config['UPLOAD_FOLDER'])
        ))
        db.session.commit()
        return redirect(url_for('admin.admin_products'))
    return render_template('admin/product_form.html', product=None, **get_common_context())

@admin_bp.route('/products/edit/<int:p_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(p_id):
    product = db.session.get(ProductModel, p_id)
    if not product: return redirect(url_for('admin.admin_products'))
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        product.category = request.form.get('category')
        product.description = request.form.get('description')
        product.stock = int(request.form.get('stock', product.stock))
        img_url = save_product_image(request.files.get('image'), current_app.config['UPLOAD_FOLDER'])
        if img_url: product.image_url = img_url
        db.session.commit()
        return redirect(url_for('admin.admin_products'))
    return render_template('admin/product_form.html', product=product, **get_common_context())

@admin_bp.route('/products/delete/<int:p_id>', methods=['POST'])
@admin_required
def admin_delete_product(p_id):
    product = db.session.get(ProductModel, p_id)
    if product:
        db.session.delete(product)
        db.session.commit()
    return redirect(url_for('admin.admin_products'))

@admin_bp.route('/orders')
@admin_required
def admin_orders():
    sf = request.args.get('status', '')
    query = OrderModel.query.filter_by(status=sf) if sf else OrderModel.query
    return render_template('admin/orders.html', orders=query.order_by(OrderModel.created_at.desc()).all(), status_filter=sf, **get_common_context())

@admin_bp.route('/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    order = db.session.get(OrderModel, order_id)
    if not order: return redirect(url_for('admin.admin_orders'))
    return render_template('admin/order_detail.html', order=order, customer=db.session.get(UserModel, order.user_id) if order.user_id else None, **get_common_context())

@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    order = db.session.get(OrderModel, order_id)
    ns = request.form.get('status')
    if order and ns in ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']:
        order.status = ns
        db.session.commit()
    return redirect(url_for('admin.admin_order_detail', order_id=order_id))

@admin_bp.route('/users')
@admin_required
def admin_users():
    return render_template('admin/users.html', users=UserModel.query.order_by(UserModel.created_at.desc()).all(), **get_common_context())

@admin_bp.route('/bi-analytics')
@admin_required
def admin_bi_analytics():
    # In a real scenario, this URL would come from a configuration or database
    # For now, we provide a placeholder or allow setting it via environment variable
    bi_embed_url = current_app.config.get('POWERBI_EMBED_URL') or os.getenv('POWERBI_EMBED_URL')
    return render_template('admin/powerbi_analytics.html', bi_embed_url=bi_embed_url, **get_common_context())

@admin_bp.route('/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin.admin_login_page'))
