function dateKey(date = new Date()) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}

export const defaultAutomations = {
  overdueHigh: false,
  checklistDone: false,
  dueTodayTag: false,
  rules: [],
};

export function createAutomationRule({ name, trigger, triggerValue = "", action, actionValue = "" }) {
  return {
    id: globalThis.crypto?.randomUUID?.() || `rule-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: String(name || "New rule").trim().slice(0, 100),
    trigger: String(trigger || "overdue"),
    triggerValue: String(triggerValue || "").trim(),
    action: String(action || "setPriority"),
    actionValue: String(actionValue || "").trim(),
    active: true,
  };
}

function customRuleMatches(task, rule, today) {
  if (!rule?.active) return false;
  if (rule.trigger === "overdue") return Boolean(task.deadline && task.deadline < today && task.status !== "done");
  if (rule.trigger === "dueToday") return task.deadline === today;
  if (rule.trigger === "status") return task.status === rule.triggerValue;
  if (rule.trigger === "priority") return task.priority === rule.triggerValue;
  if (rule.trigger === "tag") return (task.tags || []).includes(rule.triggerValue);
  return false;
}

function runCustomRule(task, rule) {
  if (rule.action === "setPriority" && ["low", "medium", "high"].includes(rule.actionValue)) {
    return { ...task, priority: rule.actionValue };
  }
  if (rule.action === "setStatus" && ["todo", "progress", "done"].includes(rule.actionValue)) {
    return { ...task, status: rule.actionValue, completedAt: rule.actionValue === "done" ? new Date().toISOString() : task.completedAt };
  }
  if (rule.action === "addTag" && rule.actionValue && !(task.tags || []).includes(rule.actionValue)) {
    return { ...task, tags: [...(task.tags || []), rule.actionValue].slice(0, 5) };
  }
  return task;
}

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
    for (const rule of settings.rules || []) {
      if (customRuleMatches(next, rule, today)) next = runCustomRule(next, rule);
    }
    if (next !== task) changed = true;
    return next;
  });
  return { tasks: nextTasks, changed };
}
