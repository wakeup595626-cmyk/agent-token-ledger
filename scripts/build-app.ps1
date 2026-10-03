[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$OutputsRoot = "",
    [string]$DesktopDir = "",
    [string]$PyInstallerVersion = "6.22.3",
    [string]$PyWebViewVersion = "6.2.1",
    [switch]$NoDesktop,
    [switch]$SkipTests,
    [switch]$Package
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $OutputsRoot) {
    $OutputsRoot = Join-Path $ProjectRoot "..\..\outputs"
}
$OutputsRoot = [System.IO.Path]::GetFullPath($OutputsRoot)
if (-not $DesktopDir) {
    $DesktopDir = [Environment]::GetFolderPath("Desktop")
}
if (-not $DesktopDir) {
    $DesktopDir = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Desktop"
}
$DesktopDir = [System.IO.Path]::GetFullPath($DesktopDir)

$DistDir = Join-Path $ProjectRoot "var\app-dist"
$WorkDir = Join-Path $ProjectRoot "var\app-build"
$SpecDir = Join-Path $ProjectRoot "var\app-spec"
$IconPath = Join-Path $ProjectRoot "assets\AgentTokenLedger.ico"
$WebDir = Join-Path $ProjectRoot "src\agent_token_ledger\web"
$ExeName = "AgentTokenLedger.exe"
$BuiltExe = Join-Path $DistDir $ExeName
$PackageName = "AgentTokenLedger-windows-x64"
$ZipPath = ""
$ZipHashPath = ""
$StagingDir = ""
$OldPythonPath = $env:PYTHONPATH

