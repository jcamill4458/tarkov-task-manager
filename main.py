import os, sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QListWidget)
from tarkov.api_client import TarkovApiClient
from tarkov.local_store import JsonStore
from tarkov.tracker import TaskTracker

def main():
    # BUILDS
    client = TarkovApiClient()
    store = JsonStore("progress.json")
    tasks = client.fetchTasks()
    traders = client.fetchTraders()
    maps = client.fetchMaps()
    tracker = TaskTracker(tasks, store)

    # base vars
    app = QApplication(sys.argv)
    tabs = QTabWidget()

    # widget contents
    for trader in traders.values():
        taskList = QListWidget()
        taskNames = [task.name for task in tracker.allTasksForTrader(trader.id)]
        taskList.addItems(taskNames)
        tabs.addTab(taskList, trader.name)

    # window
    window = QMainWindow()
    window.setWindowTitle("Tarkov Task Manager")
    window.resize(800, 600)
    window.setCentralWidget(tabs)
    window.show()

    app.exec()

if __name__ == "__main__":
    main()