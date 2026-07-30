from app.modules.weather import service


def test_location_overview_combines_current_weather_and_forecast(monkeypatch):
    monkeypatch.setattr(service, "_reverse_location_name", lambda _lat, _lon: "서울특별시 중구 명동")
    monkeypatch.setattr(
        service,
        "_fetch_json",
        lambda _params: {
            "current": {
                "time": "2026-07-30T13:00",
                "temperature_2m": 34.0,
                "relative_humidity_2m": 70,
                "apparent_temperature": 38.0,
                "precipitation": 0.0,
                "weather_code": 1,
                "wind_speed_10m": 6.0,
            },
            "daily": {
                "time": ["2026-07-30", "2026-07-31"],
                "weather_code": [1, 63],
                "temperature_2m_max": [35.0, 29.0],
                "temperature_2m_min": [27.0, 23.0],
                "apparent_temperature_max": [38.0, 31.0],
                "apparent_temperature_min": [29.0, 25.0],
                "precipitation_probability_max": [10, 80],
                "precipitation_sum": [0.0, 24.0],
                "wind_speed_10m_max": [18.0, 20.0],
            },
        },
    )

    result = service.build_location_overview(37.5, 127.0, "테스트 현장")

    assert result["available"] is True
    assert result["location_name"] == "테스트 현장"
    assert result["current"]["weather_label"] == "대체로 맑음"
    assert result["current"]["apparent_temperature_c"] is not None
    assert len(result["forecast_days"]) == 2
    assert "HEAT" in {item["code"] for item in result["forecast_days"][0]["risk_flags"]}
    assert "RAIN" in {item["code"] for item in result["forecast_days"][1]["risk_flags"]}


def test_location_overview_resolves_neighbourhood_for_gps(monkeypatch):
    monkeypatch.setattr(service, "_reverse_location_name", lambda _lat, _lon: "부산광역시 해운대구 우동")
    monkeypatch.setattr(service, "_fetch_json", lambda _params: {"current": {}, "daily": {"time": []}})

    result = service.build_location_overview(35.1631, 129.1635)

    assert result["location_name"] == "부산광역시 해운대구 우동"
    assert result["location_source"] == "GPS"
    assert "OpenStreetMap" in result["location_attribution"]


def test_location_overview_sends_location_and_five_day_request(monkeypatch):
    captured = {}

    def fake_fetch(params):
        captured.update(params)
        return {"current": {}, "daily": {"time": []}}

    monkeypatch.setattr(service, "_fetch_json", fake_fetch)
    service.build_location_overview(37.123456, 127.654321)

    assert captured["latitude"] == 37.12346
    assert captured["longitude"] == 127.65432
    assert captured["forecast_days"] == 5
    assert captured["timezone"] == "Asia/Seoul"
