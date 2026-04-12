from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from app.config.settings import settings
from app.core.datetime_utils import utc_now


WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"

# 한국은 일광절약시간이 없어 Asia/Seoul == UTC+9 고정으로 처리한다(tzdata 미설치 Windows 호환).
_KST = timezone(timedelta(hours=9), name="KST")
_UTC = timezone.utc


def kst_weather_snapshot_anchor(now_utc: datetime | None = None) -> datetime:
    """
    대시보드에 표시할 '마지막 스냅샷'의 KST 기준 시각(앵커).

    - 당일 00:00~04:59 KST: 전일 12:00 KST 앵커
    - 당일 05:00~11:59 KST: 당일 05:00 KST 앵커
    - 당일 12:00~23:59 KST: 당일 12:00 KST 앵커
    """
    now = now_utc or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_UTC)
    now_kst = now.astimezone(_KST)
    d = now_kst.date()
    t = now_kst.time()
    if t < time(5, 0):
        prev = d - timedelta(days=1)
        return datetime.combine(prev, time(12, 0), tzinfo=_KST)
    if t < time(12, 0):
        return datetime.combine(d, time(5, 0), tzinfo=_KST)
    return datetime.combine(d, time(12, 0), tzinfo=_KST)


def max_snapshot_fetched_at_iso(*payloads: dict) -> str | None:
    """여러 날씨 payload 중 snapshot_fetched_at(또는 updated_at)의 최댓값(UTC 기준)."""
    best: datetime | None = None
    for p in payloads:
        if not p:
            continue
        raw = p.get("snapshot_fetched_at") or p.get("updated_at")
        if raw is None:
            continue
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo else raw.replace(tzinfo=_UTC)
        else:
            try:
                s = str(raw).replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
            except ValueError:
                continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_UTC)
        dt = dt.astimezone(_UTC)
        if best is None or dt > best:
            best = dt
    return best.isoformat() if best else None


@dataclass(slots=True)
class WeatherLocation:
    name: str
    latitude: float
    longitude: float
    address: str | None = None
    site_id: int | None = None
    site_code: str | None = None


def _snapshots_root() -> Path:
    d = settings.storage_root / "weather_snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _geocode_dir() -> Path:
    d = _snapshots_root() / "geocode"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapshot_slug(anchor_kst: datetime, location: WeatherLocation) -> str:
    anchor_utc = anchor_kst.astimezone(_UTC)
    basis = (
        f"anchor={anchor_utc.isoformat()}|"
        f"lat={_round_coord(location.latitude)}|lon={_round_coord(location.longitude)}|"
        f"sid={location.site_id}|code={location.site_code or ''}"
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def _snapshot_path(slug: str) -> Path:
    return _snapshots_root() / f"{slug}.json"


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_snapshot_disk(slug: str) -> dict | None:
    path = _snapshot_path(slug)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def _build_advisory(
    weather_label: str,
    temperature: float | None,
    feels_like: float | None,
    wind_speed: float | None,
    precipitation: float | None,
    precipitation_probability: float | None,
    pm10: float | None,
    pm25: float | None,
    weather_code: int | None,
):
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


def _build_unavailable_payload(
    name: str, *, address: str | None = None, site_id: int | None = None, site_code: str | None = None, reason: str = "일시적 조회 실패"
):
    fetched = utc_now()
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=_UTC)
    anchor = kst_weather_snapshot_anchor(fetched)
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
        "updated_at": fetched,
        "status_text": reason,
        "snapshot_anchor_kst": anchor.isoformat(),
        "snapshot_fetched_at": fetched.astimezone(_UTC).isoformat(),
    }


def _geocode_address(name: str, address: str | None):
    query = (address or name or "").strip()
    if not query:
        return None
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()[:24]
    path = _geocode_dir() / f"{h}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return (_round_coord(float(data["latitude"])), _round_coord(float(data["longitude"])))
        except Exception:
            pass
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
            return None
        top = results[0]
        resolved = (_round_coord(top["latitude"]), _round_coord(top["longitude"]))
        _atomic_write_json(path, {"query": query, "latitude": resolved[0], "longitude": resolved[1]})
        return resolved
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


def _live_fetch_open_meteo_payload(location: WeatherLocation) -> dict:
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
    fetched = utc_now()
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=_UTC)
    anchor = kst_weather_snapshot_anchor(fetched)
    return {
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
        "updated_at": fetched,
        "status_text": "정상",
        "snapshot_anchor_kst": anchor.isoformat(),
        "snapshot_fetched_at": fetched.astimezone(_UTC).isoformat(),
    }


def build_weather_snapshot(location: WeatherLocation):
    anchor = kst_weather_snapshot_anchor()
    slug = _snapshot_slug(anchor, location)
    cached = _read_snapshot_disk(slug)
    if isinstance(cached, dict) and isinstance(cached.get("payload"), dict):
        return dict(cached["payload"])

    try:
        payload = _live_fetch_open_meteo_payload(location)
    except Exception:
        payload = _build_unavailable_payload(
            location.name,
            address=location.address,
            site_id=location.site_id,
            site_code=location.site_code,
        )

    envelope = {"payload": payload, "snapshot_slug": slug, "anchor_kst": payload.get("snapshot_anchor_kst")}
    _atomic_write_json(_snapshot_path(slug), envelope)
    return payload


def build_site_weather_summary(site):
    location = resolve_site_location(site)
    if location is None:
        fetched = utc_now()
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=_UTC)
        anchor = kst_weather_snapshot_anchor(fetched)
        p = _build_unavailable_payload(
            getattr(site, "site_name", "현장"),
            address=getattr(site, "address", None),
            site_id=getattr(site, "id", None),
            site_code=getattr(site, "site_code", None),
            reason="위치 정보 없음",
        )
        p["snapshot_anchor_kst"] = anchor.isoformat()
        p["snapshot_fetched_at"] = fetched.astimezone(_UTC).isoformat()
        return p
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
