from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from messaging_lab.db.session import async_engine
from messaging_lab.exceptions import (
    OrderNotFoundError,
    OrderValidationError,
)
from messaging_lab.routers.orders import router as orders_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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
    _request: Request,
    exc: OrderNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(OrderValidationError)
async def handle_order_validation_error(
    _request: Request,
    exc: OrderValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


app.include_router(orders_router)
