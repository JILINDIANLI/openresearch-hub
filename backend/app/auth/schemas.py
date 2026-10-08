from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    organization: str | None = Field(default=None, max_length=255)
    research_interests: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("username", "display_name", mode="before")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return str(value).strip()

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class PublicUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    avatar_url: str | None = None
    organization: str | None = None
    bio: str | None = None
    research_interests: list[str] = Field(default_factory=list)
    website_url: str | None = None
    github_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    # Backward-compatible response fields used by the first frontend version.
    avatar: str | None = None
    research_fields: list[str] = Field(default_factory=list)
    research_interest: list[str] = Field(default_factory=list)
    created_time: datetime | None = None


class UserRead(PublicUserRead):
    email: str
    is_active: bool = True
    role: str = "USER"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
