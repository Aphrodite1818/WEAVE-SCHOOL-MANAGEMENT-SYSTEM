"""Gemini contract regressions; all HTTP traffic is intercepted."""

import json
from typing import get_type_hints

import httpx
import pytest
from pydantic import SecretStr

from app.modules.cbt.ai.authoring.providers import gemini
from app.modules.cbt.ai.authoring.providers.base import (
    BaseQuestionGenerationProvider,
    ProviderImageGenerationResult,
    ProviderQuestionGenerationResult,
    ProviderQuestionRegenerationResult,
)


def mock_http(monkeypatch, response):
    requests = []

    def handle(request):
        requests.append(request)
        if isinstance(response, Exception):
            raise response
        return response

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        gemini.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs),
    )
    return requests


def content(parts):
    return {"candidates": [{"content": {"parts": parts}}]}


@pytest.mark.parametrize(
    "method,key,result_type",
    [
        ("generate_questions", "questions", ProviderQuestionGenerationResult),
        ("regenerate_question", "question", ProviderQuestionRegenerationResult),
    ],
)
async def test_question_contract(monkeypatch, method, key, result_type):
    value = [{"stem": "Example"}] if key == "questions" else {"stem": "Example"}
    text = json.dumps({key: value})
    body = content(
        [{"text": "reasoning", "thought": True}, {"text": text[:20]}, {"text": text[20:]}]
    )
    body["usageMetadata"] = {
        "promptTokenCount": 10,
        "candidatesTokenCount": 4,
        "thoughtsTokenCount": 2,
        "cachedContentTokenCount": 3,
    }
    calls = mock_http(monkeypatch, httpx.Response(200, json=body))
    provider = gemini.GeminiQuestionGenerationProvider(
        api_key=SecretStr(" test-key "), model="test"
    )
    result = await getattr(provider, method)(request={"topic": "Math"})
    assert isinstance(result, result_type)
    assert getattr(result, key) == value
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 6
    assert result.usage.cache_read_tokens == 3
    assert calls[0].headers["x-goog-api-key"] == "test-key"
    assert (
        str(calls[0].url)
        == gemini.settings.GEMINI_BASE_URL.rstrip("/") + "/models/test:generateContent"
    )
    payload = json.loads(calls[0].content)
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert json.loads(payload["contents"][0]["parts"][0]["text"]) == {"topic": "Math"}
    assert get_type_hints(BaseQuestionGenerationProvider.regenerate_question)


async def test_missing_credentials(monkeypatch):
    monkeypatch.setattr(gemini.settings, "GEMINI_API_KEY", None)
    calls = mock_http(monkeypatch, httpx.Response(200, json={}))
    provider = gemini.GeminiQuestionGenerationProvider()
    assert not provider.is_configured()
    with pytest.raises(gemini.GeminiProviderNotConfiguredError):
        await provider.generate_questions(request={})
    assert not calls


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json=[]),
        httpx.Response(403, json={"error": {"message": "private upstream content"}}),
        httpx.Response(500, text="private upstream content"),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json=[]),
        httpx.ReadTimeout("timeout"),
        httpx.ConnectError("connection failed"),
    ],
)
async def test_http_errors(monkeypatch, response):
    mock_http(monkeypatch, response)
    provider = gemini.GeminiQuestionGenerationProvider(api_key="test-key")
    with pytest.raises(gemini.GeminiProviderError) as error:
        await provider.generate_questions(request={})
    assert "private upstream content" not in str(error.value)
    if isinstance(response, httpx.Response) and response.is_error:
        assert error.value.status_code == response.status_code


@pytest.mark.parametrize(
    "body",
    [
        {},
        content([]),
        content([{"text": "{"}]),
        content([{"text": "[]"}]),
        content([{"text": '{"questions": [1]}'}]),
    ],
)
async def test_invalid_question_responses(monkeypatch, body):
    mock_http(monkeypatch, httpx.Response(200, json=body))
    with pytest.raises(gemini.GeminiProviderError):
        await gemini.GeminiQuestionGenerationProvider(api_key="test-key").generate_questions(
            request={}
        )


async def test_image_contract(monkeypatch):
    body = content([{"inlineData": {"mimeType": "image/png", "data": "dGVzdA=="}}])
    calls = mock_http(monkeypatch, httpx.Response(200, json=body))
    result = await gemini.GeminiImageGenerationProvider(api_key="test-key").generate_image(
        prompt=" Diagram ", metadata={"role": "stem"}
    )
    assert isinstance(result, ProviderImageGenerationResult)
    assert result.image.content_type == "image/png"
    assert result.image.data_base64 == "dGVzdA=="
    assert "stem" in json.loads(calls[0].content)["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize(
    "kwargs", [{"prompt": " "}, {"prompt": "test", "reference_images": ["ref"]}]
)
async def test_invalid_image_requests(monkeypatch, kwargs):
    calls = mock_http(monkeypatch, httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        await gemini.GeminiImageGenerationProvider(api_key="test-key").generate_image(**kwargs)
    assert not calls


def test_malformed_usage():
    usage = gemini._GeminiHTTPProvider._extract_usage(
        {
            "usageMetadata": {
                "promptTokenCount": "invalid",
                "candidatesTokenCount": -1,
                "cachedContentTokenCount": True,
            }
        }
    )
    assert usage.input_tokens == usage.output_tokens == usage.cache_read_tokens == 0
