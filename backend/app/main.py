import os
<<<<<<< HEAD
from dotenv import load_dotenv

load_dotenv()
=======
from pathlib import Path
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if not os.getenv("VERTEX_IGNORE_ENV_FILE"):
    load_dotenv(dotenv_path=ENV_FILE, override=True)

print("Vertex Docs .env path:", ENV_FILE)
print("Vertex Docs LLM API key loaded:", bool(os.getenv("LLM_API_KEY", "").strip()))
print("Vertex Docs LLM model:", os.getenv("LLM_MODEL"))
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models
<<<<<<< HEAD
from .routers import auth, settings, documents, pdf, ai, templates
from .chatbot.routes import router as chatbot_router


# Create database tables
Base.metadata.create_all(bind=engine)
=======
from .routers import auth, settings, documents, pdf, ai, templates, admin, notifications, history, sharing, annotations, signatures, export, translation
from .chatbot.routes import router as chatbot_router


# Create legacy/application tables as before, but let Alembic own the new
# activity log table so startup cannot silently modify an existing database.
Base.metadata.create_all(
    bind=engine,
    tables=[table for table in Base.metadata.sorted_tables if table.name != "activity_logs"],
)
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5


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
    templates.router,
<<<<<<< HEAD
=======
    admin.router,
    notifications.router,
    history.router,
    sharing.router,
    annotations.router,
    signatures.router,
    export.router,
    translation.router,
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    chatbot_router,
):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "Vertex Docs API"
    }
<<<<<<< HEAD
    
=======
    
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
