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

$pipelineLogDir = Join-Path $vkRoot 'logs'
New-Item -ItemType Directory -Path $pipelineLogDir -Force | Out-Null
$pipelineLogFile = Join-Path $pipelineLogDir ("pipeline_run_" + (Get-Date -Format 'yyyy-MM-dd_HH-mm-ss') + ".log")

function Write-RunLog([string]$message, [string]$level = 'INFO') {
  $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
  $line = "[$ts] [$level] $message"
  Add-Content -Path $pipelineLogFile -Value $line -Encoding UTF8
  Write-Host $line
}

function Get-ActivePipelineRuns {
  $all = @(Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -eq 'powershell.exe' -and
      $_.CommandLine -like '*run_tg_vk_video_pipeline.ps1*'
    })
  if ($all.Count -eq 0) { return @() }

  # Исключаем текущий powershell-процесс скрипта
  return @($all | Where-Object { $_.ProcessId -ne $PID })
}

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
  Write-RunLog "=== $title ==="
  & $sb
}

function Run-Cmd($exe, $argList, $cwd) {
  Write-RunLog ("Run-Cmd: " + $exe + " " + ($argList -join ' '))
  Push-Location $cwd
  try {
    & $exe @argList
    if ($LASTEXITCODE -ne 0) {
      Write-RunLog ("Command failed ($LASTEXITCODE): $exe $($argList -join ' ')") 'ERROR'
      throw "Command failed ($LASTEXITCODE): $exe $($argList -join ' ')"
    }
  }
  finally { Pop-Location }
}

function Get-ActiveTgParseProcesses {
  # РќР° Windows venv\Scripts\python.exe РјРѕР¶РµС‚ РґР°РІР°С‚СЊ РїР°СЂСѓ РїСЂРѕС†РµСЃСЃРѕРІ (launcher + child).
  # РЎС‡РёС‚Р°РµРј С‚РѕР»СЊРєРѕ root-РїСЂРѕС†РµСЃСЃС‹ parse (С‡РµР№ ParentProcessId РЅРµ СѓРєР°Р·С‹РІР°РµС‚ РЅР° РґСЂСѓРіРѕР№ parse-РїСЂРѕС†РµСЃСЃ).
  $all = @(Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -eq 'python.exe' -and
      $_.CommandLine -like '*telegram_parser_skill.py parse*'
    })

  if ($all.Count -eq 0) { return @() }

  $ids = @($all | ForEach-Object { $_.ProcessId })
  return @($all | Where-Object { $ids -notcontains $_.ParentProcessId })
}

function Run-TgParseCmd($exe, $argList, $cwd, $MaxAttempts = 2) {
  $active = @(Get-ActiveTgParseProcesses)
  Write-RunLog ("TG parse active root processes before start: " + $active.Count)
  if ($active.Count -gt 0) {
    Write-RunLog ("Detected active TG parse process(es): " + $active.Count + ". Abort to avoid sqlite lock.") 'ERROR'
    throw "Detected active TG parse process(es): $($active.Count). Abort to avoid sqlite lock."
  }

  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    Push-Location $cwd
    try {
      $output = & $exe @argList 2>&1
      $exitCode = $LASTEXITCODE
    }
    finally { Pop-Location }

    if ($output) { $output | ForEach-Object { Write-Host $_ } }

    if ($exitCode -eq 0 -or $exitCode -eq 2) {
      if ($exitCode -eq 2) {
        Write-RunLog "TG parse completed with partial status (exit 2). Continue pipeline." 'WARN'
      }
      return
    }

    $joined = ($output | Out-String)
    $isDbLocked = $joined -match 'database is locked'

    if ($isDbLocked -and $attempt -lt $MaxAttempts) {
      Write-RunLog "TG parse sqlite lock detected. Retry in 20s (attempt $attempt/$MaxAttempts)..." 'WARN'
      Start-Sleep -Seconds 20

      $stillActive = @(Get-ActiveTgParseProcesses)
      Write-RunLog ("TG parse active root processes before retry: " + $stillActive.Count)
      if ($stillActive.Count -gt 0) {
        Write-RunLog ("Retry blocked: active TG parse process(es) still running: " + $stillActive.Count) 'ERROR'
        throw "Retry blocked: active TG parse process(es) still running: $($stillActive.Count)"
      }
      continue
    }

    throw "Command failed ($exitCode): $exe $($argList -join ' ')"
  }
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
Write-RunLog ("Pipeline started: mode=$Mode since=$Since until=$Until batch=$BatchCount delay=$DelaySec retries=$MaxRetries")
Write-RunLog ("Pipeline log file: $pipelineLogFile")

