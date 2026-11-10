from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.audit_log import AuditLog
from backend.app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    entity_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """Retrieves immutable audit log events with optional filtering by entity or event type."""
    query = db.query(AuditLog)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    if order.lower() == "desc":
        query = query.order_by(AuditLog.created_at.desc())
    else:
        query = query.order_by(AuditLog.created_at.asc())

    return query.limit(limit).all()
