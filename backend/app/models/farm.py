import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Farm(Base):
    __tablename__ = "farms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String, ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    farm_name = Column(String, nullable=False)
    crop_type = Column(String, nullable=False)
    boundary_geojson = Column(Text, nullable=False)
    boundary_version = Column(Integer, default=1, nullable=False)
    crs = Column(String, default="EPSG:4326", nullable=False)
    area_sq_meters = Column(Float, default=0.0, nullable=False)
    area_acres = Column(Float, default=0.0, nullable=False)
    area_hectares = Column(Float, default=0.0, nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)
    validation_details = Column(Text, nullable=True)
    season = Column(String, nullable=True)
    district = Column(String, nullable=True)
    state = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

    farmer = relationship("Farmer", back_populates="farms")
    evidence_items = relationship("Evidence", back_populates="farm")
    vertices = relationship(
        "BoundaryVertex",
        back_populates="farm",
        cascade="all, delete-orphan",
        order_by="BoundaryVertex.vertex_sequence",
    )
    boundary_history = relationship(
        "BoundaryHistory",
        back_populates="farm",
        cascade="all, delete-orphan",
        order_by="desc(BoundaryHistory.boundary_version)",
    )
