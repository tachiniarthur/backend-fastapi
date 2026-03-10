from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import hashlib

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.personal_access_token import PersonalAccessToken
from app.schemas.auth import CreateAccountRequest, LoginRequest, AuthResponse
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/api")


@router.post("/create-account", status_code=status.HTTP_201_CREATED)
def create_account(data: CreateAccountRequest, db: Session = Depends(get_db)):
    # Validate password confirmation
    if data.password != data.password_confirmation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "The given data was invalid.",
                "errors": {
                    "password_confirmation": ["As senhas nao conferem."],
                },
            },
        )

    try:
        result = auth_service.create(db, data)
        db.commit()
        return {
            "message": "Conta criada com sucesso",
            "user": UserResponse.model_validate(result["user"]),
            "token": result["token"],
        }
    except IntegrityError as e:
        db.rollback()
        error_msg = str(e.orig).lower() if e.orig else str(e).lower()
        if "email" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "The given data was invalid.",
                    "errors": {
                        "email": ["O email ja esta em uso."],
                    },
                },
            )
        elif "username" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "The given data was invalid.",
                    "errors": {
                        "username": ["O username ja esta em uso."],
                    },
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "The given data was invalid.",
                    "errors": {
                        "email": ["O valor informado ja esta em uso."],
                    },
                },
            )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Erro ao criar conta"},
        )


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login(db, data.email, data.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Credenciais invalidas"},
        )
    return {
        "user": UserResponse.model_validate(result["user"]),
        "token": result["token"],
    }


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    authorization = request.headers.get("Authorization", "")
    token_str = authorization.replace("Bearer ", "", 1)

    try:
        parts = token_str.split("|", 1)
        if len(parts) == 2:
            token_id = int(parts[0])
            db.query(PersonalAccessToken).filter(
                PersonalAccessToken.id == token_id
            ).delete()
            db.commit()
    except (ValueError, IndexError):
        pass

    return {"message": "Logout realizado."}
