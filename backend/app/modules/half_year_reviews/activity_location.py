"""Read only address-bound map coordinates for an already authorized plan."""
import hashlib,math

def points(sources,directory,registered):
    found=[]
    for source in sources:
        code=source.site_code;site=directory.get(code,{})
        address=site.get('address')or'';record=registered.get(code,{})
        lat,lon=site.get('latitude'),site.get('longitude')
        if lat is None or lon is None:
            if record.get('precision')not in {'address','building','entrance','parcel','rooftop','exact'}:continue
            if record.get('address_sha256')!=hashlib.sha256(address.encode()).hexdigest():continue
            lat,lon=record.get('latitude'),record.get('longitude')
        if type(lat)not in (float,int)or type(lon)not in (float,int)or not math.isfinite(lat)or not math.isfinite(lon):continue
        if not(33<=lat<=39 and 124<=lon<=132):continue
        value={'latitude':lat,'longitude':lon}
        if value not in found:found.append(value)
    return found

def location(db,row):
    from app.modules.inspection_reports.site_identity import resolve_sources
    from app.modules.site_directory import catalog
    from app.modules.workspace_home import location_records
    data,items=catalog(db)
    directory={s['code']:s for s in items}
    return {'locations':points(resolve_sources(db,row),directory,location_records()),'radius_m':1000}
