from PySide6.QtWidgets import QWidget, QComboBox, QListWidget, QHBoxLayout, QVBoxLayout

from tarkov.ui.map_panel import MapPanel


class MapsTab(QWidget):
    def __init__(self, maps, mapConfigs, tileDir, pinBook=None):
        super().__init__()
        # important
        self.maps = maps
        # widgets
        self.mapCombo = QComboBox()
        self.extractList = QListWidget()
        self.panel = MapPanel(maps, mapConfigs, tileDir, pinBook=pinBook)

        # map menu
        self.buildMapCombo()

        # connectors
        self.mapCombo.currentIndexChanged.connect(self.onMapChanged)
        self.panel.changed.connect(self.refreshList)

        # builds
        self.buildLayout()
        self.onMapChanged()

    def buildMapCombo(self):
        for gameMap in sorted(self.maps.values(), key=lambda m: m.name):
            self.mapCombo.addItem(gameMap.name, gameMap.id)

    def buildLayout(self):
        layout = QHBoxLayout()
        leftLayout = QVBoxLayout()
        leftLayout.addWidget(self.mapCombo)
        leftLayout.addWidget(self.extractList)
        layout.addLayout(leftLayout, 1)
        layout.addWidget(self.panel, 3)   # the map gets most of the room
        self.setLayout(layout)

    def currentMap(self):
        mapId = self.mapCombo.currentData()
        if mapId is None:
            return None
        return self.maps[mapId]

    def onMapChanged(self):
        self.panel.setMap(self.currentMap())

    def refreshList(self):
        self.extractList.clear()
        for extract in self.panel.shownExtracts():
            self.extractList.addItem(extract.name)