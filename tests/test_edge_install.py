"""Exercise installation without changing the user's real registry."""
import json
import importlib
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / 'edge' / 'install-native-host.ps1'
UNINSTALL = ROOT / 'edge' / 'uninstall-native-host.ps1'
ORIGIN = 'chrome-extension://pibjjmjbipbifeddoahjagcinihkcgnf/'
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(sys.platform != 'win32' or not POWERSHELL,
                                reason='Windows PowerShell installer tests')


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_install_logic(tmp_path, commands, initial=None):
    assert INSTALL.is_file(), 'Native host installer has not been implemented'
    assert UNINSTALL.is_file(), 'Native host uninstaller has not been implemented'
    package = tmp_path / '随手回 package'
    package.mkdir()
    (package / 'SuishouReplyBridge.exe').write_bytes(b'fixture-not-executed')
    initial = initial or {'KeyExists': False, 'HasValue': False, 'Value': None, 'ValueKind': None}
    script = tmp_path / 'simulate.ps1'
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)\n"
        f'. {literal(INSTALL)}\n. {literal(UNINSTALL)}\n'
        f'$root = {literal(package)}\n'
        f'$global:fakeRegistration = ConvertFrom-Json {literal(json.dumps(initial))}\n'
        '$global:writes = 0\n'
        'function Get-SuishouRegistration { return $global:fakeRegistration }\n'
        'function Set-SuishouRegistration { param([string]$Value, [string]$ValueKind = "String")\n'
        '  $global:writes++; $global:fakeRegistration = [pscustomobject]@{KeyExists=$true;HasValue=$true;Value=$Value;ValueKind=$ValueKind}\n}\n'
        'function Clear-SuishouRegistration { param([bool]$DeleteIfEmpty)\n'
        '  $global:writes++; $global:fakeRegistration = [pscustomobject]@{KeyExists=(-not $DeleteIfEmpty);HasValue=$false;Value=$null;ValueKind=$null}\n}\n'
        + commands,
        encoding='utf-8-sig',
    )
    result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy',
                             'Bypass', '-File', str(script)], capture_output=True,
                            encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), package


def test_plan_has_exact_origin_absolute_host_and_changes_nothing(tmp_path):
    result, package = run_install_logic(tmp_path, '''
$plan = Install-SuishouNativeHost -RootPath $root -PlanOnly
@{plan=$plan; writes=$global:writes; files=@(Get-ChildItem -LiteralPath $root -File).Count} | ConvertTo-Json -Depth 10
''')
    assert result['writes'] == 0
    assert result['files'] == 1
    manifest = result['plan']['manifest']
    assert manifest['name'] == 'com.suishou.reply'
    assert manifest['type'] == 'stdio'
    assert manifest['allowed_origins'] == [ORIGIN]
    assert Path(manifest['path']) == package / 'SuishouReplyBridge.exe'


@pytest.mark.parametrize('initial', [
    {'KeyExists': False, 'HasValue': False, 'Value': None, 'ValueKind': None},
    {'KeyExists': True, 'HasValue': False, 'Value': None, 'ValueKind': None},
    {'KeyExists': True, 'HasValue': True, 'Value': r'C:\Previous Host\host.json', 'ValueKind': 'String'},
    {'KeyExists': True, 'HasValue': True, 'Value': r'%LOCALAPPDATA%\Previous\host.json', 'ValueKind': 'ExpandString'},
])
def test_install_is_idempotent_and_uninstall_restores_original(tmp_path, initial):
    result, package = run_install_logic(tmp_path, '''
$first = Install-SuishouNativeHost -RootPath $root
$before = [IO.File]::ReadAllText((Join-Path $root 'native-registration-backup.json'))
$second = Install-SuishouNativeHost -RootPath $root
$after = [IO.File]::ReadAllText((Join-Path $root 'native-registration-backup.json'))
$removed = Uninstall-SuishouNativeHost -RootPath $root
$again = Uninstall-SuishouNativeHost -RootPath $root
@{first=$first;second=$second;removed=$removed;again=$again;snapshotUnchanged=($before -eq $after);registration=$global:fakeRegistration} | ConvertTo-Json -Depth 10
''', initial)
    assert result['snapshotUnchanged'] is True
    assert result['registration'] == initial
    assert result['removed']['status'] == 'restored'
    assert result['again']['status'] == 'already-restored'
    data = (package / 'native-host.json').read_bytes()
    assert not data.startswith(b'\xef\xbb\xbf')
    assert json.loads(data)['allowed_origins'] == [ORIGIN]


def test_changed_registration_is_never_overwritten_by_uninstall_or_reinstall(tmp_path):
    result, _ = run_install_logic(tmp_path, '''
$null = Install-SuishouNativeHost -RootPath $root
$global:fakeRegistration = [pscustomobject]@{KeyExists=$true;HasValue=$true;Value='C:\\Another\\host.json';ValueKind='String'}
$before = $global:writes
$result = Uninstall-SuishouNativeHost -RootPath $root
$rejected = $false
try { $null = Install-SuishouNativeHost -RootPath $root } catch { $rejected = $true }
@{result=$result;rejected=$rejected;writesAfterChange=($global:writes - $before);value=$global:fakeRegistration.Value} | ConvertTo-Json -Depth 10
''')
    assert result['result']['status'] == 'registration-changed'
    assert result['rejected'] is True
    assert result['writesAfterChange'] == 0
    assert result['value'] == r'C:\Another\host.json'


