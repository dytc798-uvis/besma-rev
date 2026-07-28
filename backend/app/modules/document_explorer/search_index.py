from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import struct
import zlib
from pathlib import Path
from threading import Lock
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile

from app.config.settings import settings


INDEX_VERSION = 1
MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
INDEXABLE_EXTENSIONS = {
    ".csv",
    ".docx",
    ".hwp",
    ".hwpx",
    ".md",
    ".pdf",
    ".pptx",
    ".txt",
    ".xls",
    ".xlsx",
    ".xltx",
}
XML_TEXT_EXTENSIONS = {".docx", ".hwpx", ".pptx"}
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_XML_TEXT_RE = re.compile(r">([^<>]+)<")
_INDEX_LOCK = Lock()
_INDEX_CACHE: dict[str, Any] | None = None
_INDEX_CACHE_MTIME_NS: int | None = None
_INDEX_CACHE_PATH: Path | None = None


def _index_path() -> Path:
    return settings.storage_root / "search-index" / "document-explorer.json"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:MAX_TEXT_CHARS]


def _read_plain_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_xlsx(path: Path) -> str:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    parts: list[str] = []
    total_chars = 0
    try:
        for sheet in workbook.worksheets:
            parts.append(sheet.title)
            total_chars += len(sheet.title)
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value not in (None, "")]
                parts.extend(values)
                total_chars += sum(len(value) for value in values)
                if total_chars >= MAX_TEXT_CHARS:
                    return "\n".join(parts)
    finally:
        workbook.close()
    return "\n".join(parts)


def _read_xls(path: Path) -> str:
    import xlrd

    workbook = xlrd.open_workbook(path, on_demand=True)
    parts: list[str] = []
    total_chars = 0
    try:
        for sheet_name in workbook.sheet_names():
            sheet = workbook.sheet_by_name(sheet_name)
            parts.append(sheet_name)
            total_chars += len(sheet_name)
            for row_index in range(sheet.nrows):
                values = [
                    str(value)
                    for value in sheet.row_values(row_index)
                    if value not in (None, "")
                ]
                parts.extend(values)
                total_chars += sum(len(value) for value in values)
                if total_chars >= MAX_TEXT_CHARS:
                    return "\n".join(parts)
    finally:
        workbook.release_resources()
    return "\n".join(parts)


def _read_zipped_xml(path: Path) -> str:
    parts: list[str] = []
    total_chars = 0
    with ZipFile(path) as archive:
        members = sorted(
            name
            for name in archive.namelist()
            if name.lower().endswith(".xml") and not name.startswith(("_rels/", "docProps/"))
        )
        for member in members:
            raw = archive.read(member)
            text = raw.decode("utf-8", errors="ignore")
            values = _XML_TEXT_RE.findall(text)
            parts.extend(values)
            total_chars += sum(len(value) for value in values)
            if total_chars >= MAX_TEXT_CHARS:
                break
    return "\n".join(parts)


def _read_hwp(path: Path) -> str:
    import olefile

    parts: list[str] = []
    total_chars = 0
    with olefile.OleFileIO(path) as compound:
        header = compound.openstream("FileHeader").read()
        compressed = len(header) >= 40 and bool(
            int.from_bytes(header[36:40], "little") & 1
        )
        section_names = sorted(
            "/".join(parts)
            for parts in compound.listdir()
            if len(parts) == 2
            and parts[0] == "BodyText"
            and parts[1].startswith("Section")
        )
        for section_name in section_names:
            data = compound.openstream(section_name).read()
            if compressed:
                data = zlib.decompress(data, -15)
            offset = 0
            while offset + 4 <= len(data):
                record_header = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                tag_id = record_header & 0x3FF
                size = (record_header >> 20) & 0xFFF
                if size == 0xFFF:
                    if offset + 4 > len(data):
                        break
                    size = struct.unpack_from("<I", data, offset)[0]
                    offset += 4
                payload = data[offset : offset + size]
                offset += size
                if tag_id != 67:
                    continue
                decoded = payload.decode("utf-16le", errors="ignore")
                decoded = "".join(
                    character
                    if character in "\n\r\t" or ord(character) >= 32
                    else " "
                    for character in decoded
                )
                parts.append(decoded)
                total_chars += len(decoded)
                if total_chars >= MAX_TEXT_CHARS:
                    return "\n".join(parts)
    return "\n".join(parts)


