from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout


class ObjectiveRow(QWidget):
    def __init__(self, objective, count, onChange, onSelect=None, color=None, selected=False):
        super().__init__()
        # important
        self.objective = objective
        self.count = count
        self.onChange = onChange
        self.onSelect = onSelect
        # widgets
        self.colorChip = QLabel()   # same colour as this objective's places on the map
        self.colorChip.setFixedSize(10, 10)
        if color:
            self.colorChip.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self.descLabel = QLabel(f"{objective.description} (optional)" if objective.optional else objective.description)
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, self.objective.target)
        self.progressBar.setValue(count)
        self.progressBar.setTextVisible(False)
        self.countLabel = QLabel(f"{self.count}/{self.objective.target}")
        self.minusButton = QPushButton("-")
        self.plusButton = QPushButton("+")
        self.minusButton.setFixedWidth(28)
        self.plusButton.setFixedWidth(28)

        # connectors
        self.minusButton.clicked.connect(lambda: self.onChange(objective.id, -1))
        self.plusButton.clicked.connect(lambda: self.onChange(objective.id, 1))

        # build
        self.buildRow()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSelected(selected)

    def buildRow(self):
        layout = QHBoxLayout()
        layout.addWidget(self.colorChip)
        layout.addWidget(self.descLabel, 1)
        layout.addWidget(self.progressBar)
        layout.addWidget(self.minusButton)
        layout.addWidget(self.countLabel)
        layout.addWidget(self.plusButton)
        self.setLayout(layout)

    def setSelected(self, selected):
        self.setStyleSheet("ObjectiveRow { background: rgba(52, 152, 219, 45); }" if selected else "")

    def mousePressEvent(self, event):
        if self.onSelect is not None:
            self.onSelect(self.objective.id)
        super().mousePressEvent(event)