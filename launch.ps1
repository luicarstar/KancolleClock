param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'clock_gui.pyw') @args
exit $LASTEXITCODE
