from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QComboBox, QCheckBox, QHBoxLayout, QInputDialog,
                               QMenu, QMessageBox, QProgressDialog, QPushButton, QVBoxLayout)

from tarkov.map_config import (GROUND, floorForHeight, floorGroupsToHide, normalizeName,
                               satelliteStack)
from tarkov.map_files import MAP_FILES, MAP_DIR
from tarkov.map_math import (canProject, clampZoom, labelFontSize, satelliteTransform,
                             svgToWorld, worldToSvg)
from tarkov.objective_map import locationsOnMap
from tarkov.tiles import downloadTiles, missingTiles
from tarkov.ui.map_view import MapView
from tarkov.ui.satellite import stitchTiles

SATELLITE_ZOOM = 4
GROUND_DIM = 0.6
FACTION_COLORS = {"pmc": "#2ecc71", "scav": "#f39c12"}


class MapPanel(QWidget):
    # map + controls
    changed = Signal()

    def __init__(self, maps, mapConfigs, tileDir, allowScav=True, pinBook=None):
        super().__init__()
        # important
        self.maps = maps
        self.mapConfigs = mapConfigs
        self.tileDir = tileDir
        self.pinBook = pinBook
        self.pinTaskId = None
        self.gameMap = None
        self.shownTiles = None
        self.objectives = []
        self.selectedObjectiveId = None
        self.home = None
        # widgets
        self.pmcBox = QCheckBox("PMC")
        self.scavBox = QCheckBox("Scav")
        self.labelsBox = QCheckBox("Labels")
        self.pinsBox = QCheckBox("Pins")
        self.satelliteBox = QCheckBox("Satellite")
        self.floorCombo = QComboBox()
        self.fullscreenButton = QPushButton("Fullscreen")
        self.mapView = MapView()
        self.escapeKey = QShortcut(QKeySequence("Escape"), self)    # leaves full screen
        self.escapeKey.setEnabled(False)
        self.pmcBox.setChecked(True)
        self.scavBox.setChecked(allowScav)
        self.scavBox.setVisible(allowScav)      # you can't complete tasks as a scav
        self.labelsBox.setChecked(True)
        self.pinsBox.setChecked(True)
        self.pinsBox.setVisible(pinBook is not None)

        # connectors
        self.pmcBox.toggled.connect(self.refresh)
        self.scavBox.toggled.connect(self.refresh)
        self.labelsBox.toggled.connect(self.refresh)
        self.pinsBox.toggled.connect(self.refresh)
        self.fullscreenButton.clicked.connect(self.toggleFullscreen)
        self.escapeKey.activated.connect(self.exitFullscreen)
        self.mapView.pinContext.connect(self.onPinContext)
        self.mapView.emptyContext.connect(self.onEmptyContext)
        if pinBook is not None:
            pinBook.subscribe(self.refresh)     # a pin added on another map view shows up here too
        self.satelliteBox.toggled.connect(self.onSatelliteToggled)
        self.floorCombo.currentIndexChanged.connect(self.onFloorChanged)

        # build
        self.buildLayout()
        self.buildFloorCombo(None)
        self.updateSatelliteAvailability()

    def buildLayout(self):
        topRow = QHBoxLayout()
        topRow.addWidget(self.pmcBox)
        topRow.addWidget(self.scavBox)
        topRow.addWidget(self.labelsBox)
        topRow.addWidget(self.pinsBox)
        topRow.addWidget(self.satelliteBox)
        topRow.addWidget(self.floorCombo)
        topRow.addStretch(1)
        topRow.addWidget(self.fullscreenButton)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(topRow)
        layout.addWidget(self.mapView, 1)
        self.setLayout(layout)

    # fullscreen (in-window)
    def toggleFullscreen(self):
        if self.home is None:
            self.enterFullscreen()
        else:
            self.exitFullscreen()

    def enterFullscreen(self):
        parent = self.parentWidget()
        layout = parent.layout() if parent is not None else None
        index = layout.indexOf(self) if layout is not None else -1
        if index < 0:
            return
        window = self.window()
        self.home = (parent, layout, index, layout.stretch(index), window)
        layout.removeWidget(self)
        self.setParent(window)
        self.setAutoFillBackground(True)
        self.setGeometry(window.rect())
        window.installEventFilter(self)
        self.raise_()
        self.show()
        self.fullscreenButton.setText("Exit fullscreen")
        self.escapeKey.setEnabled(True)

    def exitFullscreen(self):
        if self.home is None:
            return
        parent, layout, index, stretch, window = self.home
        self.home = None
        self.escapeKey.setEnabled(False)
        window.removeEventFilter(self)
        self.setAutoFillBackground(False)
        self.setParent(parent)
        layout.insertWidget(index, self, stretch)
        self.show()
        self.fullscreenButton.setText("Fullscreen")

    def eventFilter(self, watched, event):
        if self.home is not None and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return False

    # which map
    def currentConfig(self):
        if self.gameMap is None:
            return None
        config = self.mapConfigs.get(normalizeName(self.gameMap.name))
        if config is None or not canProject(config):
            return None
        return config

    def setMap(self, gameMap):
        if gameMap is self.gameMap:
            return
        self.gameMap = gameMap
        self.satelliteBox.blockSignals(True)
        self.satelliteBox.setChecked(False)
        self.satelliteBox.blockSignals(False)
        self.shownTiles = None

        fileName = MAP_FILES.get(gameMap.name) if gameMap is not None else None
        if fileName:
            self.mapView.showMap(str(MAP_DIR / fileName))
        else:
            self.mapView.clearMap()

        self.buildFloorCombo(self.currentConfig())
        self.applyFloor()
        self.updateSatelliteAvailability()
        self.refresh()

    # floors
    def buildFloorCombo(self, config):
        self.floorCombo.blockSignals(True)
        self.floorCombo.clear()
        self.floorCombo.addItem("Ground", None)
        selected = 0
        if config is not None and self.mapView.hasMap():
            for layer in config.layers:
                self.floorCombo.addItem(layer.name, layer)
                if layer.show:
                    selected = self.floorCombo.count() - 1
        self.floorCombo.setCurrentIndex(selected)
        self.floorCombo.setEnabled(self.floorCombo.count() > 1)
        self.floorCombo.blockSignals(False)

    def currentHeightRange(self):
        layer = self.floorCombo.currentData()
        if layer is None:
            return self.currentConfig().heightRange
        return layer.low, layer.high

    def applyFloor(self):
        config = self.currentConfig()
        if config is None or not self.mapView.hasMap():
            return
        self.mapView.setHiddenGroups(floorGroupsToHide(config, self.floorCombo.currentData()))

    def onFloorChanged(self):
        self.applyFloor()
        self.updateSatelliteAvailability()
        if self.satelliteBox.isChecked():
            if not self.satelliteBox.isEnabled() or not self.showSatellite():
                self.uncheckSatellite()
        self.refresh()

    def showFloorFor(self, location):
        config = self.currentConfig()
        if config is None or not self.mapView.hasMap():
            return
        target = floorForHeight(config, location.height())
        if target is None:
            return
        for index in range(self.floorCombo.count()):
            layer = self.floorCombo.itemData(index)
            if (target == GROUND and layer is None) or (target != GROUND and layer is target):
                if index != self.floorCombo.currentIndex():
                    self.floorCombo.setCurrentIndex(index)
                return

    # satellite
    def currentSatelliteStack(self):
        config = self.currentConfig()
        if config is None or not self.mapView.hasMap():
            return []
        return satelliteStack(config, self.floorCombo.currentData())

    def updateSatelliteAvailability(self):
        self.satelliteBox.setEnabled(bool(self.currentSatelliteStack()))

    def uncheckSatellite(self):
        self.satelliteBox.blockSignals(True)
        self.satelliteBox.setChecked(False)
        self.satelliteBox.blockSignals(False)
        self.mapView.hideSatellite()
        self.shownTiles = None

    def onSatelliteToggled(self, checked):
        if not checked:
            self.mapView.hideSatellite()
            self.shownTiles = None
        elif not self.showSatellite():
            self.uncheckSatellite()

    def showSatellite(self):
        stack = self.currentSatelliteStack()
        if not stack:
            return False
        tiles = tuple(config.key for config in stack)
        if tiles == self.shownTiles:
            return True
        width, height = self.mapView.mapSize()
        layers = []
        for number, config in enumerate(stack):
            zoom = clampZoom(config, SATELLITE_ZOOM)
            if not self.downloadMissingTiles(config, zoom):
                return False
            image, firstX, firstY = stitchTiles(config, zoom, self.tileDir)
            placement = satelliteTransform(config, zoom, firstX, firstY, width, height)
            dim = GROUND_DIM if number == 0 and len(stack) > 1 else 1
            layers.append((QPixmap.fromImage(image), placement, dim))
        self.mapView.showSatellite(layers)
        self.shownTiles = tiles
        return True

    def downloadMissingTiles(self, config, zoom):
        todo = missingTiles(config, zoom, self.tileDir)
        if not todo:
            return True
        dialog = QProgressDialog("Downloading satellite tiles...", "Cancel", 0, len(todo), self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)

        def onProgress(done, total):
            dialog.setValue(done)
            QApplication.processEvents()
            return not dialog.wasCanceled()

        try:
            finished = downloadTiles(config, zoom, self.tileDir, onProgress)
        except OSError as error:   # network and disk errors both end up here
            dialog.close()
            QMessageBox.warning(self, "Satellite", f"Couldn't download the tiles:\n{error}")
            return False
        dialog.close()
        return finished

    # map drawing
    def isShown(self, extract):
        return ((extract.faction == "pmc" and self.pmcBox.isChecked())
                or (extract.faction == "scav" and self.scavBox.isChecked()))

    def shownExtracts(self):
        if self.gameMap is None:
            return []
        return [e for e in self.gameMap.extracts if self.isShown(e)]

    def setObjectives(self, objectives, selectedId=None):
        self.objectives = objectives
        self.selectedObjectiveId = selectedId
        self.refresh()

    def selectObjective(self, objectiveId):
        self.selectedObjectiveId = objectiveId
        if self.gameMap is not None:
            for objective, _ in self.objectives:
                if objective.id == objectiveId:
                    places = locationsOnMap(objective, self.gameMap.id)
                    if places:
                        self.showFloorFor(places[0])
        self.refresh()

    def setPinScope(self, taskId):
        self.pinTaskId = taskId

    def visiblePins(self):
        if self.pinBook is None or self.gameMap is None or not self.pinsBox.isChecked():
            return []
        return self.pinBook.forMap(self.gameMap.id, self.pinTaskId)

    def onEmptyContext(self, x, y, globalPosition):
        config = self.currentConfig()
        width, height = self.mapView.mapSize()
        if self.pinBook is None or config is None or not (0 <= x <= width and 0 <= y <= height):
            return
        menu = QMenu(self)
        addAction = menu.addAction("Add pin here...")
        if menu.exec(globalPosition) is not addAction:
            return
        name, accepted = QInputDialog.getText(self, "New pin", "Name (optional):")
        if accepted:
            worldX, worldZ = svgToWorld(x, y, config, width, height)
            self.pinsBox.blockSignals(True)
            self.pinsBox.setChecked(True)
            self.pinsBox.blockSignals(False)
            self.pinBook.add(self.gameMap.id, worldX, worldZ, name, self.pinTaskId)

    def onPinContext(self, pinId, globalPosition):
        if self.pinBook is None or pinId not in self.pinBook.pins:
            return
        menu = QMenu(self)
        renameAction = menu.addAction("Rename...")
        removeAction = menu.addAction("Remove pin")
        chosen = menu.exec(globalPosition)
        if chosen is renameAction:
            name, accepted = QInputDialog.getText(self, "Rename pin", "Name (optional):",
                                                  text=self.pinBook.pins[pinId].name)
            if accepted:
                self.pinBook.rename(pinId, name)
        elif chosen is removeAction:
            self.pinBook.remove(pinId)

    def refresh(self):
        self.drawOverlay(self.shownExtracts())
        self.changed.emit()

    def drawOverlay(self, extracts):
        self.mapView.clearOverlay()
        config = self.currentConfig()
        if config is None or not self.mapView.hasMap():
            return
        width, height = self.mapView.mapSize()
        low, high = self.currentHeightRange()
        for extract in extracts:
            x, y = worldToSvg(extract.x, extract.z, config, width, height)
            self.mapView.addMarker(x, y, FACTION_COLORS[extract.faction], extract.name)
        if self.labelsBox.isChecked():
            for label in config.labels:
                if label.visibleIn(low, high):
                    x, y = worldToSvg(label.x, label.z, config, width, height)
                    self.mapView.addLabel(label.text, x, y,
                                          labelFontSize(config, label, width), label.rotation)
        for objective, color in self.objectives:
            highlighted = objective.id == self.selectedObjectiveId
            for place in locationsOnMap(objective, self.gameMap.id):
                x, y = worldToSvg(place.x, place.z, config, width, height)
                if place.outline:
                    corners = [worldToSvg(cx, cz, config, width, height) for cx, cz in place.outline]
                    self.mapView.addObjectiveZone(corners, x, y, color, objective.description, highlighted)
                else:
                    self.mapView.addObjectivePin(x, y, color, objective.description, highlighted)
        for pin in self.visiblePins():
            x, y = worldToSvg(pin.x, pin.z, config, width, height)
            self.mapView.addPin(x, y, pin.id, pin.name)