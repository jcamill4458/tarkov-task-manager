"""
Tests for the Tarkov task tracker, written by Claude

Run from the project root (the folder with tracker.py) with:

    pytest

Everything here uses small made-up data and temporary files, so it needs no
network and never touches your real progress file.
"""
import json
from pathlib import Path

import pytest

from tarkov.api_client import TarkovApiClient
from tarkov.local_store import JsonStore
from tarkov.map_config import (INF, MapConfig, MapLabel, MapLayer, buildConfig, floorGroupsToHide,
                               floorForHeight, GROUND, groundRange, loadMapConfigs, normalizeName,
                               satelliteConfig, satelliteStack)
from tarkov.map_math import (canProject, clampZoom, labelFontSize, limitZoomOut, satelliteTransform,
                             screenVector, svgToWorld, tileRange, worldToSvg, worldToTile)
from tarkov.objective_map import (locationsOnMap, mapForObjective, objectiveColor, taskMaps,
                                  OBJECTIVE_COLORS)
from tarkov.pins import PinBook
from tarkov.models import (GameMap, Objective, ObjectiveLocation, Task, TaskProgress, Trader,
                           Extract, Transit)
from tarkov.svg_layers import hideGroups
from tarkov.tiles import downloadTiles, missingTiles, readTile, tileFilePath, tileUrl
from tarkov.tracker import TaskTracker


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

TRADER_A = "trader-a"
TRADER_B = "trader-b"


def makeTasks():
    """Three small tasks. Two belong to trader A, one to trader B.

    The names are chosen so a plain (case-sensitive) sort and a
    case-insensitive sort give different orders: "Yankee" vs "bravo".
    """
    yankee = Task(
        id="t1", name="Yankee", traderId=TRADER_A, wikiUrl="",
        mapIds=["m-customs"],
        objectives=[
            Objective(id="o1", description="Visit the place", objType="visit", target=1),
            Objective(id="o2", description="Hand over items", objType="giveItem", target=3),
            Objective(id="o3", description="Bonus", objType="shoot", optional=True, target=2),
        ],
    )
    bravo = Task(
        id="t2", name="bravo", traderId=TRADER_A, wikiUrl="",
        mapIds=["m-customs", "m-woods"],
        objectives=[
            Objective(id="o4", description="Find it", objType="findItem", target=1),
        ],
    )
    charlie = Task(
        id="t3", name="Charlie", traderId=TRADER_B, wikiUrl="",
        objectives=[
            Objective(id="o5", description="Kill things", objType="shoot", target=2),
        ],
    )
    return {"t1": yankee, "t2": bravo, "t3": charlie}


@pytest.fixture
def storePath(tmp_path):
    return tmp_path / "progress.json"


@pytest.fixture
def tracker(storePath):
    return TaskTracker(makeTasks(), JsonStore(storePath))


def freshTracker(storePath):
    """A second tracker on the same file. If it sees the data, it reached disk."""
    return TaskTracker(makeTasks(), JsonStore(storePath))


def makeAvailable(tracker, *taskIds):
    for taskId in taskIds:
        tracker.toggleAvailable(taskId)


# ---------------------------------------------------------------------------
# TaskProgress
# ---------------------------------------------------------------------------

def test_progress_defaults():
    p = TaskProgress(taskId="x")
    assert p.isStarred is False
    assert p.isAvailable is False
    assert p.completeOverride is None
    assert p.counts == {}


def test_progress_counts_are_not_shared_between_records():
    a = TaskProgress(taskId="a")
    b = TaskProgress(taskId="b")
    a.increment("o1")
    assert b.counts == {}


def test_increment_starts_from_zero():
    p = TaskProgress(taskId="x")
    p.increment("o1", 2)
    assert p.counts == {"o1": 2}


def test_decrement_never_goes_below_zero():
    p = TaskProgress(taskId="x")
    p.increment("o1", 1)
    p.decrement("o1", 5)
    assert p.counts["o1"] == 0


# ---------------------------------------------------------------------------
# JsonStore
# ---------------------------------------------------------------------------

def test_load_missing_file_gives_empty_dict(tmp_path):
    assert JsonStore(tmp_path / "nope.json").load() == {}


def test_save_then_load_round_trip(storePath):
    store = JsonStore(storePath)
    records = {
        "t1": TaskProgress(taskId="t1", isStarred=True, completeOverride=True, counts={"o1": 1}),
        "t2": TaskProgress(taskId="t2", completeOverride=None),
        "t3": TaskProgress(taskId="t3", completeOverride=False),
    }
    store.save(records)
    assert store.load() == records


def test_isAvailable_survives_a_round_trip(storePath):
    store = JsonStore(storePath)
    store.save({"t1": TaskProgress(taskId="t1", isAvailable=True)})
    assert store.load()["t1"].isAvailable is True


def test_load_old_file_without_isAvailable(storePath):
    storePath.write_text(
        '{"t1": {"taskId": "t1", "isStarred": false, "completeOverride": null, "counts": {}}}'
    )
    assert JsonStore(storePath).load()["t1"].isAvailable is False


def test_save_accepts_what_load_returns(storePath):
    store = JsonStore(storePath)
    store.save({"t1": TaskProgress(taskId="t1", isStarred=True)})
    loaded = store.load()
    store.save(loaded)
    assert store.load() == loaded


def test_save_leaves_no_temp_file_behind(storePath):
    store = JsonStore(storePath)
    store.save({"t1": TaskProgress(taskId="t1", isStarred=True)})

    filesInFolder = [p.name for p in storePath.parent.iterdir()]
    assert filesInFolder == ["progress.json"]


def test_save_replaces_the_old_contents(storePath):
    store = JsonStore(storePath)
    store.save({"t1": TaskProgress(taskId="t1", isStarred=True)})
    store.save({"t2": TaskProgress(taskId="t2")})

    assert list(store.load()) == ["t2"]


def test_load_garbage_file_starts_fresh_and_keeps_the_bad_file(storePath):
    storePath.write_text("{not json")

    assert JsonStore(storePath).load() == {}
    corrupt = storePath.with_name(storePath.name + ".corrupt")
    assert corrupt.exists()
    assert not storePath.exists()


# ---------------------------------------------------------------------------
# TaskTracker: records and stars
# ---------------------------------------------------------------------------

def test_progressFor_creates_a_record_once(tracker):
    first = tracker.progressFor("t1")
    assert tracker.progressFor("t1") is first


def test_isAvailable_defaults_to_false_and_creates_no_record(tracker):
    assert tracker.isAvailable("t1") is False
    assert "t1" not in tracker.progress


def test_isStarred_defaults_to_false_and_creates_no_record(tracker):
    assert tracker.isStarred("t1") is False
    assert "t1" not in tracker.progress


def test_toggleAvailable_flips_and_persists(tracker, storePath):
    tracker.toggleAvailable("t1")
    assert tracker.isAvailable("t1") is True
    assert freshTracker(storePath).isAvailable("t1") is True

    tracker.toggleAvailable("t1")
    assert freshTracker(storePath).isAvailable("t1") is False


def test_making_a_task_unavailable_clears_its_star(tracker):
    makeAvailable(tracker, "t1")
    tracker.toggleStar("t1")
    tracker.toggleAvailable("t1")
    assert tracker.isStarred("t1") is False


def test_toggleStar_needs_an_available_task_and_leaves_no_record(tracker):
    with pytest.raises(ValueError):
        tracker.toggleStar("t1")
    assert "t1" not in tracker.progress


