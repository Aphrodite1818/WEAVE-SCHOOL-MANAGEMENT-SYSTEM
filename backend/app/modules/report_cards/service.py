import html
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.modules.auth_identity.models import ActorType
from app.modules.classes.repository import ClassRoomRepository
from app.modules.parents.models import Parent
from app.modules.report_cards.models import ReportCard, ReportCardStatus, ReportCardSubjectLine
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.schemas import (
    ReportCardBulkGenerateResponse,
    ReportCardClassOverviewResponse,
    ReportCardClassOverviewRow,
    ReportCardCommentsUpdate,
    ReportCardGenerateRequest,
    ReportCardResponse,
    ReportCardSubjectLineResponse,
)
from app.modules.student_academics.models import AcademicResultStatus, ClassSubject, TeacherAssignment
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.repository import StudentParentLinkRepository, StudentRepository
from app.modules.students.models import Student
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


class ReportCardService:
    @staticmethod
    async def mark_outdated_for_score_change(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        await ReportCardRepository.mark_outdated_for_student_period(
            db=db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
        )

    @staticmethod
    async def _expected_class_subjects(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> list[ClassSubject]:
        items, _ = await StudentAcademicRepository.list_class_subjects(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
            active_only=True,
            limit=500,
        )
        return items

    @staticmethod
    async def _submitted_results_for_student(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list:
        results, _ = await StudentAcademicRepository.list_results(
            db=db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            published_only=True,
            limit=500,
        )
        return results

    @staticmethod
    async def _missing_subjects(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[str]:
        expected = await ReportCardService._expected_class_subjects(db, tenant_id, class_id)
        submitted = await ReportCardService._submitted_results_for_student(
            db, tenant_id, student_id, academic_session_id, academic_term_id
        )
        submitted_subject_ids = {result.subject_id for result in submitted}
        missing: list[str] = []
        for class_subject in expected:
            if class_subject.subject_id not in submitted_subject_ids:
                subject = await SubjectRepository.get_subject_by_id(
                    db, tenant_id, class_subject.subject_id
                )
                missing.append(subject.name if subject else str(class_subject.subject_id))
        return missing

    @staticmethod
    def _dense_rank(values: list[tuple[uuid.UUID, Decimal]]) -> dict[uuid.UUID, int]:
        """Dense rank by average score descending (1 = best)."""
        sorted_values = sorted(values, key=lambda item: item[1], reverse=True)
        ranks: dict[uuid.UUID, int] = {}
        current_rank = 0
        previous_score: Decimal | None = None
        for student_id, score in sorted_values:
            if previous_score is None or score != previous_score:
                current_rank += 1
                previous_score = score
            ranks[student_id] = current_rank
        return ranks

    @staticmethod
    async def _create_card_from_results(
        db: AsyncSession,
        actor: TenantAdmin,
        student: Student,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
        results: list,
        *,
        class_teacher_comment: str | None = None,
        principal_comment: str | None = None,
        version: int = 1,
        replace_existing: ReportCard | None = None,
    ) -> ReportCard:
        if student.class_id is None:
            raise BadRequestException("Student class is required for report card generation.")

        missing = await ReportCardService._missing_subjects(
            db,
            actor.tenant_id,
            student.class_id,
            student.id,
            academic_session_id,
            academic_term_id,
        )
        if missing:
            raise BadRequestException(
                f"Missing submitted scores for: {', '.join(missing)}"
            )

        total_score = sum((result.total_score for result in results), Decimal("0"))
        average_score = total_score / Decimal(str(len(results)))

        if replace_existing is not None:
            replace_existing.superseded_at = datetime.now(timezone.utc)
            await ReportCardRepository.save(db, replace_existing)
            version = replace_existing.version + 1
            class_teacher_comment = class_teacher_comment or replace_existing.class_teacher_comment
            principal_comment = principal_comment or replace_existing.principal_comment

        card = ReportCard(
            tenant_id=actor.tenant_id,
            student_id=student.id,
            class_id=student.class_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            total_score=total_score,
            average_score=average_score,
            class_teacher_comment=class_teacher_comment,
            principal_comment=principal_comment,
            version=version,
            published_at=datetime.now(timezone.utc),
            published_by=actor.id,
            is_outdated=False,
            status=ReportCardStatus.PUBLISHED,
            generated_by_actor_type=ActorType.TENANT_ADMIN.value,
            generated_by_actor_id=actor.id,
        )
        card = await ReportCardRepository.create(db, card)

        for result in results:
            subject = await SubjectRepository.get_subject_by_id(db, actor.tenant_id, result.subject_id)
            teacher = None
            if result.teacher_assignment_id is not None:
                teacher_assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
                    db=db,
                    tenant_id=actor.tenant_id,
                    assignment_id=result.teacher_assignment_id,
                )
                if teacher_assignment is not None:
                    teacher = await TeacherRepository.get_teacher_by_id(
                        db, actor.tenant_id, teacher_assignment.teacher_id
                    )
            if teacher is None:
                teacher = await TeacherRepository.get_teacher_by_id(db, actor.tenant_id, result.teacher_id)
            teacher_name = (
                " ".join(part for part in [teacher.first_name, teacher.last_name] if part).strip()
                if teacher
                else None
            )
            await ReportCardRepository.create_line(
                db,
                ReportCardSubjectLine(
                    tenant_id=actor.tenant_id,
                    report_card_id=card.id,
                    student_subject_result_id=result.id,
                    subject_id=result.subject_id,
                    subject_name=subject.name if subject else "Unknown subject",
                    subject_code=subject.code if subject else None,
                    teacher_name=teacher_name,
                    test_score=result.test_score,
                    assessment_score=result.assessment_score,
                    exam_score=result.exam_score,
                    total_score=result.total_score,
                    grade=result.grade,
                    remark=result.remark,
                ),
            )

        return card

    @staticmethod
    async def _apply_class_positions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        cards = await ReportCardRepository.list_active_cards_for_class_period(
            db, tenant_id, class_id, academic_session_id, academic_term_id
        )
        rank_map = ReportCardService._dense_rank(
            [(card.student_id, card.average_score) for card in cards]
        )
        for card in cards:
            card.position = rank_map.get(card.student_id)
            card.position_out_of = len(cards)
            await ReportCardRepository.save(db, card)

    @staticmethod
    async def generate(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardGenerateRequest,
    ) -> ReportCardResponse | ReportCardBulkGenerateResponse:
        if payload.class_id is not None:
            students, _ = await StudentRepository.list_students(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=payload.class_id,
                limit=500,
            )
            generated: list[ReportCardResponse] = []
            skipped: list[dict] = []
            for student in students:
                try:
                    card = await ReportCardService.generate_for_student(
                        db=db,
                        actor=actor,
                        student_id=student.id,
                        academic_session_id=payload.academic_session_id,
                        academic_term_id=payload.academic_term_id,
                    )
                    generated.append(card)
                except BadRequestException as exc:
                    skipped.append({"student_id": str(student.id), "reason": str(exc)})
            await ReportCardService._apply_class_positions(
                db,
                actor.tenant_id,
                payload.class_id,
                payload.academic_session_id,
                payload.academic_term_id,
            )
            await db.commit()
            return ReportCardBulkGenerateResponse(generated=generated, skipped=skipped)

        return await ReportCardService.generate_for_student(
            db=db,
            actor=actor,
            student_id=payload.student_id,
            academic_session_id=payload.academic_session_id,
            academic_term_id=payload.academic_term_id,
        )

    @staticmethod
    async def generate_for_student(
        db: AsyncSession,
        actor: TenantAdmin,
        *,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> ReportCardResponse:
        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )
        if student is None or student.class_id is None:
            raise NotFoundException("Student or student class not found.")

        existing = await ReportCardRepository.get_by_student_period(
            db,
            actor.tenant_id,
            student_id,
            academic_session_id,
            academic_term_id,
        )
        if existing is not None:
            raise BadRequestException("A report card already exists for this student and academic period.")

        results = await ReportCardService._submitted_results_for_student(
            db, actor.tenant_id, student_id, academic_session_id, academic_term_id
        )
        if not results:
            raise BadRequestException("No submitted scores are available for this student.")

        card = await ReportCardService._create_card_from_results(
            db,
            actor,
            student,
            academic_session_id,
            academic_term_id,
            results,
        )
        await ReportCardService._apply_class_positions(
            db,
            actor.tenant_id,
            student.class_id,
            academic_session_id,
            academic_term_id,
        )
        await db.commit()
        return await ReportCardService.get(db, actor, card.id)

    @staticmethod
    async def regenerate(
        db: AsyncSession,
        actor: TenantAdmin,
        report_card_id: uuid.UUID,
    ) -> ReportCardResponse:
        existing = await ReportCardRepository.get_by_id(db, actor.tenant_id, report_card_id)
        if existing is None or existing.superseded_at is not None:
            raise NotFoundException("Report card not found.")

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=existing.student_id,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        results = await ReportCardService._submitted_results_for_student(
            db,
            actor.tenant_id,
            existing.student_id,
            existing.academic_session_id,
            existing.academic_term_id,
        )
        if not results:
            raise BadRequestException("No submitted scores are available for regeneration.")

        card = await ReportCardService._create_card_from_results(
            db,
            actor,
            student,
            existing.academic_session_id,
            existing.academic_term_id,
            results,
            replace_existing=existing,
        )
        await ReportCardService._apply_class_positions(
            db,
            actor.tenant_id,
            existing.class_id,
            existing.academic_session_id,
            existing.academic_term_id,
        )
        await db.commit()
        return await ReportCardService.get(db, actor, card.id)

    @staticmethod
    async def update_comments(
        db: AsyncSession,
        actor: TenantAdmin,
        report_card_id: uuid.UUID,
        payload: ReportCardCommentsUpdate,
    ) -> ReportCardResponse:
        card = await ReportCardRepository.get_by_id(db, actor.tenant_id, report_card_id)
        if card is None or card.superseded_at is not None:
            raise NotFoundException("Report card not found.")

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(card, field, value)
        if card.status == ReportCardStatus.PUBLISHED and card.published_at is not None:
            card.is_outdated = True
        saved = await ReportCardRepository.save(db, card)
        await db.commit()
        return await ReportCardService.get(db, actor, saved.id)

    @staticmethod
    async def class_overview(
        db: AsyncSession,
        actor: TenantAdmin,
        *,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> ReportCardClassOverviewResponse:
        expected = await ReportCardService._expected_class_subjects(db, actor.tenant_id, class_id)
        students, _ = await StudentRepository.list_students(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
            limit=500,
        )
        cards = await ReportCardRepository.list_active_cards_for_class_period(
            db, actor.tenant_id, class_id, academic_session_id, academic_term_id
        )
        cards_by_student = {card.student_id: card for card in cards}

        rows: list[ReportCardClassOverviewRow] = []
        for student in students:
            submitted = await ReportCardService._submitted_results_for_student(
                db,
                actor.tenant_id,
                student.id,
                academic_session_id,
                academic_term_id,
            )
            missing = await ReportCardService._missing_subjects(
                db,
                actor.tenant_id,
                class_id,
                student.id,
                academic_session_id,
                academic_term_id,
            )
            card = cards_by_student.get(student.id)
            rows.append(
                ReportCardClassOverviewRow(
                    student_id=student.id,
                    student_name=(
                        " ".join(part for part in [student.first_name, student.last_name] if part).strip()
                        or None
                    ),
                    admission_number=student.admission_number,
                    submitted_count=len(submitted),
                    expected_count=len(expected),
                    report_card_id=card.id if card else None,
                    report_card_status=card.status.value if card else None,
                    report_card_version=card.version if card else None,
                    is_outdated=card.is_outdated if card else False,
                    missing_subject_names=missing,
                )
            )

        return ReportCardClassOverviewResponse(
            class_id=class_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            expected_subject_count=len(expected),
            items=rows,
        )

    @staticmethod
    async def publish(
        db: AsyncSession,
        actor: TenantAdmin,
        report_card_id: uuid.UUID,
    ) -> ReportCardResponse:
        card = await ReportCardRepository.get_by_id(db, actor.tenant_id, report_card_id)
        if card is None:
            raise NotFoundException("Report card not found.")
        card.status = ReportCardStatus.PUBLISHED
        card.published_at = card.published_at or datetime.now(timezone.utc)
        card.published_by = card.published_by or actor.id
        saved = await ReportCardRepository.save(db, card)
        await db.commit()
        return await ReportCardService.get(db, actor, saved.id)

        return await ReportCardService.get(db, actor, saved.id)

    @staticmethod
    async def _ensure_parent_can_view(
        db: AsyncSession,
        parent: Parent,
        student_id: uuid.UUID,
    ) -> None:
        link = await StudentParentLinkRepository.get_by_student_and_parent(
            db=db,
            tenant_id=parent.tenant_id,
            student_id=student_id,
            parent_id=parent.id,
        )
        if link is None:
            raise ForbiddenException("You cannot view report cards for this student.")

    @staticmethod
    async def _response(db: AsyncSession, card: ReportCard) -> ReportCardResponse:
        student = await StudentRepository.get_student_by_id(db, card.tenant_id, card.student_id)
        classroom = await ClassRoomRepository.get_classroom_by_id(db, card.tenant_id, card.class_id)
        session = await StudentAcademicRepository.get_academic_session_by_id(db, card.tenant_id, card.academic_session_id)
        term = await StudentAcademicRepository.get_term_by_id(db, card.tenant_id, card.academic_term_id)
        lines = await ReportCardRepository.list_lines(db, card.tenant_id, card.id)
        return ReportCardResponse(
            id=card.id,
            tenant_id=card.tenant_id,
            student_id=card.student_id,
            student_name=(
                " ".join(part for part in [student.first_name, student.last_name] if part).strip()
                if student
                else None
            ),
            admission_number=student.admission_number if student else None,
            student_passport_photo_url=student.passport_photo_url if student else None,
            class_id=card.class_id,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            academic_session_id=card.academic_session_id,
            academic_session_name=session.name if session else None,
            academic_term_id=card.academic_term_id,
            academic_term_name=term.name.value if term else None,
            total_score=card.total_score,
            average_score=card.average_score,
            position=card.position,
            position_out_of=card.position_out_of,
            class_teacher_comment=card.class_teacher_comment,
            principal_comment=card.principal_comment,
            version=card.version,
            published_at=card.published_at,
            published_by=card.published_by,
            is_outdated=card.is_outdated,
            status=card.status,
            lines=[ReportCardSubjectLineResponse.model_validate(line) for line in lines],
            created_at=card.created_at,
            updated_at=card.updated_at,
        )

    @staticmethod
    async def get(
        db: AsyncSession,
        actor: TenantAdmin | Parent | Student,
        report_card_id: uuid.UUID,
    ) -> ReportCardResponse:
        card = await ReportCardRepository.get_by_id(db, actor.tenant_id, report_card_id)
        if card is None:
            raise NotFoundException("Report card not found.")
        if isinstance(actor, Parent):
            await ReportCardService._ensure_parent_can_view(db, actor, card.student_id)
            if card.status != ReportCardStatus.PUBLISHED:
                raise NotFoundException("Report card not found.")
        if isinstance(actor, Student):
            if card.student_id != actor.id or card.status != ReportCardStatus.PUBLISHED:
                raise NotFoundException("Report card not found.")
        return await ReportCardService._response(db, card)

    @staticmethod
    async def list_cards(
        db: AsyncSession,
        actor: TenantAdmin | Parent | Student,
        *,
        student_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ReportCardResponse], int]:
        published_only = isinstance(actor, Parent)
        if isinstance(actor, Parent):
            if student_id is None:
                raise BadRequestException("student_id is required.")
            await ReportCardService._ensure_parent_can_view(db, actor, student_id)
        if isinstance(actor, Student):
            student_id = actor.id
            published_only = True
        cards, total = await ReportCardRepository.list_cards(
            db,
            actor.tenant_id,
            skip=skip,
            limit=min(limit, 100),
            student_id=student_id,
            published_only=published_only,
        )
        return [await ReportCardService._response(db, card) for card in cards], total

    @staticmethod
    async def render_html(db: AsyncSession, actor: TenantAdmin | Parent | Student, report_card_id: uuid.UUID) -> str:
        card = await ReportCardService.get(db, actor, report_card_id)
        tenant = await TenantRepository.get_by_id(db, actor.tenant_id)

        def _format_score(value: Decimal | None) -> str:
            if value is None:
                return "—"
            text = format(value, "f")
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            return text or "0"

        def _format_term(value: str | None) -> str:
            normalized = " ".join(str(value or "").replace("_", " ").split()).lower()
            if not normalized:
                return "—"
            return normalized[0].upper() + normalized[1:]

        def _format_subject(value: str | None) -> str:
            normalized = " ".join(str(value or "").split()).lower()
            if not normalized:
                return "—"
            return " ".join(word.capitalize() for word in normalized.split(" "))

        def _status_colors(value: str) -> tuple[str, str]:
            if value == "published":
                return "#dcfce7", "#15803d"
            if value == "draft":
                return "#e5e7eb", "#4b5563"
            return "#e0e7ff", "#3730a3"

        student_name = html.escape(card.student_name or card.admission_number or "")
        admission_number = html.escape(card.admission_number or "Not assigned")
        class_label = html.escape(" ".join(part for part in [card.class_name, card.class_arm] if part) or "Not assigned")
        session_label = html.escape(card.academic_session_name or "—")
        term_label = html.escape(_format_term(card.academic_term_name))
        school_name = html.escape((tenant.school_name if tenant else None) or "Learnly AI")
        school_logo_url = ((tenant.logo_url if tenant else None) or "").strip()
        status_value = getattr(card.status, "value", card.status)
        status_label = html.escape(str(status_value).replace("_", " ").title())
        status_bg, status_fg = _status_colors(str(status_value))
        is_published = str(status_value) == "published"
        footer_label = "Verified and published" if is_published else "Awaiting publication"
        footer_icon_fill = "#22c55e" if is_published else "#94a3b8"
        footer_text_color = "var(--success-text)" if is_published else "var(--muted)"
        photo_url = (card.student_passport_photo_url or "").strip()
        school_mark = (
            f'<img src="{html.escape(school_logo_url, quote=True)}" alt="{school_name} logo" class="school-logo" />'
            if school_logo_url
            else """
            <div class="school-logo school-logo-fallback" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" class="school-crest" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L19 5V11C19 15.5 15.9 19.58 12 21C8.1 19.58 5 15.5 5 11V5L12 2Z" fill="currentColor"/>
                <path d="M9 11.5L11 13.5L15 9.5" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            """
        )
        photo_block = (
            f'<img src="{html.escape(photo_url, quote=True)}" alt="Student passport photograph" />'
            if photo_url
            else """
            <div class="photo-placeholder" aria-label="Student avatar placeholder">
              <svg class="ti-user avatar-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 12C14.7614 12 17 9.76142 17 7C17 4.23858 14.7614 2 12 2C9.23858 2 7 4.23858 7 7C7 9.76142 9.23858 12 12 12Z" fill="currentColor"/>
                <path d="M4 21C4 17.6863 7.58172 15 12 15C16.4183 15 20 17.6863 20 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            """
        )
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(_format_subject(line.subject_name))}</td>"
            f"<td>{html.escape(line.subject_code or '—')}</td>"
            f"<td>{_format_score(line.test_score)}</td><td>{_format_score(line.assessment_score)}</td><td>{_format_score(line.exam_score)}</td>"
            f"<td>{_format_score(line.total_score)}</td><td>{html.escape(line.grade)}</td>"
            f"<td>{html.escape(line.remark or '')}</td>"
            "</tr>"
            for line in card.lines
        )
        return f"""
<!doctype html>
<html>
<head>
  <title>Report Card</title>
  <style>
    :root {{
      --ink: #0f172a;
      --muted: #64748b;
      --line: #cbd5e1;
      --soft: #f8fafc;
      --brand: #1a237e;
      --brand-soft: #e8eaf6;
      --success-soft: #dcfce7;
      --success-text: #15803d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #e2e8f0;
      color: var(--ink);
      font-family: Inter, Arial, sans-serif;
      line-height: 1.45;
    }}
    .page {{
      width: min(100%, 960px);
      margin: 24px auto;
      background: #ffffff;
      border: 1px solid var(--line);
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.14);
    }}
    .toolbar {{
      display: flex;
      justify-content: flex-end;
      padding: 16px 18px 0;
    }}
    button {{
      border: 0;
      border-radius: 10px;
      background: var(--brand);
      color: white;
      cursor: pointer;
      font-weight: 700;
      padding: 10px 16px;
    }}
    .sheet {{ padding: 28px; }}
    .branding-strip {{
      align-items: center;
      background: var(--brand);
      color: white;
      display: flex;
      justify-content: space-between;
      gap: 18px;
      padding: 16px 20px;
      border-radius: 18px;
      margin-bottom: 24px;
    }}
    .branding-left {{
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }}
    .school-logo {{
      width: 48px;
      height: 48px;
      border-radius: 14px;
      background: white;
      object-fit: cover;
      display: block;
      padding: 4px;
      flex-shrink: 0;
    }}
    .school-logo-fallback {{
      display: grid;
      place-items: center;
      color: var(--brand);
    }}
    .school-crest {{
      width: 26px;
      height: 26px;
    }}
    .school-name {{
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      line-height: 1.2;
    }}
    .doc-label {{
      text-align: right;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.02em;
      opacity: 0.96;
    }}
    .header {{
      display: grid;
      grid-template-columns: 1fr 132px;
      gap: 22px;
      align-items: start;
      border-bottom: 3px solid var(--brand);
      padding-bottom: 22px;
    }}
    h1 {{
      font-size: 32px;
      line-height: 1.1;
      margin: 0;
    }}
    .student-name {{
      color: var(--ink);
      font-size: 17px;
      font-weight: 800;
      margin: 8px 0 0;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      margin-top: 10px;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      background: {status_bg};
      color: {status_fg};
    }}
    .photo-frame {{
      align-self: stretch;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--soft);
      min-height: 150px;
      overflow: hidden;
      padding: 8px;
    }}
    .photo-frame img {{
      width: 100%;
      height: 100%;
      min-height: 132px;
      border-radius: 10px;
      display: block;
      object-fit: cover;
    }}
    .photo-placeholder {{
      min-height: 132px;
      border: 1px dashed #cbd5e1;
      border-radius: 10px;
      display: grid;
      place-items: center;
      color: #94a3b8;
      background: #f1f5f9;
    }}
    .avatar-icon {{
      width: 54px;
      height: 54px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 22px 0;
    }}
    .meta-card {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--soft);
      padding: 12px;
    }}
    .meta-card span {{
      color: var(--muted);
      display: block;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .meta-card strong {{
      display: block;
      font-size: 15px;
      margin-top: 3px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 22px;
    }}
    .summary-card {{
      border-radius: 14px;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      padding: 14px;
    }}
    .summary-card strong {{
      display: block;
      font-size: 24px;
      line-height: 1.1;
    }}
    .summary-card span {{
      color: #1e40af;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      overflow: hidden;
      border-radius: 12px;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--brand-soft);
      color: var(--brand);
      font-size: 11px;
      text-transform: uppercase;
    }}
    tbody tr:nth-child(even) {{ background: #f8fafc; }}
    .footer-bar {{
      margin-top: 26px;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      padding-top: 14px;
      color: var(--muted);
      font-size: 12px;
    }}
    .verified-stamp {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: {footer_text_color};
      font-weight: 700;
    }}
    .verified-stamp svg {{
      width: 16px;
      height: 16px;
    }}
    @media (max-width: 720px) {{
      .page {{ margin: 0; border: 0; }}
      .sheet {{ padding: 18px; }}
      .branding-strip {{ align-items: flex-start; flex-direction: column; }}
      .doc-label {{ text-align: left; }}
      .header, .meta-grid, .summary {{ grid-template-columns: 1fr; }}
      .footer-bar {{ align-items: flex-start; flex-direction: column; }}
      .photo-frame {{ max-width: 150px; }}
    }}
    @media print {{
      body {{ background: #ffffff; }}
      button, .toolbar {{ display: none; }}
      .page {{ margin: 0; width: 100%; border: 0; box-shadow: none; }}
      .sheet {{ padding: 18mm; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="toolbar"><button onclick="window.print()">Print report card</button></div>
    <section class="sheet">
      <section class="branding-strip" aria-label="School branding">
        <div class="branding-left">
          {school_mark}
          <p class="school-name">{school_name}</p>
        </div>
        <div class="doc-label">Termly academic report</div>
      </section>

      <header class="header">
        <div>
          <h1>Report Card</h1>
          <p class="student-name">{student_name}</p>
          <div class="status-pill">{status_label}</div>
        </div>
        <div class="photo-frame">{photo_block}</div>
      </header>

      <section class="meta-grid" aria-label="Student and academic details">
        <div class="meta-card"><span>Admission No.</span><strong>{admission_number}</strong></div>
        <div class="meta-card"><span>Class</span><strong>{class_label}</strong></div>
        <div class="meta-card"><span>Session</span><strong>{session_label}</strong></div>
        <div class="meta-card"><span>Term</span><strong>{term_label}</strong></div>
      </section>

      <section class="summary" aria-label="Performance summary">
        <div class="summary-card"><span>Total score</span><strong>{_format_score(card.total_score)}</strong></div>
        <div class="summary-card"><span>Average</span><strong>{_format_score(card.average_score)}</strong></div>
      </section>

      <table>
        <thead><tr><th>Subject</th><th>Code</th><th>Test</th><th>Assessment</th><th>Exam</th><th>Total</th><th>Grade</th><th>Remark</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>

      <footer class="footer-bar">
        <div>Generated by Learnly AI · {session_label} academic session</div>
        <div class="verified-stamp">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M12 2L19 5V11C19 15.5 15.9 19.58 12 21C8.1 19.58 5 15.5 5 11V5L12 2Z" fill="{footer_icon_fill}"/>
            <path d="M9 11.5L11 13.5L15 9.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          {footer_label}
        </div>
      </footer>
    </section>
  </main>
</body>
</html>
"""
