from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from auth_service.db.session import async_engine
from auth_service.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    UserBlockedError,
    PermissionDeniedError,
)
from auth_service.routers.login import router as login_router
from auth_service.routers.register import router as register_router
from auth_service.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(
    title="Auth Service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(EmailAlreadyRegisteredError)
async def handle_email_already_registered(
    request: Request,
    exc: EmailAlreadyRegisteredError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


@app.exception_handler(InvalidCredentialsError)
async def handle_invalid_credentials(
    request: Request,
    exc: InvalidCredentialsError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(InvalidAccessTokenError)
async def handle_invalid_access_token(
    request: Request,
    exc: InvalidAccessTokenError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(UserBlockedError)
async def handle_user_blocked(
    request: Request,
    exc: UserBlockedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )

@app.exception_handler(PermissionDeniedError)
async def handle_user_blocked(
    request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )

app.include_router(register_router)
app.include_router(login_router)
app.include_router(users_router)