def test_toggleStar_flips_and_persists(tracker, storePath):
    makeAvailable(tracker, "t1")
    tracker.toggleStar("t1")
    assert tracker.progressFor("t1").isStarred is True
    assert freshTracker(storePath).progressFor("t1").isStarred is True

    tracker.toggleStar("t1")
    assert freshTracker(storePath).progressFor("t1").isStarred is False


def test_countFor_defaults_to_zero_and_creates_no_record(tracker):
    assert tracker.countFor("t1", "o2") == 0
    assert "t1" not in tracker.progress


def test_countFor_reads_the_saved_count(tracker):
    tracker.updateProgress("t1", "o2", 2)
    assert tracker.countFor("t1", "o2") == 2
    assert tracker.countFor("t1", "o1") == 0      # no count saved for this one yet

# ---------------------------------------------------------------------------
# TaskTracker: completion
# ---------------------------------------------------------------------------

def test_untouched_task_is_not_complete(tracker):
    assert tracker.isCompleted("t1") is False


def test_asking_about_completion_creates_no_record(tracker):
    tracker.isCompleted("t1")
    assert "t1" not in tracker.progress


def test_complete_when_required_objectives_reach_targets(tracker):
    tracker.updateProgress("t1", "o1", 1)
    assert tracker.isCompleted("t1") is False      # o2 is still short
    tracker.updateProgress("t1", "o2", 3)
    assert tracker.isCompleted("t1") is True


def test_optional_objective_is_not_needed(tracker):
    tracker.updateProgress("t1", "o1", 1)
    tracker.updateProgress("t1", "o2", 3)
    assert "o3" not in tracker.progressFor("t1").counts
    assert tracker.isCompleted("t1") is True


def test_override_true_wins_without_any_counts(tracker):
    tracker.progressFor("t1").completeOverride = True
    assert tracker.isCompleted("t1") is True


def test_override_false_beats_full_counts(tracker):
    tracker.updateProgress("t1", "o1", 1)
    tracker.updateProgress("t1", "o2", 3)
    tracker.progressFor("t1").completeOverride = False
    assert tracker.isCompleted("t1") is False


def test_clearing_override_returns_to_the_counts(tracker):
    tracker.setComplete("t1", True)       # fills the counts
    tracker.setComplete("t1", False)
    assert tracker.isCompleted("t1") is False
    tracker.setComplete("t1", None)
    assert tracker.isCompleted("t1") is True


# ---------------------------------------------------------------------------
# TaskTracker: updateProgress
# ---------------------------------------------------------------------------

def test_updateProgress_hands_control_back_to_the_counts(tracker):
    tracker.setComplete("t1", True)
    tracker.updateProgress("t1", "o2", -1)
    assert tracker.isCompleted("t1") is False
    tracker.updateProgress("t1", "o2", 1)
    assert tracker.isCompleted("t1") is True

def test_updateProgress_caps_at_target(tracker):
    for _ in range(5):
        tracker.updateProgress("t1", "o2", 1)
    assert tracker.progressFor("t1").counts["o2"] == 3


def test_updateProgress_floors_at_zero(tracker):
    tracker.updateProgress("t1", "o2", 1)
    tracker.updateProgress("t1", "o2", -10)
    assert tracker.progressFor("t1").counts["o2"] == 0


def test_updateProgress_unknown_objective_raises_and_leaves_no_record(tracker):
    with pytest.raises(ValueError):
        tracker.updateProgress("t1", "nope", 1)
    assert "t1" not in tracker.progress


def test_updateProgress_unknown_task_raises(tracker):
    with pytest.raises(KeyError):
        tracker.updateProgress("ghost", "o1", 1)


def test_updateProgress_persists(tracker, storePath):
    tracker.updateProgress("t1", "o2", 2)
    assert freshTracker(storePath).progressFor("t1").counts["o2"] == 2


# ---------------------------------------------------------------------------
# TaskTracker: setComplete
# ---------------------------------------------------------------------------

def test_setComplete_true_fills_required_counts_only(tracker):
    tracker.setComplete("t1", True)
    assert tracker.progressFor("t1").counts == {"o1": 1, "o2": 3}   # optional o3 skipped
    assert tracker.isCompleted("t1") is True


def test_setComplete_false_leaves_counts_alone(tracker):
    tracker.updateProgress("t1", "o2", 2)
    tracker.setComplete("t1", False)
    assert tracker.progressFor("t1").counts == {"o2": 2}
    assert tracker.isCompleted("t1") is False


def test_setComplete_works_on_an_untouched_task(tracker):
    tracker.setComplete("t2", True)
    assert tracker.isCompleted("t2") is True


def test_setComplete_unknown_task_raises_and_leaves_no_record(tracker):
    with pytest.raises(KeyError):
        tracker.setComplete("ghost", True)
    assert "ghost" not in tracker.progress


def test_setComplete_persists(tracker, storePath):
    tracker.setComplete("t1", True)
    assert freshTracker(storePath).isCompleted("t1") is True


# ---------------------------------------------------------------------------
# TaskTracker: tasksForTrader
# ---------------------------------------------------------------------------

def test_tasksForTrader_filters_by_trader(tracker):
    makeAvailable(tracker, "t1", "t2", "t3")
    ids = [t.id for t in tracker.tasksForTrader(TRADER_A)]
    assert sorted(ids) == ["t1", "t2"]


def test_tasksForTrader_sorts_ignoring_case(tracker):
    makeAvailable(tracker, "t1", "t2")
    names = [t.name for t in tracker.tasksForTrader(TRADER_A)]
    assert names == ["bravo", "Yankee"]


def test_tasksForTrader_can_hide_tasks_completed_by_override(tracker):
    makeAvailable(tracker, "t1", "t2")
    tracker.setComplete("t1", True)
    shown = [t.id for t in tracker.tasksForTrader(TRADER_A, includeCompleted=False)]
    assert shown == ["t2"]
    everything = [t.id for t in tracker.tasksForTrader(TRADER_A)]
    assert sorted(everything) == ["t1", "t2"]


def test_tasksForTrader_can_hide_tasks_completed_by_counting(tracker):
    makeAvailable(tracker, "t1", "t2")
    tracker.updateProgress("t2", "o4", 1)
    shown = [t.id for t in tracker.tasksForTrader(TRADER_A, includeCompleted=False)]
    assert shown == ["t1"]


def test_tasksForTrader_unknown_trader_is_empty(tracker):
    assert tracker.tasksForTrader("nobody") == []


def test_tasksForTrader_shows_only_available_tasks(tracker):
    assert tracker.tasksForTrader(TRADER_A) == []
    makeAvailable(tracker, "t1")
    assert [t.id for t in tracker.tasksForTrader(TRADER_A)] == ["t1"]


def test_tasksForTrader_puts_starred_first(tracker):
    makeAvailable(tracker, "t1", "t2")
    assert [t.name for t in tracker.tasksForTrader(TRADER_A)] == ["bravo", "Yankee"]
    tracker.toggleStar("t1")
    assert [t.name for t in tracker.tasksForTrader(TRADER_A)] == ["Yankee", "bravo"]


# ---------------------------------------------------------------------------
# TaskTracker: allTasksForTrader (feeds the dropdown)
# ---------------------------------------------------------------------------

def test_allTasksForTrader_ignores_availability_and_stars(tracker):
    names = [t.name for t in tracker.allTasksForTrader(TRADER_A)]
    assert names == ["bravo", "Yankee"]

    makeAvailable(tracker, "t1")
    tracker.toggleStar("t1")
    names = [t.name for t in tracker.allTasksForTrader(TRADER_A)]
    assert names == ["bravo", "Yankee"]          # stays alphabetical


