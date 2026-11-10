"""ADV-01: GPS & Spatial Spoofing Adversarial Tests.
Verifies resistance against:
1. Out-of-bounds coordinates (latitude > 90, latitude < -90, longitude > 180, longitude < -180).
2. Non-finite floating point injections (NaN, +Inf, -Inf).
3. Degenerate and anomalous GPS accuracy boundaries.
4. Self-intersecting polygons (bow-tie, figure-eight).
5. Collinear zero-area degenerate polygons.
6. Polygon vertex exhaustion (< 3 distinct points).
7. Coordinates outside registered farm polygon boundaries (spatial boundary violation).
8. Polygon auto-closure and acreage computation under adversarial geometries.
"""

import math
import pytest
from typing import List, Tuple
from backend.app.services.spatial import (
    is_valid_wgs84,
    validate_farm_polygon,
    calculate_polygon_area_hectares,
    segments_intersect,
)
from tests_e2e.fixtures.spatial_fixtures import SpatialPolygonFactory


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Ray-casting algorithm to test whether a point (lat, lon) is inside a polygon.
    Polygon is list of (lat, lon) tuples.
    """
    lat, lon = point
    n = len(polygon)
    inside = False

    p1_lat, p1_lon = polygon[0]
    for i in range(1, n + 1):
        p2_lat, p2_lon = polygon[i % n]
        if lon > min(p1_lon, p2_lon):
            if lon <= max(p1_lon, p2_lon):
                if lat <= max(p1_lat, p2_lat):
                    if p1_lon != p2_lon:
                        lat_inters = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat
                    if p1_lat == p2_lat or lat <= lat_inters:
                        inside = not inside
        p1_lat, p1_lon = p2_lat, p2_lon

    return inside


class TestAdv01GPSSpatialSpoofing:
    """Adversarial test suite for GPS and spatial boundary attacks."""

    def test_out_of_bounds_latitude_spoofing(self):
        """ADV-01.1: Rejects adversarial latitude injections beyond [-90, +90]."""
        invalid_latitudes = [90.000001, 91.0, 180.0, 999.99, -90.00001, -91.0, -180.0, -999.99]
        for lat in invalid_latitudes:
            assert is_valid_wgs84(lat=lat, lon=78.5320, accuracy=5.0) is False, (
                f"Latitude {lat} should have been rejected as out-of-bounds"
            )

    def test_out_of_bounds_longitude_spoofing(self):
        """ADV-01.2: Rejects adversarial longitude injections beyond [-180, +180]."""
        invalid_longitudes = [180.000001, 181.0, 270.0, 360.0, -180.00001, -181.0, -270.0, -999.0]
        for lon in invalid_longitudes:
            assert is_valid_wgs84(lat=19.6640, lon=lon, accuracy=5.0) is False, (
                f"Longitude {lon} should have been rejected as out-of-bounds"
            )

    def test_nan_and_inf_coordinate_injection(self):
        """ADV-01.3: Rejects NaN and Inf float injections attempting IEEE 754 bypass."""
        non_finite_values = [float("nan"), float("inf"), float("-inf"), math.nan, math.inf, -math.inf]
        for bad_val in non_finite_values:
            assert is_valid_wgs84(lat=bad_val, lon=78.5320, accuracy=5.0) is False
            assert is_valid_wgs84(lat=19.6640, lon=bad_val, accuracy=5.0) is False
            assert is_valid_wgs84(lat=bad_val, lon=bad_val, accuracy=5.0) is False

    def test_anomalous_gps_accuracy_tampering(self):
        """ADV-01.4: Rejects anomalous GPS accuracy values (<= 0m or > 100m)."""
        bad_accuracies = [0.0, -0.001, -10.0, -100.0, 100.01, 500.0, 10000.0, float("inf")]
        for acc in bad_accuracies:
            assert is_valid_wgs84(lat=19.6640, lon=78.5320, accuracy=acc) is False

    def test_self_intersecting_bowtie_polygon_rejected(self):
        """ADV-01.5: Rejects self-intersecting bow-tie polygon injection."""
        bowtie = SpatialPolygonFactory.self_intersecting_bowtie_polygon()
        is_valid, reason = validate_farm_polygon(bowtie)
        assert is_valid is False
        assert "self-intersecting" in reason.lower()

    def test_collinear_degenerate_zero_area_polygon_rejected(self):
        """ADV-01.6: Rejects collinear degenerate polygon with zero area."""
        collinear = SpatialPolygonFactory.collinear_degenerate_polygon()
        is_valid, reason = validate_farm_polygon(collinear)
        assert is_valid is False
        assert "zero or degenerate area" in reason.lower()

    def test_insufficient_vertices_polygon_rejected(self):
        """ADV-01.7: Rejects polygons with fewer than 3 unique vertices."""
        insufficient = SpatialPolygonFactory.insufficient_vertices_polygon()
        is_valid, reason = validate_farm_polygon(insufficient)
        assert is_valid is False
        assert "coordinates" in reason.lower() or "unique vertices" in reason.lower()

    def test_polygon_with_invalid_wgs84_vertices_rejected(self):
        """ADV-01.8: Rejects polygon containing out-of-bounds WGS84 vertices."""
        bad_poly = [
            (19.6640, 78.5320),
            (95.0000, 78.5350),  # Lat > 90
            (19.6620, 78.5360),
            (19.6640, 78.5320),
        ]
        is_valid, reason = validate_farm_polygon(bad_poly)
        assert is_valid is False
        assert "invalid wgs84" in reason.lower()

    def test_spatial_boundary_containment_violation(self):
        """ADV-01.9: Detects evidence capture location outside registered farm polygon."""
        farm_poly = SpatialPolygonFactory.valid_telangana_farm_polygon()
        
        # Point inside farm (center of Adilabad farm)
        inside_point = (19.6630, 78.5340)
        assert point_in_polygon(inside_point, farm_poly) is True

        # Adversary claims capture from Paris, London, or Hyderabad (outside Adilabad farm)
        spoofed_points = [
            (17.3850, 78.4867),   # Hyderabad (~250km south)
            (28.6139, 77.2090),   # New Delhi (~1200km north)
            (48.8566, 2.3522),    # Paris (~7000km away)
            (19.6900, 78.5320),   # Just 3km outside boundary
        ]
        for pt in spoofed_points:
            assert point_in_polygon(pt, farm_poly) is False, (
                f"Point {pt} should be detected as OUTSIDE farm polygon"
            )

    def test_valid_polygon_closure_and_acreage(self):
        """ADV-01.10: Verifies valid farm polygon passes and calculates accurate ground area."""
        valid_poly = SpatialPolygonFactory.valid_telangana_farm_polygon()
        is_valid, reason = validate_farm_polygon(valid_poly)
        assert is_valid is True
        assert reason == "Valid polygon"

        area_ha = calculate_polygon_area_hectares(valid_poly)
        assert 0.1 <= area_ha <= 20.0, f"Expected realistic farm area, got {area_ha} ha"
