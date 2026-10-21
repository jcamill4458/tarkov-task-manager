import os, sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QListWidget)
from tarkov.api_client import TarkovApiClient
from tarkov.local_store import JsonStore
from tarkov.tracker import TaskTracker
from tarkov.ui.trader_tab import TraderTab


def main():
    # builds
    client = TarkovApiClient()
    store = JsonStore("progress.json")
    tasks = client.fetchTasks()
    traders = client.fetchTraders()
    maps = client.fetchMaps()
    tracker = TaskTracker(tasks, store)

    # base Qt vars
    app = QApplication(sys.argv)
    tabs = QTabWidget()

    # tab widget creation
    for trader in traders.values():
        tabs.addTab(TraderTab(trader, tracker), trader.name)

    # window
    window = QMainWindow()
    window.setWindowTitle("Tarkov Task Manager")
    window.resize(800, 600)
    window.setCentralWidget(tabs)
    window.show()

    app.exec()

if __name__ == "__main__":
    main()