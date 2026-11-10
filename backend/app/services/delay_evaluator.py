from datetime import datetime, timezone
from typing import Dict, Any


def assess_upload_legitimacy(
    capture_timestamp_iso: str,
    server_timestamp_iso: str,
    is_sequence_valid: bool,
    is_signature_valid: bool,
) -> Dict[str, Any]:
    """Enforces the platform invariant: delays do not equal fraud.
    
    Legitimate delayed offline uploads are NEVER classified as fraud when
    sequence numbers and cryptographic signatures are authentic.
    """
    capture_dt = datetime.fromisoformat(capture_timestamp_iso.replace("Z", "+00:00"))
    server_dt = datetime.fromisoformat(server_timestamp_iso.replace("Z", "+00:00"))

    delay_seconds = (server_dt - capture_dt).total_seconds()
    
    # Reject future timestamps beyond 5 minutes clock skew
    if delay_seconds < -300.0:
        return {
            "status": "REJECTED",
            "reason": "FUTURE_TIMESTAMP_DETECTED",
            "is_fraud": True,
            "delay_days": round(delay_seconds / 86400.0, 2),
        }

    if not is_signature_valid:
        return {"status": "REJECTED", "reason": "INVALID_SIGNATURE", "is_fraud": True}

    if not is_sequence_valid:
        return {"status": "CONFLICT", "reason": "OUT_OF_ORDER_SEQUENCE", "is_fraud": True}

    delay_days = max(0.0, delay_seconds / 86400.0)

    # Sequence and signature are valid: legitimate offline delay
    return {
        "status": "ACCEPTED",
        "delay_days": round(delay_days, 1),
        "is_fraud": False,
        "classification": "LEGITIMATE_OFFLINE_DELAY" if delay_days > 1.0 else "ONLINE_SUBMISSION",
    }

