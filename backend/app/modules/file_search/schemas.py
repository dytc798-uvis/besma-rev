from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Iterable, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_CHUNK_ENTRIES = 2_000
MAX_CHUNKS_PER_SESSION = 10_000
MAX_CHUNK_REQUEST_BYTES = 768 * 1024
MAX_EXPECTED_ENTRIES = 250_000
MAX_RELATIVE_PATH_LENGTH = 2_048
MAX_QUERY_LENGTH = 100
MAX_QUERY_TOKENS = 8
MAX_SEARCH_EXTENSIONS = 32
FILE_SEARCH_CONTRACT_VERSION = "jsi.file-search.v1a06"

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_INSTALLATION_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_INVALID_NAME_CHARACTERS = frozenset('<>:"|?*')
_ASCII_UPPERCASE_TRANSLATION = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)

DENIED_EXTENSIONS = frozenset(
    {
        ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe",
        ".js", ".jse", ".wsf", ".wsh", ".lnk", ".url", ".scr", ".msi",
        ".msp", ".reg", ".pem", ".key", ".pfx", ".p12", ".hta", ".cpl",
        ".msc", ".chm", ".application", ".appref-ms", ".jar", ".scf", ".cer",
        ".crt", ".ppk", ".jks", ".keystore", ".kdbx",
    }
)
DENIED_DIRECTORY_NAMES = frozenset(
    {
        ".secrets", "secrets", "credentials", "securekeys", "private_keys", ".ssh",
        ".aws", ".azure", ".gnupg", "공동인증서", "개인키",
    }
)
PROFILE_ROOT_NAMES = frozenset({"users", "documents and settings", "home", "사용자"})
DENIED_NAME_SIGNALS = (
    "주민", "신분증", "자격증", "재직", "통장", "인감", "인증서", "공동인증",
    "개인키", "비밀키", "비밀번호", "패스워드", "password", "passwd", "private_key",
    "secret_key", "api_key", "access_key", "ssh_key", "credential",
)
TOKEN_LIKE_EXTENSIONS = frozenset({".json", ".txt", ".yaml", ".yml", ".ini", ".cfg"})
TEAM_SAFETY_NAS_LOGICAL_ROOT_ID = "team-safety-nas-z4"
TEAM_SAFETY_NAS_DENIED_RELATIVE_PREFIXES = (
    "000.개인폴더",
    "003 정상익 차장 업무폴더",
    "104 사고 조사 및 이력",
    "997 엄재복 대리 업무폴더",
    "998 김복수 상무 자료",
    "공지사항/SafetyTeamDesk",
)


class FileSearchScope(StrEnum):
    PERSONAL = "PERSONAL"
    TEAM_SAFETY_NAS = "TEAM_SAFETY_NAS"


