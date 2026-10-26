import sys, os
from platformdirs import user_data_dir
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget)
from tarkov.api_client import TarkovApiClient
from tarkov.local_store import JsonStore
from tarkov.map_config import loadMapConfigs
from tarkov.map_files import MAP_CONFIG
from tarkov.pins import PinBook
from tarkov.tracker import TaskTracker
from tarkov.ui.maps_tab import MapsTab
from tarkov.ui.trader_tab import TraderTab

def main():
    # file nonsense
    dataDir = user_data_dir("TarkovTaskTracker", appauthor=False)
    os.makedirs(dataDir, exist_ok=True)
    cacheDir = os.path.join(dataDir, "cache")
    tileDir = os.path.join(dataDir, "tiles")
    progressPath = os.path.join(dataDir, "progress.json")
    pinsPath = os.path.join(dataDir, "pins.json")
    # builds
    client = TarkovApiClient(cacheDir=cacheDir)
    store = JsonStore(progressPath)
    tasks = client.fetchTasks()
    traders = client.fetchTraders()
    maps = client.fetchMaps()
    mapConfigs = loadMapConfigs(MAP_CONFIG)
    tracker = TaskTracker(tasks, store)
    pinBook = PinBook(pinsPath)

    # base Qt vars
    app = QApplication(sys.argv)
    tabs = QTabWidget()

    # tab widget creation
    for trader in traders.values():
        tabs.addTab(TraderTab(trader, tracker, maps, mapConfigs, tileDir, pinBook), trader.name)
    tabs.addTab(MapsTab(maps, mapConfigs, tileDir, pinBook), "Maps")

    # window
    window = QMainWindow()
    window.setWindowTitle("Tarkov Task Manager")
    window.resize(800, 600)
    window.setCentralWidget(tabs)
    window.show()

    app.exec()

if __name__ == "__main__":
    main()