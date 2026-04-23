"""
Testes básicos do serviço de usuário.
Cobre happy paths de consulta e atualização de perfil.
Requisitos: 7.1, 7.2
"""
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


def test_get_user_profile(client, auth_headers):
    """Consultar perfil de usuário autenticado retorna 200 e dados."""
    response = client.get("/api/user", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "email" in data
    assert data["email"] == "test@example.com"


def test_update_user_name(client, auth_headers):
    """Atualizar nome do usuário retorna 200 e dados atualizados."""
    response = client.put(
        "/api/user",
        json={"name": "Novo Nome"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Novo Nome"


# ---------------------------------------------------------------------------
# Testes baseados em propriedades (Hypothesis)
# ---------------------------------------------------------------------------

# Estratégia para gerar nomes válidos: letras e espaços, min_length=3, max_length=255
valid_names = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    min_size=3,
    max_size=50,
).filter(lambda s: s.strip() and any(c.isalpha() for c in s))


# Feature: junior-pleno-test-suite, Property 8: Round-trip de atualização de perfil
# **Validates: Requirements 7.1, 7.2**
@given(name=valid_names)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_profile_update_round_trip(client, db_session, auth_headers, name):
    """
    Propriedade 8: Para qualquer usuário autenticado e qualquer nome válido,
    atualizar o perfil via PUT /api/user e em seguida consultar via GET /api/user
    deve retornar os dados atualizados com o novo nome.

    **Validates: Requirements 7.1, 7.2**
    """
    # 1. Atualizar o perfil com o nome gerado via PUT /api/user
    update_response = client.put(
        "/api/user",
        json={"name": name},
        headers=auth_headers,
    )
    assert update_response.status_code == 200, (
        f"Esperado 200 ao atualizar perfil, obteve {update_response.status_code} - {update_response.text}"
    )
    update_data = update_response.json()
    assert update_data["name"] == name

    # 2. Consultar o perfil via GET /api/user
    get_response = client.get("/api/user", headers=auth_headers)
    assert get_response.status_code == 200, (
        f"Esperado 200 ao consultar perfil, obteve {get_response.status_code} - {get_response.text}"
    )
    get_data = get_response.json()

    # 3. Verificar que o nome retornado é o mesmo que foi atualizado
    assert get_data["name"] == name, (
        f"Nome esperado '{name}', mas obteve '{get_data['name']}'"
    )
