[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Database = "",
    [string]$Reports = "",
    [switch]$SkipGateway
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $Database) {
    $Database = Join-Path $ProjectRoot "var\ledger.sqlite"
}
if (-not $Reports) {
    $Reports = Join-Path $ProjectRoot "reports"
}
$Database = [System.IO.Path]::GetFullPath($Database)
$Reports = [System.IO.Path]::GetFullPath($Reports)
$Staging = Join-Path $ProjectRoot "var\report-staging"

function Assert-InProject {
    param([string]$Path)
    $rootPrefix = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\") + "\"
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path must stay inside the project: $fullPath"
    }
    return $fullPath
}

function Invoke-Python {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $Python $($Arguments -join ' ')"
    }
}

$Database = Assert-InProject $Database
$Reports = Assert-InProject $Reports
$Staging = Assert-InProject $Staging
$OldPythonPath = $env:PYTHONPATH

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Database) | Out-Null

    Write-Host "[1/4] Running tests"
    Invoke-Python @("-m", "unittest", "discover", "-s", "tests", "-v")

    Write-Host "[2/4] Scanning local sources"
    $scanArguments = @(
        "-m", "agent_token_ledger",
        "--db", $Database,
        "scan",
        "--work-dir", (Join-Path $ProjectRoot "var"),
        "--json"
    )
    if ($SkipGateway) {
        $scanArguments += "--skip-gateway"
    }
    Invoke-Python $scanArguments

    Write-Host "[3/4] Validating latest scan"
    Invoke-Python @(
        "-m", "agent_token_ledger",
        "--db", $Database,
        "validate",
        "--json"
    )

    Write-Host "[4/4] Exporting reports"
    if (Test-Path -LiteralPath $Staging) {
        Remove-Item -LiteralPath $Staging -Recurse -Force
    }
    Invoke-Python @(
        "-m", "agent_token_ledger",
        "--db", $Database,
        "export",
        "--output-dir", $Staging,
        "--work-dir", (Join-Path $ProjectRoot "var"),
        "--json"
    )

    if (-not (Test-Path -LiteralPath (Join-Path $Staging "manifest.sha256"))) {
        throw "Export completed without manifest.sha256"
    }
    if (Test-Path -LiteralPath $Reports) {
        Remove-Item -LiteralPath $Reports -Recurse -Force
    }
    Move-Item -LiteralPath $Staging -Destination $Reports
    Write-Host "Run complete."
    Write-Host "Database: $Database"
    Write-Host "Reports:  $Reports"
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
