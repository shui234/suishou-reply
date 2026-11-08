# Third-party components / 第三方组件说明

随手回使用下列第三方组件。它们的著作权属于各自作者，许可不因本应用打包而改变。构建时的精确版本见 `dist/BUILD_INFO.json`。

| Component | Version in dependency lock | License / source |
| --- | --- | --- |
| Python | Recorded at build time | Python Software Foundation License; [CPython](https://github.com/python/cpython) |
| Qt for Python / PySide6 Essentials | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only, as declared by the installed distribution; [Qt for Python source](https://code.qt.io/cgit/pyside/pyside-setup.git/) |
| Shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only, as declared by the installed distribution; [Shiboken source](https://code.qt.io/cgit/pyside/pyside-setup.git/) |
| Qt Core / Gui / Widgets / Network and runtime plugins | Shipped by the Qt for Python wheel | LGPLv3 and the respective third-party terms; [Qt source](https://code.qt.io/cgit/qt/) |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later with the PyInstaller exception; [PyInstaller](https://github.com/pyinstaller/pyinstaller) |

The Qt Toolkit is Copyright (C) The Qt Company Ltd. and other contributors. This application uses Qt and Qt for Python under the GNU Lesser General Public License version 3. Copies of LGPLv3 and GPLv3 accompany the source and packaged distribution in `licenses/`. Other license choices in package metadata are listed for provenance; no commercial Qt license is claimed.

`scripts/build.py` also copies the license files actually present in the installed Python, PySide6, Shiboken6 and PyInstaller distributions, along with their package license metadata. The PySide6 and Shiboken wheels may carry a file named `LicenseRef-Qt-Commercial.txt`; retaining this upstream file does not mean this application uses a commercial Qt license.

Official references:

- [Licenses used in Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt LGPLv3 text](https://doc.qt.io/qt-6/lgpl.html)
- [Qt third-party code and license overview](https://doc.qt.io/qt-6/licenses-used-in-qt.html)
- [Qt source archive](https://download.qt.io/archive/qt/)
- [Qt for Python source archive](https://download.qt.io/official_releases/QtForPython/)
- [PyInstaller license and bundling exception](https://pyinstaller.org/en/stable/license.html)

## Rebuilding with modified Qt libraries

The delivered project contains the application's Python source and packaging scripts. To use a compatible modified Qt / PySide6 installation, create a separate Python environment, install those libraries and PyInstaller there, and invoke that environment's Python directly:

```powershell
& C:\path\to\your\environment\Scripts\python.exe scripts\build.py --onedir
```

Do not use `start.bat` or `build.bat` with that customized environment: their purpose is to restore the project's fixed dependency lock. `scripts/build.py` itself records the packages actually installed and does not reinstall the lock. In the directory build, the dynamic libraries remain visible beneath the output directory. For a single-file build, omit `--onedir` to rebuild the executable with your replacement libraries.

This project does not impose restrictions on modifications to its LGPL-covered library portions or reverse engineering for debugging such modifications. Preserve the applicable notices and corresponding source/build materials when redistributing a combined work. Exact obligations are specified by the accompanying upstream license texts.
