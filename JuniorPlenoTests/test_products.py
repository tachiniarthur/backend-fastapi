"""
Testes básicos do serviço de produtos.
Cobre listagem de produtos, consulta por ID e produto inexistente.
Requisitos: 3.1, 3.2, 3.3
"""


def test_list_products(client, sample_product):
    """Listagem de produtos retorna 200 e uma lista com produtos."""
    response = client.get("/api/products")

    assert response.status_code == 200
    data = response.json()
    assert "products" in data
    assert isinstance(data["products"], list)
    assert len(data["products"]) >= 1

    # Verifica que o produto de teste está na lista
    names = [p["name"] for p in data["products"]]
    assert sample_product.name in names


def test_get_product_by_id(client, sample_product):
    """Consulta por ID existente retorna 200 e os dados do produto."""
    response = client.get(f"/api/products/{sample_product.id}")

    assert response.status_code == 200
    data = response.json()
    assert "product" in data
    product = data["product"]
    assert product["id"] == sample_product.id
    assert product["name"] == sample_product.name
    assert product["description"] == sample_product.description
    assert float(product["price"]) == float(sample_product.price)


def test_get_product_not_found(client):
    """Consulta por ID inexistente retorna 404."""
    response = client.get("/api/products/999999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Testes baseados em propriedades (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.product import Product


# Estratégias para gerar dados de produtos válidos
product_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Nd", "Zs")),
    min_size=3,
    max_size=50,
).map(str.strip).filter(lambda s: len(s) >= 3)

product_descriptions = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Nd", "Zs")),
    min_size=3,
    max_size=100,
).map(str.strip).filter(lambda s: len(s) >= 3)

product_prices = st.decimals(
    min_value="0.01",
    max_value="9999.99",
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

product_stocks = st.integers(min_value=0, max_value=10000)

product_data_strategy = st.lists(
    st.tuples(product_names, product_descriptions, product_prices, product_stocks),
    min_size=1,
    max_size=5,
)


# Feature: junior-pleno-test-suite, Property 3: Listagem de produtos retorna todos os produtos ativos
# **Validates: Requirements 3.1**
@given(products_data=product_data_strategy)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_list_products_returns_all_active(client, db_session, products_data):
    """
    Propriedade 3: Para qualquer conjunto de produtos ativos inseridos no banco,
    o endpoint /api/products deve retornar status 200 e uma lista contendo
    exatamente os produtos ativos.

    **Validates: Requirements 3.1**
    """
    # 1. Inserir produtos no banco via db_session
    inserted_products = []
    for name, description, price, stock in products_data:
        product = Product(
            name=name,
            description=description,
            price=float(price),
            stock=stock,
            image_url="/storage/products/test.jpg",
            active=True,
        )
        db_session.add(product)
        db_session.flush()
        inserted_products.append(product)

    # 2. Chamar GET /api/products
    response = client.get("/api/products")

    assert response.status_code == 200, (
        f"Esperado 200, obteve {response.status_code} - {response.text}"
    )

    data = response.json()
    assert "products" in data
    returned_products = data["products"]

    # 3. Verificar que todos os produtos inseridos aparecem na resposta
    returned_ids = {p["id"] for p in returned_products}
    for product in inserted_products:
        assert product.id in returned_ids, (
            f"Produto '{product.name}' (id={product.id}) não encontrado na listagem"
        )

    # Verificar que a quantidade retornada é >= a quantidade inserida
    assert len(returned_products) >= len(inserted_products), (
        f"Esperado pelo menos {len(inserted_products)} produtos, obteve {len(returned_products)}"
    )


# Feature: junior-pleno-test-suite, Property 4: Consulta de produto por ID retorna dados corretos
# **Validates: Requirements 3.2, 3.3**
@given(
    name=product_names,
    description=product_descriptions,
    price=product_prices,
    stock=product_stocks,
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_get_product_by_id_returns_correct_data(client, db_session, name, description, price, stock):
    """
    Propriedade 4 (parte 1 — ID válido): Para qualquer produto existente no banco,
    consultar /api/products/{id} deve retornar status 200 e os dados correspondentes.

    **Validates: Requirements 3.2, 3.3**
    """
    # 1. Criar produto no banco
    product = Product(
        name=name,
        description=description,
        price=float(price),
        stock=stock,
        image_url="/storage/products/test.jpg",
        active=True,
    )
    db_session.add(product)
    db_session.flush()

    # 2. Consultar por ID
    response = client.get(f"/api/products/{product.id}")

    assert response.status_code == 200, (
        f"Esperado 200 para produto id={product.id}, obteve {response.status_code}"
    )

    data = response.json()
    assert "product" in data
    returned = data["product"]

    # 3. Verificar que os dados retornados correspondem ao produto criado
    assert returned["id"] == product.id
    assert returned["name"] == product.name
    assert returned["description"] == product.description
    assert float(returned["price"]) == float(product.price)


@given(invalid_id=st.integers(min_value=900000, max_value=999999))
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_get_product_by_invalid_id_returns_404(client, invalid_id):
    """
    Propriedade 4 (parte 2 — ID inválido): Para qualquer ID que não corresponda
    a um produto existente, /api/products/{id} deve retornar 404.

    **Validates: Requirements 3.2, 3.3**
    """
    response = client.get(f"/api/products/{invalid_id}")

    assert response.status_code == 404, (
        f"Esperado 404 para id={invalid_id}, obteve {response.status_code}"
    )
