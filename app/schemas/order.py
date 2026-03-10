from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemProductResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    stock: int
    image_url: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    price: float
    product: OrderItemProductResponse
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderUserResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)


class OrderWithUserResponse(OrderResponse):
    user: OrderUserResponse


class CreateOrderItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)


class CreateOrderRequest(BaseModel):
    items: list[CreateOrderItemRequest] = Field(..., min_length=1)


class UpdateOrderStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|processing|completed|cancelled)$")
