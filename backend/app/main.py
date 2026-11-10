from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.api.v1 import api_router
from backend.app.core.database import engine, Base
from backend.app.services.ai_dispatcher import ai_dispatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP:
    # 1. Initialize tables if not already created
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Database init during lifespan startup: {e}")

    # 2. Start asynchronous AI task dispatcher background worker
    ai_dispatcher.start()

    yield

    # SHUTDOWN:
    # Gracefully stop the AI task dispatcher
    await ai_dispatcher.stop(timeout_seconds=2.0)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Praman-Sequence"],
)

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "project": "PRAMAN Evidence Intelligence Platform",
        "status": "ONLINE",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
    }
