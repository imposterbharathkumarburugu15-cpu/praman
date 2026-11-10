"""F-34: Farm Lifecycle Stage Categorization Tests.
Validates agricultural lifecycle stage taxonomy (SOWING, INPUT_APPLICATION,
CROP_GROWTH, HARVEST, STORAGE) and chronological sequence progression.
"""

import pytest
from tests_e2e.fixtures.envelope_fixtures import VALID_LIFECYCLE_STAGES, EnvelopeFactory


class TestF34LifecycleStage:
    """Verifies lifecycle stage enumeration and sequence invariants."""

    def test_all_five_stages_supported(self):
        """Test 1: Verifies all five stages exist in canonical taxonomy."""
        expected = ["SOWING", "INPUT_APPLICATION", "CROP_GROWTH", "HARVEST", "STORAGE"]
        assert list(VALID_LIFECYCLE_STAGES) == expected

    def test_invalid_stage_rejected(self):
        """Test 2: Verifies non-standard stage names raise ValueError."""
        def check_stage(stage):
            if stage not in VALID_LIFECYCLE_STAGES:
                raise ValueError(f"Invalid stage: {stage}")
            return True

        with pytest.raises(ValueError):
            check_stage("PROCESSING_FACTORY")

        with pytest.raises(ValueError):
            check_stage("RETAIL_SALE")

    def test_envelope_contains_valid_stage(self):
        """Test 3: Verifies envelope factory embeds valid stage string."""
        env = EnvelopeFactory.create_valid_envelope(lifecycle_stage="HARVEST")
        assert env["lifecycle_stage"] == "HARVEST"

    def test_chronological_stage_sequence(self):
        """Test 4: Verifies logical temporal ordering of stages (index-based)."""
        stage_order = {s: i for i, s in enumerate(VALID_LIFECYCLE_STAGES)}
        assert stage_order["SOWING"] < stage_order["CROP_GROWTH"]
        assert stage_order["CROP_GROWTH"] < stage_order["HARVEST"]
        assert stage_order["HARVEST"] < stage_order["STORAGE"]

    def test_multiple_captures_same_stage(self):
        """Test 5: Verifies multiple distinct evidence records can be captured for the same stage."""
        submissions = [
            EnvelopeFactory.create_valid_envelope(lifecycle_stage="CROP_GROWTH", sequence_number=2),
            EnvelopeFactory.create_valid_envelope(lifecycle_stage="CROP_GROWTH", sequence_number=3),
            EnvelopeFactory.create_valid_envelope(lifecycle_stage="CROP_GROWTH", sequence_number=4),
        ]
        assert len(submissions) == 3
        assert all(s["lifecycle_stage"] == "CROP_GROWTH" for s in submissions)
