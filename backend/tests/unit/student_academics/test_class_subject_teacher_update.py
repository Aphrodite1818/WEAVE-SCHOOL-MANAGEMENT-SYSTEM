from __future__ import annotations

import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import ClassSubject, ClassSubjectTeacher
from app.modules.student_academics.schemas import (
    ClassSubjectCreate,
    ClassSubjectTeacherUpdate,
    ClassSubjectUpdate,
)
from app.modules.student_academics.service import StudentAcademicService


@contextmanager
def patch_many(*context_managers):
    with ExitStack() as stack:
        yield [
            stack.enter_context(context_manager) for context_manager in context_managers
        ]


def _assignment(tenant_id: uuid.UUID) -> ClassSubjectTeacher:
    return ClassSubjectTeacher(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        teacher_membership_id=uuid.uuid4(),
        is_core=True,
        sort_order=3,
        is_active=True,
    )


def _class_subject(tenant_id: uuid.UUID) -> ClassSubject:
    now = datetime.now(timezone.utc)
    return ClassSubject(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        is_core=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _classroom(
    class_subject: ClassSubject, *, active: bool = True, archived: bool = False
):
    return SimpleNamespace(
        id=class_subject.class_id,
        is_active=active,
        archived_at=datetime.now(timezone.utc) if archived else None,
    )


def _subject(
    class_subject: ClassSubject, *, active: bool = True, archived: bool = False
):
    return SimpleNamespace(
        id=class_subject.subject_id,
        name="Mathematics",
        code="MTH",
        is_active=active,
        archived_at=datetime.now(timezone.utc) if archived else None,
    )


def _response_parent_patches(
    class_subject: ClassSubject,
    *,
    class_active=True,
    class_archived=False,
    subject_active=True,
    subject_archived=False,
):
    return (
        patch(
            "app.modules.student_academics.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(
                return_value=_classroom(
                    class_subject, active=class_active, archived=class_archived
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(
                return_value=_subject(
                    class_subject, active=subject_active, archived=subject_archived
                )
            ),
        ),
    )


def _dependency_count_patches(
    *,
    active_assignments=0,
    assignment_history=0,
    results=0,
    report_lines=0,
    compatibility_rows=0,
    active_compatibility_rows=0,
):
    assignment_counts = AsyncMock(side_effect=[active_assignments, assignment_history])
    compatibility_counts = AsyncMock(
        side_effect=[compatibility_rows, active_compatibility_rows]
    )
    return (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignments_for_class_subject",
            new=assignment_counts,
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_results_for_class_subject",
            new=AsyncMock(return_value=results),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_report_card_lines_for_class_subject",
            new=AsyncMock(return_value=report_lines),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_class_subject_teachers_for_class_subject",
            new=compatibility_counts,
        ),
    )


@pytest.mark.asyncio
async def test_update_class_subject_teacher_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    assignment = _assignment(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_teacher_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject_teacher",
            new=AsyncMock(return_value=assignment),
        ),
    ):
        response = await StudentAcademicService.update_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            payload=ClassSubjectTeacherUpdate(
                is_core=None,
                sort_order=None,
                is_active=None,
            ),
        )

    assert assignment.is_core is True
    assert assignment.sort_order == 3
    assert assignment.is_active is True
    assert response.is_core is True


@pytest.mark.asyncio
async def test_update_class_subject_teacher_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    assignment = _assignment(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_teacher_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject_teacher",
            new=AsyncMock(return_value=assignment),
        ),
    ):
        response = await StudentAcademicService.update_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            payload=ClassSubjectTeacherUpdate(
                is_core=False,
                sort_order=7,
            ),
        )

    assert assignment.is_core is False
    assert assignment.sort_order == 7
    assert assignment.is_active is True
    assert response.sort_order == 7


@pytest.mark.asyncio
async def test_archive_class_subject_requires_ending_active_assignments() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.archive_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                admin_id=uuid.uuid4(),
            )
    assert (
        exc_info.value.detail
        == "Active class-subject mappings cannot be archived. Deactivate the mapping first."
    )


