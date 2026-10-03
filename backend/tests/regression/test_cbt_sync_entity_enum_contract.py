"""The frozen baseline and runtime expose one CBT sync entity contract."""

from __future__ import annotations

import ast
from pathlib import Path

from app.modules.cbt.sync.enums import CBTSyncEntityType

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = (
    ROOT / "alembic" / "versions" / "20260911_initial_schema_initial_production_schema.py"
)


def test_initial_baseline_tracks_runtime_contract() -> None:
    tree = ast.parse(BASELINE_PATH.read_text(encoding="utf-8"))
    enum = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Enum"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "cbt_sync_entity_type"
            for keyword in node.keywords
        )
    )
    frozen_values = {ast.literal_eval(value) for value in enum.args}
    assert frozen_values == {member.value for member in CBTSyncEntityType}


def test_initial_baseline_has_no_obsolete_subject_offering_enum_value() -> None:
    source = BASELINE_PATH.read_text(encoding="utf-8")
    assert "'subject_offering'" not in source
