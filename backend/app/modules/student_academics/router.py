from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_onboarded_student,
    get_current_parent,
    get_current_teacher,
    get_current_tenant_admin,
)
from app.modules.parents.models import Parent
from app.modules.student_academics.schemas import (
    AcademicSessionCreate,
    AcademicSessionListResponse,
    AcademicSessionResponse,
    AcademicSessionUpdate,
    AcademicTermCreate,
    AcademicTermListResponse,
    AcademicTermResponse,
    AcademicTermUpdate,
    ClassSubjectTeacherCreate,
    ClassSubjectTeacherListResponse,
    ClassSubjectTeacherResponse,
    ClassSubjectTeacherUpdate,
    GradingScaleCreate,
    GradingScaleListResponse,
    GradingScaleResponse,
    GradingScaleUpdate,
    StudentSubjectCardListResponse,
    StudentSubjectResultListResponse,
    StudentSubjectResultResponse,
    StudentSubjectResultStatusUpdate,
    StudentSubjectResultUpsert,
    TeacherAssignmentCreate,
    TeacherAssignmentListResponse,
    TeacherAssignmentReassign,
    TeacherAssignmentResponse,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


tenant_admin_router = APIRouter(
    prefix="/tenant-admin/academic",
    tags=["Tenant Admin Academic"],
)
teacher_router = APIRouter(
    prefix="/teachers/me/academic",
    tags=["Teacher Academic"],
)
student_router = APIRouter(
    prefix="/students/me/academic",
    tags=["Student Academic"],
)
parent_router = APIRouter(
    prefix="/parents/me/children/{student_id}/academic",
    tags=["Parent Academic"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_onboarded_student)]
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]


def _is_submitted_status(value) -> bool:
    return (value.value if hasattr(value, "value") else str(value)) == "submitted"


def _submitted_result_list(items: list[StudentSubjectResultResponse]) -> StudentSubjectResultListResponse:
    submitted_items = [item for item in items if _is_submitted_status(item.status)]
    return StudentSubjectResultListResponse(items=submitted_items, total=len(submitted_items))


def _mask_unsubmitted_subject_cards(response: StudentSubjectCardListResponse) -> StudentSubjectCardListResponse:
    for item in response.items:
        if item.status != "submitted":
            item.result_id = None
            item.test_score = None
            item.assessment_score = None
            item.exam_score = None
            item.total_score = None
            item.grade = None
            item.remark = None
            item.status = "pending"
            item.is_complete = False
    return response


