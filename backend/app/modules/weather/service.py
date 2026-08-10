from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config.settings import settings
from app.modules.dashboard.weather_service import WeatherLocation, build_weather_snapshot
from app.modules.heat_stress.service import calculate_apparent_temperature


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
KST = timezone(timedelta(hours=9))
_LOCATION_CACHE: dict[tuple[float, float], str] = {}


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


def _direct_kma_current(latitude: float, longitude: float, location_name: str) -> dict | None:
    """Use a KMA direct observation when available while retaining the legacy provider as fallback."""
    snapshot = build_weather_snapshot(
        WeatherLocation(name=location_name, latitude=latitude, longitude=longitude)
    )
    if not snapshot.get("available"):
        return None
    if not str(snapshot.get("temperature_source") or "").startswith("kma"):
        return None
    return snapshot


def _reverse_location_name(latitude: float, longitude: float) -> str:
    cache_key = (round(latitude, 3), round(longitude, 3))
    cached = _LOCATION_CACHE.get(cache_key)
    if cached:
        return cached
    url = f"{NOMINATIM_REVERSE_URL}?{urlencode({
        'lat': latitude,
        'lon': longitude,
        'format': 'jsonv2',
        'addressdetails': 1,
        'zoom': 16,
        'accept-language': 'ko',
    })}"
    request = Request(
        url,
        headers={"User-Agent": "BESMA-CSMS/1.0 (https://www.besma.co.kr)"},
    )
    with urlopen(request, timeout=settings.weather_http_timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    address = payload.get("address") or {}
    candidates = [
        address.get("city") or address.get("state"),
        address.get("borough") or address.get("county") or address.get("city_district"),
        address.get("quarter")
        or address.get("neighbourhood")
        or address.get("suburb")
        or address.get("village")
        or address.get("town"),
    ]
    parts: list[str] = []
    for value in candidates:
        if value and value not in parts:
            parts.append(str(value))
    label = " ".join(parts) or payload.get("display_name") or f"현재 위치 ({latitude:.4f}, {longitude:.4f})"
    _LOCATION_CACHE[cache_key] = label
    return label


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
    resolved_location_name = location_name
    location_source = "SITE"
    if not resolved_location_name:
        location_source = "GPS"
        try:
            resolved_location_name = _reverse_location_name(latitude, longitude)
        except Exception:
            resolved_location_name = f"현재 위치 ({latitude:.4f}, {longitude:.4f})"
    direct_kma = _direct_kma_current(latitude, longitude, resolved_location_name)
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
    observed_at = current.get("time")
    wind_speed_kmh = current.get("wind_speed_10m")
    location_attribution = "동네명 © OpenStreetMap contributors"
    source = "OPEN_METEO_LOCATION"
    source_label = "위치 기반 기상자료"
    kma_notice = "기상청 직접 관측값을 사용할 수 없어 위치 기반 기상자료를 사용 중입니다."
    if direct_kma:
        temperature = direct_kma.get("temperature")
        humidity = direct_kma.get("humidity")
        observed_at = direct_kma.get("observed_at") or direct_kma.get("updated_at")
        wind_speed = direct_kma.get("wind_speed")
        wind_speed_kmh = (float(wind_speed) * 3.6) if wind_speed is not None else None
        station_name = direct_kma.get("kma_station_name")
        station_id = direct_kma.get("kma_station_id")
        distance_km = direct_kma.get("kma_station_distance_km")
        if direct_kma.get("temperature_source") == "kma-asos":
            source = "KMA_ASOS_NEAREST"
            source_label = "기상청 최근접 ASOS 직접 관측값"
            location_attribution = (
                f"기상청 {station_name}({station_id}) · 약 {distance_km}km"
                if station_name and distance_km is not None
                else "기상청 직접 관측값"
            )
        else:
            source = "KMA_GRID_FALLBACK"
            source_label = "기상청 격자 관측값"
            location_attribution = "기상청 ASOS 직접 관측 실패 시 격자 fallback"
        kma_notice = "현재값은 기상청 직접 관측을 우선 사용합니다. AWS 직접관측은 승인 후 별도 전환합니다."
    calculated = None
    if temperature is not None and humidity is not None:
        calculated = calculate_apparent_temperature(float(temperature), float(humidity))
    return {
        "available": True,
        "location_name": resolved_location_name,
        "location_source": location_source,
        "location_attribution": location_attribution,
        "latitude": latitude,
        "longitude": longitude,
        "source": source,
        "source_label": source_label,
        "kma_key_configured": bool(settings.kma_api_key),
        "kma_notice": kma_notice,
        "fetched_at": datetime.now(KST).isoformat(),
        "current": {
            "observed_at": observed_at,
            "weather_code": current.get("weather_code"),
            "weather_label": WEATHER_LABELS.get(current.get("weather_code"), "기상 정보"),
            "temperature_c": temperature,
            "relative_humidity_pct": humidity,
            "apparent_temperature_c": calculated,
            "provider_apparent_temperature_c": current.get("apparent_temperature"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": wind_speed_kmh,
        },
        "forecast_days": days,
    }
