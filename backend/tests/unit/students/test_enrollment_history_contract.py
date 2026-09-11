from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.students.models import StudentEnrollmentOutcome
from app.modules.students.placement_service import StudentPlacementService
from app.modules.students.repository import StudentRepository


@pytest.mark.asyncio
async def test_history_uses_joined_display_rows_without_class_relationship_lazy_loads():
    tenant_id, student_id, class_id, level_id, session_id = [uuid4() for _ in range(5)]
    now = datetime.now(timezone.utc)
    enrollment = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        student_id=student_id,
        academic_level_id=level_id,
        class_id=class_id,
        academic_session_id=session_id,
        started_on=date(2026, 9, 1),
        ended_on=None,
        entry_outcome=StudentEnrollmentOutcome.ENROLLED,
        exit_outcome=None,
        entry_reason="Initial placement",
        exit_reason=None,
        created_by_admin_id=None,
        ended_by_admin_id=None,
        created_at=now,
        updated_at=now,
    )

    class RelationshipTrap:
        id = class_id

        def __getattr__(self, name):
            if name in {"academic_level_name", "academic_level", "arm", "arm_label_ref"}:
                raise AssertionError(f"unexpected lazy relationship access: {name}")
            raise AttributeError(name)

    rows = MagicMock()
    rows.all.return_value = [
        (
            enrollment,
            RelationshipTrap(),
            SimpleNamespace(name="SS1"),
            SimpleNamespace(name="2026/27"),
            SimpleNamespace(label="A"),
        )
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=rows))
    with patch.object(
        StudentRepository,
        "get_by_id",
        new=AsyncMock(return_value=SimpleNamespace(id=student_id)),
    ):
        history = await StudentPlacementService.list_history(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
        )

    assert history[0].class_name == "SS1"
    assert history[0].class_arm == "A"
    assert history[0].entry_outcome == StudentEnrollmentOutcome.ENROLLED


@pytest.mark.asyncio
async def test_class_department_lookup_uses_term_level_department_identity():
    tenant_id, class_id, term_id = [uuid4() for _ in range(3)]
    result = MagicMock()
    result.scalar_one_or_none.return_value = "Science"
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    resolved = await StudentPlacementService._department_name(
        db,
        tenant_id=tenant_id,
        class_id=class_id,
        academic_term_id=term_id,
    )

    assert resolved == "Science"
    statement = str(db.execute.call_args.args[0])
    assert "class_term_department_assignments" in statement
    assert "academic_level_departments" in statement
    assert "departments" in statement
