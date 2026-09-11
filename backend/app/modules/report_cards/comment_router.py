"""HTTP boundary for personal comment templates and teacher term comments."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_teacher, get_current_tenant_admin
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.report_cards.comment_audit_service import TeacherCommentAuditService
from app.modules.report_cards.comment_models import (
    CommentTemplateOwnerType,
    CommentTemplateStatus,
)
from app.modules.report_cards.comment_schemas import (
    CommentTemplateListResponse,
    CommentTemplateResponse,
    CommentTemplateUpdate,
    CommentTemplateWrite,
    PersonalCommentTemplateCreate,
    PersonalCommentTemplateUpdate,
    TeacherCommentDashboardSummary,
    TeacherCommentOverrideRequest,
    TeacherCommentOverrideResponse,
    TeacherCommentResponse,
    TeacherCommentWrite,
    TeacherStudentCommentListResponse,
)
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.comment_summary_service import TeacherCommentSummaryService
from app.modules.teachers.models import TeacherMembership
from app.modules.tenant_admins.models import TenantAdmin

admin_template_router = APIRouter(
    prefix="/tenant-admin/academic/comment-templates",
    tags=["Tenant Admin Comment Templates"],
)
teacher_template_router = APIRouter(
    prefix="/teachers/me/comment-templates",
    tags=["Teacher Comment Templates"],
)
teacher_comment_router = APIRouter(
    prefix="/teachers/me/student-comments",
    tags=["Teacher Student Comments"],
)
admin_override_router = APIRouter(
    prefix="/tenant-admin/academic/report-cards/teacher-comment-overrides",
    tags=["Tenant Admin Report Cards"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[TeacherMembership, Depends(get_current_teacher)]
TemplateActor: TypeAlias = TenantAdmin | TeacherMembership


def _owner_type(actor: TemplateActor) -> CommentTemplateOwnerType:
    return (
        CommentTemplateOwnerType.TENANT_ADMIN
        if isinstance(actor, TenantAdmin)
        else CommentTemplateOwnerType.TEACHER
    )


def _status_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _derived_internal_name(text: str) -> str:
    """Keep the legacy DB column internal; actors manage only comment text."""

    compact = " ".join(str(text).split())
    return compact[:120] or "Comment"


def _single_grade_id(template: CommentTemplateResponse) -> UUID:
    grade_ids = list(template.grading_scale_ids or [])
    if len(grade_ids) != 1:
        raise ConflictException(
            "This saved comment uses an obsolete multi-grade mapping. Archive it and create one comment per grade."
        )
    return grade_ids[0]


def _is_default(template: CommentTemplateResponse, grade_id: UUID) -> bool:
    return grade_id in set(template.default_grading_scale_ids or [])


async def _owned_templates(
    db: DbSession,
    actor: TemplateActor,
) -> list[CommentTemplateResponse]:
    return await ReportCommentService.list_templates(
        db,
        tenant_id=actor.tenant_id,
        owner_type=_owner_type(actor),
        owner_id=actor.id,
        include_archived=True,
    )


async def _find_template(
    db: DbSession,
    actor: TemplateActor,
    template_id: UUID,
) -> CommentTemplateResponse:
    for item in await _owned_templates(db, actor):
        if item.id == template_id:
            return item
    raise NotFoundException("Comment template not found.")


async def _create_personal_comment(
    db: DbSession,
    actor: TemplateActor,
    payload: PersonalCommentTemplateCreate,
) -> CommentTemplateResponse:
    templates = await _owned_templates(db, actor)
    active_for_grade = [
        item
        for item in templates
        if _status_value(item.status) == CommentTemplateStatus.ACTIVE.value
        and payload.grading_scale_id in set(item.grading_scale_ids or [])
    ]
    has_default = any(_is_default(item, payload.grading_scale_id) for item in active_for_grade)
    make_default = payload.is_default or not has_default
    return await ReportCommentService.create_template(
        db,
        actor=actor,
        payload=CommentTemplateWrite(
            name=_derived_internal_name(payload.text),
            text=payload.text,
            grading_scale_ids=[payload.grading_scale_id],
            default_grading_scale_ids=([payload.grading_scale_id] if make_default else []),
        ),
    )


async def _update_personal_comment(
    db: DbSession,
    actor: TemplateActor,
    template_id: UUID,
    payload: PersonalCommentTemplateUpdate,
) -> CommentTemplateResponse:
    current = await _find_template(db, actor, template_id)
    grade_id = _single_grade_id(current)
    templates = await _owned_templates(db, actor)
    other_active = [
        item
        for item in templates
        if item.id != current.id
        and _status_value(item.status) == CommentTemplateStatus.ACTIVE.value
        and grade_id in set(item.grading_scale_ids or [])
    ]
    other_default = any(_is_default(item, grade_id) for item in other_active)
    current_default = _is_default(current, grade_id)
    target_status = payload.status or CommentTemplateStatus(_status_value(current.status))

    if target_status != CommentTemplateStatus.ACTIVE and payload.is_default is True:
        raise ConflictException("Only an active comment can be the default for a grade.")

    if target_status != CommentTemplateStatus.ACTIVE:
        if current_default and other_active and not other_default:
            raise ConflictException(
                "Choose another active comment as the default for this grade before deactivating or archiving the current default."
            )
        target_default = False
    elif payload.is_default is True:
        target_default = True
    elif payload.is_default is False and current_default:
        raise ConflictException(
            "A grade must keep one default comment. Make another comment the default instead."
        )
    else:
        target_default = current_default
        if not target_default and not other_default:
            # First/only active comment for a grade always becomes its default.
            target_default = True

    internal = CommentTemplateUpdate(
        name=(
            _derived_internal_name(payload.text)
            if payload.text is not None and target_status != CommentTemplateStatus.ARCHIVED
            else None
        ),
        text=(
            payload.text
            if payload.text is not None and target_status != CommentTemplateStatus.ARCHIVED
            else None
        ),
        status=payload.status,
        grading_scale_ids=[grade_id],
        default_grading_scale_ids=[grade_id] if target_default else [],
    )
    return await ReportCommentService.update_template(
        db,
        actor=actor,
        template_id=template_id,
        payload=internal,
    )


async def _delete_personal_comment(
    db: DbSession,
    actor: TemplateActor,
    template_id: UUID,
) -> None:
    current = await _find_template(db, actor, template_id)
    grade_id = _single_grade_id(current)
    if _status_value(current.status) == CommentTemplateStatus.ACTIVE.value and _is_default(
        current, grade_id
    ):
        other_active = [
            item
            for item in await _owned_templates(db, actor)
            if item.id != current.id
            and _status_value(item.status) == CommentTemplateStatus.ACTIVE.value
            and grade_id in set(item.grading_scale_ids or [])
        ]
        if other_active:
            raise ConflictException(
                "Choose another active comment as the default for this grade before deleting the current default."
            )
    await ReportCommentService.delete_template(db, actor=actor, template_id=template_id)


async def _ensure_teacher_comment_ready(
    db: DbSession,
    teacher: TeacherMembership,
    student_id: UUID,
    payload: TeacherCommentWrite,
) -> None:
    ready, _, grading_scale = await ReportCommentService._academic_readiness(
        db,
        tenant_id=teacher.tenant_id,
        student_id=student_id,
        academic_session_id=payload.academic_session_id,
        academic_term_id=payload.academic_term_id,
    )
    if not ready or grading_scale is None:
        raise BadRequestException(
            "Class-teacher comment work begins after all expected results are finalized and locked."
        )
    if payload.source_template_id is None:
        return
    template = await _find_template(db, teacher, payload.source_template_id)
    if _status_value(template.status) != CommentTemplateStatus.ACTIVE.value:
        raise BadRequestException("Inactive or archived comments cannot be selected.")
    if _single_grade_id(template) != grading_scale.id:
        raise BadRequestException(
            f"The selected saved comment is not assigned to Grade {grading_scale.grade}."
        )


@admin_template_router.get("", response_model=CommentTemplateListResponse)
async def list_admin_comment_templates(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    include_archived: bool = Query(default=False),
) -> CommentTemplateListResponse:
    items = await ReportCommentService.list_templates(
        db,
        tenant_id=current_admin.tenant_id,
        owner_type=CommentTemplateOwnerType.TENANT_ADMIN,
        owner_id=current_admin.id,
        include_archived=include_archived,
    )
    return CommentTemplateListResponse(items=items, total=len(items))


@admin_template_router.post(
    "",
    response_model=CommentTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_comment_template(
    payload: PersonalCommentTemplateCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CommentTemplateResponse:
    return await _create_personal_comment(db, current_admin, payload)


@admin_template_router.patch("/{template_id}", response_model=CommentTemplateResponse)
async def update_admin_comment_template(
    template_id: UUID,
    payload: PersonalCommentTemplateUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CommentTemplateResponse:
    return await _update_personal_comment(db, current_admin, template_id, payload)


@admin_template_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_comment_template(
    template_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> Response:
    await _delete_personal_comment(db, current_admin, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@teacher_template_router.get("", response_model=CommentTemplateListResponse)
async def list_teacher_comment_templates(
    db: DbSession,
    current_teacher: CurrentTeacher,
    include_archived: bool = Query(default=False),
) -> CommentTemplateListResponse:
    items = await ReportCommentService.list_templates(
        db,
        tenant_id=current_teacher.tenant_id,
        owner_type=CommentTemplateOwnerType.TEACHER,
        owner_id=current_teacher.id,
        include_archived=include_archived,
    )
    return CommentTemplateListResponse(items=items, total=len(items))


@teacher_template_router.post(
    "",
    response_model=CommentTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher_comment_template(
    payload: PersonalCommentTemplateCreate,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> CommentTemplateResponse:
    return await _create_personal_comment(db, current_teacher, payload)


@teacher_template_router.patch("/{template_id}", response_model=CommentTemplateResponse)
async def update_teacher_comment_template(
    template_id: UUID,
    payload: PersonalCommentTemplateUpdate,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> CommentTemplateResponse:
    return await _update_personal_comment(db, current_teacher, template_id, payload)


@teacher_template_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_teacher_comment_template(
    template_id: UUID,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> Response:
    await _delete_personal_comment(db, current_teacher, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@teacher_comment_router.get(
    "/summary",
    response_model=TeacherCommentDashboardSummary,
)
async def teacher_comment_summary(
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> TeacherCommentDashboardSummary:
    return await TeacherCommentSummaryService.build(db, teacher=current_teacher)


@teacher_comment_router.get("", response_model=TeacherStudentCommentListResponse)
async def list_teacher_student_comments(
    db: DbSession,
    current_teacher: CurrentTeacher,
    class_id: UUID = Query(...),
    academic_session_id: UUID = Query(...),
    academic_term_id: UUID = Query(...),
) -> TeacherStudentCommentListResponse:
    return await ReportCommentService.list_teacher_students(
        db,
        teacher=current_teacher,
        class_id=class_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
    )


@teacher_comment_router.put("/{student_id}/draft", response_model=TeacherCommentResponse)
async def save_teacher_comment_draft(
    student_id: UUID,
    payload: TeacherCommentWrite,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> TeacherCommentResponse:
    await _ensure_teacher_comment_ready(db, current_teacher, student_id, payload)
    return await ReportCommentService.save_teacher_comment(
        db,
        teacher=current_teacher,
        student_id=student_id,
        payload=payload,
        submit=False,
    )


@teacher_comment_router.post("/{student_id}/submit", response_model=TeacherCommentResponse)
async def submit_teacher_comment(
    student_id: UUID,
    payload: TeacherCommentWrite,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> TeacherCommentResponse:
    await _ensure_teacher_comment_ready(db, current_teacher, student_id, payload)
    return await ReportCommentService.save_teacher_comment(
        db,
        teacher=current_teacher,
        student_id=student_id,
        payload=payload,
        submit=True,
    )


@admin_override_router.get("", response_model=list[TeacherCommentOverrideResponse])
async def list_teacher_comment_overrides(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    student_id: UUID = Query(...),
    academic_session_id: UUID = Query(...),
    academic_term_id: UUID = Query(...),
) -> list[TeacherCommentOverrideResponse]:
    """Return append-only override history for one student-period context."""

    return await TeacherCommentAuditService.list_overrides(
        db,
        admin=current_admin,
        student_id=student_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
    )


@admin_override_router.post(
    "",
    response_model=TeacherCommentOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
async def override_teacher_comment(
    payload: TeacherCommentOverrideRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TeacherCommentOverrideResponse:
    return await ReportCommentService.create_override(db, admin=current_admin, payload=payload)
