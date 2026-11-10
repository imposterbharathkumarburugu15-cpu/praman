"""F-38: Offline Delay Legitimacy Handler Tests.
Validates the core platform invariant: legitimate delayed offline uploads
are NEVER classified as fraud when sequence numbers and cryptographic signatures are authentic.
"""

from datetime import datetime, timezone, timedelta
import pytest


def assess_upload_legitimacy(
    capture_timestamp_iso: str,
    server_timestamp_iso: str,
    is_sequence_valid: bool,
    is_signature_valid: bool,
) -> dict:
    """Enforces the platform invariant: delays do not equal fraud."""
    capture_dt = datetime.fromisoformat(capture_timestamp_iso.replace("Z", "+00:00"))
    server_dt = datetime.fromisoformat(server_timestamp_iso.replace("Z", "+00:00"))

    delay_days = (server_dt - capture_dt).total_seconds() / 86400.0

    if not is_signature_valid:
        return {"status": "REJECTED", "reason": "INVALID_SIGNATURE", "is_fraud": True}

    if not is_sequence_valid:
        return {"status": "CONFLICT", "reason": "OUT_OF_ORDER_SEQUENCE", "is_fraud": True}

    # Sequence and signature are valid: legitimate offline delay
    return {
        "status": "ACCEPTED",
        "delay_days": round(delay_days, 1),
        "is_fraud": False,
        "classification": "LEGITIMATE_OFFLINE_DELAY" if delay_days > 1.0 else "ONLINE_SUBMISSION",
    }


class TestF38DelayLegitimacy:
    """Verifies invariant: delayed offline uploads are not classified as fraud."""

    def test_fourteen_day_monsoon_offline_delay_accepted(self):
        """Test 1: Verifies 14-day delayed upload from rural area is accepted as legitimate."""
        now = datetime.now(timezone.utc)
        two_weeks_ago = now - timedelta(days=14)

        res = assess_upload_legitimacy(
            capture_timestamp_iso=two_weeks_ago.isoformat(),
            server_timestamp_iso=now.isoformat(),
            is_sequence_valid=True,
            is_signature_valid=True,
        )

        assert res["status"] == "ACCEPTED"
        assert res["is_fraud"] is False
        assert res["classification"] == "LEGITIMATE_OFFLINE_DELAY"
        assert res["delay_days"] >= 14.0

    def test_thirty_day_offline_delay_accepted(self):
        """Test 2: Verifies 30-day offline delay during harvest season is accepted without penalty."""
        now = datetime.now(timezone.utc)
        month_ago = now - timedelta(days=30)

        res = assess_upload_legitimacy(
            capture_timestamp_iso=month_ago.isoformat(),
            server_timestamp_iso=now.isoformat(),
            is_sequence_valid=True,
            is_signature_valid=True,
        )

        assert res["status"] == "ACCEPTED"
        assert res["is_fraud"] is False

    def test_immediate_online_submission(self):
        """Test 3: Verifies standard real-time upload (delay < 5 minutes) is classified as ONLINE_SUBMISSION."""
        now = datetime.now(timezone.utc)
        two_mins_ago = now - timedelta(minutes=2)

        res = assess_upload_legitimacy(
            capture_timestamp_iso=two_mins_ago.isoformat(),
            server_timestamp_iso=now.isoformat(),
            is_sequence_valid=True,
            is_signature_valid=True,
        )

        assert res["status"] == "ACCEPTED"
        assert res["classification"] == "ONLINE_SUBMISSION"
        assert res["is_fraud"] is False

    def test_invalid_sequence_with_delay_is_flagged(self):
        """Test 4: Verifies an out-of-order sequence replay is flagged regardless of delay."""
        now = datetime.now(timezone.utc)
        res = assess_upload_legitimacy(
            capture_timestamp_iso=(now - timedelta(days=5)).isoformat(),
            server_timestamp_iso=now.isoformat(),
            is_sequence_valid=False,  # Replay or skip!
            is_signature_valid=True,
        )
        assert res["status"] == "CONFLICT"
        assert res["is_fraud"] is True

    def test_invalid_signature_with_delay_is_rejected(self):
        """Test 5: Verifies tampered signature with delay is rejected."""
        now = datetime.now(timezone.utc)
        res = assess_upload_legitimacy(
            capture_timestamp_iso=(now - timedelta(days=3)).isoformat(),
            server_timestamp_iso=now.isoformat(),
            is_sequence_valid=True,
            is_signature_valid=False,
        )
        assert res["status"] == "REJECTED"
        assert res["is_fraud"] is True
