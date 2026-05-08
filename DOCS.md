# LuxeCart REST API Documentation

## Authentication
- **Endpoint**: `POST /api/register`
- **Endpoint**: `POST /api/login`
  - Body: `{"username": "admin", "password": "password"}`
  - Returns: `access_token`

## Products (REST)
- **GET /api/items**: List all products.
  - Query Params: `category`, `search`
- **POST /api/items**: Add a new product (Requires JWT).
  - Header: `Authorization: Bearer <token>`
  - Body: `{"name": "...", "description": "...", "price": 0.0, "category": "...", "image_base64": "data:image/png;base64,..."}`
- **PUT /api/items/<id>**: Update a product (Requires JWT).
- **DELETE /api/items/<id>**: Remove a product (Requires JWT).

## Cart & Checkout
- **POST /api/cart/add**: Add item to session cart.
  - Body: `{"product_id": 1}`
- **POST /api/cart/remove**: Remove item from session cart.
- **POST /api/checkout**: Process payment.
  - Body: `{"payment_method": "Credit Card", "address": "123 Street, City"}`

## Postman Testing
1. Use `POST /api/register` to create a user.
2. Use `POST /api/login` to get the token.
3. Copy the token and go to "Auth" -> "Bearer Token" in Postman for the POST/PUT/DELETE requests.
4. Try adding an item with invalid price (e.g. -5.0) to see Pydantic validation error.
