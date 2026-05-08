import pytest
import json
import base64
from io import BytesIO
from app import app, db
from models import ProductModel, UserModel

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['JWT_SECRET_KEY'] = 'test-secret'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

@pytest.fixture
def auth_header(client):
    # Register and login to get JWT
    client.post('/api/register', json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    })
    resp = client.post('/api/login', json={
        "username": "testuser",
        "password": "password123"
    })
    token = resp.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}

def test_register_and_login(client):
    # Test Registration
    resp = client.post('/api/register', json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123"
    })
    assert resp.status_code == 201
    
    # Test Login
    resp = client.post('/api/login', json={
        "username": "newuser",
        "password": "password123"
    })
    assert resp.status_code == 200
    assert 'access_token' in resp.get_json()

def test_get_items(client):
    with app.app_context():
        p = ProductModel(name="Test ItemCount", description="Desc", price=10.0, category="TestCat")
        db.session.add(p)
        db.session.commit()

    resp = client.get('/api/items')
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) > 0
    assert data[0]['name'] == "Test ItemCount"

def test_add_item_restricted(client):
    # Should fail without JWT
    resp = client.post('/api/items', json={
        "name": "Secret Item",
        "description": "...",
        "price": 50.0,
        "category": "Secret"
    })
    assert resp.status_code == 401

def test_add_item_success(client, auth_header):
    resp = client.post('/api/items', headers=auth_header, json={
        "name": "New Item",
        "description": "Item Description",
        "price": 25.50,
        "category": "Electronics"
    })
    assert resp.status_code == 201
    assert resp.get_json()['name'] == "New Item"

def test_update_item_form_data(client, auth_header):
    # Create item first
    with app.app_context():
        p = ProductModel(name="Old Name", description="Desc", price=10.0, category="Test")
        db.session.add(p)
        db.session.commit()
        p_id = p.id

    # Update using Form Data
    data = {
        'name': 'Updated Name',
        'price': '15.99',
        'category': 'UpdatedCat'
    }
    # Mock a file upload
    data['image'] = (BytesIO(b"fake image data"), 'test.jpg')
    
    resp = client.patch(f'/api/items/{p_id}', headers=auth_header, data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    assert resp.get_json()['message'] == "Product updated successfully"
    
    # Verify in DB
    with app.app_context():
        updated_p = ProductModel.query.get(p_id)
        assert updated_p.name == "Updated Name"
        assert updated_p.image_base64 is not None

def test_cart_operations(client):
    # Create a product to add
    with app.app_context():
        p = ProductModel(name="Cart Item", description="Desc", price=10.0, category="Test")
        db.session.add(p)
        db.session.commit()
        p_id = p.id

    # Add to cart
    resp = client.post('/api/cart/add', json={"product_id": p_id})
    assert resp.status_code == 200
    assert resp.get_json()['cart_count'] == 1

    # Remove from cart
    resp = client.post('/api/cart/remove', json={"product_id": p_id})
    assert resp.status_code == 200
    assert resp.get_json()['cart_count'] == 0

def test_checkout(client):
    # Setup product and add to cart
    with app.app_context():
        p = ProductModel(name="Checkout Item", description="Desc", price=100.0, category="Test")
        db.session.add(p)
        db.session.commit()
        p_id = p.id

    client.post('/api/cart/add', json={"product_id": p_id})
    
    # Checkout
    resp = client.post('/api/checkout', json={
        "payment_method": "Credit Card",
        "address": "123 Test St"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['order']['total'] == 100.0
    assert data['order']['status'] == "Paid"
