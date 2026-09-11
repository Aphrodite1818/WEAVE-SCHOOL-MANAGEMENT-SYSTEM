from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
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


BULK_REPORT_LIFECYCLE_BATCH_SIZE = 50


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
    async def _scope_card_ids(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkPublishRequest
        | ReportCardBulkArchiveRequest
        | ReportCardBulkReopenRequest,
    ) -> list[uuid.UUID]:
        """Freeze the target set so commits cannot cause offset drift."""

        cards = await BulkReportCardService._scope_cards(db, actor, payload)
        return [card.id for card in cards]

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
        card_ids = await BulkReportCardService._scope_card_ids(db, actor, payload)
        matched = 0
        processed = 0
        skipped: list[BulkActionSkippedItem] = []

        for start in range(0, len(card_ids), BULK_REPORT_LIFECYCLE_BATCH_SIZE):
            batch_ids = card_ids[start : start + BULK_REPORT_LIFECYCLE_BATCH_SIZE]
            for card_id in batch_ids:
                card = await ReportCardRepository.get_by_id(db, actor.tenant_id, card_id)
                if card is None or card.status != ReportCardStatus.DRAFT:
                    continue
                matched += 1
                try:
                    async with db.begin_nested():
                        previous = card.status
                        await ReportCardService.publish(
                            db,
                            actor,
                            card.id,
                            commit=False,
                        )
                        await BulkReportCardService._audit(
                            db,
                            actor=actor,
                            report_card_id=card.id,
                            action="bulk_publish",
                            previous_status=previous,
                            new_status=ReportCardStatus.PUBLISHED,
                        )
                    processed += 1
                except (BadRequestException, NotFoundException) as exc:
                    skipped.append(BulkActionSkippedItem(id=card_id, reason=str(exc)))
            await db.commit()

        return BulkActionResponse(
            matched=matched,
            processed=processed,
            skipped=skipped,
        )

    @staticmethod
    async def archive(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkArchiveRequest,
    ) -> BulkActionResponse:
        card_ids = await BulkReportCardService._scope_card_ids(db, actor, payload)
        processed = 0
        skipped: list[BulkActionSkippedItem] = []

        for start in range(0, len(card_ids), BULK_REPORT_LIFECYCLE_BATCH_SIZE):
            batch_ids = card_ids[start : start + BULK_REPORT_LIFECYCLE_BATCH_SIZE]
            for card_id in batch_ids:
                card = await ReportCardRepository.get_by_id(db, actor.tenant_id, card_id)
                if card is None:
                    skipped.append(
                        BulkActionSkippedItem(id=card_id, reason="Report card no longer exists.")
                    )
                    continue
                if card.status == ReportCardStatus.PUBLISHED:
                    skipped.append(
                        BulkActionSkippedItem(
                            id=card.id,
                            reason=(
                                "Published report revisions are immutable and cannot be "
                                "archived in place."
                            ),
                        )
                    )
                    continue
                if card.status == ReportCardStatus.ARCHIVED:
                    skipped.append(
                        BulkActionSkippedItem(
                            id=card.id,
                            reason="Report card is already archived.",
                        )
                    )
                    continue

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
            await db.commit()

        return BulkActionResponse(
            matched=len(card_ids),
            processed=processed,
            skipped=skipped,
        )

    @staticmethod
    async def reopen(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardBulkReopenRequest,
    ) -> BulkActionResponse:
        card_ids = await BulkReportCardService._scope_card_ids(db, actor, payload)
        processed = 0
        skipped: list[BulkActionSkippedItem] = []

        for start in range(0, len(card_ids), BULK_REPORT_LIFECYCLE_BATCH_SIZE):
            batch_ids = card_ids[start : start + BULK_REPORT_LIFECYCLE_BATCH_SIZE]
            for card_id in batch_ids:
                card = await ReportCardRepository.get_by_id(db, actor.tenant_id, card_id)
                if card is None:
                    skipped.append(
                        BulkActionSkippedItem(id=card_id, reason="Report card no longer exists.")
                    )
                    continue
                if card.status != ReportCardStatus.ARCHIVED:
                    skipped.append(
                        BulkActionSkippedItem(
                            id=card.id,
                            reason=(
                                "Only archived drafts can be reopened; current status is "
                                f"{card.status.value}."
                            ),
                        )
                    )
                    continue
                if card.superseded_at is not None or card.published_at is not None:
                    skipped.append(
                        BulkActionSkippedItem(
                            id=card.id,
                            reason=(
                                "Historical or previously published revisions cannot be reopened."
                            ),
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
                        BulkActionSkippedItem(
                            id=card.id,
                            reason="A current draft already exists.",
                        )
                    )
                    continue

                async with db.begin_nested():
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

        return BulkActionResponse(
            matched=len(card_ids),
            processed=processed,
            skipped=skipped,
        )
