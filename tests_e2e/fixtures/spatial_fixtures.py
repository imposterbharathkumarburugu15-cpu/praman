"""Spatial fixtures and geometry validation oracles for PRAMAN E2E testing.
Covers WGS84 coordinates, boundary polygon closure, minimum vertex count,
and non-self-intersection algorithms.
"""

from typing import List, Tuple, Dict, Any

# Import genuine spatial algorithms from the backend production service
from backend.app.services.spatial import (
    is_valid_wgs84,
    segments_intersect,
    validate_farm_polygon,
    calculate_polygon_area_hectares,
    calculate_farm_area_hectares,
)


class SpatialPolygonFactory:
    """Generates standard valid and invalid polygons for test cases."""

    @staticmethod
    def valid_telangana_farm_polygon() -> List[Tuple[float, float]]:
        """A valid 4-vertex quadrilateral farm boundary in Adilabad, Telangana."""
        return [
            (19.6640, 78.5320),
            (19.6645, 78.5350),
            (19.6620, 78.5360),
            (19.6615, 78.5325),
            (19.6640, 78.5320),  # Closed
        ]

    @staticmethod
    def self_intersecting_bowtie_polygon() -> List[Tuple[float, float]]:
        """A self-intersecting 'bow-tie' polygon that MUST be rejected."""
        return [
            (19.660, 78.530),
            (19.665, 78.535),
            (19.660, 78.535),
            (19.665, 78.530),
            (19.660, 78.530),
        ]

    @staticmethod
    def collinear_degenerate_polygon() -> List[Tuple[float, float]]:
        """Three collinear points with zero area."""
        return [
            (19.660, 78.530),
            (19.661, 78.531),
            (19.662, 78.532),
            (19.660, 78.530),
        ]

    @staticmethod
    def insufficient_vertices_polygon() -> List[Tuple[float, float]]:
        """Only two distinct points."""
        return [
            (19.660, 78.530),
            (19.661, 78.531),
            (19.660, 78.530),
        ]
