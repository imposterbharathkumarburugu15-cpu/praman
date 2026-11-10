"""PRAMAN E2E test fixtures package."""

from .crypto_fixtures import (
    rfc8785_canonicalize,
    generate_p256_keypair,
    sign_p256_der,
    verify_p256_der,
    ReferenceMerkleTree,
)
from .image_generator import (
    SyntheticImageGenerator,
    compute_laplacian_variance,
    compute_luminance_clipping,
    compute_phash_64,
    compute_dhash_64,
    hamming_distance_hex,
)
from .envelope_fixtures import EnvelopeFactory, VALID_LIFECYCLE_STAGES
from .spatial_fixtures import (
    is_valid_wgs84,
    validate_farm_polygon,
    SpatialPolygonFactory,
)

__all__ = [
    "rfc8785_canonicalize",
    "generate_p256_keypair",
    "sign_p256_der",
    "verify_p256_der",
    "ReferenceMerkleTree",
    "SyntheticImageGenerator",
    "compute_laplacian_variance",
    "compute_luminance_clipping",
    "compute_phash_64",
    "compute_dhash_64",
    "hamming_distance_hex",
    "EnvelopeFactory",
    "VALID_LIFECYCLE_STAGES",
    "is_valid_wgs84",
    "validate_farm_polygon",
    "SpatialPolygonFactory",
]
