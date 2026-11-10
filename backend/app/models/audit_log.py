import uuid
from sqlalchemy import Column, String, DateTime, Text, func
from backend.app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=False, index=True)
    actor_id = Column(String, nullable=False)
    previous_state = Column(String, nullable=True)
    new_state = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False)
    prev_log_hash = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

