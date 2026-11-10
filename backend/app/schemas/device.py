from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from crypto.ecdsa_p256 import load_public_key, public_key_to_pem, CryptographicError


class DeviceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    farmer_id: str
    public_key_pem: Optional[str] = Field(None, description="NIST P-256 ECDSA Public Key in PEM format")
    public_key_spki: Optional[str] = Field(None, description="NIST P-256 Public Key in SPKI PEM or DER Base64")
    device_model: Optional[str] = Field(None, max_length=128)


class DeviceCreate(DeviceBase):
    device_id: Optional[str] = None
    id: Optional[str] = None

    @field_validator("public_key_pem", "public_key_spki")
    @classmethod
    def validate_public_key(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        try:
            pub_key = load_public_key(v)
            return public_key_to_pem(pub_key).strip()
        except Exception as err:
            raise ValueError(f"Invalid NIST P-256 public key: {err}") from err


class DeviceRegisterRequest(DeviceCreate):
    pass


class DeviceStatusUpdate(BaseModel):
    status: Literal["ACTIVE", "REVOKED", "SUSPENDED"]


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: Optional[str] = None
    farmer_id: str
    public_key_pem: str
    status: str
    last_sequence_number: int
    created_at: datetime
    registered_at: Optional[datetime] = None
    message: Optional[str] = None


class DeviceRegisterResponse(DeviceResponse):
    pass
