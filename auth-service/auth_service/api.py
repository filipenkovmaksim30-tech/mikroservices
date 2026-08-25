from fastapi import FastAPI
from auth_service.routers.register import router as register_router
from auth_service.routers.login import router as login_router

app = FastAPI()


app.include_router(register_router)
app.include_router(login_router)
