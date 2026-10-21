import json
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

        with open(self.filePath, "w") as f:
            json.dump(saved, f, indent=2)

    def load(self):
        try:
            with open(self.filePath) as f:
                back = json.load(f)
        except FileNotFoundError:
            return {}

        rebuilt = {}
        for taskId, d in back.items():
            rebuilt[taskId] = TaskProgress(**d)

        return rebuilt