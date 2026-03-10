from pydantic import BaseModel, ConfigDict, Field


class CartProductResponse(BaseModel):
    id: int
    name: str
    price: float
    image_url: str
    stock: int
    available_stock: int

    model_config = ConfigDict(from_attributes=True)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: CartProductResponse
    available_stock: int

    model_config = ConfigDict(from_attributes=True)


class CartListResponse(BaseModel):
    items: list[CartItemResponse]


class CartAddRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)


class CartUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1)
