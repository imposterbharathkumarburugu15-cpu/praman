from datetime import datetime
from typing import Optional, Literal, Dict, Any, Union
import uuid
from pydantic import BaseModel, Field, ConfigDict


class EvidenceMetadata(BaseModel):
    capture_source: Literal["CAMERA", "FILE_UPLOAD"] = "CAMERA"
    capture_timestamp: str
    latitude: float
    longitude: float
    gps_accuracy: float = Field(default=5.0, ge=0.0, le=100.0)


class EvidenceEnvelopeSchema(BaseModel):
    device_id: str
    evidence_id: str
    farm_id: str
    image_hash: str
    lifecycle_stage: Literal["SOWING", "INPUT_APPLICATION", "CROP_GROWTH", "HARVEST", "STORAGE"]
    metadata: EvidenceMetadata
    schema_version: str = "1.0"
    sequence_number: int = Field(..., ge=1)


class EvidenceIngestReceipt(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = "DURABLY_ACKED"
    evidence_id: str
    sequence_number: int
    server_timestamp: str
    receipt_signature: str
    device_id: Optional[str] = None
    task_id: Optional[str] = None
    classification: Optional[str] = None
    delay_days: Optional[float] = None
    is_duplicate: Optional[bool] = None
    duplicate_type: Optional[str] = None
    hamming_distance: Optional[int] = None
    is_tamper_suspected: Optional[bool] = False
    is_ai_generated_suspected: Optional[bool] = False
    forensic_action: Optional[str] = "APPROVE"



class EvidenceReceiptResponse(EvidenceIngestReceipt):
    pass


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    farm_id: str
    device_id: str
    sequence_number: int
    lifecycle_stage: str
    image_hash: str
    canonical_envelope_json: str
    signature_b64: str
    status: str
    created_at: datetime
    phash: Optional[str] = None
    dhash: Optional[str] = None
    duplicate_type: Optional[str] = None
    hamming_distance: Optional[int] = None
    is_duplicate: Optional[bool] = None

