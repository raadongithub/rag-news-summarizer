"""Health check endpoint."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    """Return backend readiness status."""
    runtime = getattr(request.app.state, "runtime", None)
    return {
        "status": "ok",
        "service": "backend",
        "startup_complete": bool(getattr(request.app.state, "startup_complete", False)),
        "milvus_ready": bool(getattr(runtime, "chunk_store", None)),
    }
