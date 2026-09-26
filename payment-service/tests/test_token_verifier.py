from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from payment_service.exceptions import InvalidAccessTokenError
from payment_service.security.tokens import TokenVerifier


def test_payment_verifies_signed_token_and_rejects_wrong_audience() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    public_pem = key.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode()
    verifier = TokenVerifier(public_pem, "RS256", "auth-service", "orderflow-services")
    now = datetime.now(UTC)
    user_id = uuid4()
    claims = {
        "sub": str(user_id), "role": "admin", "iat": now,
        "exp": now + timedelta(minutes=15), "jti": str(uuid4()),
        "iss": "auth-service", "aud": "orderflow-services",
    }

    valid = jwt.encode(claims, private_pem, algorithm="RS256")
    assert verifier.decode_access_token(valid).sub == user_id

    wrong_audience = jwt.encode(
        {**claims, "aud": "different-service"}, private_pem, algorithm="RS256"
    )
    with pytest.raises(InvalidAccessTokenError):
        verifier.decode_access_token(wrong_audience)
