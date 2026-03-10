from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import hashlib

from app.database import SessionLocal
from app.models.user import User
from app.models.personal_access_token import PersonalAccessToken

security_scheme = HTTPBearer(auto_error=True)
security_scheme_optional = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> User:
    token = credentials.credentials

    try:
        parts = token.split("|", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
            )
        token_id = int(parts[0])
        plain_token = parts[1]
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        )

    access_token = (
        db.query(PersonalAccessToken)
        .filter(PersonalAccessToken.id == token_id)
        .first()
    )

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not found",
        )

    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    if access_token.token != token_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.query(User).filter(User.id == access_token.tokenable_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_user_optional(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme_optional),
) -> User | None:
    if credentials is None:
        return None

    token = credentials.credentials

    try:
        parts = token.split("|", 1)
        if len(parts) != 2:
            return None
        token_id = int(parts[0])
        plain_token = parts[1]
    except (ValueError, IndexError):
        return None

    access_token = (
        db.query(PersonalAccessToken)
        .filter(PersonalAccessToken.id == token_id)
        .first()
    )

    if not access_token:
        return None

    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    if access_token.token != token_hash:
        return None

    user = db.query(User).filter(User.id == access_token.tokenable_id).first()
    return user
