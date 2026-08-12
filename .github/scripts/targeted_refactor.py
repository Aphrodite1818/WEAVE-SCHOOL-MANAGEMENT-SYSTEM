from pathlib import Path


def load(path: str) -> str:
    return Path(path).read_text()


def save(path: str, text: str) -> None:
    Path(path).write_text(text)


def inject_async_guard(path: str, function_names: list[str], guard_line: str) -> None:
    lines = load(path).splitlines(keepends=True)
    for name in function_names:
        start = next(
            (i for i, line in enumerate(lines) if line.startswith(f"    async def {name}(")),
            None,
        )
        if start is None:
            raise RuntimeError(f"{path}: function {name} not found")
        end = start
        while not lines[end].rstrip().endswith(":"):
            end += 1
        if end + 1 < len(lines) and guard_line.strip() in lines[end + 1]:
            continue
        lines.insert(end + 1, guard_line)
    save(path, "".join(lines))


# Academic/class structural writes must honor the CLOSING freeze even when
# called outside HTTP route dependencies.
path = "backend/app/modules/classes/service.py"
text = load(path)
import_anchor = "from app.modules.parents.models import Parent\n"
guard_import = (
    "from app.modules.student_academics.write_guard import ensure_academic_write_window\n"
)
if guard_import not in text:
    if import_anchor not in text:
        raise RuntimeError("classes service import anchor missing")
    text = text.replace(import_anchor, import_anchor + guard_import, 1)
text = text.replace(
    "        AcademicLevelService._ensure_admin(actor)\n",
    "        AcademicLevelService._ensure_admin(actor)\n"
    "        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)\n",
)
text = text.replace(
    "        ClassRoomService._ensure_tenant_admin(actor)\n",
    "        ClassRoomService._ensure_tenant_admin(actor)\n"
    "        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)\n",
)
text = text.replace("        limit = min(limit, 100)\n", "        limit = min(limit, 500)\n", 1)
dependency_anchor = """        new_level_id = update_data.get("academic_level_id", classroom.academic_level_id)
        new_arm = update_data.get("arm", classroom.arm)
        new_normalized_arm = normalized_class_arm_key(new_arm)

"""
dependency_block = dependency_anchor + """        if new_level_id != classroom.academic_level_id:
            dependency_counts = await ClassRoomRepository.count_class_dependencies(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=classroom.id,
            )
            if any(dependency_counts.values()):
                raise ConflictException(
                    "Academic level cannot be changed after this class has academic history.",
                    payload={"dependency_counts": dependency_counts},
                )

"""
if dependency_block not in text:
    if dependency_anchor not in text:
        raise RuntimeError("class level mutation anchor missing")
    text = text.replace(dependency_anchor, dependency_block, 1)
save(path, text)

# Level-subject and teacher-assignment structural writes use the same domain
# guard rather than depending solely on route wiring.
path = "backend/app/modules/student_academics/service.py"
text = load(path)
anchor = "from app.modules.students.models import Student, StudentParentLinkStatus\n"
guard_import = (
    "from app.modules.student_academics.write_guard import ensure_academic_write_window\n"
)
if guard_import not in text:
    if anchor not in text:
        raise RuntimeError("student academic service import anchor missing")
    text = text.replace(anchor, guard_import + anchor, 1)
    save(path, text)
inject_async_guard(
    path,
    [
        "create_level_subject",
        "create_level_subjects_bulk",
        "deactivate_level_subject",
        "activate_level_subject",
        "update_level_subject",
        "archive_level_subject",
        "restore_level_subject",
        "delete_level_subject",
        "create_teacher_assignment",
        "end_teacher_assignment",
        "reassign_teacher_assignment",
    ],
    "        await ensure_academic_write_window(db, tenant_id=tenant_id)\n",
)
text = load(path)
old = """        if effective_from < current.effective_from:
            raise ConflictException(
                "Replacement effective date cannot be before the current assignment start date."
            )
"""
new = """        if effective_from <= current.effective_from:
            raise ConflictException(
                "Replacement effective date must be after the current assignment start date to avoid overlapping assignment history."
            )
"""
if old not in text:
    raise RuntimeError("teacher reassignment date anchor missing")
