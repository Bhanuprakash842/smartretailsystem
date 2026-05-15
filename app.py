import os
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from models import db, UserModel, ProductModel
from werkzeug.security import generate_password_hash
import pymssql

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-jwt-key')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads', 'products')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db_server = os.getenv('DB_SERVER')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME', 'sqldb')
db_port = int(os.getenv('DB_PORT', 1433))

import sys
if db_server and db_user and db_password and "pytest" not in sys.modules:
    def _get_azure_conn(): return pymssql.connect(server=db_server, port=db_port, user=db_user, password=db_password, database=db_name, timeout=30, login_timeout=30)
    app.config['SQLALCHEMY_DATABASE_URI'] = "mssql+pymssql://"
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'creator': _get_azure_conn}
elif "pytest" in sys.modules:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'ecommerce.db')}"

db.init_app(app)
jwt = JWTManager(app)

from routes.auth import auth_bp
from routes.api import api_bp
from routes.frontend import frontend_bp
from routes.admin import admin_bp
app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(frontend_bp)
app.register_blueprint(admin_bp)

try:
    from forecasting.forecast_routes import forecast_bp
    app.register_blueprint(forecast_bp)
except ImportError: pass

try:
    from forecasting.analytics_routes import analytics_bp
    app.register_blueprint(analytics_bp)
except ImportError: pass

try:
    from chatbot.chat_routes import chat_bp
    app.register_blueprint(chat_bp)
except ImportError: pass

@app.route('/health')
def health(): return jsonify({"status": "healthy"})

with app.app_context():
    try: 
        db.create_all()
        if not UserModel.query.filter_by(role='admin').first():
            db.session.add(UserModel(username='admin', email='admin@luxecart.com', password=generate_password_hash('admin123'), role='admin'))
            db.session.commit()
        if not ProductModel.query.first():
            sample_products = [
                ProductModel(name='Nova Headphones', description='Premium wireless noise-cancelling headphones.', price=199.99, category='Electronics', stock=25, image_url='/static/uploads/products/nova_headphones.png'),
                ProductModel(name='Smart Watch Pro', description='Tracks health and fitness goals.', price=249.50, category='Wearables', stock=18, image_url='/static/uploads/products/smart_watch.png'),
                ProductModel(name='Minimalist Lamp', description='Sleek wooden base lamp.', price=45.00, category='Home Decor', stock=40, image_url='/static/uploads/products/minimalist_lamp.png'),
                ProductModel(name='Leather Crossbody', description='Handcrafted Italian leather crossbody bag.', price=129.00, category='Fashion', stock=15, image_url='/static/uploads/products/leather_crossbody.png'),
                ProductModel(name='Ceramic Vase Set', description='Set of 3 minimalist ceramic vases.', price=68.00, category='Home Decor', stock=30, image_url='/static/uploads/products/ceramic_vase_set.png'),
                ProductModel(name='Wireless Earbuds', description='True wireless earbuds.', price=159.99, category='Electronics', stock=50, image_url='/static/uploads/products/wireless_earbuds.png'),
            ]
            for p in sample_products: db.session.add(p)
            db.session.commit()
    except: pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)
