from __future__ import annotations

import gzip
import json

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.modules.cbt.ai.transport import CBTGZipRoute


class EchoPayload(BaseModel):
    data: str


def _test_app() -> FastAPI:
    app = FastAPI()
    router = APIRouter(route_class=CBTGZipRoute)

    @router.post("/echo", response_model=EchoPayload)
    async def echo(payload: EchoPayload) -> EchoPayload:
        return payload

    app.include_router(router)
    return app


def test_gzip_request_is_decoded_before_pydantic_and_response_is_compressed() -> None:
    raw_json = json.dumps({"data": "x" * 4_000}).encode("utf-8")
    compressed_request = gzip.compress(raw_json)

    with TestClient(_test_app()) as client:
        response = client.post(
            "/echo",
            content=compressed_request,
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
                "Accept-Encoding": "gzip",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.json() == {"data": "x" * 4_000}


def test_unsupported_request_content_encoding_is_rejected() -> None:
    with TestClient(_test_app()) as client:
        response = client.post(
            "/echo",
            content=b"{}",
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "br",
            },
        )

    assert response.status_code == 415
