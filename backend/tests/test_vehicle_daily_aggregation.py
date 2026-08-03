from datetime import date
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from app.modules.safety_ledgers.workbook_export import build_vehicle_workbook


def test_original_template_aggregates_multiple_routes_on_same_day(tmp_path: Path):
    vehicle = SimpleNamespace(
        vehicle_name="Tucson",
        plate_number="181-8339",
        department="Safety",
        ownership_type="Company",
        drivers=[],
    )
    morning = SimpleNamespace(
        id=1,
        driven_on=date(2026, 7, 27),
        created_at=date(2026, 7, 27),
        driver_name="Jung",
        use_type="1.commute",
        trip_km=35,
        purpose="HQ",
    )
    afternoon = SimpleNamespace(
        id=2,
        driven_on=date(2026, 7, 27),
        created_at=date(2026, 7, 27),
        driver_name="Park",
        use_type="3.business",
        trip_km=43,
        purpose="Park home",
    )
    template_path = (
        Path(__file__).parents[1]
        / "app"
        / "modules"
        / "safety_ledgers"
        / "templates"
        / "company-vehicle-template.xlsx"
    )

    output = build_vehicle_workbook(
        vehicle,
        [morning, afternoon],
        tmp_path / "vehicle.xlsx",
        template_path=template_path,
    )

    sheet = load_workbook(output, data_only=False)["7월"]
    assert sheet["E37"].value == "Jung / Park"
    assert sheet["F37"].value == "3.업무용"
    assert sheet["G37"].value == 78
    assert sheet["H37"].value == "HQ / Park home"
