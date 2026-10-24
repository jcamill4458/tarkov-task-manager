from tarkov.models import TaskProgress

class TaskTracker:
    def __init__(self, tasks, store):
        self.tasks = tasks
        self.store = store
        self.progress = store.load()

    def progressFor(self, taskId):
        if taskId not in self.progress:
            self.progress[taskId] = TaskProgress(taskId)
        return self.progress[taskId]

    def toggleStar(self, taskId):
        if not self.isAvailable(taskId):
            raise ValueError(f"Task {taskId} not available")
        record = self.progressFor(taskId)
        record.isStarred = not record.isStarred
        self.store.save(self.progress)

    def toggleAvailable(self, taskId):
        record = self.progressFor(taskId)
        record.isAvailable = not record.isAvailable
        if not record.isAvailable:
            record.isStarred = False
        self.store.save(self.progress)

    def isCompleted(self, taskId):
        progress = self.progress.get(taskId)
        if progress and progress.completeOverride is not None:
            return progress.completeOverride

        task = self.tasks[taskId]
        if progress:
            counts = progress.counts
        else:
            counts = {}

        for objective in task.objectives:
            if objective.optional:
                continue
            if counts.get(objective.id, 0) < objective.target:
                return False

        return True

    def countFor(self, taskId, objectiveId):
        progress = self.progress.get(taskId)
        if progress is None:
            return 0
        return progress.counts.get(objectiveId, 0)

    def isAvailable(self, taskId):
        progress = self.progress.get(taskId)
        if progress is None:
            return False
        return progress.isAvailable

    def isStarred(self, taskId):
        progress = self.progress.get(taskId)
        if progress is None:
            return False
        return progress.isStarred

    def updateProgress(self, taskId, objectiveId, change):
        task = self.tasks[taskId]
        target = None
        for objective in task.objectives:
            if objective.id == objectiveId:
                target = objective.target
                break

        if target is None:
            raise ValueError(f"Task {taskId} has no objective {objectiveId}")

        record = self.progressFor(taskId)
        record.increment(objectiveId, change)
        record.counts[objectiveId] = min(target, record.counts[objectiveId])
        record.completeOverride = None
        self.store.save(self.progress)

    def setComplete(self, taskId, status):
        task = self.tasks[taskId]
        record = self.progressFor(taskId)
        record.completeOverride = status

        if status:
            for objective in task.objectives:
                if objective.optional:
                    continue
                record.counts[objective.id] = objective.target

        self.store.save(self.progress)

    def _filterAndSort(self, tasks, includeCompleted):
        filteredTasks = []
        for task in tasks:
            if includeCompleted or not self.isCompleted(task.id):
                filteredTasks.append(task)
        return sorted(filteredTasks, key=lambda t: (not self.isStarred(t.id), t.name.lower()))

    def tasksForTrader(self, traderId, includeCompleted=True):
        traderTasks = []
        for task in self.tasks.values():
            if task.traderId == traderId and self.isAvailable(task.id):
                traderTasks.append(task)
        return self._filterAndSort(traderTasks, includeCompleted)

    def tasksForMap(self, mapId, includeCompleted=True):
        mapTasks = []
        for task in self.tasks.values():
            if mapId in task.mapIds:
                mapTasks.append(task)
        return self._filterAndSort(mapTasks, includeCompleted)

    def starredTasks(self, includeCompleted=True):
        starred = []
        for record in self.progress.values():
            if record.isStarred:
                task = self.tasks.get(record.taskId)
                if task is not None:
                    starred.append(task)
        return self._filterAndSort(starred, includeCompleted)

    def allTasksForTrader(self, traderId):
        allTasks = []
        for task in self.tasks.values():
            if task.traderId == traderId:
                allTasks.append(task)
        return sorted(allTasks, key=lambda t: t.name.lower())