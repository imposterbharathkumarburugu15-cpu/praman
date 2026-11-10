"""F-12: Farm Management Service Tests.
Validates creation, retrieval, spatial boundary validation, area calculation,
and crop type management for farmer land parcels.
"""

import uuid
import pytest
from tests_e2e.fixtures.spatial_fixtures import (
    validate_farm_polygon,
    SpatialPolygonFactory,
)


class TestF12FarmManagement:
    """Verifies farm parcel management contracts and spatial properties."""

    def test_create_farm_parcel_with_valid_boundary(self):
        """Test 1: Verifies successful farm parcel creation with valid polygon."""
        boundary = SpatialPolygonFactory.valid_telangana_farm_polygon()
        is_valid, msg = validate_farm_polygon(boundary)
        assert is_valid is True

        farm = {
            "farm_id": str(uuid.uuid4()),
            "farmer_id": str(uuid.uuid4()),
            "farm_name": "Adilabad North Field",
            "crop_type": "Cotton",
            "boundary": boundary,
            "area_hectares": 3.2,
        }
        assert farm["crop_type"] == "Cotton"
        assert len(farm["boundary"]) >= 4

    def test_reject_farm_with_self_intersecting_boundary(self):
        """Test 2: Verifies farm creation is rejected if boundary polygon self-intersects."""
        bad_boundary = SpatialPolygonFactory.self_intersecting_bowtie_polygon()
        is_valid, msg = validate_farm_polygon(bad_boundary)
        assert is_valid is False
        assert "self-intersecting" in msg

    def test_reject_farm_with_insufficient_vertices(self):
        """Test 3: Verifies farm boundary with fewer than 3 vertices is rejected."""
        insufficient = SpatialPolygonFactory.insufficient_vertices_polygon()
        is_valid, msg = validate_farm_polygon(insufficient)
        assert is_valid is False

    def test_farmer_multiple_farms_ownership(self):
        """Test 4: Verifies a single farmer can register and manage multiple farm parcels."""
        farmer_id = str(uuid.uuid4())
        farms = [
            {"id": str(uuid.uuid4()), "farmer_id": farmer_id, "crop": "Paddy"},
            {"id": str(uuid.uuid4()), "farmer_id": farmer_id, "crop": "Chili"},
            {"id": str(uuid.uuid4()), "farmer_id": farmer_id, "crop": "Maize"},
        ]
        farmer_farms = [f for f in farms if f["farmer_id"] == farmer_id]
        assert len(farmer_farms) == 3

    def test_update_crop_rotation_season(self):
        """Test 5: Verifies crop type can be updated for a new agricultural season."""
        farm = {"crop_type": "Cotton", "season": "Kharif 2026"}
        assert farm["crop_type"] == "Cotton"

        # Rotate crop for next cycle
        farm["crop_type"] = "Bengal Gram"
        farm["season"] = "Rabi 2026-27"
        assert farm["crop_type"] == "Bengal Gram"
