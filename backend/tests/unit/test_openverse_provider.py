"""Openverse regressions with intercepted HTTP; no external requests."""

import asyncio
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from app.modules.cbt.ai.providers import openverse as module


def provider(**kwargs):
    return module.OpenverseImageSearchProvider(
        client_id=kwargs.pop("client_id", ""),
        client_secret=kwargs.pop("client_secret", ""),
        **kwargs,
    )


def mock_http(monkeypatch, handler):
    client_class = httpx.AsyncClient
    calls = []

    async def respond(request):
        calls.append(request)
        await asyncio.sleep(0)
        return handler(request)

    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(respond), **kwargs),
    )
    return calls


def candidate(**overrides):
    return {
        "id": "example",
        "url": "https://example.org/image.jpg",
        "foreign_landing_url": "https://example.org/source",
        "license": "by",
        "license_version": "4.0",
        "filetype": "jpg",
        "width": 800,
        "height": 600,
        "mature": False,
        **overrides,
    }


async def test_anonymous_search(monkeypatch):
    calls = mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"results": [None, candidate(mature=True), candidate(), candidate()]}
        ),
    )
    p = provider()
    assert p.is_configured()
    results = await p.search(query=" diagram ", limit=1)
    assert len(results) == 1
    assert results[0].license_name == "CC BY 4.0"
    assert results[0].mime_type == "image/jpeg"
    assert "Authorization" not in calls[0].headers
    assert calls[0].url.params["q"] == "diagram"
    assert calls[0].url.params["mature"] == "false"
    assert calls[0].url.params["license_type"] == "commercial"


@pytest.mark.parametrize("credentials", [{"client_id": "id"}, {"client_secret": "secret"}])
async def test_partial_credentials(credentials):
    p = provider(**credentials)
    assert not p.is_configured()
    with pytest.raises(module.OpenverseProviderConfigurationError):
        await p.search(query="test")


async def test_token_lock_cache_and_refresh(monkeypatch):
    def respond(request):
        if request.method == "POST":
            assert parse_qs(request.content.decode())["grant_type"] == ["client_credentials"]
            return httpx.Response(200, json={"access_token": "test-token", "expires_in": 100})
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"results": []})

    calls = mock_http(monkeypatch, respond)
    p = provider(client_id="id", client_secret=SecretStr("secret"))
    assert p.is_configured()
    await asyncio.gather(*(p.search(query="test") for _ in range(5)))
    assert sum(c.method == "POST" for c in calls) == 1
    p._access_token_expires_at = 0
    await p.search(query="test")
    assert sum(c.method == "POST" for c in calls) == 2


@pytest.mark.parametrize("lifetime", [None, 0, -1, True, "3600"])
async def test_bad_token_lifetime(monkeypatch, lifetime):
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"access_token": "test-token", "expires_in": lifetime}
        ),
    )
    p = provider(client_id="id", client_secret="secret")
    with pytest.raises(module.OpenverseProviderError, match="lifetime"):
        await p.search(query="test")
    assert p._access_token is None


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, text="private upstream content"),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={}),
        httpx.ReadTimeout("timeout"),
        httpx.ConnectError("failed"),
    ],
)
async def test_provider_errors(monkeypatch, authenticated, response):
    def respond(request):
        if isinstance(response, Exception):
            raise response
        return response

    mock_http(monkeypatch, respond)
    p = provider(client_id="id", client_secret="secret") if authenticated else provider()
    with pytest.raises(module.OpenverseProviderError) as error:
        await p.search(query="test")
    assert "private upstream content" not in str(error.value)
    if isinstance(response, httpx.Response) and response.is_error:
        assert error.value.status_code == 429


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2"])
async def test_invalid_limit(limit):
    with pytest.raises(ValueError, match="positive integer"):
        await provider().search(query="test", limit=limit)


@pytest.mark.parametrize("query", [" ", "a" * 201])
async def test_invalid_query(query):
    with pytest.raises(ValueError):
        await provider().search(query=query)


@pytest.mark.parametrize(
    "overrides,metadata",
    [
        ({"url": "https://[invalid"}, {}),
        ({"url": "https://example.org:bad/a"}, {}),
        ({"url": "javascript:alert(1)"}, {}),
        ({"license": None}, {}),
        ({"foreign_landing_url": None}, {}),
        ({"width": None}, {"min_width": 100}),
        ({"height": 50}, {"min_height": 100}),
        ({"filetype": None}, {"allowed_mime_types": ["image/jpeg"]}),
        ({"filetype": "jpg"}, {"allowed_mime_types": "image/jpeg2000"}),
    ],
)
def test_candidate_filtering(overrides, metadata):
    assert provider()._normalize_candidate(candidate(**overrides), metadata=metadata) is None


def test_page_size_bounds():
    assert provider()._build_search_params(query="test", limit=100, metadata={})["page_size"] == 20
    assert (
        provider(client_id="id", client_secret="secret")._build_search_params(
            query="test", limit=100, metadata={}
        )["page_size"]
        == 50
    )
