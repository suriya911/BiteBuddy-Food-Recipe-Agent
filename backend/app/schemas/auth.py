from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=2, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class AuthUser(BaseModel):
    user_id: int
    username: str
    email: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class RegisterResponse(BaseModel):
    message: str
    email: str
    otp_required: bool = True


class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    otp_code: str = Field(min_length=4, max_length=10)


class ResendOtpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class MessageResponse(BaseModel):
    message: str


class FavoriteRecipeItem(BaseModel):
    recipe_id: str
    recipe: dict
    saved_at: datetime


class FavoriteSaveRequest(BaseModel):
    recipe: dict


class HistoryItem(BaseModel):
    entry_id: str
    query: str
    result_count: int
    top_recipe_titles: list[str]
    created_at: datetime


class HistorySaveRequest(BaseModel):
    query: str
    result_count: int = 0
    top_recipe_titles: list[str] = Field(default_factory=list)