def test_allTasksForTrader_unknown_trader_is_empty(tracker):
    assert tracker.allTasksForTrader("nobody") == []


# ---------------------------------------------------------------------------
# TaskTracker: starredTasks
# ---------------------------------------------------------------------------

needsStarred = pytest.mark.skipif(
    not hasattr(TaskTracker, "starredTasks"),
    reason="starredTasks is not written yet",
)


@needsStarred
def test_starredTasks_returns_only_starred_sorted(tracker):
    makeAvailable(tracker, "t1", "t3")
    tracker.toggleStar("t1")
    tracker.toggleStar("t3")
    names = [t.name for t in tracker.starredTasks()]
    assert names == ["Charlie", "Yankee"]


@needsStarred
def test_starredTasks_ignores_ids_that_are_not_in_tasks(tracker):
    tracker.progress["ghost"] = TaskProgress(taskId="ghost", isStarred=True)
    makeAvailable(tracker, "t1")
    tracker.toggleStar("t1")
    assert [t.id for t in tracker.starredTasks()] == ["t1"]


@needsStarred
def test_starredTasks_can_hide_completed(tracker):
    makeAvailable(tracker, "t1", "t2")
    tracker.toggleStar("t1")
    tracker.toggleStar("t2")
    tracker.setComplete("t1", True)
    shown = [t.id for t in tracker.starredTasks(includeCompleted=False)]
    assert shown == ["t2"]


# ---------------------------------------------------------------------------
# TaskTracker: tasksForMap
# ---------------------------------------------------------------------------

def test_tasksForMap_filters_by_map(tracker):
    customs = [t.id for t in tracker.tasksForMap("m-customs")]
    woods = [t.id for t in tracker.tasksForMap("m-woods")]
    assert sorted(customs) == ["t1", "t2"]
    assert woods == ["t2"]


def test_tasksForMap_sorts_ignoring_case(tracker):
    names = [t.name for t in tracker.tasksForMap("m-customs")]
    assert names == ["bravo", "Yankee"]


def test_tasksForMap_can_hide_completed(tracker):
    tracker.setComplete("t1", True)
    shown = [t.id for t in tracker.tasksForMap("m-customs", includeCompleted=False)]
    assert shown == ["t2"]


def test_tasksForMap_unknown_map_is_empty(tracker):
    assert tracker.tasksForMap("nowhere") == []


def test_tasks_without_a_map_match_no_map(tracker):
    for mapId in ("m-customs", "m-woods"):
        assert "t3" not in [t.id for t in tracker.tasksForMap(mapId)]


# ---------------------------------------------------------------------------
# api_client builders (raw API dictionaries in, clean objects out)
# ---------------------------------------------------------------------------

GROUND_ZERO = "653e6760052c01c1c805532f"
GROUND_ZERO_21 = "65b8d6f5cdde2479cb2a3125"
NIGHT_FACTORY = "59fc81d786f774390775787e"
FACTORY = "55f2d3fd4bdc2d5f408b4567"
CUSTOMS = "56f40101d2720b2a4d8b45d6"

# Stands in for the tasks_en file: lookup key -> readable text.
LOOKUP = {"desc-key": "Do the thing", "empty-key": "", "task-key": "My Task"}

# Creating a client does no network work. Only the fetch methods do.
client = TarkovApiClient()

RAW_EXTRACT = {"id": "e1", "name": "ex-key", "faction": "pmc",
               "position": {"x": 1.5, "y": 2.5, "z": 3.5}}
RAW_TRANSIT = {"id": "9", "description": "tr-key", "map": NIGHT_FACTORY,
               "position": {"x": 4.0, "y": 5.0, "z": 6.0}}
NAMES = {"ex-key": "Crossroads", "tr-key": "Transit to Factory", "map-key": "Customs"}


def test_buildExtract_reads_the_nested_position():
    extract = client.buildExtract(RAW_EXTRACT, NAMES)
    assert extract == Extract(id="e1", name="Crossroads", faction="pmc", x=1.5, y=2.5, z=3.5)


def test_buildExtract_fallbacks():
    extract = client.buildExtract({"id": "e1", "name": "nope"}, {})
    assert extract.name == "Unknown extract"
    assert extract.faction == "unknown"
    assert (extract.x, extract.y, extract.z) == (0, 0, 0)


def test_buildTransit_translates_the_destination_map():
    transit = client.buildTransit(RAW_TRANSIT, NAMES)
    assert transit.description == "Transit to Factory"
    assert transit.destinationMapId == FACTORY
    assert (transit.x, transit.y, transit.z) == (4.0, 5.0, 6.0)


def test_buildTransit_fallbacks():
    transit = client.buildTransit({"id": "9"}, {})
    assert transit.description == "Unknown transit"
    assert transit.destinationMapId == ""


def test_buildMap_keeps_extracts_and_transits_but_skips_shared():
    raw = {"id": "m1", "name": "map-key",
           "extracts": [RAW_EXTRACT, dict(RAW_EXTRACT, id="e2", faction="shared")],
           "transits": [RAW_TRANSIT]}
    gameMap = client.buildMap(raw, NAMES)
    assert gameMap.name == "Customs"
    assert [e.id for e in gameMap.extracts] == ["e1"]
    assert len(gameMap.transits) == 1


def test_buildMap_without_extracts_or_transits_has_empty_lists():
    gameMap = client.buildMap({"id": "m1", "name": "map-key"}, NAMES)
    assert gameMap.extracts == []
    assert gameMap.transits == []

def rawObjective(**overrides):
    raw = {
        "id": "o1", "description": "desc-key", "type": "shoot",
        "optional": False, "count": 5, "maps": [],
    }
    raw.update(overrides)
    return raw


def rawTask(**overrides):
    raw = {
        "id": "t1", "name": "task-key", "trader": TRADER_A,
        "wikiLink": "https://example.com/wiki", "map": CUSTOMS,
        "objectives": [rawObjective()],
    }
    raw.update(overrides)
    return raw


def test_displayMap_translates_variants_only():
    assert client.displayMap(GROUND_ZERO_21) == GROUND_ZERO
    assert client.displayMap(NIGHT_FACTORY) == FACTORY
    assert client.displayMap(CUSTOMS) == CUSTOMS


def test_buildObjective_basic_fields():
    obj = client.buildObjective(rawObjective(), LOOKUP)
    assert obj == Objective(
        id="o1", description="Do the thing", objType="shoot",
        optional=False, target=5, mapIds=[],
    )


def test_buildObjective_target_defaults_to_one():
    assert client.buildObjective(rawObjective(count=None), LOOKUP).target == 1
    raw = rawObjective()
    del raw["count"]
    assert client.buildObjective(raw, LOOKUP).target == 1


def test_buildObjective_description_falls_back_when_missing_or_empty():
    missing = client.buildObjective(rawObjective(description="not-a-key"), LOOKUP)
    empty = client.buildObjective(rawObjective(description="empty-key"), LOOKUP)
    assert missing.description == "Unknown description"
    assert empty.description == "Unknown description"


def test_buildObjective_optional_and_maps_may_be_missing():
    raw = rawObjective()
    del raw["optional"]
    del raw["maps"]
    obj = client.buildObjective(raw, LOOKUP)
    assert obj.optional is False
    assert obj.mapIds == []


def test_buildObjective_maps_may_be_none():
    assert client.buildObjective(rawObjective(maps=None), LOOKUP).mapIds == []


