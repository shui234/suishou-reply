import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session')
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app
    # Qt's offscreen clipboard can crash at interpreter shutdown when it still
    # owns a Python-created QMimeData. Release synthetic test clipboard data
    # while QApplication is alive; never clear the native user clipboard here.
    if app.platformName() == 'offscreen':
        app.clipboard().clear()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
