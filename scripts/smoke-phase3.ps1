# Phase 3 smoke tests: CLI, scan, upload-one (not found), upload-next, py_compile, summary.
# Usage: from repo root, .\scripts\smoke-phase3.ps1
# Optional: -UploadOneId <id> to run test 5 (expect exit 2 when publish fails / NO_VIDEO).

param(
    [int]$UploadOneId = 0   # If > 0, run upload-one $UploadOneId and expect exit 2 (fail-publish scenario).
)

$ErrorActionPreference = 'Stop'
$root = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { Get-Location }
Set-Location $root

function Assert-Summary { param($cmd, $okExpected)
    $path = Join-Path $root "logs\last_summary.json"
    if (-not (Test-Path $path)) { throw "Missing $path" }
    $raw = Get-Content $path -Raw -Encoding UTF8
    $s = $raw | ConvertFrom-Json
    if ($s.command -ne $cmd) { throw "Summary command: expected $cmd, got $($s.command)" }
    if ($null -ne $okExpected -and $s.ok -ne $okExpected) { throw "Summary ok: expected $okExpected, got $($s.ok)" }
    return $s
}

$failed = 0

# 1. CLI
try {
    python main.py --help | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
    Write-Host "[1/6] CLI --help OK"
} catch { Write-Host "[1/6] FAIL: $_"; $failed++ }

# 2. scan
try {
    $proc = Start-Process -FilePath "python" -ArgumentList "main.py","scan","--source","Z:\not-exists" -WorkingDirectory $root -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 1) { throw "expected exit 1, got $($proc.ExitCode)" }
    Assert-Summary -cmd "scan" -okExpected $false | Out-Null
    Write-Host "[2/6] scan (not-exists) OK"
} catch { Write-Host "[2/6] FAIL: $_"; $failed++ }

# 3. upload-one not found
try {
    $proc = Start-Process -FilePath "python" -ArgumentList "main.py","upload-one","999999999" -WorkingDirectory $root -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 1) { throw "expected exit 1, got $($proc.ExitCode)" }
    Assert-Summary -cmd "upload-one" -okExpected $false | Out-Null
    Write-Host "[3/6] upload-one (not found) OK"
} catch { Write-Host "[3/6] FAIL: $_"; $failed++ }

# 4. upload-next
try {
    $proc = Start-Process -FilePath "python" -ArgumentList "main.py","upload-next" -WorkingDirectory $root -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) { throw "expected exit 0, got $($proc.ExitCode)" }
    $s = Assert-Summary -cmd "upload-next"
    if ($s.stats -eq $null) { throw "missing stats" }
    Write-Host "[4/6] upload-next OK"
} catch { Write-Host "[4/6] FAIL: $_"; $failed++ }

# 5. (optional) upload-one partial
if ($UploadOneId -gt 0) {
    try {
        $proc = Start-Process -FilePath "python" -ArgumentList "main.py","upload-one",$UploadOneId -WorkingDirectory $root -Wait -PassThru -NoNewWindow
        if ($proc.ExitCode -ne 2) { throw "expected exit 2 (partial), got $($proc.ExitCode)" }
        $s = Get-Content (Join-Path $root "logs\last_summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($s.ok -ne $false -or $s.exit_code -ne 2) { throw "summary: expected ok=false, exit_code=2" }
        Write-Host "[5] upload-one partial (exit 2) OK"
    } catch { Write-Host "[5] FAIL: $_"; $failed++ }
} else {
    Write-Host "[5] skip (run with -UploadOneId <id> for fail-publish scenario)"
}

# 6. py_compile
try {
    python -m py_compile main.py src/models/content.py src/adapters/base.py src/adapters/destinations/vk.py src/adapters/sources/export_fs.py 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "py_compile failed" }
    Write-Host "[6/6] py_compile OK"
} catch { Write-Host "[6/6] FAIL: $_"; $failed++ }

if ($failed -gt 0) {
    Write-Host "`nFailed: $failed"
    exit 1
}
Write-Host "`nAll Phase 3 smoke tests passed."