def test_buildObjective_maps_are_translated_and_deduplicated():
    obj = client.buildObjective(rawObjective(maps=[GROUND_ZERO, GROUND_ZERO_21]), LOOKUP)
    assert obj.mapIds == [GROUND_ZERO]


def test_buildTask_basic_fields():
    task = client.buildTask(rawTask(), LOOKUP)
    assert task.id == "t1"
    assert task.name == "My Task"
    assert task.traderId == TRADER_A
    assert task.wikiUrl == "https://example.com/wiki"
    assert len(task.objectives) == 1


def test_buildTask_combines_the_task_map_and_objective_maps():
    raw = rawTask(
        map=CUSTOMS,
        objectives=[
            rawObjective(maps=[GROUND_ZERO_21]),
            rawObjective(id="o2", maps=[NIGHT_FACTORY]),
        ],
    )
    task = client.buildTask(raw, LOOKUP)
    assert task.mapIds == sorted([CUSTOMS, GROUND_ZERO, FACTORY])


def test_buildTask_does_not_list_a_map_twice():
    raw = rawTask(map=GROUND_ZERO, objectives=[rawObjective(maps=[GROUND_ZERO_21])])
    assert client.buildTask(raw, LOOKUP).mapIds == [GROUND_ZERO]


def test_buildTask_with_no_map_anywhere_has_empty_mapIds():
    raw = rawTask(map=None, objectives=[rawObjective(maps=[])])
    assert client.buildTask(raw, LOOKUP).mapIds == []
    del raw["map"]
    assert client.buildTask(raw, LOOKUP).mapIds == []


def test_buildTask_fallbacks():
    raw = rawTask(name="not-a-key", wikiLink=None)
    task = client.buildTask(raw, LOOKUP)
    assert task.name == "Unknown task"
    assert task.wikiUrl == ""


def test_buildTask_objectives_may_be_missing():
    raw = rawTask()
    del raw["objectives"]
    assert client.buildTask(raw, LOOKUP).objectives == []


def test_buildTrader_resolves_name_and_image():
    raw = {"id": "tr1", "name": "trader-key", "imageLink": "https://x/y.webp"}
    trader = client.buildTrader(raw, {"trader-key": "Therapist"})
    assert trader == Trader(id="tr1", name="Therapist", imageUrl="https://x/y.webp")


def test_buildTrader_fallbacks():
    trader = client.buildTrader({"id": "tr1", "name": "missing"}, {})
    assert trader.name == "Unknown trader"
    assert trader.imageUrl == ""


def test_buildMap_resolves_name_and_falls_back():
    assert client.buildMap({"id": "m1", "name": "k"}, {"k": "Customs"}) == GameMap(id="m1", name="Customs")
    assert client.buildMap({"id": "m1", "name": "k"}, {}).name == "Unknown map"


# ---------------------------------------------------------------------------
# api_client fetch methods, with the network replaced by fake data
# ---------------------------------------------------------------------------

def test_fetchTasks_keeps_only_chosen_traders_and_keys_by_id(monkeypatch):
    from tarkov.api_client import TRADER_IDS
    mine = TRADER_IDS[0]

    def fakeFetch(endpoint):
        if endpoint == "tasks":
            return {"tasks": {
                "t1": rawTask(id="t1", trader=mine),
                "t2": rawTask(id="t2", trader="some-other-trader"),
            }}
        if endpoint == "tasks_en":
            return LOOKUP
        raise AssertionError(f"unexpected endpoint {endpoint}")

    fake = TarkovApiClient()
    monkeypatch.setattr(fake, "fetchData", fakeFetch)
    tasks = fake.fetchTasks()
    assert list(tasks) == ["t1"]
    assert tasks["t1"].name == "My Task"


def test_fetchMaps_keys_by_id(monkeypatch):
    def fakeFetch(endpoint):
        if endpoint == "maps":
            return {"maps": {"m1": {"id": "m1", "name": "k"}}, "mobs": {}}
        if endpoint == "maps_en":
            return {"k": "Customs"}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    fake = TarkovApiClient()
    monkeypatch.setattr(fake, "fetchData", fakeFetch)
    assert fake.fetchMaps() == {"m1": GameMap(id="m1", name="Customs")}

def test_fetchMaps_skips_the_display_variants(monkeypatch):
    def fakeFetch(endpoint):
        if endpoint == "maps":
            return {"maps": {
                "a": {"id": NIGHT_FACTORY, "name": "k"},
                "b": {"id": FACTORY, "name": "k"},
            }}
        return {"k": "Factory"}

    fake = TarkovApiClient()
    monkeypatch.setattr(fake, "fetchData", fakeFetch)
    assert list(fake.fetchMaps()) == [FACTORY]

class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload

def test_fetchData_writes_a_cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr("tarkov.api_client.requests.get",
                        lambda url, timeout: FakeResponse({"data": {"a": 1}}))
    client = TarkovApiClient(cacheDir=tmp_path / "cache")

    assert client.fetchData("tasks") == {"a": 1}
    assert (tmp_path / "cache" / "tasks.json").exists()

def test_fetchData_second_call_skips_the_network(tmp_path, monkeypatch):
    calls = []

    def fakeGet(url, timeout):
        calls.append(url)
        return FakeResponse({"data": {"a": 1}})

    monkeypatch.setattr("tarkov.api_client.requests.get", fakeGet)
    client = TarkovApiClient(cacheDir=tmp_path / "cache")

    first = client.fetchData("tasks")
    second = client.fetchData("tasks")

    assert first == second == {"a": 1}
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Map config (assets/mapConfig.json)
# ---------------------------------------------------------------------------

# Customs, as in tarkov.dev's maps.json, and the size of its SVG's viewBox
SVG_W, SVG_H = 1062.4827, 535.17401

def customsConfig():
    return MapConfig(key="customs", bounds=((698, -307), (-372, 237)), rotation=180,
                     transform=(0.239, 168.65, 0.239, 136.35),
                     hasSvg=True, tilePath="https://example.test/customs/main/{z}/{x}/{y}.png",
                     minZoom=2, maxZoom=6)

def rawEntry(**changes):
    mapData = {"key": "demo", "projection": "interactive", "bounds": [[10, 20], [-10, -20]],
               "coordinateRotation": 180, "transform": [1, 2, 3, 4]}
    mapData.update(changes)
    return {"normalizedName": "demo", "maps": [{"key": "demo-2d", "projection": "2D"}, mapData]}

def test_normalizeName_matches_the_files_naming():
    assert normalizeName("Streets of Tarkov") == "streets-of-tarkov"
    assert normalizeName("Customs") == "customs"

def test_buildConfig_picks_the_interactive_map():
    config = buildConfig(rawEntry())

    assert config.key == "demo"
    assert config.bounds == ((10, 20), (-10, -20))
    assert config.rotation == 180
    assert config.transform == (1, 2, 3, 4)
    assert config.labels == []

def test_buildConfig_returns_none_without_an_interactive_map():
    assert buildConfig({"normalizedName": "x", "maps": [{"key": "x-2d", "projection": "2D"}]}) is None

def test_buildConfig_crashes_on_a_missing_required_field():
    entry = rawEntry()
    del entry["maps"][1]["bounds"]

    with pytest.raises(KeyError):
        buildConfig(entry)

