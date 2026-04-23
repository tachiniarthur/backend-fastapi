"""
Testes básicos do serviço de carrinho.
Cobre listagem do carrinho, adição de item e remoção de item.
Requisitos: 4.1, 4.2, 4.3
"""


def test_list_cart(client, auth_headers):
    """Listar carrinho de usuário autenticado retorna 200."""
    response = client.get("/api/cart", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_add_item_to_cart(client, auth_headers, sample_product):
    """Adicionar produto válido ao carrinho retorna 200 e confirmação."""
    response = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "item" in data
    assert data["item"]["product_id"] == sample_product.id
    assert data["item"]["quantity"] == 1


def test_remove_item_from_cart(client, auth_headers, sample_product):
    """Remover item do carrinho retorna 200."""
    # Primeiro adiciona um item ao carrinho
    add_response = client.post(
        "/api/cart",
        json={"product_id": sample_product.id, "quantity": 1},
        headers=auth_headers,
    )
    assert add_response.status_code == 200
    cart_item_id = add_response.json()["item"]["id"]

    # Remove o item
    response = client.delete(f"/api/cart/{cart_item_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "message" in data


# ---------------------------------------------------------------------------
# Testes baseados em propriedades (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.product import Product


# Feature: junior-pleno-test-suite, Property 5: Round-trip do carrinho de compras
# **Validates: Requirements 4.1, 4.2, 4.3**
@given(quantity=st.integers(min_value=1, max_value=10))
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_cart_round_trip(client, db_session, auth_headers, quantity):
    """
    Propriedade 5: Para qualquer usuário autenticado e qualquer produto válido
    com estoque, adicionar o produto ao carrinho via POST /api/cart deve retornar
    200, listar o carrinho via GET /api/cart deve incluir o item adicionado, e
    remover o item via DELETE /api/cart/{id} deve retornar 200 e o item não deve
    mais aparecer na listagem.

    **Validates: Requirements 4.1, 4.2, 4.3**
    """
    # 1. Criar produto no banco
    product = Product(
        name="Produto Round-trip",
        description="Produto para teste de round-trip do carrinho",
        price=19.90,
        stock=100,
        image_url="/storage/products/roundtrip.jpg",
        active=True,
    )
    db_session.add(product)
    db_session.flush()

    # 2. Adicionar produto ao carrinho via POST /api/cart
    add_response = client.post(
        "/api/cart",
        json={"product_id": product.id, "quantity": quantity},
        headers=auth_headers,
    )
    assert add_response.status_code == 200, (
        f"Esperado 200 ao adicionar ao carrinho, obteve {add_response.status_code} - {add_response.text}"
    )
    add_data = add_response.json()
    assert "item" in add_data
    cart_item_id = add_data["item"]["id"]

    # 3. Listar carrinho via GET /api/cart e verificar que o item está presente
    list_response = client.get("/api/cart", headers=auth_headers)
    assert list_response.status_code == 200, (
        f"Esperado 200 ao listar carrinho, obteve {list_response.status_code}"
    )
    list_data = list_response.json()
    assert "items" in list_data
    item_ids = [item["id"] for item in list_data["items"]]
    assert cart_item_id in item_ids, (
        f"Item {cart_item_id} não encontrado no carrinho após adição"
    )

    # 4. Remover item via DELETE /api/cart/{id}
    delete_response = client.delete(
        f"/api/cart/{cart_item_id}", headers=auth_headers
    )
    assert delete_response.status_code == 200, (
        f"Esperado 200 ao remover item, obteve {delete_response.status_code}"
    )

    # 5. Listar carrinho novamente e verificar que o item foi removido
    list_after_response = client.get("/api/cart", headers=auth_headers)
    assert list_after_response.status_code == 200
    list_after_data = list_after_response.json()
    remaining_ids = [item["id"] for item in list_after_data["items"]]
    assert cart_item_id not in remaining_ids, (
        f"Item {cart_item_id} ainda presente no carrinho após remoção"
    )
