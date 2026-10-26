from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from tarkov.map_math import tileRange
from tarkov.tiles import readTile


def stitchTiles(config, zoom, tileDir):
    # downloaded tiles into one image
    xMin, xMax, yMin, yMax = tileRange(config, zoom)
    size = config.tileSize
    image = QImage((xMax - xMin + 1) * size, (yMax - yMin + 1) * size,
                   QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    for y in range(yMin, yMax + 1):
        for x in range(xMin, xMax + 1):
            data = readTile(tileDir, config.key, zoom, x, y)
            if data is None:
                continue
            painter.drawImage((x - xMin) * size, (y - yMin) * size,
                              QImage.fromData(data))
    painter.end()
    return image, xMin, yMin