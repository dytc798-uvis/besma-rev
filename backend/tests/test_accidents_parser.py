# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from app.modules.accidents.parser import parse_initial_report_message

TEMPLATE_MESSAGE = """[사고최초보고]
현  장  명: 서울OO현장
보  고  자: 김철수
사고시각: 2026-04-19 14:30
사고장소: 2층 거푸집
작업내용: 철근 배근 작업
재  해  자: 홍길동
사고경위: 철근 배근 작업 중 발을 헛디딤
사고원인: 발판 미설치
상해부위: 발가락
조치사항: 현장 응급조치
위와 같이 보고드립니다."""


def test_parse_success_template_message():
    out = parse_initial_report_message(TEMPLATE_MESSAGE)
    assert out["parse_status"] == "success"
    f = out["fields"]
    assert f["site_name"] == "서울OO현장"
    assert f["reporter_name"] == "김철수"
    assert f["accident_datetime_text"] == "2026-04-19 14:30"
    assert f["accident_place"] == "2층 거푸집"
    assert f["work_content"] == "철근 배근 작업"
    assert f["injured_person_name"] == "홍길동"
    assert "발을 헛디딤" in (f["accident_circumstance"] or "")
    assert f["accident_reason"] == "발판 미설치"
    note = json.loads(out["parse_note"])
    assert note["template_marker_present"] is True


def test_parse_partial_template_with_missing_required_field():
    msg = """[사고최초보고]
현  장  명: 롯데바이오로직스
보  고  자: 홍길동
사고시각: 2026-04-19 14:10
사고장소: 지상 2층 전기실
작업내용: 케이블 포설 작업
재  해  자: 김철수
사고경위: 케이블 포설 중 미끄러짐
상해부위: 우측 손목
조치사항: 현장 응급조치
위와 같이 보고드립니다."""
    out = parse_initial_report_message(msg)
    assert out["parse_status"] == "partial"
    note = json.loads(out["parse_note"])
    assert "사고원인" in note["missing_required_fields"]


def test_parse_free_sentence_never_success_without_marker():
    msg = (
        "안녕하세요. 부산현장 이영희입니다. "
        "금일 3시 15분, 당 현장 내 창고에서 적재 작업을 수행하던 김작업자가 "
        "미끄러져 손목을 다쳤습니다."
    )
    out = parse_initial_report_message(msg)
    assert out["parse_status"] in {"partial", "failed"}
    assert out["parse_status"] != "success"
    note = json.loads(out["parse_note"])
    assert note["template_marker_present"] is False


def test_parse_failed_garbled():
    msg = "아무 내용도 없음"
    out = parse_initial_report_message(msg)
    assert out["parse_status"] == "failed"
