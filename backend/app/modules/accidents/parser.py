# -*- coding: utf-8 -*-
"""네이버웍스형 최초보고 메시지 파서 (정규식 + 방어적 처리)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

_WS = re.compile(r"\s+")
_TRAILING_REASON_MARKERS = re.compile(
    r"\s*(?:사유로|원인으로|원인|이유로|이유|로|중|도중|과정에서|상태에서)\s*$"
)

_NORM = (
    (r"이에\s*대\s*해", "이에대해"),
    (r"이에\s*대하여", "이에대해"),
)
_TEMPLATE_MARKER = "[사고최초보고]"
_TEMPLATE_FIELDS: list[tuple[str, str]] = [
    ("site_name", "현장명"),
    ("reporter_name", "보고자"),
    ("accident_datetime_text", "사고시각"),
    ("accident_place", "사고장소"),
    ("work_content", "작업내용"),
    ("injured_person_name", "재해자"),
    ("accident_circumstance", "사고경위"),
    ("accident_reason", "사고원인"),
    ("injured_part", "상해부위"),
    ("action_taken", "조치사항"),
]


def _label_pattern(label: str) -> str:
    return r"\s*".join(re.escape(ch) for ch in label if not ch.isspace())


_ALL_TEMPLATE_LABELS = "|".join(_label_pattern(label) for _, label in _TEMPLATE_FIELDS)


def _normalize_text(text: str) -> str:
    t = text.strip()
    for a, b in _NORM:
        t = re.sub(a, b, t, flags=re.IGNORECASE)
    t = _WS.sub(" ", t)
    return t


def _strip_role(name: str | None) -> str | None:
    if not name:
        return name
    n = name.strip()
    n = re.sub(r"\s*반장$", "", n)
    n = re.sub(r"\s*작업자$", "", n)
    return n.strip() or None


def _clean_segment(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _WS.sub(" ", value).strip(" ,.")
    return cleaned or None


def _derive_accident_reason(segment: str | None) -> str | None:
    cleaned = _clean_segment(segment)
    if not cleaned:
        return None
    cleaned = _TRAILING_REASON_MARKERS.sub("", cleaned).strip(" ,.")
    return cleaned or None


def _extract_victim_reason(text: str) -> tuple[str | None, str | None, str | None]:
    patterns = [
        r"수행하던\s*(?P<victim>.+?)(?:이|가)\s*(?P<circumstance>.+?)\s*인해",
        r"작업하던\s*(?P<victim>.+?)(?:이|가)\s*(?P<circumstance>.+?)\s*인해",
        r"수행\s*중이던\s*(?P<victim>.+?)(?:이|가)\s*(?P<circumstance>.+?)\s*인해",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        victim = _strip_role(_clean_segment(match.group("victim")))
        circumstance = _clean_segment(match.group("circumstance"))
        reason = _derive_accident_reason(circumstance)
        if victim:
            return victim, reason, circumstance
    return None, None, None


def _extract_template_fields(message_raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    note: dict[str, Any] = {"template_marker_present": _TEMPLATE_MARKER in message_raw}
    fields: dict[str, Any] = {
        "site_name": None,
        "reporter_name": None,
        "accident_datetime_text": None,
        "accident_datetime": None,
        "accident_place": None,
        "work_content": None,
        "injured_person_name": None,
        "accident_circumstance": None,
        "accident_reason": None,
        "injured_part": None,
        "diagnosis_name": None,
        "action_taken": None,
    }
    if not note["template_marker_present"]:
        return fields, note

    body = message_raw.split(_TEMPLATE_MARKER, 1)[1].replace("\r\n", "\n").replace("\r", "\n")
    closing_pattern = re.compile(r"\s*위와\s*같이\s*보고드립니다\.?\s*$", flags=re.IGNORECASE)
    for key, label in _TEMPLATE_FIELDS:
        pattern = re.compile(
            rf"(?ims)^\s*{_label_pattern(label)}\s*:\s*(.*?)\s*(?=^\s*(?:{_ALL_TEMPLATE_LABELS})\s*:|\Z)"
        )
        match = pattern.search(body)
        if not match:
            note[f"template_{key}"] = False
            continue
        raw_value = closing_pattern.sub("", match.group(1)).strip()
        cleaned = _clean_segment(raw_value)
        if key == "accident_datetime_text":
            dt_text, dt = _parse_datetime_fragment(cleaned)
            fields["accident_datetime_text"] = dt_text
            fields["accident_datetime"] = dt
            note[f"template_{key}"] = bool(dt_text)
            continue
        fields[key] = cleaned
        note[f"template_{key}"] = bool(cleaned)
    return fields, note


def evaluate_parse_fields(fields: dict[str, Any], note: dict[str, Any] | None = None) -> tuple[str, str]:
    work_note = dict(note or {})
    patterns = dict(work_note.get("patterns") or {})
    site_name = fields.get("site_name")
    reporter_name = fields.get("reporter_name")
    accident_datetime_text = fields.get("accident_datetime_text")
    accident_place = fields.get("accident_place")
    work_content = fields.get("work_content")
    injured_person_name = fields.get("injured_person_name")
    accident_circumstance = fields.get("accident_circumstance")
    accident_reason = fields.get("accident_reason")
    injured_part = fields.get("injured_part")

    template_marker_present = bool(
        work_note.get("template_marker_present")
        or patterns.get("template_marker")
    )
    required_success_fields = {
        "현장명": bool(site_name),
        "보고자": bool(reporter_name),
        "사고시각": bool(accident_datetime_text),
        "사고장소": bool(accident_place),
        "작업내용": bool(work_content),
        "재해자": bool(injured_person_name),
        "사고경위": bool(accident_circumstance),
        "사고원인": bool(accident_reason),
    }
    work_note["template_marker_present"] = template_marker_present
    work_note["required_success_fields"] = required_success_fields
    work_note["missing_required_fields"] = [label for label, ok in required_success_fields.items() if not ok]

    filled = sum(1 for key, value in fields.items() if key != "accident_datetime" and value)
    if fields.get("accident_datetime"):
        filled += 1
    required_filled = sum(1 for ok in required_success_fields.values() if ok)

    if template_marker_present and all(required_success_fields.values()):
        parse_status = "success"
    elif required_filled > 0 or filled > 0:
        parse_status = "partial"
    else:
        parse_status = "failed"

    work_note["parse_status_basis"] = {
        "filled_field_count": filled,
        "required_filled_count": required_filled,
        "template_marker_present": template_marker_present,
        "required_success_satisfied": all(required_success_fields.values()),
    }
    return parse_status, json.dumps(work_note, ensure_ascii=False)


def _parse_datetime_fragment(frag: str | None) -> tuple[str | None, datetime | None]:
    if not frag:
        return None, None
    frag = frag.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return frag, datetime.strptime(frag, fmt)
        except ValueError:
            pass
    m = re.search(r"(오전|오후)?\s*(\d{1,2})\s*시\s*(\d{1,2})\s*분", frag)
    if not m:
        return frag, None
    meridiem = m.group(1)
    h, mi = int(m.group(2)), int(m.group(3))
    if meridiem == "오후" and h < 12:
        h += 12
    if meridiem == "오전" and h == 12:
        h = 0
    try:
        dt = datetime.combine(date.today(), datetime.min.time().replace(hour=h, minute=mi))
    except ValueError:
        return frag, None
    return frag, dt


def parse_initial_report_message(message_raw: str) -> dict[str, Any]:
    text = _normalize_text(message_raw)
    template_fields, template_note = _extract_template_fields(message_raw)
    note: dict[str, Any] = {
        "patterns": {
            "template_marker": bool(template_note.get("template_marker_present")),
        },
        "template_marker_present": bool(template_note.get("template_marker_present")),
    }
    note.update(template_note)

    fields = dict(template_fields)
    if not note["template_marker_present"]:
        site_name = reporter_name = None
        m_open = re.search(r"안녕하세요\.\s*(.+?)입니다\.?", text)
        if m_open:
            prefix = m_open.group(1).strip()
            m_sr = re.search(r"(?P<site>.+현장)\s+(?P<reporter>\S+)$", prefix)
            if m_sr:
                site_name = m_sr.group("site").strip()
                reporter_name = m_sr.group("reporter").strip()
                note["patterns"]["opening_site_reporter"] = True
            else:
                note["patterns"]["opening_site_reporter"] = False

        accident_datetime_text = None
        m_time = re.search(r"금일\s*([^,，]+?)[,，]", text)
        if not m_time:
            m_time = re.search(r"금일\s*([^\.\s]+(?:\s*\d{1,2}\s*시\s*\d{1,2}\s*분)?)", text)
        if m_time:
            accident_datetime_text = m_time.group(1).strip()
            note["patterns"]["time_fragment"] = True
        else:
            note["patterns"]["time_fragment"] = False

        accident_datetime_text, accident_datetime = _parse_datetime_fragment(
            accident_datetime_text
        )

        accident_place = work_content = None
        m_loc = re.search(
            r"당\s*현장\s*내\s*(.+?)에서\s*(.+?)(?:을|를)\s*수행하던",
            text,
        )
        if m_loc:
            accident_place = m_loc.group(1).strip()
            work_content = m_loc.group(2).strip()
            note["patterns"]["place_work"] = True
        else:
            note["patterns"]["place_work"] = False

        injured_person_name, accident_reason, accident_circumstance = _extract_victim_reason(text)
        if injured_person_name:
            note["patterns"]["victim_reason"] = True
        else:
            note["patterns"]["victim_reason"] = False

        injured_part = diagnosis_name = None
        m_pd = re.search(r"인해\s*(.+?)이\s*(.+?)되었습니다", text)
        if not m_pd:
            m_pd = re.search(r"인해\s*(.+?)가\s*(.+?)되었습니다", text)
        if m_pd:
            injured_part = m_pd.group(1).strip()
            diagnosis_name = m_pd.group(2).strip()
            note["patterns"]["part_diagnosis"] = True
        else:
            note["patterns"]["part_diagnosis"] = False

        fields = {
            "site_name": site_name,
            "reporter_name": reporter_name,
            "accident_datetime_text": accident_datetime_text,
            "accident_datetime": accident_datetime,
            "accident_place": accident_place,
            "work_content": work_content,
            "injured_person_name": injured_person_name,
            "accident_circumstance": accident_circumstance,
            "accident_reason": accident_reason,
            "injured_part": injured_part,
            "diagnosis_name": diagnosis_name,
            "action_taken": None,
        }

    parse_status, parse_note = evaluate_parse_fields(fields, note)

    return {
        "fields": fields,
        "parse_status": parse_status,
        "parse_note": parse_note,
    }


def compose_initial_report_view(fields: dict[str, Any], message_raw: str) -> dict[str, Any]:
    def nz(v: Any, fallback: str = "(미입력)") -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return fallback
        return str(v).strip()

    f = fields
    line = "\n".join(
        [
            "[사고최초보고]",
            f"현  장  명: {nz(f.get('site_name'))}",
            f"보  고  자: {nz(f.get('reporter_name'))}",
            f"사고시각: {nz(f.get('accident_datetime_text'))}",
            f"사고장소: {nz(f.get('accident_place'))}",
            f"작업내용: {nz(f.get('work_content'))}",
            f"재  해  자: {nz(f.get('injured_person_name'))}",
            f"사고경위: {nz(f.get('accident_circumstance'))}",
            f"사고원인: {nz(f.get('accident_reason'))}",
            f"상해부위: {nz(f.get('injured_part'))}",
            f"조치사항: {nz(f.get('action_taken'))}",
            "위와 같이 보고드립니다.",
        ]
    )
    return {
        "composed_line": line,
        "fields": {k: (None if v is None else v) for k, v in f.items()},
        "message_raw": message_raw,
    }
