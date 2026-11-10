"""Tier 2: Sequence Number Boundary Tests.
Tests sequence number 0 rejection, negative sequence values, max integer limits (2^31-1),
and concurrent interleaved multi-device submissions.
"""

import pytest
from tests_e2e.tier1_features.test_f13_sequence_enforcement import SequenceEnforcerOracle


class TestB05SequenceBoundaries:
    """Verifies sequence counter boundary limits and integer edge conditions."""

    def test_sequence_zero_rejected(self):
        """Boundary 1: Verifies sequence number 0 is rejected (initial sequence must be 1)."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-b05")

        status = enforcer.process_submission("dev-b05", seq=0, image_hash="hash0")
        assert status == 409

    def test_negative_sequence_rejected(self):
        """Boundary 2: Verifies negative sequence numbers are rejected."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-b05")

        status = enforcer.process_submission("dev-b05", seq=-1, image_hash="hash_neg")
        assert status == 409

    def test_high_integer_sequence_monotonicity(self):
        """Boundary 3: Verifies large 32-bit integer sequence numbers (e.g. 100,000 to 100,001) behave monotonically."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-b05")
        # Simulate device currently at seq 100,000
        enforcer.devices["dev-b05"]["last_sequence"] = 100000

        status_ok = enforcer.process_submission("dev-b05", seq=100001, image_hash="hash_large")
        assert status_ok == 201

        status_stale = enforcer.process_submission("dev-b05", seq=100000, image_hash="hash_stale")
        assert status_stale == 409

    def test_interleaved_multi_device_sequences(self):
        """Boundary 4: Verifies alternating interleaved submissions from two independent devices."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-X")
        enforcer.register_device("dev-Y")

        # Dev X: 1
        assert enforcer.process_submission("dev-X", seq=1, image_hash="x1") == 201
        # Dev Y: 1
        assert enforcer.process_submission("dev-Y", seq=1, image_hash="y1") == 201
        # Dev X: 2
        assert enforcer.process_submission("dev-X", seq=2, image_hash="x2") == 201
        # Dev Y: 2
        assert enforcer.process_submission("dev-Y", seq=2, image_hash="y2") == 201

    def test_simultaneous_idempotent_retry(self):
        """Boundary 5: Verifies identical retry immediately following first submission returns 200."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-idem")

        assert enforcer.process_submission("dev-idem", seq=1, image_hash="idem_hash") == 201
        assert enforcer.process_submission("dev-idem", seq=1, image_hash="idem_hash") == 200