text = text.replace(old, new, 1)
old = """        current.effective_to = (
            effective_from
            if effective_from == current.effective_from
            else effective_from - timedelta(days=1)
        )
"""
if old not in text:
    raise RuntimeError("teacher reassignment inclusive date anchor missing")
text = text.replace(old, "        current.effective_to = effective_from - timedelta(days=1)\n", 1)
save(path, text)

# Current OPEN and CLOSING periods are both current for uniqueness/resolution.
path = "backend/app/modules/student_academics/repository.py"
text = load(path)
old = "                    AcademicSession.status == AcademicSessionStatus.OPEN,\n"
new = """                    AcademicSession.status.in_(
                        {AcademicSessionStatus.OPEN, AcademicSessionStatus.CLOSING}
                    ),
"""
if old not in text:
    raise RuntimeError("current academic session lookup anchor missing")
text = text.replace(old, new, 1)
old = "                    AcademicTerm.status == AcademicTermStatus.OPEN,\n"
new = """                    AcademicTerm.status.in_(
                        {AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING}
                    ),
"""
if old not in text:
    raise RuntimeError("current academic term lookup anchor missing")
text = text.replace(old, new, 1)
save(path, text)

path = "backend/app/modules/student_academics/lifecycle_repository.py"
text = load(path)
old = "            AcademicSession.status == AcademicSessionStatus.OPEN,\n"
new = """            AcademicSession.status.in_(
                {AcademicSessionStatus.OPEN, AcademicSessionStatus.CLOSING}
            ),
"""
if old not in text:
    raise RuntimeError("lifecycle current session anchor missing")
text = text.replace(old, new, 1)
old_add = """    @staticmethod
    async def add(db: AsyncSession, item: StudentProgressionItem) -> StudentProgressionItem:
        db.add(item)
        await db.flush()
        return item
"""
new_add = """    @staticmethod
    async def add(db: AsyncSession, item: StudentProgressionItem) -> StudentProgressionItem:
        """ + "'''Create or update the one logical progression item for a student/run.'''
" + """
        existing = await StudentProgressionItemRepository.get_by_run_and_student(
            db,
            item.progression_run_id,
            item.student_id,
            lock=True,
        )
        if existing is not None:
            for field in (
                "tenant_id",
                "from_enrollment_id",
                "to_enrollment_id",
                "from_class_id",
                "to_class_id",
                "action",
                "status",
                "reason",
                "processed_at",
            ):
                setattr(existing, field, getattr(item, field))
            db.add(existing)
            await db.flush()
            return existing

        db.add(item)
        await db.flush()
        return item
"""
if old_add not in text:
    raise RuntimeError("progression item add anchor missing")
text = text.replace(old_add, new_add, 1)
save(path, text)

path = "backend/app/modules/student_academics/models.py"
text = load(path)
old = 'postgresql_where=text("is_current = true AND status = \'open\'"),'
new = 'postgresql_where=text("is_current = true AND status IN (\'open\', \'closing\')"),'
count = text.count(old)
if count != 2:
    raise RuntimeError(f"expected two current-period partial indexes, found {count}")
save(path, text.replace(old, new))

# Retry unresolved progression items without deleting history or shrinking the
# original cohort/counters.
path = "backend/app/modules/student_academics/session_closure_service.py"
text = load(path)
old = """            run.status = StudentProgressionRunStatus.PENDING
            run.total_students = len(enrollments)
            run.promoted_students = 0
            run.graduated_students = 0
            run.skipped_students = 0
            run.failed_students = 0
            run.started_at = None
"""
new = """            run.status = StudentProgressionRunStatus.PENDING
            if run.total_students == 0:
                run.total_students = len(enrollments)
            run.started_at = None
"""
if old not in text:
    raise RuntimeError("start-closing retry reset anchor missing")
text = text.replace(old, new, 1)
old = """        run.total_students = len(enrollments)
        run.promoted_students = 0
        run.graduated_students = 0
        run.skipped_students = 0
        run.failed_students = 0
        effective_date = session.end_date or date.today()
