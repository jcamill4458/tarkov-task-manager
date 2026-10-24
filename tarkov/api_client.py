import requests, json, os
from tarkov.models import Objective, Task, Trader, GameMap

# base of json file we pull from
BASE_URL = "https://json.tarkov.dev"
# dict to key map variations to their original map values
DISPLAY_MAP = {
    "65b8d6f5cdde2479cb2a3125" : "653e6760052c01c1c805532f", # Ground Zero 21+
    "68236e8153654e8c1200798a" : "653e6760052c01c1c805532f", # Ground Zero Tutorial
    "59fc81d786f774390775787e" : "55f2d3fd4bdc2d5f408b4567", # Night Factory
    "6a294a5b5eb5f9a1700417b7" : "5b0fc42d86f7744a585f9105" # The Lab (Dark)
}
# the traders I want included
# maybe add the other couple later
TRADER_IDS = [
"54cb50c76803fa8b248b4571", #Prapor
"54cb57776803fa99248b456e", #Therapist
"58330581ace78e27b8b10cee", #Skier
"5935c25fb3acc3127c3d8cd9", #Peacekeeper
"5a7c2eca46aef81a7ca2145d", #Mechanic
"5ac3b934156ae10c4430e83c", #Ragman
"5c0647fdd443bc2504c2d371" #Jaeger
]

# API client class
class TarkovApiClient:
    def __init__(self, gameMode="pve", cacheDir="cache"):
        self.gameMode = gameMode
        self.cacheDir = cacheDir

    # json data fetcher, unspecified
    def fetchData(self, endpoint):
        cachePath = os.path.join(self.cacheDir, f"{endpoint}.json")
        if os.path.exists(cachePath):
            with open(cachePath) as f:
                return json.load(f)
        url = f"{BASE_URL}/{self.gameMode}/{endpoint}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()["data"]
        os.makedirs(self.cacheDir, exist_ok=True)
        with open(cachePath, "w") as f:
            json.dump(data, f)
        return data

    # fetch data from tasks dataset and tasks english translation dataset
    def fetchTasks(self):
        taskData = self.fetchData("tasks")
        taskNames = self.fetchData("tasks_en")
        tasksById = {}
        for eachRaw in taskData["tasks"].values():
            if eachRaw["trader"] not in TRADER_IDS:
                continue
            tasksById[eachRaw["id"]] = self.buildTask(eachRaw, taskNames)
        return tasksById

    # fetch data from traders dataset and traders english translation dataset
    def fetchTraders(self):
        traderData = self.fetchData("traders")
        traderNames = self.fetchData("traders_en")
        tradersById = {}
        for eachTrader in traderData.values():
            if eachTrader["id"] not in TRADER_IDS:
                continue
            tradersById[eachTrader["id"]] = self.buildTrader(eachTrader, traderNames)
        return tradersById

    # fetch data from maps dataset and maps english translation dataset
    def fetchMaps(self):
        mapData = self.fetchData("maps")
        mapNames = self.fetchData("maps_en")
        mapsById = {}
        for eachMap in mapData["maps"].values():
            mapsById[eachMap["id"]] = self.buildMap(eachMap, mapNames)
        return mapsById

    # swaps map based on DISPLAY_MAP (for variations)
    @staticmethod
    def displayMap(mapId):
        return DISPLAY_MAP.get(mapId, mapId)

    # builds map dataclass (incomplete)
    def buildMap(self, raw, mapNames):
        return GameMap(id=raw["id"], name=mapNames.get(raw["name"]) or "Unknown map")

    # builds trader dataclass
    def buildTrader(self, raw, traderNames):
        return Trader(id=raw["id"], name=traderNames.get(raw["name"]) or "Unknown trader", imageUrl=raw.get("imageLink") or "")

    # builds objective dataclass
    def buildObjective(self, raw, taskNames):
        mapSet = set()
        for eachMap in raw.get("maps") or []:
            mapSet.add(self.displayMap(eachMap))
        mapList = sorted(mapSet)
        return Objective(id=raw["id"], description=taskNames.get(raw["description"]) or "Unknown description",
                         objType=raw["type"], optional=bool(raw.get("optional")), target=raw.get("count") or 1,
                         mapIds=mapList)

    # builds task dataclass
    def buildTask(self, raw, taskNames):
        objectiveList = []
        for eachObjective in raw.get("objectives") or []:
            objectiveList.append(self.buildObjective(eachObjective, taskNames))
        mapSet = set()
        mapId = raw.get("map")
        if mapId:
            mapSet.add(self.displayMap(mapId))
        for eachObjective in objectiveList:
            for eachMap in eachObjective.mapIds:
                mapSet.add(eachMap)
        mapList = sorted(mapSet)
        return Task(id=raw["id"], name=taskNames.get(raw["name"]) or "Unknown task", traderId=raw["trader"],
                    wikiUrl=raw.get("wikiLink") or "",
                    objectives=objectiveList, mapIds=mapList)