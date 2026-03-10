from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.user import User


def create_from_cart(db: Session, user: User, items: list) -> Order:
    order = Order(status="pending", user_id=user.id)
    db.add(order)
    db.flush()

    for item in items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )

        if not product or not product.active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": f'O produto "{product.name}" nao esta mais disponivel.'
                    if product
                    else "Produto nao encontrado.",
                },
            )

        if product.stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": f'Estoque insuficiente para o produto "{product.name}". Disponivel: {product.stock}.',
                },
            )

        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=product.price,
        )
        db.add(order_item)
        product.decrease_stock(item.quantity)

    db.query(CartItem).filter(CartItem.user_id == user.id).delete()

    db.flush()
    db.refresh(order)

    order = (
        db.query(Order)
        .options(subqueryload(Order.items).subqueryload(OrderItem.product))
        .filter(Order.id == order.id)
        .first()
    )

    return order


def list_for_user(db: Session, user: User):
    return (
        db.query(Order)
        .options(subqueryload(Order.items).subqueryload(OrderItem.product))
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .all()
    )


def list_all(db: Session):
    return (
        db.query(Order)
        .options(
            subqueryload(Order.items).subqueryload(OrderItem.product),
            joinedload(Order.user),
        )
        .order_by(Order.created_at.desc())
        .all()
    )


def update_status(db: Session, order_id: int, status_value: str) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Pedido nao encontrado."},
        )

    order.status = status_value
    db.commit()
    db.refresh(order)

    order = (
        db.query(Order)
        .options(
            subqueryload(Order.items).subqueryload(OrderItem.product),
            joinedload(Order.user),
        )
        .filter(Order.id == order.id)
        .first()
    )

    return order
