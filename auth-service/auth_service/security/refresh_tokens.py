import hashlib
import secrets

REFRESH_TOKEN_ENTROPY_BYTES = 32

def generate_refresh_token() -> str:
    token = secrets.token_urlsafe(REFRESH_TOKEN_ENTROPY_BYTES)
    return token


def hash_refresh_token(token: str) -> str:
    token_bytes = token.encode("utf-8")
    hash_token = hashlib.sha256(token_bytes)
    return hash_token.hexdigest()