def test_labels_are_parsed_with_defaults_and_string_rotation():
    labels = [{"position": [5, 6], "text": "Plain"},
              {"position": [1, 2], "text": "Tilted", "size": 90, "rotation": "6",
               "bottom": -1, "top": 10}]
    plain, tilted = buildConfig(rawEntry(labels=labels)).labels

    assert (plain.text, plain.x, plain.z, plain.size, plain.rotation) == ("Plain", 5, 6, 100, 0)
    assert plain.bottom is None and plain.top is None
    assert (tilted.size, tilted.rotation, tilted.bottom, tilted.top) == (90, 6.0, -1, 10)

def test_label_without_a_height_range_is_always_visible():
    assert MapLabel("a", 0, 0).visibleIn(-INF, INF)
    assert MapLabel("a", 0, 0).visibleIn(25, 34)

def test_label_is_shown_when_its_heights_overlap_the_floor():
    ground = (-1000, 28)
    assert MapLabel("a", 0, 0, bottom=-1, top=10).visibleIn(*ground)
    assert MapLabel("a", 0, 0, bottom=-1000, top=24).visibleIn(25, 34) is False
    assert MapLabel("a", 0, 0, bottom=25, top=33).visibleIn(25, 34)
    assert not MapLabel("a", 0, 0, bottom=25, top=33).visibleIn(-INF, 25)
    assert not MapLabel("a", 0, 0, bottom=-10000, top=-2).visibleIn(-1, 3)

def test_label_with_only_a_bottom_has_no_upper_limit():
    label = MapLabel("a", 0, 0, bottom=-6)

    assert label.visibleIn(-7, 10000)
    assert not label.visibleIn(-10000, -7)

def test_shoreline_outdoor_names_show_on_the_ground_view_only():
    outdoors = MapLabel("a", 0, 0, bottom=-4, top=-2)

    assert outdoors.visibleIn(-1000, -1)        # ground view
    assert not outdoors.visibleIn(-1, 2)        # 2nd floor
    assert not outdoors.visibleIn(-1000, -5)    # underground

def test_a_name_pinned_to_one_height_belongs_to_the_floor_that_starts_there():
    shop = MapLabel("a", 0, 0, bottom=28, top=28)

    assert not shop.visibleIn(-1000, 28)
    assert shop.visibleIn(28, 32.3)

def floorEntry(**changes):
    layer = {"name": "2nd Floor", "svgLayer": "First_Floor", "show": True,
             "extents": [{"height": [25, 34]}]}
    layer.update(changes)
    return layer

def test_layers_are_parsed_with_their_height_range():
    config = buildConfig(rawEntry(layers=[floorEntry()]))

    assert len(config.layers) == 1
    layer = config.layers[0]
    assert (layer.name, layer.svgLayer, layer.show, layer.low, layer.high) == ("2nd Floor", "First_Floor", True, 25, 34)

def test_a_floor_without_an_svg_group_is_skipped():
    layers = [floorEntry(), {"name": "4th Floor", "show": False, "extents": [{"height": [11, 54]}]}]

    assert [l.name for l in buildConfig(rawEntry(layers=layers)).layers] == ["2nd Floor"]

def test_floor_without_extents_covers_every_height():
    plain = {"name": "Floor", "svgLayer": "X"}
    layer = buildConfig(rawEntry(layers=[plain])).layers[0]

    assert (layer.low, layer.high) == (-INF, INF)

def test_ground_range_comes_from_the_map_when_it_has_one():
    assert buildConfig(rawEntry(heightRange=[-6, 10])).heightRange == (-6, 10)

def test_ground_range_is_worked_out_from_the_floors_when_missing():
    upper = [MapLayer("2nd", "A", low=25, high=34), MapLayer("3rd", "B", low=34, high=1000)]
    basement = MapLayer("Basement", "C", low=-1000, high=-1)

    assert groundRange(None, upper) == (-INF, 25)
    assert groundRange(None, upper + [basement]) == (-1, 25)
    assert groundRange(None, []) == (-INF, INF)

def test_the_real_shoreline_ground_view_covers_its_outdoor_names():
    path = Path(__file__).resolve().parent.parent / "assets" / "mapConfig.json"
    config = loadMapConfigs(path)["shoreline"]
    low, high = config.heightRange
    outdoors = [l for l in config.labels if l.bottom == -4 and l.top == -2]

    assert outdoors and all(l.visibleIn(low, high) for l in outdoors)

def test_the_real_config_marks_which_maps_have_an_svg():
    path = Path(__file__).resolve().parent.parent / "assets" / "mapConfig.json"
    configs = loadMapConfigs(path)

    withSvg = {name for name, c in configs.items() if c.hasSvg}
    assert withSvg == {"customs", "factory", "ground-zero", "interchange", "lighthouse",
                       "reserve", "shoreline", "streets-of-tarkov", "terminal", "woods"}
    assert configs["the-lab"].tileSize == 175
    assert configs["customs"].tileSize == 256

def test_layers_keep_their_own_tile_path():
    layer = buildConfig(rawEntry(layers=[floorEntry(tilePath="https://x.test/2nd/{z}/{x}/{y}.png")])).layers[0]

    assert layer.tilePath == "https://x.test/2nd/{z}/{x}/{y}.png"
    assert buildConfig(rawEntry(layers=[floorEntry()])).layers[0].tilePath == ""

def twoFloorConfig(key):
    layers = [MapLayer("2nd Floor", "Second_Floor", tilePath="https://x.test/2nd/{z}/{x}/{y}.png"),
              MapLayer("Tunnels", "Basement")]
    return MapConfig(key=key, bounds=((1, 2), (3, 4)), rotation=90, transform=(1, 0, 1, 0),
                     hasSvg=True, tilePath="https://x.test/main/{z}/{x}/{y}.png",
                     layers=layers, baseLayer="Ground_Floor")

def test_choosing_a_floor_hides_the_other_floors():
    config = twoFloorConfig("customs")

    assert floorGroupsToHide(config, None) == ["Second_Floor", "Basement"]
    assert floorGroupsToHide(config, config.layers[1]) == ["Second_Floor"]

def test_a_single_building_map_also_hides_its_ground_floor():
    config = twoFloorConfig("factory")

    assert floorGroupsToHide(config, None) == ["Second_Floor", "Basement"]
    assert floorGroupsToHide(config, config.layers[1]) == ["Second_Floor", "Ground_Floor"]

def test_each_floor_gets_its_own_satellite_tiles():
    config = twoFloorConfig("factory")

    ground = satelliteConfig(config, None)
    second = satelliteConfig(config, config.layers[0])
    assert ground.key == "factory" and ground.tilePath.endswith("main/{z}/{x}/{y}.png")
    assert second.key == "factory-2nd-floor" and second.tilePath.endswith("2nd/{z}/{x}/{y}.png")
    assert second.bounds == config.bounds and second.transform == config.transform
    assert satelliteConfig(config, config.layers[1]) is None      # no tiles for this floor

def realConfigs():
    return loadMapConfigs(Path(__file__).resolve().parent.parent / "assets" / "mapConfig.json")

def floorNamed(config, name):
    return next(l for l in config.layers if l.name == name)

def stackTiles(config, layer):
    return [c.tilePath.split("/")[-4] for c in satelliteStack(config, layer)]

def test_an_upper_floor_satellite_sits_on_top_of_the_ground_tiles():
    config = realConfigs()["customs"]

    assert stackTiles(config, None) == ["main"]
    assert stackTiles(config, floorNamed(config, "2nd Floor")) == ["main", "2nd"]

def test_each_floor_is_built_on_the_floors_below_it():
    config = realConfigs()["customs"]

    assert stackTiles(config, floorNamed(config, "3rd Floor")) == ["main", "2nd", "3rd"]

