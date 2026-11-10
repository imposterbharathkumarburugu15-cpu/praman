import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.farmer import Farmer
from backend.app.models.farm import Farm
from backend.app.models.boundary_vertex import BoundaryVertex
from backend.app.models.boundary_history import BoundaryHistory
from backend.app.schemas.farm import (
    FarmCreate,
    FarmUpdate,
    FarmResponse,
    BoundaryVertexCreate,
    BoundaryVertexResponse,
    BoundaryHistoryResponse,
)
from backend.app.services.spatial import (
    validate_farm_polygon,
    calculate_wgs84_geodesic_area_sq_meters,
    calculate_farm_area_acres,
    calculate_polygon_area_hectares,
    validate_declared_area,
)
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/farms", tags=["Farms"])


def _parse_timestamp(ts: Optional[Union[datetime, str]]) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _extract_coordinates_from_payload(
    vertices: Optional[List[BoundaryVertexCreate]] = None,
    boundary_polygon: Optional[Union[List[Tuple[float, float]], List[List[float]]]] = None,
    boundary_geojson: Optional[Union[str, Dict[str, Any]]] = None,
) -> Tuple[List[Tuple[float, float]], Optional[str]]:
    """Extracts raw (lat, lon) coordinates from any of the three supported input formats."""
    # 1. Individual vertex records
    if vertices and len(vertices) > 0:
        sorted_vertices = sorted(
            vertices,
            key=lambda v: v.vertex_sequence if v.vertex_sequence is not None else 0,
        )
        coords = [(v.latitude, v.longitude) for v in sorted_vertices]
        return coords, None

    # 2. Coordinate list (boundary_polygon)
    if boundary_polygon and len(boundary_polygon) > 0:
        coords = [(float(pt[0]), float(pt[1])) for pt in boundary_polygon]
        return coords, None

    # 3. GeoJSON string or dict (boundary_geojson)
    if boundary_geojson:
        if isinstance(boundary_geojson, dict):
            parsed_geo = boundary_geojson
        else:
            try:
                parsed_geo = json.loads(boundary_geojson)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="boundary_geojson must be valid JSON",
                )

        if isinstance(parsed_geo, dict) and parsed_geo.get("type") == "Polygon" and "coordinates" in parsed_geo:
            raw_coords = parsed_geo["coordinates"][0]
            # GeoJSON coordinates are [lon, lat], spatial coordinates are (lat, lon)
            coords = [(float(pt[1]), float(pt[0])) for pt in raw_coords]
            return coords, json.dumps(parsed_geo)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="GeoJSON must be a Polygon with valid coordinates",
            )

    return [], None


def _build_geojson_string(coords: List[Tuple[float, float]]) -> str:
    """Creates a standard GeoJSON Polygon string [[[lon, lat], ...]] with explicit closure."""
    closed_coords = list(coords)
    if closed_coords[0] != closed_coords[-1]:
        closed_coords.append(closed_coords[0])
    return json.dumps({
        "type": "Polygon",
        "coordinates": [[[pt[1], pt[0]] for pt in closed_coords]],
    })


