"""Aggregate CBT pairing and tenant-admin management routes."""

from fastapi import APIRouter

from app.modules.cbt.pairing.admin_management_router import router as admin_management_router
from app.modules.cbt.pairing.public_router import router as public_pairing_router
from app.modules.cbt.pairing.rotation_router import router as rotation_router

router = APIRouter()
router.include_router(public_pairing_router)
router.include_router(admin_management_router)
router.include_router(rotation_router)
