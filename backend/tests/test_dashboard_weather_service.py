from types import SimpleNamespace

from app.modules.dashboard.weather_service import _build_advisory, resolve_site_location, weather_summary_text


def test_build_advisory_for_dust_and_rain():
    advisory = _build_advisory(
        weather_label="비",
        temperature=17,
        feels_like=15,
        wind_speed=4,
        precipitation=2.5,
        precipitation_probability=80,
        pm10=95,
        pm25=82,
        weather_code=63,
    )

    assert "DUST" in advisory["advisory_flags"]
    assert "RAIN" in advisory["advisory_flags"]
    assert "KF94 마스크 착용" in advisory["safety_messages"]
    assert "위험성평가 반영 필요" in advisory["safety_messages"]
    assert advisory["risk_assessment_required"] is True
    assert advisory["warning_score"] >= 2


def test_resolve_site_location_prefers_coordinates():
    site = SimpleNamespace(
        id=1,
        site_code="SITE001",
        site_name="좌표 테스트 현장",
        address="서울시 테스트구",
        latitude=37.5665,
        longitude=126.9780,
    )

    resolved = resolve_site_location(site)
    assert resolved is not None
    assert resolved.latitude == 37.5665
    assert resolved.longitude == 126.978
    assert resolved.address == "서울시 테스트구"


def test_weather_summary_text_prefers_warning_state():
    summary = weather_summary_text(
        {
            "available": True,
            "weather_label": "맑음",
            "temperature": 18.4,
            "pm10_status": "보통",
            "pm25_status": "매우나쁨",
            "advisory_flags": ["DUST"],
            "warning_score": 3,
        }
    )

    assert "초미세먼지 매우나쁨" in summary
