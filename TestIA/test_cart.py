"""
Testes de carrinho de compras — TestIA Suite.

Cobre GET/POST /api/cart, PUT/DELETE /api/cart/{id} (endpoints)
e camada de serviço cart_service.
Requisitos: 7.1-7.11, 12.3, 12.4, 12.5
"""

import hashlib
import os

import pytest
from passlib.hash import bcrypt
from sqlalchemy import func

from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.user import User
from app.models.personal_access_token import PersonalAccessToken
from app.services import cart_service


# ── Helpers ───────────────────────────────────────────────────────────────

def _create_user_and_token(db_session, is_admin=False, suffix=""):
    """Cria usuário com senha hasheada e token válido. Retorna (user, headers)."""
    user = User(
        name=f"Cart User{suffix}",
        username=f"cartuser{suffix}",
        phone="11999999999",
        email=f"cart{suffix}@example.com",
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
# Testes Unitários — GET /api/cart
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
def test_get_cart_returns_items_with_product_data(client, auth_headers, cart_item, sample_product):
    """GET /api/cart retorna lista de itens com dados do produto e estoque disponível. (Req 7.1)"""
    resp = client.get("/api/cart", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    items = data["items"]
    assert len(items) >= 1

    found = next((i for i in items if i["id"] == cart_item.id), None)
    assert found is not None
    assert found["product_id"] == sample_product.id
    assert found["quantity"] == 2
    assert "product" in found
    assert found["product"]["id"] == sample_product.id
    assert found["product"]["name"] == "Produto Teste"
    assert found["product"]["stock"] == 100
    assert "available_stock" in found["product"]
    assert "available_stock" in found


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — POST /api/cart (adição)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
def test_add_valid_product_to_cart(client, auth_headers, sample_product):
    """POST /api/cart com produto válido → item adicionado com confirmação. (Req 7.2)"""
    resp = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 3},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Produto adicionado ao carrinho."
    assert "item" in data
    assert data["item"]["product_id"] == sample_product.id
    assert data["item"]["quantity"] == 3


@pytest.mark.cart
def test_add_existing_product_increments_quantity(client, auth_headers, cart_item, sample_product):
    """POST /api/cart com produto já no carrinho → quantidade incrementada. (Req 7.3)"""
    resp = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 5},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["item"]["quantity"] == 7  # 2 (existing) + 5


@pytest.mark.cart
def test_add_quantity_exceeds_stock(client, auth_headers, sample_product):
    """POST /api/cart com quantidade > estoque disponível → status 422. (Req 7.4)"""
    resp = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 999},
        headers=auth_headers,
    )

    assert resp.status_code == 422


