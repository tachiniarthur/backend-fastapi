from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class CreateAccountRequest(BaseModel):
    name: str = Field(..., max_length=255)
    username: str = Field(..., max_length=50)
    phone: str = Field(..., max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=6)
    password_confirmation: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class AuthResponse(BaseModel):
    user: UserResponse
    token: str


class CreateAccountResponse(BaseModel):
    message: str
    user: UserResponse
    token: str
