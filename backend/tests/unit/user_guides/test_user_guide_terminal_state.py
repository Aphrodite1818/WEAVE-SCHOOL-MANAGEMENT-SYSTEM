"""Regression tests for terminal product-guide state transitions."""

from app.modules.user_guides.service import UserGuideService


def test_completed_guide_cannot_be_reopened_by_stale_progress_request() -> None:
    assert UserGuideService._preserve_terminal_state("completed", "in_progress")
    assert UserGuideService._preserve_terminal_state("completed", "not_started")
    assert UserGuideService._preserve_terminal_state("completed", None)
    assert not UserGuideService._preserve_terminal_state("completed", "completed")


def test_dismissed_guide_can_only_remain_dismissed_or_be_completed() -> None:
    assert UserGuideService._preserve_terminal_state("dismissed", "in_progress")
    assert UserGuideService._preserve_terminal_state("dismissed", "not_started")
    assert not UserGuideService._preserve_terminal_state("dismissed", "dismissed")
    assert not UserGuideService._preserve_terminal_state("dismissed", "completed")


def test_non_terminal_guide_can_progress_normally() -> None:
    assert not UserGuideService._preserve_terminal_state("not_started", "in_progress")
    assert not UserGuideService._preserve_terminal_state("in_progress", "completed")
