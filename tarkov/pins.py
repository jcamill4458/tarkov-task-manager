import json, os, uuid
from dataclasses import asdict
from tarkov.models import Pin


class PinBook:
    # your own pins
    def __init__(self, filePath):
        self.filePath = filePath
        self.pins = self.load()
        self.listeners = []

    def load(self):
        try:
            with open(self.filePath) as f:
                saved = json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            os.replace(self.filePath, str(self.filePath) + ".corrupt")
            return {}
        return {d["id"]: Pin(**d) for d in saved}

    def subscribe(self, callback):
        self.listeners.append(callback)

    def save(self):
        tempFile = str(self.filePath) + ".tmp"
        with open(tempFile, "w") as f:
            json.dump([asdict(pin) for pin in self.pins.values()], f, indent=2)
        os.replace(tempFile, self.filePath)
        for callback in self.listeners:
            callback()

    def add(self, mapId, x, z, name="", taskId=None):
        pin = Pin(id=uuid.uuid4().hex, mapId=mapId, x=x, z=z, name=name.strip(), taskId=taskId)
        self.pins[pin.id] = pin
        self.save()
        return pin

    def remove(self, pinId):
        if pinId in self.pins:
            del self.pins[pinId]
            self.save()

    def rename(self, pinId, name):
        self.pins[pinId].name = name.strip()
        self.save()

    def forMap(self, mapId, taskId=None):
        return [pin for pin in self.pins.values()
                if pin.mapId == mapId and (taskId is None or pin.taskId == taskId)]
