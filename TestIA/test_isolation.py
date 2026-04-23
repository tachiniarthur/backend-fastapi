"""
Testes de isolamento e fixtures — TestIA Suite.

Cobre isolamento por rollback de transação e validade dos tokens de autenticação.
Requisitos: 2.3, 2.4, 3.2, 3.4
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import sessionmaker

from app.models.user import User


# ── Configuração Hypothesis ──────────────────────────────────────────────

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ── Estratégias reutilizáveis ─────────────────────────────────────────────

def _random_name():
    """Gera nomes aleatórios: 3-50 caracteres alfanuméricos."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=3,
        max_size=50,
    ).filter(lambda s: len(s.strip()) >= 3)


def _random_email_suffix():
    """Gera sufixos únicos para emails."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=5,
        max_size=20,
    ).filter(lambda s: len(s.strip()) >= 5)


# ═══════════════════════════════════════════════════════════════════════════
# Property 1: Isolamento por rollback de transação
# Feature: testia-suite, Property 1: Isolamento por rollback de transação
# **Validates: Requirements 2.3, 2.4, 3.2**
# ═══════════════════════════════════════════════════════════════════════════

# A propriedade de isolamento é verificada com um par de testes:
# - O primeiro insere dados e verifica que existem na sessão
# - O segundo verifica que os dados do primeiro NÃO estão presentes
# Isso funciona porque cada teste recebe um db_session com rollback automático.

# Marcador fixo para o username inserido no teste A
_ISOLATION_USERNAME = "isolation_marker_user"
_ISOLATION_EMAIL = "isolation_marker@test.com"


def test_isolation_part_a_insert_data(db_session):
    """Insere um usuário marcador na sessão de teste.
    O rollback automático do db_session deve reverter esta inserção."""
    user = User(
        name="Isolation Test User",
        username=_ISOLATION_USERNAME,
        phone="11999990000",
        email=_ISOLATION_EMAIL,
        password="hashed_placeholder",
        is_admin=False,
    )
    db_session.add(user)
    db_session.flush()

    # Confirma que o dado existe DENTRO desta sessão
    found = db_session.query(User).filter(User.username == _ISOLATION_USERNAME).first()
    assert found is not None, "User should exist within the test session"
    assert found.name == "Isolation Test User"


def test_isolation_part_b_verify_not_visible(db_session):
    """Verifica que o usuário inserido no teste anterior NÃO está presente.
    Isso prova que o rollback do db_session funciona corretamente."""
    found = db_session.query(User).filter(User.username == _ISOLATION_USERNAME).first()
    assert found is None, (
        f"User '{_ISOLATION_USERNAME}' from a previous test should NOT be visible. "
        "Transaction rollback isolation is broken."
    )


@settings(**_PBT_SETTINGS)
@given(
    name=_random_name(),
    email_suffix=_random_email_suffix(),
)
def test_property_isolation_by_transaction_rollback(db_session, name, email_suffix):
    # Feature: testia-suite, Property 1: Isolamento por rollback de transação
    """
    Verifica a propriedade de isolamento: dados inseridos durante um teste
    existem na sessão corrente, mas após rollback (simulado via savepoint),
    os dados não são mais visíveis.

    Usa savepoints para simular o ciclo insert → rollback → verify dentro
    de uma única invocação, provando que o mecanismo de rollback funciona.
    """
    username = f"iso_{email_suffix}"
    email = f"iso_{email_suffix}@test.com"

    # Cria um savepoint para simular o ciclo de isolamento
    savepoint = db_session.begin_nested()

    user = User(
        name=name,
        username=username,
        phone="11999990000",
        email=email,
        password="hashed_password_placeholder",
        is_admin=False,
    )
    db_session.add(user)
    db_session.flush()

    # Verifica que o usuário EXISTE na sessão corrente
    found = db_session.query(User).filter(User.username == username).first()
    assert found is not None, "User should be visible within the active savepoint"
    assert found.name == name

    # Rollback do savepoint — simula o que o db_session fixture faz ao final do teste
    savepoint.rollback()

    # Após o rollback, o usuário NÃO deve mais ser visível
    db_session.expire_all()
    found_after = db_session.query(User).filter(User.username == username).first()
    assert found_after is None, (
        f"User '{username}' should NOT be visible after savepoint rollback. "
        "Isolation mechanism is broken."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Property 2: Fixtures de autenticação geram tokens válidos
# Feature: testia-suite, Property 2: Fixtures de autenticação geram tokens válidos
# **Validates: Requirements 3.4**
# ═══════════════════════════════════════════════════════════════════════════

@settings(**_PBT_SETTINGS)
@given(
    use_admin=st.booleans(),
)
def test_property_auth_fixtures_generate_valid_tokens(
    client, auth_headers, admin_headers, use_admin
):
    # Feature: testia-suite, Property 2: Fixtures de autenticação geram tokens válidos
    """
    Verifica que tokens gerados pelas fixtures auth_headers e admin_headers
    são aceitos pelo endpoint protegido GET /api/user (status 200, não 401/403).
    """
    headers = admin_headers if use_admin else auth_headers

    resp = client.get("/api/user", headers=headers)

    assert resp.status_code == 200, (
        f"Expected 200 for {'admin' if use_admin else 'regular'} user, "
        f"got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "id" in data
    assert "email" in data
    assert "username" in data
