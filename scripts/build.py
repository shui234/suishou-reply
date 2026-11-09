"""Build a Windows x64 application from the current Python environment."""

from __future__ import annotations

import argparse
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

from make_icon import create_icon


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.0"


def build_environment() -> dict[str, str]:
    """Keep unrelated applications' DLLs out of PyInstaller's dependency scan.

    Qt 6.12 imports Windows' system ICU API. A Poppler/Conda ICU on the host
    PATH can have the same filename but incompatible, versioned exports.
    Preserve all other environment settings; change PATH only for the child.
    """
    environment = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    search = (
        Path(sys.executable).resolve().parent,
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "DLLs",
        windows / "System32",
        windows,
    )
    environment["PATH"] = os.pathsep.join(str(path) for path in search if path.is_dir())
    return environment


def collect_notices(destination: Path) -> None:
    """Preserve license files actually shipped by the installed distributions."""
    destination.mkdir(parents=True, exist_ok=True)
    bundled = ROOT / "licenses"
    if bundled.exists():
        shutil.copytree(bundled, destination, dirs_exist_ok=True)

    for name in ("PySide6-Essentials", "shiboken6", "pyinstaller"):
        distribution = metadata.distribution(name)
        package_dir = destination / f"{name}-{distribution.version}"
        package_dir.mkdir(exist_ok=True)
        manifest = {
            "name": distribution.metadata["Name"],
            "version": distribution.version,
            "license": distribution.metadata.get("License-Expression")
            or distribution.metadata.get("License"),
        }
        (package_dir / "METADATA.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for item in distribution.files or ():
            parts = item.parts
            is_license = any(part.lower() in {"licenses", "license", "copying"} for part in parts)
            is_license |= item.name.lower().startswith(("license", "copying", "copyright"))
            if not is_license:
                continue
            source = Path(distribution.locate_file(item))
            if not source.is_file():
                continue
            # Include the package's relative path so equal filenames never collide.
            safe_parts = [part for part in parts if part not in ("..", ".")]
            target = package_dir.joinpath(*safe_parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    for candidate in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
        if candidate.is_file():
            shutil.copy2(candidate, destination / "Python-LICENSE.txt")
            break


def write_version_info(path: Path) -> None:
    # PyInstaller uses a Python expression for the Win32 version resource.
    path.write_text("""VSVersionInfo(
  ffi=FixedFileInfo(filevers=(1, 1, 0, 0), prodvers=(1, 1, 0, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('080404B0', [
    StringStruct('FileDescription', '随手回 · X 互动与原创内容助手'),
    StringStruct('FileVersion', '1.1.0'),
    StringStruct('InternalName', 'SuishouReply'),
    StringStruct('OriginalFilename', 'SuishouReply.exe'),
    StringStruct('ProductName', '随手回'),
    StringStruct('ProductVersion', '1.1.0')
  ])]), VarFileInfo([VarStruct('Translation', [2052, 1200])])]
)
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SuishouReply for Windows x64")
    parser.add_argument("--onedir", action="store_true",
                        help="Keep libraries beside the executable for inspection/replacement")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / 'dist',
                        help="Output folder; use a separate folder while an older EXE is running")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        parser.error("Use 64-bit Python on Windows to build the Windows executable.")
    if not (3, 11) <= sys.version_info[:2] < (3, 16):
        parser.error("This dependency lock supports Python 3.11 through 3.15.")
    if not (ROOT / "main.py").is_file():
        parser.error(f"Application entry point is missing: {ROOT / 'main.py'}")

    build_dir = ROOT / "build"
    dist_dir = args.dist_dir.resolve()
    build_dir.mkdir(exist_ok=True)
    dist_dir.mkdir(exist_ok=True)
    icon = create_icon()
    notices = build_dir / "third-party-licenses"
    collect_notices(notices)
    version_file = build_dir / "version_info.txt"
    write_version_info(version_file)

    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir" if args.onedir else "--onefile", "--windowed",
        "--name", "SuishouReply", "--icon", str(icon),
        "--version-file", str(version_file),
        "--distpath", str(dist_dir), "--workpath", str(build_dir / "pyinstaller"),
        "--specpath", str(build_dir), "--log-level", "WARN",
        "--add-data", f"{icon};assets",
        "--add-data", f"{notices};licenses",
        "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.md'};.",
        "--add-data", f"{ROOT / 'suishou' / 'inspirations.json'};suishou",
        "--exclude-module", "tkinter", "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick", "--exclude-module", "PySide6.QtWebEngineCore",
        str(ROOT / "main.py"),
    ]
    print(f"Building SuishouReply {VERSION} with Python {platform.python_version()}...", flush=True)
    subprocess.run(command, check=True, cwd=ROOT, env=build_environment())

    executable = dist_dir / "SuishouReply.exe"
    if args.onedir:
        executable = dist_dir / "SuishouReply" / "SuishouReply.exe"
    if not executable.is_file():
        raise RuntimeError(f"Build finished without expected executable: {executable}")
    with executable.open("rb") as executable_file:
        digest = hashlib.file_digest(executable_file, "sha256").hexdigest()
    suffix = "-onedir" if args.onedir else ""
    manifest = {
        "application": "SuishouReply", "version": VERSION,
        "format": "onedir" if args.onedir else "onefile",
        "python": platform.python_version(), "architecture": platform.machine(),
        "dependencies": {name: metadata.version(name) for name in (
            "PySide6-Essentials", "shiboken6", "pyinstaller", "pyinstaller-hooks-contrib")},
        "executable": executable.relative_to(dist_dir).as_posix(),
        "size_bytes": executable.stat().st_size, "sha256": digest,
    }
    (dist_dir / f"BUILD_INFO{suffix}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dist_dir / f"SHA256SUMS{suffix}.txt").write_text(
        f"{digest}  {executable.relative_to(dist_dir).as_posix()}\n", encoding="ascii"
    )
    shutil.copytree(notices, dist_dir / "licenses", dirs_exist_ok=True)
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", dist_dir / "THIRD_PARTY_NOTICES.md")
    print(f"Built: {executable}\nSHA256: {digest}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, metadata.PackageNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
