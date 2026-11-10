"""F-32: Farm Boundary Polygon Capture & Validator Tests.
Validates mobile polygon capture, explicit closure, vertex count thresholds,
and self-intersection rejection algorithms.
"""

import pytest
from tests_e2e.fixtures.spatial_fixtures import (
    validate_farm_polygon,
    SpatialPolygonFactory,
)


class TestF32BoundaryPolygonCapture:
    """Verifies boundary polygon validation and capture rules."""

    def test_valid_quadrilateral_boundary(self):
        """Test 1: Verifies standard 4-point quadrilateral farm boundary is valid."""
        poly = SpatialPolygonFactory.valid_telangana_farm_polygon()
        valid, msg = validate_farm_polygon(poly)
        assert valid is True
        assert msg == "Valid polygon"

    def test_bowtie_self_intersecting_polygon_rejected(self):
        """Test 2: Verifies self-intersecting 'bow-tie' polygon is rejected."""
        poly = SpatialPolygonFactory.self_intersecting_bowtie_polygon()
        valid, msg = validate_farm_polygon(poly)
        assert valid is False
        assert "self-intersecting" in msg

    def test_two_point_polygon_rejected(self):
        """Test 3: Verifies boundary with only 2 points is rejected for insufficient vertices."""
        poly = [(19.0, 78.0), (19.1, 78.1), (19.0, 78.0)]
        valid, msg = validate_farm_polygon(poly)
        assert valid is False
        assert "at least 4 coordinates" in msg

    def test_automatic_closure_of_unclosed_vertices(self):
        """Test 4: Verifies an unclosed polygon ([A, B, C]) is automatically closed to ([A, B, C, A])."""
        unclosed = [(19.660, 78.530), (19.665, 78.535), (19.660, 78.535)]
        valid, msg = validate_farm_polygon(unclosed)
        assert valid is True

    def test_collinear_zero_area_polygon_rejected(self):
        """Test 5: Verifies degenerate collinear points with zero area are rejected."""
        collinear = SpatialPolygonFactory.collinear_degenerate_polygon()
        valid, msg = validate_farm_polygon(collinear)
        assert valid is False
        assert "zero or degenerate area" in msg