@router.post("", response_model=FarmResponse, status_code=status.HTTP_201_CREATED)
def create_farm(payload: FarmCreate, db: Session = Depends(get_db)):
    """Creates a new farm parcel with WGS84 geodesic area calculation, polygon validation,
    vertex records persistence, and optional farmer declared area reconciliation.
    """
    # 1. Validate farmer exists
    farmer = db.query(Farmer).filter(Farmer.id == payload.farmer_id).first()
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer {payload.farmer_id} not found",
        )

    # 2. Extract coordinates
    coords, passed_geojson_str = _extract_coordinates_from_payload(
        vertices=payload.vertices,
        boundary_polygon=payload.boundary_polygon,
        boundary_geojson=payload.boundary_geojson,
    )
    if not coords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Boundary geometry must be provided (vertices, boundary_polygon, or boundary_geojson)",
        )

    # 3. Spatial validation
    is_valid, msg = validate_farm_polygon(coords)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid boundary polygon: {msg}",
        )

    # 4. Genuine WGS84 Geodesic calculations
    area_sq_meters = calculate_wgs84_geodesic_area_sq_meters(coords)
    area_acres = calculate_farm_area_acres(coords)
    area_ha = calculate_polygon_area_hectares(coords)

    # 5. Declared area validation if provided
    validation_info: Dict[str, Any] = {
        "is_valid": True,
        "geodesic_area_sq_meters": round(area_sq_meters, 2),
        "geodesic_area_acres": round(area_acres, 4),
        "geodesic_area_hectares": round(area_ha, 4),
        "polygon_status": "VALID",
    }
    if payload.declared_area is not None and payload.declared_area > 0.0:
        declared_unit = payload.declared_area_unit or "acres"
        is_tol, tol_msg, tol_details = validate_declared_area(
            calculated_sq_meters=area_sq_meters,
            declared_area=payload.declared_area,
            declared_unit=declared_unit,
        )
        validation_info["declared_area_check"] = tol_details
        validation_info["declared_area_reconciled"] = is_tol

    geojson_str = passed_geojson_str or _build_geojson_string(coords)
    farm_name = payload.farm_name or payload.name or "Farm Parcel"
    farm_id = payload.id or str(uuid.uuid4())

    # 6. Persist Farm record
    farm = Farm(
        id=farm_id,
        farmer_id=payload.farmer_id,
        farm_name=farm_name,
        crop_type=payload.crop_type,
        boundary_geojson=geojson_str,
        boundary_version=payload.boundary_version or 1,
        crs=payload.crs or "EPSG:4326",
        area_sq_meters=area_sq_meters,
        area_acres=area_acres,
        area_hectares=area_ha,
        is_valid=True,
        validation_details=json.dumps(validation_info),
        season=payload.season,
        district=payload.district,
        state=payload.state,
    )
    db.add(farm)

    # 7. Persist BoundaryVertex records
    vertex_records: List[BoundaryVertex] = []
    if payload.vertices and len(payload.vertices) > 0:
        for idx, v in enumerate(payload.vertices):
            seq = v.vertex_sequence if v.vertex_sequence is not None else idx + 1
            v_record = BoundaryVertex(
                id=str(uuid.uuid4()),
                farm_id=farm.id,
                boundary_version=farm.boundary_version,
                latitude=v.latitude,
                longitude=v.longitude,
                horizontal_accuracy=v.horizontal_accuracy or 5.0,
                observation_timestamp=_parse_timestamp(v.observation_timestamp),
                collection_method=v.collection_method or "WALK_AND_MARK",
                vertex_sequence=seq,
            )
            db.add(v_record)
            vertex_records.append(v_record)
    else:
        # Auto-create vertex records from coordinate list (excluding trailing closure duplicate)
        non_closed = coords[:-1] if (len(coords) >= 4 and coords[0] == coords[-1]) else coords
        for idx, pt in enumerate(non_closed):
            v_record = BoundaryVertex(
                id=str(uuid.uuid4()),
                farm_id=farm.id,
                boundary_version=farm.boundary_version,
                latitude=pt[0],
                longitude=pt[1],
                horizontal_accuracy=5.0,
                observation_timestamp=datetime.now(timezone.utc),
                collection_method="COORDINATE_INPUT",
                vertex_sequence=idx + 1,
            )
            db.add(v_record)
            vertex_records.append(v_record)

    db.commit()
    db.refresh(farm)

    # 8. Audit log event
    AuditService.log_event(
        db=db,
        event_type="FARM_CREATED",
        entity_type="FARM",
        entity_id=farm.id,
        actor_id=farm.farmer_id,
        new_state="ACTIVE",
        payload=f"{farm.farm_name}:{farm.crop_type}:{farm.area_sq_meters:.2f}m2:{farm.area_acres:.2f}ac".encode("utf-8"),
    )

    vertex_responses = [
        BoundaryVertexResponse(
            id=v.id,
            farm_id=v.farm_id,
            boundary_version=v.boundary_version,
            latitude=v.latitude,
            longitude=v.longitude,
            horizontal_accuracy=v.horizontal_accuracy,
            observation_timestamp=v.observation_timestamp,
            collection_method=v.collection_method,
            vertex_sequence=v.vertex_sequence,
            created_at=v.created_at,
        )
        for v in sorted(vertex_records, key=lambda x: x.vertex_sequence)
    ]

    return FarmResponse(
        id=farm.id,
        farm_id=farm.id,
        farmer_id=farm.farmer_id,
        farm_name=farm.farm_name,
        name=farm.farm_name,
        crop_type=farm.crop_type,
        boundary_geojson=farm.boundary_geojson,
        boundary_version=farm.boundary_version,
        crs=farm.crs,
        area_sq_meters=farm.area_sq_meters,
        area_acres=farm.area_acres,
        area_hectares=farm.area_hectares,
        is_valid=farm.is_valid,
        validation_details=farm.validation_details,
        season=farm.season,
        district=farm.district,
        state=farm.state,
        vertices=vertex_responses,
        created_at=farm.created_at,
        updated_at=farm.updated_at,
    )