@pytest.mark.asyncio
async def test_restore_class_subject_returns_inactive_not_active() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    class_subject.archived_at = datetime.now(timezone.utc)
    class_subject.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=_subject(class_subject)),
        ),
        patch(
            "app.modules.student_academics.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=_classroom(class_subject)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_class_subject_teachers_for_class_subject",
            new=AsyncMock(return_value=[]),
        ),
    ):
        response = await StudentAcademicService.restore_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject.id,
        )

    assert class_subject.archived_at is None
    assert class_subject.archived_by_admin_id is None
    assert class_subject.is_active is False
    assert response.is_active is False


@pytest.mark.asyncio
async def test_create_class_subject_creates_new_mapping_only() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=_classroom(class_subject)),
        ),
        patch(
            "app.modules.student_academics.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=_subject(class_subject)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_class_and_subject",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_class_subject",
            new=AsyncMock(return_value=class_subject),
        ),
    ):
        response = await StudentAcademicService.create_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=class_subject.class_id,
            payload=ClassSubjectCreate(
                subject_id=class_subject.subject_id, is_core=True
            ),
        )

    assert response.id == class_subject.id
    assert response.lifecycle_status == "active"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_active", "archived_at", "message"),
    [
        (True, None, "This subject is already offered by the class."),
        (
            False,
            None,
            "This class-subject mapping is inactive. Activate it instead of creating a new mapping.",
        ),
        (
            False,
            datetime.now(timezone.utc),
            "This class-subject mapping is archived. Restore it before creating a new mapping.",
        ),
    ],
)
async def test_create_class_subject_rejects_duplicate_lifecycle_states(
    is_active, archived_at, message
) -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = is_active
    class_subject.archived_at = archived_at
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=_classroom(class_subject)),
        ),
        patch(
            "app.modules.student_academics.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=_subject(class_subject)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_class_and_subject",
            new=AsyncMock(return_value=class_subject),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.create_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_id=class_subject.class_id,
                payload=ClassSubjectCreate(
                    subject_id=class_subject.subject_id, is_core=False
                ),
            )

    assert exc_info.value.detail == message
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_deactivate_class_subject_blocks_active_teacher_assignment() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        *_dependency_count_patches(active_assignments=1, assignment_history=1),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.deactivate_class_subject(
                db, tenant_id, class_subject.id
            )

    assert (
        exc_info.value.payload["dependency_counts"]["active_teacher_assignments"] == 1
    )
    assert class_subject.is_active is True


@pytest.mark.asyncio
async def test_deactivate_class_subject_syncs_compatibility_rows() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    db = AsyncMock()
    sync = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        *_dependency_count_patches(active_compatibility_rows=1),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._set_compatibility_class_subject_teachers_active",
            new=sync,
        ),
        *_response_parent_patches(class_subject),
    ):
        response = await StudentAcademicService.deactivate_class_subject(
            db, tenant_id, class_subject.id
        )

    assert response.lifecycle_status == "inactive"
    sync.assert_awaited_once_with(
        db, tenant_id=tenant_id, class_subject_id=class_subject.id, is_active=False
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_inactive_class_subject_can_be_archived_when_dependency_free() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        *_dependency_count_patches(),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._set_compatibility_class_subject_teachers_active",
            new=AsyncMock(),
        ),
        *_response_parent_patches(class_subject),
    ):
        response = await StudentAcademicService.archive_class_subject(
            db, tenant_id, class_subject.id, uuid.uuid4()
        )

    assert response.lifecycle_status == "archived"
    assert class_subject.is_active is False
    assert class_subject.archived_at is not None


