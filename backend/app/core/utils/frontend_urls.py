from urllib.parse import urlsplit, urlunsplit

from fastapi import Request

from app.config.settings import settings


def normalize_url(url: str) -> str:
    """Normalize a URL string."""
    return url.strip().rstrip("/")


def extract_base_url(url: str) -> str | None:
    """Extract the base URL from a URL string."""
    parsed = urlsplit(url.strip())

    if not parsed.scheme or not parsed.netloc:
        return None

    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def get_allowed_frontend_origins() -> set[str]:
    """Return the allowed frontend origins."""
    allowed_origins = getattr(settings, "ALLOWED_ORIGINS", [])

    return {
        normalize_url(origin) for origin in allowed_origins if origin and origin != "*"
    }


def resolve_frontend_app_url(request: Request | None = None) -> str:
    """Resolve the frontend application URL."""
    fallback_url = normalize_url(settings.FRONTEND_APP_URL)
    allowed_origins = get_allowed_frontend_origins()

    if request is None:
        return fallback_url

    origin = request.headers.get("origin", "").strip()

    if origin and origin.lower() != "null":
        normalized_origin = normalize_url(origin)

        if normalized_origin in allowed_origins:
            return normalized_origin

    referer = request.headers.get("referer", "").strip()

    if referer:
        referer_base_url = extract_base_url(referer)

        if referer_base_url and referer_base_url in allowed_origins:
            return referer_base_url

    return fallback_url
