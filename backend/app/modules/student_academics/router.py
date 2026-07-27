"""Academic setup, assignment, score, student, teacher, and parent routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_parent,
    get_current_student,
    get_current_teacher,
    get_current_tenant_admin,
)
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.parents.models import Parent
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    AcademicSessionCreate,
    AcademicSessionListResponse,
    AcademicSessionResponse,
    AcademicSessionUpdate,
    AcademicTermCreate,
    AcademicTermCloseRequest,
    AcademicTermListResponse,
    AcademicTermOpenRequest,
    AcademicTermResponse,
    AcademicTermUpdate,
    GradingScaleCreate,
    GradingScaleListResponse,
    GradingScaleResponse,
    GradingScaleUpdate,
    StudentSubjectCardListResponse,
    StudentSubjectResultListResponse,
    StudentSubjectResultReopenRequest,
    StudentSubjectResultResponse,
    StudentSubjectResultStatusUpdate,
    StudentSubjectResultUpsert,
    TeacherAssignmentCreate,
    TeacherAssignmentDelete,
    TeacherAssignmentEnd,
    TeacherAssignmentListResponse,
    TeacherAssignmentReassign,
    TeacherAssignmentResponse,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student
from app.modules.students.schemas import StudentListResponse
from app.modules.students.service import StudentService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


tenant_admin_router = APIRouter(
    prefix="/tenant-admin/academics",
    tags=["Tenant Admin Academics"],
)
teacher_router = APIRouter(
    prefix="/teachers/academics",
    tags=["Teacher Academics"],
)
student_router = APIRouter(
    prefix="/students/academics",
    tags=["Student Academics"],
)
parent_router = APIRouter(
    prefix="/parents/academics",
    tags=["Parent Academics"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]
CurrentTeacher: TypeAlias = Annotated[
    Teacher,
    Depends(get_current_teacher),
]
CurrentStudent: TypeAlias = Annotated[
    Student,
    Depends(get_current_student),
]
CurrentParent: TypeAlias = Annotated[
    Parent,
    Depends(get_current_parent),
]


async def _ensure_academic_setup(
    db: DbSession,
    tenant_id: UUID,
) -> None:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db,
        tenant_id,
        FeatureCode.ACADEMIC_SETUP,
    )


@tenant_admin_router.post(
    "/sessions",
    response_model=AcademicSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_academic_session(
    payload: AcademicSessionCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await StudentAcademicService.create_academic_session(
        db,
        current_admin.tenant_id,
        payload,
    )


@tenant_admin_router.get(
    "/sessions",
    response_model=AcademicSessionListResponse,
)
async def list_academic_sessions(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AcademicSessionListResponse:
    items, total = await StudentAcademicService.list_academic_sessions(
        db,
        current_admin.tenant_id,
        skip,
        limit,
    )
    return AcademicSessionListResponse(items=items, total=total)


@tenant_admin_router.patch(
    "/sessions/{session_id}",
    response_model=AcademicSessionResponse,
)
async def update_academic_session(
    session_id: UUID,
    payload: AcademicSessionUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionResponse:
    return await StudentAcademicService.update_academic_session(
        db,
        current_admin.tenant_id,
        session_id,
        payload,
    )


@tenant_admin_router.post(
    "/terms",
    response_model=AcademicTermResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_academic_term(
    payload: AcademicTermCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicTermResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await StudentAcademicService.create_academic_term(
        db,
        current_admin.tenant_id,
        payload,
    )


@tenant_admin_router.get(
    "/terms",
    response_model=AcademicTermListResponse,
)
async def list_academic_terms(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    academic_session_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AcademicTermListResponse:
    items, total = await StudentAcademicService.list_academic_terms(
        db,
        current_admin.tenant_id,
        skip=skip,
        limit=limit,
        academic_session_id=academic_session_id,
    )
    return AcademicTermListResponse(items=items, total=total)


@tenant_admin_router.patch(
    "/terms/{term_id}",
    response_model=AcademicTermResponse,
)
async def update_academic_term(
    term_id: UUID,
    payload: AcademicTermUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicTermResponse:
    return await StudentAcademicService.update_academic_term(
        db,
        current_admin.tenant_id,
        term_id,
        payload,
    )


@tenant_admin_router.post(
    "/terms/{term_id}/open",
    response_model=AcademicTermResponse,
)
async def open_academic_term(
    term_id: UUID,
    payload: AcademicTermOpenRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicTermResponse:
    return await StudentAcademicService.open_academic_term(
        db,
        current_admin.tenant_id,
        term_id,
        current_admin.id,
    )


@tenant_admin_router.post(
    "/terms/{term_id}/close",
    response_model=AcademicTermResponse,
)
async def close_academic_term(
    term_id: UUID,
    payload: AcademicTermCloseRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicTermResponse:
    return await StudentAcademicService.close_academic_term(
        db,
        current_admin.tenant_id,
        term_id,
        current_admin.id,
    )


@tenant_admin_router.post(
    "/grading-scales",
    response_model=GradingScaleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_grading_scale(
    payload: GradingScaleCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> GradingScaleResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await StudentAcademicService.create_grading_scale(
        db,
        current_admin.tenant_id,
        payload,
    )


@tenant_admin_router.get(
    "/grading-scales",
    response_model=GradingScaleListResponse,
)
async def list_grading_scales(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    active_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> GradingScaleListResponse:
    items, total = await StudentAcademicService.list_grading_scales(
        db,
        current_admin.tenant_id,
        skip=skip,
        limit=limit,
        active_only=active_only,
    )
    return GradingScaleListResponse(items=items, total=total)


@tenant_admin_router.patch(
    "/grading-scales/{scale_id}",
    response_model=GradingScaleResponse,
)
async def update_grading_scale(
    scale_id: UUID,
    payload: GradingScaleUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> GradingScaleResponse:
    return await StudentAcademicService.update_grading_scale(
        db,
        current_admin.tenant_id,
        scale_id,
        payload,
    )


@tenant_admin_router.post(
    "/class-subjects/{class_subject_id}/teacher-assignments",
    response_model=TeacherAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher_assignment(
    class_subject_id: UUID,
    payload: TeacherAssignmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await StudentAcademicService.create_teacher_assignment(
        db,
        current_admin.tenant_id,
        payload,
        class_subject_id=class_subject_id,
    )


@tenant_admin_router.get(
    "/teacher-assignments",
    response_model=TeacherAssignmentListResponse,
)
async def list_teacher_assignments(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    teacher_membership_id: UUID | None = Query(default=None),
    class_id: UUID | None = Query(default=None),
    active_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> TeacherAssignmentListResponse:
    items, total = (
        await StudentAcademicService.list_teacher_assignment_responses(
            db,
            current_admin.tenant_id,
            teacher_id=teacher_membership_id,
            class_id=class_id,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )
    )
    return TeacherAssignmentListResponse(items=items, total=total)


@tenant_admin_router.post(
    "/teacher-assignments/{assignment_id}/end",
    response_model=TeacherAssignmentResponse,
)
async def end_teacher_assignment(
    assignment_id: UUID,
    payload: TeacherAssignmentEnd,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    return await StudentAcademicService.end_teacher_assignment(
        db,
        current_admin.tenant_id,
        assignment_id,
        payload,
    )


@tenant_admin_router.post(
    "/class-subjects/{class_subject_id}/reassign-teacher",
    response_model=TeacherAssignmentResponse,
)
async def reassign_teacher_assignment(
    class_subject_id: UUID,
    payload: TeacherAssignmentReassign,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    active = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
        db,
        current_admin.tenant_id,
        class_subject_id,
    )
    if active is None:
        raise NotFoundException("Active teacher assignment not found.")
    return await StudentAcademicService.reassign_teacher_assignment(
        db,
        current_admin.tenant_id,
        active.id,
        payload,
    )


@tenant_admin_router.delete(
    "/teacher-assignments/{assignment_id}",
    response_model=TeacherAssignmentResponse,
)
async def delete_teacher_assignment(
    assignment_id: UUID,
    payload: TeacherAssignmentDelete,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    return await StudentAcademicService.delete_teacher_assignment(
        db,
        current_admin.tenant_id,
        assignment_id,
        payload,
    )


@tenant_admin_router.post(
    "/results",
    response_model=StudentSubjectResultResponse,
)
async def upsert_student_result(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.upsert_student_result(
        db,
        current_admin,
        payload,
    )


@tenant_admin_router.get(
    "/results",
    response_model=StudentSubjectResultListResponse,
)
async def list_admin_results(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    student_id: UUID | None = Query(default=None),
    class_id: UUID | None = Query(default=None),
    academic_session_id: UUID | None = Query(default=None),
    academic_term_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> StudentSubjectResultListResponse:
    items, total = await StudentAcademicService.list_results(
        db,
        current_admin,
        skip=skip,
        limit=limit,
        student_id=student_id,
        class_id=class_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
    )
    return StudentSubjectResultListResponse(items=items, total=total)


@tenant_admin_router.patch(
    "/results/{result_id}/status",
    response_model=StudentSubjectResultResponse,
)
async def update_student_result_status(
    result_id: UUID,
    payload: StudentSubjectResultStatusUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.update_result_status(
        db,
        current_admin,
        result_id,
        payload,
    )


@tenant_admin_router.post(
    "/results/{result_id}/reopen",
    response_model=StudentSubjectResultResponse,
)
async def reopen_student_result(
    result_id: UUID,
    payload: StudentSubjectResultReopenRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.reopen_result(
        db,
        current_admin,
        result_id,
        payload,
    )


@teacher_router.get(
    "/assignments",
    response_model=TeacherAssignmentListResponse,
)
async def list_my_assignments(
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> TeacherAssignmentListResponse:
    items, total = (
        await StudentAcademicService.list_teacher_assignment_responses(
            db,
            current_teacher.tenant_id,
            teacher_id=current_teacher.id,
            active_only=True,
        )
    )
    return TeacherAssignmentListResponse(items=items, total=total)


@teacher_router.get(
    "/assignments/{assignment_id}/students",
    response_model=StudentListResponse,
)
async def list_my_assignment_students(
    assignment_id: UUID,
    db: DbSession,
    current_teacher: CurrentTeacher,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> StudentListResponse:
    assignment = (
        await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            current_teacher.tenant_id,
            assignment_id,
        )
    )
    if (
        assignment is None
        or assignment.teacher_membership_id != current_teacher.id
        or not assignment.is_active
    ):
        raise ForbiddenException(
            "You may view students only for your active assignments."
        )
    class_subject = await StudentAcademicRepository.get_class_subject_by_id(
        db,
        current_teacher.tenant_id,
        assignment.class_subject_id,
    )
    if class_subject is None:
        raise NotFoundException("Class subject not found.")
    students, total = await StudentService.list_students(
        db,
        current_teacher,
        skip=skip,
        limit=limit,
        class_id=class_subject.class_id,
    )
    return StudentListResponse(items=students, total=total)


@teacher_router.get(
    "/sessions",
    response_model=AcademicSessionListResponse,
)
async def list_teacher_sessions(
    db: DbSession,
    current_teacher: CurrentTeacher,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AcademicSessionListResponse:
    items, total = await StudentAcademicService.list_academic_sessions(
        db,
        current_teacher.tenant_id,
        skip,
        limit,
    )
    return AcademicSessionListResponse(items=items, total=total)


@teacher_router.get(
    "/terms",
    response_model=AcademicTermListResponse,
)
async def list_teacher_terms(
    db: DbSession,
    current_teacher: CurrentTeacher,
    academic_session_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AcademicTermListResponse:
    items, total = await StudentAcademicService.list_academic_terms(
        db,
        current_teacher.tenant_id,
        skip=skip,
        limit=limit,
        academic_session_id=academic_session_id,
    )
    return AcademicTermListResponse(items=items, total=total)


@teacher_router.post(
    "/results",
    response_model=StudentSubjectResultResponse,
)
async def upsert_teacher_result(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.upsert_student_result(
        db,
        current_teacher,
        payload,
    )


@teacher_router.get(
    "/results",
    response_model=StudentSubjectResultListResponse,
)
async def list_teacher_results(
    db: DbSession,
    current_teacher: CurrentTeacher,
    class_id: UUID | None = Query(default=None),
    academic_session_id: UUID | None = Query(default=None),
    academic_term_id: UUID | None = Query(default=None),
) -> StudentSubjectResultListResponse:
    items, total = await StudentAcademicService.list_results(
        db,
        current_teacher,
        class_id=class_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
    )
    return StudentSubjectResultListResponse(items=items, total=total)


@student_router.get(
    "/results",
    response_model=StudentSubjectResultListResponse,
)
async def list_my_results(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentSubjectResultListResponse:
    items, total = await StudentAcademicService.list_results(
        db,
        current_student,
    )
    return StudentSubjectResultListResponse(items=items, total=total)


@student_router.get(
    "/subjects",
    response_model=StudentSubjectCardListResponse,
)
async def list_my_subject_cards(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentSubjectCardListResponse:
    return await StudentAcademicService.list_student_subject_cards(
        db,
        actor=current_student,
    )


@parent_router.get(
    "/students/{student_id}/results",
    response_model=StudentSubjectResultListResponse,
)
async def list_child_results(
    student_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
) -> StudentSubjectResultListResponse:
    items, total = await StudentAcademicService.list_results(
        db,
        current_parent,
        student_id=student_id,
    )
    return StudentSubjectResultListResponse(items=items, total=total)


@parent_router.get(
    "/students/{student_id}/subjects",
    response_model=StudentSubjectCardListResponse,
)
async def list_child_subject_cards(
    student_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
) -> StudentSubjectCardListResponse:
    return await StudentAcademicService.list_student_subject_cards(
        db,
        actor=current_parent,
        student_id=student_id,
    )
