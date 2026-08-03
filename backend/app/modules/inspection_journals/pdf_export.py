from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image as PilImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.inspection_journals.models import InspectionJournal, InspectionJournalPhoto


_FONT = "HYSMyeongJo-Medium"
try:
    pdfmetrics.getFont(_FONT)
except KeyError:
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT))


def _paragraph(value: str | None, style: ParagraphStyle) -> Paragraph:
    safe = escape((value or "").strip()).replace("\n", "<br/>") or "-"
    return Paragraph(safe, style)


def _approval_table(style: ParagraphStyle) -> Table:
    labels = ["결재", "담당", "소장", "전무", "대표"]
    table = Table(
        [[Paragraph(label, style) for label in labels], ["", "", "", "", ""]],
        colWidths=[13 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm],
        rowHeights=[8 * mm, 18 * mm],
        hAlign="RIGHT",
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF2")),
            ]
        )
    )
    return table


def _edited_photo(path: Path, photo: InspectionJournalPhoto) -> tuple[BytesIO, int, int]:
    with PilImage.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    left = max(0.0, min(0.95, float(photo.crop_left or 0)))
    top = max(0.0, min(0.95, float(photo.crop_top or 0)))
    right = max(0.0, min(0.95, float(photo.crop_right or 0)))
    bottom = max(0.0, min(0.95, float(photo.crop_bottom or 0)))
    if left + right >= 0.99:
        left = right = 0
    if top + bottom >= 0.99:
        top = bottom = 0
    box = (
        round(image.width * left),
        round(image.height * top),
        max(round(image.width * left) + 1, round(image.width * (1 - right))),
        max(round(image.height * top) + 1, round(image.height * (1 - bottom))),
    )
    image = image.crop(box)
    rotation = int(photo.rotation_degrees or 0) % 360
    if rotation:
        image = image.rotate(-rotation, expand=True)
    image.thumbnail((1800, 1800), PilImage.Resampling.LANCZOS)
    stream = BytesIO()
    image.save(stream, "JPEG", quality=91, optimize=True)
    stream.seek(0)
    return stream, image.width, image.height


def build_inspection_journal_pdf(
    journal: InspectionJournal,
    output_path: Path,
    storage_root: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"{journal.site_name} {journal.subject} 점검일지",
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "KoreanNormal",
        parent=styles["Normal"],
        fontName=_FONT,
        fontSize=9,
        leading=13,
        wordWrap="CJK",
    )
    center = ParagraphStyle("KoreanCenter", parent=normal, alignment=TA_CENTER, fontSize=8)
    title_style = ParagraphStyle(
        "KoreanTitle",
        parent=normal,
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        spaceAfter=4 * mm,
    )
    heading = ParagraphStyle(
        "KoreanHeading",
        parent=normal,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#164E63"),
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )

    story = [
        _approval_table(center),
        Spacer(1, 4 * mm),
        Paragraph("현장 안전보건 점검·교육일지", title_style),
    ]
    details = [
        ["현장명", journal.site_name, "점검일", journal.inspected_on.isoformat()],
        ["점검·교육 제목", journal.subject, "시간", journal.time_text or "-"],
        ["장소", journal.location or "-", "교육 구분", journal.training_label],
        ["강사", journal.instructor_name or "-", "소속", journal.instructor_affiliation or "-"],
        ["참석자", journal.attendees or "-", "작성자", journal.created_by_name],
    ]
    detail_table = Table(
        [[Paragraph(escape(str(cell)), normal) for cell in row] for row in details],
        colWidths=[25 * mm, 68 * mm, 23 * mm, 64 * mm],
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#7C8A96")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF5F6")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EEF5F6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            detail_table,
            Paragraph("필수 법정 교육내용", heading),
            _paragraph(journal.legal_content, normal),
        ]
    )
    if journal.additional_content:
        story.extend([Paragraph("추가 교육내용", heading), _paragraph(journal.additional_content, normal)])
    if journal.special_notes:
        story.extend([Paragraph("특기사항 및 교육 효과성", heading), _paragraph(journal.special_notes, normal)])

    photo_rows = []
    streams: list[BytesIO] = []
    for photo in journal.photos:
        path = storage_root / photo.image_path
        if not path.is_file():
            continue
        try:
            stream, width, height = _edited_photo(path, photo)
        except (OSError, ValueError):
            continue
        streams.append(stream)
        max_width, max_height = 82 * mm, 65 * mm
        scale = min(max_width / width, max_height / height)
        image = Image(stream, width=width * scale, height=height * scale)
        caption = Paragraph(escape(photo.caption or photo.original_name), center)
        photo_rows.append(Table([[image], [caption]], colWidths=[86 * mm]))

    if photo_rows:
        story.extend([PageBreak(), Paragraph("점검·교육 사진", title_style)])
        for index in range(0, len(photo_rows), 2):
            pair = photo_rows[index : index + 2]
            if len(pair) == 1:
                pair.append("")
            table = Table([pair], colWidths=[88 * mm, 88 * mm], rowHeights=[76 * mm])
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAB5BD")),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.extend([table, Spacer(1, 3 * mm)])

    doc.build(story)
    for stream in streams:
        stream.close()
    return output_path
