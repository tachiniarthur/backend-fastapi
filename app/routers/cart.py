from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.cart import CartAddRequest, CartUpdateRequest
from app.services import cart_service

router = APIRouter(prefix="/api")


def _cart_item_response(db: Session, item, user: User):
    available = cart_service.available_stock_for_user(db, item.product, user)
    return {
        "id": item.id,
        "product_id": item.product_id,
        "quantity": item.quantity,
        "product": {
            "id": item.product.id,
            "name": item.product.name,
            "price": float(item.product.price),
            "image_url": item.product.image_url,
            "stock": item.product.stock,
            "available_stock": available,
        },
        "available_stock": max(0, available - item.quantity),
    }


@router.get("/cart")
def index(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = cart_service.get_items(db, current_user)
    return {"items": [_cart_item_response(db, item, current_user) for item in items]}


@router.post("/cart")
def store(
    data: CartAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = cart_service.add_item(db, current_user, data.product_id, data.quantity)
    if not item.product:
        db.refresh(item, ["product"])
    return {
        "message": "Produto adicionado ao carrinho.",
        "item": _cart_item_response(db, item, current_user),
    }


@router.put("/cart/{cartItemId}")
def update(
    cartItemId: int,
    data: CartUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = cart_service.update_item(db, current_user, cartItemId, data.quantity)
    if not item.product:
        db.refresh(item, ["product"])
    return {
        "message": "Quantidade atualizada.",
        "item": _cart_item_response(db, item, current_user),
    }


@router.delete("/cart/{cartItemId}")
def destroy(
    cartItemId: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart_service.remove_item(db, current_user, cartItemId)
    return {"message": "Item removido do carrinho."}
