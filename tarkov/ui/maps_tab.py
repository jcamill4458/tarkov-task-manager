from PySide6.QtWidgets import (QWidget, QComboBox, QCheckBox, QListWidget,
                               QHBoxLayout, QVBoxLayout)

from tarkov.map_files import MAP_FILES, MAP_DIR
from tarkov.ui.map_view import MapView


class MapsTab(QWidget):
    def __init__(self, maps):
        super().__init__()
        # important
        self.maps = maps
        # widgets
        self.mapCombo = QComboBox()
        self.pmcBox = QCheckBox("PMC")
        self.scavBox = QCheckBox("Scav")
        self.pmcBox.setChecked(True)
        self.scavBox.setChecked(True)
        self.extractList = QListWidget()
        self.mapView = MapView()

        # map menu
        self.buildMapCombo()

        # connectors
        self.mapCombo.currentIndexChanged.connect(self.refresh)
        self.pmcBox.toggled.connect(self.refresh)
        self.scavBox.toggled.connect(self.refresh)

        # builds
        self.buildLayout()
        self.refresh()

    def buildMapCombo(self):
        for gameMap in sorted(self.maps.values(), key=lambda m: m.name):
            self.mapCombo.addItem(gameMap.name, gameMap.id)

    def buildLayout(self):
        topRow = QHBoxLayout()
        topRow.addWidget(self.mapCombo)
        topRow.addWidget(self.pmcBox)
        topRow.addWidget(self.scavBox)
        topRow.addStretch(1)

        layout = QHBoxLayout()
        leftLayout = QVBoxLayout()
        leftLayout.addLayout(topRow)
        leftLayout.addWidget(self.extractList)
        layout.addLayout(leftLayout)
        layout.addWidget(self.mapView)
        self.setLayout(layout)

    def refresh(self):
        self.extractList.clear()
        mapId = self.mapCombo.currentData()
        if mapId is None:
            return
        gameMap = self.maps[mapId]
        showPmc = self.pmcBox.isChecked()
        showScav = self.scavBox.isChecked()
        for extract in gameMap.extracts:
            if (extract.faction == "pmc" and showPmc) or (extract.faction == "scav" and showScav):
                self.extractList.addItem(extract.name)
        fileName = MAP_FILES.get(gameMap.name)
        if fileName:
            self.mapView.showMap(str(MAP_DIR / fileName))
        else:
            self.mapView.clearMap()
