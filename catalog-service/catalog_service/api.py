from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from catalog_service.db.session import async_engine
from catalog_service.exceptions import (
    InsufficientStockError,
    InvalidAccessTokenError,
    PermissionDeniedError,
    ProductNotFoundError,
)
from catalog_service.routers.admin_products import router as admin_products_router
from catalog_service.routers.products import router as products_router

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="Product Service",
    version="0.1.0"
)

@app.exception_handler(ProductNotFoundError)
async def handle_product_not_found(
    request: Request,
    exc: ProductNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )

@app.exception_handler(InsufficientStockError)
async def handle_product_infficient_stock(
    request: Request,
    exc: InsufficientStockError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
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


app.include_router(products_router)
app.include_router(admin_products_router)