@tenant_admin_router.post(
    "/sessions",
    response_model=AcademicSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: AcademicSessionCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicSessionResponse:
    return await StudentAcademicService.create_academic_session(db, current_admin.tenant_id, payload)


@tenant_admin_router.get("/sessions", response_model=AcademicSessionListResponse)
async def list_sessions(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AcademicSessionListResponse:
    items, total = await StudentAcademicService.list_academic_sessions(
        db,
        current_admin.tenant_id,
        skip=skip,
        limit=limit,
    )
    return AcademicSessionListResponse(items=items, total=total)


@tenant_admin_router.patch("/sessions/{session_id}", response_model=AcademicSessionResponse)
async def update_session(
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
async def create_term(
    payload: AcademicTermCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AcademicTermResponse:
    return await StudentAcademicService.create_academic_term(db, current_admin.tenant_id, payload)


@tenant_admin_router.get("/terms", response_model=AcademicTermListResponse)
async def list_terms(
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


@tenant_admin_router.patch("/terms/{term_id}", response_model=AcademicTermResponse)
async def update_term(
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
    "/grading-scales",
    response_model=GradingScaleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_grading_scale(
    payload: GradingScaleCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> GradingScaleResponse:
    return await StudentAcademicService.create_grading_scale(db, current_admin.tenant_id, payload)


@tenant_admin_router.get("/grading-scales", response_model=GradingScaleListResponse)
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


@tenant_admin_router.patch("/grading-scales/{scale_id}", response_model=GradingScaleResponse)
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
    "/subject-assignments",
    response_model=ClassSubjectTeacherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_subject(
    payload: ClassSubjectTeacherCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    response: Response,
) -> ClassSubjectTeacherResponse:
    response.headers["X-Deprecated-Endpoint"] = "subject-assignments"
    response.headers["Deprecation"] = "true"
    return await StudentAcademicService.assign_subject_to_class(db, current_admin.tenant_id, payload)


@tenant_admin_router.get("/subject-assignments", response_model=ClassSubjectTeacherListResponse)
async def list_subject_assignments(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    response: Response,
    class_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    teacher_id: UUID | None = Query(default=None),
    active_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> ClassSubjectTeacherListResponse:
    response.headers["X-Deprecated-Endpoint"] = "subject-assignments"
    response.headers["Deprecation"] = "true"
    items, total = await StudentAcademicService.list_class_subject_teachers(
        db,
        current_admin.tenant_id,
        skip=skip,
        limit=limit,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        active_only=active_only,
    )
    return ClassSubjectTeacherListResponse(items=items, total=total)


@tenant_admin_router.patch(
    "/subject-assignments/{assignment_id}",
    response_model=ClassSubjectTeacherResponse,
)
async def update_subject_assignment(
    assignment_id: UUID,
    payload: ClassSubjectTeacherUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    response: Response,
) -> ClassSubjectTeacherResponse:
    response.headers["X-Deprecated-Endpoint"] = "subject-assignments"
    response.headers["Deprecation"] = "true"
    return await StudentAcademicService.update_class_subject_teacher(
        db,
        current_admin.tenant_id,
        assignment_id,
        payload,
    )


@tenant_admin_router.post(
    "/teacher-assignments",
    response_model=TeacherAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher_assignment(
    payload: TeacherAssignmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    return await StudentAcademicService.create_teacher_assignment(
        db, current_admin.tenant_id, payload
    )


@tenant_admin_router.get("/teacher-assignments", response_model=TeacherAssignmentListResponse)
async def list_teacher_assignments_admin(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    class_id: UUID | None = Query(default=None),
    teacher_id: UUID | None = Query(default=None),
    active_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> TeacherAssignmentListResponse:
    items, total = await StudentAcademicService.list_teacher_assignment_responses(
        db,
        current_admin.tenant_id,
        class_id=class_id,
        teacher_id=teacher_id,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )
    return TeacherAssignmentListResponse(items=items, total=total)


@tenant_admin_router.patch(
    "/teacher-assignments/{assignment_id}/deactivate",
    response_model=TeacherAssignmentResponse,
)
async def deactivate_teacher_assignment(
    assignment_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    return await StudentAcademicService.deactivate_teacher_assignment(
        db, current_admin.tenant_id, assignment_id
    )


@tenant_admin_router.post(
    "/teacher-assignments/{assignment_id}/reassign",
    response_model=TeacherAssignmentResponse,
)
async def reassign_teacher_assignment(
    assignment_id: UUID,
    payload: TeacherAssignmentReassign,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherAssignmentResponse:
    return await StudentAcademicService.reassign_teacher_assignment(
        db, current_admin.tenant_id, assignment_id, payload
    )


@tenant_admin_router.post("/results", response_model=StudentSubjectResultResponse)
async def upsert_admin_result(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.upsert_student_result(db, current_admin, payload)


@tenant_admin_router.get("/results", response_model=StudentSubjectResultListResponse)
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


@tenant_admin_router.patch("/results/{result_id}/status", response_model=StudentSubjectResultResponse)
async def update_result_status(
    result_id: UUID,
    payload: StudentSubjectResultStatusUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.update_result_status(db, current_admin, result_id, payload)


@teacher_router.get("/assignments", response_model=TeacherAssignmentListResponse)
async def list_my_assignments(
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> TeacherAssignmentListResponse:
    items, total = await StudentAcademicService.list_teacher_assignment_responses(
        db,
        current_teacher.tenant_id,
        teacher_id=current_teacher.id,
        active_only=True,
    )
    return TeacherAssignmentListResponse(items=items, total=total)


@teacher_router.get("/sessions", response_model=AcademicSessionListResponse)
async def list_teacher_sessions(
    db: DbSession,
    current_teacher: CurrentTeacher,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AcademicSessionListResponse:
    items, total = await StudentAcademicService.list_academic_sessions(
        db,
        current_teacher.tenant_id,
        skip=skip,
        limit=limit,
    )
    return AcademicSessionListResponse(items=items, total=total)


@teacher_router.get("/terms", response_model=AcademicTermListResponse)
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


@teacher_router.post("/results", response_model=StudentSubjectResultResponse)
async def upsert_teacher_result(
    payload: StudentSubjectResultUpsert,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentSubjectResultResponse:
    return await StudentAcademicService.upsert_student_result(db, current_teacher, payload)


@teacher_router.get("/results", response_model=StudentSubjectResultListResponse)
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


@student_router.get("/results", response_model=StudentSubjectResultListResponse)
async def list_my_results(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentSubjectResultListResponse:
    items, _ = await StudentAcademicService.list_results(db, current_student)
    return _submitted_result_list(items)


@student_router.get("/subjects", response_model=StudentSubjectCardListResponse)
async def list_my_subject_cards(
    db: DbSession,
    current_student: CurrentStudent,
) -> StudentSubjectCardListResponse:
    response = await StudentAcademicService.list_student_subject_cards(db=db, actor=current_student)
    return _mask_unsubmitted_subject_cards(response)


@parent_router.get("/results", response_model=StudentSubjectResultListResponse)
async def list_child_results(
    student_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
) -> StudentSubjectResultListResponse:
    items, _ = await StudentAcademicService.list_results(
        db,
        current_parent,
        student_id=student_id,
    )
    return _submitted_result_list(items)
