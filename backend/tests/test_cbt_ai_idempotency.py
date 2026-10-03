from __future__ import annotations

from app.modules.cbt.ai.idempotency.cache import AIReplayCache
from app.modules.cbt.ai.idempotency.service import CBTAIIdempotentAuthoringService
from app.modules.cbt.ai.schemas import AIGenerateQuestionsRequest


def _request(prompt: str = "Cover photosynthesis") -> AIGenerateQuestionsRequest:
    return AIGenerateQuestionsRequest(
        subject="Biology",
        academic_level="SS 2",
        generation_prompt=prompt,
        question_count=2,
        question_type_counts={"single_choice": 2},
        difficulty="medium",
        visual_mode="auto",
    )


def test_request_hash_is_stable_for_equivalent_payloads() -> None:
    first = CBTAIIdempotentAuthoringService._request_hash(_request())
    second = CBTAIIdempotentAuthoringService._request_hash(_request())
    assert first == second


def test_request_hash_changes_when_logical_request_changes() -> None:
    first = CBTAIIdempotentAuthoringService._request_hash(_request())
    second = CBTAIIdempotentAuthoringService._request_hash(_request("Cover respiration"))
    assert first != second


def test_replay_cache_codec_round_trips_large_image_payload() -> None:
    payload = {
        "questions": [
            {
                "question_type": "single_choice",
                "prompt": "Identify the structure.",
                "image": {
                    "content_type": "image/png",
                    "data_base64": "a" * 50_000,
                    "sha256": "0" * 64,
                    "source": "generated",
                },
                "options": [],
            }
        ],
        "repaired": False,
        "charge": {
            "reservation_id": "00000000-0000-0000-0000-000000000001",
            "credits_charged": 1,
            "credits_released": 0,
        },
    }

    encoded = AIReplayCache.encode(payload)
    assert isinstance(encoded, str)
    assert AIReplayCache.decode(encoded) == payload
