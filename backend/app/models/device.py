import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, CheckConstraint, Text, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    public_key_pem = Column(Text, nullable=False)
    status = Column(
        String,
        CheckConstraint("status IN ('ACTIVE', 'REVOKED', 'SUSPENDED')", name="ck_device_status"),
        nullable=False,
        default="ACTIVE"
    )
    last_sequence_number = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    farmer = relationship("Farmer", back_populates="devices")
    evidence_items = relationship("Evidence", back_populates="device")

