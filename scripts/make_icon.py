"""Create the application's small geometric icon using Qt, without Pillow."""

from __future__ import annotations

import os
from pathlib import Path
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen


ROOT = Path(__file__).resolve().parents[1]


def draw_icon(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 256, size / 256)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#141A24"))
    painter.drawRoundedRect(QRectF(4, 4, 248, 248), 66, 66)

    bubble = QPainterPath()
    bubble.addRoundedRect(QRectF(43, 49, 170, 134), 33, 33)
    bubble.moveTo(81, 170)
    bubble.lineTo(69, 210)
    bubble.lineTo(119, 178)
    bubble.closeSubpath()
    painter.setBrush(QColor("#76E0BA"))
    painter.drawPath(bubble)

    painter.setPen(QPen(QColor("#14251F"), 16, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    arrow = QPainterPath(QPointF(171, 133))
    arrow.cubicTo(173, 106, 146, 102, 108, 106)
    painter.drawPath(arrow)
    painter.drawLine(QPointF(108, 106), QPointF(127, 87))
    painter.drawLine(QPointF(108, 106), QPointF(128, 124))
    painter.end()
    return image


def create_icon(destination: Path | None = None) -> Path:
    # Keep a reference until all images have been rendered.
    app = QGuiApplication.instance() or QGuiApplication([])
    destination = destination or ROOT / "assets" / "app.ico"
    destination.parent.mkdir(parents=True, exist_ok=True)
    sizes = (16, 24, 32, 48, 64, 128, 256)
    payloads: list[bytes] = []
    for size in sizes:
        data = QByteArray()
        buffer = QBuffer(data)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError("Could not create icon image buffer")
        if not draw_icon(size).save(buffer, "PNG"):
            raise RuntimeError("Qt could not encode icon image")
        buffer.close()
        payloads.append(bytes(data))

    offset = 6 + 16 * len(sizes)
    entries: list[bytes] = []
    for size, payload in zip(sizes, payloads):
        dimension = 0 if size == 256 else size
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0,
                                   1, 32, len(payload), offset))
        offset += len(payload)
    destination.write_bytes(
        struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries) + b"".join(payloads)
    )
    # A PNG is convenient for inspecting the icon and documentation.
    if not draw_icon(256).save(str(destination.with_suffix(".png")), "PNG"):
        raise RuntimeError("Qt could not save the PNG icon")
    _ = app
    return destination


if __name__ == "__main__":
    print(create_icon())
