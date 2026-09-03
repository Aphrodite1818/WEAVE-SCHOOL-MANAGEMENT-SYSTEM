"""CBT sync v5 event wiring for level-department specialization identities.

The base recorder owns transaction/savepoint semantics. CBT department identity is
the AcademicLevelDepartment mapping UUID, while canonical Department mutations
refresh every derived mapping projection. Curriculum subject applicability is
persistent and projected through CurriculumSubjectDepartment.
"""

from __future__ import annotations

from app.modules.cbt.sync import model_events as _events
from app.modules.cbt.sync.enums import CBTSyncEntityType
from app.modules.classes.models import AcademicLevelDepartment, Department


_events.MODEL_ENTITY_TYPES[AcademicLevelDepartment] = CBTSyncEntityType.DEPARTMENT
_events.ENTITY_MODELS[CBTSyncEntityType.DEPARTMENT] = AcademicLevelDepartment

_original_identity_from_object = _events._identity_from_object
_original_expand_derived_contracts = _events._expand_derived_contracts


def _identity_from_object(pending):
    # Canonical Department is a cloud-side pool identity. CBT consumes the exact
    # level-department mapping, so never emit the canonical UUID directly.
    if isinstance(pending.obj, Department):
        return None
    return _original_identity_from_object(pending)


def _expand_derived_contracts(session, pending_objects, events):
    _original_expand_derived_contracts(session, pending_objects, events)

    for pending in pending_objects:
        obj = pending.obj
        tenant_id = getattr(obj, "tenant_id", None)
        if tenant_id is None:
            continue

        if isinstance(obj, Department):
            _events._append_refreshes(
                session,
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.DEPARTMENT,
            )
            _events._append_refreshes(
                session,
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
            )
            _events._append_refreshes(
                session,
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.TEACHER_ASSIGNMENT,
            )
        elif isinstance(obj, AcademicLevelDepartment):
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.CURRICULUM_SUBJECT_DEPARTMENT,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
            ):
                _events._append_refreshes(
                    session,
                    events,
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                )


_events._identity_from_object = _identity_from_object
_events._expand_derived_contracts = _expand_derived_contracts
