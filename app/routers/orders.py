from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.order import OrderResponse, CreateOrderRequest
from app.services import order_service

router = APIRouter(prefix="/api")


@router.get("/orders")
def index(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = order_service.list_for_user(db, current_user)
    return [OrderResponse.model_validate(order) for order in orders]


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def store(
    data: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = order_service.create_from_cart(db, current_user, data.items)
    return OrderResponse.model_validate(order)
