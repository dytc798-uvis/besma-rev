from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config.settings import settings
from app.modules.heat_stress.service import calculate_apparent_temperature


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
KST = timezone(timedelta(hours=9))


WEATHER_LABELS = {
    0: "맑음",
    1: "대체로 맑음",
    2: "구름 조금",
    3: "흐림",
    45: "안개",
    48: "짙은 안개",
    51: "약한 이슬비",
    53: "이슬비",
    55: "강한 이슬비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    80: "소나기",
    81: "강한 소나기",
    82: "매우 강한 소나기",
    95: "뇌우",
    96: "우박 동반 뇌우",
    99: "강한 우박 동반 뇌우",
}


def _fetch_json(params: dict[str, object]) -> dict:
    url = f"{OPEN_METEO_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "BESMA-weather/1.0"})
    with urlopen(request, timeout=settings.weather_http_timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _risk_flags(
    *,
    apparent_temperature: float | None,
    minimum_temperature: float | None,
    precipitation_probability: float | None,
    precipitation_sum: float | None,
    wind_speed: float | None,
) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if apparent_temperature is not None and apparent_temperature >= 33:
        flags.append({"code": "HEAT", "label": "폭염", "message": "휴식·음료·그늘과 작업시간 조정 계획을 확인하세요."})
    if minimum_temperature is not None and minimum_temperature <= -5:
        flags.append({"code": "COLD", "label": "한파", "message": "보온·결빙·미끄럼 및 장비 시동 계획을 확인하세요."})
    if (precipitation_probability or 0) >= 70 or (precipitation_sum or 0) >= 20:
        flags.append({"code": "RAIN", "label": "호우 가능", "message": "굴착·전기·고소작업과 배수·방수 계획을 확인하세요."})
    if (wind_speed or 0) >= 10:
        flags.append({"code": "WIND", "label": "강풍", "message": "양중·비계·고소작업 중지기준을 확인하세요."})
    return flags


def build_location_overview(latitude: float, longitude: float, location_name: str | None = None) -> dict:
    payload = _fetch_json(
        {
            "latitude": round(latitude, 5),
            "longitude": round(longitude, 5),
            "timezone": "Asia/Seoul",
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,weather_code,wind_speed_10m"
            ),
            "hourly": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation_probability,precipitation,weather_code,wind_speed_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "apparent_temperature_max,apparent_temperature_min,"
                "precipitation_probability_max,precipitation_sum,wind_speed_10m_max"
            ),
            "forecast_days": 5,
        }
    )
    current = payload.get("current") or {}
    daily = payload.get("daily") or {}
    days: list[dict] = []
    dates = daily.get("time") or []
    for index, day in enumerate(dates):
        def value(key: str):
            values = daily.get(key) or []
            return values[index] if index < len(values) else None

        weather_code = value("weather_code")
        max_apparent = value("apparent_temperature_max")
        min_temperature = value("temperature_2m_min")
        precipitation_probability = value("precipitation_probability_max")
        precipitation_sum = value("precipitation_sum")
        wind_speed = value("wind_speed_10m_max")
        days.append(
            {
                "date": day,
                "weather_code": weather_code,
                "weather_label": WEATHER_LABELS.get(weather_code, "기상 정보"),
                "temperature_max_c": value("temperature_2m_max"),
                "temperature_min_c": min_temperature,
                "apparent_temperature_max_c": max_apparent,
                "apparent_temperature_min_c": value("apparent_temperature_min"),
                "precipitation_probability_max_pct": precipitation_probability,
                "precipitation_sum_mm": precipitation_sum,
                "wind_speed_max_kmh": wind_speed,
                "risk_flags": _risk_flags(
                    apparent_temperature=max_apparent,
                    minimum_temperature=min_temperature,
                    precipitation_probability=precipitation_probability,
                    precipitation_sum=precipitation_sum,
                    wind_speed=(wind_speed / 3.6) if wind_speed is not None else None,
                ),
            }
        )

    temperature = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    calculated = None
    if temperature is not None and humidity is not None:
        calculated = calculate_apparent_temperature(float(temperature), float(humidity))
    return {
        "available": True,
        "location_name": location_name or "현재 위치",
        "latitude": latitude,
        "longitude": longitude,
        "source": "OPEN_METEO_LOCATION",
        "source_label": "위치 기반 기상자료",
        "kma_key_configured": bool(settings.kma_api_key),
        "kma_notice": (
            "기상청 AWS 연결 가능. 위치-관측지점 연결 및 단기예보 세부 API 승인 후 기상청 값으로 전환합니다."
            if settings.kma_api_key
            else "기상청 운영키가 아직 서버에 설정되지 않았습니다."
        ),
        "fetched_at": datetime.now(KST).isoformat(),
        "current": {
            "observed_at": current.get("time"),
            "weather_code": current.get("weather_code"),
            "weather_label": WEATHER_LABELS.get(current.get("weather_code"), "기상 정보"),
            "temperature_c": temperature,
            "relative_humidity_pct": humidity,
            "apparent_temperature_c": calculated,
            "provider_apparent_temperature_c": current.get("apparent_temperature"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
        },
        "forecast_days": days,
    }
