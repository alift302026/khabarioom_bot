"""Tests for daily reports (weather/market/wisdom) with mocked HTTP."""

import daily_reports

from conftest import run


class FakeAsyncClient:
    """httpx.AsyncClient stand-in with URL-substring routing."""

    routes: dict = {}  # url substring -> (status_code, json_data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None):
        for marker, (status, data) in self.routes.items():
            if marker in url:
                from conftest import FakeResponse

                return FakeResponse(status_code=status, json_data=data)
        from conftest import FakeResponse

        return FakeResponse(status_code=404)


def install_client(monkeypatch, routes):
    FakeAsyncClient.routes = routes
    monkeypatch.setattr(
        daily_reports.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient()
    )


WEATHER_JSON = {
    "current": {
        "temperature_2m": 18.4,
        "relative_humidity_2m": 35,
        "wind_speed_10m": 12.1,
    },
    "daily": {"temperature_2m_min": [11.0], "temperature_2m_max": [24.5]},
}

ARZHAAM_JSON = {
    "data": {
        "rates": [
            {"assetId": "usd", "price": "1234567"},
            {"assetId": "gold_18", "price": 8900000},
        ]
    }
}

YAHOO_JSON = {
    "chart": {"result": [{"meta": {"regularMarketPrice": 75.5}}]}
}


def test_weather_report_formats_values(monkeypatch):
    install_client(monkeypatch, {"api.open-meteo.com": (200, WEATHER_JSON)})
    text = run(daily_reports.weather_report())
    assert "18.4°C" in text
    assert "11.0°C" in text and "24.5°C" in text
    assert "35%" in text
    assert "12.1 km/h" in text
    assert "آب‌وهوای تهران" in text


def test_weather_report_handles_missing_values(monkeypatch):
    install_client(
        monkeypatch,
        {"api.open-meteo.com": (200, {"current": {}, "daily": {}})},
    )
    text = run(daily_reports.weather_report())
    assert text.count("نامشخص") == 5  # temp, min, max, humidity, wind


def test_market_report_with_api_keys(monkeypatch):
    install_client(
        monkeypatch,
        {
            "arzhaam.ir": (200, ARZHAAM_JSON),
            "finance.yahoo.com": (200, YAHOO_JSON),
        },
    )
    monkeypatch.setenv("ARZHAAM_API_KEY", "test-key")
    text = run(daily_reports.market_report())
    assert "1٬234٬567 تومان" in text  # USD
    assert "8٬900٬000 تومان" in text  # gold
    assert "75.50 دلار" in text  # WTI oil
    assert "در دسترس نیست" in text  # coin/emami absent from payload


def test_market_report_without_arzhaam_key(monkeypatch):
    install_client(monkeypatch, {"finance.yahoo.com": (200, YAHOO_JSON)})
    monkeypatch.delenv("ARZHAAM_API_KEY", raising=False)
    text = run(daily_reports.market_report())
    assert "75.50 دلار" in text
    assert "در دسترس نیست" in text  # local prices unavailable without key


def test_market_report_survives_api_failures(monkeypatch):
    install_client(
        monkeypatch,
        {"arzhaam.ir": (500, {}), "finance.yahoo.com": (500, {})},
    )
    monkeypatch.setenv("ARZHAAM_API_KEY", "test-key")
    text = run(daily_reports.market_report())
    assert "در دسترس نیست" in text  # report degrades gracefully


def test_wisdom_report_is_escaped_and_attributed():
    text = daily_reports.wisdom_report()
    assert text.startswith("🧠 <b>اندیشهٔ روز")
    assert "<i>" in text and "</i>" in text
    assert "نقل‌قول مستقیم" in text or "تحریریه" in text or "برداشت" in text
    assert "@khabarioom" in text
    # all content between tags must be escaped; no stray angle brackets
    assert text.count("<") == text.count(">")
