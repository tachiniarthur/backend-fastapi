import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.product import Product
from app.models.cart_item import CartItem
from app.models.user import User
from app.config import PRODUCTS_IMAGE_PATH


def _save_image(image: UploadFile) -> str:
    ext = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(PRODUCTS_IMAGE_PATH, filename)
    os.makedirs(PRODUCTS_IMAGE_PATH, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(image.file.read())
    return f"/storage/products/{filename}"


def _remove_image(image_url: str):
    if image_url:
        relative_path = image_url.lstrip("/")
        if os.path.exists(relative_path):
            os.remove(relative_path)


def list(db: Session):
    return db.query(Product).filter(Product.active == True).all()


def find(db: Session, id: int):
    return db.query(Product).filter(Product.id == id).first()


def create(db: Session, data: dict, image: UploadFile, actor: User) -> Product:
    if not actor.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Only admins can create products."},
        )

    image_url = _save_image(image)

    product = Product(
        name=data["name"],
        description=data["description"],
        price=data["price"],
        stock=data["stock"],
        image_url=image_url,
        active=data.get("active", True),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update(db: Session, product: Product, data: dict, image: UploadFile | None, actor: User) -> Product:
    if not actor.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Only admins can update products."},
        )

    if image is not None:
        _remove_image(product.image_url)
        product.image_url = _save_image(image)

    for field in ("name", "description", "price", "stock", "active"):
        if field in data and data[field] is not None:
            setattr(product, field, data[field])

    db.commit()
    db.refresh(product)
    return product


def delete(db: Session, product: Product, actor: User):
    if not actor.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Only admins can delete products."},
        )

    _remove_image(product.image_url)
    db.delete(product)
    db.commit()


def calculate_available_stock(db: Session, product: Product) -> int:
    reserved = (
        db.query(func.coalesce(func.sum(CartItem.quantity), 0))
        .filter(CartItem.product_id == product.id)
        .scalar()
    )
    return max(0, product.stock - reserved)
