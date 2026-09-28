from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — load model metadata before table creation
from app.api import (
    admin,
    assistant,
    auth,
    catalog,
    education,
    products,
    profile,
    reports,
    routines,
    seller,
    shop,
)
from app.core.config import settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="DermaSphere API",
    version="0.1.0",
    description="Skincare marketplace and personalized skincare services",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(catalog.router)
app.include_router(profile.router)
app.include_router(shop.router)
app.include_router(seller.router)
app.include_router(routines.router)
app.include_router(admin.router)
app.include_router(assistant.router)
app.include_router(education.router)
app.include_router(reports.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "service": "dermasphere-api"}
