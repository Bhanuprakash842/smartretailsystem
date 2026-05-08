-- Azure SQL Database Schema for LuxeCart
-- Run this on your Azure SQL Database to initialize tables

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(80) NOT NULL UNIQUE,
    email NVARCHAR(120) NOT NULL UNIQUE,
    password NVARCHAR(255) NOT NULL,
    role NVARCHAR(20) NOT NULL DEFAULT 'user',
    created_at DATETIME2 DEFAULT GETUTCDATE()
);

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='products' AND xtype='U')
CREATE TABLE products (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    description NVARCHAR(MAX) NOT NULL,
    price FLOAT NOT NULL,
    category NVARCHAR(50) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    image_base64 NVARCHAR(MAX),
    created_at DATETIME2 DEFAULT GETUTCDATE()
);

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='orders' AND xtype='U')
CREATE TABLE orders (
    id INT IDENTITY(1,1) PRIMARY KEY,
    order_uid NVARCHAR(36) NOT NULL UNIQUE,
    user_id INT NULL REFERENCES users(id),
    total FLOAT NOT NULL,
    status NVARCHAR(30) NOT NULL DEFAULT 'Pending',
    payment_method NVARCHAR(50) NOT NULL,
    address NVARCHAR(MAX) NOT NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE()
);

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='order_items' AND xtype='U')
CREATE TABLE order_items (
    id INT IDENTITY(1,1) PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id),
    product_id INT NOT NULL REFERENCES products(id),
    product_name NVARCHAR(100) NOT NULL,
    price FLOAT NOT NULL,
    quantity INT NOT NULL
);

-- Seed admin user (password: admin123, hashed with werkzeug)
-- You should run the app once to auto-seed, or insert manually:
-- INSERT INTO users (username, email, password, role) VALUES ('admin', 'admin@luxecart.com', '<hashed_password>', 'admin');

-- Seed sample products
IF NOT EXISTS (SELECT TOP 1 1 FROM products)
BEGIN
    INSERT INTO products (name, description, price, category, stock, image_base64) VALUES
    ('Nova Headphones', 'Premium wireless noise-cancelling headphones with 40hr battery life and studio-quality sound.', 199.99, 'Electronics', 25, NULL),
    ('Smart Watch Pro', 'Tracks your health and fitness goals with AMOLED display and 7-day battery.', 249.50, 'Wearables', 18, NULL),
    ('Minimalist Lamp', 'Sleek wooden base lamp for a modern workspace with adjustable warmth.', 45.00, 'Home Decor', 40, NULL),
    ('Leather Crossbody', 'Handcrafted Italian leather crossbody bag with brass hardware.', 129.00, 'Fashion', 15, NULL),
    ('Ceramic Vase Set', 'Set of 3 minimalist ceramic vases in matte earth tones.', 68.00, 'Home Decor', 30, NULL),
    ('Wireless Earbuds', 'True wireless earbuds with active noise cancellation and transparency mode.', 159.99, 'Electronics', 50, NULL);
END
