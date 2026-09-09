from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.modules.report_cards.performance_service import calculate_report_performance


def _result(total: str):
    return SimpleNamespace(id=uuid4(), total_score=Decimal(total))


def _components(*maximums: str):
    return [
        (
            SimpleNamespace(id=uuid4(), maximum_score=Decimal(maximum)),
            SimpleNamespace(score=Decimal("0")),
        )
        for maximum in maximums
    ]


def test_weighted_performance_uses_actual_possible_marks_not_subject_average() -> None:
    fifty_mark_subject = _result("40")
    hundred_mark_subject = _result("50")

    performance = calculate_report_performance(
        [fifty_mark_subject, hundred_mark_subject],
        {
            fifty_mark_subject.id: _components("20", "30"),
            hundred_mark_subject.id: _components("40", "60"),
        },
    )

    assert performance is not None
    assert performance.earned_score == Decimal("90.00")
    assert performance.possible_score == Decimal("150.00")
    assert performance.percentage == Decimal("60.00")
    assert performance.subject_count == 2


def test_duplicate_component_rows_do_not_inflate_denominator() -> None:
    result = _result("75")
    component = SimpleNamespace(id=uuid4(), maximum_score=Decimal("100"))
    score = SimpleNamespace(score=Decimal("75"))

    performance = calculate_report_performance(
        [result],
        {result.id: [(component, score), (component, score)]},
    )

    assert performance is not None
    assert performance.possible_score == Decimal("100.00")
    assert performance.percentage == Decimal("75.00")


def test_missing_component_definition_makes_performance_unresolvable() -> None:
    result = _result("50")

    assert calculate_report_performance([result], {}) is None
