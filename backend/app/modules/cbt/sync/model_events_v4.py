"""CBT sync v4 event wiring for level-department specialization identities.

The existing recorder owns transaction/savepoint semantics. This module changes only
the v4 identity contract: CBT departments are AcademicLevelDepartment mappings,
while canonical Department mutations refresh every derived mapping projection.
"""

from __future__ import annotations

from app.modules.cbt.sync import model_events as _events
from app.modules.cbt.sync.enums import CBTSyncEntityType
from app.modules.classes.models import AcademicLevelDepartment, Department


# Keep canonical Department changes observable by the recorder so their derived
# mapping projections can be refreshed, but never emit the canonical pool UUID as
# a CBT department identity.
_events.MODEL_ENTITY_TYPES[AcademicLevelDepartment] = CBTSyncEntityType.DEPARTMENT
_events.ENTITY_MODELS[CBTSyncEntityType.DEPARTMENT] = AcademicLevelDepartment

_original_identity_from_object = _events._identity_from_object
_original_expand_derived_contracts = _events._expand_derived_contracts


def _identity_from_object(pending):
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
            # Name/lifecycle changes on the canonical pool change every level
            # mapping snapshot that references this Department.
            _events._append_refreshes(
                session,
                events,
                tenant_id=tenant_id,
                entity_type=CBTSyncEntityType.DEPARTMENT,
            )
        elif isinstance(obj, AcademicLevelDepartment):
            # Mapping availability determines class specialization, scoped
            # offerings and therefore teacher assignment eligibility.
            for entity_type in (
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTSyncEntityType.SUBJECT_OFFERING,
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
