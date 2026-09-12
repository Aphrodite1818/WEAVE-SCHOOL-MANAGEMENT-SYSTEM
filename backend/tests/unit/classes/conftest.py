from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_legacy_classroom_lifecycle_from_current_term_guard(request):
    """The legacy lifecycle module tests class identity/lifecycle in isolation.

    Current-term specialization integrity has dedicated coverage in
    test_current_term_structure_integrity.py. Keep the older lifecycle tests
    focused on their original contract instead of making their structure mocks
    fabricate an AcademicLevel for the new guard.
    """

    if request.node.path.name != "test_classroom_lifecycle.py":
        yield
        return

    with patch(
        "app.modules.classes.service.CurrentTermStructureIntegrity.requirement_for_active_class",
        new=AsyncMock(return_value=None),
    ):
        yield
