from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Literal

import httpx

from app.config.settings import settings


ExtractionKind = Literal["receipt", "odometer"]


def _schema(kind: ExtractionKind) -> dict[str, Any]:
    if kind == "odometer":
        return {
            "type": "object",
            "properties": {
                "odometer_km": {"type": ["integer", "null"]},
                "trip_km": {"type": ["number", "null"]},
                "reading_type": {
                    "type": "string",
                    "enum": ["odometer", "current_drive", "after_refuel", "unknown"],
                },
                "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["odometer_km", "trip_km", "reading_type", "confidence"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "transaction_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
            "transaction_time": {"type": ["string", "null"], "description": "HH:MM, 24-hour time"},
            "merchant": {"type": ["string", "null"]},
            "amount": {"type": ["integer", "null"], "description": "total paid amount in KRW"},
            "card_last4": {"type": ["string", "null"], "description": "last four digits only"},
            "description": {"type": ["string", "null"]},
            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": [
            "transaction_date",
            "transaction_time",
            "merchant",
            "amount",
            "card_last4",
            "description",
            "confidence",
        ],
        "additionalProperties": False,
    }


def _prompt(kind: ExtractionKind) -> str:
    if kind == "odometer":
        return (
            "한국 차량 계기판 사진을 읽으세요. 이 차량은 화면 맨 아래의 작은 km 숫자가 "
            "누적 주행거리(ODO)이므로 화면 제목과 관계없이 반드시 그 값을 odometer_km로 반환하세요. "
            "가운데 '현 주행 정보', '주유 후 정보', '누적 정보' 아래의 거리는 trip_km로만 구분하세요. "
            "주행가능거리(연료 아이콘 옆 km), 내비 목적지까지 거리, 속도는 제외하세요. "
            "reading_type은 가운데 화면 제목에 맞춰 반환하고, 숫자가 불명확하면 null과 낮은 confidence를 반환하세요."
        )
    return (
        "사진이 90도 또는 180도 회전되어 있어도 영수증 글자가 바로 보이도록 방향을 판단한 뒤 읽으세요. "
        "한국 법인카드 영수증에서 승인/거래 일자와 시간, 가맹점명, 최종 결제금액, "
        "마스킹된 카드번호의 마지막 4자리, 짧은 사용내역을 추출하세요. "
        "사용내역은 가능한 경우 주유비, 중식비, 석식비, 회식비, 주차비, 통행료, 숙박비 중 하나로 분류하세요. "
        "가맹점명이나 품목에 주유소, 휘발유, 경유가 있으면 주유비입니다. "
        "추측하지 말고 읽히지 않는 값은 null로 반환하세요."
    )


def _output_text(payload: dict[str, Any]) -> str:
    for output in payload.get("output") or []:
        if output.get("type") != "message":
            continue
        for content in output.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
    raise ValueError("OpenAI response did not contain output_text")


def extract_image(path: Path, media_type: str, kind: ExtractionKind) -> dict[str, Any] | None:
    """Return structured fields, or None when the optional API integration is disabled."""
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        return None

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    body = {
        "model": settings.safety_ledger_vision_model,
        "store": False,
        "reasoning": {"effort": "low"},
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _prompt(kind)},
                    {
                        "type": "input_image",
                        "image_url": f"data:{media_type};base64,{encoded}",
                        "detail": "high",
                    },
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": f"safety_{kind}_extraction",
                "strict": True,
                "schema": _schema(kind),
            }
        },
        "max_output_tokens": 500,
    }
    with httpx.Client(timeout=settings.safety_ledger_vision_timeout_seconds) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
    return json.loads(_output_text(response.json()))