class FileSearchSort(StrEnum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    NAME = "name"


def _contains_control_character(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def normalize_nfc(value: str, *, field_name: str, maximum_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if _contains_control_character(value):
        raise ValueError(f"{field_name} contains a control character")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized or len(normalized) > maximum_length:
        raise ValueError(f"{field_name} length is invalid")
    return normalized


def normalize_relative_path(value: str) -> str:
    normalized = normalize_nfc(
        value,
        field_name="relative_path",
        maximum_length=MAX_RELATIVE_PATH_LENGTH,
    )
    if normalized.startswith(("/", "\\")) or _DRIVE_PATH_RE.match(normalized):
        raise ValueError("relative_path must not be absolute")
    raw_parts = re.split(r"[\\/]", normalized)
    if any(not part or part in {".", ".."} for part in raw_parts):
        raise ValueError("relative_path contains an invalid component")
    for part in raw_parts:
        if any(character in _WINDOWS_INVALID_NAME_CHARACTERS for character in part):
            raise ValueError("relative_path contains an invalid Windows filename character")
    if raw_parts[0].casefold() in PROFILE_ROOT_NAMES:
        raise ValueError("relative_path must be relative to the selected root, not a user profile")
    return "/".join(raw_parts)


def canonical_modified_at(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("modified_at must include a timezone")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def normalize_extension(value: str) -> str:
    """Normalize extensions without language-specific Unicode case folding.

    The desktop client and server share an exact byte contract. ASCII file
    extensions are case-insensitive, while every non-ASCII code point remains
    NFC-preserved so runtimes with different Unicode tables cannot disagree.
    """

    if not isinstance(value, str) or _contains_control_character(value):
        raise ValueError("extension contains a control character")
    return unicodedata.normalize("NFC", value).strip().translate(
        _ASCII_UPPERCASE_TRANSLATION
    )


class IndexEntry(BaseModel):
    """The only metadata accepted from an index publisher."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str
    file_name: str
    extension: str = Field(max_length=64)
    size: int = Field(ge=0, le=9_223_372_036_854_775_807)
    modified_at: datetime | None = None
    is_directory: bool

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        normalized = normalize_nfc(value, field_name="file_name", maximum_length=255)
        if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
            raise ValueError("file_name must be one path component")
        if any(character in _WINDOWS_INVALID_NAME_CHARACTERS for character in normalized):
            raise ValueError("file_name contains an invalid Windows filename character")
        return normalized

    @field_validator("extension")
    @classmethod
    def validate_extension(cls, value: str) -> str:
        normalized = normalize_extension(value)
        if normalized and (not normalized.startswith(".") or "/" in normalized or "\\" in normalized):
            raise ValueError("extension is invalid")
        return normalized

    @field_validator("modified_at")
    @classmethod
    def validate_modified_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("modified_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_path_contract(self) -> Self:
        path_name = PurePosixPath(self.relative_path).name
        if path_name.casefold() != self.file_name.casefold():
            raise ValueError("file_name must match the final relative_path component")
        expected_extension = (
            "" if self.is_directory else normalize_extension(PurePosixPath(self.file_name).suffix)
        )
        if self.extension != expected_extension:
            raise ValueError("extension must match file_name")
        if self.extension in DENIED_EXTENSIONS:
            raise ValueError("executable, script, shortcut, or credential files are not allowed")

        components = [component.casefold() for component in PurePosixPath(self.relative_path).parts]
        if any(component in DENIED_DIRECTORY_NAMES for component in components[:-1]):
            raise ValueError("sensitive directories are not allowed")
        normalized_name = self.file_name.casefold()
        if normalized_name.startswith(".env") or normalized_name in {".npmrc", "token.json", "secrets.json"}:
            raise ValueError("sensitive filenames are not allowed")
        if any(signal in self.relative_path.casefold() for signal in DENIED_NAME_SIGNALS):
            raise ValueError("sensitive filename signals are not allowed")
        if (
            ("token" in normalized_name or "secret" in normalized_name)
            and self.extension in TOKEN_LIKE_EXTENSIONS
        ):
            raise ValueError("token or secret metadata files are not allowed")
        return self


class IndexSessionBeginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: FileSearchScope
    logical_root_id: str
    root_label: str
    installation_id: str
    expected_entry_count: int = Field(ge=0, le=MAX_EXPECTED_ENTRIES)
    confirmed_previous_entry_count: int | None = Field(
        default=None,
        ge=0,
        le=MAX_EXPECTED_ENTRIES,
    )
    expected_sha256: str
    generated_at: datetime

    @field_validator("logical_root_id", "installation_id")
    @classmethod
    def validate_identifier(cls, value: str, info) -> str:
        maximum = 128 if info.field_name == "logical_root_id" else 200
        normalized = normalize_nfc(value, field_name=info.field_name, maximum_length=maximum)
        pattern = _IDENTIFIER_RE if info.field_name == "logical_root_id" else _INSTALLATION_ID_RE
        if not pattern.fullmatch(normalized):
            raise ValueError(f"{info.field_name} is invalid")
        if info.field_name == "installation_id" or _SHA256_RE.fullmatch(normalized):
            return normalized.lower()
        return normalized

    @field_validator("root_label")
    @classmethod
    def validate_root_label(cls, value: str) -> str:
        normalized = normalize_nfc(value, field_name="root_label", maximum_length=200)
        if "/" in normalized or "\\" in normalized or _DRIVE_PATH_RE.match(normalized):
            raise ValueError("root_label must be a display label, not a path")
        return normalized

    @field_validator("expected_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not isinstance(value, str) or _contains_control_character(value) or not _SHA256_RE.fullmatch(value):
            raise ValueError("expected_sha256 is invalid")
        return value.lower()

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_scope_source_identity(self) -> Self:
        if self.scope is FileSearchScope.PERSONAL:
            if not _SHA256_RE.fullmatch(self.logical_root_id):
                raise ValueError("PERSONAL logical_root_id must be an opaque 64-hex identifier")
        else:
            if self.logical_root_id != TEAM_SAFETY_NAS_LOGICAL_ROOT_ID:
                raise ValueError("TEAM_SAFETY_NAS logical_root_id is not approved")
        return self


class IndexChunkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str
    entries: list[IndexEntry] = Field(min_length=1, max_length=MAX_CHUNK_ENTRIES)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not isinstance(value, str) or _contains_control_character(value) or not _SHA256_RE.fullmatch(value):
            raise ValueError("sha256 is invalid")
        return value.lower()


class SearchResultEntry(IndexEntry):
    scope: FileSearchScope
    logical_root_id: str
    root_label: str
    installation_id: str
    generated_at: datetime
    is_important: bool = False
    mobile_view_available: bool = False
    important_file_id: str | None = None


class FolderSelector(BaseModel):
    """One exact active source and an optional relative folder within it."""

    model_config = ConfigDict(extra="forbid")

    scope: FileSearchScope
    logical_root_id: str
    installation_id: str
    relative_path: str = ""

    @field_validator("logical_root_id")
    @classmethod
    def validate_logical_root_id(cls, value: str) -> str:
        normalized = normalize_nfc(
            value,
            field_name="logical_root_id",
            maximum_length=128,
        )
        if not _IDENTIFIER_RE.fullmatch(normalized):
            raise ValueError("logical_root_id is invalid")
        return normalized.lower() if _SHA256_RE.fullmatch(normalized) else normalized

    @field_validator("installation_id")
    @classmethod
    def validate_installation_id(cls, value: str) -> str:
        normalized = normalize_nfc(
            value,
            field_name="installation_id",
            maximum_length=200,
        )
        if not _INSTALLATION_ID_RE.fullmatch(normalized):
            raise ValueError("installation_id is invalid")
        return normalized.lower()

    @field_validator("relative_path")
    @classmethod
    def validate_folder_relative_path(cls, value: str) -> str:
        if value == "":
            return ""
        return normalize_relative_path(value)

    @model_validator(mode="after")
    def validate_scope_source_identity(self) -> Self:
        if self.scope is FileSearchScope.PERSONAL:
            if not _SHA256_RE.fullmatch(self.logical_root_id):
                raise ValueError("PERSONAL logical_root_id must be an opaque 64-hex identifier")
        elif self.logical_root_id != TEAM_SAFETY_NAS_LOGICAL_ROOT_ID:
            raise ValueError("TEAM_SAFETY_NAS logical_root_id is not approved")
        return self


class SearchRequest(BaseModel):
    """Search terms belong in the JSON body so access logs never receive them."""

    model_config = ConfigDict(extra="forbid")

    q: str
    scopes: list[str] | None = Field(default=None, max_length=2)
    extensions: list[str] | None = Field(default=None, max_length=MAX_SEARCH_EXTENSIONS)
    folder: FolderSelector | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, strict=True, ge=0, le=1_000_000)
    sort: FileSearchSort = FileSearchSort.RELEVANCE

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        normalized_values: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = normalize_extension(item)
            if (
                not normalized
                or len(normalized) > 64
                or not normalized.startswith(".")
                or "/" in normalized
                or "\\" in normalized
            ):
                raise ValueError("extensions contains an invalid extension")
            if normalized not in seen:
                seen.add(normalized)
                normalized_values.append(normalized)
        return normalized_values


class SearchResponse(BaseModel):
    """A bounded page plus the full filtered-match count.

    ``total_count`` is calculated after every visibility and query predicate,
    before the requested ordering and display limit are applied.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[SearchResultEntry]
    count: int = Field(ge=0, le=500)
    total_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.count != len(self.items) or self.total_count < self.count:
            raise ValueError("search response counts are inconsistent")
        return self


class FolderRequest(FolderSelector):
    """POST body for lazy immediate-child folder enumeration."""


def canonical_entry_line(entry: IndexEntry | dict) -> bytes:
    """Return the language-neutral canonical row used by all publishers.

    Format (UTF-8): relative_path NUL file_name NUL extension NUL size NUL
    modified_at UTC ISO-8601-or-empty NUL is_directory(0|1) LF.
    """

    normalized = entry if isinstance(entry, IndexEntry) else IndexEntry.model_validate(entry)
    fields = (
        normalized.relative_path,
        normalized.file_name,
        normalized.extension,
        str(normalized.size),
        canonical_modified_at(normalized.modified_at),
        "1" if normalized.is_directory else "0",
    )
    return ("\0".join(fields) + "\n").encode("utf-8")


def canonical_entries_bytes(entries: Iterable[IndexEntry | dict]) -> bytes:
    """Canonicalize rows in unsigned lexicographic NFC relative-path UTF-8 order."""

    normalized = [
        entry if isinstance(entry, IndexEntry) else IndexEntry.model_validate(entry)
        for entry in entries
    ]
    normalized.sort(key=lambda entry: entry.relative_path.encode("utf-8"))
    seen_casefolded_paths: set[str] = set()
    rows: list[bytes] = []
    for entry in normalized:
        key = entry.relative_path.casefold()
        if key in seen_casefolded_paths:
            raise ValueError("relative_path must be unique ignoring case")
        seen_casefolded_paths.add(key)
        rows.append(canonical_entry_line(entry))
    return b"".join(rows)


def canonical_entries_sha256(entries: Iterable[IndexEntry | dict]) -> str:
    """Public Python publisher helper for the cross-language SHA-256 contract."""

    return hashlib.sha256(canonical_entries_bytes(entries)).hexdigest()


def search_text_for_entry(entry: IndexEntry) -> str:
    return unicodedata.normalize(
        "NFC",
        "\n".join((entry.relative_path, entry.file_name, entry.extension)),
    ).casefold()


def normalize_query_tokens(
    query: str,
    *,
    allow_empty: bool = False,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(query, str):
        raise ValueError("q must be a string")
    if _contains_control_character(query):
        raise ValueError("q contains a control character")
    normalized = unicodedata.normalize("NFC", query).strip()
    if not normalized:
        if allow_empty:
            return (), ()
        raise ValueError("q must contain between 1 and 8 whitespace-delimited tokens")
    if len(normalized) > MAX_QUERY_LENGTH:
        raise ValueError("q length is invalid")
    included: list[str] = []
    excluded: list[str] = []
    seen: set[tuple[bool, str]] = set()
    for raw_token in normalized.split():
        is_excluded = raw_token.startswith("/")
        token = raw_token[1:] if is_excluded else raw_token
        if not token:
            raise ValueError("an exclusion token must contain text after '/'")
        folded = token.casefold()
        key = (is_excluded, folded)
        if key in seen:
            continue
        seen.add(key)
        (excluded if is_excluded else included).append(folded)
    if not 1 <= len(seen) <= MAX_QUERY_TOKENS:
        raise ValueError("q must contain between 1 and 8 whitespace-delimited tokens")
    return tuple(included), tuple(excluded)
