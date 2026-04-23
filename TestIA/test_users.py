"""
Testes de usuários — TestIA Suite.

Cobre GET /api/user e PUT /api/user (endpoints).
Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import pytest
from uuid import uuid4

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.user import User


# ── Configuração PBT ──────────────────────────────────────────────────────

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — GET /api/user
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.users
def test_get_user_authenticated(client, auth_headers):
    """GET /api/user autenticado retorna dados completos do usuário. (Req 5.1)"""
    resp = client.get("/api/user", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test User_auth"
    assert data["username"] == "testuser_auth"
    assert data["email"] == "test_auth@example.com"
    assert data["phone"] == "11999999999"
    assert data["is_admin"] is False
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.users
def test_get_user_unauthenticated(client):
    """GET /api/user sem autenticação retorna 401 ou 403. (Req 5.2)"""
    resp = client.get("/api/user")

    assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — PUT /api/user
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.users
def test_update_user_valid_data(client, auth_headers):
    """PUT /api/user com dados válidos atualiza nome e telefone. (Req 5.3)"""
    resp = client.put(
        "/api/user",
        json={"name": "Novo Nome", "phone": "11888887777"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Novo Nome"
    assert data["phone"] == "11888887777"
    # Campos não enviados permanecem inalterados
    assert data["username"] == "testuser_auth"
    assert data["email"] == "test_auth@example.com"


@pytest.mark.users
def test_update_user_partial_null_fields(client, auth_headers):
    """PUT /api/user com campos nulos atualiza apenas os fornecidos. (Req 5.4)"""
    # Atualiza apenas o nome, phone não enviado (null)
    resp = client.put(
        "/api/user",
        json={"name": "Apenas Nome"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Apenas Nome"
    # Phone permanece o original
    assert data["phone"] == "11999999999"


@pytest.mark.users
def test_update_user_invalid_short_name(client, auth_headers):
    """PUT /api/user com nome <3 chars retorna 422. (Req 5.5)"""
    resp = client.put(
        "/api/user",
        json={"name": "AB"},
        headers=auth_headers,
    )

    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Usuários
# ═══════════════════════════════════════════════════════════════════════════


def _unique_id():
    return uuid4().hex


def _register_and_get_headers(client):
    """Registra um novo usuário e retorna (headers, user_data)."""
    uid = _unique_id()
    payload = {
        "name": f"User {uid[:8]}",
        "username": f"u{uid[:20]}",
        "phone": "11999990000",
        "email": f"u{uid}@test.com",
        "password": "senha123",
        "password_confirmation": "senha123",
    }
    resp = client.post("/api/create-account", json=payload)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, payload


# ═══════════════════════════════════════════════════════════════════════════
# Property 9: Usuário autenticado recebe seus próprios dados
# Feature: testia-suite, Property 9: Usuário autenticado recebe seus próprios dados
# **Validates: Requirements 5.1**
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.users
@settings(**_PBT_SETTINGS)
@given(st.data())
def test_property_authenticated_user_receives_own_data(client, data):
    # Feature: testia-suite, Property 9: Usuário autenticado recebe seus próprios dados
    headers, reg_data = _register_and_get_headers(client)

    resp = client.get("/api/user", headers=headers)
    assert resp.status_code == 200

    user = resp.json()
    assert user["name"] == reg_data["name"]
    assert user["username"] == reg_data["username"]
    assert user["email"] == reg_data["email"]
    assert user["phone"] == reg_data["phone"]
    assert "id" in user
    assert "is_admin" in user
    assert "created_at" in user
    assert "updated_at" in user


# ═══════════════════════════════════════════════════════════════════════════
# Property 10: Atualização parcial preserva campos não enviados
# Feature: testia-suite, Property 10: Atualização parcial preserva campos não enviados
# **Validates: Requirements 5.3, 5.4**
# ═══════════════════════════════════════════════════════════════════════════

_valid_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z"), blacklist_characters="\x00"),
    min_size=3,
    max_size=100,
).filter(lambda s: len(s.strip()) >= 3)

_valid_phone_st = st.text(
    alphabet=st.characters(whitelist_categories=("N",)),
    min_size=1,
    max_size=20,
).filter(lambda s: len(s.strip()) >= 1)


@pytest.mark.users
@settings(**_PBT_SETTINGS)
@given(
    send_name=st.booleans(),
    send_phone=st.booleans(),
    new_name=_valid_name_st,
    new_phone=_valid_phone_st,
)
def test_property_partial_update_preserves_unsent_fields(
    client, send_name, send_phone, new_name, new_phone
):
    # Feature: testia-suite, Property 10: Atualização parcial preserva campos não enviados
    headers, reg_data = _register_and_get_headers(client)

    # Get original user data
    original_resp = client.get("/api/user", headers=headers)
    assert original_resp.status_code == 200
    original = original_resp.json()

    # Build update payload with a subset of fields
    update_payload = {}
    if send_name:
        update_payload["name"] = new_name
    if send_phone:
        update_payload["phone"] = new_phone

    # Send update
    update_resp = client.put("/api/user", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    updated = update_resp.json()

    # Verify: sent fields are updated, unsent fields are preserved
    if send_name:
        assert updated["name"] == new_name
    else:
        assert updated["name"] == original["name"]

    if send_phone:
        assert updated["phone"] == new_phone
    else:
        assert updated["phone"] == original["phone"]

    # Fields that are never updatable via PUT /api/user remain unchanged
    assert updated["username"] == original["username"]
    assert updated["email"] == original["email"]
    assert updated["is_admin"] == original["is_admin"]
    assert updated["id"] == original["id"]
