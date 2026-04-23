"""
Testes de dependências de autenticação por token — TestIA Suite.

Cobre o sistema de autenticação por token em app/dependencies.py:
token sem separador, ID inexistente, hash incorreto, usuário inexistente, sem token.
Requisitos: 11.1, 11.2, 11.3, 11.4, 11.5, 13.4
"""

import hashlib
import os

import pytest
from passlib.hash import bcrypt
from uuid import uuid4

from app.models.user import User
from app.models.personal_access_token import PersonalAccessToken


# ── Helpers ───────────────────────────────────────────────────────────────

def _create_user_and_token(db_session, is_admin=False, suffix=""):
    """Cria usuário com senha hasheada e token válido. Retorna (user, token_string, token_record)."""
    user = User(
        name=f"Dep Test User{suffix}",
        username=f"deptestuser{suffix}",
        phone="11999999999",
        email=f"deptest{suffix}@example.com",
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
    return user, token_string, token_record


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — Autenticação por Token (app/dependencies.py)
# ═══════════════════════════════════════════════════════════════════════════


def test_token_without_separator_returns_401(client, db_session):
    """Token sem separador | → status 401, 'Invalid token format'. (Req 11.1)"""
    headers = {"Authorization": "Bearer noseparatortoken"}
    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token format"


def test_token_with_nonexistent_id_returns_401(client, db_session):
    """Token com ID inexistente → status 401, 'Token not found'. (Req 11.2)"""
    headers = {"Authorization": "Bearer 99999|sometoken"}
    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token not found"


def test_token_with_incorrect_hash_returns_401(client, db_session):
    """Token com hash incorreto → status 401, 'Invalid token'. (Req 11.3)"""
    user, _token_string, token_record = _create_user_and_token(
        db_session, suffix="_wronghash",
    )
    # Use the correct token ID but a wrong plain token
    wrong_token = f"{token_record.id}|wrongplaintoken"
    headers = {"Authorization": f"Bearer {wrong_token}"}

    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_token_referencing_nonexistent_user_returns_401(client, db_session):
    """Token referenciando usuário inexistente → status 401, 'User not found'. (Req 11.4)"""
    # Create a token that points to a non-existent user
    plain_token = os.urandom(40).hex()
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()

    token_record = PersonalAccessToken(
        tokenable_type="App\\Models\\User",
        tokenable_id=99999,  # non-existent user
        name="auth_token",
        token=token_hash,
    )
    db_session.add(token_record)
    db_session.flush()

    token_string = f"{token_record.id}|{plain_token}"
    headers = {"Authorization": f"Bearer {token_string}"}

    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 401
    assert resp.json()["detail"] == "User not found"


def test_no_token_on_protected_endpoint_returns_401_or_403(client, db_session):
    """Sem token em endpoint protegido → status 401 ou 403. (Req 11.5)"""
    resp = client.get("/api/user")

    assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
# Teste Parametrizado — Múltiplos formatos de token inválido (Req 13.4)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "token_value, expected_detail",
    [
        ("noseparator", "Invalid token format"),
        ("onlytext", "Invalid token format"),
        ("abc|def|ghi", "Invalid token format"),  # split("|", 1) gives 2 parts but "abc" is not int
        ("notanumber|sometoken", "Invalid token format"),
        ("99999|sometoken", "Token not found"),
        ("0|sometoken", "Token not found"),
    ],
    ids=[
        "no_separator",
        "plain_text",
        "multiple_separators_non_int",
        "non_numeric_id",
        "nonexistent_id_99999",
        "nonexistent_id_0",
    ],
)
def test_parametrized_invalid_token_formats(client, db_session, token_value, expected_detail):
    """Teste parametrizado com múltiplos formatos de token inválido. (Req 13.4)"""
    headers = {"Authorization": f"Bearer {token_value}"}
    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 401
    assert resp.json()["detail"] == expected_detail


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Tokens Inválidos
# ═══════════════════════════════════════════════════════════════════════════

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ═══════════════════════════════════════════════════════════════════════════
# Property 22: Tokens inválidos são rejeitados com 401
# Feature: testia-suite, Property 22: Tokens inválidos são rejeitados com 401
# **Validates: Requirements 11.1, 11.2, 11.3**
# ═══════════════════════════════════════════════════════════════════════════

_ascii_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), max_codepoint=127),
    min_size=1,
    max_size=50,
)


@settings(**_PBT_SETTINGS)
@given(
    token_value=st.one_of(
        # Tokens without separator — should get "Invalid token format"
        _ascii_text.filter(lambda s: "|" not in s),
        # Tokens with non-numeric ID part
        st.tuples(
            _ascii_text.filter(lambda s: not s.isdigit() and "|" not in s),
            _ascii_text.filter(lambda s: "|" not in s),
        ).map(lambda t: f"{t[0]}|{t[1]}"),
        # Tokens with nonexistent numeric ID (high range)
        st.integers(min_value=90000, max_value=99999).map(
            lambda i: f"{i}|{os.urandom(20).hex()}"
        ),
    ),
)
def test_property_invalid_tokens_rejected_with_401(client, db_session, token_value):
    # Feature: testia-suite, Property 22: Tokens inválidos são rejeitados com 401
    # **Validates: Requirements 11.1, 11.2, 11.3**
    headers = {"Authorization": f"Bearer {token_value}"}
    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 401, (
        f"Expected 401 for invalid token '{token_value}', got {resp.status_code}: {resp.text}"
    )

    detail = resp.json()["detail"]
    valid_messages = {"Invalid token format", "Token not found", "Invalid token"}
    assert detail in valid_messages, (
        f"Unexpected error message '{detail}' for token '{token_value}'"
    )