def test_a_basement_satellite_shows_its_own_tiles_alone():
    config = realConfigs()["customs"]

    assert [c.key for c in satelliteStack(config, floorNamed(config, "Underground"))] == ["customs-underground"]

def test_factory_floors_are_built_on_the_ground_but_the_tunnels_stand_alone():
    config = realConfigs()["factory"]

    assert stackTiles(config, floorNamed(config, "2nd Floor")) == ["main", "2nd"]
    assert stackTiles(config, floorNamed(config, "3rd Floor")) == ["main", "2nd", "3rd"]
    assert stackTiles(config, floorNamed(config, "Tunnels")) == ["tunnels"]

def test_a_floor_without_tiles_keeps_the_ground_satellite():
    # Interchange has no tiles for its upper floors, but you can still switch floors for the names
    config = realConfigs()["interchange"]

    assert stackTiles(config, floorNamed(config, "2nd Floor")) == ["main"]
    assert stackTiles(config, floorNamed(config, "3rd Floor")) == ["main"]

def test_a_map_without_any_tiles_has_no_satellite():
    config = realConfigs()["terminal"]

    assert satelliteStack(config, None) == []

def test_a_map_without_tiles_has_no_ground_satellite():
    config = twoFloorConfig("factory")
    config.tilePath = ""

    assert satelliteConfig(config, None) is None

def test_the_real_factory_tunnels_have_satellite_tiles_and_hide_the_ground():
    path = Path(__file__).resolve().parent.parent / "assets" / "mapConfig.json"
    config = loadMapConfigs(path)["factory"]
    tunnels = next(l for l in config.layers if l.name == "Tunnels")
    svgText = (Path(__file__).resolve().parent.parent / "assets" / "maps" / "Factory.svg").read_text(encoding="utf-8")

    hidden = floorGroupsToHide(config, tunnels)
    result = hideGroups(svgText, hidden)

    assert satelliteConfig(config, tunnels).tilePath.endswith("/tunnels/{z}/{x}/{y}.png")
    assert sorted(hidden) == ["Ground_Floor", "Second_Floor", "Third_Floor"]
    for groupId in hidden:
        assert f'id="{groupId}" display="none"' in result
    assert 'id="Basement" display="none"' not in result

def test_the_real_interchange_config_shows_its_second_floor_by_default():
    path = Path(__file__).resolve().parent.parent / "assets" / "mapConfig.json"
    layers = loadMapConfigs(path)["interchange"].layers

    assert [l.svgLayer for l in layers] == ["First_Floor", "Second_Floor"]
    assert [l.show for l in layers] == [True, False]

def test_loadMapConfigs_missing_file_gives_empty_dict(tmp_path):
    assert loadMapConfigs(tmp_path / "nope.json") == {}

def test_loadMapConfigs_keys_by_normalizedName(tmp_path):
    path = tmp_path / "maps.json"
    path.write_text(json.dumps([rawEntry(), {"normalizedName": "flat", "maps": []}]))

    configs = loadMapConfigs(path)

    assert list(configs) == ["demo"]

def test_the_real_config_file_loads():
    path = Path(__file__).resolve().parent.parent / "assets" / "mapConfig.json"
    configs = loadMapConfigs(path)

    assert configs["customs"].bounds == ((698, -307), (-372, 237))
    assert any(label.text == "Dorms" for label in configs["customs"].labels)


# ---------------------------------------------------------------------------
# Map math
# ---------------------------------------------------------------------------

def test_the_two_bounds_corners_are_the_svg_corners():
    config = customsConfig()

    assert worldToSvg(698, -307, config, SVG_W, SVG_H) == pytest.approx((0, 0))
    assert worldToSvg(-372, 237, config, SVG_W, SVG_H) == pytest.approx((SVG_W, SVG_H))

def test_the_middle_of_the_bounds_is_the_middle_of_the_svg():
    assert worldToSvg(163, -35, customsConfig(), SVG_W, SVG_H) == pytest.approx((531.24, 267.59), abs=0.01)

def test_a_known_label_position():
    # the Dorms label
    assert worldToSvg(200, 150, customsConfig(), SVG_W, SVG_H) == pytest.approx((494.50, 449.59), abs=0.01)

def test_x_runs_backwards_on_a_rotation_180_map():
    config = customsConfig()
    left, _ = worldToSvg(500, 0, config, SVG_W, SVG_H)
    right, _ = worldToSvg(-300, 0, config, SVG_W, SVG_H)

    assert left < right

def test_unsupported_rotation_is_refused():
    config = customsConfig()
    config.rotation = 45

    assert not canProject(config)
    with pytest.raises(ValueError):
        worldToSvg(0, 0, config, SVG_W, SVG_H)

def test_a_map_without_a_matching_svg_cannot_be_projected():
    config = customsConfig()
    config.hasSvg = False

    assert not canProject(config)

def test_screenVector_turns_the_picture_for_each_rotation():
    assert screenVector(3, 5, 0) == (3, -5)
    assert screenVector(3, 5, 90) == (-5, -3)
    assert screenVector(3, 5, 180) == (-3, 5)
    assert screenVector(3, 5, 270) == (5, 3)

def test_a_rotation_90_map_puts_the_bounds_corners_on_the_svg_corners():
    # Factory-style: the first corner is the top-right, the second the bottom-left
    config = MapConfig(key="f", bounds=((77, -64.5), (-65.5, 67.4)), rotation=90,
                       transform=(1, 0, 1, 0), hasSvg=True)

    assert worldToSvg(77, -64.5, config, 130, 140) == pytest.approx((130, 0))
    assert worldToSvg(-65.5, 67.4, config, 130, 140) == pytest.approx((0, 140))

def test_rotation_0_and_270_maps_put_the_corners_on_the_svg_corners():
    bounds = ((100, 50), (-100, -50))
    flat = MapConfig(key="m", bounds=bounds, rotation=0, transform=(1, 0, 1, 0), hasSvg=True)
    turned = MapConfig(key="m", bounds=bounds, rotation=270, transform=(1, 0, 1, 0), hasSvg=True)

    assert worldToSvg(100, 50, flat, 200, 100) == pytest.approx((200, 0))
    assert worldToSvg(-100, -50, flat, 200, 100) == pytest.approx((0, 100))
    assert worldToSvg(100, 50, turned, 200, 100) == pytest.approx((200, 100))
    assert worldToSvg(-100, -50, turned, 200, 100) == pytest.approx((0, 0))

def test_labelFontSize_matches_customs_at_size_100():
    # the size the Customs names were tuned at: 12 map units
    assert labelFontSize(customsConfig(), MapLabel("a", 0, 0), SVG_W) == pytest.approx(12, abs=0.2)

def test_labelFontSize_scales_with_the_label_size():
    config = customsConfig()

    assert labelFontSize(config, MapLabel("a", 0, 0, size=50), SVG_W) == pytest.approx(
        labelFontSize(config, MapLabel("a", 0, 0, size=100), SVG_W) / 2)

def test_tileRange_divides_by_the_maps_tile_size():
    bounds = ((10, -3), (25, -1))
    big = MapConfig(key="m", bounds=bounds, rotation=0, transform=(1, 0, 1, 0), hasSvg=True,
                    tileSize=256, minZoom=0, maxZoom=5)
    small = MapConfig(key="m", bounds=bounds, rotation=0, transform=(1, 0, 1, 0), hasSvg=True,
                      tileSize=100, minZoom=0, maxZoom=5)

    # at zoom 3 the map spans 80..200 pixels across and 8..24 down
    assert tileRange(big, 3) == (0, 0, 0, 0)
    assert tileRange(small, 3) == (0, 2, 0, 0)

