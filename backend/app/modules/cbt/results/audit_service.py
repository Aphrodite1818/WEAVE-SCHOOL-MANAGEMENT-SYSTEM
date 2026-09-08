"""Read-only business rules for CBT result-ingestion forensic access."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.cbt.enums import CBTResultIngestionStatus
from app.modules.cbt.models import CBTServer
from app.modules.cbt.results.models import (
    CBTResultIngestionBatch,
    CBTResultIngestionItem,
)
from app.modules.cbt.results.repository import CBTResultIngestionRepository
from app.modules.cbt.results.schemas import (
    CBTResultAuditFilterOption,
    CBTResultAuditFilterOptionsResponse,
)
from app.modules.classes.models import AcademicLevel
from app.modules.student_academics.curriculum_models import CurriculumSubject
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    AssessmentComponent,
)
from app.modules.students.models import Student
from app.modules.subjects.models import Subject
from app.tenant_management.models import Tenant


def _enum_label(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").replace("_", " ").title()


def _exam_display_label(
    *,
    subject_name: str | None,
    component_name: str | None,
    level_name: str | None,
    term_name: Any,
    exam_date: date,
) -> str:
    """Build a stable human label without exposing the source exam UUID."""

    context = " · ".join(
        part
        for part in (
            subject_name,
            component_name,
            level_name,
            _enum_label(term_name) if term_name is not None else None,
        )
        if part
    )
    date_label = exam_date.strftime("%d %b %Y")
    return f"{context} · {date_label}" if context else f"CBT exam · {date_label}"


class CBTResultIngestionAuditService:
    """Tenant-safe read access to immutable CBT ingestion evidence."""

    @staticmethod
    def _validate_date_range(
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> None:
        if created_from is not None and created_to is not None and created_from > created_to:
            raise BadRequestException("created_from cannot be after created_to.")

    @staticmethod
    async def _enrich_batches(
        db: AsyncSession,
        batches: list[CBTResultIngestionBatch],
    ) -> list[CBTResultIngestionBatch]:
        """Attach presentation metadata without changing immutable ledger identity."""

        if not batches:
            return batches

        tenant_ids = {batch.tenant_id for batch in batches}
        server_pairs = {(batch.tenant_id, batch.cbt_server_id) for batch in batches}
        session_pairs = {(batch.tenant_id, batch.academic_session_id) for batch in batches}
        term_pairs = {(batch.tenant_id, batch.academic_term_id) for batch in batches}
        level_pairs = {(batch.tenant_id, batch.academic_level_id) for batch in batches}
        subject_pairs = {(batch.tenant_id, batch.curriculum_subject_id) for batch in batches}
        component_pairs = {(batch.tenant_id, batch.assessment_component_id) for batch in batches}

        tenant_rows = (
            await db.execute(
                select(Tenant.id, Tenant.school_name).where(Tenant.id.in_(tenant_ids))
            )
        ).all()
        tenant_names = {tenant_id: name for tenant_id, name in tenant_rows}

        server_rows = (
            await db.execute(
                select(CBTServer.tenant_id, CBTServer.id, CBTServer.name).where(
                    tuple_(CBTServer.tenant_id, CBTServer.id).in_(server_pairs)
                )
            )
        ).all()
        server_names = {(tenant_id, row_id): name for tenant_id, row_id, name in server_rows}

        session_rows = (
            await db.execute(
                select(AcademicSession.tenant_id, AcademicSession.id, AcademicSession.name).where(
                    tuple_(AcademicSession.tenant_id, AcademicSession.id).in_(session_pairs)
                )
            )
        ).all()
        session_names = {(tenant_id, row_id): name for tenant_id, row_id, name in session_rows}

        term_rows = (
            await db.execute(
                select(AcademicTerm.tenant_id, AcademicTerm.id, AcademicTerm.name).where(
                    tuple_(AcademicTerm.tenant_id, AcademicTerm.id).in_(term_pairs)
                )
            )
        ).all()
        term_names = {
            (tenant_id, row_id): _enum_label(name)
            for tenant_id, row_id, name in term_rows
        }

        level_rows = (
            await db.execute(
                select(AcademicLevel.tenant_id, AcademicLevel.id, AcademicLevel.name).where(
                    tuple_(AcademicLevel.tenant_id, AcademicLevel.id).in_(level_pairs)
                )
            )
        ).all()
        level_names = {(tenant_id, row_id): name for tenant_id, row_id, name in level_rows}

        subject_rows = (
            await db.execute(
                select(CurriculumSubject.tenant_id, CurriculumSubject.id, Subject.name)
                .join(
                    Subject,
                    and_(
                        Subject.id == CurriculumSubject.subject_id,
                        Subject.tenant_id == CurriculumSubject.tenant_id,
                    ),
                )
                .where(tuple_(CurriculumSubject.tenant_id, CurriculumSubject.id).in_(subject_pairs))
            )
        ).all()
        subject_names = {(tenant_id, row_id): name for tenant_id, row_id, name in subject_rows}

        component_rows = (
            await db.execute(
                select(
                    AssessmentComponent.tenant_id,
                    AssessmentComponent.id,
                    AssessmentComponent.name,
                ).where(
                    tuple_(AssessmentComponent.tenant_id, AssessmentComponent.id).in_(
                        component_pairs
                    )
                )
            )
        ).all()
        component_names = {
            (tenant_id, row_id): name for tenant_id, row_id, name in component_rows
        }

        for batch in batches:
            tenant_id = batch.tenant_id
            batch.tenant_name = tenant_names.get(tenant_id)
            batch.server_name = server_names.get((tenant_id, batch.cbt_server_id))
            batch.academic_session_name = session_names.get(
                (tenant_id, batch.academic_session_id)
            )
            batch.academic_term_name = term_names.get((tenant_id, batch.academic_term_id))
            batch.academic_level_name = level_names.get((tenant_id, batch.academic_level_id))
            batch.subject_name = subject_names.get((tenant_id, batch.curriculum_subject_id))
            batch.assessment_component_name = component_names.get(
                (tenant_id, batch.assessment_component_id)
            )
            batch.source_exam_title = _exam_display_label(
                subject_name=batch.subject_name,
                component_name=batch.assessment_component_name,
                level_name=batch.academic_level_name,
                term_name=batch.academic_term_name,
                exam_date=batch.exam_date,
            )

        return batches

    @staticmethod
    async def _enrich_items(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        items: list[CBTResultIngestionItem],
    ) -> list[CBTResultIngestionItem]:
        if not items:
            return items

        student_ids = {item.submitted_student_id for item in items}
        rows = (
            await db.execute(
                select(
                    Student.id,
                    Student.first_name,
                    Student.last_name,
                    Student.admission_number,
                ).where(
                    Student.tenant_id == tenant_id,
                    Student.id.in_(student_ids),
                )
            )
        ).all()
        students = {
            student_id: (first_name, last_name, admission_number)
            for student_id, first_name, last_name, admission_number in rows
        }

        for item in items:
            identity = students.get(item.submitted_student_id)
            if identity is None:
                item.student_name = None
                item.student_admission_number = None
                continue

            first_name, last_name, admission_number = identity
            display_name = " ".join(
                part.strip()
                for part in (first_name or "", last_name or "")
                if part.strip()
            )
            item.student_name = display_name or admission_number
            item.student_admission_number = admission_number

        return items

    @staticmethod
    async def _filter_options(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> CBTResultAuditFilterOptionsResponse:
        """Build valid filter choices from tenant-owned ingestion evidence."""

        exam_rows = (
            await db.execute(
                select(
                    CBTResultIngestionBatch.source_exam_id,
                    Subject.name,
                    AssessmentComponent.name,
                    AcademicLevel.name,
                    AcademicTerm.name,
                    CBTResultIngestionBatch.exam_date,
                )
                .outerjoin(
                    CurriculumSubject,
                    and_(
                        CurriculumSubject.id == CBTResultIngestionBatch.curriculum_subject_id,
                        CurriculumSubject.tenant_id == CBTResultIngestionBatch.tenant_id,
                    ),
                )
                .outerjoin(
                    Subject,
                    and_(
                        Subject.id == CurriculumSubject.subject_id,
                        Subject.tenant_id == CBTResultIngestionBatch.tenant_id,
                    ),
                )
                .outerjoin(
                    AssessmentComponent,
                    and_(
                        AssessmentComponent.id
                        == CBTResultIngestionBatch.assessment_component_id,
                        AssessmentComponent.tenant_id == CBTResultIngestionBatch.tenant_id,
                    ),
                )
                .outerjoin(
                    AcademicLevel,
                    and_(
                        AcademicLevel.id == CBTResultIngestionBatch.academic_level_id,
                        AcademicLevel.tenant_id == CBTResultIngestionBatch.tenant_id,
                    ),
                )
                .outerjoin(
                    AcademicTerm,
                    and_(
                        AcademicTerm.id == CBTResultIngestionBatch.academic_term_id,
                        AcademicTerm.tenant_id == CBTResultIngestionBatch.tenant_id,
                    ),
                )
                .where(CBTResultIngestionBatch.tenant_id == tenant_id)
                .distinct(CBTResultIngestionBatch.source_exam_id)
                .order_by(
                    CBTResultIngestionBatch.source_exam_id,
                    CBTResultIngestionBatch.created_at.desc(),
                )
            )
        ).all()

        exams = [
            CBTResultAuditFilterOption(
                id=exam_id,
                label=_exam_display_label(
                    subject_name=subject_name,
                    component_name=component_name,
                    level_name=level_name,
                    term_name=term_name,
                    exam_date=exam_date,
                ),
            )
            for exam_id, subject_name, component_name, level_name, term_name, exam_date in exam_rows
        ]

        async def options_for(model, id_column, label_column, ledger_column):
            rows = (
                await db.execute(
                    select(id_column, label_column)
                    .join(
                        CBTResultIngestionBatch,
                        and_(
                            ledger_column == id_column,
                            CBTResultIngestionBatch.tenant_id == model.tenant_id,
                        ),
                    )
                    .where(model.tenant_id == tenant_id)
                    .distinct()
                    .order_by(label_column)
                )
            ).all()
            return [
                CBTResultAuditFilterOption(
                    id=row_id,
                    label=_enum_label(label) if hasattr(label, "value") else str(label),
                )
                for row_id, label in rows
            ]

        sessions = await options_for(
            AcademicSession,
            AcademicSession.id,
            AcademicSession.name,
            CBTResultIngestionBatch.academic_session_id,
        )
        terms = await options_for(
            AcademicTerm,
            AcademicTerm.id,
            AcademicTerm.name,
            CBTResultIngestionBatch.academic_term_id,
        )
        levels = await options_for(
            AcademicLevel,
            AcademicLevel.id,
            AcademicLevel.name,
            CBTResultIngestionBatch.academic_level_id,
        )
        components = await options_for(
            AssessmentComponent,
            AssessmentComponent.id,
            AssessmentComponent.name,
            CBTResultIngestionBatch.assessment_component_id,
        )
        servers = await options_for(
            CBTServer,
            CBTServer.id,
            CBTServer.name,
            CBTResultIngestionBatch.cbt_server_id,
        )

        subject_rows = (
            await db.execute(
                select(CurriculumSubject.id, Subject.name)
                .join(
                    CBTResultIngestionBatch,
                    and_(
                        CBTResultIngestionBatch.curriculum_subject_id == CurriculumSubject.id,
                        CBTResultIngestionBatch.tenant_id == CurriculumSubject.tenant_id,
                    ),
                )
                .join(
                    Subject,
                    and_(
                        Subject.id == CurriculumSubject.subject_id,
                        Subject.tenant_id == CurriculumSubject.tenant_id,
                    ),
                )
                .where(CurriculumSubject.tenant_id == tenant_id)
                .distinct()
                .order_by(Subject.name)
            )
        ).all()
        subjects = [
            CBTResultAuditFilterOption(id=row_id, label=name)
            for row_id, name in subject_rows
        ]

        return CBTResultAuditFilterOptionsResponse(
            exams=exams,
            sessions=sessions,
            terms=terms,
            levels=levels,
            subjects=subjects,
            assessment_components=components,
            servers=servers,
            statuses=[status.value for status in CBTResultIngestionStatus],
        )

    @classmethod
    async def get_filter_options_for_admin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> CBTResultAuditFilterOptionsResponse:
        return await cls._filter_options(db, tenant_id=tenant_id)

    @classmethod
    async def get_filter_options_for_superadmin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> CBTResultAuditFilterOptionsResponse:
        return await cls._filter_options(db, tenant_id=tenant_id)

    @classmethod
    async def list_batches_for_admin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filters: Mapping[str, Any] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        cls._validate_date_range(created_from, created_to)
        batches, total = await CBTResultIngestionRepository.list_batches(
            db,
            tenant_id=tenant_id,
            filters=filters,
            created_from=created_from,
            created_to=created_to,
            skip=skip,
            limit=limit,
        )
        return await cls._enrich_batches(db, batches), total

    @classmethod
    async def list_batches_for_superadmin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID | None = None,
        filters: Mapping[str, Any] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        cls._validate_date_range(created_from, created_to)
        batches, total = await CBTResultIngestionRepository.list_batches(
            db,
            tenant_id=tenant_id,
            filters=filters,
            created_from=created_from,
            created_to=created_to,
            skip=skip,
            limit=limit,
        )
        return await cls._enrich_batches(db, batches), total

    @classmethod
    async def get_batch_for_admin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        batch_record_id: UUID,
    ) -> CBTResultIngestionBatch:
        batch = await CBTResultIngestionRepository.get_batch_by_id(
            db,
            batch_record_id=batch_record_id,
            tenant_id=tenant_id,
        )
        if batch is None:
            raise NotFoundException("CBT result-ingestion batch not found.")
        await cls._enrich_batches(db, [batch])
        return batch

    @classmethod
    async def get_batch_for_superadmin(
        cls,
        db: AsyncSession,
        *,
        batch_record_id: UUID,
    ) -> CBTResultIngestionBatch:
        batch = await CBTResultIngestionRepository.get_batch_by_id(
            db,
            batch_record_id=batch_record_id,
            tenant_id=None,
        )
        if batch is None:
            raise NotFoundException("CBT result-ingestion batch not found.")
        await cls._enrich_batches(db, [batch])
        return batch

    @classmethod
    async def list_batch_items_for_admin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        batch_record_id: UUID,
        filters: Mapping[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        await cls.get_batch_for_admin(
            db,
            tenant_id=tenant_id,
            batch_record_id=batch_record_id,
        )
        item_filters = dict(filters or {})
        item_filters["ingestion_batch_id"] = batch_record_id
        items, total = await CBTResultIngestionRepository.list_items(
            db,
            tenant_id=tenant_id,
            filters=item_filters,
            skip=skip,
            limit=limit,
        )
        return await cls._enrich_items(db, tenant_id=tenant_id, items=items), total

    @classmethod
    async def list_batch_items_for_superadmin(
        cls,
        db: AsyncSession,
        *,
        batch_record_id: UUID,
        filters: Mapping[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        batch = await cls.get_batch_for_superadmin(
            db,
            batch_record_id=batch_record_id,
        )
        item_filters = dict(filters or {})
        item_filters["ingestion_batch_id"] = batch_record_id
        items, total = await CBTResultIngestionRepository.list_items(
            db,
            tenant_id=batch.tenant_id,
            filters=item_filters,
            skip=skip,
            limit=limit,
        )
        return await cls._enrich_items(
            db,
            tenant_id=batch.tenant_id,
            items=items,
        ), total
