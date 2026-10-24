from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ContactCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    message: str = Field(min_length=10, max_length=3000)

    @field_validator("name", "message")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank")
        return value


class ContactCreated(BaseModel):
    id: int
    message: str


class AdminLogin(BaseModel):
    credential: str = Field(min_length=1, max_length=10000)


class AdminToken(BaseModel):
    token: str


class AdminMessage(BaseModel):
    id: int
    name: str
    email: EmailStr
    message: str
    created_at: datetime
