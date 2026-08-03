from datetime import date
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
from PIL import Image

from app.modules.safety_ledgers.workbook_export import build_card_workbook


def test_card_settlement_never_attaches_receipt_sheets(tmp_path: Path):
    expenses = []
    for index in range(1, 6):
        relative_path = Path("receipts") / f"receipt-{index}.jpg"
        image_path = tmp_path / relative_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (900, 1400), "white").save(image_path)
        expenses.append(
            SimpleNamespace(
                id=index,
                used_at=date(2026, 7, index),
                created_at=date(2026, 7, index),
                site_name="Site",
                merchant=f"Merchant {index}",
                amount=1000 * index,
                description="Meal",
                card_last4="6925",
                note=None,
                receipt_image_path=str(relative_path),
            )
        )

    output = build_card_workbook(
        expenses,
        tmp_path / "settlement.xlsx",
    )

    book = load_workbook(output, data_only=False)
    evidence_sheets = [sheet for sheet in book.worksheets if sheet.title.startswith("영수증")]
    assert evidence_sheets == []
    assert all(not sheet._images for sheet in book.worksheets)
