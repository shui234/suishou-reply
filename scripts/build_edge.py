"""Build an isolated Edge companion; never replace the desktop EXE."""
from __future__ import annotations

import argparse
import base64
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
from build import build_environment, collect_notices

VERSION = '1.2.0'
EXTENSION_ID = 'pibjjmjbipbifeddoahjagcinihkcgnf'
HOST_NAME = 'com.suishou.reply'
EXE_NAME = 'SuishouReplyBridge.exe'
INSTALLER_NAMES = ('install-native-host.ps1', 'uninstall-native-host.ps1', 'Install.cmd', 'Uninstall.cmd')
DOC_NAMES = ('EDGE_EXTENSION.md', 'EDGE_TEST_REPORT.md', 'EDGE_PLATFORM_RULES.md',
             'edge-preview.png', 'edge-preview-small.png', 'edge-verification.json')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extension_files(root: Path = ROOT) -> list[Path]:
    """Only browser runtime assets; no tests, npm packages, logs or private data."""
    extension = root / 'extension'
    files = [extension / name for name in ('manifest.json', 'popup.html', 'popup.css', 'popup.js')]
    for folder, suffixes in (('src', {'.js', '.css'}), ('icons', {'.png', '.svg'})):
        files.extend(path for path in sorted((extension / folder).rglob('*'))
                     if path.is_file() and path.suffix.lower() in suffixes)
    if any(not path.is_file() for path in files):
        raise ValueError('Extension runtime files are incomplete.')
    if any(path.is_symlink() or not path.resolve().is_relative_to(extension.resolve()) for path in files):
        raise ValueError('Extension runtime must contain ordinary files within its directory.')
    manifest = json.loads((extension / 'manifest.json').read_text(encoding='utf-8'))
    key = base64.b64decode(manifest['key'], validate=True)
    identity = hashlib.sha256(key).hexdigest()[:32].translate(str.maketrans('0123456789abcdef', 'abcdefghijklmnop'))
    if manifest.get('manifest_version') != 3 or manifest.get('version') != VERSION or identity != EXTENSION_ID:
        raise ValueError('Extension version, manifest or fixed ID does not match this bridge.')
    return files


def write_version_info(path: Path) -> None:
    path.write_text("""VSVersionInfo(
 ffi=FixedFileInfo(filevers=(1,2,0,0), prodvers=(1,2,0,0), mask=0x3f,
  flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),
 kids=[StringFileInfo([StringTable('040904B0', [
  StringStruct('FileDescription', 'SuishouReply Edge Native Messaging Bridge'),
  StringStruct('FileVersion', '1.2.0'),
  StringStruct('InternalName', 'SuishouReplyBridge'),
  StringStruct('OriginalFilename', 'SuishouReplyBridge.exe'),
  StringStruct('ProductName', 'SuishouReply Edge'),
  StringStruct('ProductVersion', '1.2.0')
 ])]), VarFileInfo([VarStruct('Translation', [1033,1200])])]
)
""", encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Build the separate SuishouReply Edge native bridge')
    parser.add_argument('--dist-dir', type=Path, default=ROOT / f'dist-edge-v{VERSION}')
    args = parser.parse_args()
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        parser.error('Use 64-bit Python on Windows.')
    dist = args.dist_dir.resolve()
    if dist.parent != ROOT or not dist.name.startswith('dist-edge-'):
        parser.error('Choose a dist-edge-* directory immediately inside the project; desktop outputs are protected.')
    runtime = extension_files()
    for name in INSTALLER_NAMES:
        if not (ROOT / 'edge' / name).is_file():
            parser.error(f'Missing installer: {name}')
    if not (ROOT / 'edge_host.py').is_file():
        parser.error('Native host entry point is missing.')

    build = ROOT / 'build' / 'edge-v1.2.0'
    build.mkdir(parents=True, exist_ok=True)
    dist.mkdir(parents=True, exist_ok=True)
    version = build / 'version_info.txt'
    write_version_info(version)
    notices = build / 'third-party-licenses'
    collect_notices(notices)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
               '--console', '--noupx', '--name', 'SuishouReplyBridge',
               '--version-file', str(version), '--distpath', str(dist),
               '--workpath', str(build / 'pyinstaller'), '--specpath', str(build),
               '--log-level', 'WARN', '--add-data', f'{notices};licenses',
               '--add-data', f'{ROOT / "THIRD_PARTY_NOTICES.md"};.',
               '--exclude-module', 'tkinter', '--exclude-module', 'PySide6.QtQml',
               '--exclude-module', 'PySide6.QtQuick', '--exclude-module', 'PySide6.QtWebEngineCore',
               str(ROOT / 'edge_host.py')]
    print(f'Building Edge companion {VERSION}; desktop builds are unchanged.', flush=True)
    subprocess.run(command, cwd=ROOT, env=build_environment(), check=True)
    exe = dist / EXE_NAME
    if not exe.is_file():
        raise RuntimeError('PyInstaller did not create the native bridge.')

    copied: list[Path] = [exe]
    expected_extension = {path.relative_to(ROOT / 'extension') for path in runtime}
    existing_extension = dist / 'extension'
    if existing_extension.exists():
        extras = [path for path in existing_extension.rglob('*') if path.is_file()
                  and path.relative_to(existing_extension) not in expected_extension]
        if extras:
            raise RuntimeError('Distribution contains old extension files. Use a new dist-edge-* directory.')
    for source in runtime:
        destination = dist / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    for name in INSTALLER_NAMES:
        shutil.copy2(ROOT / 'edge' / name, dist / name)
        copied.append(dist / name)
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, dist / name)
        copied.append(dist / name)
    shutil.copytree(notices, dist / 'licenses', dirs_exist_ok=True)
    for name in DOC_NAMES:
        if (ROOT / 'docs' / name).is_file():
            (dist / 'docs').mkdir(exist_ok=True)
            shutil.copy2(ROOT / 'docs' / name, dist / 'docs' / name)

    files = {path.relative_to(dist).as_posix(): digest(path) for path in sorted(copied)}
    info = {
        'application': 'SuishouReplyBridge', 'version': VERSION, 'format': 'onefile-console-stdio',
        'native_host': HOST_NAME, 'extension_id': EXTENSION_ID,
        'python': platform.python_version(), 'architecture': platform.machine(),
        'dependencies': {name: metadata.version(name) for name in (
            'PySide6-Essentials', 'shiboken6', 'pyinstaller', 'pyinstaller-hooks-contrib')},
        'executable': EXE_NAME, 'size_bytes': exe.stat().st_size, 'sha256': files[EXE_NAME],
        'runtime_sha256': files,
    }
    (dist / 'BUILD_INFO.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (dist / 'SHA256SUMS.txt').write_text(''.join(f'{value}  {name}\n' for name, value in sorted(files.items())), encoding='ascii')
    print(json.dumps({'dist': str(dist), 'exe': EXE_NAME, 'bytes': exe.stat().st_size, 'sha256': files[EXE_NAME]}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, metadata.PackageNotFoundError, subprocess.CalledProcessError) as exc:
        print(f'Edge build failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
