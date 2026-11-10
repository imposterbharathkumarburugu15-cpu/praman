import pytest
import math
from backend.app.services.spatial import (
    validate_farm_polygon,
    calculate_wgs84_geodesic_area_sq_meters,
    calculate_farm_area_acres,
    calculate_polygon_area_hectares,
    calculate_farm_area_hectares,
    validate_declared_area,
    is_valid_wgs84,
    M2_PER_ACRE,
    M2_PER_HECTARE,
)


def test_valid_farm_polygon():
    # Valid 4-vertex closed polygon in Adilabad, Telangana
    polygon = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6615, 78.5325),
        (19.6640, 78.5320),
    ]
    is_valid, msg = validate_farm_polygon(polygon)
    assert is_valid is True
    assert msg == "Valid polygon"

    area = calculate_farm_area_hectares(polygon)
    assert area > 0.0


def test_reject_self_intersecting_bowtie():
    # Bowtie self-intersecting polygon
    bowtie = [
        (19.660, 78.530),
        (19.665, 78.535),
        (19.660, 78.535),
        (19.665, 78.530),
        (19.660, 78.530),
    ]
    is_valid, msg = validate_farm_polygon(bowtie)
    assert is_valid is False
    assert "self-intersecting" in msg


def test_reject_insufficient_vertices():
    # Only 2 vertices
    too_few = [
        (19.660, 78.530),
        (19.661, 78.531),
    ]
    is_valid, msg = validate_farm_polygon(too_few)
    assert is_valid is False
    assert "at least 3 vertices" in msg


def test_reject_collinear_degenerate_zero_area():
    # 3 collinear points
    collinear = [
        (19.660, 78.530),
        (19.661, 78.531),
        (19.662, 78.532),
        (19.660, 78.530),
    ]
    is_valid, msg = validate_farm_polygon(collinear)
    assert is_valid is False
    assert "zero or degenerate area" in msg


def test_reject_out_of_bounds_coordinates():
    # Latitude > 90
    bad_lat = [
        (95.0, 78.530),
        (95.1, 78.535),
        (95.0, 78.535),
        (95.0, 78.530),
    ]
    is_valid, msg = validate_farm_polygon(bad_lat)
    assert is_valid is False
    assert "Invalid WGS84 coordinate" in msg


def test_unclosed_polygon_normalization():
    # 3 unclosed points (should be normalized by closing first == last)
    unclosed = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
    ]
    is_valid, msg = validate_farm_polygon(unclosed)
    assert is_valid is True


def test_reject_consecutive_duplicate_vertices():
    # Consecutive identical points (zero-length edge)
    dup_consecutive = [
        (19.6640, 78.5320),
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6640, 78.5320),
    ]
    is_valid, msg = validate_farm_polygon(dup_consecutive)
    assert is_valid is False
    assert "Duplicate consecutive vertex" in msg


def test_reject_unclosed_duplicate_vertices():
    # Unclosed points with non-consecutive duplicates
    dup_unclosed = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6640, 78.5320),
        (19.6620, 78.5360),
    ]
    is_valid, msg = validate_farm_polygon(dup_unclosed)
    assert is_valid is False
    assert "Duplicate" in msg


def test_wgs84_geodesic_area_accuracy_and_conversion():
    # Standard agricultural parcel
    polygon = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6615, 78.5325),
        (19.6640, 78.5320),
    ]
    sq_meters = calculate_wgs84_geodesic_area_sq_meters(polygon)
    acres = calculate_farm_area_acres(polygon)
    hectares = calculate_polygon_area_hectares(polygon)

    # Sanity checks on area scale
    assert sq_meters > 90000.0 and sq_meters < 110000.0  # ~98,675 m^2
    assert math.isclose(acres, sq_meters / M2_PER_ACRE, rel_tol=1e-5)
    assert math.isclose(hectares, sq_meters / M2_PER_HECTARE, rel_tol=1e-3)
    assert acres > 20.0 and acres < 30.0  # ~24.38 acres


def test_declared_area_validation():
    # Calculate for a parcel
    polygon = [
        (19.6640, 78.5320),
        (19.6645, 78.5350),
        (19.6620, 78.5360),
        (19.6615, 78.5325),
        (19.6640, 78.5320),
    ]
    sq_meters = calculate_wgs84_geodesic_area_sq_meters(polygon)
    # Geodesic area is ~24.38 acres

    # Test 1: Within tolerance (declared 24.0 acres, ~1.5% difference)
    is_ok, msg, details = validate_declared_area(sq_meters, 24.0, declared_unit="acres", tolerance_pct=25.0)
    assert is_ok is True
    assert details["is_within_tolerance"] is True
    assert details["percentage_difference"] < 25.0

    # Test 2: Outside tolerance (declared 5.0 acres when actual is 24.38 acres)
    is_ok, msg, details = validate_declared_area(sq_meters, 5.0, declared_unit="acres", tolerance_pct=25.0)
    assert is_ok is False
    assert details["is_within_tolerance"] is False
    assert "Discrepancy" in msg

    # Test 3: Unit conversion check with hectares (declared 9.8 ha vs ~9.86 ha)
    is_ok, msg, details = validate_declared_area(sq_meters, 9.8, declared_unit="hectares", tolerance_pct=10.0)
    assert is_ok is True

    # Test 4: Invalid/negative declared area rejected
    is_ok, msg, _ = validate_declared_area(sq_meters, -2.0, declared_unit="acres")
    assert is_ok is False
    assert "strictly positive" in msg


def test_reject_closed_pinch_point_polygon():
    # Pre-closed polygon with internal repeated vertex (pinch-point / figure-8)
    pinch_closed = [
        (17.380, 78.480),
        (17.385, 78.485),
        (17.390, 78.480),
        (17.385, 78.475),
        (17.385, 78.485),  # duplicate non-consecutive
        (17.380, 78.480),  # explicit closure
    ]
    is_valid, msg = validate_farm_polygon(pinch_closed)
    assert is_valid is False
    assert "Duplicate non-consecutive vertex" in msg


def test_validate_vertex_accuracy_boundaries():
    base_polygon = [
        {"latitude": 17.380, "longitude": 78.480, "accuracy": 5.0},
        {"latitude": 17.390, "longitude": 78.480, "accuracy": 3.0},
        {"latitude": 17.390, "longitude": 78.490, "accuracy": 4.0},
        {"latitude": 17.380, "longitude": 78.490, "accuracy": 2.5},
    ]
    is_valid, msg = validate_farm_polygon(base_polygon)
    assert is_valid is True

    # Negative accuracy
    bad_acc_neg = [dict(v) for v in base_polygon]
    bad_acc_neg[0]["accuracy"] = -50.0
    is_valid, msg = validate_farm_polygon(bad_acc_neg)
    assert is_valid is False
    assert "horizontal accuracy" in msg

    # Zero accuracy
    bad_acc_zero = [dict(v) for v in base_polygon]
    bad_acc_zero[0]["accuracy"] = 0.0
    is_valid, msg = validate_farm_polygon(bad_acc_zero)
    assert is_valid is False
    assert "horizontal accuracy" in msg

    # Excessive accuracy (> 500m)
    bad_acc_excess = [dict(v) for v in base_polygon]
    bad_acc_excess[0]["accuracy"] = 501.0
    is_valid, msg = validate_farm_polygon(bad_acc_excess)
    assert is_valid is False
    assert "horizontal accuracy" in msg
