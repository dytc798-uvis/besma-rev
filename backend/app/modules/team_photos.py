"""Authenticated HQ safety team photo sharing. Originals are append-only."""
from __future__ import annotations

import hashlib
import io
import re
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import text

from app.config.settings import settings
from app.core.auth import DbDep, get_current_user

router = APIRouter(prefix="/team-photos", tags=["team-photos"])
MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 40_000_000
STORAGE = Path(settings.storage_root) / "hq-team-photos"
SLOTS = [
    {"id": "a-door", "group": "A조", "title": "부사장실 쪽 나가는 문", "hint": "문과 대피 방향이 함께 보이게"},
    {"id": "a-stairs", "group": "A조", "title": "후문으로 내려가는 계단", "hint": "계단 아래 방향과 난간이 보이게"},
    {"id": "a-assembly", "group": "A조", "title": "후문 앞 인도 집결지", "hint": "후문과 모일 인도가 함께 보이게"},
    {"id": "b-door", "group": "B조", "title": "정문 쪽 나가는 문", "hint": "문과 대피 방향이 함께 보이게"},
    {"id": "b-stairs", "group": "B조", "title": "정문으로 내려가는 계단", "hint": "계단 아래 방향과 난간이 보이게"},
    {"id": "b-assembly", "group": "B조", "title": "정문 앞 벤치 집결지", "hint": "벤치와 모일 공간이 함께 보이게"},
    {"id": "c-door", "group": "회의조", "title": "옥상정원으로 나가는 문", "hint": "회의실에서 정원으로 향하는 문"},
    {"id": "c-assembly", "group": "회의조", "title": "옥상정원 대기 장소", "hint": "인원이 대기할 공간이 보이게"},
    {"id": "office-overview", "group": "공통", "title": "사무실 전경", "hint": "탕비실과 주변 동선 · 계수대 왼쪽 유리벽이 보이게"},
]
SLOT_IDS = {s["id"] for s in SLOTS} | {"extra"}
SCHEMA = """CREATE TABLE IF NOT EXISTS hq_team_photos (
 id TEXT PRIMARY KEY, slot TEXT NOT NULL, uploader_id INTEGER NOT NULL REFERENCES users(id),
 original_name TEXT NOT NULL, extension TEXT NOT NULL, content_type TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, caption TEXT NOT NULL DEFAULT '',
 width INTEGER NOT NULL, height INTEGER NOT NULL, created_at TEXT NOT NULL,
 request_id TEXT NOT NULL, UNIQUE(uploader_id,request_id))"""


def migrate(connection):
    connection.execute(text(SCHEMA))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_hq_team_photos_created ON hq_team_photos(created_at DESC)"))


def authorized(db: DbDep, user=Depends(get_current_user)):
    role = getattr(user.role, "value", user.role)
    if role != "HQ_SAFE" or not user.is_active:
        raise HTTPException(403, "안전보건실 팀원만 이용할 수 있습니다.")
    member = db.execute(text("SELECT 1 FROM team_schedule_members WHERE user_id=:id AND is_active=1 AND can_read=1"), {"id": user.id}).first()
    if not member:
        raise HTTPException(403, "사진공유 이용 대상이 아닙니다.")
    return user


def record(row):
    return dict(row._mapping)


PUBLIC_COLUMNS = "p.id,p.slot,p.uploader_id,u.name AS uploader_name,p.original_name,p.content_type,p.size_bytes,p.sha256,p.caption,p.width,p.height,p.created_at"


@router.get("/capabilities")
def capabilities(user=Depends(authorized)):
    return {"can_read": True, "can_upload": True, "user_id": user.id, "user_name": user.name,
            "slots": SLOTS, "max_bytes": MAX_BYTES, "version": "2026.10.19.1"}


@router.get("")
def listing(db: DbDep, limit: int = 200, user=Depends(authorized)):
    if not 1 <= limit <= 500:
        raise HTTPException(422, "조회 건수는 1~500입니다.")
    rows = db.execute(text(f"SELECT {PUBLIC_COLUMNS} FROM hq_team_photos p JOIN users u ON u.id=p.uploader_id ORDER BY p.created_at DESC,p.id DESC LIMIT :limit"), {"limit": limit})
    return {"photos": [record(r) for r in rows]}


def safe_name(name):
    name = (name or "photo").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:180]
    return name or "photo"