@router.get("/{farm_id}", response_model=FarmResponse)
def get_farm(farm_id: str, db: Session = Depends(get_db)):
    """Retrieves full farm parcel details including current vertices, boundary version, and geodesic areas."""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    vertices = (
        db.query(BoundaryVertex)
        .filter(
            BoundaryVertex.farm_id == farm_id,
            BoundaryVertex.boundary_version == farm.boundary_version,
        )
        .order_by(BoundaryVertex.vertex_sequence)
        .all()
    )

    vertex_responses = [
        BoundaryVertexResponse(
            id=v.id,
            farm_id=v.farm_id,
            boundary_version=v.boundary_version,
            latitude=v.latitude,
            longitude=v.longitude,
            horizontal_accuracy=v.horizontal_accuracy,
            observation_timestamp=v.observation_timestamp,
            collection_method=v.collection_method,
            vertex_sequence=v.vertex_sequence,
            created_at=v.created_at,
        )
        for v in vertices
    ]

    return FarmResponse(
        id=farm.id,
        farm_id=farm.id,
        farmer_id=farm.farmer_id,
        farm_name=farm.farm_name,
        name=farm.farm_name,
        crop_type=farm.crop_type,
        boundary_geojson=farm.boundary_geojson,
        boundary_version=farm.boundary_version,
        crs=farm.crs,
        area_sq_meters=farm.area_sq_meters,
        area_acres=farm.area_acres,
        area_hectares=farm.area_hectares,
        is_valid=farm.is_valid,
        validation_details=farm.validation_details,
        season=farm.season,
        district=farm.district,
        state=farm.state,
        vertices=vertex_responses,
        created_at=farm.created_at,
        updated_at=farm.updated_at,
    )


