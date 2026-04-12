from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.modules.dashboard.weather_service import _build_advisory, kst_weather_snapshot_anchor, resolve_site_location, weather_summary_text


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


def test_kst_anchor_before_5am_uses_previous_noon():
    kst = timezone(timedelta(hours=9), name="KST")
    # 2026-04-12 04:59 KST == 2026-04-11 19:59 UTC
    t = datetime(2026, 4, 11, 19, 59, 0, tzinfo=timezone.utc)
    anchor = kst_weather_snapshot_anchor(t)
    assert anchor == datetime(2026, 4, 11, 12, 0, 0, tzinfo=kst)


def test_kst_anchor_morning_window_uses_today_5am():
    kst = timezone(timedelta(hours=9), name="KST")
    # 2026-04-12 06:00 KST == 2026-04-11 21:00 UTC
    t = datetime(2026, 4, 11, 21, 0, 0, tzinfo=timezone.utc)
    anchor = kst_weather_snapshot_anchor(t)
    assert anchor == datetime(2026, 4, 12, 5, 0, 0, tzinfo=kst)


def test_kst_anchor_afternoon_uses_today_noon():
    kst = timezone(timedelta(hours=9), name="KST")
    # 2026-04-12 15:00 KST == 2026-04-12 06:00 UTC
    t = datetime(2026, 4, 12, 6, 0, 0, tzinfo=timezone.utc)
    anchor = kst_weather_snapshot_anchor(t)
    assert anchor == datetime(2026, 4, 12, 12, 0, 0, tzinfo=kst)