@pytest.mark.cart
def test_add_inactive_product(client, auth_headers, db_session):
    """POST /api/cart com produto inativo → status 422. (Req 7.5)"""
    inactive = Product(
        name="Inativo Cart", description="Desc", price=10.0,
        stock=50, image_url="img.jpg", active=False,
    )
    db_session.add(inactive)
    db_session.flush()

    resp = client.post(
        "/api/cart",
        json={"product_id": inactive.id, "quantity": 1},
        headers=auth_headers,
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "Este produto nao esta disponivel." in str(detail)


@pytest.mark.cart
def test_add_nonexistent_product(client, auth_headers):
    """POST /api/cart com produto inexistente → status 422. (Req 7.5)"""
    resp = client.post(
        "/api/cart",
        json={"product_id": 99999, "quantity": 1},
        headers=auth_headers,
    )

    assert resp.status_code == 422


@pytest.mark.cart
def test_add_product_zero_stock(client, auth_headers, db_session):
    """POST /api/cart com produto estoque zero → status 422. (Req 7.6)"""
    zero_stock = Product(
        name="Sem Estoque", description="Desc", price=10.0,
        stock=0, image_url="img.jpg", active=True,
    )
    db_session.add(zero_stock)
    db_session.flush()

    resp = client.post(
        "/api/cart",
        json={"product_id": zero_stock.id, "quantity": 1},
        headers=auth_headers,
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "Produto sem estoque disponivel no momento." in str(detail)


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — PUT /api/cart/{id}
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
def test_update_cart_item_quantity(client, auth_headers, cart_item):
    """PUT /api/cart/{id} → quantidade atualizada. (Req 7.7)"""
    resp = client.put(
        f"/api/cart/{cart_item.id}",
        json={"quantity": 10},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Quantidade atualizada."
    assert data["item"]["quantity"] == 10


@pytest.mark.cart
def test_update_cart_item_exceeds_stock(client, auth_headers, cart_item):
    """PUT /api/cart/{id} com quantidade > estoque → status 422. (Req 7.8)"""
    resp = client.put(
        f"/api/cart/{cart_item.id}",
        json={"quantity": 999},
        headers=auth_headers,
    )

    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — DELETE /api/cart/{id}
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
def test_delete_cart_item(client, auth_headers, cart_item):
    """DELETE /api/cart/{id} → item removido. (Req 7.9)"""
    resp = client.delete(
        f"/api/cart/{cart_item.id}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Item removido do carrinho."


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — Operação em item de outro usuário
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
def test_update_other_user_cart_item_returns_404(client, db_session, cart_item):
    """PUT em item de outro usuário → status 404. (Req 7.10)"""
    _other_user, other_headers = _create_user_and_token(db_session, suffix="_other_upd")

    resp = client.put(
        f"/api/cart/{cart_item.id}",
        json={"quantity": 5},
        headers=other_headers,
    )

    assert resp.status_code == 404


@pytest.mark.cart
def test_delete_other_user_cart_item_returns_404(client, db_session, cart_item):
    """DELETE em item de outro usuário → status 404. (Req 7.10)"""
    _other_user, other_headers = _create_user_and_token(db_session, suffix="_other_del")

    resp = client.delete(
        f"/api/cart/{cart_item.id}",
        headers=other_headers,
    )

    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — Estoque disponível com reservas de outros
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
def test_available_stock_considers_other_users_reservations(
    client, db_session, auth_headers, sample_product
):
    """Estoque disponível desconta reservas de outros usuários. (Req 7.11)"""
    other_user, _other_headers = _create_user_and_token(db_session, suffix="_reserv")

    # Other user reserves 30 units
    other_cart = CartItem(
        user_id=other_user.id,
        product_id=sample_product.id,
        quantity=30,
    )
    db_session.add(other_cart)
    db_session.flush()

    resp = client.get("/api/cart", headers=auth_headers)
    assert resp.status_code == 200

    # Now try to add more than available (100 - 30 = 70 available)
    resp = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 71},
        headers=auth_headers,
    )
    assert resp.status_code == 422

    # But 70 should work
    resp = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 70},
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Serviço — cart_service
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
@pytest.mark.service
def test_service_available_stock_for_user(db_session, sample_product):
    """cart_service.available_stock_for_user desconta reservas de outros. (Req 12.3)"""
    user_a, _ = _create_user_and_token(db_session, suffix="_svc_a")
    user_b, _ = _create_user_and_token(db_session, suffix="_svc_b")

    # No reservations → full stock
    stock = cart_service.available_stock_for_user(db_session, sample_product, user_a)
    assert stock == 100

    # user_b reserves 40
    cart_b = CartItem(user_id=user_b.id, product_id=sample_product.id, quantity=40)
    db_session.add(cart_b)
    db_session.flush()

    stock = cart_service.available_stock_for_user(db_session, sample_product, user_a)
    assert stock == 60

    # user_a's own reservation should NOT be subtracted
    cart_a = CartItem(user_id=user_a.id, product_id=sample_product.id, quantity=10)
    db_session.add(cart_a)
    db_session.flush()

    stock = cart_service.available_stock_for_user(db_session, sample_product, user_a)
    assert stock == 60  # Still 60, user_a's own cart doesn't count


@pytest.mark.cart
@pytest.mark.service
def test_service_add_item_increments_existing(db_session, sample_product):
    """cart_service.add_item incrementa quantidade de item existente. (Req 12.4)"""
    user, _ = _create_user_and_token(db_session, suffix="_svc_inc")

    # First add
    item1 = cart_service.add_item(db_session, user, sample_product.id, 3)
    assert item1.quantity == 3

    # Second add → increment
    item2 = cart_service.add_item(db_session, user, sample_product.id, 5)
    assert item2.id == item1.id  # Same item
    assert item2.quantity == 8  # 3 + 5


@pytest.mark.cart
@pytest.mark.service
def test_service_update_item_min_quantity(db_session, sample_product):
    """cart_service.update_item aplica max(1, quantity). (Req 12.5)"""
    user, _ = _create_user_and_token(db_session, suffix="_svc_min")

    item = CartItem(user_id=user.id, product_id=sample_product.id, quantity=5)
    db_session.add(item)
    db_session.flush()

    # Update with 0 → should become 1
    updated = cart_service.update_item(db_session, user, item.id, 0)
    assert updated.quantity == 1

    # Update with negative → should become 1
    updated = cart_service.update_item(db_session, user, item.id, -5)
    assert updated.quantity == 1

    # Update with valid value → should be that value
    updated = cart_service.update_item(db_session, user, item.id, 10)
    assert updated.quantity == 10


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Carrinho
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
# Property 14: Estoque disponível desconta reservas de outros usuários
# Feature: testia-suite, Property 14: Estoque disponível desconta reservas de outros usuários
# **Validates: Requirements 7.11, 12.3, 12.7**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
@settings(**_PBT_SETTINGS)
@given(
    stock=st.integers(min_value=0, max_value=500),
    num_others=st.integers(min_value=0, max_value=4),
    other_quantities=st.lists(
        st.integers(min_value=1, max_value=100),
        min_size=0, max_size=4,
    ),
)
def test_property_available_stock_discounts_other_reservations(
    db_session, stock, num_others, other_quantities,
):
    # Feature: testia-suite, Property 14: Estoque disponível desconta reservas de outros usuários
    uid = uuid4().hex[:8]

    # Trim other_quantities to match num_others
    quantities = other_quantities[:num_others]

    product = Product(
        name=f"Prop14_{uid}", description="Desc",
        price=10.0, stock=stock, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    current_user, _ = _create_user_and_token(db_session, suffix=f"_p14cur_{uid}")

    total_reserved = 0
    for i, qty in enumerate(quantities):
        other, _ = _create_user_and_token(db_session, suffix=f"_p14o{i}_{uid}")
        ci = CartItem(user_id=other.id, product_id=product.id, quantity=qty)
        db_session.add(ci)
        db_session.flush()
        total_reserved += qty

    available = cart_service.available_stock_for_user(db_session, product, current_user)
    expected = max(0, stock - total_reserved)
    assert available == expected, (
        f"Expected available={expected} (stock={stock}, reserved={total_reserved}), got {available}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Property 15: Adição ao carrinho incrementa quantidade de item existente
# Feature: testia-suite, Property 15: Adição ao carrinho incrementa quantidade de item existente
# **Validates: Requirements 7.3, 12.4**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
@settings(**_PBT_SETTINGS)
@given(
    initial_qty=st.integers(min_value=1, max_value=30),
    add_qty=st.integers(min_value=1, max_value=30),
)
def test_property_add_to_cart_increments_existing(
    db_session, initial_qty, add_qty,
):
    # Feature: testia-suite, Property 15: Adição ao carrinho incrementa quantidade de item existente
    uid = uuid4().hex[:8]

    total_needed = initial_qty + add_qty
    product = Product(
        name=f"Prop15_{uid}", description="Desc",
        price=10.0, stock=total_needed + 50, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    user, _ = _create_user_and_token(db_session, suffix=f"_p15_{uid}")

    # First add
    item1 = cart_service.add_item(db_session, user, product.id, initial_qty)
    assert item1.quantity == initial_qty

    # Second add → should increment
    item2 = cart_service.add_item(db_session, user, product.id, add_qty)
    assert item2.id == item1.id, "Should be the same cart item, not a new one"
    assert item2.quantity == initial_qty + add_qty


# ═══════════════════════════════════════════════════════════════════════════
# Property 16: Limite de estoque é respeitado no carrinho
# Feature: testia-suite, Property 16: Limite de estoque é respeitado no carrinho
# **Validates: Requirements 7.4, 7.8**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
@settings(**_PBT_SETTINGS)
@given(
    stock=st.integers(min_value=1, max_value=100),
    excess=st.integers(min_value=1, max_value=100),
)
def test_property_stock_limit_respected_in_cart(
    client, db_session, excess, stock,
):
    # Feature: testia-suite, Property 16: Limite de estoque é respeitado no carrinho
    uid = uuid4().hex[:8]

    product = Product(
        name=f"Prop16_{uid}", description="Desc",
        price=10.0, stock=stock, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    user, headers = _create_user_and_token(db_session, suffix=f"_p16_{uid}")

    over_quantity = stock + excess

    # POST with quantity > stock → 422
    resp = client.post(
        "/api/cart",
        json={"product_id": product.id, "quantity": over_quantity},
        headers=headers,
    )
    assert resp.status_code == 422, (
        f"Expected 422 for qty={over_quantity} > stock={stock}, got {resp.status_code}"
    )

    # Add a valid item first, then try to update beyond stock
    resp_add = client.post(
        "/api/cart",
        json={"product_id": product.id, "quantity": 1},
        headers=headers,
    )
    assert resp_add.status_code == 200
    item_id = resp_add.json()["item"]["id"]

    resp_upd = client.put(
        f"/api/cart/{item_id}",
        json={"quantity": over_quantity},
        headers=headers,
    )
    assert resp_upd.status_code == 422, (
        f"Expected 422 for update qty={over_quantity} > stock={stock}, got {resp_upd.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Property 17: Operações no carrinho de outro usuário retornam 404
# Feature: testia-suite, Property 17: Operações no carrinho de outro usuário retornam 404
# **Validates: Requirements 7.10**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
@settings(**_PBT_SETTINGS)
@given(
    operation=st.sampled_from(["update", "delete"]),
)
def test_property_other_user_cart_operations_return_404(
    client, db_session, operation,
):
    # Feature: testia-suite, Property 17: Operações no carrinho de outro usuário retornam 404
    uid = uuid4().hex[:8]

    product = Product(
        name=f"Prop17_{uid}", description="Desc",
        price=10.0, stock=100, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    user_a, _headers_a = _create_user_and_token(db_session, suffix=f"_p17a_{uid}")
    _user_b, headers_b = _create_user_and_token(db_session, suffix=f"_p17b_{uid}")

    # Create cart item for user_a
    cart = CartItem(user_id=user_a.id, product_id=product.id, quantity=2)
    db_session.add(cart)
    db_session.flush()
    item_id = cart.id

    if operation == "update":
        resp = client.put(
            f"/api/cart/{item_id}",
            json={"quantity": 5},
            headers=headers_b,
        )
    else:
        resp = client.delete(
            f"/api/cart/{item_id}",
            headers=headers_b,
        )

    assert resp.status_code == 404, (
        f"Expected 404 for {operation} on other user's cart item, got {resp.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Property 23: Quantidade mínima no carrinho é 1
# Feature: testia-suite, Property 23: Quantidade mínima no carrinho é 1
# **Validates: Requirements 12.5**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.cart
@settings(**_PBT_SETTINGS)
@given(
    quantity=st.integers(max_value=0),
)
def test_property_minimum_cart_quantity_is_one(
    db_session, quantity,
):
    # Feature: testia-suite, Property 23: Quantidade mínima no carrinho é 1
    uid = uuid4().hex[:8]

    product = Product(
        name=f"Prop23_{uid}", description="Desc",
        price=10.0, stock=100, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    user, _ = _create_user_and_token(db_session, suffix=f"_p23_{uid}")

    cart = CartItem(user_id=user.id, product_id=product.id, quantity=5)
    db_session.add(cart)
    db_session.flush()

    updated = cart_service.update_item(db_session, user, cart.id, quantity)
    assert updated.quantity == 1, (
        f"Expected quantity=1 for input={quantity}, got {updated.quantity}"
    )
