from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=12, max_length=128)
    repeat_password: str = Field(min_length=12, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        if not any(character.isalpha() for character in password):
            raise ValueError("Пароль должен содержать хотя бы одну букву")
        if not any(character.isdigit() for character in password):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        return password

    @model_validator(mode="after")
    def check_passwords(self) -> Self:
        if self.password != self.repeat_password:
            raise ValueError("Пароли должны совпадать")
        return self