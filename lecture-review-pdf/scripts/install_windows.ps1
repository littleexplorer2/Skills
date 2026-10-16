[CmdletBinding()]
param([switch]$CheckOnly, [switch]$NoInstallSkill)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath;$env:Path"
}
function Find-Python {
    $candidates = @()
    if ($env:LECTURE_REVIEW_PYTHON) { $candidates += $env:LECTURE_REVIEW_PYTHON }
    $candidates += (Join-Path $env:LOCALAPPDATA 'LectureReviewPDF\venv\Scripts\python.exe')
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    foreach ($name in @('python3.exe', 'python.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            & $candidate -c 'import sys; raise SystemExit(sys.version_info < (3,10))' 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Exe = $candidate; Prefix = @() } }
        } catch { }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            & $launcher.Source -3 -c 'import sys; raise SystemExit(sys.version_info < (3,10))' 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Exe = $launcher.Source; Prefix = @('-3') } }
        } catch { }
    }
    return $null
}
function Find-XeLaTeX {
    $candidates = @()
    if ($env:LECTURE_REVIEW_XELATEX) { $candidates += $env:LECTURE_REVIEW_XELATEX }
    $cmd = Get-Command xelatex.exe -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\MiKTeX\miktex\bin\x64\xelatex.exe')
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles 'MiKTeX\miktex\bin\x64\xelatex.exe') }
    $texLiveRoot = Join-Path "$env:SystemDrive\" 'texlive'
    if (Test-Path -LiteralPath $texLiveRoot) {
        $candidates += @(Get-ChildItem -LiteralPath $texLiveRoot -Directory | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'bin\windows\xelatex.exe' })
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}
function Install-WithWinget([string]$Id) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'winget is missing. Install Microsoft App Installer, or install Python 3.10+ and MiKTeX from their official websites, then rerun.'
    }
    & $winget.Source install --exact --id $Id --source winget --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "winget failed for $Id (exit $LASTEXITCODE). Resolve its reported error and rerun; existing environments were not removed." }
    Refresh-ProcessPath
}
try {
    if ($env:OS -ne 'Windows_NT') { throw 'This installer is for Windows.' }
    $python = Find-Python
    if (-not $python) {
        if ($CheckOnly) { throw 'Python 3.10+ missing; check-only installed nothing.' }
        Install-WithWinget 'Python.Python.3.12'
        $python = Find-Python
        if (-not $python) { throw 'Python was installed but cannot be located. Reopen Terminal and rerun.' }
    }
    $engine = Find-XeLaTeX
    if (-not $engine -and -not $CheckOnly) {
        Install-WithWinget 'MiKTeX.MiKTeX'
        $engine = Find-XeLaTeX
        if (-not $engine) { throw 'MiKTeX was installed but XeLaTeX cannot be located. Reopen Terminal and rerun.' }
    }
    if ($engine) {
        $env:LECTURE_REVIEW_XELATEX = $engine
        $env:Path = "$(Split-Path -Parent $engine);$env:Path"
    }
    $setupArgs = @($python.Prefix) + @((Join-Path $PSScriptRoot 'install_runtime.py'))
    if ($CheckOnly) { $setupArgs += '--check-only' }
    if ($NoInstallSkill) { $setupArgs += '--no-install-skill' }
    & $python.Exe @setupArgs
    if ($LASTEXITCODE -ne 0) { throw "Runtime setup failed (exit $LASTEXITCODE)." }
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
