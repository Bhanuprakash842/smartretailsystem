from flask import Blueprint, request, render_template, redirect, url_for, session
from models import db, ProductModel, OrderModel
from utils import get_common_context, get_cart_details, login_required_page

frontend_bp = Blueprint('frontend', __name__)

@frontend_bp.route('/login')
def login_page():
    return render_template('login.html', **get_common_context())

@frontend_bp.route('/register')
def register_page():
    return render_template('register.html', **get_common_context())

@frontend_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('frontend.home'))

@frontend_bp.route('/')
def home():
    cat = request.args.get('category')
    search = request.args.get('search')
    query = ProductModel.query
    if cat: query = query.filter_by(category=cat)
    if search: query = query.filter(ProductModel.name.ilike(f'%{search}%'))
    categories = sorted(list(set(p.category for p in ProductModel.query.all())))
    return render_template('home.html', products=query.all(), categories=categories, **get_common_context())

@frontend_bp.route('/product/<int:p_id>')
def product_detail(p_id):
    product = db.session.get(ProductModel, p_id)
    if not product: return "Not Found", 404
    related = ProductModel.query.filter(ProductModel.category == product.category, ProductModel.id != product.id).limit(3).all()
    return render_template('product_detail.html', product=product, related=related, **get_common_context())

@frontend_bp.route('/cart')
def cart_page():
    detailed_cart, total = get_cart_details()
    return render_template('cart.html', cart=detailed_cart, total=total, **get_common_context())

@frontend_bp.route('/checkout')
def checkout_view():
    detailed_cart, total = get_cart_details()
    if not detailed_cart: return redirect(url_for('frontend.cart_page'))
    return render_template('checkout.html', total=total, cart=detailed_cart, **get_common_context())

@frontend_bp.route('/results')
def results_page():
    return render_template('results.html', order_id=request.args.get('order_id'), status=request.args.get('status', 'success'), **get_common_context())

@frontend_bp.route('/orders')
@login_required_page
def user_orders_page():
    orders = OrderModel.query.filter_by(user_id=session.get('user_id')).order_by(OrderModel.created_at.desc()).all()
    return render_template('user_orders.html', orders=orders, **get_common_context())
