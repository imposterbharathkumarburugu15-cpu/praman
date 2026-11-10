import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evidence_id = Column(String, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # 'APPROVE', 'REJECT', 'REQUEST_RETAKE'
    new_state = Column(String, nullable=False)  # 'APPROVED', 'REJECTED', 'RETAKE_REQUESTED'
    notes = Column(Text, nullable=True, default="")
    decided_at = Column(DateTime, server_default=func.now(), nullable=False)

    evidence = relationship("Evidence", back_populates="review_decisions")
