from PySide6.QtWidgets import QWidget, QLabel, QProgressBar, QPushButton, QHBoxLayout


class ObjectiveRow(QWidget):
    def __init__(self, objective, count, onChange):
        super().__init__()
        # important
        self.objective = objective
        self.count = count
        self.onChange = onChange
        # widgets
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

    def buildRow(self):
        layout = QHBoxLayout()
        layout.addWidget(self.descLabel, 1)
        layout.addWidget(self.progressBar)
        layout.addWidget(self.minusButton)
        layout.addWidget(self.countLabel)
        layout.addWidget(self.plusButton)
        self.setLayout(layout)