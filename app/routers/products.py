from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.services import product_service

router = APIRouter(prefix="/api")


def _product_with_stock(db: Session, product):
    available = product_service.calculate_available_stock(db, product)
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": float(product.price),
        "stock": product.stock,
        "image_url": product.image_url,
        "active": product.active,
        "available_stock": available,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


@router.get("/products")
def index(db: Session = Depends(get_db)):
    products = product_service.list(db)
    return {
        "products": [_product_with_stock(db, p) for p in products]
    }


@router.get("/products/{id}")
def show(id: int, db: Session = Depends(get_db)):
    product = product_service.find(db, id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Produto nao encontrado."},
        )
    return {"product": _product_with_stock(db, product)}


@router.post("/products", status_code=status.HTTP_201_CREATED)
def store(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    active: bool = Form(True),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate fields
    errors = {}
    if len(name) < 3 or len(name) > 255:
        errors["name"] = ["O campo name deve ter entre 3 e 255 caracteres."]
    if len(description) < 3:
        errors["description"] = ["O campo description deve ter pelo menos 3 caracteres."]
    if price < 0:
        errors["price"] = ["O campo price deve ser maior ou igual a 0."]
    if stock < 0:
        errors["stock"] = ["O campo stock deve ser maior ou igual a 0."]

    # Validate image size
    image.file.seek(0, 2)
    size = image.file.tell()
    image.file.seek(0)
    if size > 10 * 1024 * 1024:
        errors["image"] = ["O campo image nao pode ser superior a 10MB."]

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "The given data was invalid.", "errors": errors},
        )

    data = {
        "name": name,
        "description": description,
        "price": price,
        "stock": stock,
        "active": active,
    }

    product = product_service.create(db, data, image, current_user)
    return {"product": _product_with_stock(db, product)}


@router.post("/products/{id}")
def update(
    id: int,
    name: str | None = Form(None),
    description: str | None = Form(None),
    price: float | None = Form(None),
    stock: int | None = Form(None),
    active: bool | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = product_service.find(db, id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Produto nao encontrado."},
        )

    # Validate optional fields
    errors = {}
    if name is not None and (len(name) < 3 or len(name) > 255):
        errors["name"] = ["O campo name deve ter entre 3 e 255 caracteres."]
    if description is not None and len(description) < 3:
        errors["description"] = ["O campo description deve ter pelo menos 3 caracteres."]
    if price is not None and price < 0:
        errors["price"] = ["O campo price deve ser maior ou igual a 0."]
    if stock is not None and stock < 0:
        errors["stock"] = ["O campo stock deve ser maior ou igual a 0."]

    # Validate image size if provided
    if image is not None:
        image.file.seek(0, 2)
        size = image.file.tell()
        image.file.seek(0)
        if size > 10 * 1024 * 1024:
            errors["image"] = ["O campo image nao pode ser superior a 10MB."]

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "The given data was invalid.", "errors": errors},
        )

    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if price is not None:
        data["price"] = price
    if stock is not None:
        data["stock"] = stock
    if active is not None:
        data["active"] = active

    product = product_service.update(db, product, data, image, current_user)
    return {"product": _product_with_stock(db, product)}


@router.delete("/products/{id}")
def destroy(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = product_service.find(db, id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Produto nao encontrado."},
        )

    product_service.delete(db, product, current_user)
    return {"message": "Produto removido."}