def extract_search_text(path: Path) -> tuple[str, str]:
    extension = path.suffix.lower()
    if extension not in INDEXABLE_EXTENSIONS:
        return "", "metadata_only"
    if path.stat().st_size > MAX_FILE_BYTES:
        return "", "too_large"
    try:
        if extension in {".txt", ".csv", ".md"}:
            text = _read_plain_text(path)
        elif extension == ".pdf":
            text = _read_pdf(path)
        elif extension == ".hwp":
            text = _read_hwp(path)
        elif extension in {".xlsx", ".xltx"}:
            text = _read_xlsx(path)
        elif extension == ".xls":
            text = _read_xls(path)
        elif extension in XML_TEXT_EXTENSIONS:
            text = _read_zipped_xml(path)
        else:
            return "", "metadata_only"
    except (BadZipFile, OSError, ValueError, RuntimeError, TypeError):
        return "", "parse_failed"
    except Exception:
        # 손상된 외부 문서 하나가 전체 검색을 막지 않게 메타데이터 검색으로 강등한다.
        return "", "parse_failed"
    cleaned = _clean_text(text)
    return cleaned, "indexed" if cleaned else "empty"


def _load_index() -> dict[str, Any]:
    global _INDEX_CACHE, _INDEX_CACHE_MTIME_NS, _INDEX_CACHE_PATH
    path = _index_path()
    try:
        current_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        current_mtime_ns = None
    if (
        _INDEX_CACHE is not None
        and path == _INDEX_CACHE_PATH
        and current_mtime_ns is not None
        and current_mtime_ns == _INDEX_CACHE_MTIME_NS
    ):
        return _INDEX_CACHE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") == INDEX_VERSION and isinstance(payload.get("items"), dict):
            _INDEX_CACHE = payload
            _INDEX_CACHE_MTIME_NS = current_mtime_ns
            _INDEX_CACHE_PATH = path
            return payload
    except (OSError, ValueError, TypeError):
        pass
    return {"version": INDEX_VERSION, "generated_at": None, "items": {}}


def _write_index(payload: dict[str, Any]) -> None:
    global _INDEX_CACHE, _INDEX_CACHE_MTIME_NS, _INDEX_CACHE_PATH
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)
    _INDEX_CACHE = payload
    _INDEX_CACHE_MTIME_NS = path.stat().st_mtime_ns
    _INDEX_CACHE_PATH = path


def refresh_document_index(
    documents: Iterable[tuple[str, Path]],
    *,
    force: bool = False,
) -> dict[str, Any]:
    with _INDEX_LOCK:
        payload = _load_index()
        previous = payload["items"]
        refreshed: dict[str, Any] = {}
        changed = False
        indexed_count = 0

        for relative_path, path in documents:
            try:
                stat = path.stat()
            except OSError:
                continue
            cached = previous.get(relative_path)
            if (
                not force
                and cached
                and cached.get("mtime_ns") == stat.st_mtime_ns
                and cached.get("size_bytes") == stat.st_size
            ):
                item = cached
            else:
                text, status = extract_search_text(path)
                item = {
                    "mtime_ns": stat.st_mtime_ns,
                    "size_bytes": stat.st_size,
                    "text": text,
                    "status": status,
                }
                changed = True
            refreshed[relative_path] = item
            if item.get("status") == "indexed":
                indexed_count += 1

        if set(previous) != set(refreshed):
            changed = True
        payload = {
            "version": INDEX_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": refreshed,
        }
        if changed or not _index_path().exists():
            _write_index(payload)
        return {
            "total": len(refreshed),
            "indexed": indexed_count,
            "metadata_only": len(refreshed) - indexed_count,
            "changed": changed,
            "items": refreshed,
        }


def _query_tokens(query: str) -> list[str]:
    return list(dict.fromkeys(token.lower() for token in _TOKEN_RE.findall(query)))


def _snippet(text: str, tokens: list[str], max_chars: int = 180) -> str | None:
    if not text or not tokens:
        return None
    lowered = text.lower()
    positions = [lowered.find(token) for token in tokens]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return None
    start = max(0, min(positions) - 55)
    end = min(len(text), start + max_chars)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def score_document(
    *,
    query: str,
    name: str,
    relative_path: str,
    indexed_text: str,
) -> tuple[float, str | None, str | None]:
    phrase = _clean_text(query).lower()
    tokens = _query_tokens(query)
    if not tokens:
        return 0.0, None, None

    name_lower = name.lower()
    path_lower = relative_path.lower()
    text_lower = indexed_text.lower()
    matched = [
        token
        for token in tokens
        if token in name_lower or token in path_lower or token in text_lower
    ]
    if not matched:
        return 0.0, None, None

    score = 0.0
    if phrase and phrase in name_lower:
        score += 30
    elif phrase and phrase in path_lower:
        score += 18
    elif phrase and phrase in text_lower:
        score += 8
    for token in tokens:
        if token in name_lower:
            score += 10
        if token in path_lower:
            score += 5
        if token in text_lower:
            score += 2
    if len(matched) == len(tokens):
        score += 10

    if any(token in name_lower or token in path_lower for token in matched):
        match_source = "metadata"
    else:
        match_source = "content"
    return round(score, 2), _snippet(indexed_text, matched), match_source
