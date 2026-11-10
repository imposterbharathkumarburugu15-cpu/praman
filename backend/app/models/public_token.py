import secrets
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def generate_public_token() -> str:
    """Generates a 256-bit cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


class PublicToken(Base):
    __tablename__ = "public_tokens"

    token = Column(String(128), primary_key=True, index=True)
    evidence_id = Column(String, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    evidence = relationship("Evidence", back_populates="public_tokens")
