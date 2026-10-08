from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LegacyUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None
    organization: str | None = None
    bio: str | None = None
    research_fields: list[str] = Field(default_factory=list)
    research_interest: list[str] | None = None


class LegacyLogin(BaseModel):
    identifier: str | None = None
    email: str | None = None
    password: str
