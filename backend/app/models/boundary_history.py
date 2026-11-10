import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class BoundaryHistory(Base):
    __tablename__ = "boundary_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id = Column(String, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    boundary_version = Column(Integer, nullable=False, index=True)
    boundary_geojson = Column(Text, nullable=False)
    area_sq_meters = Column(Float, nullable=False)
    area_acres = Column(Float, nullable=False)
    crs = Column(String, default="EPSG:4326", nullable=False)
    validation_details = Column(Text, nullable=True)
    superseded_at = Column(DateTime, server_default=func.now(), nullable=False)

    farm = relationship("Farm", back_populates="boundary_history")
