"""SecureRAG-Health FastAPI application entry point."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.dependencies import init_embedding_model, init_llm_client, init_spicedb_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler — runs on startup and shutdown.

    Startup:
    1. Initialize SpiceDB client and load schema
    2. Seed default roles and demo tenant if tables are empty
    3. Load embedding model into app state
    4. Initialize LLM client
    """
    logger.info("=" * 60)
    logger.info("SecureRAG-Health API starting up...")
    logger.info("=" * 60)

    # 1. Initialize SpiceDB client
    try:
        spicedb_client = init_spicedb_client()
        if spicedb_client.is_available:
            from app.authz.schema_loader import load_spicedb_schema

            await load_spicedb_schema(spicedb_client)
        else:
            logger.warning("SpiceDB client not available — authorization checks will fail-closed")
    except Exception as e:
        logger.error(f"SpiceDB initialization failed: {e}")

    # 2. Seed initial data (roles and demo data)
    try:
        from app.db.session import AsyncSessionLocal
        from app.seed import seed_initial_data

        async with AsyncSessionLocal() as db:
            await seed_initial_data(db)
    except Exception as e:
        logger.warning(f"Auto-seeding failed (run manually: python -m app.seed): {e}")

    # 3. Load embedding model
    try:
        init_embedding_model()
        logger.info("Embedding model loaded successfully")
    except Exception as e:
        logger.warning(f"Embedding model loading failed (will lazy-load on first request): {e}")

    # 4. Initialize LLM client
    try:
        init_llm_client()
        logger.info("Anthropic LLM client initialized")
    except Exception as e:
        logger.warning(f"LLM client initialization failed: {e}")

    logger.info("=" * 60)
    logger.info("SecureRAG-Health API ready!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("SecureRAG-Health API shutting down...")


# ── Create FastAPI application ───────────────────────────────────
app = FastAPI(
    title="SecureRAG-Health API",
    description=(
        "Secure, role-aware, multi-tenant Retrieval-Augmented Generation (RAG) "
        "system for Hospital Management. Enforces access control via JWT authentication, "
        "SpiceDB authorization (ReBAC), and PostgreSQL Row-Level Security."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware (allow all in dev) ───────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Timing Middleware ────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to every response."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# ── Include Routers ──────────────────────────────────────────────
from app.auth.router import router as auth_router  # noqa: E402
from app.documents.router import router as documents_router  # noqa: E402
from app.rag.router import router as rag_router  # noqa: E402

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(rag_router)


# ── Health Check ─────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}
