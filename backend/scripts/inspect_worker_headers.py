from pathlib import Path

import xlrd


def main() -> None:
    base = Path("d:/besma-rev/backend")
    files = [
        "docs/sample/worker_import/raw/사원리스트_20260318084600.xls",
        "docs/sample/worker_import/raw/일용직사원리스트_20260318083047.xls",
    ]
    for name in files:
        p = base / name
        wb = xlrd.open_workbook(p)
        sh = wb.sheet_by_index(0)
        header = sh.row_values(0)
        print("FILE", name)
        print("HEADER", header)


if __name__ == "__main__":
    main()

