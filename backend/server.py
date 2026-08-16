"""VyaparPulse AI — FastAPI entry point."""
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.db import close_client, ensure_indexes, reset_client
from app.routers.auth import router as auth_router
from app.routers.demo import router as demo_router
from app.routers.tenant import router as tenant_router
from app.routers.imports import router as imports_router
from app.routers.radar import router as radar_router
from app.routers.phase3 import router as phase3_router
from app.routers.brief import router as brief_router
from app.routers.share import router as share_router
from app.seed import seed_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vyaparpulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_client()
    await ensure_indexes()
    seed_info = await seed_all()
    logger.info("Startup seed complete: %s", seed_info)
    try:
        from app.demo_seed import seed_contest_sandbox
        demo_info = await seed_contest_sandbox()
        logger.info("Contest sandbox seed: %s", demo_info)
    except Exception as e:
        logger.warning("Contest sandbox seed skipped: %s", e)
    yield
    await close_client()


app = FastAPI(title="VyaparPulse AI", lifespan=lifespan)

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(demo_router)
app.include_router(tenant_router)
app.include_router(imports_router)
app.include_router(radar_router)
app.include_router(phase3_router)
app.include_router(brief_router)
app.include_router(share_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "vyaparpulse-ai", "phase": 4}
