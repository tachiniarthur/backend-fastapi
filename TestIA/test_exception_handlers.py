"""
Testes de exception handlers — TestIA Suite.

Cobre o handler customizado de erros de validação em app/exception_handlers.py:
formato Laravel, múltiplos campos com erro, status HTTP 422.
Requisitos: 10.1, 10.2, 10.3
"""

import pytest

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st


# ═══════════════════════════════════════════════════════════════════════════
# Testes Unitários — Exception Handlers (app/exception_handlers.py)
# ═══════════════════════════════════════════════════════════════════════════

def test_validation_error_format_follows_laravel_pattern(client, db_session):
    """Formato de erro de validação → {"message": "The given data was invalid.", "errors": {...}}. (Req 10.1)"""
    # Send invalid data to trigger Pydantic validation
    resp = client.post("/api/create-account", json={
        "name": "Test",
        "username": "testuser",
        "email": "invalid-email",  # invalid email format
        "password": "short",       # too short
        "password_confirmation": "short",
    })

    assert resp.status_code == 422

    data = resp.json()
    assert "message" in data
    assert data["message"] == "The given data was invalid."
    assert "errors" in data
    assert isinstance(data["errors"], dict)

    # At least one field should have errors
    assert len(data["errors"]) > 0

    # Each field's errors should be a list of strings
    for field, messages in data["errors"].items():
        assert isinstance(messages, list)
        assert all(isinstance(m, str) for m in messages)


def test_validation_error_multiple_fields_all_included(client, db_session):
    """Múltiplos campos com erro → todos incluídos no objeto errors. (Req 10.2)"""
    # Send completely empty/invalid data to trigger multiple field errors
    resp = client.post("/api/create-account", json={})

    assert resp.status_code == 422

    data = resp.json()
    assert data["message"] == "The given data was invalid."
    assert isinstance(data["errors"], dict)

    # Multiple fields should be present in errors
    assert len(data["errors"]) > 1, (
        f"Expected multiple fields with errors, got: {data['errors']}"
    )


def test_validation_error_returns_status_422(client, db_session):
    """Status HTTP 422 para erros de validação. (Req 10.3)"""
    # Send data with missing required fields
    resp = client.post("/api/create-account", json={
        "name": "A",  # too short
    })

    assert resp.status_code == 422

    data = resp.json()
    assert data["message"] == "The given data was invalid."
    assert "errors" in data


# ═══════════════════════════════════════════════════════════════════════════
# Testes de Propriedade (Hypothesis) — Formato de Erro de Validação
# ═══════════════════════════════════════════════════════════════════════════

_PBT_SETTINGS = dict(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ═══════════════════════════════════════════════════════════════════════════
# Property 21: Formato de erro segue padrão Laravel
# Feature: testia-suite, Property 21: Formato de erro segue padrão Laravel
# **Validates: Requirements 10.1, 10.2, 10.3**
# ═══════════════════════════════════════════════════════════════════════════

@settings(**_PBT_SETTINGS)
@given(
    data=st.fixed_dictionaries({}, optional={
        "name": st.one_of(st.none(), st.text(max_size=2)),
        "username": st.one_of(st.none(), st.text(max_size=0)),
        "email": st.one_of(st.none(), st.text(max_size=5).filter(lambda s: "@" not in s)),
        "password": st.one_of(st.none(), st.text(max_size=3)),
        "password_confirmation": st.one_of(st.none(), st.text(max_size=3)),
    }),
)
def test_property_validation_error_follows_laravel_format(client, db_session, data):
    # Feature: testia-suite, Property 21: Formato de erro segue padrão Laravel
    # **Validates: Requirements 10.1, 10.2, 10.3**

    # Filter out None values to simulate missing fields
    payload = {k: v for k, v in data.items() if v is not None}

    resp = client.post("/api/create-account", json=payload)

    # If validation fails (422), verify the Laravel format
    if resp.status_code == 422:
        body = resp.json()

        # Must have "message" key with exact text
        assert "message" in body, f"Missing 'message' key in response: {body}"
        assert body["message"] == "The given data was invalid.", (
            f"Unexpected message: {body['message']}"
        )

        # Must have "errors" key as a dict
        assert "errors" in body, f"Missing 'errors' key in response: {body}"
        assert isinstance(body["errors"], dict), (
            f"'errors' should be a dict, got {type(body['errors'])}"
        )

        # Each field's errors must be a list of strings
        for field, messages in body["errors"].items():
            assert isinstance(field, str), f"Field key should be str, got {type(field)}"
            assert isinstance(messages, list), (
                f"Messages for '{field}' should be a list, got {type(messages)}"
            )
            for msg in messages:
                assert isinstance(msg, str), (
                    f"Each message should be str, got {type(msg)} for field '{field}'"
                )
