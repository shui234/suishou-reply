"""Package current source plus a verified build; keep binaries out of Git."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from suishou import __version__


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Package SuishouReply source + Windows EXE')
    parser.add_argument('--dist-dir', type=Path, default=ROOT / 'dist')
    parser.add_argument('--output-dir', type=Path, default=ROOT.parent)
    args = parser.parse_args()
    dist = args.dist_dir.resolve()
    info = json.loads((dist / 'BUILD_INFO.json').read_text(encoding='utf-8'))
    exe = dist / 'SuishouReply.exe'
    if info['version'] != __version__ or info['sha256'] != digest(exe):
        raise SystemExit('Build version/hash mismatch; rebuild before packaging.')
    sources = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                      '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    forbidden_dirs = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'build', 'dist', 'work'}
    forbidden_names = {'settings.json', 'original-history.json', '.env'}
    files = []
    for relative in sorted(set(filter(None, sources))):
        path = Path(relative)
        if (any(part in forbidden_dirs or part.startswith('dist-') for part in path.parts)
                or path.name in forbidden_names or path.name.startswith('.env.')
                or path.suffix.lower() in {'.exe', '.zip', '.dll', '.pyd', '.log', '.tmp', '.pyc', '.pem', '.key'}):
            raise SystemExit('Unsafe source file selected; check Git tracking/ignore rules.')
        source = ROOT / path
        if source.is_file():
            files.append((source, 'SuishouReply/' + path.as_posix()))
    for path in sorted(dist.rglob('*')):
        if path.is_file():
            relative = path.relative_to(dist)
            if relative.parts[0] not in {'SuishouReply.exe', 'BUILD_INFO.json', 'SHA256SUMS.txt',
                                        'THIRD_PARTY_NOTICES.md', 'licenses'}:
                raise SystemExit('Unexpected distribution file; inspect before packaging.')
            files.append((path, 'SuishouReply/dist/' + relative.as_posix()))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'SuishouReply-{__version__}-Windows.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path, name in files:
            package.write(path, name)
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise SystemExit('ZIP integrity check failed.')
    checksum = output / f'SuishouReply-{__version__}-SHA256.txt'
    checksum.write_text(f'{digest(archive)}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'entries': len(files),
                      'bytes': archive.stat().st_size, 'sha256': digest(archive)}, indent=2))


if __name__ == '__main__':
    main()
