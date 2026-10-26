import os
import requests

from tarkov.map_math import tileRange

USER_AGENT = "TarkovTaskTracker/0.1 (personal project)"


def tileUrl(template, zoom, x, y):
    return template.replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))


def tileFilePath(tileDir, mapKey, zoom, x, y):
    return os.path.join(tileDir, mapKey, str(zoom), str(x), f"{y}.png")


def tileCoordinates(config, zoom):
    xMin, xMax, yMin, yMax = tileRange(config, zoom)
    return [(x, y) for y in range(yMin, yMax + 1) for x in range(xMin, xMax + 1)]


def missingTiles(config, zoom, tileDir):
    return [(x, y) for x, y in tileCoordinates(config, zoom)
            if not os.path.exists(tileFilePath(tileDir, config.key, zoom, x, y))]


def readTile(tileDir, mapKey, zoom, x, y):
    try:
        with open(tileFilePath(tileDir, mapKey, zoom, x, y), "rb") as f:
            return f.read() or None
    except FileNotFoundError:
        return None


def fetchBytes(url):
    response = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.content


def downloadTiles(config, zoom, tileDir, onProgress=None, fetch=fetchBytes):
    # tile downloader
    todo = missingTiles(config, zoom, tileDir)
    for done, (x, y) in enumerate(todo):
        if onProgress is not None and onProgress(done, len(todo)) is False:
            return False
        data = fetch(tileUrl(config.tilePath, zoom, x, y))
        filePath = tileFilePath(tileDir, config.key, zoom, x, y)
        os.makedirs(os.path.dirname(filePath), exist_ok=True)
        tempPath = filePath + ".tmp"
        with open(tempPath, "wb") as f:
            f.write(data or b"")
        os.replace(tempPath, filePath)
    if onProgress is not None:
        onProgress(len(todo), len(todo))
    return True