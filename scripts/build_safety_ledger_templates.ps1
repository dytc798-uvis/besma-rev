param(
    [Parameter(Mandatory = $true)][string]$LedgerRoot,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$cardSource = Get-ChildItem -LiteralPath $LedgerRoot -Recurse -File -Filter *.xlsx |
    Where-Object { $_.Length -eq 139904 } |
    Select-Object -First 1
$vehicleSource = Get-ChildItem -LiteralPath $LedgerRoot -Recurse -File -Filter *.xls |
    Where-Object { $_.Length -eq 129536 } |
    Select-Object -First 1
if (-not $cardSource -or -not $vehicleSource) {
    throw "The two source workbooks were not found."
}
$monthSuffix = [string][char]0xC6D4
$safetyDepartment = -join ([char[]](0xC548, 0xC804, 0xBCF4, 0xAC74, 0xC2E4))

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {
    $cardTarget = Join-Path $OutputDirectory "company-card-template.xlsx"
    Copy-Item -LiteralPath $cardSource.FullName -Destination $cardTarget -Force
    $templateBook = $excel.Workbooks.Open($cardTarget, 0, $false)
    $templateBook.Worksheets.Item(2).Delete()
    $sheet = $templateBook.Worksheets.Item(1)
    $sheet.Name = "template"
    $sheet.Range("B4:G44").ClearContents()
    $sheet.Range("A4").Value2 = 1
    for ($row = 5; $row -le 44; $row++) {
        $sheet.Range("A$row").Formula = "=ROW()-3"
    }
    $sheet.Range("E45").Formula = "=SUM(E4:E44)"
    $templateBook.Save()
    $templateBook.Close($false)

    $vehicleTarget = Join-Path $OutputDirectory "company-vehicle-template.xlsx"
    $templateBook = $excel.Workbooks.Open($vehicleSource.FullName, 0, $true)
    $templateBook.SaveAs($vehicleTarget, 51)
    for ($index = $templateBook.Worksheets.Count; $index -ge 1; $index--) {
        if ($index -ne 4) {
            $templateBook.Worksheets.Item($index).Delete()
        }
    }
    $sourceSheet = $templateBook.Worksheets.Item(1)
    for ($copyIndex = 2; $copyIndex -le 6; $copyIndex++) {
        $sourceSheet.Copy([Type]::Missing, $templateBook.Worksheets.Item($templateBook.Worksheets.Count))
    }
    for ($month = 7; $month -le 12; $month++) {
        $sheetIndex = $month - 6
        $sheet = $templateBook.Worksheets.Item($sheetIndex)
        $sheet.Name = "${month}${monthSuffix}"
        $sheet.Range("G7").ClearContents()
        $sheet.Range("E11:H41").ClearContents()
        for ($day = 1; $day -le 31; $day++) {
            $row = 10 + $day
            try {
                $validDate = Get-Date -Year 2026 -Month $month -Day $day -ErrorAction Stop
                $sheet.Range("A$row").Value2 = 2026
                $sheet.Range("B$row").Value2 = $month
                $sheet.Range("C$row").Value2 = $day
                $sheet.Range("D$row").Value2 = $safetyDepartment
            } catch {
                $sheet.Range("A${row}:H${row}").ClearContents()
            }
        }
        $sheet.Range("G42").Formula = "=SUM(G11:G41)"
    }
    $templateBook.Save()
    $templateBook.Close($false)
} finally {
    $excel.Quit()
    [Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}

Get-ChildItem -LiteralPath $OutputDirectory -File | Select-Object Name, Length, LastWriteTime
