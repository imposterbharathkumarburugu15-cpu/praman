import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class AIAssessment(Base):
    __tablename__ = "ai_assessments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evidence_id = Column(String, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    blur_score = Column(Float, nullable=False, default=0.0)
    is_blurry = Column(Boolean, nullable=False, default=False)
    exposure_under_pct = Column(Float, nullable=False, default=0.0)
    exposure_over_pct = Column(Float, nullable=False, default=0.0)
    is_exposure_valid = Column(Boolean, nullable=False, default=True)
    width = Column(Integer, nullable=False, default=0)
    height = Column(Integer, nullable=False, default=0)
    is_resolution_valid = Column(Boolean, nullable=False, default=True)
    sha256 = Column(String(64), nullable=False)
    phash = Column(String(64), nullable=False)
    nearest_phash_distance = Column(Integer, nullable=True)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    predicted_crop_class = Column(String, nullable=True)
    crop_confidence = Column(Float, nullable=True)
    is_crop_consistent = Column(Boolean, nullable=False, default=True)
    ela_variance = Column(Float, nullable=True)
    noise_variance = Column(Float, nullable=True)
    is_tamper_suspected = Column(Boolean, nullable=False, default=False)
    recommendation = Column(String, nullable=False, default="AUTO_APPROVE")
    assessment_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    evidence = relationship("Evidence", back_populates="ai_assessments")
