from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from analytics_service.exceptions import InvalidAccessTokenError, OrderNotFoundError, PermissionDeniedError
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from analytics_service.observability import install_http_logging
from analytics_service.db.session import async_engine

from analytics_service.routers.analytics_order import router as analytics_router
from analytics_service.exceptions import InvalidAnalyticsPeriodError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="Analytics Service",
    version="0.1.0",
)

@app.exception_handler(InvalidAccessTokenError)
async def handle_invalid_acces_token(
    request: Request,
    exc: InvalidAccessTokenError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.exception_handler(PermissionDeniedError)
async def handle_permission_denied(
    request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )

@app.exception_handler(OrderNotFoundError)
async def handle_order_not_found(
    request: Request,
    exc: InvalidAnalyticsPeriodError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(InvalidAnalyticsPeriodError)
async def handle_order_validation_error(
    request: Request,
    exc: InvalidAnalyticsPeriodError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


install_http_logging(app)
app.include_router(analytics_router)
