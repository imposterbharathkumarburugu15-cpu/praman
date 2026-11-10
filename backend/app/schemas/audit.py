from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor_id: str
    previous_state: Optional[str] = None
    new_state: str
    payload_hash: str
    prev_log_hash: Optional[str] = None
    created_at: datetime
