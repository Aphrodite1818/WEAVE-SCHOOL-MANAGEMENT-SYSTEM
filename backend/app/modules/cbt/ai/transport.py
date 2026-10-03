"""HTTP transport helpers for large CBT AI JSON/image payloads."""

from __future__ import annotations

import gzip
import zlib
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


class CBTGZipRoute(APIRoute):
    """Support bounded gzip requests and responses for CBT AI routes.

    Base64 remains a JSON-boundary representation only. Compression applies to
    the complete HTTP JSON body and is transparent to the application service.
    Both compressed and ordinary request bodies are read with hard limits before
    FastAPI/Pydantic parsing so oversized payloads cannot be allocated unchecked.
    """

    MIN_RESPONSE_BYTES = 1_024
    MAX_COMPRESSED_REQUEST_BYTES = 24 * 1024 * 1024
    MAX_DECOMPRESSED_REQUEST_BYTES = 32 * 1024 * 1024
    MAX_PLAIN_REQUEST_BYTES = 32 * 1024 * 1024
    COMPRESS_LEVEL = 6

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            encoding = self._header(request.scope, b"content-encoding")
            normalized_encoding = (
                encoding.decode("latin-1").strip().casefold() if encoding else "identity"
            )

            if normalized_encoding == "gzip":
                failure = await self._prepare_gzip_request(request)
            elif normalized_encoding == "identity":
                failure = await self._prepare_plain_request(request)
            else:
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={"detail": "Unsupported Content-Encoding for CBT AI request"},
                )

            if failure is not None:
                return failure

            response = await original_handler(request)
            self._compress_response_if_accepted(request, response)
            return response

        return custom_handler

    @classmethod
    async def _prepare_plain_request(cls, request: Request) -> Response | None:
        try:
            body = await cls._read_limited_body(
                request,
                max_bytes=cls.MAX_PLAIN_REQUEST_BYTES,
            )
        except OverflowError:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "CBT AI request body is too large"},
            )

        request._body = body
        return None

    @classmethod
    async def _prepare_gzip_request(cls, request: Request) -> Response | None:
        try:
            compressed = await cls._read_limited_body(
                request,
                max_bytes=cls.MAX_COMPRESSED_REQUEST_BYTES,
            )
        except OverflowError:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Compressed CBT AI request body is too large"},
            )

        try:
            decompressed = cls._safe_gunzip(
                compressed,
                max_output_bytes=cls.MAX_DECOMPRESSED_REQUEST_BYTES,
            )
        except (ValueError, zlib.error):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid gzip CBT AI request body"},
            )
        except OverflowError:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Decompressed CBT AI request body is too large"},
            )

        request._body = decompressed
        request.scope["headers"] = [
            (name, value)
            for name, value in request.scope.get("headers", [])
            if name.lower() not in {b"content-encoding", b"content-length"}
        ]
        if hasattr(request, "_headers"):
            delattr(request, "_headers")
        return None

    @classmethod
    async def _read_limited_body(cls, request: Request, *, max_bytes: int) -> bytes:
        content_length = cls._header(request.scope, b"content-length")
        if content_length:
            try:
                declared = int(content_length)
            except ValueError:
                declared = 0
            if declared > max_bytes:
                raise OverflowError

        existing = getattr(request, "_body", None)
        if isinstance(existing, bytes):
            if len(existing) > max_bytes:
                raise OverflowError
            return existing

        body = bytearray()
        async for chunk in request.stream():
            if not chunk:
                continue
            if len(body) + len(chunk) > max_bytes:
                raise OverflowError
            body.extend(chunk)
        return bytes(body)

    @classmethod
    def _safe_gunzip(cls, payload: bytes, *, max_output_bytes: int) -> bytes:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        output = bytearray()
        chunk_size = 64 * 1024

        for offset in range(0, len(payload), chunk_size):
            chunk = payload[offset : offset + chunk_size]
            while chunk:
                remaining = max_output_bytes - len(output)
                if remaining <= 0:
                    raise OverflowError
                piece = decoder.decompress(chunk, remaining + 1)
                output.extend(piece)
                if len(output) > max_output_bytes:
                    raise OverflowError
                chunk = decoder.unconsumed_tail

        remaining = max_output_bytes - len(output)
        if remaining <= 0 and not decoder.eof:
            raise OverflowError
        tail = decoder.flush(max(1, remaining + 1))
        output.extend(tail)
        if len(output) > max_output_bytes:
            raise OverflowError
        if not decoder.eof or decoder.unused_data:
            raise ValueError("Invalid or concatenated gzip stream")
        return bytes(output)

    @classmethod
    def _compress_response_if_accepted(cls, request: Request, response: Response) -> None:
        accept_encoding = cls._header(request.scope, b"accept-encoding")
        if not cls._accepts_gzip(accept_encoding):
            return
        if response.status_code in {204, 304} or "content-encoding" in response.headers:
            return

        body = getattr(response, "body", None)
        if not isinstance(body, bytes) or len(body) < cls.MIN_RESPONSE_BYTES:
            return

        compressed = gzip.compress(body, compresslevel=cls.COMPRESS_LEVEL)
        response.body = compressed
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        existing_vary = response.headers.get("Vary")
        if existing_vary:
            vary_values = {value.strip().casefold() for value in existing_vary.split(",")}
            if "accept-encoding" not in vary_values:
                response.headers["Vary"] = f"{existing_vary}, Accept-Encoding"
        else:
            response.headers["Vary"] = "Accept-Encoding"

    @staticmethod
    def _accepts_gzip(value: bytes | None) -> bool:
        if not value:
            return False
        for item in value.decode("latin-1").casefold().split(","):
            token, *parameters = item.strip().split(";")
            if token != "gzip":
                continue
            quality = 1.0
            for parameter in parameters:
                key, separator, raw_value = parameter.strip().partition("=")
                if separator and key == "q":
                    try:
                        quality = float(raw_value)
                    except ValueError:
                        quality = 0.0
            return quality > 0
        return False

    @staticmethod
    def _header(scope: dict[str, Any], name: bytes) -> bytes | None:
        for header_name, value in scope.get("headers", []):
            if header_name.lower() == name:
                return value
        return None
