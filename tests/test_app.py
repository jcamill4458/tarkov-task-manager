"""
Tests for the Tarkov task tracker.

Run from the project root (the folder with tracker.py) with:

    pytest

Everything here uses small made-up data and temporary files, so it needs no
network and never touches your real progress file.
"""
import pytest

from tarkov.api_client import TarkovApiClient
from tarkov.local_store import JsonStore
from tarkov.models import GameMap, Objective, Task, TaskProgress, Trader
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
        objectives=[
            Objective(id="o1", description="Visit the place", objType="visit", target=1),
            Objective(id="o2", description="Hand over items", objType="giveItem", target=3),
            Objective(id="o3", description="Bonus", objType="shoot", optional=True, target=2),
        ],
    )
    bravo = Task(
        id="t2", name="bravo", traderId=TRADER_A, wikiUrl="",
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


# ---------------------------------------------------------------------------
# TaskProgress
# ---------------------------------------------------------------------------

def test_progress_defaults():
    p = TaskProgress(taskId="x")
    assert p.isStarred is False
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


def test_save_accepts_what_load_returns(storePath):
    store = JsonStore(storePath)
    store.save({"t1": TaskProgress(taskId="t1", isStarred=True)})
    loaded = store.load()
    store.save(loaded)
    assert store.load() == loaded


# ---------------------------------------------------------------------------
# TaskTracker: records and stars
# ---------------------------------------------------------------------------

def test_progressFor_creates_a_record_once(tracker):
    first = tracker.progressFor("t1")
    assert tracker.progressFor("t1") is first


def test_toggleStar_flips_and_persists(tracker, storePath):
    tracker.toggleStar("t1")
    assert tracker.progressFor("t1").isStarred is True
    assert freshTracker(storePath).progressFor("t1").isStarred is True

    tracker.toggleStar("t1")
    assert freshTracker(storePath).progressFor("t1").isStarred is False


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
    ids = [t.id for t in tracker.tasksForTrader(TRADER_A)]
    assert sorted(ids) == ["t1", "t2"]


def test_tasksForTrader_sorts_ignoring_case(tracker):
    names = [t.name for t in tracker.tasksForTrader(TRADER_A)]
    assert names == ["bravo", "Yankee"]


def test_tasksForTrader_can_hide_tasks_completed_by_override(tracker):
    tracker.setComplete("t1", True)
    shown = [t.id for t in tracker.tasksForTrader(TRADER_A, includeCompleted=False)]
    assert shown == ["t2"]
    everything = [t.id for t in tracker.tasksForTrader(TRADER_A)]
    assert sorted(everything) == ["t1", "t2"]


def test_tasksForTrader_can_hide_tasks_completed_by_counting(tracker):
    tracker.updateProgress("t2", "o4", 1)
    shown = [t.id for t in tracker.tasksForTrader(TRADER_A, includeCompleted=False)]
    assert shown == ["t1"]


def test_tasksForTrader_unknown_trader_is_empty(tracker):
    assert tracker.tasksForTrader("nobody") == []


# ---------------------------------------------------------------------------
# TaskTracker: starredTasks (skipped until the method exists)
# ---------------------------------------------------------------------------

needsStarred = pytest.mark.skipif(
    not hasattr(TaskTracker, "starredTasks"),
    reason="starredTasks is not written yet",
)


@needsStarred
def test_starredTasks_returns_only_starred_sorted(tracker):
    tracker.toggleStar("t1")
    tracker.toggleStar("t3")
    names = [t.name for t in tracker.starredTasks()]
    assert names == ["Charlie", "Yankee"]


@needsStarred
def test_starredTasks_ignores_ids_that_are_not_in_tasks(tracker):
    tracker.progress["ghost"] = TaskProgress(taskId="ghost", isStarred=True)
    tracker.toggleStar("t1")
    assert [t.id for t in tracker.starredTasks()] == ["t1"]


@needsStarred
def test_starredTasks_can_hide_completed(tracker):
    tracker.toggleStar("t1")
    tracker.toggleStar("t2")
    tracker.setComplete("t1", True)
    shown = [t.id for t in tracker.starredTasks(includeCompleted=False)]
    assert shown == ["t2"]


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