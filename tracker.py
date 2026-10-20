from models import TaskProgress

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