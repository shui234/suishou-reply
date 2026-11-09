import argparse
import getpass
import hashlib
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='随手回 · X 互动与原创内容助手')
    parser.add_argument('--demo', action='store_true', help='离线演示，不保存密钥或访问网络')
    parser.add_argument('--self-test', action='store_true', help='运行离线剪贴板完整流程自检')
    parser.add_argument('--smoke-test', action='store_true', help='短暂运行离线界面后退出')
    parser.add_argument('--report', type=Path, help='自检结果 JSON 输出路径')
    parser.add_argument('--screenshot', type=Path, help='自检模拟回复窗口截图')
    args = parser.parse_args()
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtNetwork import QLocalServer, QLocalSocket, QNetworkProxyFactory
    from .runtime import AppRuntime
    app = QApplication(sys.argv[:1])
    app.setApplicationName('SuishouReply')
    app.setApplicationDisplayName('随手回')
    app.setOrganizationName('SuishouReply')
    from . import __version__
    app.setApplicationVersion(__version__)
    QNetworkProxyFactory.setUseSystemConfiguration(True)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont('Microsoft YaHei UI', 10))

    if args.self_test:
        from .selftest import run_self_test
        result = run_self_test(app, args.screenshot)
        import json
        report = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(report, encoding='utf-8')
        if sys.stdout:
            print(report)
        return 0 if result['passed'] else 1

    # Local IPC prevents two tray instances from both sending paid API requests.
    server = None
    if not args.smoke_test:
        user_scope = hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
        name = 'SuishouReply-v1-' + user_scope + ('-demo' if args.demo else '')
        socket = QLocalSocket()
        socket.connectToServer(name)
        if socket.waitForConnected(150):
            socket.write(b'show')
            socket.waitForBytesWritten(150)
            socket.disconnectFromServer()
            return 0
        socket.abort()
        server = QLocalServer()
        if not server.listen(name):
            QMessageBox.information(None, '随手回', '应用可能已在运行，请检查系统托盘。')
            return 1

    runtime = AppRuntime(app, demo=args.demo or args.smoke_test)
    if server:
        def accept_connection():
            while server.hasPendingConnections():
                connection = server.nextPendingConnection()
                connection.close()
                connection.deleteLater()
                runtime.window.present()
        server.newConnection.connect(accept_connection)

    def safe_error(exc_type, exc_value, traceback):
        # Avoid tracebacks, HTTP bodies, or local variables leaking secrets into logs.
        runtime.controller.set_listening(False)
        runtime.original_controller.cancel()
        runtime.window.show_error('发生意外错误，监听已暂停。请重启应用后重试。')
        runtime.window.present()
    sys.excepthook = safe_error
    QTimer.singleShot(0, runtime.start)
    if args.smoke_test:
        QTimer.singleShot(1800, app.quit)
    code = app.exec()
    runtime.cleanup()
    if server:
        server.close()
    return code
