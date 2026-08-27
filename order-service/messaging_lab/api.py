from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from messaging_lab.db.session import async_engine
from messaging_lab.exceptions import (
    OrderNotFoundError,
    OrderValidationError,
    InvalidAccessTokenError,
    PermissionDeniedError
)
from messaging_lab.routers.orders import router as orders_router
from messaging_lab.routers.admin_orders import router as admin_orders_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="Order Service",
    version="0.1.0",
)


@app.exception_handler(OrderNotFoundError)
async def handle_order_not_found(
    request: Request,
    exc: OrderNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(OrderValidationError)
async def handle_order_validation_error(
    request: Request,
    exc: OrderValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
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

app.include_router(orders_router)
app.include_router(admin_orders_router)
