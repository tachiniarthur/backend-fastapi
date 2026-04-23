"""
Fixtures centralizadas para a TestIA Suite.

Fornece engine SQLite em memória, sessão com rollback automático,
TestClient com override de get_db, e fixtures de autenticação e dados de teste.
"""

import os

# Força SQLite em memória ANTES de qualquer import da app
# (evita tentativa de conexão com PostgreSQL do .env)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import hashlib

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
from passlib.hash import bcrypt

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models.user import User
from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.personal_access_token import PersonalAccessToken


# ---------------------------------------------------------------------------
# Engine e tabelas (escopo session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """Cria engine SQLAlchemy SQLite em memória (uma vez por sessão)."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    return eng


@pytest.fixture(scope="session")
def tables(engine):
    """Cria todas as tabelas antes dos testes e destrói ao final."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Sessão de banco com rollback automático (escopo function)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session(engine, tables):
    """Fornece sessão limpa com rollback automático para cada teste."""
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()

    # Garante que nested transactions (SAVEPOINT) funcionem com SQLite
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# TestClient com override de get_db (escopo function)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client(db_session):
    """TestClient do FastAPI com get_db substituído pela sessão de teste."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper de criação de usuário com token
# ---------------------------------------------------------------------------

def _create_user_and_token(
    db_session: Session,
    is_admin: bool = False,
    suffix: str = "",
) -> tuple[User, str]:
    """Cria usuário com senha hasheada e token válido.

    Retorna (user, token_string) onde token_string = "{token_id}|{plain_token}".
    """
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
# Fixtures de autenticação (escopo function)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def auth_headers(db_session) -> dict[str, str]:
    """Headers Bearer para usuário comum (is_admin=False)."""
    _user, token = _create_user_and_token(db_session, is_admin=False, suffix="_auth")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_headers(db_session) -> dict[str, str]:
    """Headers Bearer para usuário administrador (is_admin=True)."""
    _user, token = _create_user_and_token(db_session, is_admin=True, suffix="_admin")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures de dados de teste (escopo function)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def sample_product(db_session) -> Product:
    """Produto ativo com stock=100."""
    product = Product(
        name="Produto Teste",
        description="Descrição teste",
        price=29.90,
        stock=100,
        image_url="test.jpg",
        active=True,
    )
    db_session.add(product)
    db_session.flush()
    return product


@pytest.fixture(scope="function")
def cart_item(db_session, auth_headers, sample_product) -> CartItem:
    """Item no carrinho associado ao usuário autenticado e ao produto de teste."""
    # Recupera o usuário criado pela fixture auth_headers
    user = db_session.query(User).filter(User.username == "testuser_auth").first()

    item = CartItem(
        user_id=user.id,
        product_id=sample_product.id,
        quantity=2,
    )
    db_session.add(item)
    db_session.flush()
    return item
