from pwdlib import PasswordHash


class PasswordHasher:
    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, hash_password_from_db: str) -> bool:
        return self._password_hash.verify(password, hash_password_from_db)