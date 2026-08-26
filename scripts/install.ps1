# Lie ce depot au dossier de plugins de LichtFeld Studio (mode developpement).
# Necessite une console PowerShell en administrateur, ou le mode developpeur
# de Windows active, pour creer la jonction.
$ErrorActionPreference = "Stop"

$PluginId  = "photosplat"
$SourceDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TargetDir = Join-Path $HOME ".lichtfeld\plugins\$PluginId"

New-Item -ItemType Directory -Force -Path (Split-Path $TargetDir) | Out-Null

if (Test-Path $TargetDir) {
    $item = Get-Item $TargetDir -Force
    if ($item.LinkType) {
        Write-Host "Jonction existante remplacee : $TargetDir"
        Remove-Item $TargetDir -Force
    } else {
        Write-Error "$TargetDir existe et n'est pas une jonction. Deplacez-le, puis relancez."
    }
}

New-Item -ItemType Junction -Path $TargetDir -Target $SourceDir | Out-Null
Write-Host "Plugin lie : $TargetDir -> $SourceDir"
Write-Host ""
Write-Host "Dans LichtFeld Studio, console Python :"
Write-Host "  import lichtfeld as lf"
Write-Host "  lf.plugins.discover()"
Write-Host "  lf.plugins.load('$PluginId')"
