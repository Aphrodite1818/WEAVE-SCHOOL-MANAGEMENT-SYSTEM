# =================================#
#     core.cache.serialization    #
# =================================#
"""Helpers for converting cache payloads to and from Redis-safe JSON values.

Redis stores strings, bytes, and a small set of scalar values. The application
also caches richer Python objects such as UUIDs, datetimes, Decimals, enums,
and Pydantic models. This module converts those objects into JSON-compatible
structures before storage and decodes them again when reading from Redis.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def convert_to_jsonable(value: Any) -> Any:
    """
    Convert a Python value into a structure that `json.dumps` can serialize.

    Supported conversions:
    - `BaseModel` instances become dictionaries via `model_dump(mode="json")`
    - dictionaries are processed recursively and have their keys stringified
    - lists, tuples, and sets become lists
    - `datetime` and `date` values become ISO-8601 strings
    - `Decimal` values become floats
    - `Enum` values become their underlying `.value`
    - `UUID` values become strings

    Values that are already JSON-safe are returned unchanged.
    """

    if value is None:
        return None

    if isinstance(value, BaseModel):
        return convert_to_jsonable(value.model_dump(mode="json"))

    if isinstance(value, dict):
        return {str(key): convert_to_jsonable(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [convert_to_jsonable(item) for item in value]

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, UUID):
        return str(value)

    return value


def dumps(value: Any) -> str:
    """
    Serialize a Python value into a compact JSON string for Redis storage.

    The value is normalized first so nested objects that are not JSON-native
    are converted before encoding.
    """

    return json.dumps(
        convert_to_jsonable(value),
        separators=(",", ":"),
        ensure_ascii=False,
    )


def loads(value: str | bytes | None) -> Any | None:
    """
    Decode a Redis JSON payload into normal Python containers.

    Redis clients may return either `str` or `bytes`. `None` is preserved so
    callers can distinguish a missing cache entry from an empty JSON value.
    """

    if value is None:
        return None

    if isinstance(value, bytes):
        value = value.decode("utf-8")

    return json.loads(value)
