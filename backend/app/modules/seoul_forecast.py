"""서울의 제공 시점 예보만 선택한다. 관측값이나 일 최저·최고로 바꾸지 않는다."""
import datetime as dt
import json
import math
import os
import tempfile
import threading
import zlib
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

URL = 'https://api.met.no/weatherapi/locationforecast/2.0/complete?lat=37.5665&lon=126.9780'
USER_AGENT = 'BESMA/2026.10.26 (+https://www.besma.co.kr/)'
SOURCE_URL = 'https://api.met.no/weatherapi/locationforecast/2.0/documentation'
LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'
UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))
_LOCK = threading.RLock()
_LIMIT = 256000


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('FORECAST_TIME')
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset() != dt.timedelta(0):
        raise ValueError('FORECAST_UTC')
    return stamp


def _http_date(value):
    if not value:
        return None
    try:
        stamp = parsedate_to_datetime(value)
        return stamp.astimezone(UTC) if stamp.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and -70 <= value <= 70 else None


def _label(symbol):
    if not isinstance(symbol, str):
        return '확인 중'
    code = symbol.split('_')[0]
    labels = {'clearsky': '맑음', 'fair': '대체로 맑음', 'partlycloudy': '구름 많음', 'cloudy': '흐림', 'fog': '안개'}
    if code in labels:
        return labels[code]
    if 'thunder' in code:
        return '뇌우'
    if 'sleet' in code:
        return '진눈깨비'
    if 'snow' in code:
        return '눈'
    if 'rain' in code:
        return '소나기' if 'showers' in code else '비'
    return '확인 중'


def select_forecast(body, now):
    """UTC 원본에서 각 KST 날짜의 15시를 우선 선택한다."""
    if now.tzinfo is None:
        raise ValueError('NOW_TIMEZONE')
    if not isinstance(body, dict) or not isinstance(body.get('geometry'), dict) or body.get('type') != 'Feature' or body['geometry'].get('type') != 'Point':
        raise ValueError('FORECAST_GEOMETRY')
    coords = body['geometry'].get('coordinates', [])
    if len(coords) < 2 or abs(coords[0] - 126.9780) > .0001 or abs(coords[1] - 37.5665) > .0001:
        raise ValueError('FORECAST_LOCATION')
    properties = body.get('properties', {})
    if not isinstance(properties, dict):
        raise ValueError('FORECAST_PROPERTIES')
    meta = properties.get('meta', {})
    if not isinstance(meta, dict) or not isinstance(meta.get('units'), dict):
        raise ValueError('FORECAST_META')
    if meta.get('units', {}).get('air_temperature') != 'celsius':
        raise ValueError('FORECAST_UNITS')
    updated = _utc(meta['updated_at'])
    if updated > now.astimezone(UTC) + dt.timedelta(minutes=10):
        raise ValueError('FORECAST_FUTURE_UPDATE')
    if now.astimezone(UTC) - updated > dt.timedelta(hours=24):
        raise ValueError('FORECAST_STALE_UPDATE')
    series = properties.get('timeseries')
    if not isinstance(series, list) or not 1 <= len(series) <= 1000:
        raise ValueError('FORECAST_SERIES')
    rows = {}
    for item in series:
        stamp = _utc(item['time']).astimezone(KST)
        if stamp in rows:
            raise ValueError('FORECAST_DUPLICATE_TIME')
        data = item.get('data', {})
        temperature = _number(data.get('instant', {}).get('details', {}).get('air_temperature'))
        symbol = next((data.get(period, {}).get('summary', {}).get('symbol_code') for period in ('next_1_hours', 'next_6_hours', 'next_12_hours') if data.get(period, {}).get('summary', {}).get('symbol_code')), None)
        rows[stamp] = (temperature, _label(symbol))
    start = now.astimezone(KST).date()
    days = []
    for i in range(7):
        date = start + dt.timedelta(days=i)
        candidates = sorted(stamp for stamp in rows if stamp.date() == date)
        preferred = next((stamp for stamp in candidates if stamp.hour == 15 and stamp.minute == 0), None)
        selected = preferred or (candidates[0] if candidates else None)
        temperature, label = rows[selected] if selected else (None, '확인 중')
        days.append({'date': str(date), 'temperature': temperature, 'weather_label': label,
                     'forecast_at': selected.isoformat() if selected else None,
                     'forecast_time': selected.strftime('%H:%M') if selected else None})
    return {'available': any(day['temperature'] is not None for day in days), 'location': '서울', 'timezone': 'Asia/Seoul',
            'forecast_kind': 'point_forecast', 'preferred_time': '15:00', 'source': 'MET Norway', 'source_url': SOURCE_URL,
            'license_url': LICENSE_URL, 'processing_note': '제공된 시점 선택 · 기온값 가공 없음',
            'updated_at': meta['updated_at'], 'current': None, 'days': days}


