[CmdletBinding()]
param(
    [string]$Python = "python",
    [int]$Port = 8765,
    [int]$RefreshSeconds = 30,
    [switch]$NoBrowser,
    [switch]$SkipGateway
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$OldPythonPath = $env:PYTHONPATH

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    $Arguments = @(
        "-m", "agent_token_ledger.app",
        "--port", $Port,
        "--refresh-seconds", $RefreshSeconds
    )
    if ($NoBrowser) {
        $Arguments += "--no-browser"
    }
    if ($SkipGateway) {
        $Arguments += "--skip-gateway"
    }
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    if ($null -eq $OldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $OldPythonPath
    }
    Pop-Location
}
