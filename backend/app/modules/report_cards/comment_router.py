"""HTTP boundary for personal comment templates and teacher term comments."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_teacher, get_current_tenant_admin
from app.modules.report_cards.comment_models import CommentTemplateOwnerType
from app.modules.report_cards.comment_schemas import (
    CommentTemplateListResponse,
    CommentTemplateResponse,
    CommentTemplateUpdate,
    CommentTemplateWrite,
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
    payload: CommentTemplateWrite,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CommentTemplateResponse:
    return await ReportCommentService.create_template(db, actor=current_admin, payload=payload)


@admin_template_router.patch("/{template_id}", response_model=CommentTemplateResponse)
async def update_admin_comment_template(
    template_id: UUID,
    payload: CommentTemplateUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> CommentTemplateResponse:
    return await ReportCommentService.update_template(
        db,
        actor=current_admin,
        template_id=template_id,
        payload=payload,
    )


@admin_template_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_comment_template(
    template_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> Response:
    await ReportCommentService.delete_template(
        db, actor=current_admin, template_id=template_id
    )
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
    payload: CommentTemplateWrite,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> CommentTemplateResponse:
    return await ReportCommentService.create_template(db, actor=current_teacher, payload=payload)


@teacher_template_router.patch("/{template_id}", response_model=CommentTemplateResponse)
async def update_teacher_comment_template(
    template_id: UUID,
    payload: CommentTemplateUpdate,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> CommentTemplateResponse:
    return await ReportCommentService.update_template(
        db,
        actor=current_teacher,
        template_id=template_id,
        payload=payload,
    )


@teacher_template_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_teacher_comment_template(
    template_id: UUID,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> Response:
    await ReportCommentService.delete_template(
        db, actor=current_teacher, template_id=template_id
    )
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
    return await ReportCommentService.save_teacher_comment(
        db,
        teacher=current_teacher,
        student_id=student_id,
        payload=payload,
        submit=True,
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
    return await ReportCommentService.create_override(
        db, admin=current_admin, payload=payload
    )
