from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "20260903_persistent_curriculum_department_scopes.py"
)


def test_persistent_curriculum_cutover_has_one_predecessor_and_no_downgrade_alias() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert (
        'down_revision: Union[str, Sequence[str], None] = "20260901_global_departments"' in source
    )
    assert 'op.drop_table("curriculum_offerings"' in source
    assert "cannot reconstruct removed term-specific curriculum offerings" in source


def test_persistent_scope_foreign_keys_include_tenant_identity() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '["tenant_id", "curriculum_subject_id"]' in source
    assert '["tenant_id", "academic_level_department_id"]' in source
    assert "fk_curriculum_subject_department_tenant_subject" in source
    assert "fk_curriculum_subject_department_tenant_level_department" in source


def test_cbt_sync_enum_is_cut_over_without_offering_compatibility() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "WHERE entity_type = 'subject_offering'" in source
    assert '"curriculum_subject_department"' in source
    assert "DROP TYPE {SCHEMA}.cbt_sync_entity_type_old" in source