@router.patch("/{farm_id}", response_model=FarmResponse)
def update_farm(
    farm_id: str,
    payload: FarmUpdate,
    db: Session = Depends(get_db),
):
    """Updates farm metadata or boundary coordinates. When boundary is updated:
    1. Previous boundary and geodesic metrics are archived to boundary_history.
    2. boundary_version is incremented.
    3. New vertices and recalculated geodesic area (m^2, acres, ha) are persisted.
    4. Audit log event is generated.
    """
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    has_boundary_update = bool(payload.vertices or payload.boundary_polygon or payload.boundary_geojson)

    if has_boundary_update:
        # Extract and validate new coordinates
        coords, passed_geojson_str = _extract_coordinates_from_payload(
            vertices=payload.vertices,
            boundary_polygon=payload.boundary_polygon,
            boundary_geojson=payload.boundary_geojson,
        )
        if not coords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid boundary geometry update payload",
            )

        is_valid, msg = validate_farm_polygon(coords)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid updated boundary polygon: {msg}",
            )

        # 1. Archive current boundary to BoundaryHistory
        history = BoundaryHistory(
            id=str(uuid.uuid4()),
            farm_id=farm.id,
            boundary_version=farm.boundary_version,
            boundary_geojson=farm.boundary_geojson,
            area_sq_meters=farm.area_sq_meters,
            area_acres=farm.area_acres,
            crs=farm.crs,
            validation_details=farm.validation_details,
            superseded_at=datetime.now(timezone.utc),
        )
        db.add(history)

        # 2. Increment boundary_version
        new_version = farm.boundary_version + 1
        farm.boundary_version = new_version

        # 3. Recalculate geodesic areas
        new_area_sq_meters = calculate_wgs84_geodesic_area_sq_meters(coords)
        new_area_acres = calculate_farm_area_acres(coords)
        new_area_ha = calculate_polygon_area_hectares(coords)

        validation_info: Dict[str, Any] = {
            "is_valid": True,
            "geodesic_area_sq_meters": round(new_area_sq_meters, 2),
            "geodesic_area_acres": round(new_area_acres, 4),
            "geodesic_area_hectares": round(new_area_ha, 4),
            "polygon_status": "VALID",
            "supersedes_version": history.boundary_version,
        }
        if payload.declared_area is not None and payload.declared_area > 0.0:
            is_tol, tol_msg, tol_details = validate_declared_area(
                calculated_sq_meters=new_area_sq_meters,
                declared_area=payload.declared_area,
                declared_unit=payload.declared_area_unit or "acres",
            )
            validation_info["declared_area_check"] = tol_details
            validation_info["declared_area_reconciled"] = is_tol

        farm.boundary_geojson = passed_geojson_str or _build_geojson_string(coords)
        farm.area_sq_meters = new_area_sq_meters
        farm.area_acres = new_area_acres
        farm.area_hectares = new_area_ha
        farm.validation_details = json.dumps(validation_info)

        # 4. Save new vertices with incremented version
        if payload.vertices and len(payload.vertices) > 0:
            for idx, v in enumerate(payload.vertices):
                seq = v.vertex_sequence if v.vertex_sequence is not None else idx + 1
                v_record = BoundaryVertex(
                    id=str(uuid.uuid4()),
                    farm_id=farm.id,
                    boundary_version=new_version,
                    latitude=v.latitude,
                    longitude=v.longitude,
                    horizontal_accuracy=v.horizontal_accuracy or 5.0,
                    observation_timestamp=_parse_timestamp(v.observation_timestamp),
                    collection_method=v.collection_method or "WALK_AND_MARK",
                    vertex_sequence=seq,
                )
                db.add(v_record)
        else:
            non_closed = coords[:-1] if (len(coords) >= 4 and coords[0] == coords[-1]) else coords
            for idx, pt in enumerate(non_closed):
                v_record = BoundaryVertex(
                    id=str(uuid.uuid4()),
                    farm_id=farm.id,
                    boundary_version=new_version,
                    latitude=pt[0],
                    longitude=pt[1],
                    horizontal_accuracy=5.0,
                    observation_timestamp=datetime.now(timezone.utc),
                    collection_method="COORDINATE_INPUT",
                    vertex_sequence=idx + 1,
                )
                db.add(v_record)

        AuditService.log_event(
            db=db,
            event_type="FARM_BOUNDARY_UPDATED",
            entity_type="FARM",
            entity_id=farm.id,
            actor_id=farm.farmer_id,
            previous_state=f"v{history.boundary_version}:{history.area_sq_meters:.2f}m2",
            new_state=f"v{new_version}:{farm.area_sq_meters:.2f}m2",
            payload=f"{farm.id}:boundary_updated:v{history.boundary_version}->v{new_version}".encode("utf-8"),
        )

    # Apply metadata updates if provided
    metadata_changed = False
    old_state = f"{farm.farm_name}:{farm.crop_type}"
    if payload.crop_type and payload.crop_type != farm.crop_type:
        farm.crop_type = payload.crop_type
        metadata_changed = True
    new_name = payload.farm_name or payload.name
    if new_name and new_name != farm.farm_name:
        farm.farm_name = new_name
        metadata_changed = True
    if payload.season and payload.season != farm.season:
        farm.season = payload.season
        metadata_changed = True
    if payload.district and payload.district != farm.district:
        farm.district = payload.district
        metadata_changed = True
    if payload.state and payload.state != farm.state:
        farm.state = payload.state
        metadata_changed = True

    if metadata_changed and not has_boundary_update:
        AuditService.log_event(
            db=db,
            event_type="FARM_METADATA_UPDATED",
            entity_type="FARM",
            entity_id=farm.id,
            actor_id=farm.farmer_id,
            previous_state=old_state,
            new_state=f"{farm.farm_name}:{farm.crop_type}",
            payload=f"{farm.id}:{old_state}->{farm.farm_name}:{farm.crop_type}".encode("utf-8"),
        )

    db.commit()
    db.refresh(farm)

    current_vertices = (
        db.query(BoundaryVertex)
        .filter(
            BoundaryVertex.farm_id == farm_id,
            BoundaryVertex.boundary_version == farm.boundary_version,
        )
        .order_by(BoundaryVertex.vertex_sequence)
        .all()
    )

    vertex_responses = [
        BoundaryVertexResponse(
            id=v.id,
            farm_id=v.farm_id,
            boundary_version=v.boundary_version,
            latitude=v.latitude,
            longitude=v.longitude,
            horizontal_accuracy=v.horizontal_accuracy,
            observation_timestamp=v.observation_timestamp,
            collection_method=v.collection_method,
            vertex_sequence=v.vertex_sequence,
            created_at=v.created_at,
        )
        for v in current_vertices
    ]

    return FarmResponse(
        id=farm.id,
        farm_id=farm.id,
        farmer_id=farm.farmer_id,
        farm_name=farm.farm_name,
        name=farm.farm_name,
        crop_type=farm.crop_type,
        boundary_geojson=farm.boundary_geojson,
        boundary_version=farm.boundary_version,
        crs=farm.crs,
        area_sq_meters=farm.area_sq_meters,
        area_acres=farm.area_acres,
        area_hectares=farm.area_hectares,
        is_valid=farm.is_valid,
        validation_details=farm.validation_details,
        season=farm.season,
        district=farm.district,
        state=farm.state,
        vertices=vertex_responses,
        created_at=farm.created_at,
        updated_at=farm.updated_at,
    )


