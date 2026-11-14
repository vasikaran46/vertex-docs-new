import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models
from .routers import auth, settings, documents, pdf, ai, templates


# Create database tables
Base.metadata.create_all(bind=engine)


# Initialize FastAPI
app = FastAPI(
    title="Vertex Docs API",
    version="1.0.0"
)


# Allow frontend development origins
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]


# Include additional origins configured in .env
env_origins = os.getenv("CORS_ORIGINS", "")

if env_origins:
    allowed_origins.extend(
        origin.strip()
        for origin in env_origins.split(",")
        if origin.strip()
    )


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register API routers
for router in (
    auth.router,
    settings.router,
    documents.router,  
    pdf.router,
    ai.router,
    templates.router
):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "Vertex Docs API"
    }
    