@pytest.mark.asyncio
async def test_archive_class_subject_rejects_already_archived_mapping() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    class_subject.archived_at = datetime.now(timezone.utc)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
        new=AsyncMock(return_value=class_subject),
    ):
        with pytest.raises(ConflictException, match="already archived"):
            await StudentAcademicService.archive_class_subject(
                db,
                tenant_id,
                class_subject.id,
                uuid.uuid4(),
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "class_active",
        "class_archived",
        "subject_active",
        "subject_archived",
        "expected",
    ),
    [
        (
            False,
            False,
            True,
            False,
            "Classroom must be active before activating this class subject.",
        ),
        (
            True,
            True,
            True,
            False,
            "Classroom must be active before activating this class subject.",
        ),
        (
            True,
            False,
            False,
            False,
            "Subject must be active before activating this class subject.",
        ),
        (
            True,
            False,
            True,
            True,
            "Subject must be active before activating this class subject.",
        ),
    ],
)
async def test_activate_class_subject_requires_active_parent_records(
    class_active, class_archived, subject_active, subject_archived, expected
) -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        *_response_parent_patches(
            class_subject,
            class_active=class_active,
            class_archived=class_archived,
            subject_active=subject_active,
            subject_archived=subject_archived,
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.activate_class_subject(
                db, tenant_id, class_subject.id
            )

    assert exc_info.value.detail == expected


@pytest.mark.asyncio
async def test_archived_class_subject_cannot_be_activated_directly() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    class_subject.archived_at = datetime.now(timezone.utc)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
        new=AsyncMock(return_value=class_subject),
    ):
        with pytest.raises(ConflictException):
            await StudentAcademicService.activate_class_subject(
                db, tenant_id, class_subject.id
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_active", "archived_at", "message"),
    [
        (
            True,
            None,
            "Active class-subject mappings cannot be hard-deleted. Deactivate the mapping first.",
        ),
        (
            False,
            datetime.now(timezone.utc),
            "Archived class-subject mappings cannot be hard-deleted. Restore them first.",
        ),
    ],
)
async def test_class_subject_hard_delete_rejects_invalid_lifecycle_state(
    is_active, archived_at, message
) -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = is_active
    class_subject.archived_at = archived_at
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
        new=AsyncMock(return_value=class_subject),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.delete_class_subject(
                db, tenant_id, class_subject.id
            )

    assert exc_info.value.detail == message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("assignment_history", "results", "report_lines", "dependency_key"),
    [
        (1, 0, 0, "teacher_assignment_history"),
        (0, 1, 0, "student_results"),
        (0, 0, 1, "report_card_lines"),
    ],
)
async def test_class_subject_hard_delete_returns_dependency_counts(
    assignment_history, results, report_lines, dependency_key
) -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    db = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        *_dependency_count_patches(
            assignment_history=assignment_history,
            results=results,
            report_lines=report_lines,
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.delete_class_subject(
                db, tenant_id, class_subject.id
            )

    assert exc_info.value.payload["dependency_counts"][dependency_key] == 1


@pytest.mark.asyncio
async def test_unused_inactive_class_subject_hard_delete_removes_disposable_compatibility_rows() -> (
    None
):
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    compatibility = _assignment(tenant_id)
    db = AsyncMock()
    delete_compatibility = AsyncMock()
    delete_mapping = AsyncMock()

    with patch_many(
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        *_dependency_count_patches(compatibility_rows=1),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_class_subject_teachers_for_class_subject",
            new=AsyncMock(return_value=[compatibility]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_class_subject_teacher",
            new=delete_compatibility,
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_class_subject",
            new=delete_mapping,
        ),
        *_response_parent_patches(class_subject),
    ):
        response = await StudentAcademicService.delete_class_subject(
            db, tenant_id, class_subject.id
        )

    assert response.id == class_subject.id
    delete_compatibility.assert_awaited_once_with(db, compatibility)
    delete_mapping.assert_awaited_once_with(db, class_subject)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_class_subject_rejects_archived_mapping() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.archived_at = datetime.now(timezone.utc)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
        new=AsyncMock(return_value=class_subject),
    ):
        with pytest.raises(ConflictException):
            await StudentAcademicService.update_class_subject(
                db,
                tenant_id,
                class_subject.id,
                ClassSubjectUpdate(is_core=False),
            )
