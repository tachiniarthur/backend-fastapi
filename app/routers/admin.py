from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.order import OrderWithUserResponse, UpdateOrderStatusRequest
from app.services import order_service

router = APIRouter(prefix="/api/admin")


@router.get("/orders")
def index_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Acesso negado."},
        )

    orders = order_service.list_all(db)
    return [OrderWithUserResponse.model_validate(order) for order in orders]


@router.patch("/orders/{orderId}/status")
def update_status(
    orderId: int,
    data: UpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Acesso negado."},
        )

    order = order_service.update_status(db, orderId, data.status)
    return OrderWithUserResponse.model_validate(order)
