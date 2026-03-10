from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/api")


@router.get("/user")
def show(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/user")
def update(
    data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.name is not None:
        current_user.name = data.name
    if data.phone is not None:
        current_user.phone = data.phone
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)
