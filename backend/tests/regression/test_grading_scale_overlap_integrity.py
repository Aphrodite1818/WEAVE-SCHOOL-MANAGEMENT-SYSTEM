from decimal import Decimal

from app.modules.student_academics.grading_scale_integrity import ranges_overlap


def test_exact_duplicate_grading_range_overlaps() -> None:
    assert ranges_overlap(
        Decimal("70"),
        Decimal("100"),
        Decimal("70"),
        Decimal("100"),
    )


def test_partial_grading_range_overlap_is_rejected() -> None:
    assert ranges_overlap(
        Decimal("50"),
        Decimal("69.99"),
        Decimal("60"),
        Decimal("79.99"),
    )


def test_shared_inclusive_boundary_overlaps() -> None:
    assert ranges_overlap(
        Decimal("0"),
        Decimal("50"),
        Decimal("50"),
        Decimal("59.99"),
    )


def test_adjacent_non_overlapping_grading_ranges_are_allowed() -> None:
    assert not ranges_overlap(
        Decimal("0"),
        Decimal("49.99"),
        Decimal("50"),
        Decimal("59.99"),
    )
