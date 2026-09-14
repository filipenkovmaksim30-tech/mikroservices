
from fastapi import APIRouter, Request, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    ForwardedHeadersDependency,
    HttpClientDependency,
    LoginFormDependency,
    SettingsDependency,
)
from api_gateway.schemas.auth import UserRegisterRequest

router = APIRouter(tags=["Auth"], prefix="/auth")


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистарция пользователя"
)
async def register_user(
    forwarded_headers: ForwardedHeadersDependency,
    payload: UserRegisterRequest,
    client: HttpClientDependency,
    settings: SettingsDependency
) -> Response:
    url = f"{settings.auth_base_url.rstrip("/")}/auth/register"
    json_body = payload.model_dump(mode="json")

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        json_body=json_body,
        headers=forwarded_headers,
    )

    return build_gateway_response(upstream_response)


@router.post(
    "/token",
    status_code=status.HTTP_200_OK,
    summary="Создание токена и аутенфикация"
)
async def login_user(
    forwarded_headers: ForwardedHeadersDependency,
    form: LoginFormDependency,
    client: HttpClientDependency,
    settings: SettingsDependency
) -> Response:
    url = f"{settings.auth_base_url.rstrip("/")}/auth/token"
    form_data = {
        "username": form.username,
        "password": form.password,
    }

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        form_data=form_data,
        headers=forwarded_headers,
    )

    return build_gateway_response(upstream_response)

@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Обновление access-токена",
)
async def refresh(
    request: Request,
    forwarded_headers: ForwardedHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
) -> Response:
    url = f"{settings.auth_base_url.rstrip("/")}/auth/refresh"
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    cookies = (
        {settings.refresh_cookie_name: refresh_token}
        if refresh_token is not None
        else None
    )
    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        cookies=cookies,
        headers=forwarded_headers
    )

    return build_gateway_response(upstream_response)

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Закончить сессию",
)
async def logout(
    request: Request,
    forwarded_headers: ForwardedHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency
) -> Response:
    url = f"{settings.auth_base_url.rstrip("/")}/auth/logout"
    refresh_token = request.cookies.get(settings.refresh_cookie_name)

    cookies = (
        {settings.refresh_cookie_name: refresh_token}
        if refresh_token is not None
        else None
    )

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        cookies=cookies,
        headers=forwarded_headers,
    )

    return build_gateway_response(upstream_response)

@router.get(
    "/users/me",
    status_code=status.HTTP_200_OK,
    summary="Получить текущего пользователя",
)
async def get_user(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency
) -> Response:
    url = f"{settings.auth_base_url.rstrip("/")}/users/me"

    upstream_response = await request_upstream(
        client=client,
        url=url,
        method="GET",
        headers=authorization_headers,
    )

    return build_gateway_response(upstream_response)

