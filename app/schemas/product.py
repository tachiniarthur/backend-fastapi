from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    stock: int
    image_url: str
    active: bool
    available_stock: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    products: list[ProductResponse]


class ProductDetailResponse(BaseModel):
    product: ProductResponse
