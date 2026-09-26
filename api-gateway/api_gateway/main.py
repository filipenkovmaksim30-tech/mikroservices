import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from api_gateway.observability import install_http_logging
from api_gateway.api_clients.http import create_http_client
from api_gateway.exceptions import InvalidAccessTokenError, PermissionDeniedError
from api_gateway.routers.admin_catalog import router as admin_catalog_router
from api_gateway.routers.admin_orders import router as admin_order_router
from api_gateway.routers.analytics import router as analytic_router
from api_gateway.routers.auth import router as auth_router
from api_gateway.routers.catalog import router as catalog_router
from api_gateway.routers.dependencies import get_settings
from api_gateway.routers.health import router as health_router
from api_gateway.routers.orders import router as order_router
from api_gateway.routers.payments import router as payment_router

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http_client = create_http_client(settings)
    app.state.http_client = http_client

    try:
        yield
    finally:
        await http_client.aclose()


app = FastAPI(
    title="Orderflow API-Gateway",
    lifespan=lifespan
)

@app.exception_handler(httpx.TimeoutException)
async def handle_timeout(
    _request: Request,
    _exc: httpx.TimeoutException,
) -> JSONResponse:
    logger.warning("upstream.timeout")
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={"detail": "Upstream service timed out"},
    )

@app.exception_handler(httpx.RequestError)
async def handle_service_unavailable(
    _request: Request,
    _exc: httpx.RequestError,
) -> JSONResponse:
    logger.error("upstream.unavailable")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Upstream service unavailable"},
    )


@app.exception_handler(PermissionDeniedError)
async def handle_permission_denied(
    _request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.exception_handler(InvalidAccessTokenError)
async def handle_invalid_access_token(
    _request: Request,
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
api_router.include_router(admin_catalog_router)
api_router.include_router(order_router)
api_router.include_router(admin_order_router)
api_router.include_router(analytic_router)
api_router.include_router(payment_router)

install_http_logging(app)
app.include_router(api_router)
