from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.user import User


def available_stock_for_user(db: Session, product: Product, user: User) -> int:
    reserved_by_others = (
        db.query(func.coalesce(func.sum(CartItem.quantity), 0))
        .filter(CartItem.product_id == product.id, CartItem.user_id != user.id)
        .scalar()
    )
    return max(0, product.stock - reserved_by_others)


def get_items(db: Session, user: User):
    items = (
        db.query(CartItem)
        .options(joinedload(CartItem.product))
        .filter(CartItem.user_id == user.id)
        .order_by(CartItem.quantity.desc())
        .all()
    )
    for item in items:
        available = available_stock_for_user(db, item.product, user)
        item.product.available_stock = available
        item.available_stock = max(0, available - item.quantity)
    return items


def add_item(db: Session, user: User, product_id: int, quantity: int) -> CartItem:
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .with_for_update()
        .first()
    )

    if not product or not product.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "The given data was invalid.",
                "errors": {
                    "product_id": ["Este produto nao esta disponivel."]
                },
            },
        )

    available = available_stock_for_user(db, product, user)

    if available == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "The given data was invalid.",
                "errors": {
                    "product_id": ["Produto sem estoque disponivel no momento."]
                },
            },
        )

    existing = (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id, CartItem.product_id == product_id)
        .first()
    )

    if existing:
        new_quantity = existing.quantity + quantity
        if new_quantity > available:
            max_addable = available - existing.quantity
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "The given data was invalid.",
                    "errors": {
                        "product_id": [
                            f"Estoque insuficiente. Disponivel: {max_addable} unidade(s)."
                        ]
                    },
                },
            )
        existing.quantity = new_quantity
        db.commit()
        db.refresh(existing)
        return existing
    else:
        if quantity > available:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "The given data was invalid.",
                    "errors": {
                        "product_id": [
                            f"Estoque insuficiente. Disponivel: {available} unidade(s)."
                        ]
                    },
                },
            )
        cart_item = CartItem(
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
        )
        db.add(cart_item)
        db.commit()
        db.refresh(cart_item)
        return cart_item


def update_item(db: Session, user: User, cart_item_id: int, quantity: int) -> CartItem:
    cart_item = (
        db.query(CartItem)
        .filter(CartItem.id == cart_item_id, CartItem.user_id == user.id)
        .first()
    )

    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    product = (
        db.query(Product)
        .filter(Product.id == cart_item.product_id)
        .with_for_update()
        .first()
    )

    quantity = max(1, quantity)

    available = available_stock_for_user(db, product, user)

    if quantity > available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "The given data was invalid.",
                "errors": {
                    "product_id": [
                        f"Estoque insuficiente. Maximo disponivel: {available} unidade(s)."
                    ]
                },
            },
        )

    cart_item.quantity = quantity
    db.commit()
    db.refresh(cart_item)
    return cart_item


def remove_item(db: Session, user: User, cart_item_id: int):
    cart_item = (
        db.query(CartItem)
        .filter(CartItem.id == cart_item_id, CartItem.user_id == user.id)
        .first()
    )

    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    db.delete(cart_item)
    db.commit()


def clear(db: Session, user: User):
    db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()
