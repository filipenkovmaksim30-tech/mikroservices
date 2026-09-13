import httpx

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI, APIRouter, Request, status
from fastapi.responses import JSONResponse

from api_gateway.routers.dependencies import get_settings
from api_gateway.api_clients.http import create_http_client
from api_gateway.routers.health import router as health_router
from api_gateway.routers.catalog import router as catalog_router
from api_gateway.routers.auth import router as auth_router
from api_gateway.exeptions import PermissionDeniedError, InvalidAccessTokenError

api_router = APIRouter(prefix="/api")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http_client = create_http_client(settings)
    app.state.http_client = http_client

    yield

    await http_client.aclose()


app = FastAPI(
    title="Orderflow API-Gateway",
    lifespan=lifespan
)

@app.exception_handler(httpx.TimeoutException)
async def handle_timeout(
    _request: Request,
    exc: httpx.TimeoutException,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={"detail": "Upstream service timed out"},
    )

@app.exception_handler(httpx.RequestError)
async def handle_service_unavailable(
    request: Request,
    exc: httpx.RequestError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Upstream service unavailable"},
    )


@app.exception_handler(PermissionDeniedError)
async def handle_timeout(
    _request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.exception_handler(InvalidAccessTokenError)
async def handle_service_unavailable(
    request: Request,
    exc: InvalidAccessTokenError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


api_router.include_router(health_router)
api_router.include_router(catalog_router)
api_router.include_router(auth_router)
app.include_router(api_router)