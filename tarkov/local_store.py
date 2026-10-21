import json, os
from dataclasses import asdict
from tarkov.models import TaskProgress


class JsonStore:
    def __init__(self, filePath):
        self.filePath = filePath

    def save(self, records):
        saved = {}
        for t in records.values():
            d = asdict(t)
            saved[d["taskId"]] = d

        tempFile = str(self.filePath) + ".tmp"
        with open(tempFile, "w") as f:
            json.dump(saved, f, indent=2)

        os.replace(tempFile, self.filePath)

    def load(self):
        try:
            with open(self.filePath) as f:
                back = json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            os.replace(self.filePath, str(self.filePath) + ".corrupt")
            return {}

        rebuilt = {}
        for taskId, d in back.items():
            rebuilt[taskId] = TaskProgress(**d)

        return rebuilt