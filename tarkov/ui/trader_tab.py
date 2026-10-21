from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QListWidget, QCheckBox, QToolButton, QHBoxLayout, QVBoxLayout, QMenu, QLabel,
                               QListWidgetItem, QPushButton)

class TraderTab(QWidget):
    def __init__(self, trader, tracker):
        super().__init__()
        # important
        self.trader = trader
        self.tracker = tracker
        self.currentTaskId = None
        # left widgets
        self.taskList = QListWidget()
        self.showCompleted = QCheckBox("Show Completed")
        self.tasksButton = QToolButton()
        self.tasksButton.setText("Tasks ")
        # right widgets
        self.titleLabel = QLabel("Select a task")
        self.starButton = QPushButton("★")
        self.starButton.setEnabled(False)
        self.starButton.setStyleSheet("padding: 3px; margin: 3px;")
        self.wikiButton = QPushButton("Wiki")
        self.wikiButton.setEnabled(False)
        self.wikiButton.setStyleSheet("padding: 3px; margin: 2px;")
        self.completeButton = QPushButton("Mark complete")
        self.completeButton.setEnabled(False)

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
        return rightLayout


    def buildLayout(self):
        layout = QHBoxLayout()
        left = self.buildLeft()
        right = self.buildRight()
        layout.addLayout(left, 5)
        layout.addLayout(right, 7)
        self.setLayout(layout)

    def buildTasksMenu(self):
        menu = QMenu(self)
        for task in self.tracker.allTasksForTrader(self.trader.id):
            action = menu.addAction(task.name)
            action.setCheckable(True)
            action.setChecked(self.tracker.isAvailable(task.id))
            action.toggled.connect(lambda checked, taskId=task.id: self.onTaskToggled(taskId))
        self.tasksButton.setMenu(menu)
        self.tasksButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def onTaskToggled(self, taskId):
        self.tracker.toggleAvailable(taskId)
        self.refreshList()

    def onTaskSelected(self, current, previous):
        if current is None: return
        self.currentTaskId = current.data(Qt.ItemDataRole.UserRole)
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

    def updateDetail(self):
        task = self.tracker.tasks[self.currentTaskId]
        self.titleLabel.setText(task.name)
        self.wikiButton.setEnabled(bool(task.wikiUrl))
        self.starButton.setEnabled(True)
        self.starButton.setText("★" if self.tracker.isStarred(task.id) else "☆")
        self.completeButton.setEnabled(True)
        self.completeButton.setText("Mark incomplete" if self.tracker.isCompleted(task.id) else "Mark complete")

    def clearDetail(self):
        self.currentTaskId = None
        self.titleLabel.setText("Select a task")
        self.starButton.setEnabled(False)
        self.wikiButton.setEnabled(False)
        self.completeButton.setEnabled(False)

    def refreshList(self):
        selectedId = self.currentTaskId
        self.taskList.blockSignals(True)
        self.taskList.clear()
        tasks = self.tracker.tasksForTrader(self.trader.id, self.showCompleted.isChecked())
        found = False
        for task in tasks:
            item = QListWidgetItem(task.name)
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