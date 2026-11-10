import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, func
from backend.app.core.database import Base


class MerkleBatch(Base):
    __tablename__ = "merkle_batches"

    id = Column(String, primary_key=True, default=lambda: f"batch-{uuid.uuid4()}")
    merkle_root = Column(String(64), nullable=False, index=True)
    leaf_count = Column(Integer, nullable=False)
    evidence_ids_json = Column(Text, nullable=False)  # JSON-encoded list of evidence IDs
    status = Column(String, nullable=False, default="COMMITTED_TO_LEDGER")
    checkpoint_id = Column(String, nullable=True)
    checkpoint_signature = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
