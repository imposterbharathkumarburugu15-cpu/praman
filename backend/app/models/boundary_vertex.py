import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class BoundaryVertex(Base):
    __tablename__ = "boundary_vertices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id = Column(String, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    boundary_version = Column(Integer, default=1, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    horizontal_accuracy = Column(Float, nullable=True)
    observation_timestamp = Column(DateTime, nullable=True)
    collection_method = Column(String, nullable=True, default="WALK_AND_MARK")
    vertex_sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    farm = relationship("Farm", back_populates="vertices")
