import json
from dataclasses import dataclass, field, replace

# Map layout data
# From tarkov.dev's src/data/maps.json -> saved as assets/mapConfig.json

INF = float("inf")
UNBOUNDED = 1000

# For single building maps
STANDALONE_FLOOR_MAPS = ("factory",)


@dataclass
class MapLabel:
    text: str
    x: float
    z: float
    size: float = 100
    rotation: float = 0
    bottom: float | None = None
    top: float | None = None

    def visibleIn(self, low, high):
        bottom = -INF if self.bottom is None else self.bottom
        top = INF if self.top is None else self.top
        if bottom == top:
            return low <= bottom < high
        return bottom < high and top > low


@dataclass
class MapLayer:
    # per-floor
    name: str
    svgLayer: str
    show: bool = False
    low: float = -INF
    high: float = INF
    tilePath: str = ""


@dataclass
class MapConfig:
    key: str
    bounds: tuple
    rotation: int
    transform: tuple
    hasSvg: bool = False
    tileSize: int = 256
    tilePath: str = ""
    minZoom: int = 0
    maxZoom: int = 0
    labels: list[MapLabel] = field(default_factory=list)
    layers: list[MapLayer] = field(default_factory=list)
    heightRange: tuple = (-INF, INF)
    baseLayer: str = ""


def normalizeName(name):
    return name.lower().replace(" ", "-")


def buildLabel(raw):
    x, z = raw["position"]
    return MapLabel(
        text=raw["text"],
        x=x,
        z=z,
        size=raw.get("size", 100),
        rotation=float(raw.get("rotation", 0)),
        bottom=raw.get("bottom"),
        top=raw.get("top"),
    )


def layerRange(raw):
    extents = raw.get("extents", [])
    if not extents or "height" not in extents[0]:
        return -INF, INF
    low, high = extents[0]["height"]
    return low, high


def buildLayer(raw):
    low, high = layerRange(raw)
    return MapLayer(
        name=raw["name"],
        svgLayer=raw["svgLayer"],
        show=raw.get("show", False),
        low=low,
        high=high,
        tilePath=raw.get("tilePath", ""),
    )


def groundRange(heightRange, layers):
    if heightRange:
        return tuple(heightRange)
    low, high = -INF, INF
    for layer in layers:
        if layer.low > 0:
            high = min(high, layer.low)
        if layer.high <= 0:
            low = max(low, layer.high)
    return low, high


def buildConfig(entry):
    raw = next((m for m in entry["maps"] if m.get("projection") == "interactive"), None)
    if raw is None:
        return None
    (x0, z0), (x1, z1) = raw["bounds"]
    layers = [buildLayer(layer) for layer in raw.get("layers", []) if layer.get("svgLayer")]
    return MapConfig(
        key=raw["key"],
        bounds=((x0, z0), (x1, z1)),
        rotation=raw["coordinateRotation"],
        transform=tuple(raw["transform"]),
        hasSvg=bool(raw.get("svgPath")),
        tileSize=raw.get("tileSize", 256),
        tilePath=raw.get("tilePath", ""),
        minZoom=raw.get("minZoom", 0),
        maxZoom=raw.get("maxZoom", 0),
        labels=[buildLabel(label) for label in raw.get("labels", [])],
        layers=layers,
        baseLayer=raw.get("svgLayer", ""),
        heightRange=groundRange(raw.get("heightRange"), layers),
    )


def floorGroupsToHide(config, layer):
    chosen = layer.svgLayer if layer is not None else None
    hidden = [other.svgLayer for other in config.layers if other.svgLayer != chosen]
    if layer is not None and config.key in STANDALONE_FLOOR_MAPS and config.baseLayer:
        hidden.append(config.baseLayer)
    return hidden


GROUND = "ground"


def floorForHeight(config, height):
    low, high = config.heightRange
    if height is None or low <= -UNBOUNDED or high >= UNBOUNDED:
        return None
    if low <= height < high:
        return GROUND
    for layer in config.layers:
        if layer.low <= height < layer.high:
            return layer
    return None


def satelliteConfig(config, layer):
    if layer is None:
        return config if config.tilePath else None
    if not layer.tilePath:
        return None
    return replace(config, key=f"{config.key}-{normalizeName(layer.name)}", tilePath=layer.tilePath)


def loadMapConfigs(filePath):
    try:
        with open(filePath, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except FileNotFoundError:
        return {}
    configs = {}
    for entry in entries:
        config = buildConfig(entry)
        if config is not None:
            configs[entry["normalizedName"]] = config
    return configs


def satelliteStack(config, layer):
    ground = satelliteConfig(config, None)
    floor = satelliteConfig(config, layer) if layer is not None else None
    if floor is None:
        return [ground] if ground is not None else []
    if layer.low < 0 or ground is None:
        return [floor]
    stack = [ground]
    for other in config.layers:
        if other.low >= 0:
            tiles = satelliteConfig(config, other)
            if tiles is not None:
                stack.append(tiles)
        if other is layer:
            break
    return stack