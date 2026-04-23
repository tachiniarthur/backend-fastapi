"""
Testes unitários de autenticação — TestIA Suite.

Cobre registro, login, logout (endpoints) e camada de serviço auth_service.
Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 12.1, 12.2, 13.3
"""

import pytest
from passlib.hash import bcrypt

from app.models.personal_access_token import PersonalAccessToken
from app.services import auth_service


# ── Dados auxiliares ──────────────────────────────────────────────────────

VALID_REGISTER_PAYLOAD = {
    "name": "Maria Silva",
    "username": "mariasilva",
    "phone": "11988887777",
    "email": "maria@example.com",
    "password": "senha123",
    "password_confirmation": "senha123",
}


def _register(client, **overrides):
    """Helper: envia POST /api/create-account com payload padrão + overrides."""
    payload = {**VALID_REGISTER_PAYLOAD, **overrides}
    return client.post("/api/create-account", json=payload)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Registro com dados válidos → 201, dados do usuário e token
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_register_valid_data(client):
    """Registro com dados válidos retorna 201, dados do usuário e token."""
    resp = _register(client)

    assert resp.status_code == 201
    data = resp.json()
    assert data["message"] == "Conta criada com sucesso"
    assert data["user"]["name"] == "Maria Silva"
    assert data["user"]["email"] == "maria@example.com"
    assert data["user"]["username"] == "mariasilva"
    assert "token" in data
    # Token no formato {id}|{plain_token}
    parts = data["token"].split("|", 1)
    assert len(parts) == 2
    assert parts[0].isdigit()
    assert len(parts[1]) == 80  # os.urandom(40).hex() → 80 chars


