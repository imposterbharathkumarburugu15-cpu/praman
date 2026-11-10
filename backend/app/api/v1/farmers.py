import time
import uuid
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import jwt

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.farmer import Farmer
from backend.app.schemas.farmer import (
    FarmerCreate,
    FarmerRegisterRequest,
    FarmerLoginRequest,
    LanguageUpdateRequest,
    FarmerResponse,
    FarmerAuthResponse,
)
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/farmers", tags=["Farmers"])


def generate_jwt_token(farmer_id: str, language_pref: str) -> str:
    now = int(time.time())
    payload = {
        "sub": farmer_id,
        "role": "FARMER",
        "language_pref": language_pref,
        "iat": now,
        "exp": now + 86400,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _handle_registration(payload: Union[FarmerCreate, FarmerRegisterRequest], db: Session) -> FarmerAuthResponse:
    # Check if phone number is already registered
    existing = db.query(Farmer).filter(Farmer.phone_number == payload.phone_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Farmer with phone number {payload.phone_number} already registered",
        )

    farmer_id = getattr(payload, "farmer_id", None) or getattr(payload, "id", None) or str(uuid.uuid4())
    farmer = Farmer(
        id=str(farmer_id),
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        language_pref=payload.language_pref,
    )
    db.add(farmer)
    db.commit()
    db.refresh(farmer)

    # Log audit event
    AuditService.log_event(
        db=db,
        event_type="FARMER_REGISTERED",
        entity_type="FARMER",
        entity_id=farmer.id,
        actor_id=farmer.id,
        new_state="REGISTERED",
        payload=f"{farmer.full_name}:{farmer.phone_number}:{farmer.language_pref}".encode("utf-8"),
    )

    token = generate_jwt_token(farmer.id, farmer.language_pref)
    f_resp = FarmerResponse.model_validate(farmer)
    return FarmerAuthResponse(
        farmer=f_resp,
        access_token=token,
        token_type="bearer",
        expires_in=86400,
        id=farmer.id,
        full_name=farmer.full_name,
        phone_number=farmer.phone_number,
        language_pref=farmer.language_pref,
        created_at=farmer.created_at,
    )


@router.post("/register", response_model=FarmerAuthResponse, status_code=status.HTTP_201_CREATED)
def register_farmer_explicit(payload: FarmerRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new farmer profile, issuing a JWT session token."""
    return _handle_registration(payload, db)


@router.post("", response_model=FarmerAuthResponse, status_code=status.HTTP_201_CREATED)
def register_farmer(payload: FarmerCreate, db: Session = Depends(get_db)):
    """Registers a new farmer profile (root collection route)."""
    return _handle_registration(payload, db)


@router.post("/login", response_model=FarmerAuthResponse)
def login_farmer(payload: FarmerLoginRequest, db: Session = Depends(get_db)):
    """Authenticates farmer by registered phone number and issues session JWT."""
    farmer = db.query(Farmer).filter(Farmer.phone_number == payload.phone_number).first()
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer with phone number {payload.phone_number} not found",
        )

    token = generate_jwt_token(farmer.id, farmer.language_pref)
    f_resp = FarmerResponse.model_validate(farmer)
    return FarmerAuthResponse(
        farmer=f_resp,
        access_token=token,
        token_type="bearer",
        expires_in=86400,
        id=farmer.id,
        full_name=farmer.full_name,
        phone_number=farmer.phone_number,
        language_pref=farmer.language_pref,
        created_at=farmer.created_at,
    )


@router.patch("/{farmer_id}/language", response_model=FarmerResponse)
def update_farmer_language(
    farmer_id: str,
    payload: LanguageUpdateRequest,
    db: Session = Depends(get_db),
):
    """Updates farmer preferred UI language ('te', 'hi', 'en')."""
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer not found")

    old_lang = farmer.language_pref
    farmer.language_pref = payload.language_pref
    db.commit()
    db.refresh(farmer)

    AuditService.log_event(
        db=db,
        event_type="FARMER_LANGUAGE_UPDATED",
        entity_type="FARMER",
        entity_id=farmer.id,
        actor_id=farmer.id,
        previous_state=old_lang,
        new_state=payload.language_pref,
        payload=f"{farmer_id}:{old_lang}->{payload.language_pref}".encode("utf-8"),
    )

    return farmer


@router.get("/{farmer_id}", response_model=FarmerResponse)
def get_farmer(farmer_id: str, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer not found")
    return farmer


@router.get("", response_model=List[FarmerResponse])
def list_farmers(db: Session = Depends(get_db)):
    return db.query(Farmer).all()
