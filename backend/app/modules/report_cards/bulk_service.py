from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.report_cards.bulk_schemas import (
    BulkActionResponse,
    BulkActionSkippedItem,
    ReportCardBulkArchiveRequest,
    ReportCardBulkPublishRequest,
    ReportCardBulkReopenRequest,
)
from app.modules.report_cards.models import ReportCardStatus
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.models import (
    AcademicLifecycleAudit,
    AcademicResultStatus,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.tenant_admins.models import TenantAdmin


class BulkReportCardService:
    @staticmethod
    async def _scope_cards(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: (
            ReportCardBulkPublishRequest
            | ReportCardBulkArchiveRequest
            | ReportCardBulkReopenRequest
        ),
    ):
        return await ReportCardRepository.list_active_cards_for_class_period(
            db,
            actor.tenant_id,
            payload.class_id,
            payload.academic_session_id,
            payload.academic_term_id,
        )

    @staticmethod
    async def _audit(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        report_card_id: uuid.UUID,
        action: str,
        previous_status: ReportCardStatus,
        new_status: ReportCardStatus,
        reason: str | None = None,
    ) -> None:
        await StudentAcademicRepository.add_academic_lifecycle_audit(
            db,
            AcademicLifecycleAudit(
                tenant_id=actor.tenant_id,
                entity_type="report_card",
                entity_id=report_card_id,
                action=action,
                previous_status=previous_status.value,
                new_status=new_status.value,
                acting_admin_id=actor.id,
                reason=reason,
            ),
        )

    @staticmethod
    async def _validate_publishable(
        db: AsyncSession,
        actor: TenantAdmin,
        card,
    ) -> None:
        if card.status != ReportCardStatus.DRAFT:
            raise BadRequestException("Only draft report cards can be published.")
        if card.superseded_at is not None:
            raise BadRequestException("Superseded report cards cannot be published.")
        if card.is_outdated:
            raise BadRequestException(
                "Outdated report cards must be regenerated before publication."
            )

        lines = await ReportCardRepository.list_lines(
            db,
            actor.tenant_id,
            card.id,
        )
        expected = await ReportCardService._expected_curriculum_subjects(
            db, actor.tenant_id, card.student_id, card.academic_term_id
        )
        expected_subject_ids = {item.subject_id for item in expected}
        line_subject_ids = {line.subject_id for line in lines}
        if line_subject_ids != expected_subject_ids:
            raise BadRequestException("Report card is missing expected subject lines.")

        for line in lines:
            result = await StudentAcademicRepository.get_result_by_id(
                db,
                actor.tenant_id,
                line.student_subject_result_id,
            )
            if result is None or result.status != AcademicResultStatus.LOCKED:
                raise BadRequestException(
                    "Report card source scores must be locked before publication."
                )

    @staticmethod
    async def publish(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkPublishRequest,
    ) -> BulkActionResponse:
        cards = await BulkReportCardService._scope_cards(db, actor, payload)
        processed = 0
        skipped: list[BulkActionSkippedItem] = []

        for card in cards:
            try:
                async with db.begin_nested():
                    await BulkReportCardService._validate_publishable(
                        db,
                        actor,
                        card,
                    )
                    previous = card.status
                    card.status = ReportCardStatus.PUBLISHED
                    card.published_at = datetime.now(timezone.utc)
                    card.published_by = actor.id
                    await ReportCardRepository.save(db, card)
                    await BulkReportCardService._audit(
                        db,
                        actor=actor,
                        report_card_id=card.id,
                        action="bulk_publish",
                        previous_status=previous,
                        new_status=ReportCardStatus.PUBLISHED,
                    )
                processed += 1
            except Exception as exc:
                skipped.append(BulkActionSkippedItem(id=card.id, reason=str(exc)))

        await db.commit()
        return BulkActionResponse(
            matched=len(cards),
            processed=processed,
            skipped=skipped,
        )

    @staticmethod
    async def archive(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkArchiveRequest,
    ) -> BulkActionResponse:
        cards = await BulkReportCardService._scope_cards(db, actor, payload)
        processed = 0
        skipped: list[BulkActionSkippedItem] = []

        for card in cards:
            if card.status == ReportCardStatus.ARCHIVED:
                skipped.append(
                    BulkActionSkippedItem(
                        id=card.id,
                        reason="Report card is already archived.",
                    )
                )
                continue
            try:
                async with db.begin_nested():
                    previous = card.status
                    card.status = ReportCardStatus.ARCHIVED
                    await ReportCardRepository.save(db, card)
                    await BulkReportCardService._audit(
                        db,
                        actor=actor,
                        report_card_id=card.id,
                        action="bulk_archive",
                        previous_status=previous,
                        new_status=ReportCardStatus.ARCHIVED,
                        reason=payload.reason,
                    )
                processed += 1
            except Exception as exc:
                skipped.append(BulkActionSkippedItem(id=card.id, reason=str(exc)))

        await db.commit()
        return BulkActionResponse(
            matched=len(cards),
            processed=processed,
            skipped=skipped,
        )

    @staticmethod
    async def reopen(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkReopenRequest,
    ) -> BulkActionResponse:
        cards = await BulkReportCardService._scope_cards(db, actor, payload)
        processed = 0
        skipped: list[BulkActionSkippedItem] = []

        for card in cards:
            if card.status != ReportCardStatus.ARCHIVED:
                skipped.append(
                    BulkActionSkippedItem(
                        id=card.id,
                        reason=(
                            "Only archived report cards can be reopened; "
                            f"current status is {card.status.value}."
                        ),
                    )
                )
                continue
            if card.superseded_at is not None:
                skipped.append(
                    BulkActionSkippedItem(
                        id=card.id,
                        reason=("Superseded historical versions cannot be reopened."),
                    )
                )
                continue
            try:
                async with db.begin_nested():
                    previous = card.status
                    card.status = ReportCardStatus.DRAFT
                    card.published_at = None
                    card.published_by = None
                    await ReportCardRepository.save(db, card)
                    await BulkReportCardService._audit(
                        db,
                        actor=actor,
                        report_card_id=card.id,
                        action="bulk_reopen",
                        previous_status=previous,
                        new_status=ReportCardStatus.DRAFT,
                        reason=payload.reason,
                    )
                processed += 1
            except Exception as exc:
                skipped.append(BulkActionSkippedItem(id=card.id, reason=str(exc)))

        await db.commit()
        return BulkActionResponse(
            matched=len(cards),
            processed=processed,
            skipped=skipped,
        )
