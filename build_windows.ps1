param(
    [string]$Python = 'python',
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\KancolleClock-Windows'),
    [string]$WorkDirectory = (Join-Path ([IO.Path]::GetTempPath()) 'KancolleClock-build'),
    [switch]$ValidatePathsOnly
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath($PSScriptRoot)
$build = [IO.Path]::GetFullPath($WorkDirectory)
$release = [IO.Path]::GetFullPath($OutputDirectory)
$outputRoot = [IO.Path]::GetFullPath((Join-Path $project '..'))
$comparison = [StringComparison]::OrdinalIgnoreCase
function Is-Inside([string]$Child, [string]$Parent) {
    return $Child.Equals($Parent, $comparison) -or $Child.StartsWith($Parent.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar, $comparison)
}
if ((Is-Inside $release $project) -or (Is-Inside $project $release)) {
    throw 'The release directory must be outside the source directory.'
}
if ((Is-Inside $build $project) -or (Is-Inside $project $build) -or
    (Is-Inside $build $release) -or (Is-Inside $release $build)) {
    throw 'The build cache must be outside the source directory.'
}
# Existing directories may only be replaced at this known sibling output path.
if ((Test-Path -LiteralPath $release) -and
    -not $release.Equals((Join-Path $outputRoot 'KancolleClock-Windows'), $comparison)) {
    throw 'Existing release cleanup is limited to the sibling KancolleClock-Windows directory.'
}
function Assert-NoReparseAncestor([string]$Target) {
    $cursor = $Target
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reparse point is not allowed: $cursor"
            }
        }
        $parent = Split-Path -Parent $cursor
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}
Assert-NoReparseAncestor $release
Assert-NoReparseAncestor $build
if ($ValidatePathsOnly) {
    Write-Output "Validated release: $release"
    Write-Output "Validated build cache: $build"
    exit 0
}
New-Item -ItemType Directory -Path $build -Force | Out-Null
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name KancolleClock `
    --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder `
    --exclude-module numpy --exclude-module OpenGL `
    --distpath (Join-Path $build 'dist') --workpath (Join-Path $build 'cache') `
    --specpath $build (Join-Path $project 'clock_gui.pyw')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
# Recheck the resolved absolute target immediately before recursive cleanup.
if (Test-Path -LiteralPath $release) {
    Assert-NoReparseAncestor $release
    if (-not $release.Equals((Join-Path $outputRoot 'KancolleClock-Windows'), $comparison) -or
        -not (Is-Inside $release $outputRoot)) { throw 'Release cleanup target failed final verification.' }
    Write-Output "Replacing verified release directory: $release"
    Remove-Item -LiteralPath $release -Recurse -Force
}
New-Item -ItemType Directory -Path $release -Force | Out-Null
Copy-Item -Path (Join-Path $build 'dist\KancolleClock\*') -Destination $release -Recurse -Force
foreach ($name in @('README.md','THIRD_PARTY_NOTICES.md')) {
    Copy-Item -LiteralPath (Join-Path $project $name) -Destination $release -Force
}
& $Python (Join-Path $project 'tools\collect_licenses.py') (Join-Path $release 'third_party_licenses')
if ($LASTEXITCODE -ne 0) { throw 'Dependency license collection failed.' }
Write-Output "Built: $(Join-Path $release 'KancolleClock.exe')"
Write-Output 'External audio is not bundled. Integrate the verified manifest and kancolle directory separately.'
