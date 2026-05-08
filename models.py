from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# --- SQLAlchemy Models ---
class UserModel(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProductModel(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(500), nullable=True)  # File path relative to static/
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OrderModel(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_uid = db.Column(db.String(36), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Pending')
    payment_method = db.Column(db.String(50), nullable=False)
    address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItemModel', backref='order', lazy=True)

class OrderItemModel(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship('ProductModel', lazy=True)

# --- Pydantic Schemas (for Validation) ---
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class ProductBase(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)
    category: str
    image_url: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: datetime

class CartItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class CheckoutRequest(BaseModel):
    payment_method: str
    address: str

class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
