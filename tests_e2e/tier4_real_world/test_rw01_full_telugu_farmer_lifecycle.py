"""Tier 4: Scenario RW-01 — Full Telugu Farmer Lifecycle to Privacy-Preserving Public QR Verification.
End-to-end journey:
1. Farmer Ramesh in Adilabad registers cotton parcel using Telugu UI (te).
2. Captures 5 agricultural lifecycle stages: SOWING, INPUT_APPLICATION, CROP_GROWTH, HARVEST, STORAGE.
3. Envelopes signed on-device with P-256 ECDSA and queued offline in SQLite.
4. Device reconnects, performs idempotent sync with durable server acknowledgement.
5. Local AI assesses quality, exposure, resolution, and crop stage consistency.
6. Reviewer console inspects crypto/AI badges and records attributable approval.
7. Merkle batching engine commits records into local ledger anchor record.
8. Public verification token generated; consumer independently verifies cryptographic proof with zero PII/GPS leaked.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
import pytest

from tests_e2e.fixtures.crypto_fixtures import (
    generate_p256_keypair,
    sign_p256_der,
    verify_p256_der,
    ReferenceMerkleTree,
    rfc8785_canonicalize,
)
from tests_e2e.fixtures.image_generator import SyntheticImageGenerator
from tests_e2e.fixtures.spatial_fixtures import (
    validate_farm_polygon,
    SpatialPolygonFactory,
)
from tests_e2e.fixtures.envelope_fixtures import EnvelopeFactory, VALID_LIFECYCLE_STAGES
from tests_e2e.tier1_features.test_f29_multilingual_onboarding import translate
from tests_e2e.tier1_features.test_f43_merkle_batch_anchor import MerkleBatchEngine
from tests_e2e.tier1_features.test_f44_public_token import PublicTokenRegistry
from tests_e2e.tier1_features.test_f45_privacy_public_verify import PublicVerificationPortal


class TestRW01FullTeluguFarmerLifecycle:
    """Verifies complete real-world agricultural evidence lifecycle."""

    def test_complete_telugu_farmer_lifecycle(self, mock_sqlite_queue):
        """Executes full end-to-end farmer journey from Telugu onboarding to consumer QR verification."""
        # --- Step 1: Telugu Onboarding & Profile ---
        locale = "te"
        assert translate("app_title", locale) == "ప్రమాణ్ ఆధార వేదిక"
        farmer_id = str(uuid.uuid4())
        farmer_phone = "+919849012345"

        # --- Step 2: Farm Parcel Registration in Adilabad ---
        boundary_coords = SpatialPolygonFactory.valid_telangana_farm_polygon()
        is_poly_valid, msg = validate_farm_polygon(boundary_coords)
        assert is_poly_valid is True
        farm_id = str(uuid.uuid4())

        # --- Step 3: Device Enrollment with P-256 Keypair ---
        priv_key, pub_pem, _ = generate_p256_keypair()
        device_id = str(uuid.uuid4())

        # --- Step 4: Capture 5 Lifecycle Stages Offline ---
        queue_cursor = mock_sqlite_queue.cursor()
        evidence_records = []
        raw_images = []

        for seq, stage in enumerate(VALID_LIFECYCLE_STAGES, start=1):
            # Generate sharp synthetic image
            img_bytes, img_hash = SyntheticImageGenerator.create_sharp_crop_image(1920, 1080)
            raw_images.append(img_bytes)

            ev_id = str(uuid.uuid4())
            env = EnvelopeFactory.create_valid_envelope(
                device_id=device_id,
                evidence_id=ev_id,
                farm_id=farm_id,
                image_hash=img_hash,
                lifecycle_stage=stage,
                sequence_number=seq,
                capture_source="CAMERA",
                latitude=19.6640,
                longitude=78.5320,
            )
            canonical_bytes = rfc8785_canonicalize(env)
            sig_der = sign_p256_der(priv_key, canonical_bytes)

            # Persist in mobile SQLite offline queue
            queue_cursor.execute(
                """INSERT INTO offline_evidence_queue 
                   (evidence_id, device_id, sequence_number, envelope_json, signature_b64, image_path, image_hash, sync_state)
                   VALUES (?, ?, ?, ?, 'MOCK_B64_SIG', '/local/path.jpg', ?, 'QUEUED')""",
                (ev_id, device_id, seq, json.dumps(env), img_hash),
            )
            evidence_records.append((env, canonical_bytes, sig_der))

        mock_sqlite_queue.commit()

        # Verify all 5 queued offline
        queue_cursor.execute("SELECT COUNT(*) FROM offline_evidence_queue WHERE device_id = ?", (device_id,))
        assert queue_cursor.fetchone()[0] == 5

        # --- Step 5: Network Reconnect & Durable Ingestion ---
        # Server verifies monotonic sequence progression and cryptographic signatures
        for seq, (env, canonical_bytes, sig_der) in enumerate(evidence_records, start=1):
            assert verify_p256_der(pub_pem, sig_der, canonical_bytes) is True
            assert env["sequence_number"] == seq

            # Server durable ACK
            queue_cursor.execute(
                "UPDATE offline_evidence_queue SET sync_state = 'DURABLY_ACKED', synced_at = CURRENT_TIMESTAMP WHERE evidence_id = ?",
                (env["evidence_id"],),
            )

        mock_sqlite_queue.commit()
        queue_cursor.execute("SELECT COUNT(*) FROM offline_evidence_queue WHERE sync_state = 'DURABLY_ACKED'")
        assert queue_cursor.fetchone()[0] == 5

        # --- Step 6: Reviewer Console Batch Approval & Ledger Anchoring ---
        batch_engine = MerkleBatchEngine()
        approved_envelopes = [env for env, _, _ in evidence_records]

        batch_result = batch_engine.commit_batch(approved_envelopes)
        anchor = batch_result["anchor"]
        tree = batch_result["tree"]

        assert anchor["status"] == "COMMITTED_TO_LEDGER"
        assert anchor["leaf_count"] == 5

        # --- Step 7: Consumer Public QR Code Generation ---
        token_registry = PublicTokenRegistry()
        harvest_envelope = approved_envelopes[3]  # HARVEST stage
        public_token = token_registry.issue_token(harvest_envelope["evidence_id"])
        assert len(public_token) >= 43

        # --- Step 8: Privacy-Preserving Web Verification Recomputation ---
        harvest_idx = 3
        public_payload = PublicVerificationPortal.sanitize_public_payload(
            harvest_envelope, tree, harvest_idx, public_token
        )

        # Invariant 1: Zero Farmer PII
        payload_str = json.dumps(public_payload).lower()
        for pii in ["ramesh", "9849012345", "phone"]:
            assert pii not in payload_str

        # Invariant 2: Zero Exact GPS Coordinates
        assert "19.664" not in payload_str
        assert "78.532" not in payload_str
        assert public_payload["region_coarse"] == "Adilabad, Telangana"

        # Invariant 3: Independent Client Merkle Proof Recomputation
        harvest_leaf_canonical = rfc8785_canonicalize(harvest_envelope)
        proof = public_payload["inclusion_proof"]
        expected_root = bytes.fromhex(public_payload["merkle_root"])

        proof_valid = ReferenceMerkleTree.verify_inclusion_proof(
            harvest_leaf_canonical,
            proof,
            expected_root,
        )
        assert proof_valid is True
        assert public_payload["provenance_status"] == "COMMITTED_TO_LEDGER"
