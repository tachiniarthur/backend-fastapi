import os

# Forçar SQLite em memória ANTES de importar qualquer módulo da app,
# pois app.main executa Base.metadata.create_all no import.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models.user import User
from app.models.product import Product
from app.models.personal_access_token import PersonalAccessToken
from passlib.hash import bcrypt


# ---------------------------------------------------------------------------
# Engine e tabelas (scope=session) — criados uma vez por sessão de testes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """Cria engine SQLite em memória para os testes."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    return engine


@pytest.fixture(scope="session")
def tables(engine):
    """Cria todas as tabelas antes dos testes e destrói ao final."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Sessão de banco (scope=function) — cada teste recebe sessão limpa
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session(engine, tables):
    """Sessão de banco com rollback automático após cada teste."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Cliente de teste FastAPI
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client(db_session):
    """TestClient com override de get_db para usar a sessão de teste."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers para criação de token
# ---------------------------------------------------------------------------

def _create_user_and_token(db_session, *, is_admin=False, suffix=""):
    """Cria um usuário no banco e retorna (user, token_string)."""
    user = User(
        name=f"Test User{suffix}",
        username=f"testuser{suffix}",
        phone="11999999999",
        email=f"test{suffix}@example.com",
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
    return user, token_string


# ---------------------------------------------------------------------------
# Fixtures de autenticação
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def auth_headers(client, db_session):
    """Cria usuário de teste comum e retorna headers com token Bearer."""
    _user, token = _create_user_and_token(db_session)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_headers(client, db_session):
    """Cria usuário admin de teste e retorna headers com token Bearer."""
    _user, token = _create_user_and_token(db_session, is_admin=True, suffix="_admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixture de produto de teste
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def sample_product(db_session):
    """Cria um produto de teste no banco."""
    product = Product(
        name="Produto Teste",
        description="Descrição do produto de teste",
        price=29.90,
        stock=100,
        image_url="/storage/products/test.jpg",
        active=True,
    )
    db_session.add(product)
    db_session.flush()
    return product
