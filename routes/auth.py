from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import db, UserModel, UserCreate, UserLogin
from datetime import timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = UserCreate(**request.json)
        if UserModel.query.filter_by(username=data.username).first():
            return jsonify({"error": "User already exists"}), 400
        new_user = UserModel(username=data.username, email=data.email, password=generate_password_hash(data.password), role='user')
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User registered"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = UserLogin(**request.json)
        user = UserModel.query.filter_by(username=data.username).first()
        if not user or not check_password_hash(user.password, data.password):
            return jsonify({"error": "Invalid credentials"}), 401
        access_token = create_access_token(identity=data.username, expires_delta=timedelta(hours=24))
        session['username'] = data.username
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify(access_token=access_token, role=user.role), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
