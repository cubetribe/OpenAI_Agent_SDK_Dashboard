from pytest import MonkeyPatch

from dashboard_service.settings import Settings


def test_cors_origins_accept_comma_separated_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_CORS_ORIGINS", "http://localhost:8090,https://example.test")

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:8090", "https://example.test"]


def test_cors_origins_accept_json_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_CORS_ORIGINS", '["http://localhost:8090"]')

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:8090"]
