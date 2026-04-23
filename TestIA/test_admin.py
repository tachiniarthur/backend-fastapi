"""
Testes de administração — TestIA Suite.

Cobre GET /api/admin/orders, PATCH /api/admin/orders/{id}/status (endpoints)
e camada de serviço order_service (list_all, update_status).
Requisitos: 9.1-9.6, 13.1
"""

import hashlib
import os

import pytest
from passlib.hash import bcrypt
from uuid import uuid4

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
        name=f"Admin Test User{suffix}",
        username=f"admintestuser{suffix}",
        phone="11999999999",
        email=f"admintest{suffix}@example.com",
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


def _create_order_for_user(db_session, user, product, quantity=2):
    """Helper: cria um pedido para o usuário via order_service."""
    class FakeItem:
        def __init__(self, product_id, qty):
            self.product_id = product_id
            self.quantity = qty

    return order_service.create_from_cart(db_session, user, [FakeItem(product.id, quantity)])


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — GET /api/admin/orders
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.admin
def test_admin_get_orders_returns_all_orders_with_user_data(client, db_session):
    """GET /api/admin/orders por admin → todos os pedidos com dados dos usuários. (Req 9.1)"""
    admin_user, admin_hdrs = _create_user_and_token(db_session, is_admin=True, suffix="_adm_list")
    regular_user, _ = _create_user_and_token(db_session, is_admin=False, suffix="_reg_list")

    product = Product(
        name="Produto Admin List", description="Desc", price=50.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    # Create orders for both users
    _create_order_for_user(db_session, admin_user, product, quantity=1)
    _create_order_for_user(db_session, regular_user, product, quantity=2)

    resp = client.get("/api/admin/orders", headers=admin_hdrs)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Verify user data is present in each order
    for order in data:
        assert "user" in order
        assert "id" in order["user"]
        assert "name" in order["user"]
        assert "email" in order["user"]
        assert "items" in order
        assert "status" in order


@pytest.mark.admin
def test_admin_get_orders_non_admin_returns_403(client, db_session):
    """GET /api/admin/orders por não-admin → status 403. (Req 9.2)"""
    _user, headers = _create_user_and_token(db_session, is_admin=False, suffix="_nonadm_list")

    resp = client.get("/api/admin/orders", headers=headers)
    assert resp.status_code == 403

    data = resp.json()
    assert data["detail"]["message"] == "Acesso negado."


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — PATCH /api/admin/orders/{id}/status
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.admin
def test_admin_update_order_status_valid(client, db_session):
    """PATCH /api/admin/orders/{id}/status com status válido → status atualizado. (Req 9.3)"""
    admin_user, admin_hdrs = _create_user_and_token(db_session, is_admin=True, suffix="_adm_upd")
    regular_user, _ = _create_user_and_token(db_session, is_admin=False, suffix="_reg_upd")

    product = Product(
        name="Produto Status", description="Desc", price=30.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    order = _create_order_for_user(db_session, regular_user, product, quantity=1)

    resp = client.patch(
        f"/api/admin/orders/{order.id}/status",
        json={"status": "completed"},
        headers=admin_hdrs,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["id"] == order.id
    assert "user" in data


@pytest.mark.admin
@pytest.mark.parametrize("valid_status", ["pending", "processing", "completed", "cancelled"])
def test_admin_update_order_status_parametrized(client, db_session, valid_status):
    """Teste parametrizado com múltiplos status válidos. (Req 9.3, 13.1)"""
    uid = uuid4().hex[:6]
    admin_user, admin_hdrs = _create_user_and_token(db_session, is_admin=True, suffix=f"_adm_p_{uid}")
    regular_user, _ = _create_user_and_token(db_session, is_admin=False, suffix=f"_reg_p_{uid}")

    product = Product(
        name=f"Prod Param {uid}", description="Desc", price=20.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    order = _create_order_for_user(db_session, regular_user, product, quantity=1)

    resp = client.patch(
        f"/api/admin/orders/{order.id}/status",
        json={"status": valid_status},
        headers=admin_hdrs,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == valid_status


@pytest.mark.admin
def test_admin_update_order_status_invalid_returns_422(client, db_session):
    """PATCH com status inválido → status 422. (Req 9.4)"""
    admin_user, admin_hdrs = _create_user_and_token(db_session, is_admin=True, suffix="_adm_inv")
    regular_user, _ = _create_user_and_token(db_session, is_admin=False, suffix="_reg_inv")

    product = Product(
        name="Produto Invalid", description="Desc", price=20.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    order = _create_order_for_user(db_session, regular_user, product, quantity=1)

    resp = client.patch(
        f"/api/admin/orders/{order.id}/status",
        json={"status": "invalid_status"},
        headers=admin_hdrs,
    )

    assert resp.status_code == 422


@pytest.mark.admin
def test_admin_update_order_status_nonexistent_order_returns_404(client, db_session):
    """PATCH com pedido inexistente → status 404. (Req 9.5)"""
    _admin, admin_hdrs = _create_user_and_token(db_session, is_admin=True, suffix="_adm_404")

    resp = client.patch(
        "/api/admin/orders/99999/status",
        json={"status": "completed"},
        headers=admin_hdrs,
    )

    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"]["message"] == "Pedido nao encontrado."


@pytest.mark.admin
def test_admin_update_order_status_non_admin_returns_403(client, db_session):
    """PATCH por não-admin → status 403. (Req 9.6)"""
    admin_user, admin_hdrs = _create_user_and_token(db_session, is_admin=True, suffix="_adm_403")
    regular_user, regular_hdrs = _create_user_and_token(db_session, is_admin=False, suffix="_reg_403")

    product = Product(
        name="Produto 403", description="Desc", price=20.0,
        stock=100, image_url="img.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    order = _create_order_for_user(db_session, regular_user, product, quantity=1)

    resp = client.patch(
        f"/api/admin/orders/{order.id}/status",
        json={"status": "completed"},
        headers=regular_hdrs,
    )

    assert resp.status_code == 403
    data = resp.json()
    assert data["detail"]["message"] == "Acesso negado."


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Administração
# ═══════════════════════════════════════════════════════════════════════════

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

VALID_STATUSES = ["pending", "processing", "completed", "cancelled"]


# ═══════════════════════════════════════════════════════════════════════════
# Property 20: Atualização de status de pedido com valores válidos
# Feature: testia-suite, Property 20: Atualização de status com valores válidos
# **Validates: Requirements 9.3, 9.4**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.admin
@settings(**_PBT_SETTINGS)
@given(
    status_value=st.one_of(
        # Valid statuses
        st.sampled_from(VALID_STATUSES),
        # Invalid statuses: random strings that are NOT in the valid set
        st.text(min_size=1, max_size=30).filter(lambda s: s not in VALID_STATUSES),
    ),
)
def test_property_admin_update_status_valid_and_invalid(
    client, db_session, status_value,
):
    # Feature: testia-suite, Property 20: Atualização de status com valores válidos
    # **Validates: Requirements 9.3, 9.4**
    uid = uuid4().hex[:8]

    admin_user, admin_hdrs = _create_user_and_token(
        db_session, is_admin=True, suffix=f"_p20a_{uid}",
    )
    regular_user, _ = _create_user_and_token(
        db_session, is_admin=False, suffix=f"_p20r_{uid}",
    )

    product = Product(
        name=f"Prop20_{uid}", description="Desc",
        price=10.0, stock=100, image_url="p.jpg", active=True,
    )
    db_session.add(product)
    db_session.flush()

    order = _create_order_for_user(db_session, regular_user, product, quantity=1)

    resp = client.patch(
        f"/api/admin/orders/{order.id}/status",
        json={"status": status_value},
        headers=admin_hdrs,
    )

    if status_value in VALID_STATUSES:
        assert resp.status_code == 200, (
            f"Expected 200 for valid status '{status_value}', got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert data["status"] == status_value
        assert data["id"] == order.id
        assert "user" in data
    else:
        assert resp.status_code == 422, (
            f"Expected 422 for invalid status '{status_value}', got {resp.status_code}: {resp.text}"
        )