# ═══════════════════════════════════════════════════════════════════════════
# 2. Registro com email duplicado → 422
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_register_duplicate_email(client):
    """Registro com email já cadastrado retorna 422 com erro de email."""
    _register(client)
    resp = _register(client, username="outrouser")

    assert resp.status_code == 422
    body = resp.json()
    data = body.get("detail", body)
    assert data["message"] == "The given data was invalid."
    assert "email" in data["errors"]
    assert "O email ja esta em uso." in data["errors"]["email"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. Registro com username duplicado → 422
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_register_duplicate_username(client):
    """Registro com username já cadastrado retorna 422 com erro de username."""
    _register(client)
    resp = _register(client, email="outro@example.com")

    assert resp.status_code == 422
    body = resp.json()
    data = body.get("detail", body)
    assert data["message"] == "The given data was invalid."
    assert "username" in data["errors"]
    assert "O username ja esta em uso." in data["errors"]["username"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Registro com senhas não coincidentes → 422
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_register_password_mismatch(client):
    """Senhas diferentes retornam 422 com erro de confirmação."""
    resp = _register(client, password_confirmation="outrasenha")

    assert resp.status_code == 422
    body = resp.json()
    data = body.get("detail", body)
    assert data["message"] == "The given data was invalid."
    assert "password_confirmation" in data["errors"]
    assert "As senhas nao conferem." in data["errors"]["password_confirmation"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Parametrizado — dados inválidos de registro → 422
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@pytest.mark.parametrize(
    "overrides, error_field",
    [
        # Senha curta (< 6 chars)
        ({"password": "abc", "password_confirmation": "abc"}, "password"),
        # Email inválido
        ({"email": "nao-e-email"}, "email"),
        # Campo name ausente
        ({"name": None}, "name"),
        # Campo username ausente
        ({"username": None}, "username"),
        # Campo email ausente
        ({"email": None}, "email"),
    ],
    ids=[
        "short_password",
        "invalid_email",
        "missing_name",
        "missing_username",
        "missing_email",
    ],
)
def test_register_invalid_data(client, overrides, error_field):
    """Dados inválidos de registro retornam 422 com erro no campo esperado."""
    payload = {**VALID_REGISTER_PAYLOAD, **overrides}
    # Remove campos None para simular ausência
    payload = {k: v for k, v in payload.items() if v is not None}
    resp = client.post("/api/create-account", json=payload)

    assert resp.status_code == 422
    data = resp.json()
    assert data["message"] == "The given data was invalid."
    assert error_field in data["errors"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. Login com credenciais válidas → dados do usuário e token
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_login_valid_credentials(client):
    """Login com credenciais válidas retorna 200, dados do usuário e token."""
    # Cria conta primeiro
    _register(client)

    resp = client.post("/api/login", json={
        "email": "maria@example.com",
        "password": "senha123",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "maria@example.com"
    assert data["user"]["name"] == "Maria Silva"
    assert "token" in data
    parts = data["token"].split("|", 1)
    assert len(parts) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 7. Login com credenciais inválidas → 401
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_login_invalid_credentials(client):
    """Login com credenciais inválidas retorna 401."""
    resp = client.post("/api/login", json={
        "email": "naoexiste@example.com",
        "password": "senhaerrada",
    })

    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["message"] == "Credenciais invalidas"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Logout com token válido → token invalidado
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
def test_logout_invalidates_token(client, db_session, auth_headers):
    """Logout com token válido retorna 200 e invalida o token no banco."""
    # Logout
    resp = client.post("/api/logout", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logout realizado."

    # Verifica que o token foi deletado do banco
    token_str = auth_headers["Authorization"].replace("Bearer ", "")
    token_id = int(token_str.split("|")[0])
    token_record = (
        db_session.query(PersonalAccessToken)
        .filter(PersonalAccessToken.id == token_id)
        .first()
    )
    assert token_record is None, "Token deveria ter sido deletado após logout"


# ═══════════════════════════════════════════════════════════════════════════
# 9. Serviço auth_service.create → senha hasheada e token {id}|{plain_token}
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@pytest.mark.service
def test_auth_service_create(db_session):
    """auth_service.create hasheia a senha e retorna token no formato correto."""
    from types import SimpleNamespace

    data = SimpleNamespace(
        name="Serviço User",
        username="servicouser",
        phone="11900001111",
        email="servico@example.com",
        password="senha123",
        password_confirmation="senha123",
    )

    result = auth_service.create(db_session, data)

    user = result["user"]
    token = result["token"]

    # Senha deve estar hasheada (bcrypt)
    assert user.password != "senha123"
    assert bcrypt.verify("senha123", user.password)

    # Token no formato {id}|{plain_token}
    parts = token.split("|", 1)
    assert len(parts) == 2
    token_id_str, plain_token = parts
    assert token_id_str.isdigit()
    assert len(plain_token) == 80  # os.urandom(40).hex()

    # Verifica que o hash armazenado no banco confere
    import hashlib
    token_record = (
        db_session.query(PersonalAccessToken)
        .filter(PersonalAccessToken.id == int(token_id_str))
        .first()
    )
    assert token_record is not None
    expected_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    assert token_record.token == expected_hash


# ═══════════════════════════════════════════════════════════════════════════
# 10. Serviço auth_service.login → None para inválido, dados+token para válido
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@pytest.mark.service
def test_auth_service_login_valid(db_session):
    """auth_service.login retorna dados do usuário e token para credenciais válidas."""
    from types import SimpleNamespace

    data = SimpleNamespace(
        name="Login User",
        username="loginuser",
        phone="11900002222",
        email="login@example.com",
        password="senha123",
        password_confirmation="senha123",
    )
    auth_service.create(db_session, data)

    result = auth_service.login(db_session, "login@example.com", "senha123")

    assert result is not None
    assert result["user"].email == "login@example.com"
    assert "|" in result["token"]


@pytest.mark.auth
@pytest.mark.service
def test_auth_service_login_invalid(db_session):
    """auth_service.login retorna None para credenciais inválidas."""
    # Email inexistente
    result = auth_service.login(db_session, "naoexiste@example.com", "qualquer")
    assert result is None


@pytest.mark.auth
@pytest.mark.service
def test_auth_service_login_wrong_password(db_session):
    """auth_service.login retorna None para senha incorreta."""
    from types import SimpleNamespace

    data = SimpleNamespace(
        name="Wrong Pass User",
        username="wrongpassuser",
        phone="11900003333",
        email="wrongpass@example.com",
        password="senha123",
        password_confirmation="senha123",
    )
    auth_service.create(db_session, data)

    result = auth_service.login(db_session, "wrongpass@example.com", "senhaerrada")
    assert result is None



# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Autenticação
# ═══════════════════════════════════════════════════════════════════════════

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
import uuid as uuid_mod

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _unique_id():
    """Runtime unique suffix (not Hypothesis-managed) to avoid collisions."""
    return uuid_mod.uuid4().hex


# ── Estratégias reutilizáveis ─────────────────────────────────────────────

def _valid_name():
    """Gera nomes válidos: 3-100 caracteres, printable."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Z"),
            blacklist_characters="\x00",
        ),
        min_size=3,
        max_size=100,
    ).filter(lambda s: len(s.strip()) >= 3)


def _valid_password():
    """Gera senhas válidas: >=6 caracteres, printable."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P"),
            blacklist_characters="\x00",
        ),
        min_size=6,
        max_size=30,
    ).filter(lambda s: len(s.strip()) >= 6)


# ═══════════════════════════════════════════════════════════════════════════
# Property 3: Registro com dados válidos retorna 201 e token
# Feature: testia-suite, Property 3: Registro com dados válidos retorna 201 e token
# **Validates: Requirements 4.1, 12.1**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@settings(**_PBT_SETTINGS)
@given(
    name=_valid_name(),
    password=_valid_password(),
)
def test_property_register_valid_data_returns_201_and_token(client, name, password):
    # Feature: testia-suite, Property 3: Registro com dados válidos retorna 201 e token
    uid = _unique_id()
    username = f"r{uid[:20]}"
    email = f"r{uid}@test.com"

    payload = {
        "name": name,
        "username": username,
        "phone": "11999990000",
        "email": email,
        "password": password,
        "password_confirmation": password,
    }
    resp = client.post("/api/create-account", json=payload)

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "token" in data
    parts = data["token"].split("|", 1)
    assert len(parts) == 2, "Token must be in format {id}|{plain_token}"
    assert parts[0].isdigit(), "Token ID must be numeric"
    assert len(parts[1]) == 80, "Plain token must be 80 hex chars"
    assert data["user"]["email"] == email
    assert data["user"]["username"] == username


# ═══════════════════════════════════════════════════════════════════════════
# Property 4: Campos únicos duplicados são rejeitados no registro
# Feature: testia-suite, Property 4: Campos únicos duplicados são rejeitados no registro
# **Validates: Requirements 4.2, 4.3**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@settings(**_PBT_SETTINGS)
@given(
    duplicate_field=st.sampled_from(["email", "username"]),
)
def test_property_duplicate_unique_fields_rejected(client, duplicate_field):
    # Feature: testia-suite, Property 4: Campos únicos duplicados são rejeitados no registro
    uid = _unique_id()
    base_payload = {
        "name": "Dup Test",
        "username": f"d{uid[:20]}",
        "phone": "11999990000",
        "email": f"d{uid}@test.com",
        "password": "senha123",
        "password_confirmation": "senha123",
    }

    # First registration must succeed
    resp1 = client.post("/api/create-account", json=base_payload)
    assert resp1.status_code == 201, f"First register failed: {resp1.text}"

    # Second registration with same email or username must fail
    other = _unique_id()
    second_payload = {
        **base_payload,
        "username": f"o{other[:20]}" if duplicate_field == "email" else base_payload["username"],
        "email": f"o{other}@test.com" if duplicate_field == "username" else base_payload["email"],
    }
    resp2 = client.post("/api/create-account", json=second_payload)

    assert resp2.status_code == 422, f"Expected 422, got {resp2.status_code}: {resp2.text}"
    body = resp2.json()
    data = body.get("detail", body)
    assert data["message"] == "The given data was invalid."
    assert duplicate_field in data["errors"]


# ═══════════════════════════════════════════════════════════════════════════
# Property 5: Senhas não coincidentes são rejeitadas
# Feature: testia-suite, Property 5: Senhas não coincidentes são rejeitadas
# **Validates: Requirements 4.4**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@settings(**_PBT_SETTINGS)
@given(
    password=_valid_password(),
    confirmation=_valid_password(),
)
def test_property_mismatched_passwords_rejected(client, password, confirmation):
    # Feature: testia-suite, Property 5: Senhas não coincidentes são rejeitadas
    assume(password != confirmation)

    uid = _unique_id()
    payload = {
        "name": "Mismatch Test",
        "username": f"m{uid[:20]}",
        "phone": "11999990000",
        "email": f"m{uid}@test.com",
        "password": password,
        "password_confirmation": confirmation,
    }
    resp = client.post("/api/create-account", json=payload)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    body = resp.json()
    data = body.get("detail", body)
    assert data["message"] == "The given data was invalid."
    assert "password_confirmation" in data["errors"]
    assert "As senhas nao conferem." in data["errors"]["password_confirmation"]


# ═══════════════════════════════════════════════════════════════════════════
# Property 6: Login com credenciais válidas retorna token
# Feature: testia-suite, Property 6: Login com credenciais válidas retorna token
# **Validates: Requirements 4.5, 4.6, 12.2**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@settings(**_PBT_SETTINGS)
@given(
    password=_valid_password(),
)
def test_property_login_valid_credentials_returns_token(client, password):
    # Feature: testia-suite, Property 6: Login com credenciais válidas retorna token
    uid = _unique_id()
    email = f"l{uid}@test.com"

    # Register first
    reg_payload = {
        "name": "Login Test",
        "username": f"l{uid[:20]}",
        "phone": "11999990000",
        "email": email,
        "password": password,
        "password_confirmation": password,
    }
    reg_resp = client.post("/api/create-account", json=reg_payload)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"

    # Login with correct credentials -> token returned
    login_resp = client.post("/api/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    login_data = login_resp.json()
    assert "token" in login_data
    parts = login_data["token"].split("|", 1)
    assert len(parts) == 2
    assert parts[0].isdigit()

    # Login with wrong password -> 401
    # Use a completely different short password to avoid bcrypt 72-byte truncation issues
    wrong_password = "WRONG!" if password != "WRONG!" else "XXXXXX"
    wrong_resp = client.post("/api/login", json={"email": email, "password": wrong_password})
    assert wrong_resp.status_code == 401, f"Expected 401, got {wrong_resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
# Property 7: Logout invalida o token (round-trip)
# Feature: testia-suite, Property 7: Logout invalida o token (round-trip)
# **Validates: Requirements 4.7**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@settings(**_PBT_SETTINGS)
@given(st.data())
def test_property_logout_invalidates_token(client, data):
    # Feature: testia-suite, Property 7: Logout invalida o token (round-trip)
    uid = _unique_id()
    email = f"x{uid}@test.com"

    # Register to get a token
    reg_payload = {
        "name": "Logout Test",
        "username": f"x{uid[:20]}",
        "phone": "11999990000",
        "email": email,
        "password": "senha123",
        "password_confirmation": "senha123",
    }
    reg_resp = client.post("/api/create-account", json=reg_payload)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    token = reg_resp.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Verify token works (access protected endpoint)
    user_resp = client.get("/api/user", headers=headers)
    assert user_resp.status_code == 200, f"Token should be valid before logout: {user_resp.text}"

    # Logout
    logout_resp = client.post("/api/logout", headers=headers)
    assert logout_resp.status_code == 200

    # Token should now be invalid
    after_resp = client.get("/api/user", headers=headers)
    assert after_resp.status_code == 401, (
        f"Expected 401 after logout, got {after_resp.status_code}: {after_resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Property 8: Dados de registro inválidos retornam 422
# Feature: testia-suite, Property 8: Dados de registro inválidos retornam 422
# **Validates: Requirements 4.8**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.auth
@settings(**_PBT_SETTINGS)
@given(
    invalid_case=st.sampled_from(["short_password", "invalid_email"]),
)
def test_property_invalid_registration_data_returns_422(client, invalid_case):
    # Feature: testia-suite, Property 8: Dados de registro inválidos retornam 422
    uid = _unique_id()

    base_payload = {
        "name": "Invalid Test",
        "username": f"i{uid[:20]}",
        "phone": "11999990000",
        "email": f"i{uid}@test.com",
        "password": "senha123",
        "password_confirmation": "senha123",
    }

    if invalid_case == "short_password":
        # Password < 6 chars
        base_payload["password"] = "abc"
        base_payload["password_confirmation"] = "abc"
    elif invalid_case == "invalid_email":
        # Invalid email format
        base_payload["email"] = "not-an-email"

    resp = client.post("/api/create-account", json=base_payload)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["message"] == "The given data was invalid."
    assert "errors" in data
    assert len(data["errors"]) > 0, "Should have at least one error field"
