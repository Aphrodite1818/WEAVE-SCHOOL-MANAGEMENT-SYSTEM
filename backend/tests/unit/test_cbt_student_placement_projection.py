from types import SimpleNamespace
from uuid import uuid4

from app.modules.cbt.sync.projectors.curriculum import project_curriculum_subject
from app.modules.cbt.sync.projectors.students import project_student_enrollment
from app.modules.student_academics.models import AcademicSessionStatus
from app.modules.students.models import AcademicStatus


class _Result:
    def __init__(self, *, first=None, scalar=None):
        self._first = first
        self._scalar = scalar

    def first(self):
        return self._first

    def scalar_one_or_none(self):
        return self._scalar


class _Session:
    def __init__(self, result):
        self.result = result

    def execute(self, _statement):
        return self.result


def _student_enrollment_context(*, current=True, level_id=None, class_id=None):
    tenant_id = uuid4()
    level_id = level_id or uuid4()
    class_id = class_id or uuid4()
    enrollment = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        student_id=uuid4(),
        academic_session_id=uuid4(),
        academic_level_id=level_id,
        class_id=class_id,
        is_current=current,
    )
    student = SimpleNamespace(
        id=enrollment.student_id,
        admission_number="STD-001",
        first_name="Ada",
        last_name="Student",
        status=AcademicStatus.ACTIVE,
        is_archived=False,
    )
    academic_session = SimpleNamespace(
        id=enrollment.academic_session_id,
        tenant_id=tenant_id,
        is_current=True,
        status=AcademicSessionStatus.OPEN,
    )
    level = SimpleNamespace(
        id=level_id,
        tenant_id=tenant_id,
        status="active",
        is_active=True,
        archived_at=None,
    )
    classroom = SimpleNamespace(
        id=class_id,
        tenant_id=tenant_id,
        academic_level_id=level_id,
        status="active",
        is_active=True,
        archived_at=None,
    )
    return tenant_id, enrollment, student, academic_session, level, classroom


def test_closed_source_enrollment_projects_as_tombstone():
    tenant_id, enrollment, student, academic_session, level, classroom = (
        _student_enrollment_context(current=False)
    )
    session = _Session(
        _Result(first=(enrollment, student, academic_session, level, classroom))
    )

    assert project_student_enrollment(session, tenant_id, enrollment.id) is None


def test_destination_enrollment_projects_new_level_and_class_identity():
    new_level_id = uuid4()
    new_class_id = uuid4()
    tenant_id, enrollment, student, academic_session, level, classroom = (
        _student_enrollment_context(
            current=True,
            level_id=new_level_id,
            class_id=new_class_id,
        )
    )
    session = _Session(
        _Result(first=(enrollment, student, academic_session, level, classroom))
    )

    payload = project_student_enrollment(session, tenant_id, enrollment.id)

    assert payload is not None
    assert payload["id"] == str(enrollment.id)
    assert payload["academic_level_id"] == str(new_level_id)
    assert payload["class_id"] == str(new_class_id)
    assert payload["academic_session_id"] == str(enrollment.academic_session_id)
    assert payload["is_current"] is True


def test_same_named_subjects_remain_distinct_curriculum_subject_identities():
    tenant_id = uuid4()
    shared_subject_id = uuid4()

    first_curriculum_subject = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        curriculum_id=uuid4(),
        subject_id=shared_subject_id,
        is_elective=False,
        is_active=True,
        archived_at=None,
        status="active",
    )
    second_curriculum_subject = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        curriculum_id=uuid4(),
        subject_id=shared_subject_id,
        is_elective=False,
        is_active=True,
        archived_at=None,
        status="active",
    )
    level = SimpleNamespace(status="active", is_active=True, archived_at=None)
    subject = SimpleNamespace(
        id=shared_subject_id,
        name="Mathematics",
        status="active",
        is_active=True,
        archived_at=None,
    )

    first_payload = project_curriculum_subject(
        _Session(
            _Result(
                first=(
                    first_curriculum_subject,
                    SimpleNamespace(id=first_curriculum_subject.curriculum_id),
                    level,
                    subject,
                )
            )
        ),
        tenant_id,
        first_curriculum_subject.id,
    )
    second_payload = project_curriculum_subject(
        _Session(
            _Result(
                first=(
                    second_curriculum_subject,
                    SimpleNamespace(id=second_curriculum_subject.curriculum_id),
                    level,
                    subject,
                )
            )
        ),
        tenant_id,
        second_curriculum_subject.id,
    )

    assert first_payload["subject_id"] == second_payload["subject_id"]
    assert first_payload["id"] != second_payload["id"]
    assert first_payload["curriculum_id"] != second_payload["curriculum_id"]
