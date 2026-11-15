function dateKey(date = new Date()) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}

export const defaultAutomations = {
  overdueHigh: false,
  checklistDone: false,
  dueTodayTag: false,
};

export function applyAutomations(tasks, rules = {}, now = new Date()) {
  const settings = { ...defaultAutomations, ...rules };
  const today = dateKey(now);
  let changed = false;
  const nextTasks = (Array.isArray(tasks) ? tasks : []).map((task) => {
    let next = task;
    if (settings.overdueHigh && task.deadline && task.deadline < today && task.status !== "done" && task.priority !== "high") {
      next = { ...next, priority: "high" };
    }
    const checklist = Array.isArray(next.checklist) ? next.checklist : [];
    if (settings.checklistDone && checklist.length > 0 && checklist.every((item) => item.done) && next.status !== "done") {
      next = { ...next, status: "done", completedAt: new Date(now).toISOString() };
    }
    if (settings.dueTodayTag && next.deadline === today && !(next.tags ?? []).includes("today")) {
      next = { ...next, tags: [...(next.tags ?? []), "today"].slice(0, 5) };
    }
    if (next !== task) changed = true;
    return next;
  });
  return { tasks: nextTasks, changed };
}
