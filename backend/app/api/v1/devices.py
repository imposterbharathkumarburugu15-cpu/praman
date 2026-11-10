import uuid
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.farmer import Farmer
from backend.app.models.device import Device
from backend.app.schemas.device import (
    DeviceCreate,
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceRegisterResponse,
    DeviceStatusUpdate,
)
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/register", response_model=DeviceResponse)
def register_device(
    payload: DeviceCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Enrolls a mobile capture device, binding its UUID to a P-256 public key.
    
    Idempotent: Identical registration requests for an active device return HTTP 200 OK.
    """
    key_pem = payload.public_key_pem or payload.public_key_spki
    if not key_pem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing public key (public_key_pem or public_key_spki)",
        )
    key_pem = key_pem.strip()

    # 1. Verify farmer exists
    farmer = db.query(Farmer).filter(Farmer.id == payload.farmer_id).first()
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer {payload.farmer_id} not found",
        )

    device_id = payload.device_id or payload.id or str(uuid.uuid4())

    # 2. Check if device_id already registered (with row lock if postgresql)
    query = db.query(Device).filter(Device.id == device_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        existing = query.with_for_update().first()
    else:
        existing = query.first()

    if existing:
        if (
            existing.public_key_pem.strip() == key_pem
            and str(existing.farmer_id) == str(payload.farmer_id)
            and existing.status == "ACTIVE"
        ):
            response.status_code = status.HTTP_200_OK
            return DeviceResponse(
                id=existing.id,
                device_id=existing.id,
                farmer_id=existing.farmer_id,
                public_key_pem=existing.public_key_pem,
                status=existing.status,
                last_sequence_number=existing.last_sequence_number,
                created_at=existing.created_at,
                registered_at=existing.created_at,
                message="Device already registered (idempotent OK)",
            )

        if existing.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device {device_id} is {existing.status} and cannot be re-registered",
            )

        if existing.public_key_pem.strip() != key_pem:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device {device_id} already registered with different key",
            )

        if str(existing.farmer_id) != str(payload.farmer_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Device {device_id} is bound to a different farmer",
            )

    # 3. Fresh registration
    device = Device(
        id=device_id,
        farmer_id=payload.farmer_id,
        public_key_pem=key_pem,
        status="ACTIVE",
        last_sequence_number=0,
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    # Log audit event
    AuditService.log_event(
        db=db,
        event_type="DEVICE_REGISTERED",
        entity_type="DEVICE",
        entity_id=device.id,
        actor_id=device.farmer_id,
        new_state="ACTIVE",
        payload=f"{device.id}:{device.farmer_id}:{device.public_key_pem[:30]}".encode("utf-8"),
    )

    response.status_code = status.HTTP_201_CREATED
    return DeviceResponse(
        id=device.id,
        device_id=device.id,
        farmer_id=device.farmer_id,
        public_key_pem=device.public_key_pem,
        status=device.status,
        last_sequence_number=device.last_sequence_number,
        created_at=device.created_at,
        registered_at=device.created_at,
        message="Device registered successfully",
    )


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceResponse(
        id=device.id,
        device_id=device.id,
        farmer_id=device.farmer_id,
        public_key_pem=device.public_key_pem,
        status=device.status,
        last_sequence_number=device.last_sequence_number,
        created_at=device.created_at,
        registered_at=device.created_at,
    )


@router.patch("/{device_id}/status", response_model=DeviceResponse)
def update_device_status(
    device_id: str,
    payload: DeviceStatusUpdate,
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    old_status = device.status
    device.status = payload.status
    db.commit()
    db.refresh(device)

    AuditService.log_event(
        db=db,
        event_type="DEVICE_STATUS_CHANGED",
        entity_type="DEVICE",
        entity_id=device.id,
        actor_id="system",
        previous_state=old_status,
        new_state=payload.status,
        payload=f"{device_id}:{old_status}->{payload.status}".encode("utf-8"),
    )

    return DeviceResponse(
        id=device.id,
        device_id=device.id,
        farmer_id=device.farmer_id,
        public_key_pem=device.public_key_pem,
        status=device.status,
        last_sequence_number=device.last_sequence_number,
        created_at=device.created_at,
        registered_at=device.created_at,
    )
