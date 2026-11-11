[CmdletBinding()]
param([string]$InstallRoot = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'install-native-host.ps1') -InstallRoot $InstallRoot

function Uninstall-SuishouNativeHost {
    param([string]$RootPath)
    $paths = Get-SuishouInstallPaths -RootPath $RootPath
    $saved = Read-SuishouBackup -Paths $paths
    if ($null -eq $saved) { throw 'No registration backup exists in this folder. Nothing was changed.' }
    $current = Get-SuishouRegistration
    if (Test-SuishouRegistrationEqual $current $saved.original) {
        return [pscustomobject]@{status='already-restored'}
    }
    $ours = [pscustomobject]@{KeyExists=$true; HasValue=$true; Value=$paths.Manifest; ValueKind='String'}
    if (-not (Test-SuishouRegistrationEqual $current $ours)) {
        return [pscustomobject]@{status='registration-changed'; message='Another registration is active. Nothing was changed.'}
    }
    if ($saved.original.HasValue) {
        Set-SuishouRegistration -Value $saved.original.Value -ValueKind $saved.original.ValueKind
    } else {
        Clear-SuishouRegistration -DeleteIfEmpty:(-not $saved.original.KeyExists)
    }
    # Keep files and rollback evidence. Never recursively remove application directories.
    return [pscustomobject]@{status='restored'; message='Previous registration restored. Application files and desktop credentials were kept.'}
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Uninstall-SuishouNativeHost -RootPath $InstallRoot | ConvertTo-Json -Depth 8
        Write-Host 'To remove the browser extension, use edge://extensions. Desktop SuishouReply is unchanged.'
    } catch { Write-Error $_.Exception.Message; exit 1 }
}
