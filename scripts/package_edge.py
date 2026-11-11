"""Allowlisted Edge distribution; never collect a dirty repository wholesale."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_edge import DOC_NAMES, EXE_NAME, EXTENSION_ID, HOST_NAME, INSTALLER_NAMES, ROOT, VERSION, digest, extension_files

SOURCE_NAMES = (
    'edge_host.py', 'suishou/__init__.py', 'suishou/edge_bridge.py', 'suishou/edge_protocol.py', 'suishou/api.py',
    'suishou/config.py', 'suishou/prompts.py', 'suishou/credentials.py',
    'requirements.txt', 'requirements-dev.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
    'scripts/build_edge.py', 'scripts/package_edge.py', 'scripts/build.py', 'scripts/make_icon.py', 'tests/conftest.py',
)


def selected_sources(root: Path = ROOT) -> list[Path]:
    files = [root / name for name in SOURCE_NAMES]
    files.extend(root / 'edge' / name for name in INSTALLER_NAMES)
    files.extend(extension_files(root))
    for name in ('package.json', 'package-lock.json'):
        if (root / 'extension' / name).is_file():
            files.append(root / 'extension' / name)
    for folder, patterns in (('extension/tests', ('*.js', '*.cjs', '*.html', '*.json')),
                             ('tests', ('test_edge_*.py',)), ('licenses', ('*',))):
        for pattern in patterns:
            files.extend(path for path in (root / folder).rglob(pattern)
                         if path.is_file() and not any(part in {'node_modules', '__pycache__'} for part in path.parts))
    files.extend(root / 'docs' / name for name in DOC_NAMES if (root / 'docs' / name).is_file())
    for path in files:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('A required source file is missing or resolves outside the project.')
        if any('backup' in part.lower() or part in {'node_modules', '.git'} for part in path.relative_to(root).parts):
            raise ValueError('Backup or dependency cache selected as source.')
        if path.suffix.lower() in {'.pem', '.key', '.log', '.exe', '.dll', '.pyc'}:
            raise ValueError('Private or generated file selected as source.')
    return sorted(set(files))


def verified_runtime(dist: Path) -> list[Path]:
    info = json.loads((dist / 'BUILD_INFO.json').read_text(encoding='utf-8'))
    expected = {EXE_NAME, 'LICENSE', 'THIRD_PARTY_NOTICES.md', *INSTALLER_NAMES}
    expected.update(path.relative_to(ROOT).as_posix() for path in extension_files())
    if (info.get('version') != VERSION or info.get('extension_id') != EXTENSION_ID
            or info.get('native_host') != HOST_NAME or info.get('executable') != EXE_NAME
            or set(info.get('runtime_sha256', {})) != expected):
        raise ValueError('Build identity or runtime inventory mismatch; rebuild before packaging.')
    for name, recorded in info['runtime_sha256'].items():
        path = dist / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(dist.resolve()) or digest(path) != recorded:
            raise ValueError('Built runtime checksum mismatch; rebuild before packaging.')
        if name.startswith('extension/') or name in INSTALLER_NAMES:
            source = ROOT / name if name.startswith('extension/') else ROOT / 'edge' / name
            if digest(source) != recorded:
                raise ValueError('Runtime no longer matches current source; rebuild before packaging.')
    if info.get('sha256') != digest(dist / EXE_NAME) or info.get('size_bytes') != (dist / EXE_NAME).stat().st_size:
        raise ValueError('Bridge checksum or size differs from the build record.')
    files = [dist / name for name in sorted(expected | {'BUILD_INFO.json', 'SHA256SUMS.txt'})]
    files.extend(path for path in sorted((dist / 'licenses').rglob('*')) if path.is_file())
    if not (dist / 'licenses').is_dir():
        raise ValueError('Dependency licenses are missing.')
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description='Package the separate Edge extension and native companion')
    parser.add_argument('--dist-dir', type=Path, default=ROOT / f'dist-edge-v{VERSION}')
    parser.add_argument('--output-dir', type=Path, default=ROOT.parent)
    args = parser.parse_args()
    dist, output = args.dist_dir.resolve(), args.output_dir.resolve()
    runtime = verified_runtime(dist)
    sources = selected_sources()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'SuishouReply-{VERSION}-Edge-Windows.zip'
    temporary = archive.with_suffix('.zip.partial')
    prefix = f'SuishouReply-{VERSION}-Edge'
    entries = {}
    for path in runtime:
        entries[f'{prefix}/{path.relative_to(dist).as_posix()}'] = path
    for name in DOC_NAMES:
        if (ROOT / 'docs' / name).is_file():
            entries[f'{prefix}/docs/{name}'] = ROOT / 'docs' / name
    for path in sources:
        entries[f'{prefix}/source/{path.relative_to(ROOT).as_posix()}'] = path
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for name, path in sorted(entries.items()):
            package.write(path, name)
        package.writestr(f'{prefix}/source/README-REBUILD.md',
            '# Rebuild the Edge companion\n\n'
            'This source subset contains the complete Edge extension and native bridge, including the reused desktop API, prompts, settings and credential modules. '
            'It does not replace the full desktop project: https://github.com/shui234/suishou-reply .\n\n'
            'Use Windows x64 and Python 3.11-3.15 (verified environment: Python 3.14.4). From this source folder:\n\n'
            '```powershell\npython -m venv .venv\n.\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt\n'
            '.\\.venv\\Scripts\\python.exe scripts\\build_edge.py\n```\n\n'
            f'The build writes only dist-edge-v{VERSION}. Install that folder in place and load its extension subfolder in Edge. '
            'Configure the existing DeepSeek key using the desktop application. The bridge never asks the browser for secrets.\n')
    with zipfile.ZipFile(temporary) as package:
        if package.testzip() is not None:
            raise RuntimeError('ZIP CRC validation failed.')
        count = len(package.infolist())
        if len({item.filename for item in package.infolist()}) != count:
            raise RuntimeError('Duplicate ZIP entries.')
    os.replace(temporary, archive)
    value = digest(archive)
    checksum = output / f'SuishouReply-{VERSION}-Edge-SHA256.txt'
    checksum.write_text(f'{value}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'entries': count, 'bytes': archive.stat().st_size, 'sha256': value}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'Edge packaging failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
