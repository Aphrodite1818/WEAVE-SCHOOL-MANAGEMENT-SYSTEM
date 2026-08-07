import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.report_cards.models import ReportCard, ReportCardSubjectLine
from app.modules.report_cards.models import ReportCardStatus


class ReportCardRepository:
    @staticmethod
    async def create(db: AsyncSession, report_card: ReportCard) -> ReportCard:
        db.add(report_card)
        await db.flush()
        await db.refresh(report_card)
        return report_card

    @staticmethod
    async def create_line(
        db: AsyncSession, line: ReportCardSubjectLine
    ) -> ReportCardSubjectLine:
        db.add(line)
        await db.flush()
        await db.refresh(line)
        return line

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        report_card_id: uuid.UUID,
    ) -> ReportCard | None:
        result = await db.execute(
            select(ReportCard).where(
                ReportCard.tenant_id == tenant_id,
                ReportCard.id == report_card_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_student_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> ReportCard | None:
        result = await db.execute(
            select(ReportCard).where(
                ReportCard.tenant_id == tenant_id,
                ReportCard.student_id == student_id,
                ReportCard.academic_session_id == academic_session_id,
                ReportCard.academic_term_id == academic_term_id,
                ReportCard.superseded_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

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
        filters = [
            ReportCard.tenant_id == tenant_id,
            ReportCard.superseded_at.is_(None),
        ]
        if student_id is not None:
            filters.append(ReportCard.student_id == student_id)
        if class_id is not None:
            filters.append(ReportCard.class_id == class_id)
        if academic_session_id is not None:
            filters.append(ReportCard.academic_session_id == academic_session_id)
        if academic_term_id is not None:
            filters.append(ReportCard.academic_term_id == academic_term_id)
        if status is not None:
            filters.append(ReportCard.status == status)
        if is_outdated is not None:
            filters.append(ReportCard.is_outdated.is_(is_outdated))
        if published_only:
            filters.append(ReportCard.status == ReportCardStatus.PUBLISHED)

        total = (
            await db.execute(
                select(func.count()).select_from(ReportCard).where(*filters)
            )
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    select(ReportCard)
                    .where(*filters)
                    .order_by(ReportCard.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    @staticmethod
    async def list_lines(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        report_card_id: uuid.UUID,
    ) -> list[ReportCardSubjectLine]:
        rows = (
            (
                await db.execute(
                    select(ReportCardSubjectLine)
                    .where(
                        ReportCardSubjectLine.tenant_id == tenant_id,
                        ReportCardSubjectLine.report_card_id == report_card_id,
                    )
                    .order_by(ReportCardSubjectLine.subject_name.asc())
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @staticmethod
    async def list_active_cards_for_class_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ReportCard]:
        rows = (
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
            )
            .scalars()
            .all()
        )
        return list(rows)

    @staticmethod
    async def mark_outdated_for_student_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        rows = (
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
            )
            .scalars()
            .all()
        )
        for card in rows:
            card.is_outdated = True
        await db.flush()

    @staticmethod
    async def delete_lines_for_card(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        report_card_id: uuid.UUID,
    ) -> None:
        rows = (
            (
                await db.execute(
                    select(ReportCardSubjectLine).where(
                        ReportCardSubjectLine.tenant_id == tenant_id,
                        ReportCardSubjectLine.report_card_id == report_card_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for line in rows:
            await db.delete(line)
        await db.flush()

    @staticmethod
    async def save(db: AsyncSession, report_card: ReportCard) -> ReportCard:
        db.add(report_card)
        await db.flush()
        await db.refresh(report_card)
        return report_card
