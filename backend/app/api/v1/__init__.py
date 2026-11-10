from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.farmers import router as farmers_router
from backend.app.api.v1.devices import router as devices_router
from backend.app.api.v1.farms import router as farms_router
from backend.app.api.v1.evidence import router as evidence_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.reviewer import router as reviewer_router
from backend.app.api.v1.verify import router as verify_router
from backend.app.api.v1.merkle import router as merkle_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(farmers_router)
api_router.include_router(devices_router)
api_router.include_router(farms_router)
api_router.include_router(evidence_router)
api_router.include_router(audit_router)
api_router.include_router(reviewer_router)
api_router.include_router(verify_router)
api_router.include_router(merkle_router)
