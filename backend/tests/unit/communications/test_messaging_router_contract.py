from __future__ import annotations

import inspect

from app.modules.communications import router as communications_router


def test_conversation_get_is_read_only_and_read_receipt_has_explicit_endpoint() -> None:
    get_source = inspect.getsource(communications_router.get_conversation)
    read_source = inspect.getsource(communications_router.mark_conversation_read)

    assert "MessagingService.get_conversation" in get_source
    assert "MessagingService.mark_read" not in get_source
    assert "MessagingService.mark_read" in read_source
