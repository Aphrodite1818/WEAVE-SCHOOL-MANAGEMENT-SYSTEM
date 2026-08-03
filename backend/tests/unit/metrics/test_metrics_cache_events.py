from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.core.cache.events import CACHE_INVALIDATION_EVENTS, CacheInvalidationEvent
from app.modules.communications.enums import CommunicationActorType, NotificationSourceType
from app.modules.communications.models import NotificationDelivery
from app.modules.metrics.cache import (
    parent_dashboard_cache_key,
    student_dashboard_cache_key,
    superadmin_dashboard_cache_key,
    teacher_dashboard_cache_key,
    tenant_admin_dashboard_cache_key,
)
from app.modules.metrics.events import queue_metrics_cache_invalidations
from app.modules.student_academics.models import StudentSubjectResult
from app.tenant_management.models import Tenant


def _session(*objects: object) -> SimpleNamespace:
    return SimpleNamespace(new=list(objects), dirty=[], deleted=[], info={})


def _queued_events(session: SimpleNamespace) -> set[CacheInvalidationEvent]:
    return session.info[CACHE_INVALIDATION_EVENTS]


def test_student_result_change_invalidates_metric_dashboard_sources() -> None:
    tenant_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    student_id = uuid.uuid4()
    result = StudentSubjectResult(
        tenant_id=tenant_id,
        student_id=student_id,
        teacher_membership_id=teacher_id,
    )
    session = _session(result)

    queue_metrics_cache_invalidations(session)

    events = _queued_events(session)
    assert (
        CacheInvalidationEvent(
            kind="key",
            value=tenant_admin_dashboard_cache_key(tenant_id),
        )
        in events
    )
    assert (
        CacheInvalidationEvent(
            kind="key",
            value=teacher_dashboard_cache_key(tenant_id, teacher_id),
        )
        in events
    )
    assert (
        CacheInvalidationEvent(
            kind="key",
            value=student_dashboard_cache_key(tenant_id, student_id),
        )
        in events
    )
    assert (
        CacheInvalidationEvent(
            kind="pattern",
            value=f"tenant:{tenant_id}:dashboard:teacher:*:metrics",
        )
        in events
    )
    assert (
        CacheInvalidationEvent(
            kind="pattern",
            value=f"tenant:{tenant_id}:dashboard:student:*:metrics",
        )
        in events
    )


def test_tenant_change_invalidates_superadmin_metrics() -> None:
    tenant = Tenant(id=uuid.uuid4(), school_name="Example", slug="example", email="a@example.com")
    session = _session(tenant)

    queue_metrics_cache_invalidations(session)

    assert CacheInvalidationEvent(
        kind="key",
        value=superadmin_dashboard_cache_key(),
    ) in _queued_events(session)


def test_parent_notification_delivery_invalidates_parent_dashboard() -> None:
    tenant_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    read = NotificationDelivery(
        tenant_id=tenant_id,
        recipient_actor_type=CommunicationActorType.PARENT,
        recipient_actor_id=parent_id,
        source_type=NotificationSourceType.ANNOUNCEMENT,
        source_id=uuid.uuid4(),
        title="School update",
        preview="A school update is available.",
    )
    session = _session(read)

    queue_metrics_cache_invalidations(session)

    assert CacheInvalidationEvent(
        kind="key",
        value=parent_dashboard_cache_key(tenant_id, parent_id),
    ) in _queued_events(session)
