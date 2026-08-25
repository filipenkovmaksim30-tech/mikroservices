from typing import Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(min_length=1)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)

class AccessTokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sub: UUID
    role: str
    iat: datetime
    exp: datetime
    jti: UUID
    iss: str
    aud: str