function Assert-UnderRoot {
    param(
        [string]$Path,
        [string]$Root,
        [string]$Label
    )
    $rootPrefix = [System.IO.Path]::GetFullPath($Root).TrimEnd("\") + "\"
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must stay inside $Root`: $fullPath"
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

function Get-PyInstallerVersion {
    try {
        $value = & $Python -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $value) {
            return $value.Trim()
        }
    }
    catch {
        return ""
    }
    return ""
}

function Get-PackageVersion {
    param([string]$PackageName)
    try {
        $value = & $Python -c "import importlib.metadata as m; print(m.version('$PackageName'))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $value) {
            return $value.Trim()
        }
    }
    catch {
        return ""
    }
    return ""
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

function Copy-ReleaseDocs {
    param([string]$Destination)
    foreach ($name in @(
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md"
    )) {
        $source = Join-Path $ProjectRoot $name
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination $Destination -Force
        }
    }
    $docsSource = Join-Path $ProjectRoot "docs"
    if (Test-Path -LiteralPath $docsSource) {
        $docsDestination = Join-Path $Destination "docs"
        New-Item -ItemType Directory -Force -Path $docsDestination | Out-Null
        foreach ($item in Get-ChildItem -LiteralPath $docsSource -File) {
            Copy-Item -LiteralPath $item.FullName -Destination $docsDestination -Force
        }
    }
    $assetsSource = Join-Path $ProjectRoot "assets"
    if (Test-Path -LiteralPath $assetsSource) {
        $assetsDestination = Join-Path $Destination "assets"
        New-Item -ItemType Directory -Force -Path $assetsDestination | Out-Null
        foreach ($item in Get-ChildItem -LiteralPath $assetsSource -File) {
            Copy-Item -LiteralPath $item.FullName -Destination $assetsDestination -Force
        }
    }
}

function New-VersionResourceFile {
    param(
        [string]$Path,
        [string]$Version
    )
    $parts = @($Version.Split(".") | ForEach-Object { [int]($_ -replace "\D", "") })
    while ($parts.Count -lt 4) {
        $parts += 0
    }
    $quad = ($parts[0..3] -join ", ")
    $content = @"
# -*- coding: utf-8 -*-
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($quad),
    prodvers=($quad),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [
          StringStruct('CompanyName', 'AgentTokenLedger'),
          StringStruct('FileDescription', '\u672c\u673a\u667a\u80fd\u4f53 Token \u7528\u91cf\u770b\u677f'),
          StringStruct('FileVersion', '$Version'),
          StringStruct('InternalName', 'AgentTokenLedger'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 AgentTokenLedger contributors'),
          StringStruct('OriginalFilename', 'AgentTokenLedger.exe'),
          StringStruct('ProductName', '\u672c\u673a\u667a\u80fd\u4f53\u7528\u91cf\u8d26\u672c'),
          StringStruct('ProductVersion', '$Version')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"@
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
}

if ($Package) {
    New-Item -ItemType Directory -Force -Path $OutputsRoot | Out-Null
}
Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    if (-not $SkipTests) {
        Write-Host "[1/5] Running tests"
        Invoke-Python @("-m", "unittest", "discover", "-s", "tests", "-v")
    }
    else {
        Write-Host "[1/5] Tests skipped by request"
    }

    $ProjectVersion = Get-ProjectVersion
    $PackageName = "AgentTokenLedger-windows-x64-v$ProjectVersion"
    if ($Package) {
        $ZipPath = Assert-UnderRoot (Join-Path $OutputsRoot "$PackageName.zip") $OutputsRoot "app zip"
        $ZipHashPath = Assert-UnderRoot (Join-Path $OutputsRoot "$PackageName.zip.sha256") $OutputsRoot "app zip hash"
        $StagingDir = Assert-UnderRoot (Join-Path $OutputsRoot ".$PackageName-$([System.Guid]::NewGuid().ToString('N'))") $OutputsRoot "app staging"
    }
    if (-not (Test-Path -LiteralPath $WebDir)) {
        throw "Packaged web assets are missing: $WebDir"
    }

    $InstalledPyInstaller = Get-PyInstallerVersion
    if ($InstalledPyInstaller -ne $PyInstallerVersion) {
        Write-Host "[2/5] Installing PyInstaller $PyInstallerVersion"
        Invoke-Python @(
            "-m", "pip", "install", "--disable-pip-version-check",
            "pyinstaller==$PyInstallerVersion"
        )
    }
    else {
        Write-Host "[2/5] Reusing PyInstaller $InstalledPyInstaller"
    }

    $InstalledPyWebView = Get-PackageVersion "pywebview"
    if ($InstalledPyWebView -ne $PyWebViewVersion) {
        Write-Host "[2/5] Installing pywebview $PyWebViewVersion"
        Invoke-Python @(
            "-m", "pip", "install", "--disable-pip-version-check",
            "pywebview==$PyWebViewVersion"
        )
    }
    else {
        Write-Host "[2/5] Reusing pywebview $InstalledPyWebView"
    }

    if (Test-Path -LiteralPath $DistDir) {
        Remove-Item -LiteralPath $DistDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $WorkDir) {
        Remove-Item -LiteralPath $WorkDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $SpecDir) {
        Remove-Item -LiteralPath $SpecDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $DistDir, $WorkDir, $SpecDir | Out-Null
    $VersionFile = Join-Path $SpecDir "version_info.txt"
    New-VersionResourceFile -Path $VersionFile -Version $ProjectVersion

    $Arguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "AgentTokenLedger",
        "--paths", (Join-Path $ProjectRoot "src"),
        "--collect-all", "webview",
        "--collect-submodules", "agent_token_ledger",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "webview.platforms.winforms",
        "--hidden-import", "clr",
        "--hidden-import", "clr_loader",
        "--add-data", "$WebDir;agent_token_ledger\web",
        "--distpath", $DistDir,
        "--workpath", $WorkDir,
        "--specpath", $SpecDir
    )
    if (Test-Path -LiteralPath $IconPath) {
        $Arguments += @("--icon", $IconPath)
    }
    $Arguments += @("--version-file", $VersionFile)
    $Arguments += @(Join-Path $ProjectRoot "src\agent_token_ledger\app.py")

    Write-Host "[3/5] Building $ExeName"
    Invoke-Python $Arguments
    if (-not (Test-Path -LiteralPath $BuiltExe)) {
        throw "PyInstaller did not produce $BuiltExe"
    }

    Write-Host "[4/5] Copying desktop executable"
    if ($NoDesktop) {
        Write-Host "Desktop copy skipped by request"
    }
    else {
        New-Item -ItemType Directory -Force -Path $DesktopDir | Out-Null
        Copy-Item -LiteralPath $BuiltExe -Destination (Join-Path $DesktopDir $ExeName) -Force
        Write-Host "Desktop: $(Join-Path $DesktopDir $ExeName)"
    }

    if ($Package) {
        Write-Host "[5/5] Creating outputs ZIP and SHA-256"
        if (Test-Path -LiteralPath $StagingDir) {
            Remove-Item -LiteralPath $StagingDir -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
        Copy-Item -LiteralPath $BuiltExe -Destination (Join-Path $StagingDir $ExeName)
        Copy-ReleaseDocs -Destination $StagingDir

        $ExeHash = (Get-FileHash -LiteralPath $BuiltExe -Algorithm SHA256).Hash.ToLowerInvariant()
        "$ExeHash  $ExeName" | Set-Content -LiteralPath (Join-Path $StagingDir "$ExeName.sha256") -Encoding Ascii

        if (Test-Path -LiteralPath $ZipPath) {
            Remove-Item -LiteralPath $ZipPath -Force
        }
        Compress-Archive -Path (Join-Path $StagingDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal
        $ZipHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        "$ZipHash  $PackageName.zip" | Set-Content -LiteralPath $ZipHashPath -Encoding Ascii
    }
    else {
        Write-Host "[5/5] Packaging skipped; the build produced the EXE only."
    }

    Write-Host "App build complete."
    Write-Host "EXE:       $BuiltExe"
    if (-not $NoDesktop) {
        Write-Host "Desktop:   $(Join-Path $DesktopDir $ExeName)"
    }
    if ($Package) {
        Write-Host "ZIP:       $ZipPath"
        Write-Host "SHA-256:   $ZipHash"
    }
    else {
        Write-Host "ZIP:       skipped (pass -Package to create one)"
    }
}
finally {
    if ($StagingDir -and (Test-Path -LiteralPath $StagingDir)) {
        Remove-Item -LiteralPath $StagingDir -Recurse -Force
    }
    if ($null -eq $OldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $OldPythonPath
    }
    Pop-Location
}
