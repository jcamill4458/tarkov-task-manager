from dataclasses import dataclass, field

# dataclass file
# GameMap incomplete

@dataclass
class Objective:
    id: str
    description: str
    objType: str
    optional: bool = False
    target: int = 1
    mapIds: list[str] = field(default_factory=list)

@dataclass
class Task:
    id: str
    name: str
    traderId: str
    wikiUrl: str = ""
    mapIds: list[str] = field(default_factory=list)
    objectives: list[Objective] = field(default_factory=list)

@dataclass
class Trader:
    id: str
    name: str
    imageUrl: str = ""

@dataclass
class GameMap:
    id: str
    name: str

@dataclass
class TaskProgress:
    taskId: str
    isStarred: bool = False
    isAvailable: bool = False
    completeOverride: bool | None = None
    counts: dict[str, int] = field(default_factory=dict)

    def increment(self, objectiveId, amount=1):
        self.counts[objectiveId] = max(0, self.counts.get(objectiveId, 0) + amount)

    def decrement(self, objectiveId, amount=1):
        self.increment(objectiveId, -amount)