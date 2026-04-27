"""FastAPI 主应用。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from ..config import get_settings, validate_config
from ..core.logging import setup_logging
from .routes import map as map_routes
from .routes import poi, trip

setup_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于 LangChain / LangGraph 的智能旅行规划助手 API",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trip.router, prefix="/api")
app.include_router(poi.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")


@app.on_event("startup")
async def startup_event() -> None:
    """应用启动事件。"""
    logger.info("{} v{} 启动", settings.app_name, settings.app_version)
    logger.info("安全配置摘要: {}", settings.safe_summary())
    for warning in validate_config():
        logger.warning(warning)
    logger.info("API文档: http://localhost:{}/docs", settings.port)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("应用正在关闭")


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }
