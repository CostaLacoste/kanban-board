function dateKey(date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}

export function parseSearchQuery(search, now = new Date()) {
  const filters = {};
  const text = [];
  const today = dateKey(now);
  for (const token of String(search || "").trim().split(/\s+/).filter(Boolean)) {
    const match = token.match(/^([a-z-]+):(.+)$/i);
    if (!match) { text.push(token); continue; }
    const [, rawKey, rawValue] = match;
    const key = rawKey.toLowerCase();
    const value = rawValue.toLowerCase();
    if (["status", "priority", "tag", "assignee", "board"].includes(key)) filters[key] = value;
    else if (key === "due") {
      filters.due = value;
      filters.today = today;
      const week = new Date(now); week.setDate(week.getDate() + 7);
      filters.weekEnd = dateKey(week);
    } else text.push(token);
  }
  return { text: text.join(" ").toLowerCase(), filters };
}

export function filterTasks(tasks, search, priority, tag = "all", advanced = {}) {
  const parsed = parseSearchQuery(search, advanced.now || new Date());
  const normalizedSearch = parsed.text;

  return tasks.filter((task) => {
    const title = String(task.title ?? "").toLowerCase();
    const description = String(task.description ?? "").toLowerCase();
    const tags = Array.isArray(task.tags) ? task.tags : [];
    const checklistText = Array.isArray(task.checklist)
      ? task.checklist.map((item) => item.text).join(" ").toLowerCase()
      : "";
    const matchesSearch = !normalizedSearch ||
      title.includes(normalizedSearch) ||
      description.includes(normalizedSearch) ||
      tags.some((taskTag) => taskTag.includes(normalizedSearch)) ||
      checklistText.includes(normalizedSearch);

    const selectedPriority = parsed.filters.priority || priority;
    const selectedTag = parsed.filters.tag || tag;
    const selectedAssignee = parsed.filters.assignee === "me" ? advanced.currentUser : (parsed.filters.assignee || advanced.assignee);
    const matchesPriority = selectedPriority === "all" || !selectedPriority || task.priority === selectedPriority;
    const matchesTag = selectedTag === "all" || !selectedTag || tags.map(String).map((item) => item.toLowerCase()).includes(selectedTag);
    const matchesAssignee = !selectedAssignee || selectedAssignee === "all"
      || String(task.assignee || "").toLowerCase() === String(selectedAssignee).toLowerCase();
    const deadline = String(task.deadline || "");
    const matchesDeadlineFrom = !advanced.deadlineFrom || (deadline && deadline >= advanced.deadlineFrom);
    const matchesDeadlineTo = !advanced.deadlineTo || (deadline && deadline <= advanced.deadlineTo);

    const matchesStatus = !parsed.filters.status || task.status === parsed.filters.status;
    const matchesBoard = !parsed.filters.board || String(task.boardId || "").toLowerCase() === parsed.filters.board;
    const due = parsed.filters.due;
    const matchesDue = !due
      || (due === "today" && deadline === parsed.filters.today)
      || (due === "overdue" && deadline && deadline < parsed.filters.today && task.status !== "done")
      || (due === "this-week" && deadline && deadline >= parsed.filters.today && deadline <= parsed.filters.weekEnd);

    return matchesSearch && matchesPriority && matchesTag && matchesStatus && matchesBoard
      && matchesAssignee && matchesDeadlineFrom && matchesDeadlineTo && matchesDue;
  });
}
