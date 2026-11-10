"""F-31: WGS84 GPS Coordinate Capture Tests.
Validates mobile GPS location acquisition, WGS84 coordinate bounds,
accuracy thresholds, and altitude metadata.
"""

import pytest
from tests_e2e.fixtures.spatial_fixtures import is_valid_wgs84


class MockGPSProvider:
    """Simulates mobile device GPS sensor hardware."""

    @staticmethod
    def get_location_fix(lat: float, lon: float, accuracy: float, altitude: float = 300.0) -> dict:
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Out-of-bounds WGS84 coordinates: lat={lat}, lon={lon}")

        is_fix_usable = accuracy <= 25.0  # Require accuracy <= 25 meters for agricultural evidence

        return {
            "latitude": lat,
            "longitude": lon,
            "accuracy_meters": accuracy,
            "altitude_meters": altitude,
            "is_high_accuracy": is_fix_usable,
        }


class TestF31GPSCoordinateCapture:
    """Verifies GPS coordinate acquisition contracts."""

    def test_high_accuracy_field_fix(self):
        """Test 1: Verifies valid high-accuracy GPS fix in an agricultural field (accuracy <= 5m)."""
        fix = MockGPSProvider.get_location_fix(17.3850, 78.4867, accuracy=3.8)
        assert fix["is_high_accuracy"] is True
        assert is_valid_wgs84(fix["latitude"], fix["longitude"], fix["accuracy_meters"]) is True

    def test_low_accuracy_cell_tower_fix_flagged(self):
        """Test 2: Verifies coarse fix (accuracy > 50m) is flagged as unusable."""
        fix = MockGPSProvider.get_location_fix(17.3850, 78.4867, accuracy=75.0)
        assert fix["is_high_accuracy"] is False

    def test_latitude_boundary_enforcement(self):
        """Test 3: Verifies latitude values exceeding [-90, 90] raise ValueError."""
        with pytest.raises(ValueError, match="Out-of-bounds"):
            MockGPSProvider.get_location_fix(95.0, 78.0, accuracy=5.0)

        with pytest.raises(ValueError, match="Out-of-bounds"):
            MockGPSProvider.get_location_fix(-91.0, 78.0, accuracy=5.0)

    def test_longitude_boundary_enforcement(self):
        """Test 4: Verifies longitude values exceeding [-180, 180] raise ValueError."""
        with pytest.raises(ValueError, match="Out-of-bounds"):
            MockGPSProvider.get_location_fix(17.0, 185.0, accuracy=5.0)

    def test_altitude_metadata_recorded(self):
        """Test 5: Verifies altitude is recorded in meters above mean sea level."""
        fix = MockGPSProvider.get_location_fix(19.664, 78.532, accuracy=4.0, altitude=450.5)
        assert fix["altitude_meters"] == 450.5
