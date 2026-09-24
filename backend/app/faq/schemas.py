from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class FAQCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("question", "answer")
    @classmethod
    def validate_not_blank(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{info.field_name} cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FAQUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=500)
    answer: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("question", "answer")
    @classmethod
    def validate_not_blank(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError(f"{info.field_name} cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FAQResponse(BaseModel):
    id: UUID
    question: str
    answer: str
    category: str | None
    is_active: bool
    created_by: UUID
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
