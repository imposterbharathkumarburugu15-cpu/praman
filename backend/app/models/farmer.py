import uuid
from sqlalchemy import Column, String, DateTime, CheckConstraint, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    language_pref = Column(
        String,
        CheckConstraint("language_pref IN ('te', 'hi', 'en')", name="ck_farmer_language"),
        nullable=False,
        default="te"
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    devices = relationship("Device", back_populates="farmer", cascade="all, delete-orphan")
    farms = relationship("Farm", back_populates="farmer", cascade="all, delete-orphan")

