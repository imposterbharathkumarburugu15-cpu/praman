import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Union, Any, Dict
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Request,
    Response,
)
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.device import Device
from backend.app.models.farm import Farm
from backend.app.models.evidence import Evidence
from backend.app.schemas.evidence import (
    EvidenceIngestReceipt,
    EvidenceReceiptResponse,
    EvidenceResponse,
)
from backend.app.storage.content_storage import content_storage
from backend.app.services.crypto_verifier import CryptoVerifier
from backend.app.services.sequence_service import SequenceService
from backend.app.services.delay_evaluator import assess_upload_legitimacy
from backend.app.services.ai_dispatcher import ai_dispatcher
from backend.app.services.audit_service import AuditService
from backend.app.services.receipt_signer import sign_server_receipt
from backend.app.services.duplicate_service import DuplicateService, DuplicateOutcome
from ai_engine.evaluator import ai_evaluator
from crypto.rfc8785 import canonicalize

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.post("/ingest", response_model=EvidenceIngestReceipt)
async def ingest_evidence(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    envelope: Optional[str] = Form(None),
    signature: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
):
    """Multipart and JSON evidence ingestion endpoint.
    
    Coordinates cryptographic verification against crypto/ package,
    monotonic sequence enforcement with row-level locks, idempotency evaluation,
    atomic content-addressable storage, audit trail logging, and asynchronous AI task dispatch.
    """
    server_now = datetime.now(timezone.utc)
    server_timestamp_iso = server_now.isoformat()

    envelope_dict = None
    signature_b64 = None
    image_bytes = None

    # 1. Parse Multipart Form or JSON Body
    upload_file = file or image
    if envelope is not None:
        try:
            envelope_dict = json.loads(envelope)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Envelope must be valid JSON: {e}",
            )
        signature_b64 = signature
        if upload_file is not None:
            image_bytes = await upload_file.read()
    else:
        try:
            body = await request.json()
            envelope_dict = body.get("envelope")
            signature_b64 = body.get("signature") or body.get("signature_b64")
            raw_img_b64 = body.get("image_b64") or body.get("image")
            if raw_img_b64:
                image_bytes = base64.b64decode(raw_img_b64)
        except Exception:
            pass

    if not envelope_dict or not signature_b64 or image_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: envelope, signature, and binary file",
        )

    device_id = envelope_dict.get("device_id")
    evidence_id = envelope_dict.get("evidence_id") or str(uuid.uuid4())
    farm_id = envelope_dict.get("farm_id")
    seq_num = envelope_dict.get("sequence_number")
    lifecycle_stage = envelope_dict.get("lifecycle_stage", "CROP_GROWTH")
    submitted_image_hash = envelope_dict.get("image_hash")

    if not device_id or seq_num is None or not submitted_image_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envelope missing essential fields (device_id, sequence_number, image_hash)",
        )

    # 2. Check binary image SHA-256 against envelope image_hash
    actual_hash = hashlib.sha256(image_bytes).hexdigest().lower()
    if actual_hash != str(submitted_image_hash).lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image hash does not match binary file",
        )

    # 3. Check capture timestamp future boundary (tolerance = 5 minutes)
    meta = envelope_dict.get("metadata", {})
    capture_ts = meta.get("capture_timestamp") or server_timestamp_iso
    try:
        capture_dt = datetime.fromisoformat(capture_ts.replace("Z", "+00:00"))
        if capture_dt > server_now + timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Capture timestamp cannot be in the future",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed capture timestamp: {e}",
        )

    # 4. Acquire row-level lock on Device (SELECT ... FOR UPDATE)
    query = db.query(Device).filter(Device.id == device_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        device = query.with_for_update().first()
    else:
        device = query.first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unregistered device",
        )
    if device.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device status {device.status} is not permitted to submit evidence",
        )

    # 5. Cryptographic signature verification over RFC 8785 canonical envelope bytes
    is_crypto_valid, crypto_err = CryptoVerifier.verify_envelope_and_image(
        envelope=envelope_dict,
        signature_b64=signature_b64,
        image_bytes=image_bytes,
        public_key_pem=device.public_key_pem,
    )
    if not is_crypto_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=crypto_err or "Invalid cryptographic signature",
        )

    # 6. Monotonic Sequence Progression & Idempotency Evaluation
    try:
        canonical_envelope_hash = hashlib.sha256(canonicalize(envelope_dict)).hexdigest()
    except Exception:
        canonical_envelope_hash = None

    is_seq_ok, seq_status_code, seq_msg, existing_ev = SequenceService.evaluate_sequence(
        db=db,
        device_id=device.id,
        sequence_number=seq_num,
        image_hash=actual_hash,
        canonical_envelope_hash=canonical_envelope_hash,
    )

    if not is_seq_ok:
        # Log conflict attempt in audit trail
        AuditService.log_event(
            db=db,
            event_type="REPLAY_CONFLICT_ATTEMPT",
            entity_type="DEVICE",
            entity_id=device.id,
            actor_id=device.id,
            previous_state=None,
            new_state="CONFLICT",
            payload=f"{device.id}:{seq_num}:{actual_hash}".encode("utf-8"),
        )
        raise HTTPException(status_code=seq_status_code, detail=seq_msg)

    # 7. Handle Idempotent Retry ($S == S_last$ with matching payload) -> Return original receipt with HTTP 200 OK
    if existing_ev:
        AuditService.log_event(
            db=db,
            event_type="IDEMPOTENT_RETRY",
            entity_type="EVIDENCE",
            entity_id=existing_ev.id,
            actor_id=device.id,
            previous_state=existing_ev.status,
            new_state=existing_ev.status,
            payload=f"{existing_ev.id}:{existing_ev.sequence_number}:{existing_ev.image_hash}".encode("utf-8"),
        )
        response.status_code = status.HTTP_200_OK
        receipt_sig = sign_server_receipt(
            evidence_id=existing_ev.id,
            device_id=device.id,
            sequence_number=existing_ev.sequence_number,
            image_hash=existing_ev.image_hash,
            server_timestamp=existing_ev.created_at.isoformat(),
        )
        return EvidenceIngestReceipt(
            status="DURABLY_ACKED",
            evidence_id=existing_ev.id,
            device_id=device.id,
            sequence_number=existing_ev.sequence_number,
            server_timestamp=existing_ev.created_at.isoformat(),
            receipt_signature=receipt_sig,
            task_id="IDEMPOTENT_CACHED",
            classification="IDEMPOTENT_RETRY",
        )

    # 8. Offline Delay Legitimacy Assessment (F-38 Invariant: delays are not fraud)
    delay_assessment = assess_upload_legitimacy(
        capture_timestamp_iso=capture_ts,
        server_timestamp_iso=server_timestamp_iso,
        is_sequence_valid=True,
        is_signature_valid=True,
    )
    if delay_assessment.get("status") == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload rejected: {delay_assessment.get('reason')}",
        )

    # 9. Duplicate Content Detection per ORIGINAL_REQUEST.md §4
    dup_result = DuplicateService.evaluate_duplicate(
        db=db,
        image_bytes=image_bytes,
        current_sha256=actual_hash,
    )
    classification = dup_result.classification

    # 9.5 Immediate Forensic & AI Evaluation for Receipt Feedback
    try:
        immediate_forensics = ai_evaluator.forensics.evaluate_tamper(image_bytes)
    except Exception as fe:
        immediate_forensics = {"is_tamper_suspected": False, "is_ai_generated_suspected": False}

    # 10. Atomic Content-Addressable Storage
    stored_hash = content_storage.store(image_bytes)

    # 11. Generate Server Durable Receipt Signature
    receipt_sig = sign_server_receipt(
        evidence_id=evidence_id,
        device_id=device.id,
        sequence_number=seq_num,
        image_hash=stored_hash,
        server_timestamp=server_timestamp_iso,
    )

    # 11.5 Ensure target Farm exists for foreign key integrity
    target_farm_id = farm_id or "farm_default"
    existing_farm = db.query(Farm).filter(Farm.id == target_farm_id).first()
    if not existing_farm:
        # Auto-provision farm record for device farmer so foreign key constraint passes
        new_farm = Farm(
            id=target_farm_id,
            farmer_id=device.farmer_id,
            farm_name="Registered Farm Parcel",
            crop_type=lifecycle_stage or "CROP_GROWTH",
            boundary_geojson='{"type":"Polygon","coordinates":[[[0,0],[0,0.001],[0.001,0.001],[0.001,0],[0,0]]]}',
            boundary_version=1,
            crs="EPSG:4326",
            area_sq_meters=4046.86,
            area_acres=1.0,
            area_hectares=0.404686,
            is_valid=True,
        )
        db.add(new_farm)
        db.flush()

    # 12. Persist Evidence Record & Advance Device Monotonic Sequence Counter
    device.last_sequence_number = seq_num
    evidence_status = "PENDING_REVIEW" if dup_result.is_duplicate else "DURABLY_ACKED"
    evidence_record = Evidence(
        id=evidence_id,
        farm_id=target_farm_id,
        device_id=device.id,
        sequence_number=seq_num,
        lifecycle_stage=lifecycle_stage,
        image_hash=stored_hash,
        phash=dup_result.phash,
        dhash=dup_result.dhash,
        duplicate_of_id=dup_result.matched_evidence_id if dup_result.is_duplicate else None,
        duplicate_type=dup_result.classification if dup_result.is_duplicate else None,
        hamming_distance=dup_result.hamming_distance,
        canonical_envelope_json=canonicalize(envelope_dict).decode("utf-8") if isinstance(canonicalize(envelope_dict), bytes) else json.dumps(envelope_dict),
        signature_b64=signature_b64,
        status=evidence_status,
    )
    db.add(evidence_record)
    db.commit()
    db.refresh(evidence_record)

    # 13. Dispatch Asynchronous AI Task
    ai_task_id = ai_dispatcher.enqueue_evaluation(
        evidence_id=evidence_record.id,
        image_hash=stored_hash,
        envelope=envelope_dict,
    )

    # 14. Append-only Audit Log Entry
    if dup_result.is_duplicate:
        AuditService.log_event(
            db=db,
            event_type="DUPLICATE_DETECTED",
            entity_type="EVIDENCE",
            entity_id=evidence_record.id,
            actor_id=device.id,
            previous_state="QUEUED",
            new_state=dup_result.classification,
            payload=f"{evidence_record.id}:{stored_hash}:{dup_result.classification}:{dup_result.matched_evidence_id or ''}".encode("utf-8"),
        )
    else:
        AuditService.log_event(
            db=db,
            event_type="EVIDENCE_INGESTED",
            entity_type="EVIDENCE",
            entity_id=evidence_record.id,
            actor_id=device.id,
            previous_state="QUEUED",
            new_state="DURABLY_ACKED",
            payload=f"{evidence_record.id}:{stored_hash}:{seq_num}".encode("utf-8"),
        )

    response.status_code = status.HTTP_201_CREATED
    is_tampered_flag = bool(immediate_forensics.get("is_tamper_suspected", False))
    is_ai_flag = bool(immediate_forensics.get("is_ai_generated_suspected", False))
    return EvidenceIngestReceipt(
        status="DURABLY_ACKED",
        evidence_id=evidence_record.id,
        device_id=device.id,
        sequence_number=seq_num,
        server_timestamp=server_timestamp_iso,
        receipt_signature=receipt_sig,
        task_id=ai_task_id,
        classification=classification,
        is_duplicate=dup_result.is_duplicate,
        duplicate_type=dup_result.classification if dup_result.is_duplicate else None,
        hamming_distance=dup_result.hamming_distance,
        delay_days=delay_assessment.get("delay_days"),
        is_tamper_suspected=is_tampered_flag,
        is_ai_generated_suspected=is_ai_flag,
        forensic_action="FLAG_FOR_REVIEW" if (is_tampered_flag or is_ai_flag) else "APPROVE",
    )



@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    resp = EvidenceResponse.model_validate(ev)
    resp.is_duplicate = bool(ev.duplicate_of_id or (ev.duplicate_type and ev.duplicate_type != "NEW_EVIDENCE"))
    return resp

