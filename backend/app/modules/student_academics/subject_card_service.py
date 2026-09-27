"""Current student subject-card projection.

Report-card curriculum remains score-evidence based. This read model overlays the
student's persisted current elective selections so the Subjects page immediately
reflects a successful choice before the first assessment score exists.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.parents.models import ParentMembership
from app.modules.student_academics.assessment_repository import AssessmentRepository
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    AssessmentComponentScoreResponse,
    StudentSubjectCardListResponse,
    StudentSubjectCardResponse,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.repository import TeacherMembershipRepository


class StudentSubjectCardService:
    """Build the current Subjects-page view without changing report-card semantics."""

    @staticmethod
    async def list_current_subject_cards(
        db: AsyncSession,
        *,
        actor: Student | ParentMembership,
        student_id: uuid.UUID | None = None,
    ) -> StudentSubjectCardListResponse:
        base = await StudentAcademicService.list_student_subject_cards(
            db,
            actor=actor,
            student_id=student_id,
        )
        target_student_id = actor.id if isinstance(actor, Student) else student_id
        term_id = base.context.academic_term_id
        class_id = base.context.class_id
        if target_student_id is None or term_id is None or class_id is None:
            return base

        resolved = await CurriculumResolutionService.resolve_student_subjects(
            db,
            tenant_id=actor.tenant_id,
            student_id=target_student_id,
            academic_term_id=term_id,
        )
        existing_ids = {item.curriculum_subject_id for item in base.items}
        selected_electives = [
            item
            for item in resolved
            if item.curriculum_subject_id not in existing_ids
            and item.is_elective
            and item.elective_group_id is not None
        ]
        if not selected_electives:
            return base

        active_scheme = await AssessmentRepository.get_active_scheme(db, actor.tenant_id)
        active_components = (
            await AssessmentRepository.list_components(db, actor.tenant_id, active_scheme.id)
            if active_scheme is not None
            else []
        )
        maximum_score = sum(
            (component.maximum_score for component in active_components),
            Decimal("0"),
        )

        extras: list[StudentSubjectCardResponse] = []
        for curriculum_subject in selected_electives:
            subject = await SubjectRepository.get_subject_by_id(
                db,
                actor.tenant_id,
                curriculum_subject.subject_id,
            )
            if subject is None:
                continue
            assignment = await StudentAcademicRepository.get_active_teacher_assignment_for_curriculum_subject(
                db,
                actor.tenant_id,
                curriculum_subject.curriculum_subject_id,
                class_id,
            )
            teacher = (
                await TeacherMembershipRepository.get_by_id(
                    db,
                    assignment.teacher_membership_id,
                    tenant_id=actor.tenant_id,
                    load_account=True,
                )
                if assignment is not None
                else None
            )
            teacher_name = (
                " ".join(
                    part
                    for part in [
                        teacher.teacher_account.first_name,
                        teacher.teacher_account.last_name,
                    ]
                    if part
                )
                if teacher is not None
                else None
            ) or None
            extras.append(
                StudentSubjectCardResponse(
                    id=curriculum_subject.curriculum_subject_id,
                    result_id=None,
                    curriculum_subject_id=curriculum_subject.curriculum_subject_id,
                    class_id=class_id,
                    class_name=base.context.class_name,
                    class_arm=base.context.class_arm,
                    subject_id=curriculum_subject.subject_id,
                    subject_name=subject.name,
                    subject_code=subject.code,
                    teacher_membership_id=(
                        assignment.teacher_membership_id if assignment is not None else None
                    ),
                    teacher_name=teacher_name,
                    academic_session_id=base.context.academic_session_id,
                    academic_session_name=base.context.academic_session_name,
                    academic_term_id=term_id,
                    academic_term_name=base.context.academic_term_name,
                    assessment_scheme_id=(active_scheme.id if active_scheme is not None else None),
                    assessment_scheme_name=(
                        active_scheme.name if active_scheme is not None else None
                    ),
                    components=[
                        AssessmentComponentScoreResponse(
                            assessment_component_id=component.id,
                            name=component.name,
                            code=component.code,
                            position=component.position,
                            maximum_score=component.maximum_score,
                            score=None,
                        )
                        for component in active_components
                    ],
                    maximum_score=maximum_score,
                    total_score=None,
                    grade=None,
                    remark=None,
                    status="pending",
                    is_complete=False,
                )
            )

        combined = [*base.items, *extras]
        combined.sort(
            key=lambda item: (
                (item.subject_name or "").casefold(),
                str(item.curriculum_subject_id),
            )
        )
        return base.model_copy(update={"items": combined, "total": len(combined)})