"""
new = """        if run.total_students == 0:
            run.total_students = len(enrollments)
        effective_date = session.end_date or date.today()
"""
if old not in text:
    raise RuntimeError("progression processing counter reset anchor missing")
text = text.replace(old, new, 1)
old = """                db.add(
                    StudentProgressionItem(
                        tenant_id=tenant_id,
                        progression_run_id=run.id,
                        student_id=enrollment.student_id,
                        from_enrollment_id=enrollment.id,
                        from_class_id=enrollment.class_id,
                        to_class_id=None,
                        action=StudentProgressionItemAction.SKIP,
                        status=StudentProgressionItemStatus.FAILED,
                        reason=str(exc)[:1000],
                        processed_at=_utc_now(),
                    )
                )
                await db.flush()

        run.status = (
            StudentProgressionRunStatus.FAILED
            if run.failed_students > 0
            else StudentProgressionRunStatus.COMPLETED
        )
        run.completed_at = _utc_now()
        run.failure_reason = (
            f"{run.failed_students} student progression item(s) failed."
            if run.failed_students
            else None
        )
"""
new = """                await StudentProgressionRepository.add_item(
                    db,
                    StudentProgressionItem(
                        tenant_id=tenant_id,
                        progression_run_id=run.id,
                        student_id=enrollment.student_id,
                        from_enrollment_id=enrollment.id,
                        from_class_id=enrollment.class_id,
                        to_class_id=None,
                        action=StudentProgressionItemAction.SKIP,
                        status=StudentProgressionItemStatus.FAILED,
                        reason=str(exc)[:1000],
                        processed_at=_utc_now(),
                    ),
                )

        persisted_items = await StudentProgressionRepository.list_items_for_run(
            db, tenant_id, run.id
        )
        run.promoted_students = sum(
            item.status == StudentProgressionItemStatus.PROMOTED for item in persisted_items
        )
        run.graduated_students = sum(
            item.status == StudentProgressionItemStatus.GRADUATED for item in persisted_items
        )
        run.skipped_students = sum(
            item.status == StudentProgressionItemStatus.SKIPPED for item in persisted_items
        )
        run.failed_students = sum(
            item.status == StudentProgressionItemStatus.FAILED for item in persisted_items
        )
        incomplete_students = max(run.total_students - len(persisted_items), 0)
        run.status = (
            StudentProgressionRunStatus.FAILED
            if run.failed_students > 0 or incomplete_students > 0
            else StudentProgressionRunStatus.COMPLETED
        )
        run.completed_at = _utc_now()
        run.failure_reason = (
            f"{run.failed_students} failed and {incomplete_students} incomplete student progression item(s)."
            if run.status == StudentProgressionRunStatus.FAILED
            else None
        )
