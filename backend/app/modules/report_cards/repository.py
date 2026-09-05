import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.report_cards.models import (
    ReportCard,
    ReportCardStatus,
    ReportCardSubjectComponent,
    ReportCardSubjectLine,
)


class ReportCardRepository:
    @staticmethod
    async def create(db: AsyncSession, report_card: ReportCard) -> ReportCard:
        db.add(report_card)
        await db.flush()
        await db.refresh(report_card)
        return report_card

    @staticmethod
    async def create_line(db: AsyncSession, line: ReportCardSubjectLine) -> ReportCardSubjectLine:
        db.add(line)
        await db.flush()
        await db.refresh(line)
        return line

    @staticmethod
    async def create_component(
        db: AsyncSession, component: ReportCardSubjectComponent
    ) -> ReportCardSubjectComponent:
        db.add(component)
        await db.flush()
        return component

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        report_card_id: uuid.UUID,
    ) -> ReportCard | None:
        return (
            await db.execute(
                select(ReportCard).where(
                    ReportCard.tenant_id == tenant_id,
                    ReportCard.id == report_card_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_current_draft(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> ReportCard | None:
        return (
            await db.execute(
                select(ReportCard).where(
                    ReportCard.tenant_id == tenant_id,
                    ReportCard.student_id == student_id,
                    ReportCard.academic_session_id == academic_session_id,
                    ReportCard.academic_term_id == academic_term_id,
                    ReportCard.status == ReportCardStatus.DRAFT,
                    ReportCard.superseded_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_current_published(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> ReportCard | None:
        return (
            await db.execute(
                select(ReportCard).where(
                    ReportCard.tenant_id == tenant_id,
                    ReportCard.student_id == student_id,
                    ReportCard.academic_session_id == academic_session_id,
                    ReportCard.academic_term_id == academic_term_id,
                    ReportCard.status == ReportCardStatus.PUBLISHED,
                    ReportCard.superseded_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def next_version(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> int:
        value = (
            await db.execute(
                select(func.max(ReportCard.version)).where(
                    ReportCard.tenant_id == tenant_id,
                    ReportCard.student_id == student_id,
                    ReportCard.academic_session_id == academic_session_id,
                    ReportCard.academic_term_id == academic_term_id,
                )
            )
        ).scalar_one_or_none()
        return int(value or 0) + 1

    @staticmethod
    async def list_cards(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
        status: ReportCardStatus | None = None,
        is_outdated: bool | None = None,
        published_only: bool = False,
    ) -> tuple[list[ReportCard], int]:
        filters = [ReportCard.tenant_id == tenant_id]
        if published_only:
            filters.extend(
                [
                    ReportCard.status == ReportCardStatus.PUBLISHED,
                    ReportCard.superseded_at.is_(None),
                ]
            )
        elif status is not None:
            filters.append(ReportCard.status == status)
        if student_id is not None:
            filters.append(ReportCard.student_id == student_id)
        if class_id is not None:
            filters.append(ReportCard.class_id == class_id)
        if academic_session_id is not None:
            filters.append(ReportCard.academic_session_id == academic_session_id)
        if academic_term_id is not None:
            filters.append(ReportCard.academic_term_id == academic_term_id)
        if is_outdated is not None:
            filters.append(ReportCard.is_outdated.is_(is_outdated))

        total = (
            await db.execute(select(func.count()).select_from(ReportCard).where(*filters))
        ).scalar_one()
        rows = list(
            (
                await db.execute(
                    select(ReportCard)
                    .where(*filters)
                    .order_by(ReportCard.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            ).scalars()
        )
        return rows, int(total)

    @staticmethod
    async def list_lines(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        report_card_id: uuid.UUID,
    ) -> list[ReportCardSubjectLine]:
        return list(
            (
                await db.execute(
                    select(ReportCardSubjectLine)
                    .where(
                        ReportCardSubjectLine.tenant_id == tenant_id,
                        ReportCardSubjectLine.report_card_id == report_card_id,
                    )
                    .order_by(ReportCardSubjectLine.subject_name.asc())
                )
            ).scalars()
        )

    @staticmethod
    async def list_line_components_batch(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        line_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[ReportCardSubjectComponent]]:
        if not line_ids:
            return {}
        rows = list(
            (
                await db.execute(
                    select(ReportCardSubjectComponent)
                    .where(
                        ReportCardSubjectComponent.tenant_id == tenant_id,
                        ReportCardSubjectComponent.report_card_subject_line_id.in_(line_ids),
                    )
                    .order_by(
                        ReportCardSubjectComponent.report_card_subject_line_id.asc(),
                        ReportCardSubjectComponent.position.asc(),
                    )
                )
            ).scalars()
        )
        output: dict[uuid.UUID, list[ReportCardSubjectComponent]] = {}
        for row in rows:
            output.setdefault(row.report_card_subject_line_id, []).append(row)
        return output

    @staticmethod
    async def list_current_drafts_for_class_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ReportCard]:
        return list(
            (
                await db.execute(
                    select(ReportCard).where(
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.class_id == class_id,
                        ReportCard.academic_session_id == academic_session_id,
                        ReportCard.academic_term_id == academic_term_id,
                        ReportCard.status == ReportCardStatus.DRAFT,
                        ReportCard.superseded_at.is_(None),
                    )
                )
            ).scalars()
        )

    @staticmethod
    async def list_current_cards_for_class_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ReportCard]:
        return list(
            (
                await db.execute(
                    select(ReportCard).where(
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.class_id == class_id,
                        ReportCard.academic_session_id == academic_session_id,
                        ReportCard.academic_term_id == academic_term_id,
                        ReportCard.superseded_at.is_(None),
                    )
                )
            ).scalars()
        )

    @staticmethod
    async def mark_outdated_for_student_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        cards = list(
            (
                await db.execute(
                    select(ReportCard).where(
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.student_id == student_id,
                        ReportCard.academic_session_id == academic_session_id,
                        ReportCard.academic_term_id == academic_term_id,
                        ReportCard.superseded_at.is_(None),
                    )
                )
            ).scalars()
        )
        for card in cards:
            card.is_outdated = True
            db.add(card)
        await db.flush()

    @staticmethod
    async def save(db: AsyncSession, report_card: ReportCard) -> ReportCard:
        db.add(report_card)
        await db.flush()
        await db.refresh(report_card)
        return report_card
