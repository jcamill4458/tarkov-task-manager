from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QAction, QKeySequence
from PySide6.QtWidgets import (QWidget, QListWidget, QCheckBox, QToolButton, QHBoxLayout, QVBoxLayout, QMenu, QLabel,
                               QListWidgetItem, QPushButton)
from tarkov.objective_map import objectiveColor, taskMaps
from tarkov.ui.objective_row import ObjectiveRow
from tarkov.ui.task_map import TaskMapView

class TraderTab(QWidget):
    def __init__(self, trader, tracker, maps=None, mapConfigs=None, tileDir=None, pinBook=None):
        super().__init__()
        # important
        self.trader = trader
        self.tracker = tracker
        self.maps = maps
        self.mapConfigs = mapConfigs
        self.tileDir = tileDir
        self.pinBook = pinBook
        self.currentTaskId = None
        self.selectedObjectiveId = None
        self.taskMap = None
        # left widgets
        self.taskList = QListWidget()
        self.showCompleted = QCheckBox("Show Completed")
        self.tasksButton = QToolButton()
        self.menu = QMenu()
        self.action = QAction()
        self.action.setShortcut(QKeySequence("t"))
        self.action.triggered.connect(self.tasksButton.showMenu)
        self.tasksButton.setDefaultAction(self.action)
        self.tasksButton.setText("Tasks ")
        # right widgets
        self.titleLabel = QLabel("Select a task")
        self.starButton = QPushButton("☆")
        self.starButton.setEnabled(False)
        self.starButton.setStyleSheet("padding: 3px; margin: 3px;")
        self.wikiButton = QPushButton("Wiki")
        self.wikiButton.setEnabled(False)
        self.wikiButton.setStyleSheet("padding: 3px; margin: 2px;")
        self.completeButton = QPushButton("Mark complete")
        self.completeButton.setEnabled(False)
        self.objectivesLayout = QVBoxLayout()
        self.mapSlot = QVBoxLayout()

        # connectors
        self.showCompleted.toggled.connect(self.refreshList)
        self.taskList.currentItemChanged.connect(self.onTaskSelected)
        self.wikiButton.clicked.connect(self.openWiki)
        self.starButton.clicked.connect(self.onStarClicked)
        self.completeButton.clicked.connect(self.onCompleteClicked)

        # build
        self.buildLayout()
        self.refreshList()
        self.buildTasksMenu()

    def buildLeft(self):
        leftLayout = QVBoxLayout()
        topRow = QHBoxLayout()
        topRow.addWidget(self.showCompleted)
        topRow.addStretch(1)
        topRow.addWidget(self.tasksButton)
        leftLayout.addLayout(topRow)
        leftLayout.addWidget(self.taskList)
        return leftLayout

    def buildRight(self):
        rightLayout = QVBoxLayout()
        topRow = QHBoxLayout()
        topRow.addWidget(self.titleLabel)
        topRow.addStretch(1)
        topRow.addWidget(self.starButton)
        topRow.addWidget(self.wikiButton)
        topRow.addWidget(self.completeButton)
        rightLayout.addLayout(topRow)
        rightLayout.addLayout(self.objectivesLayout)
        rightLayout.addLayout(self.mapSlot, 1)    # the task's map takes the rest of the room
        return rightLayout


    def buildLayout(self):
        layout = QHBoxLayout()
        left = self.buildLeft()
        right = self.buildRight()
        layout.addLayout(left, 5)
        layout.addLayout(right, 7)
        self.setLayout(layout)

    def buildTasksMenu(self):
        for task in self.tracker.allTasksForTrader(self.trader.id):
            action = self.menu.addAction(task.name)
            action.setCheckable(True)
            action.setChecked(self.tracker.isAvailable(task.id))
            action.toggled.connect(lambda checked, taskId=task.id: self.onTaskToggled(taskId))
        self.tasksButton.setMenu(self.menu)
        self.tasksButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def onTaskToggled(self, taskId):
        self.tracker.toggleAvailable(taskId)
        self.refreshList()

    def onTaskSelected(self, current, previous):
        if current is None: return
        taskId = current.data(Qt.ItemDataRole.UserRole)
        if taskId != self.currentTaskId:
            self.selectedObjectiveId = None
        self.currentTaskId = taskId
        self.updateDetail()

    def openWiki(self):
        task = self.tracker.tasks[self.currentTaskId]
        QDesktopServices.openUrl(QUrl(task.wikiUrl))

    def onStarClicked(self):
        self.tracker.toggleStar(self.currentTaskId)
        self.refreshList()

    def onCompleteClicked(self):
        done = self.tracker.isCompleted(self.currentTaskId)
        self.tracker.setComplete(self.currentTaskId, not done)
        self.refreshList()

    def onObjectiveChanged(self, objectiveId, change):
        self.tracker.updateProgress(self.currentTaskId, objectiveId, change)
        self.refreshList()

    def updateDetail(self):
        task = self.tracker.tasks[self.currentTaskId]
        self.titleLabel.setText(task.name)
        self.wikiButton.setEnabled(bool(task.wikiUrl))
        self.starButton.setEnabled(True)
        self.starButton.setText("★" if self.tracker.isStarred(task.id) else "☆")
        self.completeButton.setEnabled(True)
        self.completeButton.setText("Mark incomplete" if self.tracker.isCompleted(task.id) else "Mark complete")
        self.clearObjectives()
        for number, objective in enumerate(task.objectives):
            count = self.tracker.countFor(task.id, objective.id)
            row = ObjectiveRow(objective, count, self.onObjectiveChanged, self.onObjectiveSelected,
                               objectiveColor(number), objective.id == self.selectedObjectiveId)
            self.objectivesLayout.addWidget(row)
        self.showTaskMap(task)

    def showTaskMap(self, task):
        if self.maps is None:
            return
        if self.taskMap is None:
            if not taskMaps(task, self.maps):
                return
            self.taskMap = TaskMapView(self.maps, self.mapConfigs, self.tileDir, self.pinBook)
            self.mapSlot.addWidget(self.taskMap)
        self.taskMap.setVisible(self.taskMap.showTask(task, self.selectedObjectiveId))

    def onObjectiveSelected(self, objectiveId):
        self.selectedObjectiveId = objectiveId
        for number in range(self.objectivesLayout.count()):
            row = self.objectivesLayout.itemAt(number).widget()
            if row is not None:
                row.setSelected(row.objective.id == objectiveId)
        if self.taskMap is not None and not self.taskMap.isHidden():
            self.taskMap.selectObjective(objectiveId)

    def clearDetail(self):
        self.currentTaskId = None
        self.selectedObjectiveId = None
        if self.taskMap is not None:
            self.taskMap.hide()
        self.titleLabel.setText("Select a task")
        self.starButton.setEnabled(False)
        self.wikiButton.setEnabled(False)
        self.completeButton.setEnabled(False)
        self.clearObjectives()

    def clearObjectives(self):
        while self.objectivesLayout.count():
            item = self.objectivesLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refreshList(self):
        selectedId = self.currentTaskId
        self.taskList.blockSignals(True)
        self.taskList.clear()
        tasks = self.tracker.tasksForTrader(self.trader.id, self.showCompleted.isChecked())
        found = False
        for task in tasks:
            text = f"{task.name} ★" if self.tracker.isStarred(task.id) else task.name
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.taskList.addItem(item)
            if task.id == selectedId:
                self.taskList.setCurrentItem(item)
                found = True
        self.taskList.blockSignals(False)
        if found:
            self.updateDetail()
        else:
            self.clearDetail()