"""F-37: Offline Sync State Machine & Protocol Tests.
Validates the mobile sync state machine transitions:
QUEUED -> SYNCING -> DURABLY_ACKED -> FAILED, handling network reconnects and backoffs.
"""

import pytest


class SyncStateMachine:
    """Models mobile client sync state machine."""

    ALLOWED_TRANSITIONS = {
        "QUEUED": ["SYNCING"],
        "SYNCING": ["DURABLY_ACKED", "QUEUED", "FAILED"],
        "FAILED": ["QUEUED"],  # Manual retry
        "DURABLY_ACKED": [],    # Terminal state
    }

    def __init__(self, initial_state: str = "QUEUED"):
        self.state = initial_state
        self.retries = 0

    def transition(self, next_state: str):
        if next_state not in self.ALLOWED_TRANSITIONS.get(self.state, []):
            raise ValueError(f"Illegal state transition: {self.state} -> {next_state}")
        self.state = next_state

    def on_network_failure(self):
        self.retries += 1
        if self.retries >= 3:
            self.transition("FAILED")
        else:
            self.transition("QUEUED")


class TestF37SyncStateMachine:
    """Verifies state machine transitions and network resilience."""

    def test_happy_path_sync_lifecycle(self):
        """Test 1: Verifies QUEUED -> SYNCING -> DURABLY_ACKED happy path."""
        sm = SyncStateMachine()
        assert sm.state == "QUEUED"

        sm.transition("SYNCING")
        assert sm.state == "SYNCING"

        sm.transition("DURABLY_ACKED")
        assert sm.state == "DURABLY_ACKED"

    def test_transient_network_drop_reverts_to_queued(self):
        """Test 2: Verifies network disconnection during SYNCING reverts to QUEUED for later attempt."""
        sm = SyncStateMachine()
        sm.transition("SYNCING")

        sm.on_network_failure()
        assert sm.state == "QUEUED"
        assert sm.retries == 1

    def test_repeated_failures_transition_to_failed(self):
        """Test 3: Verifies 3 consecutive failures transition state to FAILED."""
        sm = SyncStateMachine()

        for _ in range(2):
            sm.transition("SYNCING")
            sm.on_network_failure()
            assert sm.state == "QUEUED"

        # Third failure
        sm.transition("SYNCING")
        sm.on_network_failure()
        assert sm.state == "FAILED"
        assert sm.retries == 3

    def test_illegal_transition_raises_error(self):
        """Test 4: Verifies direct jump from QUEUED to DURABLY_ACKED without SYNCING is prohibited."""
        sm = SyncStateMachine()
        with pytest.raises(ValueError, match="Illegal state transition"):
            sm.transition("DURABLY_ACKED")

    def test_terminal_state_immutable(self):
        """Test 5: Verifies DURABLY_ACKED state cannot transition to any other state."""
        sm = SyncStateMachine("DURABLY_ACKED")
        with pytest.raises(ValueError, match="Illegal state transition"):
            sm.transition("SYNCING")
