from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth, tailor, templates

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


app = FastAPI(title="ResumeForge API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(templates.router, prefix="/api")
app.include_router(tailor.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Return a health signal for local and container deployments."""
    return {"status": "healthy", "product": "ResumeForge"}