@router.post("", status_code=201)
def upload(db: DbDep, file: UploadFile = File(...), slot: str = Form(...),
           request_id: str = Form(...), caption: str = Form(""), user=Depends(authorized)):
    if slot not in SLOT_IDS or len(caption) > 300:
        raise HTTPException(422, "사진 항목 또는 설명을 확인해 주세요.")
    try:
        request_id = str(uuid.UUID(request_id))
    except ValueError:
        raise HTTPException(422, "업로드 요청 번호가 올바르지 않습니다.")
    # Authorize before both upload and idempotent replay. No cross-owner replay.
    previous = db.execute(text(f"SELECT {PUBLIC_COLUMNS} FROM hq_team_photos p JOIN users u ON u.id=p.uploader_id WHERE p.uploader_id=:uid AND p.request_id=:rid"), {"uid": user.id, "rid": request_id}).first()
    if previous:
        return record(previous)
    data = bytearray()
    while chunk := file.file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "사진은 25MB 이하로 올려 주세요.")
    if not data:
        raise HTTPException(422, "빈 사진입니다.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                fmt = im.format
                if fmt not in {"JPEG", "PNG", "WEBP"} or im.width * im.height > MAX_PIXELS:
                    raise ValueError("format or dimensions")
                if getattr(im, "n_frames", 1) != 1:
                    raise ValueError("animated image")
                im.load()
                preview = ImageOps.exif_transpose(im).convert("RGB")
                width, height = preview.size
                preview.thumbnail((2000, 2000))
                full = io.BytesIO()
                preview.save(full, format="JPEG", quality=88, optimize=True)
                preview.thumbnail((480, 480))
                thumb = io.BytesIO()
                preview.save(thumb, format="JPEG", quality=82, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "JPG·PNG·WEBP 사진을 선택해 주세요. HEIC 사진은 JPG로 저장한 뒤 올려 주세요.")
    ident = str(uuid.uuid4())
    ext, mime = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}[fmt]
    STORAGE.mkdir(parents=True, exist_ok=True)
    folder = STORAGE / ident
    folder.mkdir(mode=0o750)
    paths = [folder / ("original." + ext), folder / "preview.jpg", folder / "thumb.jpg"]
    try:
        for p, content in zip(paths, [data, full.getvalue(), thumb.getvalue()]):
            p.write_bytes(content)
            p.chmod(0o640)
        db.execute(text("""INSERT INTO hq_team_photos
          (id,slot,uploader_id,original_name,extension,content_type,size_bytes,sha256,caption,width,height,created_at,request_id)
          VALUES (:id,:slot,:uid,:name,:ext,:mime,:size,:hash,:caption,:width,:height,:created,:rid)"""),
          {"id": ident, "slot": slot, "uid": user.id, "name": safe_name(file.filename), "ext": ext, "mime": mime,
           "size": len(data), "hash": hashlib.sha256(data).hexdigest(), "caption": caption.strip(),
           "width": width, "height": height, "created": datetime.now(timezone.utc).isoformat(), "rid": request_id})
        db.commit()
    except Exception:
        db.rollback()
        # Only this failed request's newly created files are removed; no existing history.
        for p in paths:
            p.unlink(missing_ok=True)
        folder.rmdir()
        raise
    return record(db.execute(text(f"SELECT {PUBLIC_COLUMNS} FROM hq_team_photos p JOIN users u ON u.id=p.uploader_id WHERE p.id=:id"), {"id": ident}).one())


@router.get("/{photo_id}/{variant}")
def content(photo_id: str, variant: str, db: DbDep, user=Depends(authorized)):
    try:
        photo_id = str(uuid.UUID(photo_id))
    except ValueError:
        raise HTTPException(404, "사진을 찾을 수 없습니다.")
    if variant not in {"original", "preview", "thumb"}:
        raise HTTPException(404, "사진을 찾을 수 없습니다.")
    row = db.execute(text("SELECT extension,content_type,original_name FROM hq_team_photos WHERE id=:id"), {"id": photo_id}).first()
    if not row:
        raise HTTPException(404, "사진을 찾을 수 없습니다.")
    path = STORAGE / photo_id / ("original." + row.extension if variant == "original" else variant + ".jpg")
    if not path.is_file():
        raise HTTPException(404, "사진 파일을 찾을 수 없습니다.")
    return FileResponse(path, media_type=row.content_type if variant == "original" else "image/jpeg",
                        filename=row.original_name if variant == "original" else None,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
