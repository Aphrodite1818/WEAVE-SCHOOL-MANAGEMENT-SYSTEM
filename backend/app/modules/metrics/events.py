"""ORM-driven invalidation for dashboard metric caches."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.cache.events import (
    CACHE_INVALIDATION_EVENTS,
    CacheInvalidationEvent,
)
from app.core.cache.base import build_cache_key, tenant_prefix
from app.modules.announcements.models import (
    Announcement,
    AnnouncementRead,
    AnnouncementRecipientRole,
    AnnouncementTarget,
)
from app.modules.classes.models import ClassRoom
from app.modules.metrics.cache import (
    parent_dashboard_cache_key,
    student_dashboard_cache_key,
    superadmin_dashboard_cache_key,
    teacher_dashboard_cache_key,
    tenant_admin_dashboard_cache_key,
)
from app.modules.parents.models import ParentAccount, ParentMembership
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    ClassSubject,
    ClassSubjectTeacher,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.students.models import Student, StudentEnrollment, StudentParentLink
from app.modules.subjects.models import Subject
from app.modules.subscriptions.models import TenantSubscription
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherMembership,
    TeacherMembershipSubject,
)
from app.tenant_management.models import Tenant


TENANT_ADMIN_METRIC_MODELS = (
    AcademicSession,
    AcademicTerm,
    Announcement,
    AnnouncementRead,
    AnnouncementTarget,
    ClassRoom,
    ClassSubject,
    ClassSubjectTeacher,
    ParentAccount,
    ParentMembership,
    ReportCard,
    Student,
    StudentEnrollment,
    StudentParentLink,
    StudentSubjectResult,
    Subject,
    TeacherAccount,
    TeacherAssignment,
    TeacherMembership,
    TeacherMembershipSubject,
)

SUPERADMIN_METRIC_MODELS = (
    Tenant,
    TenantSubscription,
)


def _coerce_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _queue_key(session: Session, key: str) -> None:
    bucket = session.info.setdefault(CACHE_INVALIDATION_EVENTS, set())
    bucket.add(CacheInvalidationEvent(kind="key", value=key))


def _queue_pattern(session: Session, pattern: str) -> None:
    bucket = session.info.setdefault(CACHE_INVALIDATION_EVENTS, set())
    bucket.add(CacheInvalidationEvent(kind="pattern", value=pattern))


def _dashboard_actor_pattern(tenant_id: UUID, actor_type: str) -> str:
    return build_cache_key(
        tenant_prefix(str(tenant_id)),
        "dashboard",
        actor_type,
        "*",
        "metrics",
    )


def _iter_changed_objects(session: Session) -> Iterable[object]:
    yield from session.new
    yield from session.dirty
    yield from session.deleted


def _queue_tenant_dashboard(session: Session, tenant_id: UUID | None) -> None:
    if tenant_id is not None:
        _queue_key(session, tenant_admin_dashboard_cache_key(tenant_id))


def _queue_tenant_actor_dashboards(session: Session, tenant_id: UUID | None) -> None:
    if tenant_id is None:
        return
    _queue_pattern(session, _dashboard_actor_pattern(tenant_id, "teacher"))
    _queue_pattern(session, _dashboard_actor_pattern(tenant_id, "parent"))
    _queue_pattern(session, _dashboard_actor_pattern(tenant_id, "student"))


def _queue_teacher_dashboard(
    session: Session,
    tenant_id: UUID | None,
    teacher_id: UUID | None,
) -> None:
    if tenant_id is not None and teacher_id is not None:
        _queue_key(session, teacher_dashboard_cache_key(tenant_id, teacher_id))


def _queue_parent_dashboard(
    session: Session,
    tenant_id: UUID | None,
    parent_id: UUID | None,
) -> None:
    if tenant_id is not None and parent_id is not None:
        _queue_key(session, parent_dashboard_cache_key(tenant_id, parent_id))


def _queue_student_dashboard(
    session: Session,
    tenant_id: UUID | None,
    student_id: UUID | None,
) -> None:
    if tenant_id is not None and student_id is not None:
        _queue_key(session, student_dashboard_cache_key(tenant_id, student_id))


def _queue_metric_invalidations_for_object(session: Session, obj: object) -> None:
    tenant_id = _coerce_uuid(getattr(obj, "tenant_id", None))

    if isinstance(obj, SUPERADMIN_METRIC_MODELS):
        _queue_key(session, superadmin_dashboard_cache_key())
        if isinstance(obj, Tenant):
            tenant_id = _coerce_uuid(obj.id)

    if isinstance(obj, TENANT_ADMIN_METRIC_MODELS):
        _queue_tenant_dashboard(session, tenant_id)
        _queue_tenant_actor_dashboards(session, tenant_id)

    if isinstance(obj, ClassRoom):
        _queue_teacher_dashboard(
            session,
            tenant_id,
            _coerce_uuid(obj.teacher_membership_id),
        )

    if isinstance(obj, TeacherMembership):
        _queue_teacher_dashboard(session, tenant_id, _coerce_uuid(obj.id))

    if isinstance(obj, (TeacherAssignment, ClassSubjectTeacher)):
        _queue_teacher_dashboard(
            session,
            tenant_id,
            _coerce_uuid(obj.teacher_membership_id),
        )

    if isinstance(obj, StudentSubjectResult):
        _queue_teacher_dashboard(
            session,
            tenant_id,
            _coerce_uuid(obj.teacher_membership_id),
        )
        _queue_student_dashboard(session, tenant_id, _coerce_uuid(obj.student_id))

    if isinstance(obj, Student):
        _queue_student_dashboard(session, tenant_id, _coerce_uuid(obj.id))

    if isinstance(obj, StudentParentLink):
        _queue_parent_dashboard(
            session,
            tenant_id,
            _coerce_uuid(obj.parent_membership_id),
        )
        _queue_student_dashboard(session, tenant_id, _coerce_uuid(obj.student_id))

    if isinstance(obj, ParentMembership):
        _queue_parent_dashboard(session, tenant_id, _coerce_uuid(obj.id))

    if isinstance(obj, AnnouncementRead):
        actor_id = _coerce_uuid(obj.actor_id)
        if obj.actor_type == AnnouncementRecipientRole.PARENT:
            _queue_parent_dashboard(session, tenant_id, actor_id)
        elif obj.actor_type == AnnouncementRecipientRole.STUDENT:
            _queue_student_dashboard(session, tenant_id, actor_id)


def queue_metrics_cache_invalidations(
    session: Session,
    flush_context: object | None = None,
) -> None:
    """Queue dashboard invalidations for ORM changes flushed by this session."""

    _ = flush_context
    for obj in _iter_changed_objects(session):
        _queue_metric_invalidations_for_object(session, obj)


def register_metrics_cache_invalidation_events() -> None:
    """Install dashboard metric cache invalidation listeners once."""

    if event.contains(Session, "after_flush", queue_metrics_cache_invalidations):
        return
    event.listen(Session, "after_flush", queue_metrics_cache_invalidations)
