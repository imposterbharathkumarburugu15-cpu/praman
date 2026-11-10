"""F-13: Monotonic Sequence Number Enforcer Tests.
Validates strict per-device monotonic sequence progression (S = S_last + 1),
rejection of replays (HTTP 409 Conflict), and gap detection.
"""

import pytest


class SequenceEnforcerOracle:
    """Reference sequence enforcer logic per Interface Contract R2."""

    def __init__(self):
        # Maps device_id -> {"last_sequence": int, "history": {seq: image_hash}}
        self.devices = {}

    def register_device(self, device_id: str):
        self.devices[device_id] = {"last_sequence": 0, "history": {}}

    def process_submission(self, device_id: str, seq: int, image_hash: str) -> int:
        if device_id not in self.devices:
            raise KeyError(f"Device {device_id} not registered")

        dev = self.devices[device_id]
        last_seq = dev["last_sequence"]

        # Check idempotent retry
        if seq in dev["history"]:
            if dev["history"][seq] == image_hash:
                return 200  # Idempotent retry OK
            else:
                return 409  # Conflict: same sequence with different payload

        # Check strictly monotonic: next must be last_seq + 1
        if seq == last_seq + 1:
            dev["last_sequence"] = seq
            dev["history"][seq] = image_hash
            return 201  # Created
        elif seq <= last_seq:
            return 409  # Conflict: stale sequence
        else:
            return 409  # Conflict: sequence gap (seq > last_seq + 1)


class TestF13SequenceEnforcement:
    """Verifies monotonic sequence counter invariants."""

    def test_initial_sequence_acceptance(self):
        """Test 1: Verifies first submission must have sequence_number == 1."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-01")

        status = enforcer.process_submission("dev-01", seq=1, image_hash="hash_seq_1")
        assert status == 201

    def test_consecutive_monotonic_progression(self):
        """Test 2: Verifies strictly increasing sequences (1, 2, 3, 4, 5) are accepted."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-01")

        for s in range(1, 6):
            status = enforcer.process_submission("dev-01", seq=s, image_hash=f"hash_{s}")
            assert status == 201

    def test_replay_with_different_payload_returns_409(self):
        """Test 3: Verifies replaying an old sequence number with different data returns HTTP 409 Conflict."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-01")

        enforcer.process_submission("dev-01", seq=1, image_hash="hash_1")
        enforcer.process_submission("dev-01", seq=2, image_hash="hash_2")

        # Attempt to replay seq=1 with malicious payload
        status = enforcer.process_submission("dev-01", seq=1, image_hash="MALICIOUS_HASH")
        assert status == 409

    def test_sequence_gap_returns_409(self):
        """Test 4: Verifies skipping sequence numbers (e.g. 1 -> 3) is rejected."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-01")

        enforcer.process_submission("dev-01", seq=1, image_hash="hash_1")

        # Jump straight to seq=3
        status = enforcer.process_submission("dev-01", seq=3, image_hash="hash_3")
        assert status == 409

    def test_device_sequence_isolation(self):
        """Test 5: Verifies sequence counters are strictly isolated per device."""
        enforcer = SequenceEnforcerOracle()
        enforcer.register_device("dev-A")
        enforcer.register_device("dev-B")

        # Dev A reaches seq=3
        enforcer.process_submission("dev-A", seq=1, image_hash="a1")
        enforcer.process_submission("dev-A", seq=2, image_hash="a2")
        enforcer.process_submission("dev-A", seq=3, image_hash="a3")

        # Dev B starts at seq=1 independently
        status_b = enforcer.process_submission("dev-B", seq=1, image_hash="b1")
        assert status_b == 201
