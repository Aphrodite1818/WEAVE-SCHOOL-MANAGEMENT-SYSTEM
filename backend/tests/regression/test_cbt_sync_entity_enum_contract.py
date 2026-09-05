from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENUM_PATH = ROOT / "app" / "modules" / "cbt" / "sync" / "enums.py"
MIGRATION_PATH = ROOT / "alembic" / "versions" / "20260905_cbt_sync_entity_enum_repair.py"


def _assigned_tuple(path: Path, name: str) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"{name} is missing from {path}")


def _enum_values() -> tuple[str, ...]:
    tree = ast.parse(ENUM_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CBTSyncEntityType":
            values = []
            for statement in node.body:
                if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
                    if isinstance(statement.value.value, str):
                        values.append(statement.value.value)
            return tuple(values)
    raise AssertionError("CBTSyncEntityType is missing")


class CBTSyncEntityEnumContractTests(unittest.TestCase):
    def test_repair_tracks_runtime_contract(self) -> None:
        self.assertEqual(
            set(_assigned_tuple(MIGRATION_PATH, "CBT_SYNC_ENTITY_VALUES")),
            set(_enum_values()),
        )

    def test_repair_is_idempotent_and_forward_only(self) -> None:
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("ADD VALUE IF NOT EXISTS", source)
        self.assertIn("autocommit_block", source)
        self.assertIn("intentionally irreversible", source)

    def test_repair_follows_curriculum_cutover_head(self) -> None:
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn('down_revision: Union[str, Sequence[str], None] = "20260903_curriculum_scopes"', source)


if __name__ == "__main__":
    unittest.main()
