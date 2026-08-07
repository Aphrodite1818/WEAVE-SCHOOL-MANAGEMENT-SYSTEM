# ==========================#
#        UTILS.PY          #
# ==========================#


from typing import Any


def require_api_key(api_key: str | None, provider_name: str) -> str:
    """Return the provider API key or raise if it is missing."""
    if not api_key:
        raise ValueError(f"{provider_name} API key is not configured")
    return api_key


def text_from_content(content: Any) -> str:
    """Normalize provider content payloads into plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "\n".join(text_parts)

    if content is None:
        return ""

    return str(content)


def model_to_dict(value: Any) -> Any:
    """Convert SDK model objects into plain Python dictionaries."""
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)

    if hasattr(value, "to_dict"):
        return value.to_dict()

    if isinstance(value, list):
        return [model_to_dict(item) for item in value]

    if isinstance(value, dict):
        return {key: model_to_dict(item) for key, item in value.items()}

    return value


def openai_tool_to_anthropic(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI tool schema into Anthropic's tool format."""
    if tool.get("type") != "function":
        return tool

    function = tool.get("function", {})
    return {
        "name": function.get("name"),
        "description": function.get("description", ""),
        "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
    }


def openai_tool_to_gemini_declaration(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI tool schema into Gemini's declaration format."""
    if tool.get("type") != "function":
        return tool

    function = tool.get("function", {})
    return {
        "name": function.get("name"),
        "description": function.get("description", ""),
        "parameters_json_schema": function.get(
            "parameters",
            {"type": "object", "properties": {}},
        ),
    }
