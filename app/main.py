import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import tasks_router, telegram_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Register Telegram webhook on startup
    try:
        from app.services.telegram_service import TelegramService
        telegram = TelegramService(settings)
        webhook_url = f"{settings.BASE_URL}/webhook/telegram"
        await telegram.set_webhook(webhook_url, settings.TELEGRAM_WEBHOOK_SECRET)
    except Exception as exc:
        logger.warning("Could not register Telegram webhook: %s", exc)

    yield

    logger.info("Shutting down…")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router, prefix="/api/v1")
app.include_router(telegram_router)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.APP_VERSION})
