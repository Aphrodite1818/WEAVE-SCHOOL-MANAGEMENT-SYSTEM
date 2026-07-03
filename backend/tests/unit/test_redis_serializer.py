from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

import pytest

from app.core.cache.serialization import convert_to_jsonable, dumps, loads


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


# ---------------------------------------------------------------------------
# Edge cases: empty / falsy values
# ---------------------------------------------------------------------------


def test_none_input():
    assert convert_to_jsonable(None) is None


def test_empty_dict():
    assert convert_to_jsonable({}) == {}


def test_empty_list():
    assert convert_to_jsonable([]) == []


def test_empty_tuple():
    assert convert_to_jsonable(()) == []


def test_empty_set():
    assert convert_to_jsonable(set()) == []


def test_empty_string():
    assert convert_to_jsonable("") == ""


def test_zero_values_not_treated_as_falsy_none():
    # 0, 0.0, False are falsy but should NOT be converted to None
    assert convert_to_jsonable(0) == 0
    assert convert_to_jsonable(0.0) == 0.0
    assert convert_to_jsonable(False) is False


# ---------------------------------------------------------------------------
# Edge cases: primitives pass through untouched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [1, 1.5, "text", True, False])
def test_primitives_pass_through_unchanged(value):
    result = convert_to_jsonable(value)
    assert result == value
    assert type(result) is type(value)


# ---------------------------------------------------------------------------
# Edge cases: dict keys that aren't strings
# ---------------------------------------------------------------------------


def test_non_string_dict_keys_are_stringified():
    data = {1: "one", 2: "two", uuid4(): "uuid-keyed"}
    result = convert_to_jsonable(data)
    assert all(isinstance(k, str) for k in result.keys())
    assert result["1"] == "one"
    assert result["2"] == "two"


def test_uuid_dict_key_matches_str_conversion():
    my_uuid = uuid4()
    data = {my_uuid: "value"}
    result = convert_to_jsonable(data)
    assert result[str(my_uuid)] == "value"


# ---------------------------------------------------------------------------
# Edge cases: deep / mixed nesting
# ---------------------------------------------------------------------------


def test_deeply_nested_structure():
    data = {
        "level1": {
            "level2": {
                "level3": [
                    {"id": uuid4(), "amount": Decimal("5.00")},
                    {"id": uuid4(), "amount": Decimal("10.00")},
                ]
            }
        }
    }
    result = convert_to_jsonable(data)
    level3 = result["level1"]["level2"]["level3"]
    assert isinstance(level3, list)
    for item in level3:
        assert isinstance(item["id"], str)
        assert isinstance(item["amount"], float)


def test_list_of_mixed_types():
    data = [1, "two", Decimal("3.0"), uuid4(), None, Status.ACTIVE, {"nested": True}]
    result = convert_to_jsonable(data)
    assert result[0] == 1
    assert result[1] == "two"
    assert result[2] == 3.0
    assert isinstance(result[3], str)
    assert result[4] is None
    assert result[5] == "active"
    assert result[6] == {"nested": True}


def test_list_containing_empty_collections():
    data = {"a": [], "b": {}, "c": (), "d": set()}
    result = convert_to_jsonable(data)
    assert result == {"a": [], "b": {}, "c": [], "d": []}


# ---------------------------------------------------------------------------
# Edge cases: dumps / loads round trip
# ---------------------------------------------------------------------------


def test_dumps_produces_valid_json_string():
    data = {"id": uuid4(), "amount": Decimal("9.99"), "when": datetime(2026, 1, 1)}
    result = dumps(data)
    assert isinstance(result, str)


def test_loads_none_returns_none():
    assert loads(None) is None


def test_loads_handles_bytes_input():
    data = {"key": "value", "num": 42}
    raw_bytes = dumps(data).encode("utf-8")
    result = loads(raw_bytes)
    assert result == {"key": "value", "num": 42}


def test_dumps_loads_round_trip_preserves_values_as_json_types():
    my_uuid = uuid4()
    data = {
        "id": my_uuid,
        "amount": Decimal("42.50"),
        "when": datetime(2026, 7, 3, 10, 0, 0),
        "status": Status.ACTIVE,
        "tags": ("a", "b"),
    }
    result = loads(dumps(data))

    # values match, but types have changed (UUID/Decimal/datetime/tuple -> str/float/str/list)
    assert result["id"] == str(my_uuid)
    assert result["amount"] == 42.5
    assert result["when"] == data["when"].isoformat()
    assert result["status"] == "active"
    assert result["tags"] == ["a", "b"]


def test_dumps_empty_dict_round_trip():
    assert loads(dumps({})) == {}


def test_dumps_is_compact_no_extra_whitespace():
    data = {"a": 1, "b": 2}
    result = dumps(data)
    assert " " not in result  # separators=(",", ":") should strip spaces


def test_dumps_preserves_non_ascii_characters():
    data = {"name": "Café Münchën 日本語"}
    result = dumps(data)
    assert "Café" in result  # ensure_ascii=False keeps characters literal
    assert loads(result) == data
