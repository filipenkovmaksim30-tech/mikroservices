


from auth_service.security.tokens import TokenService
from auth_service.services.authentication import AuthenticationService
from auth_service.schemas.tokens import TokenResponse


class LoginService:
    def __init__(
        self,
        authentication_service: AuthenticationService,
        token_service: TokenService,
        access_token_expire_minutes: int
    ) -> None:
        self._authentication_service = authentication_service
        self._token_service = token_service
        self._access_token_expire_minutes = access_token_expire_minutes

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._authentication_service.authenticate(email=email, password=password)
        access_token = self._token_service.create_access_token(user_id=user.id, role=user.role)
        return TokenResponse(
            access_token=access_token, expires_in=self._access_token_expire_minutes * 60
        )