@router.get("/{farm_id}/history", response_model=List[BoundaryHistoryResponse])
def get_farm_boundary_history(farm_id: str, db: Session = Depends(get_db)):
    """Returns historical boundary versions for a farm parcel in reverse chronological order."""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    histories = (
        db.query(BoundaryHistory)
        .filter(BoundaryHistory.farm_id == farm_id)
        .order_by(BoundaryHistory.boundary_version.desc())
        .all()
    )

    return [
        BoundaryHistoryResponse(
            id=h.id,
            farm_id=h.farm_id,
            boundary_version=h.boundary_version,
            boundary_geojson=h.boundary_geojson,
            area_sq_meters=h.area_sq_meters,
            area_acres=h.area_acres,
            crs=h.crs,
            validation_details=h.validation_details,
            superseded_at=h.superseded_at,
        )
        for h in histories
    ]


@router.get("", response_model=List[FarmResponse])
def list_farms(
    farmer_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lists farms, optionally filtered by farmer_id."""
    query = db.query(Farm)
    if farmer_id:
        query = query.filter(Farm.farmer_id == farmer_id)
    farms = query.all()

    results = []
    for f in farms:
        vertices = (
            db.query(BoundaryVertex)
            .filter(
                BoundaryVertex.farm_id == f.id,
                BoundaryVertex.boundary_version == f.boundary_version,
            )
            .order_by(BoundaryVertex.vertex_sequence)
            .all()
        )
        v_responses = [
            BoundaryVertexResponse(
                id=v.id,
                farm_id=v.farm_id,
                boundary_version=v.boundary_version,
                latitude=v.latitude,
                longitude=v.longitude,
                horizontal_accuracy=v.horizontal_accuracy,
                observation_timestamp=v.observation_timestamp,
                collection_method=v.collection_method,
                vertex_sequence=v.vertex_sequence,
                created_at=v.created_at,
            )
            for v in vertices
        ]
        results.append(
            FarmResponse(
                id=f.id,
                farm_id=f.id,
                farmer_id=f.farmer_id,
                farm_name=f.farm_name,
                name=f.farm_name,
                crop_type=f.crop_type,
                boundary_geojson=f.boundary_geojson,
                boundary_version=f.boundary_version,
                crs=f.crs,
                area_sq_meters=f.area_sq_meters,
                area_acres=f.area_acres,
                area_hectares=f.area_hectares,
                is_valid=f.is_valid,
                validation_details=f.validation_details,
                season=f.season,
                district=f.district,
                state=f.state,
                vertices=v_responses,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
        )
    return results
