from types import SimpleNamespace

import pytest

from app.config.settings import EnvironmentType
from app.modules.cbt.releases.schemas import CBTReleaseResponse
from app.modules.cbt.releases.service import (
    CBTReleaseService,
    CBTReleaseUnavailableError,
)
import app.modules.cbt.releases.service as release_service_module


def _release(*, channel: str = "production", tag: str = "manager-production-latest") -> CBTReleaseResponse:
    asset = (
        "WeaveCBT-Setup-Windows-x64.exe"
        if channel == "production"
        else "WeaveCBT-Setup-Staging-x64.exe"
    )
    return CBTReleaseResponse(
        channel=channel,
        manager_version="0.1.0",
        cbt_version="0.1.0",
        minimum_supported_version="0.1.0",
        image="ghcr.io/aphrodite1818/weave-cbt-module:sha-7604735",
        installer_asset=asset,
        installer_url=(
            "https://github.com/Aphrodite1818/WEAVE-CBT-MODULE/"
            f"releases/download/{tag}/{asset}"
        ),
        installer_sha256="a" * 64,
        release_notes="Test release",
        source_commit="b" * 40,
    )


def test_release_channel_matches_weave_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        release_service_module,
        "settings",
        SimpleNamespace(ENV=EnvironmentType.PRODUCTION),
    )
    assert CBTReleaseService.channel_for_environment() == "production"

    monkeypatch.setattr(
        release_service_module,
        "settings",
        SimpleNamespace(ENV=EnvironmentType.STAGING),
    )
    assert CBTReleaseService.channel_for_environment() == "staging"

    monkeypatch.setattr(
        release_service_module,
        "settings",
        SimpleNamespace(ENV=EnvironmentType.DEVELOPMENT),
    )
    assert CBTReleaseService.channel_for_environment() == "staging"


def test_valid_production_release_is_accepted() -> None:
    CBTReleaseService._validate_release(
        channel="production",
        tag="manager-production-latest",
        release=_release(),
    )


def test_wrong_release_channel_is_rejected() -> None:
    with pytest.raises(CBTReleaseUnavailableError, match="does not match"):
        CBTReleaseService._validate_release(
            channel="production",
            tag="manager-production-latest",
            release=_release(
                channel="staging",
                tag="manager-staging-latest",
            ),
        )


def test_wrong_release_tag_is_rejected() -> None:
    with pytest.raises(CBTReleaseUnavailableError, match="URL failed"):
        CBTReleaseService._validate_release(
            channel="production",
            tag="manager-production-latest",
            release=_release(tag="manager-staging-latest"),
        )


def test_unexpected_image_repository_is_rejected() -> None:
    release = _release().model_copy(
        update={"image": "ghcr.io/example/untrusted:latest"},
    )
    with pytest.raises(CBTReleaseUnavailableError, match="unexpected container image"):
        CBTReleaseService._validate_release(
            channel="production",
            tag="manager-production-latest",
            release=release,
        )
