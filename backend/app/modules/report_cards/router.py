from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import HTMLResponse

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_onboarded_student,
    get_current_parent,
    get_current_tenant_admin,
)
from app.modules.parents.models import Parent
from app.modules.report_cards.schemas import (
    ReportCardBulkGenerateResponse,
    ReportCardClassOverviewResponse,
    ReportCardCommentsUpdate,
    ReportCardGenerateRequest,
    ReportCardListResponse,
    ReportCardResponse,
)
from app.modules.report_cards.models import ReportCardStatus
from app.modules.report_cards.service import ReportCardService
from app.modules.students.models import Student
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin

REPORT_CARD_HTML_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data: https:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
}
REPORT_CARD_DATA_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _prevent_report_card_cache(response: Response) -> None:
    for key, value in REPORT_CARD_DATA_HEADERS.items():
        response.headers[key] = value


tenant_admin_router = APIRouter(
    prefix="/tenant-admin/academic/report-cards",
    tags=["Tenant Admin Report Cards"],
)
parent_router = APIRouter(
    prefix="/parents/me/children/{student_id}/academic/report-cards",
    tags=["Parent Report Cards"],
)
student_router = APIRouter(
    prefix="/students/me/academic/report-cards",
    tags=["Student Report Cards"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_onboarded_student)]


@tenant_admin_router.get("", response_model=ReportCardListResponse)
async def list_report_cards(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    response: Response,
    student_id: UUID | None = Query(default=None),
    class_id: UUID | None = Query(default=None),
    academic_session_id: UUID | None = Query(default=None),
    academic_term_id: UUID | None = Query(default=None),
    status: ReportCardStatus | None = Query(default=None),
    is_outdated: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> ReportCardListResponse:
    _prevent_report_card_cache(response)
    items, total = await ReportCardService.list_cards(
        db,
        current_admin,
        student_id=student_id,
        class_id=class_id,
        academic_session_id=academic_session_id,
        academic_term_id=academic_term_id,
        status=status,
        is_outdated=is_outdated,
        skip=skip,
        limit=limit,
    )
    return ReportCardListResponse(items=items, total=total)


@tenant_admin_router.get("/{report_card_id}", response_model=ReportCardResponse)
async def get_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    response: Response,
) -> ReportCardResponse:
    _prevent_report_card_cache(response)
    return await ReportCardService.get(db, current_admin, report_card_id)


@tenant_admin_router.post("/{report_card_id}/regenerate", response_model=ReportCardResponse)
async def regenerate_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ReportCardResponse:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_admin.tenant_id,
        feature=FeatureCode.REPORT_CARDS,
    )
    return await ReportCardService.regenerate(db, current_admin, report_card_id)


@tenant_admin_router.patch("/{report_card_id}/comments", response_model=ReportCardResponse)
async def update_report_card_comments(
    report_card_id: UUID,
    payload: ReportCardCommentsUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ReportCardResponse:
    return await ReportCardService.update_comments(db, current_admin, report_card_id, payload)


@tenant_admin_router.post("/{report_card_id}/publish", response_model=ReportCardResponse)
async def publish_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ReportCardResponse:
    return await ReportCardService.publish(db, current_admin, report_card_id)


@tenant_admin_router.get("/{report_card_id}/print", response_class=HTMLResponse)
async def print_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> HTMLResponse:
    return HTMLResponse(
        await ReportCardService.render_html(db, current_admin, report_card_id),
        headers=REPORT_CARD_HTML_HEADERS,
    )


@tenant_admin_router.get("/{report_card_id}/download", response_class=HTMLResponse)
async def download_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> HTMLResponse:
    return HTMLResponse(
        await ReportCardService.render_html(db, current_admin, report_card_id),
        headers=REPORT_CARD_HTML_HEADERS,
    )


@parent_router.get("", response_model=ReportCardListResponse)
async def list_child_report_cards(
    student_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
    response: Response,
) -> ReportCardListResponse:
    _prevent_report_card_cache(response)
    items, total = await ReportCardService.list_cards(
        db,
        current_parent,
        student_id=student_id,
    )
    return ReportCardListResponse(items=items, total=total)


@student_router.get("", response_model=ReportCardListResponse)
async def list_my_report_cards(
    db: DbSession,
    current_student: CurrentStudent,
    response: Response,
) -> ReportCardListResponse:
    _prevent_report_card_cache(response)
    items, total = await ReportCardService.list_cards(db, current_student)
    return ReportCardListResponse(items=items, total=total)


@student_router.get("/{report_card_id}", response_model=ReportCardResponse)
async def get_my_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_student: CurrentStudent,
    response: Response,
) -> ReportCardResponse:
    _prevent_report_card_cache(response)
    return await ReportCardService.get(db, current_student, report_card_id)


@student_router.get("/{report_card_id}/print", response_class=HTMLResponse)
async def print_my_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_student: CurrentStudent,
) -> HTMLResponse:
    return HTMLResponse(
        await ReportCardService.render_html(db, current_student, report_card_id),
        headers=REPORT_CARD_HTML_HEADERS,
    )


@parent_router.get("/{report_card_id}", response_model=ReportCardResponse)
async def get_child_report_card(
    student_id: UUID,
    report_card_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
    response: Response,
) -> ReportCardResponse:
    _prevent_report_card_cache(response)
    card = await ReportCardService.get(db, current_parent, report_card_id)
    if card.student_id != student_id:
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("Report card does not belong to this child.")
    return card


@parent_router.get("/{report_card_id}/print", response_class=HTMLResponse)
async def print_child_report_card(
    report_card_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
) -> HTMLResponse:
    return HTMLResponse(
        await ReportCardService.render_html(db, current_parent, report_card_id),
        headers=REPORT_CARD_HTML_HEADERS,
    )
