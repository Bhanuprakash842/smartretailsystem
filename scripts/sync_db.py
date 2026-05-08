import os
import sys
from app import app, db, ProductModel, UserModel
from werkzeug.security import generate_password_hash
from forecasting.predict import PRODUCT_CATALOG

def sync():
    with app.app_context():
        print("--- Database Sync Started (Using SQLite) ---")
        
        # 1. Ensure tables exist
        db.create_all()
        
        # 2. Ensure Admin exists
        admin = UserModel.query.filter_by(username='admin').first()
        if not admin:
            admin = UserModel(
                username='admin',
                email='admin@luxecart.com',
                password=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            print("[+] Admin user 'admin' created.")
        else:
            print("[i] Admin user already exists.")

        # 3. Sync Forecasting Products
        print("Syncing products from forecasting catalog...")
        for pid, info in PRODUCT_CATALOG.items():
            product = ProductModel.query.filter_by(name=info['name']).first()
            if not product:
                new_product = ProductModel(
                    name=info['name'],
                    description=f"Premium {info['category']} product. High performance and sleek design.",
                    price=info['price'],
                    category=info['category'],
                    stock=100,
                    image_url=f"/static/uploads/products/sample_{pid}.png"
                )
                db.session.add(new_product)
                print(f"[+] Added Product: {info['name']}")
            else:
                # Update existing product price to match catalog
                product.price = info['price']
                product.category = info['category']
                print(f"[i] Updated Product: {info['name']}")

        try:
            db.session.commit()
            print("--- Sync Complete! ---")
            print("Credentials: admin / admin123")
        except Exception as e:
            db.session.rollback()
            print(f"[!] Error during sync: {e}")

if __name__ == "__main__":
    sync()
