"""
Testes básicos do serviço de pedidos.
Cobre listagem de pedidos e criação de pedido com itens válidos.
Requisitos: 5.1, 5.2
"""


def test_list_orders(client, auth_headers):
    """Listar pedidos de usuário autenticado retorna 200."""
    response = client.get("/api/orders", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_order(client, auth_headers, sample_product):
    """Criar pedido com itens válidos retorna 201 e dados do pedido."""
    response = client.post(
        "/api/orders",
        json={
            "items": [
                {"product_id": sample_product.id, "quantity": 2}
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == sample_product.id
    assert data["items"][0]["quantity"] == 2


# ---------------------------------------------------------------------------
# Testes baseados em propriedades (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from app.models.product import Product


# Feature: junior-pleno-test-suite, Property 6: Round-trip de criação de pedido
# **Validates: Requirements 5.1, 5.2**
@given(quantity=st.integers(min_value=1, max_value=5))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_order_creation_roundtrip(client, auth_headers, db_session, quantity):
    """
    Propriedade 6: Para qualquer usuário autenticado com itens válidos,
    criar um pedido via POST /api/orders deve retornar 201, e listar
    pedidos via GET /api/orders deve incluir o pedido recém-criado.
    """
    # Criar produto no banco com estoque suficiente
    product = Product(
        name="Prop Test Product",
        description="Produto gerado por Hypothesis",
        price=10.00,
        stock=100,
        image_url="/storage/products/hypothesis.jpg",
        active=True,
    )
    db_session.add(product)
    db_session.flush()

    # Criar pedido via POST
    create_resp = client.post(
        "/api/orders",
        json={"items": [{"product_id": product.id, "quantity": quantity}]},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    created_order = create_resp.json()
    order_id = created_order["id"]

    # Listar pedidos via GET e verificar que o pedido aparece
    list_resp = client.get("/api/orders", headers=auth_headers)
    assert list_resp.status_code == 200
    orders = list_resp.json()
    order_ids = [o["id"] for o in orders]
    assert order_id in order_ids, (
        f"Pedido {order_id} não encontrado na listagem. IDs: {order_ids}"
    )
