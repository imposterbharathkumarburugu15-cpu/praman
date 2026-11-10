"""Tier 2: Spatial & Boundary Coordinate Tests.
Tests polar coordinates (+-90.0), anti-meridian (+-180.0), minimal triangle parcels,
and extreme spatial boundary cases.
"""

import pytest
from tests_e2e.fixtures.spatial_fixtures import (
    is_valid_wgs84,
    validate_farm_polygon,
)


class TestB03SpatialBoundaries:
    """Verifies geographic boundary coordinates and polygon edge cases."""

    def test_exact_poles_and_equator(self):
        """Boundary 1: Verifies exact boundary values of latitude: +90.0, -90.0, and 0.0."""
        assert is_valid_wgs84(90.0, 0.0) is True   # North Pole
        assert is_valid_wgs84(-90.0, 0.0) is True  # South Pole
        assert is_valid_wgs84(0.0, 0.0) is True    # Equator & Prime Meridian

        # 1 milli-degree beyond limits
        assert is_valid_wgs84(90.0001, 0.0) is False
        assert is_valid_wgs84(-90.0001, 0.0) is False

    def test_anti_meridian_boundaries(self):
        """Boundary 2: Verifies anti-meridian boundaries (+-180.0)."""
        assert is_valid_wgs84(17.0, 180.0) is True
        assert is_valid_wgs84(17.0, -180.0) is True

        assert is_valid_wgs84(17.0, 180.0001) is False
        assert is_valid_wgs84(17.0, -180.0001) is False

    def test_minimal_three_vertex_triangle_polygon(self):
        """Boundary 3: Verifies minimal valid farm boundary (triangle with exactly 3 vertices)."""
        triangle = [
            (17.380, 78.480),
            (17.385, 78.485),
            (17.380, 78.490),
            (17.380, 78.480),
        ]
        is_valid, msg = validate_farm_polygon(triangle)
        assert is_valid is True
        assert msg == "Valid polygon"

    def test_all_identical_vertices_rejected(self):
        """Boundary 4: Verifies degenerate polygon with all identical points is rejected."""
        all_same = [
            (17.380, 78.480),
            (17.380, 78.480),
            (17.380, 78.480),
            (17.380, 78.480),
        ]
        is_valid, msg = validate_farm_polygon(all_same)
        assert is_valid is False
        assert "distinct coordinates" in msg or "zero or degenerate area" in msg

    def test_extreme_precision_coordinates(self):
        """Boundary 5: Verifies high-precision 7-decimal place coordinates (~1cm precision) are accepted."""
        lat = 17.3850441
        lon = 78.4866719
        assert is_valid_wgs84(lat, lon, accuracy=0.5) is True
