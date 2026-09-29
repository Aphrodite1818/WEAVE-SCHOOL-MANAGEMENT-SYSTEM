"""Openverse regressions with intercepted HTTP; no external requests."""

import asyncio
import time
from unittest.mock import AsyncMock
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


async def test_token_lock_cache_and_refresh(monkeypatch, redis_cache):
    def respond(request):
        if request.method == "POST":
            assert parse_qs(request.content.decode())["grant_type"] == ["client_credentials"]
            return httpx.Response(200, json={"access_token": "test-token", "expires_in": 100})
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"results": []})

    calls = mock_http(monkeypatch, respond)
    p = provider(client_id="id", client_secret=SecretStr("secret"))
    assert p.is_configured()
    await asyncio.gather(
        *(provider(client_id="id", client_secret="secret").search(query="test") for _ in range(5))
    )
    assert sum(c.method == "POST" for c in calls) == 1
    redis_cache.expires[p._token_cache_key] = 0
    await p.search(query="test")
    assert sum(c.method == "POST" for c in calls) == 2


@pytest.mark.parametrize("lifetime", [None, 0, -1, True, "3600"])
async def test_bad_token_lifetime(monkeypatch, lifetime, redis_cache):
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"access_token": "test-token", "expires_in": lifetime}
        ),
    )
    p = provider(client_id="id", client_secret="secret")
    with pytest.raises(module.OpenverseProviderError, match="lifetime"):
        await p.search(query="test")
    assert await redis_cache.get(p._token_cache_key) is None
    assert await redis_cache.get(p._token_lock_key) is None


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


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expires = {}

    async def get(self, key):
        if time.monotonic() >= self.expires.get(key, 0):
            self.values.pop(key, None)
        return self.values.get(key)

    async def set(self, key, value, *, nx=False, ex):
        if nx and await self.get(key) is not None:
            return False
        self.values[key] = value
        self.expires[key] = time.monotonic() + ex
        return True

    async def eval(self, script, numkeys, *args):
        lock_key = args[0]
        owner = args[numkeys]
        if await self.get(lock_key) != owner:
            return 0
        if numkeys == 2:
            await self.set(args[1], args[3], ex=args[4])
        else:
            self.values.pop(lock_key, None)
        return 1


@pytest.fixture(autouse=True)
def redis_cache(monkeypatch):
    cache = FakeRedis()
    monkeypatch.setattr(module, "get_redis", lambda: cache)
    return cache


async def test_missing_redis_only_blocks_authenticated_requests(monkeypatch):
    monkeypatch.setattr(module, "get_redis", lambda: None)
    assert await provider()._get_headers() == {"Accept": "application/json"}
    with pytest.raises(module.OpenverseProviderError, match="unavailable"):
        await provider(client_id="id", client_secret="secret")._get_headers()


async def test_redis_failure(monkeypatch, redis_cache):
    monkeypatch.setattr(redis_cache, "get", AsyncMock(side_effect=module.RedisError("failure")))
    with pytest.raises(module.OpenverseProviderError, match="cache is unavailable"):
        await provider(client_id="id", client_secret="secret")._get_headers()


def test_credential_and_endpoint_cache_isolation():
    first = provider(client_id="one", client_secret="secret")
    assert (
        first._token_cache_key != provider(client_id="two", client_secret="secret")._token_cache_key
    )
    assert (
        first._token_cache_key
        != provider(client_id="one", client_secret="rotated")._token_cache_key
    )
    assert (
        first._token_cache_key
        != provider(
            client_id="one", client_secret="secret", base_url="https://other.example"
        )._token_cache_key
    )
    assert "secret" not in first._token_cache_key


async def test_lock_wait_is_bounded(redis_cache):
    p = provider(client_id="id", client_secret="secret", timeout=0.01)
    p.LOCK_SAFETY_BUFFER_SECONDS = 0
    await redis_cache.set(p._token_lock_key, "another-worker", ex=30)
    with pytest.raises(module.OpenverseProviderError, match="timed out"):
        await p._get_access_token()
    assert await redis_cache.get(p._token_lock_key) == "another-worker"


async def test_lost_lock_cannot_publish_or_delete_successor(monkeypatch, redis_cache):
    p = provider(client_id="id", client_secret="secret")

    async def refresh():
        await redis_cache.set(p._token_lock_key, "successor", ex=30)
        return "stale-token", 3600

    monkeypatch.setattr(p, "_request_access_token", refresh)
    with pytest.raises(module.OpenverseProviderError, match="lock expired"):
        await p._get_access_token()
    assert await redis_cache.get(p._token_cache_key) is None
    assert await redis_cache.get(p._token_lock_key) == "successor"


async def test_cancelled_refresh_releases_lock(monkeypatch, redis_cache):
    p = provider(client_id="id", client_secret="secret")
    started = asyncio.Event()

    async def refresh():
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(p, "_request_access_token", refresh)
    task = asyncio.create_task(p._get_access_token())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await redis_cache.get(p._token_lock_key) is None