"""
if old not in text:
    raise RuntimeError("progression failure persistence anchor missing")
text = text.replace(old, new, 1)
save(path, text)

# Each retry gets a fresh queue-attempt identity. The run id remains business
# idempotency, while Redis job retention cannot suppress a later retry.
path = "backend/app/core/queue/arq.py"
text = load(path)
if "import uuid\n" not in text:
    text = text.replace("from __future__ import annotations\n\n", "from __future__ import annotations\n\nimport uuid\n", 1)
old = '    if retry:\n        job_id = f"{job_id}:retry"\n'
new = '    if retry:\n        job_id = f"{job_id}:retry:{uuid.uuid4().hex}"\n'
if old not in text:
    raise RuntimeError("session progression retry queue id anchor missing")
text = text.replace(old, new, 1)
save(path, text)

# Historical report cards use the enrollment for the requested session rather
# than the student's current class pointer.
path = "backend/app/modules/report_cards/service.py"
text = load(path)
text = text.replace(
    "from sqlalchemy.ext.asyncio import AsyncSession\n",
    "from sqlalchemy import select\nfrom sqlalchemy.ext.asyncio import AsyncSession\n",
    1,
)
text = text.replace(
    "from app.modules.students.models import Student\n",
    "from app.modules.students.models import Student, StudentEnrollment\n",
    1,
)
old = """        if student.class_id is None:
            raise BadRequestException("Student class is required for report card generation.")
        if not results:
            raise BadRequestException("No locked scores are available for this student.")

        missing = await ReportCardService._missing_subjects(
            db,
            actor.tenant_id,
            student.class_id,
"""
new = """        enrollment = (
            await db.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.tenant_id == actor.tenant_id,
                    StudentEnrollment.student_id == student.id,
                    StudentEnrollment.academic_session_id == academic_session_id,
                )
            )
        ).scalar_one_or_none()
        if enrollment is None:
            raise BadRequestException(
                "Student enrollment for this academic session is required for report card generation."
            )
        class_id = enrollment.class_id
        if not results:
            raise BadRequestException("No locked scores are available for this student.")

        missing = await ReportCardService._missing_subjects(
            db,
            actor.tenant_id,
            class_id,
"""
if old not in text:
    raise RuntimeError("report card class resolution anchor missing")
text = text.replace(old, new, 1)
old = "            class_id=student.class_id,\n"
if old not in text:
    raise RuntimeError("report card persisted class anchor missing")
text = text.replace(old, "            class_id=class_id,\n", 1)
old = """        if student is None or student.class_id is None:
            raise NotFoundException("Student or student class not found.")
"""
if old not in text:
    raise RuntimeError("report card current student class guard missing")
text = text.replace(
    old,
    """        if student is None:
            raise NotFoundException("Student not found.")
""",
    1,
)
old = """            student.class_id,
            academic_session_id,
            academic_term_id,
        )
        await db.commit()
"""
new = """            card.class_id,
            academic_session_id,
            academic_term_id,
        )
        await db.commit()
"""
if old not in text:
    raise RuntimeError("report card position class anchor missing")
text = text.replace(old, new, 1)
save(path, text)

# High-risk backend regression coverage.
Path("backend/tests/test_academic_refactor_regressions.py").write_text(
    '''from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from app.modules.student_academics.lifecycle_repository import StudentProgressionItemRepository
from app.modules.student_academics.models import (
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
)


@pytest.mark.asyncio
async def test_progression_item_retry_updates_existing_logical_item(monkeypatch):
    run_id = uuid.uuid4()
    student_id = uuid.uuid4()
    existing_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=existing_id,
        tenant_id=uuid.uuid4(),
        progression_run_id=run_id,
        student_id=student_id,
        from_enrollment_id=None,
        to_enrollment_id=None,
        from_class_id=None,
        to_class_id=None,
        action=StudentProgressionItemAction.SKIP,
        status=StudentProgressionItemStatus.FAILED,
        reason="first failure",
        processed_at=None,
    )
    monkeypatch.setattr(
        StudentProgressionItemRepository,
        "get_by_run_and_student",
        AsyncMock(return_value=existing),
    )
    db = SimpleNamespace(add=lambda item: None, flush=AsyncMock())
    incoming = StudentProgressionItem(
        tenant_id=existing.tenant_id,
        progression_run_id=run_id,
        student_id=student_id,
        action=StudentProgressionItemAction.PROMOTE,
        status=StudentProgressionItemStatus.PROMOTED,
        reason="retry succeeded",
    )

    saved = await StudentProgressionItemRepository.add(db, incoming)

    assert saved is existing
    assert saved.id == existing_id
    assert saved.status == StudentProgressionItemStatus.PROMOTED
    assert saved.reason == "retry succeeded"
    db.flush.assert_awaited_once()


def test_current_period_partial_indexes_cover_closing_state():
    from app.modules.student_academics.models import AcademicSession, AcademicTerm

    session_index = next(
        item
        for item in AcademicSession.__table__.indexes
        if item.name == "uq_academic_sessions_current_per_tenant"
    )
    term_index = next(
        item
        for item in AcademicTerm.__table__.indexes
        if item.name == "uq_academic_terms_current_per_tenant"
    )
    assert "closing" in str(session_index.dialect_options["postgresql"]["where"])
    assert "closing" in str(term_index.dialect_options["postgresql"]["where"])
'''
)
