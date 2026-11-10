import uuid
import hashlib
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        new_state: str,
        payload: bytes,
        previous_state: Optional[str] = None,
    ) -> AuditLog:
        payload_hash = hashlib.sha256(payload).hexdigest()
        
        # Get previous log hash for hash-chaining
        last_log = db.query(AuditLog).order_by(AuditLog.created_at.desc()).first()
        prev_hash = None
        if last_log:
            prev_data = f"{last_log.log_id}:{last_log.event_type}:{last_log.payload_hash}"
            prev_hash = hashlib.sha256(prev_data.encode("utf-8")).hexdigest()
        
        audit_entry = AuditLog(
            log_id=str(uuid.uuid4()),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            previous_state=previous_state,
            new_state=new_state,
            payload_hash=payload_hash,
            prev_log_hash=prev_hash,
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry

