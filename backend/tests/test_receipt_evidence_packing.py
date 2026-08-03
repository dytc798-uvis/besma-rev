from datetime import date
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
from PIL import Image

from app.modules.safety_ledgers.workbook_export import build_card_workbook


def test_receipt_evidence_packs_two_or_three_receipts_per_a4_page(tmp_path: Path):
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
        tmp_path / "evidence.xlsx",
        receipt_storage_root=tmp_path,
        include_receipt_evidence=True,
    )

    book = load_workbook(output, data_only=False)
    evidence_sheets = [sheet for sheet in book.worksheets if sheet.title.startswith("영수증")]
    assert len(evidence_sheets) == 2
    assert sorted(len(sheet._images) for sheet in evidence_sheets) == [2, 3]
    assert all(sheet.page_setup.paperSize == 9 for sheet in evidence_sheets)
    assert all(sheet.page_setup.fitToWidth == 1 for sheet in evidence_sheets)
    two_receipt_sheet = next(sheet for sheet in evidence_sheets if len(sheet._images) == 2)
    assert [image.anchor._from.col for image in two_receipt_sheet._images] == [0, 4]
