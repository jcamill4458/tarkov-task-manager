from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

class MapView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.mapScene = QGraphicsScene(self)
        self.setScene(self.mapScene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def showMap(self, svgPath):
        self.mapScene.clear()
        item = QGraphicsSvgItem(svgPath)
        self.mapScene.addItem(item)
        self.mapScene.setSceneRect(item.boundingRect())
        self.resetTransform()
        self.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)

    def clearMap(self):
        self.mapScene.clear()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)