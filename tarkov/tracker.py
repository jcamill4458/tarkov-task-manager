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
        record = self.progressFor(taskId)
        record.isStarred = not record.isStarred
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
        return sorted(filteredTasks, key=lambda t: t.name.lower())

    def tasksForTrader(self, traderId, includeCompleted=True):
        traderTasks = []
        for task in self.tasks.values():
            if task.traderId in traderId:
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