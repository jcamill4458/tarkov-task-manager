from PySide6.QtWidgets import QWidget, QComboBox, QLabel, QHBoxLayout, QVBoxLayout

from tarkov.objective_map import locationsOnMap, mapForObjective, objectiveColor, taskMaps
from tarkov.ui.map_panel import MapPanel


class TaskMapView(QWidget):
    # individual task map view
    def __init__(self, maps, mapConfigs, tileDir, pinBook=None):
        super().__init__()
        # important
        self.maps = maps
        self.taskId = None
        self.task = None
        self.selectedObjectiveId = None
        # widgets
        self.mapCombo = QComboBox()
        self.noteLabel = QLabel()
        self.panel = MapPanel(maps, mapConfigs, tileDir, allowScav=False, pinBook=pinBook)

        # connectors
        self.mapCombo.currentIndexChanged.connect(self.onMapChosen)

        # build
        self.buildLayout()

    def buildLayout(self):
        topRow = QHBoxLayout()
        topRow.addWidget(self.mapCombo)
        topRow.addWidget(self.noteLabel, 1)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(topRow)
        layout.addWidget(self.panel, 1)
        self.setLayout(layout)

    def showTask(self, task, selectedObjectiveId=None):
        self.task = task
        self.selectedObjectiveId = selectedObjectiveId
        if task.id != self.taskId:
            self.taskId = task.id
            self.panel.setPinScope(task.id)     # this task's pins only
            self.buildMapCombo(task)
        if self.mapCombo.count() == 0:
            return False
        self.showMap()
        return True

    def buildMapCombo(self, task):
        self.mapCombo.blockSignals(True)
        self.mapCombo.clear()
        chosen = 0
        found = False
        for number, gameMap in enumerate(taskMaps(task, self.maps)):
            self.mapCombo.addItem(gameMap.name, gameMap.id)
            hasPlaces = any(locationsOnMap(o, gameMap.id) for o in task.objectives)
            if hasPlaces and not found:
                chosen = number
                found = True
        self.mapCombo.setCurrentIndex(chosen)
        self.mapCombo.blockSignals(False)

    def onMapChosen(self):
        self.showMap()

    def showMap(self):
        mapId = self.mapCombo.currentData()
        gameMap = self.maps.get(mapId)
        self.panel.setMap(gameMap)
        coloured = [(objective, objectiveColor(number))
                    for number, objective in enumerate(self.task.objectives)]
        self.panel.setObjectives(coloured, self.selectedObjectiveId)
        placed = sum(1 for objective in self.task.objectives if locationsOnMap(objective, mapId))
        if placed:
            self.noteLabel.setText(f"{placed} objective(s) with places on this map")
        else:
            self.noteLabel.setText("No place data for this task's objectives here")

    def selectObjective(self, objectiveId):
        self.selectedObjectiveId = objectiveId
        objective = next((o for o in self.task.objectives if o.id == objectiveId), None)
        if objective is None:
            return
        target = mapForObjective(objective, self.mapCombo.currentData(), self.maps)
        if target is not None and target != self.mapCombo.currentData():
            self.mapCombo.setCurrentIndex(self.mapCombo.findData(target))
        self.panel.selectObjective(objectiveId)