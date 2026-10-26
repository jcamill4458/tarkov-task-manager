# which maps and places an objective points at

OBJECTIVE_COLORS = ["#e74c3c", "#3498db", "#f1c40f", "#9b59b6",
                    "#1abc9c", "#e67e22", "#ecf0f1", "#fd79a8"]


def objectiveColor(index):
    return OBJECTIVE_COLORS[index % len(OBJECTIVE_COLORS)]


def locationsOnMap(objective, mapId):
    return [location for location in objective.locations if location.mapId == mapId]


def taskMaps(task, maps):
    ids = set(task.mapIds)
    for objective in task.objectives:
        ids.update(location.mapId for location in objective.locations)
    return sorted((maps[mapId] for mapId in ids if mapId in maps), key=lambda m: m.name)


def mapForObjective(objective, currentMapId, maps):
    mapIds = {location.mapId for location in objective.locations}
    if currentMapId in mapIds:
        return currentMapId
    known = sorted((maps[mapId] for mapId in mapIds if mapId in maps), key=lambda m: m.name)
    return known[0].id if known else None