def test_satellite_image_lines_up_with_the_svg_corners():
    config = customsConfig()
    zoom = 4
    xMin, _, yMin, _ = tileRange(config, zoom)
    scaleX, scaleY, offsetX, offsetY = satelliteTransform(config, zoom, xMin, yMin, SVG_W, SVG_H)

    # a world point's pixel inside the stitched image, then through the transform
    for world, svgPoint in [((698, -307), (0, 0)), ((-372, 237), (SVG_W, SVG_H)), ((200, 150), (494.5, 449.59))]:
        u, v = worldToTile(*world, config, zoom)
        localX, localY = u - xMin * 256, v - yMin * 256
        placed = (localX * scaleX + offsetX, localY * scaleY + offsetY)
        assert placed == pytest.approx(svgPoint, abs=0.01)


# ---------------------------------------------------------------------------
# Satellite tiles
# ---------------------------------------------------------------------------

def test_tileUrl_fills_in_the_template():
    assert tileUrl("https://x.test/{z}/{x}/{y}.png", 3, 5, 7) == "https://x.test/3/5/7.png"

def test_downloadTiles_fetches_every_missing_tile_and_caches_them(tmp_path):
    config = customsConfig()
    urls = []

    def fakeFetch(url):
        urls.append(url)
        return b"png-bytes"

    assert downloadTiles(config, 3, tmp_path, fetch=fakeFetch) is True

    assert len(urls) == 8 * 6          # tileRange(customs, 3) is 8 columns by 6 rows
    assert urls[0] == "https://example.test/customs/main/3/0/1.png"
    assert readTile(tmp_path, "customs", 3, 0, 1) == b"png-bytes"
    assert missingTiles(config, 3, tmp_path) == []

def test_downloadTiles_second_run_downloads_nothing(tmp_path):
    config = customsConfig()
    downloadTiles(config, 3, tmp_path, fetch=lambda url: b"x")
    urls = []

    downloadTiles(config, 3, tmp_path, fetch=lambda url: urls.append(url) or b"x")

    assert urls == []

def test_a_missing_tile_is_remembered_and_reads_as_none(tmp_path):
    config = customsConfig()
    downloadTiles(config, 3, tmp_path, fetch=lambda url: None)

    assert readTile(tmp_path, "customs", 3, 0, 1) is None
    assert missingTiles(config, 3, tmp_path) == []

def test_readTile_for_an_unknown_tile_is_none(tmp_path):
    assert readTile(tmp_path, "customs", 3, 0, 1) is None

def test_downloadTiles_can_be_cancelled_and_keeps_what_it_has(tmp_path):
    config = customsConfig()

    finished = downloadTiles(config, 3, tmp_path, fetch=lambda url: b"x",
                             onProgress=lambda done, total: done < 5)

    assert finished is False
    assert len(missingTiles(config, 3, tmp_path)) == 8 * 6 - 5

def test_downloadTiles_reports_progress_up_to_the_total(tmp_path):
    seen = []

    downloadTiles(customsConfig(), 3, tmp_path, fetch=lambda url: b"x",
                  onProgress=lambda done, total: seen.append((done, total)))

    assert seen[0] == (0, 48)
    assert seen[-1] == (48, 48)

def test_downloadTiles_leaves_no_temp_files(tmp_path):
    downloadTiles(customsConfig(), 3, tmp_path, fetch=lambda url: b"x")

    assert list(tmp_path.rglob("*.tmp")) == []
    assert tileFilePath(tmp_path, "customs", 3, 0, 1).endswith("1.png")


# ---------------------------------------------------------------------------
# Hiding floors in an SVG
# ---------------------------------------------------------------------------

FLOOR_SVG = ('<svg viewBox="0 0 10 10"><g id="Ground_Level" class="a"><g id="Roads"/></g>'
             '<g class="shadow" id="First_Floor"><rect/></g><g id="Second_Floor"/></svg>')

def test_hideGroups_hides_only_the_named_groups():
    result = hideGroups(FLOOR_SVG, ["Second_Floor"])

    assert 'id="Second_Floor" display="none"' in result
    assert "display" not in result.replace('id="Second_Floor" display="none"', "")

def test_hideGroups_finds_the_id_after_other_attributes():
    assert 'id="First_Floor" display="none"' in hideGroups(FLOOR_SVG, ["First_Floor"])

def test_hideGroups_keeps_the_viewBox_and_everything_else():
    result = hideGroups(FLOOR_SVG, ["First_Floor", "Second_Floor"])

    assert 'viewBox="0 0 10 10"' in result
    assert '<g id="Ground_Level" class="a">' in result

def test_hideGroups_ignores_unknown_ids():
    assert hideGroups(FLOOR_SVG, ["Nope"]) == FLOOR_SVG

def test_hideGroups_does_not_match_a_longer_id():
    svg = '<svg><g id="Floor_2"/><g id="Floor_20"/></svg>'

    assert hideGroups(svg, ["Floor_2"]) == '<svg><g id="Floor_2" display="none"/><g id="Floor_20"/></svg>'

def test_hideGroups_works_on_the_real_customs_svg():
    path = Path(__file__).resolve().parent.parent / "assets" / "maps" / "Customs.svg"
    text = path.read_text(encoding="utf-8")
    result = hideGroups(text, ["Second_Floor", "Third_Floor", "Underground_Level"])

    assert result.count('display="none"') == 3
    assert 'viewBox="0 0 1062.4827 535.17401"' in result


# ---------------------------------------------------------------------------
# Objective locations
# ---------------------------------------------------------------------------

def rawZone(mapId=CUSTOMS, x=10.0, z=20.0, **overrides):
    zone = {"id": "zone", "map": mapId, "position": {"x": x, "y": 5.0, "z": z},
            "outline": [{"x": x - 1, "y": 4.0, "z": z - 1}, {"x": x + 1, "y": 4.0, "z": z - 1},
                        {"x": x + 1, "y": 4.0, "z": z + 1}], "top": 6.0, "bottom": 4.0}
    zone.update(overrides)
    return zone

def test_a_zone_becomes_a_location_with_an_outline_and_heights():
    objective = client.buildObjective(rawObjective(type="visit", zones=[rawZone()]), LOOKUP)

    place, = objective.locations
    assert (place.mapId, place.x, place.z) == (CUSTOMS, 10.0, 20.0)
    assert place.outline == [(9.0, 19.0), (11.0, 19.0), (11.0, 21.0)]
    assert (place.bottom, place.top, place.height()) == (4.0, 6.0, 5.0)

def test_quest_item_spots_become_locations_without_an_outline():
    spots = [{"map": CUSTOMS, "positions": [{"x": 1.0, "y": 2.0, "z": 3.0}, {"x": 4.0, "y": 5.0, "z": 6.0}]}]
    objective = client.buildObjective(rawObjective(type="findQuestItem", possibleLocations=spots), LOOKUP)

    assert [(l.x, l.z, l.height(), l.outline) for l in objective.locations] == [(1.0, 3.0, 2.0, []), (4.0, 6.0, 5.0, [])]

def test_map_variants_do_not_repeat_a_place():
    zones = [rawZone(GROUND_ZERO), rawZone(GROUND_ZERO_21)]
    objective = client.buildObjective(rawObjective(zones=zones), LOOKUP)

    assert [l.mapId for l in objective.locations] == [GROUND_ZERO]

