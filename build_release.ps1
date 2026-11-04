param([switch]$Clean)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$Dist = Join-Path $ProjectRoot "dist\VisioExam"
$Release = Join-Path $ProjectRoot "release"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project virtual environment not found at $Python. Create it and install requirements.txt first."
}

Push-Location $ProjectRoot
try {
    $BuildArgs = @("-m", "PyInstaller", "--noconfirm")
    if ($Clean) { $BuildArgs += "--clean" }
    $BuildArgs += (Join-Path $ProjectRoot "VisioExam.spec")
    & $Python @BuildArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath (Join-Path $Dist "VisioExam.exe"))) {
    throw "PyInstaller completed without producing VisioExam.exe."
}

New-Item -ItemType Directory -Force -Path $Release | Out-Null
$ZipPath = Join-Path $Release "VisioExam-portable.zip"
if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $Dist,
    $ZipPath,
    [System.IO.Compression.CompressionLevel]::Fastest,
    $false
)
Write-Host "Portable package created: $ZipPath"

$Compiler = (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue).Source
if (-not $Compiler) {
    $Candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Compiler = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if ($Compiler) {
    & $Compiler (Join-Path $ProjectRoot "installer\VisioExam.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE." }
    Write-Host "Installer created: $(Join-Path $Release 'VisioExam-Setup.exe')"
} else {
    Write-Warning "Inno Setup 6 is not installed. The portable ZIP is ready; install Inno Setup 6 and rerun to create the installer."
}
