[CmdletBinding()]
param(
    [switch]$SkipRunAll,
    [string]$Python = "python",
    [string]$OutputsRoot = "",
    [string]$Version = "",
    [string]$PackageName = "agent-token-ledger"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $OutputsRoot) {
    $OutputsRoot = Join-Path $ProjectRoot "..\..\outputs"
}
$OutputsRoot = [System.IO.Path]::GetFullPath($OutputsRoot)
$Db = Join-Path $ProjectRoot "var\ledger.sqlite"
$Reports = Join-Path $ProjectRoot "reports"
$OldPythonPath = $env:PYTHONPATH

function Assert-InOutputs {
    param([string]$Path)
    $rootPrefix = [System.IO.Path]::GetFullPath($OutputsRoot).TrimEnd("\") + "\"
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path must stay inside outputs: $fullPath"
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

function Get-ProjectVersion {
    $initFile = Join-Path $ProjectRoot "src\agent_token_ledger\__init__.py"
    $content = Get-Content -LiteralPath $initFile -Raw
    $match = [regex]::Match($content, '__version__\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        throw "Could not read project version from $initFile"
    }
    return $match.Groups[1].Value
}

function Copy-TreeFiltered {
    param(
        [string]$Source,
        [string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Required path is missing: $Source"
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        if ($item.PSIsContainer) {
            if ($item.Name -notin @(
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                "htmlcov",
                "build",
                "dist",
                "var",
                "reports"
            )) {
                Copy-TreeFiltered -Source $item.FullName -Destination (Join-Path $Destination $item.Name)
            }
        }
        elseif ($item.Extension -ne ".pyc" -and
                $item.Extension -ne ".pyo" -and
                $item.Name -notlike "*.sqlite" -and
                $item.Name -notlike "*.sqlite-*" -and
                $item.Name -notlike "*.db" -and
                $item.Name -notlike "*.log" -and
                $item.Name -notlike "*.tmp") {
            Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $Destination $item.Name)
        }
    }
}

function Copy-ReleaseSource {
    param([string]$Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($name in @("src", "tests", "scripts", "docs", ".github", "assets")) {
        $source = Join-Path $ProjectRoot $name
        if (Test-Path -LiteralPath $source) {
            Copy-TreeFiltered -Source $source -Destination (Join-Path $Destination $name)
        }
    }
    foreach ($name in @(
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "pyproject.toml",
        ".gitignore",
        ".gitattributes",
        "requirements-dev.txt"
    )) {
        $source = Join-Path $ProjectRoot $name
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination $Destination -Force
        }
    }
}

function Write-ZipAndHash {
    param(
        [string]$Directory,
        [string]$ZipPath,
        [string]$HashPath
    )
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive `
        -Path (Join-Path $Directory "*") `
        -DestinationPath $ZipPath `
        -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([System.IO.Path]::GetFileName($ZipPath))" |
        Set-Content -LiteralPath $HashPath -Encoding Ascii
    return $hash
}

if (-not $Version) {
    $Version = Get-ProjectVersion
}
if ($PackageName -eq "agent-token-ledger") {
    $PackageName = "agent-token-ledger-v$Version"
}

$SourceDir = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-source")
$ReportsDir = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-reports")
$DeliveryDir = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-delivery")
$SourceZip = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-source.zip")
$ReportsZip = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-reports.zip")
$DeliveryZip = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-delivery.zip")
$SourceHash = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-source.zip.sha256")
$ReportsHash = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-reports.zip.sha256")
$DeliveryHash = Assert-InOutputs (Join-Path $OutputsRoot "$PackageName-delivery.zip.sha256")

if (-not $SkipRunAll) {
    & (Join-Path $PSScriptRoot "run-all.ps1") -Python $Python
    if ($LASTEXITCODE -ne 0) {
        throw "run-all.ps1 failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $Db)) {
    throw "Ledger database is missing: $Db"
}
if (-not (Test-Path -LiteralPath (Join-Path $Reports "manifest.sha256"))) {
    throw "Reports are missing or incomplete: $Reports"
}

New-Item -ItemType Directory -Force -Path $OutputsRoot | Out-Null
foreach ($path in @($SourceDir, $ReportsDir, $DeliveryDir)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"

    Write-Host "[1/5] Checkpointing SQLite"
    Invoke-Python @(
        "-c",
        "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()); c.close()",
        $Db
    )

    Write-Host "[2/5] Building public source directory"
    Copy-ReleaseSource -Destination $SourceDir

    Write-Host "[3/5] Building local reports directory"
    Copy-TreeFiltered -Source $Reports -Destination $ReportsDir
    @"
# 报告隐私提示

本目录是当前电脑生成的本地报告，包含本机路径、用量统计和扫描证据。
它适合在本机查看和交付，但不是 GitHub 公共源码包的一部分。

- 公共源码包：`$PackageName-source.zip`
- 本地报告包：`$PackageName-reports.zip`
- 完整交付包：`$PackageName-delivery.zip`

不要把报告包、`var\ledger.sqlite` 或本机路径上传到公开仓库。
"@ | Set-Content -LiteralPath (Join-Path $ReportsDir "README_报告隐私.md") -Encoding UTF8

    Write-Host "[4/5] Building combined delivery directory"
    Copy-ReleaseSource -Destination $DeliveryDir
    $DeliveryReports = Join-Path $DeliveryDir "reports"
    Copy-TreeFiltered -Source $Reports -Destination $DeliveryReports
    @"
# 本地交付说明

本目录同时包含源码、一键脚本、文档和本次扫描生成的报告。

- 源码入口：`README.md`
- 一键扫描与报告：`scripts\run-all.ps1`
- 构建 Windows 程序：`scripts\build-app.ps1`
- 生成发布包：`scripts\package.ps1`
- 本地数据库不进入公共源码包，也不进入这里。

报告目录包含本机路径和用量证据，请按隐私资料管理。
"@ | Set-Content -LiteralPath (Join-Path $DeliveryDir "DELIVERY.md") -Encoding UTF8

    Write-Host "[5/5] Writing ZIP and SHA-256 files"
    $sourceSha = Write-ZipAndHash -Directory $SourceDir -ZipPath $SourceZip -HashPath $SourceHash
    $reportsSha = Write-ZipAndHash -Directory $ReportsDir -ZipPath $ReportsZip -HashPath $ReportsHash
    $deliverySha = Write-ZipAndHash -Directory $DeliveryDir -ZipPath $DeliveryZip -HashPath $DeliveryHash

    Write-Host "Package complete."
    Write-Host "Source directory:   $SourceDir"
    Write-Host "Source ZIP:         $SourceZip"
    Write-Host "Source SHA-256:     $sourceSha"
    Write-Host "Reports directory:  $ReportsDir"
    Write-Host "Reports ZIP:        $ReportsZip"
    Write-Host "Reports SHA-256:    $reportsSha"
    Write-Host "Delivery directory: $DeliveryDir"
    Write-Host "Delivery ZIP:       $DeliveryZip"
    Write-Host "Delivery SHA-256:   $deliverySha"
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
