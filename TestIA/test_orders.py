"""
Testes de pedidos — TestIA Suite.

Cobre GET /api/orders, POST /api/orders (endpoints)
e camada de serviço order_service.
Requisitos: 8.1-8.8, 12.6
"""

import hashlib
import os

import pytest
from passlib.hash import bcrypt

from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.personal_access_token import PersonalAccessToken
from app.services import order_service


# ── Helpers ───────────────────────────────────────────────────────────────

def _create_user_and_token(db_session, is_admin=False, suffix=""):
    """Cria usuário com senha hasheada e token válido. Retorna (user, headers)."""
    user = User(
        name=f"Order User{suffix}",
        username=f"orderuser{suffix}",
        phone="11999999999",
        email=f"order{suffix}@example.com",
        password=bcrypt.hash("password123"),
        is_admin=is_admin,
    )
    db_session.add(user)
    db_session.flush()

    plain_token = os.urandom(40).hex()
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()

    token_record = PersonalAccessToken(
        tokenable_type="App\\Models\\User",
        tokenable_id=user.id,
        name="auth_token",
        token=token_hash,
    )
    db_session.add(token_record)
    db_session.flush()

    token_string = f"{token_record.id}|{plain_token}"
    headers = {"Authorization": f"Bearer {token_string}"}
    return user, headers


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — GET /api/orders
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.orders
def test_get_orders_returns_user_orders_with_items(client, db_session):
    """GET /api/orders → lista de pedidos do usuário com itens e dados dos produtos. (Req 8.1)"""
    user, headers = _create_user_and_token(db_session, suffix="_getord")

    product = Product(
        name="Produto Pedido", description="Desc", price=50.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    # Create an order with items via service
    class FakeItem:
        def __init__(self, product_id, quantity):
            self.product_id = product_id
            self.quantity = quantity

    order_service.create_from_cart(db_session, user, [FakeItem(product.id, 2)])

    resp = client.get("/api/orders", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    order = data[0]
    assert order["user_id"] == user.id
    assert order["status"] == "pending"
    assert "items" in order
    assert len(order["items"]) >= 1

    item = order["items"][0]
    assert item["product_id"] == product.id
    assert item["quantity"] == 2
    assert "product" in item
    assert item["product"]["id"] == product.id
    assert item["product"]["name"] == "Produto Pedido"


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — POST /api/orders (criação)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.orders
def test_create_order_with_valid_items(client, db_session):
    """POST /api/orders com itens válidos → status 201, status 'pending', itens corretos. (Req 8.2)"""
    user, headers = _create_user_and_token(db_session, suffix="_crord")

    product = Product(
        name="Produto Criar", description="Desc", price=25.0,
        stock=50, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": 3}]},
        headers=headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["user_id"] == user.id
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == product.id
    assert data["items"][0]["quantity"] == 3
    assert data["items"][0]["price"] == 25.0


@pytest.mark.orders
def test_create_order_decrements_stock(client, db_session):
    """POST /api/orders decrementa estoque dos produtos. (Req 8.3)"""
    user, headers = _create_user_and_token(db_session, suffix="_decstk")

    product = Product(
        name="Produto Estoque", description="Desc", price=10.0,
        stock=80, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": 15}]},
        headers=headers,
    )

    assert resp.status_code == 201

    db_session.refresh(product)
    assert product.stock == 65  # 80 - 15


@pytest.mark.orders
def test_create_order_clears_cart(client, db_session):
    """POST /api/orders limpa o carrinho do usuário após criação. (Req 8.4)"""
    user, headers = _create_user_and_token(db_session, suffix="_clrcart")

    product = Product(
        name="Produto Carrinho", description="Desc", price=10.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    # Add items to cart
    cart1 = CartItem(user_id=user.id, product_id=product.id, quantity=2)
    db_session.add(cart1)
    db_session.flush()

    # Verify cart has items
    cart_count = db_session.query(CartItem).filter(CartItem.user_id == user.id).count()
    assert cart_count >= 1

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": 3}]},
        headers=headers,
    )

    assert resp.status_code == 201

    # Cart should be empty
    cart_count = db_session.query(CartItem).filter(CartItem.user_id == user.id).count()
    assert cart_count == 0


@pytest.mark.orders
def test_create_order_insufficient_stock(client, db_session):
    """POST /api/orders com estoque insuficiente → status 422. (Req 8.5)"""
    user, headers = _create_user_and_token(db_session, suffix="_insuf")

    product = Product(
        name="Produto Pouco", description="Desc", price=10.0,
        stock=5, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": 10}]},
        headers=headers,
    )

    assert resp.status_code == 422


@pytest.mark.orders
def test_create_order_inactive_product(client, db_session):
    """POST /api/orders com produto inativo → status 422. (Req 8.6)"""
    user, headers = _create_user_and_token(db_session, suffix="_inact")

    product = Product(
        name="Produto Inativo", description="Desc", price=10.0,
        stock=50, image_url="img.jpg", active=False,
    )
    db_session.add(product)
    db_session.flush()

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": 1}]},
        headers=headers,
    )

    assert resp.status_code == 422


@pytest.mark.orders
def test_create_order_nonexistent_product(client, db_session):
    """POST /api/orders com produto inexistente → status 422. (Req 8.6)"""
    _user, headers = _create_user_and_token(db_session, suffix="_noexist")

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": 99999, "quantity": 1}]},
        headers=headers,
    )

    assert resp.status_code == 422


@pytest.mark.orders
def test_create_order_empty_items(client, auth_headers):
    """POST /api/orders com lista vazia → status 422. (Req 8.7)"""
    resp = client.post(
        "/api/orders",
        json={"items": []},
        headers=auth_headers,
    )

    assert resp.status_code == 422


@pytest.mark.orders
def test_create_order_quantity_less_than_one(client, db_session):
    """POST /api/orders com quantidade < 1 → status 422. (Req 8.8)"""
    _user, headers = _create_user_and_token(db_session, suffix="_qty0")

    product = Product(
        name="Produto Qty", description="Desc", price=10.0,
        stock=50, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": 0}]},
        headers=headers,
    )

    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Serviço — order_service
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.orders
@pytest.mark.service
def test_service_create_from_cart_decrements_stock_and_clears_cart(db_session):
    """order_service.create_from_cart decrementa estoque e limpa carrinho. (Req 12.6)"""
    user, _ = _create_user_and_token(db_session, suffix="_svc_ord")

    product1 = Product(
        name="Svc Prod1", description="Desc", price=20.0,
        stock=50, image_url="img.jpg", active=True,
    )
    product2 = Product(
        name="Svc Prod2", description="Desc", price=30.0,
        stock=40, image_url="img.jpg", active=True,
    )
    db_session.add_all([product1, product2])
    db_session.flush()

    # Add items to cart
    cart1 = CartItem(user_id=user.id, product_id=product1.id, quantity=3)
    cart2 = CartItem(user_id=user.id, product_id=product2.id, quantity=2)
    db_session.add_all([cart1, cart2])
    db_session.flush()

    class FakeItem:
        def __init__(self, product_id, quantity):
            self.product_id = product_id
            self.quantity = quantity

    items = [FakeItem(product1.id, 5), FakeItem(product2.id, 10)]
    order = order_service.create_from_cart(db_session, user, items)

    assert order.status == "pending"
    assert order.user_id == user.id
    assert len(order.items) == 2

    # Stock decremented
    db_session.refresh(product1)
    db_session.refresh(product2)
    assert product1.stock == 45  # 50 - 5
    assert product2.stock == 30  # 40 - 10

    # Cart cleared
    cart_count = db_session.query(CartItem).filter(CartItem.user_id == user.id).count()
    assert cart_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Pedidos
# ═══════════════════════════════════════════════════════════════════════════

from uuid import uuid4

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ═══════════════════════════════════════════════════════════════════════════
# Property 18: Criação de pedido decrementa estoque e limpa carrinho
# Feature: testia-suite, Property 18: Criação de pedido decrementa estoque e limpa carrinho
# **Validates: Requirements 8.3, 8.4, 12.6**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.orders
@settings(**_PBT_SETTINGS)
@given(
    quantity=st.integers(min_value=1, max_value=50),
    cart_qty=st.integers(min_value=1, max_value=20),
)
def test_property_order_creation_decrements_stock_and_clears_cart(
    client, db_session, quantity, cart_qty,
):
    # Feature: testia-suite, Property 18: Criação de pedido decrementa estoque e limpa carrinho
    uid = uuid4().hex[:8]

    initial_stock = quantity + 50  # Ensure enough stock
    product = Product(
        name=f"Prop18_{uid}", description="Desc",
        price=10.0, stock=initial_stock, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    user, headers = _create_user_and_token(db_session, suffix=f"_p18_{uid}")

    # Add items to cart (these should be cleared after order)
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=cart_qty)
    db_session.add(cart)
    db_session.flush()

    # Verify cart has items
    cart_before = db_session.query(CartItem).filter(CartItem.user_id == user.id).count()
    assert cart_before >= 1

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": quantity}]},
        headers=headers,
    )

    assert resp.status_code == 201, (
        f"Expected 201 for qty={quantity}, stock={initial_stock}, got {resp.status_code}: {resp.text}"
    )

    # Stock decremented by order quantity
    db_session.refresh(product)
    assert product.stock == initial_stock - quantity, (
        f"Expected stock={initial_stock - quantity}, got {product.stock}"
    )

    # Cart cleared
    cart_after = db_session.query(CartItem).filter(CartItem.user_id == user.id).count()
    assert cart_after == 0, (
        f"Expected cart to be empty after order, but found {cart_after} items"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Property 19: Pedido com estoque insuficiente é rejeitado
# Feature: testia-suite, Property 19: Pedido com estoque insuficiente é rejeitado
# **Validates: Requirements 8.5**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.orders
@settings(**_PBT_SETTINGS)
@given(
    stock=st.integers(min_value=0, max_value=50),
    excess=st.integers(min_value=1, max_value=100),
)
def test_property_order_with_insufficient_stock_rejected(
    client, db_session, stock, excess,
):
    # Feature: testia-suite, Property 19: Pedido com estoque insuficiente é rejeitado
    uid = uuid4().hex[:8]

    product = Product(
        name=f"Prop19_{uid}", description="Desc",
        price=10.0, stock=stock, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    _user, headers = _create_user_and_token(db_session, suffix=f"_p19_{uid}")

    over_quantity = stock + excess  # Always exceeds stock

    resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": over_quantity}]},
        headers=headers,
    )

    assert resp.status_code == 422, (
        f"Expected 422 for qty={over_quantity} > stock={stock}, got {resp.status_code}"
    )

    # Stock should remain unchanged
    db_session.refresh(product)
    assert product.stock == stock, (
        f"Stock should remain {stock} after rejected order, got {product.stock}"
    )