def _unavailable():
    return {'available': False, 'location': '서울', 'timezone': 'Asia/Seoul', 'forecast_kind': 'point_forecast',
            'source': 'MET Norway', 'source_url': SOURCE_URL, 'license_url': LICENSE_URL,
            'processing_note': '제공된 시점 선택 · 기온값 가공 없음', 'updated_at': None, 'current': None, 'days': [],
            'status_text': '서울 예보를 확인하고 있습니다.'}


def _read(path):
    try:
        if path.stat().st_size > _LIMIT * 2:
            return {}
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) and value.get('schema') == 1 and value.get('url') == URL else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.seoul-met-', delete=False) as stream:
            temp = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, separators=(',', ':'))
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


@contextmanager
def _cache_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.with_suffix('.lock').open('ab') as stream:
        if os.name == 'posix':
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'posix':
                fcntl.flock(stream, fcntl.LOCK_UN)


def _cached_forecast(cache_path, *, now=None, opener=None):
    """공유 서버 캐시를 사용하며 Expires 전에는 재요청하지 않는다."""
    now = now or dt.datetime.now(UTC)
    opener = opener or urlopen
    path = Path(cache_path)
    with _cache_lock(path):
        cached = _read(path)
        retry_at = _http_date(cached.get('retry_at'))
        if retry_at and now < retry_at:
            return _unavailable()
        expiry = _http_date(cached.get('expires'))
        if cached.get('body') and expiry and now < expiry:
            try:
                return select_forecast(cached['body'], now)
            except (KeyError, ValueError, TypeError, AttributeError, IndexError):
                return _unavailable()
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate'}
        if cached.get('last_modified'):
            headers['If-Modified-Since'] = cached['last_modified']
        try:
            try:
                response = opener(Request(URL, headers=headers), timeout=6)
            except HTTPError as error:
                if error.code != 304 or not cached.get('body'):
                    raise
                response = error
            with response:
                status = response.status
                if status not in (200, 304):
                    raise ValueError('FORECAST_HTTP_STATUS')
                if status == 304:
                    body = cached['body']
                else:
                    raw = response.read(_LIMIT + 1)
                    if len(raw) > _LIMIT:
                        raise ValueError('FORECAST_SIZE')
                    encoding = response.headers.get('Content-Encoding', '').lower()
                    if encoding in ('gzip', 'deflate'):
                        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS)
                        raw = decoder.decompress(raw, _LIMIT + 1)
                        if decoder.unconsumed_tail or not decoder.eof:
                            raise ValueError('FORECAST_SIZE_OR_ENCODING')
                    elif encoding and encoding != 'identity':
                        raise ValueError('FORECAST_ENCODING')
                    if len(raw) > _LIMIT:
                        raise ValueError('FORECAST_SIZE')
                    body = json.loads(raw)
                value = select_forecast(body, now)
                expires = response.headers.get('Expires')
                if not _http_date(expires):
                    from email.utils import format_datetime
                    expires = format_datetime(now.astimezone(UTC) + dt.timedelta(minutes=30), usegmt=True)
                envelope = {'schema': 1, 'url': URL, 'body': body, 'expires': expires,
                            'last_modified': response.headers.get('Last-Modified') or cached.get('last_modified'),
                            'fetched_at': now.isoformat()}
            _write(path, envelope)
            return value
        except Exception as error:
            from email.utils import format_datetime
            retry = now.astimezone(UTC) + dt.timedelta(minutes=10)
            if isinstance(error, HTTPError):
                retry_header = error.headers.get('Retry-After')
                if retry_header and retry_header.isdigit():
                    retry = now.astimezone(UTC) + dt.timedelta(seconds=max(600, int(retry_header)))
                else:
                    retry = max(retry, _http_date(retry_header) or retry)
                error.close()
            try:
                cached.update({'schema': 1, 'url': URL, 'retry_at': format_datetime(retry, usegmt=True)})
                _write(path, cached)
            except OSError:
                pass
            return _unavailable()


def seoul_forecast(cache_path, *, now=None, opener=None):
    try:
        return _cached_forecast(cache_path, now=now, opener=opener)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        return _unavailable()
