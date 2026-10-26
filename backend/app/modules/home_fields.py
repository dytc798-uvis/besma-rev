"""workspace_home에 합칠 순수 함수 후보. 호출 전 기존 workspace.authorized를 유지한다."""
import hashlib
import math
import re


def bound_location_region(address, point, latitude, longitude):
    """현재 주소와 같은 좌표에 묶인 기존 위치자료의 명확한 시·도만 보완한다."""
    if not isinstance(address, str) or not address.strip() or not isinstance(point, dict):return None
    if point.get('address_sha256') != hashlib.sha256(address.encode()).hexdigest():return None
    if point.get('address') != address or point.get('precision') in (None, '', 'unresolved'):return None
    values = (latitude, longitude, point.get('latitude'), point.get('longitude'))
    try:
        if any(isinstance(v, bool) or v is None or not math.isfinite(float(v)) for v in values):return None
        lat, lon, source_lat, source_lon = map(float, values)
    except (ValueError, TypeError, OverflowError):return None
    if not (33 <= lat <= 39 and 124 <= lon <= 132 and lat == source_lat and lon == source_lon):return None
    provinces = {'서울특별시': '서울', '경기도': '경기', '인천광역시': '인천',
                 '강원도': '강원권', '강원특별자치도': '강원권',
                 '충청북도': '충청권', '충청남도': '충청권', '대전광역시': '충청권', '세종특별자치시': '충청권',
                 '전라북도': '호남권', '전북특별자치도': '호남권', '전라남도': '호남권', '광주광역시': '호남권',
                 '경상북도': '영남권', '경상남도': '영남권', '부산광역시': '영남권', '대구광역시': '영남권', '울산광역시': '영남권',
                 '제주특별자치도': '제주권'}
    # 도로명·현장명 문자열을 검색하지 않고 쉼표로 구분된 행정구역 토큰만 읽는다.
    tokens = [token.strip() for token in str(point.get('display_name') or '').split(',')]
    found = [token for token in tokens if token in provinces]
    return provinces[found[0]] if len(found) == 1 else None


def home_site_fields(site, user=None):
    """현장검색의 완성 레코드만 사용하며 새로운 담당 배정을 만들지 않는다."""
    team = re.match(r'^\[([1-6])\.', str(site.get('name') or '').strip())
    role = getattr(getattr(user, 'role', None), 'value', getattr(user, 'role', None))
    full_allowed = bool(user and getattr(user, 'is_active', False) and role == 'HQ_SAFE')
    fields = {
        'team': {'key': team[1], 'label': f'공사{team[1]}팀', 'source': '현장검색 현장명 팀 표기'} if team else None,
        'contacts': [{key: contact.get(key, '') for key in (
            'name', 'role', 'rank', 'label', 'phone', 'contact_id', 'rank_revision', 'rank_confirmed'
        )} for contact in site.get('contacts', [])],
        'contractor': next((d['value'] for d in site.get('details', []) if d['key'] == 'contractor'), ''),
        'client': next((d['value'] for d in site.get('details', []) if d['key'] == 'client'), ''),
        'info_revision': site.get('info_revision', 0),
        'full_detail_available': full_allowed,
    }
    if full_allowed:
        fields.update(
            details=[{key: d.get(key, '') for key in ('key', 'label', 'value', 'unit')} for d in site.get('details', [])],
            contracts=[{key: c.get(key, '') for key in ('name', 'amount', 'basis', 'start', 'end')} for c in site.get('contracts', [])],
            contract_total_complete=site.get('contract_total_complete', False),
        )
    return fields


def home_site_scope(sites):
    """홈에 실제 포함된 현장 범위만 집계한다. 지도 제외는 전체 집계에서 빼지 않는다."""
    team_keys = tuple(str(i) for i in range(1, 7))
    groups = {key: [] for key in team_keys}
    unknown = []
    for site in sites:
        key = (site.get('team') or {}).get('key')
        (groups[key] if key in groups else unknown).append(site)
    teams = [
        {'key': key, 'label': f'공사{key}팀', 'site_count': len(group),
         'map_site_count': sum(s.get('map_visible') is not False for s in group)}
        for key, group in groups.items()
    ]
    teams.append({'key': 'unconfirmed', 'label': '팀 확인 중', 'site_count': len(unknown),
                  'map_site_count': sum(s.get('map_visible') is not False for s in unknown)})
    scope = {
        'site_count': len(sites),
        'map_site_count': sum(s.get('map_visible') is not False for s in sites),
        'missing_address_count': sum(not str(s.get('address') or '').strip() for s in sites),
        'unknown_region_count': sum(s.get('region') not in ('서울', '경기', '인천', '강원권', '충청권', '호남권', '영남권', '제주권') for s in sites),
        'missing_coordinate_count': sum(s.get('latitude') is None or s.get('longitude') is None for s in sites),
        'missing_map_coordinate_count': sum(s.get('map_visible') is not False and (s.get('latitude') is None or s.get('longitude') is None) for s in sites),
        'unconfirmed_team_count': len(unknown),
        'team_source': '현장검색 현장명 시작의 [1~6. 표기',
    }
    return {'teams': teams, 'site_scope': scope}
