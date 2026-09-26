from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from pydantic import ValidationError

from auth_service.db.models.users import UserRole
from auth_service.exceptions import InvalidAccessTokenError
from auth_service.schemas.users import UserRegister
from auth_service.security.refresh_tokens import generate_refresh_token, hash_refresh_token
from auth_service.security.tokens import TokenService


def test_refresh_token_hash_is_stable_without_exposing_token() -> None:
    token = generate_refresh_token()

    assert token != generate_refresh_token()
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != token
    assert len(hash_refresh_token(token)) == 64


def test_registration_rejects_password_mismatch() -> None:
    with pytest.raises(ValidationError, match="Пароли должны совпадать"):
        UserRegister(
            email="buyer@example.com",
            password="password12345",
            repeat_password="different12345",
        )


def test_access_token_uses_signature_and_rejects_tampering() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode()
    service = TokenService(
        private_key=private_pem,
        public_key=public_pem,
        algorithm="RS256",
        access_token_expire_minutes=15,
        issuer="auth-service",
        audience="orderflow-services",
    )
    user_id = uuid4()

    token = service.create_access_token(user_id=user_id, role=UserRole.USER)
    payload = service.decode_access_token(token)

    assert payload.sub == user_id
    assert payload.role == UserRole.USER
    signature = token.rsplit(".", 1)[1]
    changed_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token(token.rsplit(".", 1)[0] + "." + changed_signature)
