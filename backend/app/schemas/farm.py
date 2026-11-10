import json
from datetime import datetime
from typing import Optional, List, Tuple, Union, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class BoundaryVertexBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    horizontal_accuracy: Optional[float] = Field(
        None,
        alias="accuracy",
        gt=0.0,
        le=500.0,
        description="Horizontal accuracy in metres",
    )
    observation_timestamp: Optional[Union[datetime, str]] = Field(None, alias="timestamp")
    collection_method: Optional[str] = Field("WALK_AND_MARK", alias="method")
    vertex_sequence: Optional[int] = Field(None, alias="sequence")


class BoundaryVertexCreate(BoundaryVertexBase):
    pass


class BoundaryVertexResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    farm_id: str
    boundary_version: int
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None
    observation_timestamp: Optional[datetime] = None
    collection_method: Optional[str] = None
    vertex_sequence: int
    created_at: Optional[datetime] = None


class BoundaryHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    farm_id: str
    boundary_version: int
    boundary_geojson: str
    area_sq_meters: float
    area_acres: float
    crs: str
    validation_details: Optional[str] = None
    superseded_at: datetime


class FarmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    farmer_id: str
    farm_name: Optional[str] = Field(None, min_length=2, max_length=150)
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    crop_type: str = Field(..., min_length=2, max_length=100)
    boundary_geojson: Optional[Union[str, Dict[str, Any]]] = None
    boundary_polygon: Optional[Union[List[Tuple[float, float]], List[List[float]]]] = None
    vertices: Optional[List[BoundaryVertexCreate]] = None
    boundary_version: Optional[int] = 1
    crs: Optional[str] = "EPSG:4326"
    area_sq_meters: Optional[float] = None
    area_acres: Optional[float] = None
    area_hectares: Optional[float] = None
    declared_area: Optional[float] = None
    declared_area_unit: Optional[str] = "acres"
    season: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None


class FarmCreate(FarmBase):
    id: Optional[str] = None


class FarmUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    crop_type: Optional[str] = None
    season: Optional[str] = None
    farm_name: Optional[str] = None
    name: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    boundary_geojson: Optional[Union[str, Dict[str, Any]]] = None
    boundary_polygon: Optional[Union[List[Tuple[float, float]], List[List[float]]]] = None
    vertices: Optional[List[BoundaryVertexCreate]] = None
    declared_area: Optional[float] = None
    declared_area_unit: Optional[str] = "acres"


class FarmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    farm_id: Optional[str] = None
    farmer_id: str
    farm_name: str
    name: Optional[str] = None
    crop_type: str
    boundary_geojson: str
    boundary_version: int = 1
    crs: str = "EPSG:4326"
    area_sq_meters: float = 0.0
    area_acres: float = 0.0
    area_hectares: float = 0.0
    is_valid: bool = True
    validation_details: Optional[str] = None
    season: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    vertices: Optional[List[BoundaryVertexResponse]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
