"""
GoLearn FastAPI Application
Main entry point for the web API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, study, quiz, dashboard, exam, voice, feynman, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("🚀 GoLearn API starting...")
    yield
    # Shutdown
    print("👋 GoLearn API shutting down...")


app = FastAPI(
    title="GoLearn API",
    description="Three-Pass Study Companion API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(study.router, prefix="/study", tags=["Study Sessions"])
app.include_router(quiz.router, prefix="/quiz", tags=["Quiz & Retention"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(exam.router, prefix="/exam", tags=["Exam Generation"])
app.include_router(voice.router, prefix="/ws", tags=["Voice Chat"])
app.include_router(feynman.router, prefix="/feynman", tags=["Feynman Technique"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "GoLearn API is running"}


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {"status": "healthy"}
