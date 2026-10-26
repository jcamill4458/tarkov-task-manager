from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF, QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsPolygonItem,
                               QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QToolTip)

from tarkov.map_math import limitZoomOut
from tarkov.svg_layers import hideGroups

MARKER_RADIUS = 6
LABEL_BASE_SIZE = 12
LABEL_HALO = 1.8
ZOOM_OUT_LIMIT = 0.7
PIN_COLOR = "#ff4fd8"
PIN_ID = 0
PIN_NAME = 1


class MapView(QGraphicsView):
    pinContext = Signal(str, object)
    emptyContext = Signal(float, float, object)

    def __init__(self):
        super().__init__()
        self.mapScene = QGraphicsScene(self)
        self.setScene(self.mapScene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.svgText = ""
        self.renderer = None
        self.svgItem = None
        self.satelliteItems = []
        self.overlayItems = []

    def showMap(self, svgPath):
        self.clearMap()
        self.svgText = Path(svgPath).read_text(encoding="utf-8")
        self.renderer = QSvgRenderer(QByteArray(self.svgText.encode("utf-8")))
        self.svgItem = QGraphicsSvgItem()
        self.svgItem.setSharedRenderer(self.renderer)
        self.mapScene.addItem(self.svgItem)
        self.mapScene.setSceneRect(self.svgItem.boundingRect())
        self.resetTransform()
        self.fitInView(self.svgItem, Qt.AspectRatioMode.KeepAspectRatio)

    def setHiddenGroups(self, groupIds):
        if self.renderer is None:
            return
        text = hideGroups(self.svgText, groupIds)
        self.renderer.load(QByteArray(text.encode("utf-8")))
        self.svgItem.update()

    def clearMap(self):
        self.mapScene.clear()
        self.svgText = ""
        self.renderer = None
        self.svgItem = None
        self.satelliteItems = []
        self.overlayItems = []
        self.setBackgroundBrush(QBrush())

    def hasMap(self):
        return self.svgItem is not None

    def mapSize(self):
        rect = self.svgItem.boundingRect()
        return rect.width(), rect.height()

    def clearOverlay(self):
        for item in self.overlayItems:
            self.mapScene.removeItem(item)
        self.overlayItems = []

    def addMarker(self, x, y, color, name=""):
        dot = QGraphicsEllipseItem(-MARKER_RADIUS, -MARKER_RADIUS,
                                   MARKER_RADIUS * 2, MARKER_RADIUS * 2)
        dot.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIgnoresTransformations)
        dot.setBrush(QBrush(QColor(color)))
        dot.setPen(QPen(QColor("black"), 1.5))
        dot.setToolTip(name)
        dot.setPos(x, y)
        dot.setZValue(10)
        self.mapScene.addItem(dot)
        self.overlayItems.append(dot)

        if name:
            text = QGraphicsSimpleTextItem(name, dot)   # child of the dot: moves with it
            font = QFont()
            font.setPointSize(8)
            font.setBold(True)
            text.setFont(font)
            text.setBrush(QBrush(QColor(color)))
            text.setPen(QPen(QColor("black"), 0.8))
            rect = text.boundingRect()
            text.setPos(-rect.width() / 2, MARKER_RADIUS + 1)

    def addLabel(self, text, x, y, fontSize, rotation=0):
        item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPixelSize(LABEL_BASE_SIZE)
        item.setFont(font)
        item.setBrush(QBrush(QColor("white")))
        item.setPen(QPen(Qt.PenStyle.NoPen))
        halo = QGraphicsSimpleTextItem(text, item)
        halo.setFont(font)
        halo.setBrush(QBrush(QColor("black")))
        haloPen = QPen(QColor("black"), LABEL_HALO)
        haloPen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        halo.setPen(haloPen)
        halo.setFlag(QGraphicsSimpleTextItem.GraphicsItemFlag.ItemStacksBehindParent)
        rect = item.boundingRect()
        item.setTransformOriginPoint(rect.center())
        item.setScale(fontSize / LABEL_BASE_SIZE)
        item.setRotation(rotation)
        item.setPos(x - rect.center().x(), y - rect.center().y())
        item.setZValue(5)
        self.mapScene.addItem(item)
        self.overlayItems.append(item)

    def addObjectiveZone(self, corners, x, y, color, tooltip="", highlighted=False):
        shape = QGraphicsPolygonItem(QPolygonF([QPointF(cx, cy) for cx, cy in corners]))
        fill = QColor(color)
        fill.setAlpha(120 if highlighted else 60)
        shape.setBrush(QBrush(fill))
        pen = QPen(QColor(color), 3 if highlighted else 1.5)
        pen.setCosmetic(True)
        shape.setPen(pen)
        shape.setToolTip(tooltip)
        shape.setZValue(8 if highlighted else 7)
        self.mapScene.addItem(shape)
        self.overlayItems.append(shape)
        self.addObjectivePin(x, y, color, tooltip, highlighted)

    def addObjectivePin(self, x, y, color, tooltip="", highlighted=False):
        radius = MARKER_RADIUS + 3 if highlighted else MARKER_RADIUS - 1
        dot = QGraphicsEllipseItem(-radius, -radius, radius * 2, radius * 2)
        dot.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIgnoresTransformations)
        dot.setBrush(QBrush(QColor(color)))
        dot.setPen(QPen(QColor("white" if highlighted else "black"), 2 if highlighted else 1.5))
        dot.setToolTip(tooltip)
        dot.setPos(x, y)
        dot.setZValue(12 if highlighted else 11)
        self.mapScene.addItem(dot)
        self.overlayItems.append(dot)

    def addPin(self, x, y, pinId, name=""):
        size = MARKER_RADIUS + 2
        diamond = QGraphicsPolygonItem(QPolygonF([QPointF(0, -size * 1.3), QPointF(size, 0),
                                                  QPointF(0, size * 1.3), QPointF(-size, 0)]))
        diamond.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIgnoresTransformations)
        diamond.setBrush(QBrush(QColor(PIN_COLOR)))
        diamond.setPen(QPen(QColor("white"), 1.5))
        diamond.setData(PIN_ID, pinId)
        diamond.setData(PIN_NAME, name)
        diamond.setPos(x, y)
        diamond.setZValue(15)
        self.mapScene.addItem(diamond)
        self.overlayItems.append(diamond)

    def pinAt(self, viewPosition):
        for item in self.items(viewPosition):
            if item.data(PIN_ID):
                return item
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pin = self.pinAt(event.position().toPoint())
            if pin is not None:
                QToolTip.showText(event.globalPosition().toPoint(), pin.data(PIN_NAME) or "(no name)", self)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if self.svgItem is None:
            return
        pin = self.pinAt(event.pos())
        if pin is not None:
            self.pinContext.emit(pin.data(PIN_ID), event.globalPos())
        else:
            spot = self.mapToScene(event.pos())
            self.emptyContext.emit(spot.x(), spot.y(), event.globalPos())

    def showSatellite(self, layers):
        self.hideSatellite()
        for number, (pixmap, placement, opacity) in enumerate(layers):
            scaleX, scaleY, offsetX, offsetY = placement
            item = QGraphicsPixmapItem(pixmap)
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            item.setTransform(QTransform(scaleX, 0, 0, scaleY, offsetX, offsetY))
            item.setOpacity(opacity)
            item.setZValue(1 + number * 0.01)    # later layers sit on top
            self.mapScene.addItem(item)
            self.satelliteItems.append(item)
        self.svgItem.setVisible(False)
        self.setBackgroundBrush(QBrush(QColor("#1a1a1a")))

    def hideSatellite(self):
        for item in self.satelliteItems:
            self.mapScene.removeItem(item)
        self.satelliteItems = []
        if self.svgItem is not None:
            self.svgItem.setVisible(True)
        self.setBackgroundBrush(QBrush())

    def fitScale(self):
        rect = self.mapScene.sceneRect()
        view = self.viewport()
        return min(view.width() / rect.width(), view.height() / rect.height())

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if self.svgItem is not None and self.mapScene.sceneRect().width() > 0:
            factor = limitZoomOut(self.transform().m11(), factor, self.fitScale() * ZOOM_OUT_LIMIT)
        self.scale(factor, factor)