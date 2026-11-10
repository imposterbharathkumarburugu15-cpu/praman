"""Tier 3: Interaction Test I-02 — AI Quality Flags x Reviewer Console x Attributable Retake.
Validates the interaction when local AI flags low quality evidence,
displaying signals in the reviewer console, and triggering an attributable retake request to the farmer.
"""

import uuid
import pytest
from tests_e2e.tier1_features.test_f28_never_reject_rule import determine_ai_transition
from tests_e2e.tier1_features.test_f41_signal_visualizer import build_reviewer_inspection_view
from tests_e2e.tier1_features.test_f42_review_decision_engine import ReviewDecisionEngine
from tests_e2e.tier1_features.test_f39_farmer_notifications import NotificationInbox


class TestI02AIFlagsReviewerFlow:
    """Verifies cross-feature flow from AI anomaly flagging to reviewer decision to mobile notification."""

    def test_end_to_end_blurry_flag_to_retake_notification(self):
        """Interaction 1: Verifies complete pipeline: blurry image -> AI flags PENDING_REVIEW -> Reviewer requests retake -> Farmer notified."""
        evidence_id = str(uuid.uuid4())
        device_id = "device-farmer-01"

        # 1. AI Assessment: Blurry image (score 25.0 < 50.0)
        ai_assessment = {
            "quality": {
                "blur_score": 25.0,
                "is_blurry": True,
                "exposure_under_pct": 0.0,
                "exposure_over_pct": 0.0,
                "is_exposure_valid": True,
                "width": 1920,
                "height": 1080,
                "is_resolution_valid": True,
                "exif_consistent": True,
            },
            "duplicate": {
                "exact_sha256_match": False,
                "phash": "1234567890abcdef",
                "nearest_phash_distance": 25,
                "is_duplicate": False,
            },
            "category": {
                "declared_stage": "CROP_GROWTH",
                "predicted_class": "cotton_field",
                "confidence": 0.82,
                "is_consistent": True,
            },
            "governance": {
                "model_tiers_used": ["deterministic", "pretrained", "heuristic"],
                "manipulation_detector_status": "UNVALIDATED",
                "review_recommended": True,
                "recommended_action": "FLAG_FOR_REVIEW",
            },
        }

        # 2. Never-Autonomous-Reject Rule: Transition to PENDING_REVIEW
        state = determine_ai_transition(ai_assessment)
        assert state == "PENDING_REVIEW"

        # 3. Reviewer Console: Visualizer card generation
        envelope = {"evidence_id": evidence_id, "device_id": device_id, "sequence_number": 4}
        inspection_view = build_reviewer_inspection_view(envelope, True, ai_assessment)
        assert inspection_view["quality_card"]["blur_status"] == "FAIL"

        # 4. Reviewer Decision Engine: Human reviewer decides REQUEST_RETAKE
        reviewer_engine = ReviewDecisionEngine()
        retake_notes = "Image is out of focus. Please capture sharp photo of the cotton flowers."
        decision_rec = reviewer_engine.record_decision(
            evidence_id=evidence_id,
            reviewer_id="reviewer-padma",
            action="REQUEST_RETAKE",
            notes=retake_notes,
        )
        assert decision_rec["new_state"] == "RETAKE_REQUESTED"

        # 5. Farmer Mobile Notification: Farmer receives attributable feedback
        farmer_inbox = NotificationInbox()
        farmer_inbox.receive_notification(
            evidence_id=evidence_id,
            decision=decision_rec["new_state"],
            notes=decision_rec["notes"],
        )
        assert farmer_inbox.get_unread_count() == 1
        notif = farmer_inbox.notifications[0]
        assert notif["decision"] == "RETAKE_REQUESTED"
        assert notif["notes"] == retake_notes

    def test_overexposed_image_reviewer_flow(self):
        """Interaction 2: Verifies overexposed image flags review and reviewer requests retake."""
        ai_assessment = {
            "quality": {"is_blurry": False, "is_exposure_valid": False, "blur_score": 120.0, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 30},
            "category": {"is_consistent": True},
        }
        assert determine_ai_transition(ai_assessment) == "PENDING_REVIEW"

    def test_category_mismatch_reviewer_flow(self):
        """Interaction 3: Verifies crop category mismatch (declared SOWING, observed HARVEST) transitions to human review."""
        ai_assessment = {
            "quality": {"is_blurry": False, "is_exposure_valid": True, "blur_score": 150.0, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 25},
            "category": {"is_consistent": False},
        }
        assert determine_ai_transition(ai_assessment) == "PENDING_REVIEW"

    def test_pristine_evidence_bypasses_reviewer_queue(self):
        """Interaction 4: Verifies high-quality pristine evidence transitions to PENDING_BATCH without reviewer intervention."""
        ai_assessment = {
            "quality": {"is_blurry": False, "is_exposure_valid": True, "blur_score": 180.0, "width": 1920, "height": 1080},
            "duplicate": {"is_duplicate": False, "nearest_phash_distance": 35},
            "category": {"is_consistent": True},
        }
        assert determine_ai_transition(ai_assessment) == "PENDING_BATCH"

    def test_reviewer_override_approval_on_borderline_evidence(self):
        """Interaction 5: Verifies human reviewer can evaluate a flagged image and choose to APPROVE it."""
        engine = ReviewDecisionEngine()
        decision = engine.record_decision(
            evidence_id="ev-borderline",
            reviewer_id="rev-experienced",
            action="APPROVE",
            notes="Slight motion blur is acceptable; crop canopy is clearly identifiable.",
        )
        assert decision["new_state"] == "APPROVED"