def test_objectives_without_places_have_no_locations():
    assert client.buildObjective(rawObjective(), LOOKUP).locations == []
    assert client.buildObjective(rawObjective(zones=None, possibleLocations=None), LOOKUP).locations == []

def test_a_zone_without_a_position_is_skipped():
    objective = client.buildObjective(rawObjective(zones=[rawZone(position=None)]), LOOKUP)

    assert objective.locations == []

def test_a_location_without_heights_has_no_height():
    assert ObjectiveLocation(CUSTOMS, 1, 2).height() is None
    assert ObjectiveLocation(CUSTOMS, 1, 2, bottom=3).height() == 3

def place(mapId, x=0.0, z=0.0):
    return ObjectiveLocation(mapId, x, z)

def sampleMaps():
    return {CUSTOMS: GameMap(id=CUSTOMS, name="Customs"), FACTORY: GameMap(id=FACTORY, name="Factory"),
            GROUND_ZERO: GameMap(id=GROUND_ZERO, name="Ground Zero")}

def test_taskMaps_lists_the_maps_a_task_needs_by_name():
    task = Task(id="t", name="T", traderId="x", mapIds=[CUSTOMS],
                objectives=[Objective(id="a", description="", objType="visit", locations=[place(FACTORY)])])

    assert [m.name for m in taskMaps(task, sampleMaps())] == ["Customs", "Factory"]

def test_taskMaps_ignores_maps_we_dont_have():
    task = Task(id="t", name="T", traderId="x", mapIds=["unknown-map", CUSTOMS])

    assert [m.name for m in taskMaps(task, sampleMaps())] == ["Customs"]

def test_mapForObjective_prefers_the_current_map_then_the_first_by_name():
    objective = Objective(id="a", description="", objType="visit", locations=[place(GROUND_ZERO), place(FACTORY)])

    assert mapForObjective(objective, GROUND_ZERO, sampleMaps()) == GROUND_ZERO
    assert mapForObjective(objective, CUSTOMS, sampleMaps()) == FACTORY
    assert mapForObjective(Objective(id="b", description="", objType="shoot"), CUSTOMS, sampleMaps()) is None

def test_locationsOnMap_filters_by_map():
    objective = Objective(id="a", description="", objType="visit", locations=[place(CUSTOMS), place(FACTORY)])

    assert [l.mapId for l in locationsOnMap(objective, FACTORY)] == [FACTORY]

def test_objective_colours_wrap_round():
    assert objectiveColor(0) == OBJECTIVE_COLORS[0]
    assert objectiveColor(len(OBJECTIVE_COLORS)) == OBJECTIVE_COLORS[0]
    assert len(set(OBJECTIVE_COLORS)) == len(OBJECTIVE_COLORS)

def test_floorForHeight_trusts_only_maps_with_a_ground_band():
    configs = realConfigs()
    factory = configs["factory"]

    assert floorForHeight(factory, 1.0) == GROUND
    assert floorForHeight(factory, 4.5) is factory.layers[0]       # 2nd floor
    assert floorForHeight(factory, -3.0).name == "Tunnels"
    assert floorForHeight(configs["customs"], 4.0) is None          # terrain varies; can't tell
    assert floorForHeight(factory, None) is None


# ---------------------------------------------------------------------------
# Zoom limit and pins
# ---------------------------------------------------------------------------

def test_zooming_out_stops_at_the_limit():
    assert limitZoomOut(1.0, 0.87, 0.7) == pytest.approx(0.87)
    assert limitZoomOut(0.75, 0.87, 0.7) == pytest.approx(0.7 / 0.75)      # only part of the step
    assert limitZoomOut(0.7, 0.87, 0.7) == pytest.approx(1.0)               # already at the limit

def test_zooming_in_is_never_limited():
    assert limitZoomOut(0.1, 1.15, 0.7) == 1.15

def test_a_view_below_the_limit_does_not_jump_back_in():
    # e.g. the window grew, so the limit rose above the current zoom
    assert limitZoomOut(0.5, 0.87, 0.7) == 1.0

def test_svgToWorld_undoes_worldToSvg_for_every_rotation():
    for rotation in (0, 90, 180, 270):
        config = MapConfig(key="m", bounds=((100, 50), (-80, -60)), rotation=rotation,
                           transform=(1, 0, 1, 0), hasSvg=True)
        for world in [(10, 20), (-40, 33.5), (99, -59)]:
            x, y = worldToSvg(*world, config, 400, 250)
            assert svgToWorld(x, y, config, 400, 250) == pytest.approx(world)

def test_svgToWorld_on_a_real_map_finds_the_dorms_label():
    assert svgToWorld(494.50, 449.59, customsConfig(), SVG_W, SVG_H) == pytest.approx((200, 150), abs=0.05)

def test_a_pin_can_be_added_with_or_without_a_name(tmp_path):
    book = PinBook(tmp_path / "pins.json")

    named = book.add(CUSTOMS, 1.0, 2.0, "  Stash spot  ")
    blank = book.add(CUSTOMS, 3.0, 4.0)

    assert named.name == "Stash spot"       # trimmed
    assert blank.name == ""
    assert named.id != blank.id

def test_pins_are_saved_and_come_back(tmp_path):
    path = tmp_path / "pins.json"
    PinBook(path).add(FACTORY, 5.0, 6.0, "Exit", taskId="t1")

    pin, = PinBook(path).pins.values()

    assert (pin.mapId, pin.x, pin.z, pin.name, pin.taskId) == (FACTORY, 5.0, 6.0, "Exit", "t1")

def test_a_missing_pin_file_gives_no_pins(tmp_path):
    assert PinBook(tmp_path / "nope.json").pins == {}

def test_a_corrupt_pin_file_is_set_aside(tmp_path):
    path = tmp_path / "pins.json"
    path.write_text("{ not json")

    assert PinBook(path).pins == {}
    assert (tmp_path / "pins.json.corrupt").exists()

def test_a_pin_can_be_renamed_and_removed(tmp_path):
    book = PinBook(tmp_path / "pins.json")
    pin = book.add(CUSTOMS, 1.0, 2.0, "Old")

    book.rename(pin.id, "New")
    assert PinBook(tmp_path / "pins.json").pins[pin.id].name == "New"
    book.rename(pin.id, "")
    assert book.pins[pin.id].name == ""
    book.remove(pin.id)
    book.remove(pin.id)                      # removing twice is harmless
    assert PinBook(tmp_path / "pins.json").pins == {}

def test_pins_are_listed_per_map_and_optionally_per_task(tmp_path):
    book = PinBook(tmp_path / "pins.json")
    free = book.add(CUSTOMS, 0, 0, "free")
    mine = book.add(CUSTOMS, 0, 0, "mine", taskId="t1")
    book.add(CUSTOMS, 0, 0, "other task", taskId="t2")
    book.add(FACTORY, 0, 0, "other map")

    assert {p.id for p in book.forMap(CUSTOMS)} == {free.id, mine.id, [p for p in book.pins.values() if p.name == "other task"][0].id}
    assert [p.id for p in book.forMap(CUSTOMS, taskId="t1")] == [mine.id]

def test_listeners_hear_about_every_change(tmp_path):
    book = PinBook(tmp_path / "pins.json")
    heard = []
    book.subscribe(lambda: heard.append(1))

    pin = book.add(CUSTOMS, 0, 0)
    book.rename(pin.id, "x")
    book.remove(pin.id)

    assert len(heard) == 3
