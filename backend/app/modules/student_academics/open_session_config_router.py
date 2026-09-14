"""Canonical open-session configuration route.

This override keeps OPEN sessions configurable for their name, dates and next
session target while preserving lifecycle-owned fields.
"""

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.models import AcademicSessionStatus
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    AcademicSessionResponse,
    AcademicSessionUpdate,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academics/sessions",
    tags=["Tenant Admin Academics"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


@router.patch("/{session_id}", response_model=AcademicSessionResponse)
async def configure_academic_session(
    session_id: UUID,
    payload: AcademicSessionUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionResponse:
    # This dedicated override is registered separately from the aggregate
    # academic router, so acquire the canonical tenant lifecycle lock directly.
    await ensure_academic_write_window(db, tenant_id=current_admin.tenant_id)

    session = await StudentAcademicRepository.get_academic_session_by_id(
        db,
        current_admin.tenant_id,
        session_id,
        lock=True,
    )
    if session is None:
        raise NotFoundException("Academic session not found.")
    if session.status in {AcademicSessionStatus.CLOSING, AcademicSessionStatus.CLOSED}:
        raise ConflictException("Closing or closed sessions cannot be edited.")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("name") is None:
        update_data.pop("name", None)

    effective_start_date = update_data.get("start_date", session.start_date)
    effective_end_date = update_data.get("end_date", session.end_date)
    await StudentAcademicService._validate_session_dates(
        start_date=effective_start_date,
        end_date=effective_end_date,
        require_complete=session.status == AcademicSessionStatus.OPEN,
    )

    if session.status == AcademicSessionStatus.OPEN:
        terms, _ = await StudentAcademicRepository.list_terms_by_session(
            db,
            current_admin.tenant_id,
            session.id,
            limit=500,
            statuses=set(),
        )
        for term in terms:
            if (
                effective_start_date is not None
                and term.start_date is not None
                and term.start_date < effective_start_date
            ):
                raise ConflictException(
                    "Session start date cannot move after an existing term starts."
                )
            if (
                effective_end_date is not None
                and term.end_date is not None
                and term.end_date > effective_end_date
            ):
                raise ConflictException(
                    "Session end date cannot move before an existing term ends."
                )

    if "name" in update_data and update_data["name"] != session.name:
        existing = await StudentAcademicRepository.get_academic_session_by_name(
            db,
            current_admin.tenant_id,
            update_data["name"],
        )
        if existing is not None and existing.id != session.id:
            raise ConflictException("Academic session name already exists.")

    next_session_id = update_data.get(
        "next_academic_session_id",
        session.next_academic_session_id,
    )
    await StudentAcademicService._validate_next_session_link(
        db,
        tenant_id=current_admin.tenant_id,
        session_id=session.id,
        next_academic_session_id=next_session_id,
        start_date=effective_start_date,
        end_date=effective_end_date,
    )
    if next_session_id is not None:
        next_session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            current_admin.tenant_id,
            next_session_id,
            lock=True,
        )
        if next_session is None:
            raise NotFoundException("Next academic session not found.")
        if next_session.status != AcademicSessionStatus.DRAFT:
            raise ConflictException("The configured next academic session must be in draft status.")

    previous_values = {
        "name": session.name,
        "start_date": session.start_date.isoformat() if session.start_date else None,
        "end_date": session.end_date.isoformat() if session.end_date else None,
        "next_academic_session_id": (
            str(session.next_academic_session_id) if session.next_academic_session_id else None
        ),
    }
    for field, value in update_data.items():
        setattr(session, field, value)

    try:
        session = await StudentAcademicRepository.save_academic_session(db, session)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=current_admin.tenant_id,
            entity_type="session",
            entity_id=session.id,
            action="configuration_updated",
            previous_status=session.status.value,
            new_status=session.status.value,
            acting_admin_id=current_admin.id,
            metadata={
                "previous": previous_values,
                "updated_fields": sorted(update_data.keys()),
            },
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException(
            "Academic session configuration conflicts with another session or lifecycle invariant."
        ) from exc

    await db.refresh(session)
    return AcademicSessionResponse.model_validate(session)
