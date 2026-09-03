"""Batch-oriented report-card construction helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException
from app.modules.auth_identity.models import ActorType
from app.modules.report_cards.models import (
    ReportCard,
    ReportCardStatus,
    ReportCardSubjectComponent,
    ReportCardSubjectLine,
)
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.models import AcademicResultStatus, TeacherAssignment
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.models import StudentEnrollment
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import TeacherMembership
from app.modules.tenant_admins.models import TenantAdmin


async def create_card_from_results_batched(
    db: AsyncSession,
    actor: TenantAdmin,
    *,
    student_id,
    enrollment: StudentEnrollment,
    academic_session_id,
    academic_term_id,
    results: list,
    replace_existing: ReportCard | None = None,
) -> ReportCard:
    """Create one card while resolving result metadata in bounded batch queries."""

    expected_curriculum_subjects = await ReportCardService._expected_curriculum_subjects(
        db,
        actor.tenant_id,
        student_id,
        academic_term_id,
    )
    eligible_curriculum_subject_ids = {
        item.curriculum_subject_id for item in expected_curriculum_subjects
    }
    results = [
        result
        for result in results
        if result.curriculum_subject_id in eligible_curriculum_subject_ids
    ]
    if not results:
        raise BadRequestException("No locked scores are available for this student.")

    submitted_curriculum_subject_ids = {
        result.curriculum_subject_id for result in results
    }
    missing_subject_ids = [
        item.subject_id
        for item in expected_curriculum_subjects
        if item.curriculum_subject_id not in submitted_curriculum_subject_ids
    ]

    subject_ids = {result.subject_id for result in results}
    subject_ids.update(missing_subject_ids)
    subjects = await SubjectRepository.get_subjects_by_id(
        db,
        actor.tenant_id,
        list(subject_ids),
    )
    subjects_by_id = {subject.id: subject for subject in subjects}
    if missing_subject_ids:
        missing_names = [
            subjects_by_id.get(subject_id).name
            if subjects_by_id.get(subject_id) is not None
            else str(subject_id)
            for subject_id in missing_subject_ids
        ]
        raise BadRequestException(f"Missing locked scores for: {', '.join(missing_names)}")

    if any(result.status != AcademicResultStatus.LOCKED for result in results):
        raise BadRequestException("Report cards can only be generated from locked scores.")

    assignment_ids = {
        result.teacher_assignment_id
        for result in results
        if result.teacher_assignment_id is not None
    }
    assignments = (
        list(
            (
                await db.execute(
                    select(TeacherAssignment).where(
                        TeacherAssignment.tenant_id == actor.tenant_id,
                        TeacherAssignment.id.in_(assignment_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        if assignment_ids
        else []
    )
    assignments_by_id = {assignment.id: assignment for assignment in assignments}

    teacher_ids = {
        result.teacher_membership_id
        for result in results
        if result.teacher_membership_id is not None
    }
    teacher_ids.update(assignment.teacher_membership_id for assignment in assignments)
    teachers = (
        list(
            (
                await db.execute(
                    select(TeacherMembership)
                    .options(selectinload(TeacherMembership.teacher_account))
                    .where(
                        TeacherMembership.tenant_id == actor.tenant_id,
                        TeacherMembership.id.in_(teacher_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        if teacher_ids
        else []
    )
    teachers_by_id = {teacher.id: teacher for teacher in teachers}

    grading_scales, _ = await StudentAcademicRepository.list_grading_scales(
        db,
        actor.tenant_id,
        skip=0,
        limit=100,
        active_only=True,
    )

    component_scores_by_result = (
        await StudentAcademicRepository.list_result_component_scores_batch(
            db,
            actor.tenant_id,
            results,
        )
    )

    total_score = sum((result.total_score for result in results), Decimal("0"))
    average_score = total_score / Decimal(str(len(results)))
    version = 1
    class_teacher_comment = None
    principal_comment = None
    if replace_existing is not None:
        replace_existing.superseded_at = datetime.now(timezone.utc)
        replace_existing.is_outdated = True
        replace_existing.status = ReportCardStatus.ARCHIVED
        await ReportCardRepository.save(db, replace_existing)
        version = replace_existing.version + 1
        class_teacher_comment = replace_existing.class_teacher_comment
        principal_comment = replace_existing.principal_comment

    card = await ReportCardRepository.create(
        db,
        ReportCard(
            tenant_id=actor.tenant_id,
            student_id=student_id,
            class_id=enrollment.class_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            total_score=total_score,
            average_score=average_score,
            class_teacher_comment=class_teacher_comment,
            principal_comment=principal_comment,
            version=version,
            published_at=None,
            published_by=None,
            is_outdated=False,
            status=ReportCardStatus.DRAFT,
            generated_by_actor_type=ActorType.TENANT_ADMIN.value,
            generated_by_actor_id=actor.id,
        ),
    )

    for result in results:
        subject = subjects_by_id.get(result.subject_id)
        assignment = assignments_by_id.get(result.teacher_assignment_id)
        teacher = (
            teachers_by_id.get(assignment.teacher_membership_id)
            if assignment is not None
            else None
        )
        if teacher is None and result.teacher_membership_id is not None:
            teacher = teachers_by_id.get(result.teacher_membership_id)
        teacher_name = None
        if teacher is not None:
            teacher_name = (
                " ".join(
                    part for part in [teacher.first_name, teacher.last_name] if part
                ).strip()
                or None
            )

        grade = result.grade
        remark = result.remark
        if grade is None:
            scale = next(
                (
                    item
                    for item in grading_scales
                    if item.min_score <= result.total_score <= item.max_score
                ),
                None,
            )
            if scale is not None:
                grade = scale.grade
                remark = remark or scale.remark

        line = await ReportCardRepository.create_line(
            db,
            ReportCardSubjectLine(
                tenant_id=actor.tenant_id,
                report_card_id=card.id,
                student_subject_result_id=result.id,
                subject_id=result.subject_id,
                subject_name=subject.name if subject else "Unknown subject",
                subject_code=subject.code if subject else None,
                teacher_name=teacher_name,
                total_score=result.total_score,
                grade=grade or "Pending",
                remark=remark,
            ),
        )
        for component, score in component_scores_by_result.get(result.id, []):
            if score is None:
                raise BadRequestException(
                    f"{component.name} is missing for {subject.name if subject else 'subject'}."
                )
            await ReportCardRepository.create_component(
                db,
                ReportCardSubjectComponent(
                    tenant_id=actor.tenant_id,
                    report_card_subject_line_id=line.id,
                    assessment_component_id=component.id,
                    name=component.name,
                    code=component.code,
                    position=component.position,
                    maximum_score=component.maximum_score,
                    score=score.score,
                ),
            )

    return card
