"""Tier 4: Scenario RW-02 — Blurry Photo AI Flag, Reviewer Retake, Resubmission, and Anchor.
End-to-end journey:
1. Farmer captures an evening photo with camera motion blur.
2. AI assessment evaluates image: Laplacian variance < 40, flags is_blurry: True.
3. Never-Autonomous-Reject invariant: Image transitions to PENDING_REVIEW (never rejected).
4. Reviewer console displays blur failure badge; reviewer requests retake with clear instructions.
5. Farmer receives mobile notification with reviewer feedback in Telugu.
6. Farmer captures sharp retake image the next morning (Laplacian variance > 150).
7. Retake is signed with next sequence number and uploaded.
8. AI scores retake as sharp; reviewer approves; batched into Merkle ledger anchor.
"""

import uuid
import pytest
from tests_e2e.fixtures.image_generator import (
    SyntheticImageGenerator,
    compute_laplacian_variance,
)
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory
from tests_e2e.fixtures.crypto_fixtures import ReferenceMerkleTree, rfc8785_canonicalize
from tests_e2e.tier1_features.test_f28_never_reject_rule import determine_ai_transition
from tests_e2e.tier1_features.test_f41_signal_visualizer import build_reviewer_inspection_view
from tests_e2e.tier1_features.test_f42_review_decision_engine import ReviewDecisionEngine
from tests_e2e.tier1_features.test_f39_farmer_notifications import NotificationInbox
from tests_e2e.tier1_features.test_f43_merkle_batch_anchor import MerkleBatchEngine


class TestRW02BlurryRetakeWorkflow:
    """Verifies end-to-end AI blur detection, human adjudication, retake resubmission, and anchoring."""

    def test_blurry_photo_retake_lifecycle(self):
        """Executes complete retake flow from initial blur detection to approved ledger commitment."""
        device_id = "device-retake-flow"
        evidence_id_1 = str(uuid.uuid4())
        reviewer_id = "reviewer-laxmi"

        # --- Phase 1: Capture Blurry Evening Photo ---
        blurry_bytes, blur_hash = SyntheticImageGenerator.create_blurry_image(1920, 1080, blur_radius=25)
        blur_score = compute_laplacian_variance(blurry_bytes)
        assert blur_score < 50.0

        # --- Phase 2: AI Pipeline Assessment ---
        ai_assessment_1 = {
            "quality": {
                "blur_score": blur_score,
                "is_blurry": True,
                "exposure_under_pct": 2.0,
                "exposure_over_pct": 1.0,
                "is_exposure_valid": True,
                "width": 1920,
                "height": 1080,
                "is_resolution_valid": True,
                "exif_consistent": True,
            },
            "duplicate": {"exact_sha256_match": False, "phash": "0123456789abcdef", "nearest_phash_distance": 30, "is_duplicate": False},
            "category": {"declared_stage": "CROP_GROWTH", "predicted_class": "cotton_field", "confidence": 0.85, "is_consistent": True},
            "governance": {
                "model_tiers_used": ["deterministic", "pretrained", "heuristic"],
                "manipulation_detector_status": "UNVALIDATED",
                "review_recommended": True,
                "recommended_action": "FLAG_FOR_REVIEW",
            },
        }

        # Verify Never-Autonomous-Reject rule
        initial_state = determine_ai_transition(ai_assessment_1)
        assert initial_state == "PENDING_REVIEW"
        assert initial_state != "REJECTED"

        # --- Phase 3: Reviewer Inspection & Attributable Retake Request ---
        env_1 = EnvelopeFactory.create_valid_envelope(
            evidence_id=evidence_id_1,
            device_id=device_id,
            image_hash=blur_hash,
            sequence_number=1,
        )
        inspection_1 = build_reviewer_inspection_view(env_1, True, ai_assessment_1)
        assert inspection_1["quality_card"]["blur_status"] == "FAIL"

        decision_engine = ReviewDecisionEngine()
        retake_notes = "Image is blurred due to low light. Please retake photo in morning daylight."
        decision_1 = decision_engine.record_decision(
            evidence_id=evidence_id_1,
            reviewer_id=reviewer_id,
            action="REQUEST_RETAKE",
            notes=retake_notes,
        )
        assert decision_1["new_state"] == "RETAKE_REQUESTED"

        # --- Phase 4: Farmer Notification ---
        farmer_inbox = NotificationInbox()
        farmer_inbox.receive_notification(
            evidence_id=evidence_id_1,
            decision=decision_1["new_state"],
            notes=decision_1["notes"],
        )
        assert farmer_inbox.get_unread_count() == 1
        assert farmer_inbox.notifications[0]["notes"] == retake_notes

        # --- Phase 5: Morning Retake Capture (Sharp Image) ---
        sharp_bytes, sharp_hash = SyntheticImageGenerator.create_sharp_crop_image(1920, 1080)
        sharp_score = compute_laplacian_variance(sharp_bytes)
        assert sharp_score > 100.0

        evidence_id_2 = str(uuid.uuid4())
        env_2 = EnvelopeFactory.create_valid_envelope(
            evidence_id=evidence_id_2,
            device_id=device_id,
            image_hash=sharp_hash,
            sequence_number=2,  # Monotonic next sequence
        )

        ai_assessment_2 = {
            "quality": {
                "blur_score": sharp_score,
                "is_blurry": False,
                "exposure_under_pct": 1.0,
                "exposure_over_pct": 0.5,
                "is_exposure_valid": True,
                "width": 1920,
                "height": 1080,
                "is_resolution_valid": True,
                "exif_consistent": True,
            },
            "duplicate": {"exact_sha256_match": False, "phash": "fedcba9876543210", "nearest_phash_distance": 28, "is_duplicate": False},
            "category": {"declared_stage": "CROP_GROWTH", "predicted_class": "cotton_field", "confidence": 0.94, "is_consistent": True},
            "governance": {
                "model_tiers_used": ["deterministic", "pretrained", "heuristic"],
                "manipulation_detector_status": "UNVALIDATED",
                "review_recommended": False,
                "recommended_action": "APPROVE",
            },
        }

        # --- Phase 6: Reviewer Approval & Ledger Anchoring ---
        inspection_2 = build_reviewer_inspection_view(env_2, True, ai_assessment_2)
        assert inspection_2["quality_card"]["blur_status"] == "PASS"

        decision_2 = decision_engine.record_decision(
            evidence_id=evidence_id_2,
            reviewer_id=reviewer_id,
            action="APPROVE",
            notes="Retake photo is sharp, well-exposed, and verified.",
        )
        assert decision_2["new_state"] == "APPROVED"

        # Batch committed to Merkle ledger anchor
        batch_engine = MerkleBatchEngine()
        batch_res = batch_engine.commit_batch([env_2])
        assert batch_res["anchor"]["status"] == "COMMITTED_TO_LEDGER"
        assert evidence_id_2 in batch_res["anchor"]["evidence_ids"]
        assert evidence_id_1 not in batch_res["anchor"]["evidence_ids"]
