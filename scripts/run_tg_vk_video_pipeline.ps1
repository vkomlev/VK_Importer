param(
  [ValidateSet('daily','backfill','manual')]
  [string]$Mode = 'manual',
  [string]$Since,
  [string]$Until,
  [int]$BatchCount = 200,
  [double]$DelaySec = 5,
  [int]$MaxRetries = 3,
  [switch]$SkipParse,
  [switch]$SkipPreStep,
  [string]$SkipFilesList = 'logs\skip_files.txt',
  [string]$SkipIdsList = 'logs\skip_ids.txt'
)

$ErrorActionPreference = 'Stop'
$vkRoot = 'D:\work\VK_Importer'
$tgRoot = 'D:\work\TG_Parser'
$vkPy = Join-Path $vkRoot 'venv\Scripts\python.exe'
$tgPy = Join-Path $tgRoot '.venv\Scripts\python.exe'

$channels = @(
  'https://t.me/cyberguru_ege',
  'https://t.me/CyberGuruPython',
  'https://t.me/InfOGELihgt',
  'https://t.me/CyberGuruKomlev',
  'https://t.me/cyberguru_excel',
  'https://t.me/SQLPandasBI',
  'https://t.me/AlgorithmPythonStruct'
)

function Invoke-Step($title, [scriptblock]$sb) {
  Write-Host "`n=== $title ==="
  & $sb
}

function Run-Cmd($exe, $argList, $cwd) {
  Push-Location $cwd
  try {
    & $exe @argList
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $exe $($argList -join ' ')" }
  }
  finally { Pop-Location }
}

if (-not $Since) {
  if ($Mode -eq 'daily') {
    $Since = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
  } elseif ($Mode -eq 'backfill') {
    throw 'For backfill set -Since YYYY-MM-DD (and optional -Until).'
  } else {
    $Since = (Get-Date).ToString('yyyy-MM-dd')
  }
}
if (-not $Until) { $Until = (Get-Date).ToString('yyyy-MM-dd') }

Invoke-Step 'Preflight VK stats' {
  Run-Cmd $vkPy @('main.py','stats') $vkRoot
}

if (-not $SkipParse) {
  Invoke-Step "TG parse ($Mode)" {
    foreach ($ch in $channels) {
      if ($Mode -eq 'backfill') {
        Run-Cmd $tgPy @('telegram_parser_skill.py','parse','--channel',$ch,'--date-from',$Since,'--date-to',$Until,'--output-dir','D:\work\TG_Parser\out') $tgRoot
      } else {
        Run-Cmd $tgPy @('telegram_parser_skill.py','parse','--channel',$ch,'--output-dir','D:\work\TG_Parser\out') $tgRoot
      }
    }
  }
}

Invoke-Step 'VK ingest scan -s mapped' {
  Run-Cmd $vkPy @('main.py','scan','-s','mapped','--since',$Since,'--until',$Until) $vkRoot
}

if (-not $SkipPreStep) {
  Invoke-Step 'Apply skip pre-step' {
    $skipFilesPath = Join-Path $vkRoot $SkipFilesList
    $skipIdsPath = Join-Path $vkRoot $SkipIdsList

    if (Test-Path $skipFilesPath) {
      Write-Host "Applying skip by --file-from: $skipFilesPath"
      Run-Cmd $vkPy @('main.py','skip','--file-from',$skipFilesPath) $vkRoot
    } else {
      Write-Host "Skip files list not found (ok): $skipFilesPath"
    }

    if (Test-Path $skipIdsPath) {
      $raw = Get-Content $skipIdsPath -Encoding UTF8
      $ids = @()
      foreach ($line in $raw) {
        $clean = ($line -replace '#.*$','').Trim()
        if (-not $clean) { continue }
        $parts = $clean -split '[,\s]+'
        foreach ($p in $parts) {
          if ($p -match '^\d+$') { $ids += [int]$p }
        }
      }
      $ids = $ids | Select-Object -Unique
      if ($ids.Count -gt 0) {
        $args = @('main.py','skip')
        foreach ($id in $ids) {
          $args += '--id'
          $args += "$id"
        }
        Write-Host "Applying skip by ids: $($ids.Count)"
        Run-Cmd $vkPy $args $vkRoot
      } else {
        Write-Host "Skip ids list has no valid IDs (ok): $skipIdsPath"
      }
    } else {
      Write-Host "Skip IDs list not found (ok): $skipIdsPath"
    }
  }
}

# Build eligible IDs in DB with policy:
# - only not uploaded
# - respect run window
# - keep global #noexport skip
# - no channel/date hardcoded exclusions (now handled by built-in skip workflow)
Invoke-Step 'Select eligible IDs by policy' {
  $sql = @"
import sqlite3
con=sqlite3.connect('videos.db')
cur=con.cursor()
since='$Since'
until='$Until'
rows=cur.execute('''
SELECT id, channel, date
FROM videos
WHERE uploaded=0
  AND date(date) >= date(?)
  AND date(date) <= date(?)
  AND (description IS NULL OR lower(description) NOT LIKE '%#noexport%')
ORDER BY date ASC, id ASC
''',(since, until)).fetchall()
print('\n'.join(str(r[0]) for r in rows))
print(f'__COUNT__={len(rows)}')
con.close()
"@
  $out = @'
'@ + $sql
  $result = $out | & $vkPy -
  if ($LASTEXITCODE -ne 0) { throw 'failed to query eligible ids' }
  $script:EligibleIds = @()
  foreach ($line in $result) {
    if ($line -match '^__COUNT__=') { $script:EligibleCount = [int]($line -replace '^__COUNT__=',''); continue }
    if ($line -match '^\d+$') { $script:EligibleIds += [int]$line }
  }
  Write-Host "Eligible by policy: $($script:EligibleCount)"
}

Invoke-Step 'Publish eligible IDs' {
  $published = 0
  $failed = 0
  $total = [Math]::Min($EligibleIds.Count, $BatchCount)
  for ($i=0; $i -lt $total; $i++) {
    $id = $EligibleIds[$i]
    try {
      Run-Cmd $vkPy @('main.py','upload-one',$id,'--delay',$DelaySec,'--max-retries',$MaxRetries) $vkRoot
      $published++
    } catch {
      Write-Host "Failed ID ${id}: $($_.Exception.Message)"
      $failed++
    }
  }
  $script:Published = $published
  $script:Failed = $failed
}

Invoke-Step 'Final stats' {
  Run-Cmd $vkPy @('main.py','stats') $vkRoot
  Write-Host "`nPipeline summary: mode=$Mode since=$Since until=$Until eligible=$EligibleCount published=$Published failed=$Failed"
}
