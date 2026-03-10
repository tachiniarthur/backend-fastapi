import os
import hashlib

from passlib.hash import bcrypt
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.personal_access_token import PersonalAccessToken


def _generate_token(db: Session, user: User) -> str:
    """Generate a Sanctum-compatible token for the given user.

    Creates a random 80-char hex string, stores its SHA-256 hash in the
    personal_access_tokens table, and returns the plain token in the
    format "{token_record.id}|{plain_token}".
    """
    plain_token = os.urandom(40).hex()  # 80 char hex string
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()

    token_record = PersonalAccessToken(
        tokenable_type="App\\Models\\User",
        tokenable_id=user.id,
        name="auth_token",
        token=token_hash,
    )
    db.add(token_record)
    db.flush()

    return f"{token_record.id}|{plain_token}"


def create(db: Session, data) -> dict:
    """Create a new user with hashed password and generate an auth token."""
    user = User(
        name=data.name,
        username=data.username,
        phone=data.phone,
        email=data.email,
        password=bcrypt.hash(data.password),
    )
    db.add(user)
    db.flush()

    token = _generate_token(db, user)

    return {"user": user, "token": token}


def login(db: Session, email: str, password: str) -> dict | None:
    """Authenticate a user by email and password.

    Returns {"user": user, "token": token_string} on success, or None
    if the credentials are invalid.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    if not bcrypt.verify(password, user.password):
        return None

    token = _generate_token(db, user)

    return {"user": user, "token": token}
