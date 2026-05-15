import pytest
from app import app, db
from models import ProductModel, UserModel

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier testing if applicable
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_home_page_renders(client):
    """Test that the home page renders and contains expected elements."""
    # Add a mock product
    with app.app_context():
        p = ProductModel(
            name="Test Headphones",
            description="Awesome sound",
            price=99.99,
            category="Electronics"
        )
        db.session.add(p)
        db.session.commit()

    resp = client.get('/')
    assert resp.status_code == 200
    # Check if the product name appears in the HTML content
    assert b"Test Headphones" in resp.data
    assert b"Electronics" in resp.data
    # Check if the navbar brand is present
    assert b"LuxeCart" in resp.data

def test_product_detail_page(client):
    """Test that the product detail page shows detailed info."""
    with app.app_context():
        p = ProductModel(
            name="Unique Gadget",
            description="A very unique description that should appear only here.",
            price=49.99,
            category="Gadgets"
        )
        db.session.add(p)
        db.session.commit()
        p_id = p.id

    resp = client.get(f'/product/{p_id}')
    assert resp.status_code == 200
    assert b"Unique Gadget" in resp.data
    assert b"A very unique description that should appear only here." in resp.data

def test_cart_page_flow(client):
    """Test adding to cart via API and then viewing it on the HTML cart page."""
    with app.app_context():
        p = ProductModel(name="Cart Item", description="Test Description", price=10.0, category="Test")
        db.session.add(p)
        db.session.commit()
        p_id = p.id

    # Add to cart (this uses the session)
    client.post('/api/cart/add', json={"product_id": p_id})

    # Request the cart page
    resp = client.get('/cart')
    assert resp.status_code == 200
    assert b"Cart Item" in resp.data
    assert "₹10.00".encode('utf-8') in resp.data 

def test_login_page_renders(client):
    """Test that the login page contains the login form."""
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b"Login" in resp.data
    assert b"username" in resp.data.lower()
    assert b"password" in resp.data.lower()

def test_flash_message_on_upload(client):
    """Test that a successful upload redirects and shows a flash message."""
    data = {
        'name': 'New Upload',
        'price': '150.0',
        'category': 'Home',
        'description': 'Description here',
        # image is optional in app.py's upload_page
    }
    
    # follow_redirects=True is key to seeing the flash message on the home page
    with client.session_transaction() as sess:
        sess['role'] = 'admin'
        sess['username'] = 'admin'
        sess['user_id'] = 1

    resp = client.post('/admin/products/add', data=data, follow_redirects=True)
    
    assert resp.status_code == 200
    assert b"New Upload" in resp.data
