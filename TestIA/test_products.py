"""
Testes de produtos — TestIA Suite.

Cobre GET/POST/DELETE /api/products, POST /api/products/{id} (endpoints)
e camada de serviço product_service.
Requisitos: 6.1-6.11, 12.7, 12.8, 13.2, 14.1
"""

import io
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.user import User
from app.services import product_service


# ── Helpers ───────────────────────────────────────────────────────────────

MOCK_SAVE = "app.services.product_service._save_image"
MOCK_REMOVE = "app.services.product_service._remove_image"

VALID_PRODUCT_DATA = {
    "name": "Produto Novo",
    "description": "Descrição válida do produto",
    "price": "29.90",
    "stock": "50",
    "active": "true",
}

VALID_IMAGE = ("test.jpg", b"fake image content", "image/jpeg")


def _product_form(overrides=None):
    """Retorna (data, files) para envio via Form."""
    data = {**VALID_PRODUCT_DATA, **(overrides or {})}
    return data


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — GET /api/products
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
def test_list_products_returns_active_with_stock(client, sample_product):
    """GET /api/products retorna lista de produtos ativos com estoque disponível. (Req 6.1)"""
    resp = client.get("/api/products")

    assert resp.status_code == 200
    data = resp.json()
    assert "products" in data
    products = data["products"]
    assert len(products) >= 1

    found = next((p for p in products if p["id"] == sample_product.id), None)
    assert found is not None
    assert found["name"] == "Produto Teste"
    assert found["active"] is True
    assert "available_stock" in found
    assert found["available_stock"] >= 0


@pytest.mark.products
def test_list_products_excludes_inactive(client, db_session):
    """GET /api/products não retorna produtos inativos. (Req 6.1)"""
    inactive = Product(
        name="Inativo", description="Desc", price=10.0,
        stock=50, image_url="img.jpg", active=False,
    )
    db_session.add(inactive)
    db_session.flush()

    resp = client.get("/api/products")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["products"]]
    assert inactive.id not in ids


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — GET /api/products/{id}
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
def test_get_product_by_id(client, sample_product):
    """GET /api/products/{id} com ID válido retorna detalhes completos. (Req 6.2)"""
    resp = client.get(f"/api/products/{sample_product.id}")

    assert resp.status_code == 200
    data = resp.json()["product"]
    assert data["id"] == sample_product.id
    assert data["name"] == "Produto Teste"
    assert data["description"] == "Descrição teste"
    assert float(data["price"]) == 29.90
    assert data["stock"] == 100
    assert data["active"] is True
    assert "available_stock" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.products
def test_get_product_not_found(client):
    """GET /api/products/{id} com ID inexistente retorna 404. (Req 6.3)"""
    resp = client.get("/api/products/99999")

    assert resp.status_code == 404
    data = resp.json()["detail"]
    assert data["message"] == "Produto nao encontrado."


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — POST /api/products (criação)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@patch(MOCK_SAVE, return_value="/storage/products/fake.jpg")
def test_create_product_admin_valid(mock_save, client, admin_headers):
    """POST /api/products por admin com dados válidos → 201. (Req 6.4)"""
    resp = client.post(
        "/api/products",
        data=_product_form(),
        files={"image": VALID_IMAGE},
        headers=admin_headers,
    )

    assert resp.status_code == 201
    product = resp.json()["product"]
    assert product["name"] == "Produto Novo"
    assert float(product["price"]) == 29.90
    assert product["stock"] == 50
    assert product["active"] is True
    assert "id" in product
    assert "available_stock" in product
    mock_save.assert_called_once()


@pytest.mark.products
@patch(MOCK_SAVE, return_value="/storage/products/fake.jpg")
def test_create_product_non_admin_forbidden(mock_save, client, auth_headers):
    """POST /api/products por não-admin → 403. (Req 6.5)"""
    resp = client.post(
        "/api/products",
        data=_product_form(),
        files={"image": VALID_IMAGE},
        headers=auth_headers,
    )

    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Testes Parametrizados — Validação de campos de produto
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@pytest.mark.parametrize(
    "overrides, files_override, error_field",
    [
        # Nome curto (< 3 chars)
        ({"name": "AB"}, None, "name"),
        # Preço negativo
        ({"price": "-1"}, None, "price"),
        # Estoque negativo
        ({"stock": "-5"}, None, "stock"),
        # Imagem > 10MB
        (
            {},
            {"image": ("big.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")},
            "image",
        ),
    ],
    ids=["short_name", "negative_price", "negative_stock", "image_too_large"],
)
def test_create_product_validation(
    client, admin_headers, overrides, files_override, error_field
):
    """Validação de campos de produto retorna 422. (Req 6.6, 13.2)"""
    data = _product_form(overrides)
    files = files_override or {"image": VALID_IMAGE}

    resp = client.post(
        "/api/products",
        data=data,
        files=files,
        headers=admin_headers,
    )

    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail", body)
    assert detail["message"] == "The given data was invalid."
    assert error_field in detail["errors"]


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — POST /api/products/{id} (atualização)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@patch(MOCK_SAVE, return_value="/storage/products/updated.jpg")
@patch(MOCK_REMOVE)
def test_update_product_admin(mock_remove, mock_save, client, admin_headers, sample_product):
    """POST /api/products/{id} por admin → produto atualizado. (Req 6.7)"""
    resp = client.post(
        f"/api/products/{sample_product.id}",
        data={"name": "Nome Atualizado", "price": "49.90"},
        headers=admin_headers,
    )

    assert resp.status_code == 200
    product = resp.json()["product"]
    assert product["name"] == "Nome Atualizado"
    assert float(product["price"]) == 49.90


