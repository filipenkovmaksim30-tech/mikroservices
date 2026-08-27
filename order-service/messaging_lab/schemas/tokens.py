from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

class AccessTokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sub: UUID
    role: str
    iat: datetime
    exp: datetime
    jti: UUID
    iss: str
    aud: str