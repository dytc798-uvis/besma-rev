from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from threading import Lock
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config.settings import settings
from app.core.datetime_utils import utc_now


WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"

_CACHE_LOCK = Lock()
_CACHE: dict[str, tuple[object, object]] = {}


@dataclass(slots=True)
class WeatherLocation:
    name: str
    latitude: float
    longitude: float
    address: str | None = None
    site_id: int | None = None
    site_code: str | None = None


def _cache_get(key: str):
    now = utc_now()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at <= now:
            _CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: str, value, ttl_minutes: int | None = None):
    ttl = ttl_minutes if ttl_minutes is not None else settings.weather_cache_ttl_minutes
    expires_at = utc_now() + timedelta(minutes=ttl)
    with _CACHE_LOCK:
        _CACHE[key] = (expires_at, value)
    return value


def _fetch_json(base_url: str, params: dict[str, object]):
    query = urlencode(params)
    url = f"{base_url}?{query}"
    with urlopen(url, timeout=settings.weather_http_timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _round_coord(value: float) -> float:
    return round(float(value), 4)


def _weather_label(code: int | None) -> str:
    mapping = {
        0: "맑음",
        1: "대체로 맑음",
        2: "구름 조금",
        3: "흐림",
        45: "안개",
        48: "짙은 안개",
        51: "이슬비",
        53: "약한 비",
        55: "비",
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
    return mapping.get(int(code or 0), "기상 정보")


def _pm_status(value: float | None, pollutant: str) -> str:
    if value is None:
        return "정보없음"
    if pollutant == "pm10":
        if value <= 30:
            return "좋음"
        if value <= 80:
            return "보통"
        if value <= 150:
            return "나쁨"
        return "매우나쁨"
    if value <= 15:
        return "좋음"
    if value <= 35:
        return "보통"
    if value <= 75:
        return "나쁨"
    return "매우나쁨"


def _severity_rank(status: str) -> int:
    if status == "매우나쁨":
        return 3
    if status == "나쁨":
        return 2
    if status == "보통":
        return 1
    return 0


def _is_precipitation_risk(weather_code: int | None, precipitation: float | None, probability: float | None) -> bool:
    rainy_codes = {51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99}
    return (
        (weather_code in rainy_codes)
        or ((precipitation or 0) > 0)
        or ((probability or 0) >= 50)
    )


def _build_advisory(weather_label: str, temperature: float | None, feels_like: float | None, wind_speed: float | None, precipitation: float | None, precipitation_probability: float | None, pm10: float | None, pm25: float | None, weather_code: int | None):
    flags: list[str] = []
    messages: list[str] = []
    risk_assessment_required = False

    pm10_status = _pm_status(pm10, "pm10")
    pm25_status = _pm_status(pm25, "pm25")

    if _severity_rank(pm10_status) >= 2 or _severity_rank(pm25_status) >= 2:
        flags.append("DUST")
        messages.extend(
            [
                "미세먼지 주의",
                "KF94 마스크 착용",
                "장시간 외부 작업 노출 최소화",
            ]
        )
        risk_assessment_required = True

    if _is_precipitation_risk(weather_code, precipitation, precipitation_probability):
        flags.append("RAIN")
        messages.extend(
            [
                "우천 작업 주의",
                "미끄럼 위험 증가",
                "전기작업 사전 점검",
            ]
        )
        risk_assessment_required = True

    if (wind_speed or 0) >= 8:
        flags.append("WIND")
        messages.extend(
            [
                "강풍 주의",
                "고소작업 중지 여부 검토",
                "자재 비산 방지 조치",
            ]
        )
        risk_assessment_required = True

    heat_reference = max(
        temperature if temperature is not None else -999,
        feels_like if feels_like is not None else -999,
    )
    cold_reference = min(
        temperature if temperature is not None else 999,
        feels_like if feels_like is not None else 999,
    )

    if heat_reference >= 33:
        flags.append("HEAT")
        messages.extend(
            [
                "폭염 주의",
                "휴식시간 확보",
                "수분 섭취 관리",
                "열사병 예방 조치",
            ]
        )

    if cold_reference <= -5:
        flags.append("COLD")
        messages.extend(
            [
                "한파 주의",
                "결빙 구간 점검",
                "방한장비 착용",
            ]
        )

    deduped_messages: list[str] = []
    for message in messages:
        if message not in deduped_messages:
            deduped_messages.append(message)

    if risk_assessment_required and "위험성평가 반영 필요" not in deduped_messages:
        deduped_messages.append("위험성평가 반영 필요")

    warning_score = max(
        _severity_rank(pm10_status),
        _severity_rank(pm25_status),
        2 if "WIND" in flags else 0,
        2 if "RAIN" in flags else 0,
        1 if "HEAT" in flags else 0,
        1 if "COLD" in flags else 0,
    )

    return {
        "weather_label": weather_label,
        "pm10_status": pm10_status,
        "pm25_status": pm25_status,
        "advisory_flags": flags,
        "safety_messages": deduped_messages,
        "risk_assessment_required": risk_assessment_required,
        "warning_score": warning_score,
    }


def _build_unavailable_payload(name: str, *, address: str | None = None, site_id: int | None = None, site_code: str | None = None, reason: str = "일시적 조회 실패"):
    return {
        "available": False,
        "location_name": name,
        "address": address,
        "site_id": site_id,
        "site_code": site_code,
        "weather_label": "정보 없음",
        "temperature": None,
        "feels_like": None,
        "wind_speed": None,
        "precipitation": None,
        "precipitation_probability": None,
        "pm10": None,
        "pm10_status": "정보없음",
        "pm25": None,
        "pm25_status": "정보없음",
        "advisory_flags": [],
        "safety_messages": [],
        "risk_assessment_required": False,
        "warning_score": -1,
        "updated_at": utc_now(),
        "status_text": reason,
    }


def _geocode_address(name: str, address: str | None):
    query = (address or name or "").strip()
    if not query:
        return None
    cache_key = f"weather:geocode:{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        payload = _fetch_json(
            GEOCODING_API_URL,
            {
                "name": query,
                "count": 1,
                "language": "ko",
                "format": "json",
            },
        )
        results = payload.get("results") or []
        if not results:
            return _cache_set(cache_key, None, ttl_minutes=120)
        top = results[0]
        resolved = (_round_coord(top["latitude"]), _round_coord(top["longitude"]))
        return _cache_set(cache_key, resolved, ttl_minutes=120)
    except Exception:
        return None


def resolve_site_location(site) -> WeatherLocation | None:
    lat = getattr(site, "latitude", None)
    lon = getattr(site, "longitude", None)
    if lat is not None and lon is not None:
        return WeatherLocation(
            name=getattr(site, "site_name", "현장"),
            latitude=_round_coord(lat),
            longitude=_round_coord(lon),
            address=getattr(site, "address", None),
            site_id=getattr(site, "id", None),
            site_code=getattr(site, "site_code", None),
        )
    resolved = _geocode_address(getattr(site, "site_name", "현장"), getattr(site, "address", None))
    if resolved is None:
        return None
    return WeatherLocation(
        name=getattr(site, "site_name", "현장"),
        latitude=resolved[0],
        longitude=resolved[1],
        address=getattr(site, "address", None),
        site_id=getattr(site, "id", None),
        site_code=getattr(site, "site_code", None),
    )


def build_hq_location() -> WeatherLocation | None:
    if settings.weather_hq_lat is None or settings.weather_hq_lon is None:
        return None
    return WeatherLocation(
        name=settings.weather_hq_name or "본사",
        latitude=_round_coord(settings.weather_hq_lat),
        longitude=_round_coord(settings.weather_hq_lon),
    )


def build_weather_snapshot(location: WeatherLocation):
    cache_key = f"weather:snapshot:{location.latitude}:{location.longitude}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        weather_payload = _fetch_json(
            WEATHER_API_URL,
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timezone": "Asia/Seoul",
                "current": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code",
                "hourly": "precipitation_probability",
                "forecast_hours": 1,
            },
        )
        air_payload = _fetch_json(
            AIR_QUALITY_API_URL,
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timezone": "Asia/Seoul",
                "current": "pm10,pm2_5",
            },
        )
        current_weather = weather_payload.get("current") or {}
        current_air = air_payload.get("current") or {}
        hourly = weather_payload.get("hourly") or {}
        precipitation_probability = None
        hourly_prob = hourly.get("precipitation_probability")
        if isinstance(hourly_prob, list) and hourly_prob:
            precipitation_probability = hourly_prob[0]
        weather_code = current_weather.get("weather_code")
        advisory = _build_advisory(
            weather_label=_weather_label(weather_code),
            temperature=current_weather.get("temperature_2m"),
            feels_like=current_weather.get("apparent_temperature"),
            wind_speed=current_weather.get("wind_speed_10m"),
            precipitation=current_weather.get("precipitation"),
            precipitation_probability=precipitation_probability,
            pm10=current_air.get("pm10"),
            pm25=current_air.get("pm2_5"),
            weather_code=weather_code,
        )
        payload = {
            "available": True,
            "location_name": location.name,
            "address": location.address,
            "site_id": location.site_id,
            "site_code": location.site_code,
            "weather_label": advisory["weather_label"],
            "temperature": current_weather.get("temperature_2m"),
            "feels_like": current_weather.get("apparent_temperature"),
            "wind_speed": current_weather.get("wind_speed_10m"),
            "precipitation": current_weather.get("precipitation"),
            "precipitation_probability": precipitation_probability,
            "pm10": current_air.get("pm10"),
            "pm10_status": advisory["pm10_status"],
            "pm25": current_air.get("pm2_5"),
            "pm25_status": advisory["pm25_status"],
            "advisory_flags": advisory["advisory_flags"],
            "safety_messages": advisory["safety_messages"],
            "risk_assessment_required": advisory["risk_assessment_required"],
            "warning_score": advisory["warning_score"],
            "updated_at": utc_now(),
            "status_text": "정상",
        }
        return _cache_set(cache_key, payload)
    except Exception:
        unavailable = _build_unavailable_payload(
            location.name,
            address=location.address,
            site_id=location.site_id,
            site_code=location.site_code,
        )
        return _cache_set(cache_key, unavailable, ttl_minutes=5)


def build_site_weather_summary(site):
    location = resolve_site_location(site)
    if location is None:
        return _build_unavailable_payload(
            getattr(site, "site_name", "현장"),
            address=getattr(site, "address", None),
            site_id=getattr(site, "id", None),
            site_code=getattr(site, "site_code", None),
            reason="위치 정보 없음",
        )
    return build_weather_snapshot(location)


def weather_summary_text(payload: dict) -> str:
    if not payload.get("available"):
        return payload.get("status_text") or "정보 없음"
    primary = f"{payload.get('weather_label', '기상 정보')} {int(round(payload.get('temperature') or 0))}℃"
    if payload.get("warning_score", 0) >= 2:
        if payload.get("pm25_status") in {"나쁨", "매우나쁨"}:
            return f"{primary} · 초미세먼지 {payload['pm25_status']}"
        if payload.get("pm10_status") in {"나쁨", "매우나쁨"}:
            return f"{primary} · 미세먼지 {payload['pm10_status']}"
        if "WIND" in payload.get("advisory_flags", []):
            return f"{primary} · 강풍 주의"
        if "RAIN" in payload.get("advisory_flags", []):
            return f"{primary} · 우천 주의"
    return primary
