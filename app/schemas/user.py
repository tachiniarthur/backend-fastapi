from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    id: int
    name: str
    username: str | None
    phone: str | None
    email: str
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=255)
    phone: str | None = Field(None, max_length=20)
