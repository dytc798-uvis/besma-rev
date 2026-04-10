from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.modules.safety_features.routes import (
    _extract_ledger_rows,
    _extract_worker_voice_rows,
    _extract_worker_voice_rows_from_csv,
)


def test_extract_ledger_rows_with_offset_header():
    wb = Workbook()
    ws = wb.active
    ws.append(["", "", "", "", "", "", "", "", "", "", "", ""])
    ws.append(["", "부적합 사항 관리대장(샘플)", "", "", "", "", "", "", "", "", "", ""])
    ws.append(["", "", "일자", "위치", "업체", "부적합 사항", "부적합 사항 상세", "부적합 사항 원인", "조치 계획 및 내용", "조치 후 사진", "조치일자", "조치 담당자"])
    ws.append(["", "1", "2025.07.11", "I/37", "OO업체", "난간", "세부내용", "원인", "난간 보강", "", "2025-07-11", "홍길동"])
    ws.append(["", "2", "2025.07.12", "I/38", "OO업체", "", "", "", "", "", "", ""])

    buff = BytesIO()
    wb.save(buff)
    rows = _extract_ledger_rows(buff.getvalue())

    assert len(rows) == 1
    assert rows[0]["issue_text"] == "난간"
    assert rows[0]["improvement_action"] == "난간 보강"
    assert rows[0]["improvement_owner"] == "홍길동"


def test_extract_worker_voice_rows_with_offset_header():
    wb = Workbook()
    ws = wb.active
    ws.append(["", "", "", ""])
    ws.append(["", "근로자 의견청취 관리대장", "", ""])
    ws.append(["번호", "근로자 성명", "생년월일", "휴대전화번호", "의견종류", "근로자 의견", "비고"])
    ws.append([1, "김철수", "900101", "010-1111-2222", "아차사고", "안전 통로 표지 개선 필요", ""])
    ws.append([2, "이영희", "", ""])

    buff = BytesIO()
    wb.save(buff)
    rows = _extract_worker_voice_rows(buff.getvalue())

    assert len(rows) == 1
    assert rows[0]["worker_name"] == "김철수"
    assert rows[0]["worker_birth_date"] == "900101"
    assert rows[0]["worker_phone_number"] == "010-1111-2222"
    assert rows[0]["opinion_kind"] == "아차사고"
    assert rows[0]["opinion_text"] == "안전 통로 표지 개선 필요"


def test_extract_worker_voice_rows_from_google_forms_csv():
    csv_text = """타임스탬프,근로자 성명,생년월일,휴대전화번호,의견종류,근로자 의견
2026. 4. 10 오후 5:00:00,홍길동,880101,010-3333-4444,유해위험요인발굴,작업구역 미끄럼 위험
"""
    rows = _extract_worker_voice_rows_from_csv(csv_text.encode("utf-8-sig"))
    assert len(rows) == 1
    assert rows[0]["worker_name"] == "홍길동"
    assert rows[0]["worker_birth_date"] == "880101"
    assert rows[0]["worker_phone_number"] == "010-3333-4444"
    assert rows[0]["opinion_kind"] == "유해위험요인발굴"
    assert rows[0]["opinion_text"] == "작업구역 미끄럼 위험"
