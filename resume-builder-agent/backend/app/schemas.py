import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Gender = Literal["male", "female", "prefer_not_to_say"]
AddressType = Literal["temporary", "permanent"]

_SYMBOL_RE = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]")


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain an uppercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain a number")
    if not _SYMBOL_RE.search(password):
        raise ValueError("Password must contain a symbol")
    return password


class SignUpRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    gender: Gender = "prefer_not_to_say"
    address_type: AddressType = "permanent"
    address: str = Field(default="", max_length=500)
    country_code: str = Field(min_length=1, max_length=10)
    phone: str = Field(min_length=4, max_length=30)
    country: str = Field(min_length=1, max_length=100)
    state: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=100)
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    gender: Gender
    address_type: AddressType
    address: str
    country_code: str
    phone: str
    country: str
    state: str
    city: str
    has_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    gender: Gender | None = None
    address_type: AddressType | None = None
    address: str | None = Field(default=None, max_length=500)
    country_code: str | None = Field(default=None, max_length=10)
    phone: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ResumeCreate(BaseModel):
    title: str = "Untitled Resume"
    template_id: str = "modern"
    data: dict[str, Any] = Field(default_factory=dict)
    styles: dict[str, Any] = Field(default_factory=dict)
    source: Literal["new", "upload"] = "new"


class ResumeUpdate(BaseModel):
    title: str | None = None
    template_id: str | None = None
    data: dict[str, Any] | None = None
    styles: dict[str, Any] | None = None


class ResumeOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    template_id: str
    data: dict[str, Any]
    styles: dict[str, Any]
    source: str
    uploaded_file_path: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
