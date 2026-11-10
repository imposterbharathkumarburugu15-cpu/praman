import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id = Column(String, ForeignKey("farms.id"), nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)
    lifecycle_stage = Column(String, nullable=False)
    image_hash = Column(String, nullable=False, index=True)
    phash = Column(String(64), nullable=True, index=True)
    dhash = Column(String(64), nullable=True, index=True)
    duplicate_of_id = Column(String, ForeignKey("evidence.id"), nullable=True, index=True)
    duplicate_type = Column(String(32), nullable=True)
    hamming_distance = Column(Integer, nullable=True)
    canonical_envelope_json = Column(Text, nullable=False)
    signature_b64 = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="DURABLY_ACKED")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("device_id", "sequence_number", name="uq_device_sequence"),
    )

    farm = relationship("Farm", back_populates="evidence_items")
    device = relationship("Device", back_populates="evidence_items")
    ai_assessments = relationship("AIAssessment", back_populates="evidence", cascade="all, delete-orphan")
    review_decisions = relationship("ReviewDecision", back_populates="evidence", cascade="all, delete-orphan")
    public_tokens = relationship("PublicToken", back_populates="evidence", cascade="all, delete-orphan")
    duplicate_of = relationship("Evidence", remote_side=[id], backref="duplicates")


