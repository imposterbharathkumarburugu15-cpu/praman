from typing import Tuple, Optional
from sqlalchemy.orm import Session
from backend.app.models.device import Device
from backend.app.models.evidence import Evidence


class SequenceService:
    @staticmethod
    def evaluate_sequence(
        db: Session,
        device_id: str,
        sequence_number: int,
        image_hash: str,
        canonical_envelope_hash: Optional[str] = None,
    ) -> Tuple[bool, int, str, Optional[Evidence]]:
        """Evaluates per-device monotonic sequence progression and idempotency.
        
        Enforces:
        - Row-level lock: SELECT ... FOR UPDATE on devices
        - Strict progression: S = S_last + 1
        - Stale replay rejection: S < S_last -> 409 Conflict
        - Gap rejection: S > S_last + 1 -> 409 Conflict
        - Boundary rejection: S <= 0 -> 409 Conflict
        - Idempotent retry: S == S_last with matching payload -> 200 OK
        
        Returns:
            (is_ok, http_status, message, existing_evidence_if_idempotent)
        """
        # 1. Enforce sequence boundary: sequence_number must be >= 1
        if sequence_number <= 0:
            return False, 409, f"Conflict: Sequence number must be a positive integer >= 1 (got {sequence_number})", None

        # 2. Query device with row-level lock if supported by database dialect
        query = db.query(Device).filter(Device.id == device_id)
        if db.bind and db.bind.dialect.name == "postgresql":
            device = query.with_for_update().first()
        else:
            device = query.first()

        if not device:
            return False, 404, f"Device {device_id} not found", None

        if device.status != "ACTIVE":
            return False, 403, f"Device status {device.status} is not permitted to submit evidence", None

        # 3. Check for existing record with (device_id, sequence_number)
        existing = db.query(Evidence).filter(
            Evidence.device_id == device_id,
            Evidence.sequence_number == sequence_number
        ).first()

        if existing:
            # Check if this is an identical retry (idempotent submission)
            image_matches = existing.image_hash.lower() == image_hash.lower()
            
            # Check canonical envelope hash if provided
            envelope_matches = True
            if canonical_envelope_hash:
                import hashlib
                existing_canonical_hash = hashlib.sha256(
                    existing.canonical_envelope_json.encode("utf-8")
                ).hexdigest()
                envelope_matches = (existing_canonical_hash == canonical_envelope_hash)

            if image_matches and envelope_matches:
                return True, 200, "Idempotent submission accepted", existing
            else:
                return False, 409, "Conflict: Sequence number already used with differing payload", None

        # 4. Check strictly monotonic progression: sequence_number == last_sequence_number + 1
        expected_seq = device.last_sequence_number + 1
        if sequence_number == expected_seq:
            return True, 201, "Sequence number accepted", None
        elif sequence_number <= device.last_sequence_number:
            return False, 409, f"Conflict: Sequence number {sequence_number} is stale (last is {device.last_sequence_number})", None
        else:
            return False, 409, f"Conflict: Sequence gap detected (expected {expected_seq}, got {sequence_number})", None
