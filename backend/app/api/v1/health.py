from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.storage.content_storage import content_storage
from backend.app.services.ai_dispatcher import ai_dispatcher

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint assessing database, storage, and AI dispatcher subsystem status."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    storage_ok = os_storage_check()
    ai_status = "RUNNING" if getattr(ai_dispatcher, "_is_running", False) else "IDLE"

    is_overall_healthy = db_ok and storage_ok

    return {
        "status": "HEALTHY" if is_overall_healthy else "DEGRADED",
        "version": settings.VERSION,
        "database": "CONNECTED" if db_ok else "DISCONNECTED",
        "storage": "READY" if storage_ok else "ERROR",
        "ai_dispatcher": ai_status,
        "components": {
            "database": {
                "status": "UP" if db_ok else "DOWN",
                "port": settings.POSTGRES_PORT,
                "database": settings.POSTGRES_DB,
            },
            "storage": {
                "status": "UP" if storage_ok else "DOWN",
                "base_dir": settings.STORAGE_DIR,
                "writable": storage_ok,
            },
            "ai_dispatcher": {
                "status": ai_status,
                "queue_depth": getattr(ai_dispatcher._queue, "qsize", lambda: 0)(),
            },
        },
    }


def os_storage_check() -> bool:
    import os
    try:
        os.makedirs(settings.STORAGE_DIR, exist_ok=True)
        test_file = os.path.join(settings.STORAGE_DIR, ".health_check_tmp")
        with open(test_file, "w") as f:
            f.write("OK")
        os.remove(test_file)
        return True
    except Exception:
        return False
