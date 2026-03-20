from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: test DB connection
    try:
        from sqlalchemy import text
        from app.db import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] Database connection OK")
    except Exception as e:
        print(f"[WARN] Database connection failed: {e}")
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="AgentID + AgentEscrow API",
    description="Trust infrastructure for the agent economy",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes import agents as agents_router
from app.routes.escrow import router as escrow_router, stripe_router
from app.routes import newsletter as newsletter_router

app.include_router(agents_router.router)
app.include_router(escrow_router)
app.include_router(stripe_router)
app.include_router(newsletter_router.router)


@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "db_connected": True,
    }