$otherRuns = @(Get-ActivePipelineRuns)
if ($otherRuns.Count -gt 0) {
  Write-RunLog ("Another pipeline run is already active ($($otherRuns.Count)). Skip current start to avoid overlap.") 'WARN'
  exit 0
}

Invoke-Step 'Preflight VK stats' {
  Run-Cmd $vkPy @('main.py','stats') $vkRoot
}

if (-not $SkipParse) {
  Invoke-Step "TG parse ($Mode)" {
    foreach ($ch in $channels) {
      if ($Mode -eq 'backfill') {
        Run-TgParseCmd $tgPy @('telegram_parser_skill.py','parse','--channel',$ch,'--date-from',$Since,'--date-to',$Until,'--output-dir','D:\work\TG_Parser\out') $tgRoot
      } else {
        Run-TgParseCmd $tgPy @('telegram_parser_skill.py','parse','--channel',$ch,'--output-dir','D:\work\TG_Parser\out') $tgRoot
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
  $dbPath = Join-Path $vkRoot 'videos.db'
  try { $dbPathAbs = (Resolve-Path -LiteralPath $vkRoot -ErrorAction Stop).Path } catch { $dbPathAbs = $vkRoot }
  $dbPathAbs = Join-Path $dbPathAbs 'videos.db'
  $dbExists = Test-Path -LiteralPath $dbPathAbs
  Write-RunLog ("pwd=" + (Get-Location).Path + "; db_path=" + $dbPathAbs + "; db_exists=" + $dbExists)
  $env:VK_IMPORTER_DB = $dbPathAbs
  Push-Location $vkRoot
  try {
    $sql = @"
import os
import sys
import sqlite3

db_path = os.environ.get('VK_IMPORTER_DB', 'videos.db')
db_path_abs = os.path.abspath(db_path)
uri = 'file:' + db_path_abs.replace(chr(92), '/') + '?mode=rw'
try:
    con = sqlite3.connect(uri, uri=True)
except sqlite3.OperationalError as e:
    sys.stderr.write('DB path invalid or cannot open in rw mode: ' + db_path_abs + ' cwd=' + os.getcwd() + ' err=' + str(e) + chr(10))
    sys.exit(1)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos'")
if not cur.fetchone():
    sys.stderr.write('Preflight failed: table videos not found. db_path=' + db_path_abs + ' cwd=' + os.getcwd() + chr(10))
    con.close()
    sys.exit(1)
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
  } finally {
    Pop-Location
    Remove-Item Env:VK_IMPORTER_DB -ErrorAction SilentlyContinue
  }
}

Invoke-Step 'Preflight VK video' {
  Run-Cmd $vkPy @('main.py','vk-preflight') $vkRoot
}

Invoke-Step 'Publish eligible IDs' {
  $published = 0
  $failed = 0
  $total = [Math]::Min($EligibleIds.Count, $BatchCount)
  for ($i=0; $i -lt $total; $i++) {
    $id = $EligibleIds[$i]
    Push-Location $vkRoot
    try {
      & $vkPy main.py upload-one $id --delay $DelaySec --max-retries $MaxRetries
      $exit = $LASTEXITCODE
    } finally {
      Pop-Location
    }
    if ($exit -eq 3) {
      Write-RunLog 'VK API 1051: stop batch (method unavailable for current profile/token)' 'ERROR'
      throw 'VK API 1051: method unavailable for current profile/token. Re-issue token with video permission.'
    }
    if ($exit -eq 0) {
      $published++
    } else {
      Write-Host "Failed ID ${id}: exit $exit"
      $failed++
    }
  }
  $script:Published = $published
  $script:Failed = $failed
}

Invoke-Step 'Final stats' {
  Run-Cmd $vkPy @('main.py','stats') $vkRoot
  Write-RunLog ("Pipeline summary: mode=$Mode since=$Since until=$Until eligible=$EligibleCount published=$Published failed=$Failed")
}
