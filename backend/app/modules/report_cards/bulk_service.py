from __future__ import annotations

import uuid

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
from app.modules.student_academics.models import AcademicLifecycleAudit
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.tenant_admins.models import TenantAdmin


class BulkReportCardService:
    @staticmethod
    async def _scope_cards(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkPublishRequest
        | ReportCardBulkArchiveRequest
        | ReportCardBulkReopenRequest,
    ):
        return await ReportCardRepository.list_current_cards_for_class_period(
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
    async def publish(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkPublishRequest,
    ) -> BulkActionResponse:
        cards = await BulkReportCardService._scope_cards(db, actor, payload)
        drafts = [card for card in cards if card.status == ReportCardStatus.DRAFT]
        processed = 0
        skipped: list[BulkActionSkippedItem] = []
        for card in drafts:
            try:
                previous = card.status
                await ReportCardService.publish(db, actor, card.id)
                await BulkReportCardService._audit(
                    db,
                    actor=actor,
                    report_card_id=card.id,
                    action="bulk_publish",
                    previous_status=previous,
                    new_status=ReportCardStatus.PUBLISHED,
                )
                await db.commit()
                processed += 1
            except Exception as exc:
                await db.rollback()
                skipped.append(BulkActionSkippedItem(id=card.id, reason=str(exc)))
        return BulkActionResponse(
            matched=len(drafts),
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
            if card.status == ReportCardStatus.PUBLISHED:
                skipped.append(
                    BulkActionSkippedItem(
                        id=card.id,
                        reason="Published report revisions are immutable and cannot be archived in place.",
                    )
                )
                continue
            if card.status == ReportCardStatus.ARCHIVED:
                skipped.append(
                    BulkActionSkippedItem(id=card.id, reason="Report card is already archived.")
                )
                continue
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
        await db.commit()
        return BulkActionResponse(matched=len(cards), processed=processed, skipped=skipped)

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
                        reason=f"Only archived drafts can be reopened; current status is {card.status.value}.",
                    )
                )
                continue
            if card.superseded_at is not None or card.published_at is not None:
                skipped.append(
                    BulkActionSkippedItem(
                        id=card.id,
                        reason="Historical or previously published revisions cannot be reopened.",
                    )
                )
                continue
            current_draft = await ReportCardRepository.get_current_draft(
                db,
                actor.tenant_id,
                card.student_id,
                card.academic_session_id,
                card.academic_term_id,
            )
            if current_draft is not None and current_draft.id != card.id:
                skipped.append(
                    BulkActionSkippedItem(id=card.id, reason="A current draft already exists.")
                )
                continue
            previous = card.status
            card.status = ReportCardStatus.DRAFT
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
        await db.commit()
        return BulkActionResponse(matched=len(cards), processed=processed, skipped=skipped)
