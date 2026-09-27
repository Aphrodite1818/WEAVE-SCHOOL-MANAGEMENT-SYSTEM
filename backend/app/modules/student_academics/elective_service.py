"""Elective group policy, student selection, and curriculum integration."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation
from app.modules.cbt.sync.recorder import CBTSyncRecorder
from app.modules.cbt.sync.schemas import CBTSyncMutation
from app.modules.student_academics.curriculum_models import (
    Curriculum,
    CurriculumElectiveGroup,
    CurriculumSubject,
    ElectiveGroupLifecycle,
    StudentElectiveSelection,
)
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.curriculum_v2_repository import CurriculumSubjectRepository
from app.modules.student_academics.curriculum_v2_schemas import (
    CurriculumResponse,
    CurriculumSubjectCreate,
    CurriculumSubjectResponse,
    CurriculumSubjectUpdate,
)
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.elective_schemas import (
    ElectiveGroupCreate,
    ElectiveGroupResponse,
    ElectiveGroupUpdate,
    StudentElectiveGroupWorkspace,
    StudentElectiveSelectionUpdate,
    StudentElectiveSubjectOption,
    StudentElectiveWorkspaceResponse,
)
from app.modules.student_academics.models import (
    AcademicTerm,
    AcademicTermStatus,
    StudentAssessmentScore,
    StudentSubjectResult,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.models import Student
from app.modules.students.repository import StudentEnrollmentRepository
from app.modules.subjects.models import Subject


class ElectivePolicyService:
    """Own elective-group policy and persistent student selections.

    Student selections deliberately have no term foreign key. They remain the
    student's current choice until changed, while result rows remain the historical
    source of truth for previously-assessed electives.
    """

    LOCKED_REASON = (
        "Elective choices are locked for this term because assessment scores already "
        "exist for this elective group."
    )

    @staticmethod
    async def _curriculum_for_level(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        require_active_level: bool = False,
    ) -> Curriculum:
        return await AcademicCurriculumService._curriculum(
            db,
            tenant_id,
            academic_level_id,
            require_active_level=require_active_level,
        )

    @staticmethod
    async def _group(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        elective_group_id: uuid.UUID,
        lock: bool = False,
    ) -> CurriculumElectiveGroup:
        query = select(CurriculumElectiveGroup).where(
            CurriculumElectiveGroup.tenant_id == tenant_id,
            CurriculumElectiveGroup.id == elective_group_id,
        )
        if lock:
            query = query.with_for_update()
        row = (await db.execute(query)).scalar_one_or_none()
        if row is None:
            raise NotFoundException("Elective group not found.")
        return row

    @staticmethod
    async def validate_curriculum_subject_group(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        is_elective: bool,
        elective_group_id: uuid.UUID | None,
        lock: bool = False,
    ) -> CurriculumElectiveGroup | None:
        if not is_elective:
            if elective_group_id is not None:
                raise BadRequestException(
                    "Compulsory curriculum subjects cannot reference an elective group."
                )
            return None
        if elective_group_id is None:
            raise BadRequestException("An elective group is required for elective subjects.")
        group = await ElectivePolicyService._group(
            db,
            tenant_id=tenant_id,
            elective_group_id=elective_group_id,
            lock=lock,
        )
        if group.curriculum_id != curriculum_id:
            raise BadRequestException(
                "The selected elective group does not belong to this level curriculum."
            )
        if group.lifecycle != ElectiveGroupLifecycle.ACTIVE.value:
            raise ConflictException("Archived elective groups cannot receive elective subjects.")
        return group

    @staticmethod
    async def list_groups(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
    ) -> list[ElectiveGroupResponse]:
        curriculum = await ElectivePolicyService._curriculum_for_level(
            db,
            tenant_id=tenant_id,
            academic_level_id=academic_level_id,
        )
        rows = list(
            (
                await db.execute(
                    select(CurriculumElectiveGroup)
                    .where(
                        CurriculumElectiveGroup.tenant_id == tenant_id,
                        CurriculumElectiveGroup.curriculum_id == curriculum.id,
                    )
                    .order_by(CurriculumElectiveGroup.name, CurriculumElectiveGroup.id)
                )
            ).scalars()
        )
        return [ElectiveGroupResponse.model_validate(row) for row in rows]

    @staticmethod
    async def create_group(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        payload: ElectiveGroupCreate,
    ) -> ElectiveGroupResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        curriculum = await ElectivePolicyService._curriculum_for_level(
            db,
            tenant_id=tenant_id,
            academic_level_id=academic_level_id,
            require_active_level=True,
        )
        duplicate = (
            await db.execute(
                select(CurriculumElectiveGroup.id).where(
                    CurriculumElectiveGroup.tenant_id == tenant_id,
                    CurriculumElectiveGroup.curriculum_id == curriculum.id,
                    func.lower(CurriculumElectiveGroup.name) == payload.name.lower(),
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise ConflictException("An elective group with this name already exists.")
        row = CurriculumElectiveGroup(
            tenant_id=tenant_id,
            curriculum_id=curriculum.id,
            name=payload.name,
            minimum_choices=payload.minimum_choices,
            maximum_choices=payload.maximum_choices,
            lifecycle=ElectiveGroupLifecycle.ACTIVE.value,
        )
        try:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("An elective group with this name already exists.") from exc
        return ElectiveGroupResponse.model_validate(row)

    @staticmethod
    async def update_group(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        elective_group_id: uuid.UUID,
        payload: ElectiveGroupUpdate,
    ) -> ElectiveGroupResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        group = await ElectivePolicyService._group(
            db,
            tenant_id=tenant_id,
            elective_group_id=elective_group_id,
            lock=True,
        )
        if group.lifecycle != ElectiveGroupLifecycle.ACTIVE.value:
            raise ConflictException("Archived elective groups must be restored before editing.")

        minimum = (
            payload.minimum_choices
            if "minimum_choices" in payload.model_fields_set
            else group.minimum_choices
        )
        maximum = (
            payload.maximum_choices
            if "maximum_choices" in payload.model_fields_set
            else group.maximum_choices
        )
        assert minimum is not None and maximum is not None
        if minimum > maximum:
            raise BadRequestException("minimum_choices cannot exceed maximum_choices.")

        if "name" in payload.model_fields_set:
            if payload.name is None:
                raise BadRequestException("name cannot be null.")
            duplicate = (
                await db.execute(
                    select(CurriculumElectiveGroup.id).where(
                        CurriculumElectiveGroup.tenant_id == tenant_id,
                        CurriculumElectiveGroup.curriculum_id == group.curriculum_id,
                        CurriculumElectiveGroup.id != group.id,
                        func.lower(CurriculumElectiveGroup.name) == payload.name.lower(),
                    )
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                raise ConflictException("An elective group with this name already exists.")
            group.name = payload.name

        if "minimum_choices" in payload.model_fields_set:
            group.minimum_choices = minimum
        if "maximum_choices" in payload.model_fields_set:
            group.maximum_choices = maximum

        # Never make an already-valid persisted selection invalid by reducing the
        # maximum below an existing student's selected count.
        violating_maximum = (
            await db.execute(
                select(StudentElectiveSelection.student_id)
                .where(
                    StudentElectiveSelection.tenant_id == tenant_id,
                    StudentElectiveSelection.elective_group_id == group.id,
                )
                .group_by(StudentElectiveSelection.student_id)
                .having(func.count(StudentElectiveSelection.id) > maximum)
                .limit(1)
            )
        ).scalar_one_or_none()
        if violating_maximum is not None:
            raise ConflictException(
                "The new maximum is lower than an existing student's elective selection count."
            )

        try:
            await db.commit()
            await db.refresh(group)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("The elective group could not be updated.") from exc
        return ElectiveGroupResponse.model_validate(group)

    @staticmethod
    async def archive_group(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        elective_group_id: uuid.UUID,
    ) -> ElectiveGroupResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        group = await ElectivePolicyService._group(
            db,
            tenant_id=tenant_id,
            elective_group_id=elective_group_id,
            lock=True,
        )
        if group.lifecycle == ElectiveGroupLifecycle.ARCHIVED.value:
            return ElectiveGroupResponse.model_validate(group)
        active_subject = (
            await db.execute(
                select(CurriculumSubject.id)
                .where(
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.elective_group_id == group.id,
                    CurriculumSubject.is_active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if active_subject is not None:
            raise ConflictException(
                "Deactivate or move active elective subjects before archiving this group."
            )
        group.lifecycle = ElectiveGroupLifecycle.ARCHIVED.value
        await db.commit()
        await db.refresh(group)
        return ElectiveGroupResponse.model_validate(group)

    @staticmethod
    async def restore_group(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        elective_group_id: uuid.UUID,
    ) -> ElectiveGroupResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        group = await ElectivePolicyService._group(
            db,
            tenant_id=tenant_id,
            elective_group_id=elective_group_id,
            lock=True,
        )
        if group.lifecycle != ElectiveGroupLifecycle.ACTIVE.value:
            group.lifecycle = ElectiveGroupLifecycle.ACTIVE.value
            await db.commit()
            await db.refresh(group)
        return ElectiveGroupResponse.model_validate(group)

    @staticmethod
    async def _group_has_current_term_score_evidence(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
        elective_group_id: uuid.UUID,
    ) -> bool:
        count = (
            await db.execute(
                select(func.count(StudentAssessmentScore.id))
                .select_from(StudentAssessmentScore)
                .join(
                    StudentSubjectResult,
                    StudentSubjectResult.id == StudentAssessmentScore.student_subject_result_id,
                )
                .join(
                    CurriculumSubject,
                    CurriculumSubject.id == StudentSubjectResult.curriculum_subject_id,
                )
                .where(
                    StudentAssessmentScore.tenant_id == tenant_id,
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.student_id == student_id,
                    StudentSubjectResult.academic_term_id == academic_term_id,
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.elective_group_id == elective_group_id,
                )
            )
        ).scalar_one()
        return int(count) > 0

    @staticmethod
    async def _current_context(
        db: AsyncSession,
        *,
        student: Student,
    ):
        session = await StudentAcademicRepository.get_current_academic_session(
            db, student.tenant_id
        )
        term = await StudentAcademicRepository.get_current_term(db, student.tenant_id)
        if session is None or term is None or term.academic_session_id != session.id:
            return session, term, None
        enrollment = await StudentEnrollmentRepository.get_authoritative_for_session(
            db,
            student.tenant_id,
            student.id,
            session.id,
        )
        return session, term, enrollment

    @staticmethod
    async def get_student_workspace(
        db: AsyncSession,
        *,
        student: Student,
    ) -> StudentElectiveWorkspaceResponse:
        session, term, enrollment = await ElectivePolicyService._current_context(
            db, student=student
        )
        if session is None or term is None or enrollment is None or enrollment.class_id is None:
            return StudentElectiveWorkspaceResponse(
                academic_session_id=session.id if session else None,
                academic_session_name=session.name if session else None,
                academic_term_id=term.id if term else None,
                academic_term_name=(
                    getattr(term.name, "value", str(term.name)) if term is not None else None
                ),
                academic_level_id=enrollment.academic_level_id if enrollment else None,
                class_id=enrollment.class_id if enrollment else None,
                groups=[],
            )

        curriculum = await ElectivePolicyService._curriculum_for_level(
            db,
            tenant_id=student.tenant_id,
            academic_level_id=enrollment.academic_level_id,
        )
        resolved = await CurriculumResolutionService.resolve_class_subjects(
            db,
            tenant_id=student.tenant_id,
            class_id=enrollment.class_id,
            academic_term_id=term.id,
        )
        resolved_ids = {item.curriculum_subject_id for item in resolved}
        if not resolved_ids:
            return StudentElectiveWorkspaceResponse(
                academic_session_id=session.id,
                academic_session_name=session.name,
                academic_term_id=term.id,
                academic_term_name=getattr(term.name, "value", str(term.name)),
                academic_level_id=enrollment.academic_level_id,
                class_id=enrollment.class_id,
                groups=[],
            )

        option_rows = (
            await db.execute(
                select(CurriculumSubject, Subject, CurriculumElectiveGroup)
                .join(Subject, Subject.id == CurriculumSubject.subject_id)
                .join(
                    CurriculumElectiveGroup,
                    CurriculumElectiveGroup.id == CurriculumSubject.elective_group_id,
                )
                .where(
                    CurriculumSubject.tenant_id == student.tenant_id,
                    CurriculumSubject.id.in_(resolved_ids),
                    CurriculumSubject.curriculum_id == curriculum.id,
                    CurriculumSubject.is_active.is_(True),
                    CurriculumSubject.is_elective.is_(True),
                    CurriculumSubject.elective_group_id.is_not(None),
                    Subject.tenant_id == student.tenant_id,
                    Subject.is_active.is_(True),
                    Subject.archived_at.is_(None),
                    CurriculumElectiveGroup.tenant_id == student.tenant_id,
                    CurriculumElectiveGroup.curriculum_id == curriculum.id,
                    CurriculumElectiveGroup.lifecycle == ElectiveGroupLifecycle.ACTIVE.value,
                )
                .order_by(CurriculumElectiveGroup.name, Subject.name)
            )
        ).all()
        if not option_rows:
            groups: list[StudentElectiveGroupWorkspace] = []
        else:
            group_ids = {group.id for _membership, _subject, group in option_rows}
            selected_ids = set(
                (
                    await db.execute(
                        select(StudentElectiveSelection.curriculum_subject_id).where(
                            StudentElectiveSelection.tenant_id == student.tenant_id,
                            StudentElectiveSelection.student_id == student.id,
                            StudentElectiveSelection.elective_group_id.in_(group_ids),
                        )
                    )
                ).scalars()
            )
            options_by_group: dict[uuid.UUID, list[StudentElectiveSubjectOption]] = {}
            group_by_id: dict[uuid.UUID, CurriculumElectiveGroup] = {}
            for membership, subject, group in option_rows:
                group_by_id[group.id] = group
                options_by_group.setdefault(group.id, []).append(
                    StudentElectiveSubjectOption(
                        curriculum_subject_id=membership.id,
                        subject_id=subject.id,
                        subject_name=subject.name,
                        subject_code=subject.code,
                        selected=membership.id in selected_ids,
                    )
                )
            groups = []
            for group_id, group in sorted(
                group_by_id.items(), key=lambda item: item[1].name.lower()
            ):
                locked = (
                    term.status != AcademicTermStatus.OPEN
                    or await ElectivePolicyService._group_has_current_term_score_evidence(
                        db,
                        tenant_id=student.tenant_id,
                        student_id=student.id,
                        academic_term_id=term.id,
                        elective_group_id=group_id,
                    )
                )
                subjects = options_by_group.get(group_id, [])
                groups.append(
                    StudentElectiveGroupWorkspace(
                        elective_group_id=group.id,
                        name=group.name,
                        minimum_choices=group.minimum_choices,
                        maximum_choices=group.maximum_choices,
                        selected_count=sum(item.selected for item in subjects),
                        locked=locked,
                        locked_reason=(
                            ElectivePolicyService.LOCKED_REASON
                            if locked and term.status == AcademicTermStatus.OPEN
                            else (
                                "Elective choices are unavailable while the current academic term is not open."
                                if locked
                                else None
                            )
                        ),
                        subjects=subjects,
                    )
                )

        return StudentElectiveWorkspaceResponse(
            academic_session_id=session.id,
            academic_session_name=session.name,
            academic_term_id=term.id,
            academic_term_name=getattr(term.name, "value", str(term.name)),
            academic_level_id=enrollment.academic_level_id,
            class_id=enrollment.class_id,
            groups=groups,
        )

    @staticmethod
    async def replace_student_selection(
        db: AsyncSession,
        *,
        student: Student,
        elective_group_id: uuid.UUID,
        payload: StudentElectiveSelectionUpdate,
    ) -> StudentElectiveWorkspaceResponse:
        await ensure_academic_write_window(db, tenant_id=student.tenant_id)
        session, term, enrollment = await ElectivePolicyService._current_context(
            db, student=student
        )
        if session is None or term is None or enrollment is None or enrollment.class_id is None:
            raise ConflictException(
                "A current academic session, term, and class enrollment are required to choose electives."
            )
        if term.status != AcademicTermStatus.OPEN:
            raise ConflictException("Elective choices can only be changed during an open term.")

        curriculum = await ElectivePolicyService._curriculum_for_level(
            db,
            tenant_id=student.tenant_id,
            academic_level_id=enrollment.academic_level_id,
            require_active_level=True,
        )
        group = await ElectivePolicyService._group(
            db,
            tenant_id=student.tenant_id,
            elective_group_id=elective_group_id,
            lock=True,
        )
        if group.curriculum_id != curriculum.id:
            raise BadRequestException(
                "This elective group is not available to your academic level."
            )
        if group.lifecycle != ElectiveGroupLifecycle.ACTIVE.value:
            raise ConflictException("This elective group is archived.")

        if await ElectivePolicyService._group_has_current_term_score_evidence(
            db,
            tenant_id=student.tenant_id,
            student_id=student.id,
            academic_term_id=term.id,
            elective_group_id=group.id,
        ):
            raise ConflictException(ElectivePolicyService.LOCKED_REASON)

        requested_ids = set(payload.curriculum_subject_ids)
        if not group.minimum_choices <= len(requested_ids) <= group.maximum_choices:
            raise BadRequestException(
                f"Choose between {group.minimum_choices} and {group.maximum_choices} subject(s) in {group.name}."
            )

        resolved = await CurriculumResolutionService.resolve_class_subjects(
            db,
            tenant_id=student.tenant_id,
            class_id=enrollment.class_id,
            academic_term_id=term.id,
        )
        applicable_ids = {item.curriculum_subject_id for item in resolved}
        if requested_ids:
            valid_ids = set(
                (
                    await db.execute(
                        select(CurriculumSubject.id).where(
                            CurriculumSubject.tenant_id == student.tenant_id,
                            CurriculumSubject.id.in_(requested_ids),
                            CurriculumSubject.curriculum_id == curriculum.id,
                            CurriculumSubject.elective_group_id == group.id,
                            CurriculumSubject.is_elective.is_(True),
                            CurriculumSubject.is_active.is_(True),
                        )
                    )
                ).scalars()
            )
            if valid_ids != requested_ids or not requested_ids.issubset(applicable_ids):
                raise BadRequestException(
                    "One or more selected subjects are not available in this elective group."
                )

        existing_rows = list(
            (
                await db.execute(
                    select(StudentElectiveSelection)
                    .where(
                        StudentElectiveSelection.tenant_id == student.tenant_id,
                        StudentElectiveSelection.student_id == student.id,
                        StudentElectiveSelection.elective_group_id == group.id,
                    )
                    .with_for_update()
                )
            ).scalars()
        )
        existing_by_subject = {row.curriculum_subject_id: row for row in existing_rows}
        remove_ids = set(existing_by_subject) - requested_ids
        add_ids = requested_ids - set(existing_by_subject)

        mutations: list[CBTSyncMutation] = []
        for curriculum_subject_id in sorted(remove_ids, key=str):
            row = existing_by_subject[curriculum_subject_id]
            await db.delete(row)
            mutations.append(
                CBTSyncMutation(
                    entity_type=CBTSyncEntityType.STUDENT_ELECTIVE_SELECTION,
                    entity_id=row.id,
                    operation=CBTSyncOperation.DELETED,
                    payload=None,
                )
            )
        for curriculum_subject_id in sorted(add_ids, key=str):
            row = StudentElectiveSelection(
                tenant_id=student.tenant_id,
                student_id=student.id,
                elective_group_id=group.id,
                curriculum_subject_id=curriculum_subject_id,
            )
            db.add(row)
            await db.flush()
            mutations.append(
                CBTSyncMutation(
                    entity_type=CBTSyncEntityType.STUDENT_ELECTIVE_SELECTION,
                    entity_id=row.id,
                    operation=CBTSyncOperation.CREATED,
                    payload={
                        "id": str(row.id),
                        "student_id": str(row.student_id),
                        "elective_group_id": str(row.elective_group_id),
                        "curriculum_subject_id": str(row.curriculum_subject_id),
                    },
                )
            )

        if mutations:
            await db.flush()
            await db.run_sync(
                lambda sync_db: CBTSyncRecorder.record_many_sync(
                    sync_db,
                    tenant_id=student.tenant_id,
                    mutations=mutations,
                )
            )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Elective choices changed concurrently. Refresh and try again."
            ) from exc
        return await ElectivePolicyService.get_student_workspace(db, student=student)


class ElectiveAwareCurriculumService:
    """Curriculum writes that enforce the elective-group invariant atomically."""

    @staticmethod
    def _enrich_subject_response(
        response: CurriculumSubjectResponse,
        row: CurriculumSubject,
    ) -> CurriculumSubjectResponse:
        return response.model_copy(update={"elective_group_id": row.elective_group_id})

    @staticmethod
    async def get_curriculum(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level_id: uuid.UUID,
    ) -> CurriculumResponse:
        response = await AcademicCurriculumService.get_curriculum(db, tenant_id, level_id)
        rows = list(
            (
                await db.execute(
                    select(CurriculumSubject).where(
                        CurriculumSubject.tenant_id == tenant_id,
                        CurriculumSubject.curriculum_id == response.id,
                    )
                )
            ).scalars()
        )
        by_id = {row.id: row for row in rows}
        return response.model_copy(
            update={
                "subjects": [
                    item.model_copy(
                        update={
                            "elective_group_id": (
                                by_id[item.id].elective_group_id if item.id in by_id else None
                            )
                        }
                    )
                    for item in response.subjects
                ]
            }
        )

    @staticmethod
    async def add_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level_id: uuid.UUID,
        payload: CurriculumSubjectCreate,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        curriculum = await AcademicCurriculumService._curriculum(
            db, tenant_id, level_id, require_active_level=True
        )
        await ElectivePolicyService.validate_curriculum_subject_group(
            db,
            tenant_id=tenant_id,
            curriculum_id=curriculum.id,
            is_elective=payload.is_elective,
            elective_group_id=payload.elective_group_id,
            lock=True,
        )
        subject = (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.id == payload.subject_id,
                    Subject.is_active.is_(True),
                    Subject.archived_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if subject is None:
            raise NotFoundException("Active subject not found.")
        existing = await CurriculumSubjectRepository.get_for_curriculum_subject(
            db, tenant_id, curriculum.id, subject.id
        )
        if existing:
            raise ConflictException("This subject is already in the level curriculum.")
        row = CurriculumSubject(
            tenant_id=tenant_id,
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            is_elective=payload.is_elective,
            elective_group_id=payload.elective_group_id,
            is_active=True,
        )
        try:
            await CurriculumSubjectRepository.add(db, row)
            await AcademicCurriculumService._replace_department_scopes(
                db,
                tenant_id=tenant_id,
                curriculum_subject=row,
                curriculum=curriculum,
                academic_level_department_ids=payload.academic_level_department_ids,
            )
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("This subject is already in the level curriculum.") from exc
        response = await AcademicCurriculumService._curriculum_subject_response(db, row, subject)
        return ElectiveAwareCurriculumService._enrich_subject_response(response, row)

    @staticmethod
    async def update_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        payload: CurriculumSubjectUpdate,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row, curriculum, subject = await AcademicCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=True,
            require_active_level=True,
        )
        if not row.is_active:
            raise ConflictException(
                "Inactive curriculum subjects cannot be edited. Activate the membership first."
            )
        dependencies = await CurriculumSubjectRepository.count_dependencies(db, tenant_id, row.id)

        final_is_elective = (
            bool(payload.is_elective)
            if "is_elective" in payload.model_fields_set
            else row.is_elective
        )
        if "elective_group_id" in payload.model_fields_set:
            final_group_id = payload.elective_group_id
        elif "is_elective" in payload.model_fields_set and not final_is_elective:
            final_group_id = None
        else:
            final_group_id = row.elective_group_id

        semantic_change = (
            final_is_elective != row.is_elective or final_group_id != row.elective_group_id
        )
        if semantic_change and dependencies["results_total"] > 0:
            raise ConflictException(
                "Curriculum subject elective meaning is locked after academic results exist.",
                payload={"dependency_counts": {"results_total": dependencies["results_total"]}},
            )
        await ElectivePolicyService.validate_curriculum_subject_group(
            db,
            tenant_id=tenant_id,
            curriculum_id=curriculum.id,
            is_elective=final_is_elective,
            elective_group_id=final_group_id,
            lock=True,
        )

        scope_changed = False
        if "academic_level_department_ids" in payload.model_fields_set:
            requested = payload.academic_level_department_ids or []
            existing_links = await CurriculumSubjectRepository.list_department_links(
                db, tenant_id, row.id, lock=True
            )
            old_ids = {link.academic_level_department_id for link in existing_links}
            if old_ids != set(requested) and dependencies["results_total"] > 0:
                raise ConflictException(
                    "Department applicability is locked after academic results exist for this curriculum subject.",
                    payload={"dependency_counts": {"results_total": dependencies["results_total"]}},
                )
            scope_changed = await AcademicCurriculumService._replace_department_scopes(
                db,
                tenant_id=tenant_id,
                curriculum_subject=row,
                curriculum=curriculum,
                academic_level_department_ids=requested,
            )

        row.is_elective = final_is_elective
        row.elective_group_id = final_group_id
        await CurriculumSubjectRepository.save(db, row)
        if scope_changed:
            current_term = (
                await db.execute(
                    select(AcademicTerm).where(
                        AcademicTerm.tenant_id == tenant_id,
                        AcademicTerm.is_current.is_(True),
                        AcademicTerm.status == AcademicTermStatus.OPEN,
                    )
                )
            ).scalar_one_or_none()
            if current_term is not None:
                await AcademicCurriculumService.reconcile_teacher_assignments_for_term(
                    db,
                    tenant_id=tenant_id,
                    term=current_term,
                    acting_admin_id=None,
                    transition_boundary=date.today(),
                )
        await db.commit()
        await db.refresh(row)
        response = await AcademicCurriculumService._curriculum_subject_response(db, row, subject)
        return ElectiveAwareCurriculumService._enrich_subject_response(response, row)

    @staticmethod
    async def activate_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> CurriculumSubjectResponse:
        row, curriculum, _subject = await AcademicCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=False,
            require_active_level=True,
            require_active_subject=True,
        )
        await ElectivePolicyService.validate_curriculum_subject_group(
            db,
            tenant_id=tenant_id,
            curriculum_id=curriculum.id,
            is_elective=row.is_elective,
            elective_group_id=row.elective_group_id,
        )
        response = await AcademicCurriculumService.activate_subject(
            db, tenant_id, curriculum_subject_id
        )
        refreshed = await CurriculumSubjectRepository.get_by_id(
            db, tenant_id, curriculum_subject_id
        )
        return ElectiveAwareCurriculumService._enrich_subject_response(response, refreshed or row)

    @staticmethod
    async def deactivate_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> CurriculumSubjectResponse:
        response = await AcademicCurriculumService.deactivate_subject(
            db, tenant_id, curriculum_subject_id
        )
        row = await CurriculumSubjectRepository.get_by_id(db, tenant_id, curriculum_subject_id)
        return (
            ElectiveAwareCurriculumService._enrich_subject_response(response, row)
            if row is not None
            else response
        )

    @staticmethod
    async def hard_delete_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> CurriculumSubjectResponse:
        row = await CurriculumSubjectRepository.get_by_id(db, tenant_id, curriculum_subject_id)
        response = await AcademicCurriculumService.hard_delete_subject(
            db, tenant_id, curriculum_subject_id
        )
        return (
            ElectiveAwareCurriculumService._enrich_subject_response(response, row)
            if row is not None
            else response
        )
