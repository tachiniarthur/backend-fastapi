"""
Testes básicos do painel administrativo.
Cobre listagem de pedidos por admin e bloqueio de acesso para não-admin.
Requisitos: 6.1, 6.2
"""


def test_admin_list_orders(client, admin_headers):
    """Admin lista pedidos retorna 200."""
    response = client.get("/api/admin/orders", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_non_admin_forbidden(client, auth_headers):
    """Não-admin recebe 403 ao tentar listar pedidos administrativos."""
    response = client.get("/api/admin/orders", headers=auth_headers)

    assert response.status_code == 403


# Feature: junior-pleno-test-suite, Property 7: Controle de acesso baseado em papel (admin)
import itertools

import hypothesis
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from JuniorPlenoTests.conftest import _create_user_and_token

_prop7_counter = itertools.count()


@given(is_admin=st.booleans())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_admin_access_control_property(client, db_session, is_admin):
    """
    Propriedade 7: Para qualquer usuário, acessar GET /api/admin/orders deve
    retornar 200 se admin, 403 se não-admin.

    **Validates: Requirements 6.1, 6.2**
    """
    suffix = f"_prop7_{next(_prop7_counter)}"
    user, token_string = _create_user_and_token(
        db_session, is_admin=is_admin, suffix=suffix,
    )
    headers = {"Authorization": f"Bearer {token_string}"}

    response = client.get("/api/admin/orders", headers=headers)

    if is_admin:
        assert response.status_code == 200, (
            f"Admin user should get 200, got {response.status_code}"
        )
    else:
        assert response.status_code == 403, (
            f"Non-admin user should get 403, got {response.status_code}"
        )
