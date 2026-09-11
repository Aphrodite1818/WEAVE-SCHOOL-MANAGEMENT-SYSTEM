from app.core.exceptions import ConflictException


def test_conflict_uses_concrete_blocker_messages_as_user_detail() -> None:
    blockers = [
        "Activate at least one academic level before opening the term.",
        "Create at least one active class before opening the term.",
    ]

    error = ConflictException(
        "Academic term cannot be opened until class specializations are ready.",
        payload={
            "blocker_messages": blockers,
            "dependency_counts": {
                "active_academic_levels": 0,
                "active_classes": 0,
                "classes_missing_department": 0,
            },
        },
    )

    assert error.detail == " ".join(blockers)
    assert error.payload["blocker_messages"] == blockers


def test_conflict_keeps_specific_detail_when_no_blockers_are_supplied() -> None:
    error = ConflictException("Another academic term is currently open. Close it first.")

    assert error.detail == "Another academic term is currently open. Close it first."
    assert error.payload == {}


def test_conflict_keeps_specific_detail_for_empty_blocker_list() -> None:
    error = ConflictException(
        "Academic term cannot be opened until its calendar is ready.",
        payload={"blocker_messages": []},
    )

    assert error.detail == "Academic term cannot be opened until its calendar is ready."


def test_conflict_filters_blank_blocker_messages() -> None:
    error = ConflictException(
        "Generic readiness failure.",
        payload={
            "blocker_messages": [
                "",
                "  ",
                "1 active class belongs to an inactive or missing academic level.",
            ]
        },
    )

    assert (
        error.detail
        == "1 active class belongs to an inactive or missing academic level."
    )
