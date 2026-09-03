from uuid import uuid4

from app.modules.cbt.academics.schemas import CBTAcademicLevelSnapshot


def test_cbt_v3_academic_level_snapshot_does_not_expose_lifecycle_status() -> None:
    snapshot = CBTAcademicLevelSnapshot(
        id=uuid4(),
        name="SS1",
        category="SENIOR_SECONDARY",
        position=1,
    )

    payload = snapshot.model_dump(mode="json")

    assert payload == {
        "id": str(snapshot.id),
        "name": "SS1",
        "category": "SENIOR_SECONDARY",
        "position": 1,
        "specialization_required_from_term_position": None,
    }
    assert "status" not in payload
