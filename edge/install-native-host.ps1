[CmdletBinding()]
param([string]$InstallRoot = $PSScriptRoot, [switch]$PlanOnly)

$ErrorActionPreference = 'Stop'
$script:SuishouHostKey = 'SOFTWARE\Microsoft\Edge\NativeMessagingHosts\com.suishou.reply'
$script:SuishouOrigin = 'chrome-extension://pibjjmjbipbifeddoahjagcinihkcgnf/'

function Get-SuishouRegistration {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($script:SuishouHostKey)
    if ($null -eq $key) {
        return [pscustomobject]@{KeyExists=$false; HasValue=$false; Value=$null; ValueKind=$null}
    }
    try {
        $hasValue = @($key.GetValueNames()) -contains ''
        if (-not $hasValue) {
            return [pscustomobject]@{KeyExists=$true; HasValue=$false; Value=$null; ValueKind=$null}
        }
        $kind = $key.GetValueKind('').ToString()
        if ($kind -notin @('String', 'ExpandString')) { throw 'Existing host registration is not a string. Nothing was changed.' }
        $value = $key.GetValue('', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        return [pscustomobject]@{KeyExists=$true; HasValue=$true; Value=[string]$value; ValueKind=$kind}
    } finally { $key.Dispose() }
}

function Set-SuishouRegistration {
    param([string]$Value, [string]$ValueKind = 'String')
    if ($ValueKind -notin @('String', 'ExpandString')) { throw 'Unsupported registry value kind.' }
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($script:SuishouHostKey)
    try { $key.SetValue('', $Value, [Microsoft.Win32.RegistryValueKind]::$ValueKind) }
    finally { $key.Dispose() }
}

function Clear-SuishouRegistration {
    param([bool]$DeleteIfEmpty)
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($script:SuishouHostKey, $true)
    if ($null -eq $key) { return }
    $removeKey = $false
    try {
        $key.DeleteValue('', $false)
        $removeKey = $DeleteIfEmpty -and $key.ValueCount -eq 0 -and $key.SubKeyCount -eq 0
    } finally { $key.Dispose() }
    if ($removeKey) { [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($script:SuishouHostKey, $false) }
}

function Test-SuishouRegistrationEqual {
    param($Left, $Right)
    return ($Left.KeyExists -eq $Right.KeyExists -and $Left.HasValue -eq $Right.HasValue -and
            $Left.Value -ceq $Right.Value -and $Left.ValueKind -ceq $Right.ValueKind)
}

function Get-SuishouInstallPaths {
    param([string]$RootPath)
    if ([string]::IsNullOrWhiteSpace($RootPath) -or $RootPath.StartsWith('\\') -or $RootPath.StartsWith('//')) {
        throw 'Use a local, fully extracted installation folder.'
    }
    $root = [IO.Path]::GetFullPath($RootPath)
    if (-not [IO.Directory]::Exists($root)) { throw 'Installation folder does not exist.' }
    return [pscustomobject]@{
        Root=$root
        Exe=[IO.Path]::Combine($root, 'SuishouReplyBridge.exe')
        Manifest=[IO.Path]::Combine($root, 'native-host.json')
        Backup=[IO.Path]::Combine($root, 'native-registration-backup.json')
    }
}

function Write-SuishouJson {
    param([string]$Path, $Value)
    $json = ConvertTo-Json -InputObject $Value -Depth 8
    [IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
}

function Read-SuishouBackup {
    param($Paths)
    if (-not [IO.File]::Exists($Paths.Backup)) { return $null }
    if ((Get-Item -LiteralPath $Paths.Backup).Length -gt 16384) { throw 'Registration backup is invalid. Nothing was changed.' }
    $saved = [IO.File]::ReadAllText($Paths.Backup, [Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($saved.schema -ne 1 -or $saved.host -cne 'com.suishou.reply' -or
        $saved.manifest -cne $Paths.Manifest -or $null -eq $saved.original -or
        $saved.original.KeyExists -isnot [bool] -or $saved.original.HasValue -isnot [bool]) {
        throw 'Registration backup is invalid or belongs to a different installation. Nothing was changed.'
    }
    if ($saved.original.HasValue) {
        if (-not $saved.original.KeyExists -or $saved.original.Value -isnot [string] -or
            $saved.original.Value.Length -gt 8192 -or $saved.original.ValueKind -notin @('String', 'ExpandString')) {
            throw 'Registration backup value is invalid. Nothing was changed.'
        }
    } elseif ($null -ne $saved.original.Value -or $null -ne $saved.original.ValueKind) {
        throw 'Registration backup value is inconsistent. Nothing was changed.'
    }
    return $saved
}

function Install-SuishouNativeHost {
    param([string]$RootPath, [switch]$PlanOnly)
    $paths = Get-SuishouInstallPaths -RootPath $RootPath
    if (-not [IO.File]::Exists($paths.Exe)) { throw 'SuishouReplyBridge.exe is missing. Extract the complete package first.' }
    $manifest = [ordered]@{
        name='com.suishou.reply'
        description='SuishouReply local DeepSeek reply bridge'
        path=$paths.Exe
        type='stdio'
        allowed_origins=@($script:SuishouOrigin)
    }
    if ($PlanOnly) {
        return [pscustomobject]@{status='plan'; registry=('HKCU\' + $script:SuishouHostKey); manifest_path=$paths.Manifest; manifest=$manifest}
    }
    $current = Get-SuishouRegistration
    $ours = [pscustomobject]@{KeyExists=$true; HasValue=$true; Value=$paths.Manifest; ValueKind='String'}
    $saved = Read-SuishouBackup -Paths $paths
    if ($null -eq $saved) {
        if (Test-SuishouRegistrationEqual $current $ours) {
            throw 'This host is registered but its rollback backup is missing. Nothing was changed.'
        }
        $saved = [ordered]@{schema=1; host='com.suishou.reply'; manifest=$paths.Manifest; original=$current}
        Write-SuishouJson -Path $paths.Backup -Value $saved
    } elseif (-not (Test-SuishouRegistrationEqual $current $ours) -and
              -not (Test-SuishouRegistrationEqual $current $saved.original)) {
        throw 'Another installation changed the registration. Nothing was changed; keep or uninstall that installation first.'
    }
    Write-SuishouJson -Path $paths.Manifest -Value $manifest
    if (-not (Test-SuishouRegistrationEqual $current $ours)) { Set-SuishouRegistration -Value $paths.Manifest }
    return [pscustomobject]@{status='installed'; extension_id='pibjjmjbipbifeddoahjagcinihkcgnf'; manifest=$paths.Manifest}
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        $result = Install-SuishouNativeHost -RootPath $InstallRoot -PlanOnly:$PlanOnly
        $result | ConvertTo-Json -Depth 8
        if (-not $PlanOnly) {
            Write-Host 'Installed for the current Windows user. No administrator rights were used.'
            Write-Host 'Keep this folder in place. In Edge, load the extension subfolder at edge://extensions.'
            Write-Host 'Expected extension ID: pibjjmjbipbifeddoahjagcinihkcgnf'
        }
    } catch { Write-Error $_.Exception.Message; exit 1 }
}
