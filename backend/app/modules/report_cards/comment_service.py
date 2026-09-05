"""Authoritative teacher-comment and personal template workflow."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.classes.models import ClassRoom
from app.modules.report_cards.comment_models import (
    CommentTemplate,
    CommentTemplateGradeMapping,
    CommentTemplateOwnerType,
    CommentTemplateStatus,
    StudentTermTeacherComment,
    TeacherCommentOverride,
    TeacherCommentSource,
    TeacherCommentStatus,
)
from app.modules.report_cards.comment_schemas import (
    CommentTemplateResponse,
    CommentTemplateUpdate,
    CommentTemplateWrite,
    TeacherCommentOverrideRequest,
    TeacherCommentOverrideResponse,
    TeacherCommentResponse,
    TeacherCommentWrite,
    TeacherStudentCommentListResponse,
    TeacherStudentCommentRow,
)
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.models import AcademicResultStatus, GradingScale
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.models import Student, StudentEnrollment
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.teachers.models import TeacherMembership
from app.modules.tenant_admins.models import TenantAdmin


class ReportCommentService:
    """Own comment readiness, authorship, templates, and audited overrides."""

    @staticmethod
    async def _is_current_class_teacher(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
        class_id: uuid.UUID | None = None,
    ) -> bool:
        filters = [
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.teacher_membership_id == teacher_membership_id,
            ClassRoom.is_active.is_(True),
            ClassRoom.archived_at.is_(None),
        ]
        if class_id is not None:
            filters.append(ClassRoom.id == class_id)
        return (
            await db.execute(select(ClassRoom.id).where(*filters).limit(1))
        ).scalar_one_or_none() is not None

    @staticmethod
    async def _require_class_teacher_capability(
        db: AsyncSession,
        teacher: TeacherMembership,
        *,
        class_id: uuid.UUID | None = None,
    ) -> None:
        if not await ReportCommentService._is_current_class_teacher(
            db,
            tenant_id=teacher.tenant_id,
            teacher_membership_id=teacher.id,
            class_id=class_id,
        ):
            raise ForbiddenException(
                "Only a currently assigned class teacher can use teacher comments and templates."
            )

    @staticmethod
    async def _validate_grading_scales(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        grading_scale_ids: Iterable[uuid.UUID],
    ) -> None:
        ids = set(grading_scale_ids)
        if not ids:
            return
        found = set(
            (
                await db.execute(
                    select(GradingScale.id).where(
                        GradingScale.tenant_id == tenant_id,
                        GradingScale.id.in_(ids),
                    )
                )
            ).scalars()
        )
        if found != ids:
            raise BadRequestException("One or more grading-scale entries are invalid.")

    @staticmethod
    def _owner_filters(
        owner_type: CommentTemplateOwnerType,
        owner_id: uuid.UUID,
    ) -> list:
        if owner_type == CommentTemplateOwnerType.TENANT_ADMIN:
            return [
                CommentTemplate.owner_type == owner_type,
                CommentTemplate.tenant_admin_id == owner_id,
                CommentTemplate.teacher_membership_id.is_(None),
            ]
        return [
            CommentTemplate.owner_type == owner_type,
            CommentTemplate.teacher_membership_id == owner_id,
            CommentTemplate.tenant_admin_id.is_(None),
        ]

    @staticmethod
    async def _template_response(
        db: AsyncSession,
        template: CommentTemplate,
    ) -> CommentTemplateResponse:
        mappings = list(
            (
                await db.execute(
                    select(CommentTemplateGradeMapping).where(
                        CommentTemplateGradeMapping.tenant_id == template.tenant_id,
                        CommentTemplateGradeMapping.comment_template_id == template.id,
                    )
                )
            ).scalars()
        )
        return CommentTemplateResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            name=template.name,
            text=template.text,
            owner_type=template.owner_type,
            status=template.status,
            grading_scale_ids=[item.grading_scale_id for item in mappings],
            default_grading_scale_ids=[
                item.grading_scale_id for item in mappings if item.is_default
            ],
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        owner_type: CommentTemplateOwnerType,
        owner_id: uuid.UUID,
        include_archived: bool = False,
    ) -> list[CommentTemplateResponse]:
        filters = [
            CommentTemplate.tenant_id == tenant_id,
            *ReportCommentService._owner_filters(owner_type, owner_id),
        ]
        if not include_archived:
            filters.append(CommentTemplate.status != CommentTemplateStatus.ARCHIVED)
        templates = list(
            (
                await db.execute(
                    select(CommentTemplate)
                    .where(*filters)
                    .order_by(CommentTemplate.created_at.desc())
                )
            ).scalars()
        )
        return [await ReportCommentService._template_response(db, item) for item in templates]

    @staticmethod
    async def _clear_personal_defaults(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        owner_type: CommentTemplateOwnerType,
        owner_id: uuid.UUID,
        grading_scale_ids: set[uuid.UUID],
        excluding_template_id: uuid.UUID | None = None,
    ) -> None:
        if not grading_scale_ids:
            return
        query = (
            select(CommentTemplateGradeMapping)
            .join(
                CommentTemplate,
                CommentTemplate.id == CommentTemplateGradeMapping.comment_template_id,
            )
            .where(
                CommentTemplateGradeMapping.tenant_id == tenant_id,
                CommentTemplateGradeMapping.grading_scale_id.in_(grading_scale_ids),
                CommentTemplateGradeMapping.is_default.is_(True),
                CommentTemplate.tenant_id == tenant_id,
                *ReportCommentService._owner_filters(owner_type, owner_id),
            )
            .with_for_update()
        )
        if excluding_template_id is not None:
            query = query.where(CommentTemplate.id != excluding_template_id)
        for mapping in (await db.execute(query)).scalars():
            mapping.is_default = False
            db.add(mapping)

    @staticmethod
    async def _replace_grade_mappings(
        db: AsyncSession,
        *,
        template: CommentTemplate,
        owner_type: CommentTemplateOwnerType,
        owner_id: uuid.UUID,
        grading_scale_ids: list[uuid.UUID],
        default_grading_scale_ids: list[uuid.UUID],
    ) -> None:
        await ReportCommentService._validate_grading_scales(
            db,
            tenant_id=template.tenant_id,
            grading_scale_ids=grading_scale_ids,
        )
        defaults = set(default_grading_scale_ids)
        await ReportCommentService._clear_personal_defaults(
            db,
            tenant_id=template.tenant_id,
            owner_type=owner_type,
            owner_id=owner_id,
            grading_scale_ids=defaults,
            excluding_template_id=template.id,
        )
        existing = list(
            (
                await db.execute(
                    select(CommentTemplateGradeMapping).where(
                        CommentTemplateGradeMapping.tenant_id == template.tenant_id,
                        CommentTemplateGradeMapping.comment_template_id == template.id,
                    )
                )
            ).scalars()
        )
        for row in existing:
            await db.delete(row)
        await db.flush()
        for grading_scale_id in grading_scale_ids:
            db.add(
                CommentTemplateGradeMapping(
                    tenant_id=template.tenant_id,
                    comment_template_id=template.id,
                    grading_scale_id=grading_scale_id,
                    is_default=grading_scale_id in defaults,
                )
            )
        await db.flush()

    @staticmethod
    async def create_template(
        db: AsyncSession,
        *,
        actor: TenantAdmin | TeacherMembership,
        payload: CommentTemplateWrite,
    ) -> CommentTemplateResponse:
        if isinstance(actor, TenantAdmin):
            owner_type = CommentTemplateOwnerType.TENANT_ADMIN
            owner_id = actor.id
            template = CommentTemplate(
                tenant_id=actor.tenant_id,
                name=payload.name,
                text=payload.text,
                owner_type=owner_type,
                tenant_admin_id=actor.id,
            )
        else:
            await ReportCommentService._require_class_teacher_capability(db, actor)
            owner_type = CommentTemplateOwnerType.TEACHER
            owner_id = actor.id
            template = CommentTemplate(
                tenant_id=actor.tenant_id,
                name=payload.name,
                text=payload.text,
                owner_type=owner_type,
                teacher_membership_id=actor.id,
            )
        db.add(template)
        await db.flush()
        await ReportCommentService._replace_grade_mappings(
            db,
            template=template,
            owner_type=owner_type,
            owner_id=owner_id,
            grading_scale_ids=payload.grading_scale_ids,
            default_grading_scale_ids=payload.default_grading_scale_ids,
        )
        await db.commit()
        await db.refresh(template)
        return await ReportCommentService._template_response(db, template)

    @staticmethod
    async def _owned_template(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        owner_type: CommentTemplateOwnerType,
        owner_id: uuid.UUID,
        template_id: uuid.UUID,
        lock: bool = False,
    ) -> CommentTemplate:
        query = select(CommentTemplate).where(
            CommentTemplate.tenant_id == tenant_id,
            CommentTemplate.id == template_id,
            *ReportCommentService._owner_filters(owner_type, owner_id),
        )
        if lock:
            query = query.with_for_update()
        template = (await db.execute(query)).scalar_one_or_none()
        if template is None:
            raise NotFoundException("Comment template not found.")
        return template

    @staticmethod
    async def update_template(
        db: AsyncSession,
        *,
        actor: TenantAdmin | TeacherMembership,
        template_id: uuid.UUID,
        payload: CommentTemplateUpdate,
    ) -> CommentTemplateResponse:
        owner_type = (
            CommentTemplateOwnerType.TENANT_ADMIN
            if isinstance(actor, TenantAdmin)
            else CommentTemplateOwnerType.TEACHER
        )
        if not isinstance(actor, TenantAdmin) and payload.status != CommentTemplateStatus.ARCHIVED:
            await ReportCommentService._require_class_teacher_capability(db, actor)
        template = await ReportCommentService._owned_template(
            db,
            tenant_id=actor.tenant_id,
            owner_type=owner_type,
            owner_id=actor.id,
            template_id=template_id,
            lock=True,
        )
        if template.status == CommentTemplateStatus.ARCHIVED:
            raise BadRequestException("Archived templates are immutable.")
        for field in ("name", "text", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(template, field, value)
        if payload.grading_scale_ids is not None:
            await ReportCommentService._replace_grade_mappings(
                db,
                template=template,
                owner_type=owner_type,
                owner_id=actor.id,
                grading_scale_ids=payload.grading_scale_ids,
                default_grading_scale_ids=payload.default_grading_scale_ids or [],
            )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return await ReportCommentService._template_response(db, template)

    @staticmethod
    async def delete_template(
        db: AsyncSession,
        *,
        actor: TenantAdmin | TeacherMembership,
        template_id: uuid.UUID,
    ) -> None:
        owner_type = (
            CommentTemplateOwnerType.TENANT_ADMIN
            if isinstance(actor, TenantAdmin)
            else CommentTemplateOwnerType.TEACHER
        )
        template = await ReportCommentService._owned_template(
            db,
            tenant_id=actor.tenant_id,
            owner_type=owner_type,
            owner_id=actor.id,
            template_id=template_id,
            lock=True,
        )
        teacher_ref = (
            await db.execute(
                select(StudentTermTeacherComment.id).where(
                    StudentTermTeacherComment.tenant_id == actor.tenant_id,
                    StudentTermTeacherComment.source_template_id == template.id,
                ).limit(1)
            )
        ).scalar_one_or_none()
        report_ref = (
            await db.execute(
                select(ReportCard.id).where(
                    ReportCard.tenant_id == actor.tenant_id,
                    ReportCard.principal_comment_source_template_id == template.id,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if teacher_ref is not None or report_ref is not None:
            raise ConflictException(
                "Referenced templates cannot be deleted; deactivate or archive the template instead."
            )
        await db.delete(template)
        await db.commit()

    @staticmethod
    async def default_template_for_grade(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        owner_type: CommentTemplateOwnerType,
        owner_id: uuid.UUID,
        grading_scale_id: uuid.UUID,
    ) -> CommentTemplateResponse | None:
        rows = list(
            (
                await db.execute(
                    select(CommentTemplate)
                    .join(
                        CommentTemplateGradeMapping,
                        CommentTemplateGradeMapping.comment_template_id == CommentTemplate.id,
                    )
                    .where(
                        CommentTemplate.tenant_id == tenant_id,
                        CommentTemplate.status == CommentTemplateStatus.ACTIVE,
                        CommentTemplateGradeMapping.tenant_id == tenant_id,
                        CommentTemplateGradeMapping.grading_scale_id == grading_scale_id,
                        CommentTemplateGradeMapping.is_default.is_(True),
                        *ReportCommentService._owner_filters(owner_type, owner_id),
                    )
                )
            ).scalars()
        )
        if len(rows) > 1:
            raise ConflictException("Multiple personal default templates exist for this grade.")
        return await ReportCommentService._template_response(db, rows[0]) if rows else None

    @staticmethod
    async def _academic_readiness(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> tuple[bool, Decimal | None, GradingScale | None]:
        expected = await CurriculumResolutionService.resolve_student_curriculum(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_term_id=academic_term_id,
        )
        if not expected:
            return False, None, None
        results, _ = await StudentAcademicRepository.list_results(
            db=db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            finalized_only=True,
            limit=500,
        )
        by_curriculum = {item.curriculum_subject_id: item for item in results}
        expected_ids = {item.curriculum_subject_id for item in expected}
        if not expected_ids.issubset(by_curriculum) or any(
            by_curriculum[item_id].status != AcademicResultStatus.LOCKED
            for item_id in expected_ids
        ):
            return False, None, None
        applicable = [by_curriculum[item_id] for item_id in expected_ids]
        average = sum((item.total_score for item in applicable), Decimal("0")) / Decimal(
            len(applicable)
        )
        grading_scale = await StudentAcademicRepository.find_grade_for_score(
            db=db,
            tenant_id=tenant_id,
            score=average,
        )
        if grading_scale is None:
            return False, average, None
        return True, average, grading_scale

    @staticmethod
    async def _current_comment_context(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> tuple[StudentEnrollment, ClassRoom]:
        enrollment = await StudentEnrollmentRepository.get_authoritative_for_session(
            db,
            tenant_id,
            student_id,
            academic_session_id,
        )
        if enrollment is None or enrollment.class_id is None:
            raise BadRequestException("A resolved class placement is required.")
        classroom = (
            await db.execute(
                select(ClassRoom).where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.id == enrollment.class_id,
                )
            )
        ).scalar_one_or_none()
        if classroom is None:
            raise NotFoundException("Student class not found.")
        return enrollment, classroom

    @staticmethod
    async def _active_teacher_template(
        db: AsyncSession,
        *,
        teacher: TeacherMembership,
        template_id: uuid.UUID,
    ) -> CommentTemplate:
        template = await ReportCommentService._owned_template(
            db,
            tenant_id=teacher.tenant_id,
            owner_type=CommentTemplateOwnerType.TEACHER,
            owner_id=teacher.id,
            template_id=template_id,
        )
        if template.status != CommentTemplateStatus.ACTIVE:
            raise BadRequestException("Inactive or archived templates cannot be used.")
        return template

    @staticmethod
    async def save_teacher_comment(
        db: AsyncSession,
        *,
        teacher: TeacherMembership,
        student_id: uuid.UUID,
        payload: TeacherCommentWrite,
        submit: bool,
    ) -> TeacherCommentResponse:
        enrollment, classroom = await ReportCommentService._current_comment_context(
            db,
            tenant_id=teacher.tenant_id,
            student_id=student_id,
            academic_session_id=payload.academic_session_id,
        )
        await ReportCommentService._require_class_teacher_capability(
            db, teacher, class_id=classroom.id
        )
        if classroom.teacher_membership_id != teacher.id:
            raise ForbiddenException("Only the student's explicit class teacher can comment.")
        ready, average, grading_scale = await ReportCommentService._academic_readiness(
            db,
            tenant_id=teacher.tenant_id,
            student_id=student_id,
            academic_session_id=payload.academic_session_id,
            academic_term_id=payload.academic_term_id,
        )
        if not ready or average is None or grading_scale is None:
            if submit:
                raise BadRequestException(
                    "Teacher comments cannot be submitted until all expected results are locked."
                )
            average = average or Decimal("0")
            grade_snapshot = grading_scale.grade if grading_scale else "Pending"
        else:
            grade_snapshot = grading_scale.grade
        if payload.source_template_id is not None:
            await ReportCommentService._active_teacher_template(
                db, teacher=teacher, template_id=payload.source_template_id
            )

        comment = (
            await db.execute(
                select(StudentTermTeacherComment).where(
                    StudentTermTeacherComment.tenant_id == teacher.tenant_id,
                    StudentTermTeacherComment.student_id == student_id,
                    StudentTermTeacherComment.student_enrollment_id == enrollment.id,
                    StudentTermTeacherComment.academic_term_id == payload.academic_term_id,
                    StudentTermTeacherComment.teacher_membership_id == teacher.id,
                )
            )
        ).scalar_one_or_none()
        if comment is None:
            comment = StudentTermTeacherComment(
                tenant_id=teacher.tenant_id,
                student_id=student_id,
                student_enrollment_id=enrollment.id,
                class_id=classroom.id,
                academic_session_id=payload.academic_session_id,
                academic_term_id=payload.academic_term_id,
                teacher_membership_id=teacher.id,
                average_snapshot=average,
                grade_snapshot=grade_snapshot,
                comment_text=payload.comment_text,
                source_template_id=payload.source_template_id,
            )
        else:
            comment.average_snapshot = average
            comment.grade_snapshot = grade_snapshot
            comment.comment_text = payload.comment_text
            comment.source_template_id = payload.source_template_id
        comment.status = TeacherCommentStatus.SUBMITTED if submit else TeacherCommentStatus.DRAFT
        comment.submitted_at = datetime.now(timezone.utc) if submit else None
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return TeacherCommentResponse.model_validate(comment)

    @staticmethod
    async def list_teacher_students(
        db: AsyncSession,
        *,
        teacher: TeacherMembership,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> TeacherStudentCommentListResponse:
        await ReportCommentService._require_class_teacher_capability(
            db, teacher, class_id=class_id
        )
        enrollments = await StudentEnrollmentRepository.list_current_for_class_session(
            db,
            teacher.tenant_id,
            class_id,
            academic_session_id,
        )
        rows: list[TeacherStudentCommentRow] = []
        for enrollment in enrollments:
            student = await StudentRepository.get_by_id(
                db, teacher.tenant_id, enrollment.student_id
            )
            if student is None:
                continue
            ready, average, grading_scale = await ReportCommentService._academic_readiness(
                db,
                tenant_id=teacher.tenant_id,
                student_id=student.id,
                academic_session_id=academic_session_id,
                academic_term_id=academic_term_id,
            )
            comment = (
                await db.execute(
                    select(StudentTermTeacherComment)
                    .where(
                        StudentTermTeacherComment.tenant_id == teacher.tenant_id,
                        StudentTermTeacherComment.student_id == student.id,
                        StudentTermTeacherComment.student_enrollment_id == enrollment.id,
                        StudentTermTeacherComment.academic_term_id == academic_term_id,
                        StudentTermTeacherComment.teacher_membership_id == teacher.id,
                    )
                    .order_by(StudentTermTeacherComment.updated_at.desc())
                )
            ).scalars().first()
            if comment is not None and comment.status == TeacherCommentStatus.SUBMITTED:
                if (
                    not ready
                    or average != comment.average_snapshot
                    or grading_scale is None
                    or grading_scale.grade != comment.grade_snapshot
                ):
                    comment.status = TeacherCommentStatus.NEEDS_REVIEW
                    db.add(comment)
            suggested = None
            if grading_scale is not None:
                suggested = await ReportCommentService.default_template_for_grade(
                    db,
                    tenant_id=teacher.tenant_id,
                    owner_type=CommentTemplateOwnerType.TEACHER,
                    owner_id=teacher.id,
                    grading_scale_id=grading_scale.id,
                )
            status = (
                comment.status.value
                if comment is not None
                else ("ready_for_comment" if ready else "waiting_for_results")
            )
            rows.append(
                TeacherStudentCommentRow(
                    student_id=student.id,
                    student_name=" ".join(
                        part for part in [student.first_name, student.last_name] if part
                    ).strip()
                    or None,
                    admission_number=student.admission_number,
                    academic_ready=ready,
                    readiness_label="READY FOR COMMENT" if ready else "WAITING FOR RESULTS",
                    average=average,
                    overall_grade=grading_scale.grade if grading_scale else None,
                    comment=(TeacherCommentResponse.model_validate(comment) if comment else None),
                    comment_status=status,
                    suggested_template=suggested,
                )
            )
        await db.commit()
        return TeacherStudentCommentListResponse(
            class_id=class_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            items=rows,
        )

    @staticmethod
    async def invalidate_for_result_change(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        comments = list(
            (
                await db.execute(
                    select(StudentTermTeacherComment).where(
                        StudentTermTeacherComment.tenant_id == tenant_id,
                        StudentTermTeacherComment.student_id == student_id,
                        StudentTermTeacherComment.academic_session_id == academic_session_id,
                        StudentTermTeacherComment.academic_term_id == academic_term_id,
                        StudentTermTeacherComment.status == TeacherCommentStatus.SUBMITTED,
                    )
                )
            ).scalars()
        )
        for comment in comments:
            comment.status = TeacherCommentStatus.NEEDS_REVIEW
            db.add(comment)

    @staticmethod
    async def invalidate_for_placement_change(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> None:
        comments = list(
            (
                await db.execute(
                    select(StudentTermTeacherComment).where(
                        StudentTermTeacherComment.tenant_id == tenant_id,
                        StudentTermTeacherComment.student_id == student_id,
                        StudentTermTeacherComment.academic_session_id == academic_session_id,
                        StudentTermTeacherComment.status == TeacherCommentStatus.SUBMITTED,
                    )
                )
            ).scalars()
        )
        for comment in comments:
            comment.status = TeacherCommentStatus.NEEDS_REVIEW
            db.add(comment)

    @staticmethod
    async def create_override(
        db: AsyncSession,
        *,
        admin: TenantAdmin,
        payload: TeacherCommentOverrideRequest,
    ) -> TeacherCommentOverrideResponse:
        enrollment, classroom = await ReportCommentService._current_comment_context(
            db,
            tenant_id=admin.tenant_id,
            student_id=payload.student_id,
            academic_session_id=payload.academic_session_id,
        )
        override = TeacherCommentOverride(
            tenant_id=admin.tenant_id,
            student_id=payload.student_id,
            student_enrollment_id=enrollment.id,
            class_id=classroom.id,
            academic_session_id=payload.academic_session_id,
            academic_term_id=payload.academic_term_id,
            admin_id=admin.id,
            comment_text=payload.comment_text,
            reason=payload.reason,
        )
        db.add(override)
        await db.commit()
        await db.refresh(override)
        return TeacherCommentOverrideResponse.model_validate(override)

    @staticmethod
    async def effective_teacher_comment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> tuple[str, TeacherCommentSource, uuid.UUID, str | None, uuid.UUID | None, datetime | None]:
        enrollment, classroom = await ReportCommentService._current_comment_context(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
        )
        override = (
            await db.execute(
                select(TeacherCommentOverride)
                .where(
                    TeacherCommentOverride.tenant_id == tenant_id,
                    TeacherCommentOverride.student_id == student_id,
                    TeacherCommentOverride.student_enrollment_id == enrollment.id,
                    TeacherCommentOverride.class_id == classroom.id,
                    TeacherCommentOverride.academic_session_id == academic_session_id,
                    TeacherCommentOverride.academic_term_id == academic_term_id,
                )
                .order_by(TeacherCommentOverride.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if override is not None:
            return (
                override.comment_text,
                TeacherCommentSource.ADMIN_OVERRIDE,
                override.id,
                override.reason,
                override.admin_id,
                override.created_at,
            )
        if classroom.teacher_membership_id is None:
            raise BadRequestException(
                "Teacher comment is missing; an explicit admin override is required."
            )
        comment = (
            await db.execute(
                select(StudentTermTeacherComment)
                .where(
                    StudentTermTeacherComment.tenant_id == tenant_id,
                    StudentTermTeacherComment.student_id == student_id,
                    StudentTermTeacherComment.student_enrollment_id == enrollment.id,
                    StudentTermTeacherComment.class_id == classroom.id,
                    StudentTermTeacherComment.academic_session_id == academic_session_id,
                    StudentTermTeacherComment.academic_term_id == academic_term_id,
                    StudentTermTeacherComment.teacher_membership_id
                    == classroom.teacher_membership_id,
                    StudentTermTeacherComment.status == TeacherCommentStatus.SUBMITTED,
                )
                .order_by(StudentTermTeacherComment.submitted_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if comment is None:
            raise BadRequestException(
                "Teacher comment is missing or needs review; an explicit admin override is required."
            )
        ready, average, grading_scale = await ReportCommentService._academic_readiness(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )
        if (
            not ready
            or average != comment.average_snapshot
            or grading_scale is None
            or grading_scale.grade != comment.grade_snapshot
        ):
            comment.status = TeacherCommentStatus.NEEDS_REVIEW
            db.add(comment)
            await db.flush()
            raise BadRequestException(
                "Teacher comment needs review after academic results changed."
            )
        return (
            comment.comment_text,
            TeacherCommentSource.TEACHER_SUBMISSION,
            comment.id,
            None,
            None,
            comment.submitted_at,
        )

    @staticmethod
    async def principal_default_for_average(
        db: AsyncSession,
        *,
        admin: TenantAdmin,
        average: Decimal,
    ) -> CommentTemplateResponse | None:
        scale = await StudentAcademicRepository.find_grade_for_score(
            db=db,
            tenant_id=admin.tenant_id,
            score=average,
        )
        if scale is None:
            return None
        return await ReportCommentService.default_template_for_grade(
            db,
            tenant_id=admin.tenant_id,
            owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
            owner_id=admin.id,
            grading_scale_id=scale.id,
        )
