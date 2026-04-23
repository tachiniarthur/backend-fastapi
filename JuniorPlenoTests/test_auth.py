"""
Testes básicos do serviço de autenticação.
Cobre happy paths de registro, login, login inválido e logout.
Requisitos: 2.1, 2.2, 2.3, 2.4
"""


def test_register_valid_user(client):
    """Registro com dados válidos retorna 201 e dados do usuário criado."""
    payload = {
        "name": "Maria Silva",
        "username": "mariasilva",
        "phone": "11988887777",
        "email": "maria@example.com",
        "password": "senha123",
        "password_confirmation": "senha123",
    }

    response = client.post("/api/create-account", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Conta criada com sucesso"
    assert data["user"]["name"] == "Maria Silva"
    assert data["user"]["email"] == "maria@example.com"
    assert "token" in data


def test_login_valid_credentials(client):
    """Login com credenciais válidas retorna 200 e token."""
    # Primeiro cria a conta
    client.post("/api/create-account", json={
        "name": "João Teste",
        "username": "joaoteste",
        "phone": "11977776666",
        "email": "joao@example.com",
        "password": "senha123",
        "password_confirmation": "senha123",
    })

    # Depois faz login
    response = client.post("/api/login", json={
        "email": "joao@example.com",
        "password": "senha123",
    })

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["email"] == "joao@example.com"


def test_login_invalid_credentials(client):
    """Login com credenciais inválidas retorna 401."""
    response = client.post("/api/login", json={
        "email": "naoexiste@example.com",
        "password": "senhaerrada",
    })

    assert response.status_code == 401


def test_logout_valid_token(client, auth_headers):
    """Logout com token válido retorna 200."""
    response = client.post("/api/logout", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Logout realizado."


# ---------------------------------------------------------------------------
# Testes baseados em propriedades (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


# Estratégias para gerar dados de registro válidos
valid_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Zs")),
    min_size=1,
    max_size=50,
).map(str.strip).filter(lambda s: len(s) >= 1)

valid_usernames = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    min_size=3,
    max_size=30,
).filter(lambda s: s.isalnum() and len(s) >= 3)

valid_emails = st.emails().filter(lambda e: e.isascii() and "xn--" not in e.lower())

valid_passwords = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Nd", "P")),
    min_size=6,
    max_size=30,
).filter(lambda s: len(s) >= 6)

valid_phones = st.from_regex(r"[0-9]{10,15}", fullmatch=True)


# Feature: junior-pleno-test-suite, Property 1: Round-trip do ciclo de autenticação
# **Validates: Requirements 2.1, 2.2, 2.4**
@given(
    name=valid_names,
    username=valid_usernames,
    email=valid_emails,
    password=valid_passwords,
    phone=valid_phones,
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_auth_round_trip(client, db_session, name, username, email, password, phone):
    """
    Propriedade 1: Para qualquer conjunto válido de dados de registro,
    registrar → login → logout deve completar com sucesso.

    **Validates: Requirements 2.1, 2.2, 2.4**
    """
    import uuid

    # Tornar username e email únicos por iteração para evitar conflitos
    suffix = uuid.uuid4().hex[:8]
    unique_username = f"{username}{suffix}"[:50]
    local, domain = email.rsplit("@", 1)
    unique_email = f"{local}+{suffix}@{domain}"

    # 1. Registrar conta
    register_payload = {
        "name": name,
        "username": unique_username,
        "phone": phone,
        "email": unique_email,
        "password": password,
        "password_confirmation": password,
    }
    register_resp = client.post("/api/create-account", json=register_payload)

    assert register_resp.status_code == 201, (
        f"Registro falhou: {register_resp.status_code} - {register_resp.text}"
    )
    register_data = register_resp.json()
    assert register_data["message"] == "Conta criada com sucesso"
    assert "token" in register_data

    # 2. Login com as mesmas credenciais
    login_resp = client.post("/api/login", json={
        "email": unique_email,
        "password": password,
    })
    assert login_resp.status_code == 200, (
        f"Login falhou: {login_resp.status_code} - {login_resp.text}"
    )
    login_data = login_resp.json()
    assert "token" in login_data
    # EmailStr normaliza para lowercase, comparar case-insensitive
    assert login_data["user"]["email"].lower() == unique_email.lower()

    # 3. Logout com o token obtido no login
    token = login_data["token"]
    logout_resp = client.post(
        "/api/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_resp.status_code == 200, (
        f"Logout falhou: {logout_resp.status_code} - {logout_resp.text}"
    )
    assert logout_resp.json()["message"] == "Logout realizado."


# Feature: junior-pleno-test-suite, Property 2: Credenciais inválidas são rejeitadas
# **Validates: Requirements 2.3**
@given(
    email=valid_emails,
    password=valid_passwords,
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invalid_credentials_rejected(client, email, password):
    """
    Propriedade 2: Para qualquer combinação de email e senha que não
    corresponda a um usuário registrado, o endpoint /api/login deve
    retornar status 401.

    **Validates: Requirements 2.3**
    """
    response = client.post("/api/login", json={
        "email": email,
        "password": password,
    })

    assert response.status_code == 401, (
        f"Esperado 401 para credenciais aleatórias, obteve {response.status_code} - {response.text}"
    )
