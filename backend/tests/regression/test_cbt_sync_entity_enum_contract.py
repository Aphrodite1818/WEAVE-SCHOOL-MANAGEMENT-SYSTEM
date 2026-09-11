"""The frozen baseline and runtime expose one CBT sync entity contract."""

from __future__ import annotations

from pathlib import Path

from app.modules.cbt.sync.enums import CBTSyncEntityType

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = (
    ROOT / "alembic" / "versions" / "20260911_initial_schema_initial_production_schema.py"
)


def test_initial_baseline_tracks_runtime_contract() -> None:
    source = BASELINE_PATH.read_text(encoding="utf-8")
    for member in CBTSyncEntityType:
        assert repr(member.value) in source


def test_initial_baseline_has_no_obsolete_subject_offering_enum_value() -> None:
    source = BASELINE_PATH.read_text(encoding="utf-8")
    assert "'subject_offering'" not in source