def test_invalid_backup_fails_without_registry_write(tmp_path):
    result, _ = run_install_logic(tmp_path, '''
[IO.File]::WriteAllText((Join-Path $root 'native-registration-backup.json'), '{}')
$rejected = $false
try { $null = Install-SuishouNativeHost -RootPath $root } catch { $rejected = $true }
@{rejected=$rejected;writes=$global:writes} | ConvertTo-Json
''')
    assert result == {'rejected': True, 'writes': 0}


def test_missing_bridge_fails_without_registry_write(tmp_path):
    result, _ = run_install_logic(tmp_path, '''
Remove-Item -LiteralPath (Join-Path $root 'SuishouReplyBridge.exe')
$rejected = $false
try { $null = Install-SuishouNativeHost -RootPath $root } catch { $rejected = $true }
@{rejected=$rejected;writes=$global:writes} | ConvertTo-Json
''')
    assert result == {'rejected': True, 'writes': 0}


def packaging_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    return importlib.import_module('build_edge'), importlib.import_module('package_edge')


def source_fixture(tmp_path, package):
    root = tmp_path / 'source'
    for name in (*package.SOURCE_NAMES,
                 *(f'edge/{name}' for name in package.INSTALLER_NAMES),
                 'extension/popup.html', 'extension/popup.css', 'extension/popup.js',
                 'extension/src/content.js', 'extension/icons/icon16.png'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture', encoding='utf-8')
    (root / 'extension' / 'manifest.json').write_bytes((ROOT / 'extension' / 'manifest.json').read_bytes())
    return root


def test_package_selects_only_edge_sources_and_excludes_user_data(tmp_path, monkeypatch):
    build, package = packaging_modules(monkeypatch)
    root = source_fixture(tmp_path, package)
    private = ('docs/HORIZON.md', '.side-panel-backup/original.py', 'settings.json',
               'original-history.json', 'extension/node_modules/test.js', 'extension/test.log',
               'extension/src/private.key', '.env', 'dist/SuishouReply.exe')
    for name in private:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('must-not-be-packaged', encoding='utf-8')
    names = {path.relative_to(root).as_posix() for path in package.selected_sources(root)}
    assert not names.intersection(private)
    assert 'suishou/credentials.py' in names
    assert 'edge_host.py' in names
    assert 'suishou/edge_protocol.py' in names
    assert 'tests/conftest.py' in names
    assert 'extension/popup.html' in names
    assert 'extension/src/content.js' in names
    runtime = {path.relative_to(root).as_posix() for path in build.extension_files(root)}
    assert not runtime.intersection(private)


def test_wrong_extension_identity_is_rejected_before_packaging(tmp_path, monkeypatch):
    build, package = packaging_modules(monkeypatch)
    root = source_fixture(tmp_path, package)
    path = root / 'extension' / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['key'] = 'd3JvbmctaWRlbnRpdHk='
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='fixed ID'):
        build.extension_files(root)


def test_runtime_checksum_and_inventory_reject_tampering(tmp_path, monkeypatch):
    build, package = packaging_modules(monkeypatch)
    source = source_fixture(tmp_path, package)
    monkeypatch.setattr(package, 'ROOT', source)
    monkeypatch.setattr(package, 'extension_files', lambda: build.extension_files(source))
    dist = tmp_path / 'dist'
    names = {package.EXE_NAME, 'LICENSE', 'THIRD_PARTY_NOTICES.md', *package.INSTALLER_NAMES}
    names.update(path.relative_to(source).as_posix() for path in build.extension_files(source))
    for name in names:
        path = dist / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.startswith('extension/'):
            path.write_bytes((source / name).read_bytes())
        elif name in package.INSTALLER_NAMES:
            path.write_bytes((source / 'edge' / name).read_bytes())
        else:
            path.write_bytes(b'fixture')
    (dist / 'licenses').mkdir()
    (dist / 'licenses' / 'license.txt').write_text('fixture', encoding='utf-8')
    (dist / 'SHA256SUMS.txt').write_text('fixture', encoding='utf-8')
    info = {'version': package.VERSION, 'extension_id': package.EXTENSION_ID,
            'native_host': package.HOST_NAME, 'executable': package.EXE_NAME,
            'runtime_sha256': {name: build.digest(dist / name) for name in names},
            'sha256': build.digest(dist / package.EXE_NAME), 'size_bytes': len(b'fixture')}
    (dist / 'BUILD_INFO.json').write_text(json.dumps(info), encoding='utf-8')
    assert package.verified_runtime(dist)
    (dist / 'popup-untracked.js').write_text('not-selected', encoding='utf-8')
    assert dist / 'popup-untracked.js' not in package.verified_runtime(dist)
    (source / 'extension' / 'popup.js').write_text('new source', encoding='utf-8')
    with pytest.raises(ValueError, match='current source'):
        package.verified_runtime(dist)
    (source / 'extension' / 'popup.js').write_text('fixture', encoding='utf-8')
    (dist / 'extension' / 'popup.js').write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='checksum'):
        package.verified_runtime(dist)
