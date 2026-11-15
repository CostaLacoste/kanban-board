let tasks = [];

function cloneTask(task) {
  return {
    ...task,
    boardId: String(task.boardId || "default"),
    order: Number.isFinite(Number(task.order)) ? Number(task.order) : 0,
    archived: Boolean(task.archived),
    recurrence: ["none", "daily", "weekly", "monthly"].includes(task.recurrence)
      ? task.recurrence
      : "none",
    tags: Array.isArray(task.tags) ? [...task.tags] : [],
    checklist: Array.isArray(task.checklist)
      ? task.checklist.map((item) => ({ ...item }))
      : [],
    dependsOn: Array.isArray(task.dependsOn) ? [...task.dependsOn] : [],
    comments: Array.isArray(task.comments)
      ? task.comments.map((comment) => ({ ...comment }))
      : [],
    attachments: Array.isArray(task.attachments)
      ? task.attachments.map((attachment) => ({ ...attachment }))
      : [],
    estimatedMinutes: Math.max(0, Number(task.estimatedMinutes) || 0),
    timeSpentSeconds: Math.max(0, Number(task.timeSpentSeconds) || 0),
    timerStartedAt: String(task.timerStartedAt || ""),
  };
}

export function getTasks() {
  return tasks.map(cloneTask);
}

export function setTasks(newTasks) {
  tasks = Array.isArray(newTasks)
    ? newTasks.map(cloneTask)
    : [];
}
