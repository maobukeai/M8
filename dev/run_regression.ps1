[CmdletBinding()]
param(
    [string]$Blender = $env:BLENDER_BIN,
    [switch]$Foreground,
    [switch]$KeepUserPrefs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$RegressionScript = Join-Path $ScriptDir "run_regression.py"

if ([string]::IsNullOrWhiteSpace($Blender)) {
    $Blender = "blender"
}

$BlenderCommand = Get-Command $Blender -ErrorAction SilentlyContinue
if ($BlenderCommand) {
    $Blender = $BlenderCommand.Source
}
elseif (Test-Path -LiteralPath $Blender) {
    $Blender = (Resolve-Path -LiteralPath $Blender).Path
}
else {
    Write-Error "Blender executable not found. Pass -Blender 'C:\path\to\blender.exe' or set BLENDER_BIN."
    exit 127
}

$BlenderArgs = @()
if (-not $Foreground) {
    $BlenderArgs += "--background"
}
if (-not $KeepUserPrefs) {
    $BlenderArgs += "--factory-startup"
}
$BlenderArgs += @("--python", $RegressionScript)

Push-Location $Root
try {
    & $Blender @BlenderArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
