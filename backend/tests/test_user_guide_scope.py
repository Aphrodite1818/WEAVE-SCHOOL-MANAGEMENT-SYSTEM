import uuid

from app.modules.user_guides.service import UserGuideService


class TeacherMembership:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.teacher_account_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()


class ParentMembership:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.parent_account_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()


class TenantAdmin:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()


class Student:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()


def test_teacher_guide_scope_is_global_to_the_teacher_account() -> None:
    actor = TeacherMembership()

    context = UserGuideService.actor_context(actor)

    assert context.actor_type == "teacher_account"
    assert context.actor_id == actor.teacher_account_id
    assert context.tenant_id is None
    assert context.scope_key == "global"


def test_parent_guide_scope_is_global_to_the_parent_account() -> None:
    actor = ParentMembership()

    context = UserGuideService.actor_context(actor)

    assert context.actor_type == "parent_account"
    assert context.actor_id == actor.parent_account_id
    assert context.tenant_id is None
    assert context.scope_key == "global"


def test_tenant_admin_guide_scope_remains_per_school() -> None:
    actor = TenantAdmin()

    context = UserGuideService.actor_context(actor)

    assert context.actor_type == "tenant_admin"
    assert context.actor_id == actor.id
    assert context.tenant_id == actor.tenant_id
    assert context.scope_key == str(actor.tenant_id)


def test_student_guide_scope_remains_per_school_identity() -> None:
    actor = Student()

    context = UserGuideService.actor_context(actor)

    assert context.actor_type == "student"
    assert context.actor_id == actor.id
    assert context.tenant_id == actor.tenant_id
    assert context.scope_key == str(actor.tenant_id)
