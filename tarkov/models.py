from dataclasses import dataclass, field

# dataclass file

@dataclass
class ObjectiveLocation:
    mapId: str
    x: float
    z: float
    bottom: float | None = None
    top: float | None = None
    outline: list[tuple[float, float]] = field(default_factory=list)

    def height(self):
        heights = [h for h in (self.bottom, self.top) if h is not None]
        return sum(heights) / len(heights) if heights else None


@dataclass
class Objective:
    id: str
    description: str
    objType: str
    optional: bool = False
    target: int = 1
    mapIds: list[str] = field(default_factory=list)
    locations: list[ObjectiveLocation] = field(default_factory=list)

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
class Extract:
    id: str
    name: str
    faction: str
    x: float
    y: float
    z: float

@dataclass
class Transit:
    id: str
    description: str
    destinationMapId: str
    x: float
    y: float
    z: float

@dataclass
class GameMap:
    id: str
    name: str
    extracts: list[Extract] = field(default_factory=list)
    transits: list[Transit] = field(default_factory=list)

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

@dataclass
class Pin:
    id: str
    mapId: str
    x: float
    z: float
    name: str = ""
    taskId: str | None = None