@pytest.mark.products
@patch(MOCK_SAVE, return_value="/storage/products/new_img.jpg")
@patch(MOCK_REMOVE)
def test_update_product_with_new_image(mock_remove, mock_save, client, admin_headers, sample_product):
    """Atualização com nova imagem substitui a anterior. (Req 6.8)"""
    resp = client.post(
        f"/api/products/{sample_product.id}",
        data={"name": "Com Imagem Nova"},
        files={"image": ("new.jpg", b"new image data", "image/jpeg")},
        headers=admin_headers,
    )

    assert resp.status_code == 200
    mock_remove.assert_called_once()
    mock_save.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — DELETE /api/products/{id}
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@patch(MOCK_REMOVE)
def test_delete_product_admin(mock_remove, client, admin_headers, sample_product):
    """DELETE /api/products/{id} por admin → produto removido. (Req 6.9)"""
    resp = client.delete(
        f"/api/products/{sample_product.id}",
        headers=admin_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Produto removido."
    mock_remove.assert_called_once()


@pytest.mark.products
def test_delete_product_non_admin_forbidden(client, auth_headers, sample_product):
    """DELETE /api/products/{id} por não-admin → 403. (Req 6.10)"""
    resp = client.delete(
        f"/api/products/{sample_product.id}",
        headers=auth_headers,
    )

    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — Produto inexistente (atualização/exclusão)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
def test_update_nonexistent_product(client, admin_headers):
    """POST /api/products/{id} com ID inexistente → 404. (Req 6.11)"""
    resp = client.post(
        "/api/products/99999",
        data={"name": "Qualquer"},
        headers=admin_headers,
    )

    assert resp.status_code == 404


@pytest.mark.products
def test_delete_nonexistent_product(client, admin_headers):
    """DELETE /api/products/{id} com ID inexistente → 404. (Req 6.11)"""
    resp = client.delete(
        "/api/products/99999",
        headers=admin_headers,
    )

    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Serviço — product_service
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@pytest.mark.service
def test_service_calculate_available_stock(db_session, sample_product):
    """product_service.calculate_available_stock desconta reservas. (Req 12.7)"""
    # Sem reservas → estoque total
    stock = product_service.calculate_available_stock(db_session, sample_product)
    assert stock == 100

    # Adiciona reserva de outro usuário
    from app.models.user import User
    from passlib.hash import bcrypt as bcrypt_hash

    other_user = User(
        name="Other", username="otheruser_stock", phone="11000000000",
        email="other_stock@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=False,
    )
    db_session.add(other_user)
    db_session.flush()

    cart = CartItem(user_id=other_user.id, product_id=sample_product.id, quantity=30)
    db_session.add(cart)
    db_session.flush()

    stock = product_service.calculate_available_stock(db_session, sample_product)
    assert stock == 70


@pytest.mark.products
@pytest.mark.service
def test_service_calculate_available_stock_min_zero(db_session, sample_product):
    """calculate_available_stock nunca retorna negativo. (Req 12.7)"""
    from app.models.user import User
    from passlib.hash import bcrypt as bcrypt_hash

    user = User(
        name="Heavy", username="heavyuser", phone="11000000001",
        email="heavy@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=False,
    )
    db_session.add(user)
    db_session.flush()

    # Reserva maior que estoque
    cart = CartItem(user_id=user.id, product_id=sample_product.id, quantity=200)
    db_session.add(cart)
    db_session.flush()

    stock = product_service.calculate_available_stock(db_session, sample_product)
    assert stock == 0


@pytest.mark.products
@pytest.mark.service
@patch(MOCK_SAVE, return_value="/storage/products/svc.jpg")
def test_service_create_requires_admin(mock_save, db_session):
    """product_service.create exige admin. (Req 12.8)"""
    from passlib.hash import bcrypt as bcrypt_hash

    admin = User(
        name="Admin Svc", username="adminsvc", phone="11000000002",
        email="adminsvc@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=True,
    )
    non_admin = User(
        name="User Svc", username="usersvc", phone="11000000003",
        email="usersvc@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=False,
    )
    db_session.add_all([admin, non_admin])
    db_session.flush()

    mock_image = MagicMock(spec=UploadFile)
    mock_image.filename = "test.jpg"
    mock_image.file = io.BytesIO(b"fake")

    data = {"name": "Svc Product", "description": "Desc", "price": 10.0, "stock": 5}

    # Non-admin → 403
    with pytest.raises(HTTPException) as exc_info:
        product_service.create(db_session, data, mock_image, non_admin)
    assert exc_info.value.status_code == 403

    # Admin → success
    product = product_service.create(db_session, data, mock_image, admin)
    assert product.name == "Svc Product"


@pytest.mark.products
@pytest.mark.service
@patch(MOCK_SAVE, return_value="/storage/products/upd.jpg")
@patch(MOCK_REMOVE)
def test_service_update_requires_admin(mock_remove, mock_save, db_session, sample_product):
    """product_service.update exige admin. (Req 12.8)"""
    from passlib.hash import bcrypt as bcrypt_hash

    admin = User(
        name="Admin Upd", username="adminupd", phone="11000000004",
        email="adminupd@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=True,
    )
    non_admin = User(
        name="User Upd", username="userupd", phone="11000000005",
        email="userupd@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=False,
    )
    db_session.add_all([admin, non_admin])
    db_session.flush()

    # Non-admin → 403
    with pytest.raises(HTTPException) as exc_info:
        product_service.update(db_session, sample_product, {"name": "X"}, None, non_admin)
    assert exc_info.value.status_code == 403

    # Admin → success
    updated = product_service.update(db_session, sample_product, {"name": "Updated"}, None, admin)
    assert updated.name == "Updated"


@pytest.mark.products
@pytest.mark.service
@patch(MOCK_REMOVE)
def test_service_delete_requires_admin(mock_remove, db_session):
    """product_service.delete exige admin. (Req 12.8)"""
    from passlib.hash import bcrypt as bcrypt_hash

    product = Product(
        name="To Delete", description="Desc", price=5.0,
        stock=10, image_url="del.jpg", active=True,
    )
    admin = User(
        name="Admin Del", username="admindel", phone="11000000006",
        email="admindel@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=True,
    )
    non_admin = User(
        name="User Del", username="userdel", phone="11000000007",
        email="userdel@test.com", password=bcrypt_hash.hash("pass123"),
        is_admin=False,
    )
    db_session.add_all([product, admin, non_admin])
    db_session.flush()

    # Non-admin → 403
    with pytest.raises(HTTPException) as exc_info:
        product_service.delete(db_session, product, non_admin)
    assert exc_info.value.status_code == 403

    # Admin → success
    product_service.delete(db_session, product, admin)


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Produtos
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
# Property 11: Listagem retorna apenas ativos com estoque calculado
# Feature: testia-suite, Property 11: Listagem retorna apenas ativos com estoque calculado
# **Validates: Requirements 6.1, 6.2**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@settings(**_PBT_SETTINGS)
@given(
    num_active=st.integers(min_value=0, max_value=3),
    num_inactive=st.integers(min_value=0, max_value=3),
)
def test_property_listing_returns_only_active_with_stock(
    client, db_session, num_active, num_inactive
):
    # Feature: testia-suite, Property 11: Listagem retorna apenas ativos com estoque calculado
    uid = uuid4().hex[:8]

    active_ids = []
    for i in range(num_active):
        p = Product(
            name=f"Active_{uid}_{i}", description="Desc ativo",
            price=10.0, stock=50, image_url="a.jpg", active=True,
        )
        db_session.add(p)
        db_session.flush()
        active_ids.append(p.id)

    inactive_ids = []
    for i in range(num_inactive):
        p = Product(
            name=f"Inactive_{uid}_{i}", description="Desc inativo",
            price=10.0, stock=50, image_url="i.jpg", active=False,
        )
        db_session.add(p)
        db_session.flush()
        inactive_ids.append(p.id)

    resp = client.get("/api/products")
    assert resp.status_code == 200

    returned_ids = [p["id"] for p in resp.json()["products"]]

    # All active products we created must be in the listing
    for aid in active_ids:
        assert aid in returned_ids, f"Active product {aid} missing from listing"

    # No inactive products we created should be in the listing
    for iid in inactive_ids:
        assert iid not in returned_ids, f"Inactive product {iid} should not be in listing"

    # Every returned product must have available_stock field
    for p in resp.json()["products"]:
        assert "available_stock" in p
        assert isinstance(p["available_stock"], int)
        assert p["available_stock"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Property 12: Operações de produto exigem administrador
# Feature: testia-suite, Property 12: Operações de produto exigem administrador
# **Validates: Requirements 6.5, 6.10, 9.2, 9.6, 12.8**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@settings(**_PBT_SETTINGS)
@given(
    operation=st.sampled_from(["create", "update", "delete"]),
)
def test_property_product_operations_require_admin(
    client, db_session, admin_headers, auth_headers,
    sample_product, operation
):
    # Feature: testia-suite, Property 12: Operações de produto exigem administrador

    with patch(MOCK_SAVE, return_value="/storage/products/prop.jpg"), \
         patch(MOCK_REMOVE):

        if operation == "create":
            # Non-admin → 403
            resp_non = client.post(
                "/api/products",
                data=_product_form(),
                files={"image": VALID_IMAGE},
                headers=auth_headers,
            )
            assert resp_non.status_code == 403, (
                f"Non-admin create should be 403, got {resp_non.status_code}"
            )

            # Admin → 201
            resp_admin = client.post(
                "/api/products",
                data=_product_form(),
                files={"image": VALID_IMAGE},
                headers=admin_headers,
            )
            assert resp_admin.status_code == 201, (
                f"Admin create should be 201, got {resp_admin.status_code}: {resp_admin.text}"
            )

        elif operation == "update":
            pid = sample_product.id
            # Non-admin → 403
            resp_non = client.post(
                f"/api/products/{pid}",
                data={"name": "Updated Name"},
                headers=auth_headers,
            )
            assert resp_non.status_code == 403, (
                f"Non-admin update should be 403, got {resp_non.status_code}"
            )

            # Admin → 200
            resp_admin = client.post(
                f"/api/products/{pid}",
                data={"name": "Updated Name"},
                headers=admin_headers,
            )
            assert resp_admin.status_code == 200, (
                f"Admin update should be 200, got {resp_admin.status_code}: {resp_admin.text}"
            )

        elif operation == "delete":
            # Create a product to delete (so we don't conflict across iterations)
            prod = Product(
                name="Del Prop", description="Desc", price=5.0,
                stock=10, image_url="d.jpg", active=True,
            )
            db_session.add(prod)
            db_session.flush()
            pid = prod.id

            # Non-admin → 403
            resp_non = client.delete(f"/api/products/{pid}", headers=auth_headers)
            assert resp_non.status_code == 403, (
                f"Non-admin delete should be 403, got {resp_non.status_code}"
            )

            # Admin → 200
            resp_admin = client.delete(f"/api/products/{pid}", headers=admin_headers)
            assert resp_admin.status_code == 200, (
                f"Admin delete should be 200, got {resp_admin.status_code}: {resp_admin.text}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Property 13: Validação rejeita dados inválidos de produto
# Feature: testia-suite, Property 13: Validação rejeita dados inválidos de produto
# **Validates: Requirements 6.6**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.products
@settings(**_PBT_SETTINGS)
@given(
    invalid_case=st.sampled_from([
        "short_name", "negative_price", "negative_stock", "large_image",
    ]),
    short_name=st.text(min_size=0, max_size=2),
    neg_price=st.floats(max_value=-0.01, allow_nan=False, allow_infinity=False),
    neg_stock=st.integers(max_value=-1),
)
def test_property_validation_rejects_invalid_product_data(
    client, admin_headers,
    invalid_case, short_name, neg_price, neg_stock,
):
    # Feature: testia-suite, Property 13: Validação rejeita dados inválidos de produto

    data = _product_form()
    files = {"image": VALID_IMAGE}

    if invalid_case == "short_name":
        data["name"] = short_name
    elif invalid_case == "negative_price":
        data["price"] = str(neg_price)
    elif invalid_case == "negative_stock":
        data["stock"] = str(neg_stock)
    elif invalid_case == "large_image":
        # Image > 10MB
        files = {"image": ("big.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")}

    resp = client.post(
        "/api/products",
        data=data,
        files=files,
        headers=admin_headers,
    )

    assert resp.status_code == 422, (
        f"Expected 422 for {invalid_case}, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    detail = body.get("detail", body)
    assert detail["message"] == "The given data was invalid."
    assert "errors" in detail
    assert len(detail["errors"]) > 0
