import assert from "node:assert/strict";
import test from "node:test";

import { applyAutomations } from "../js/automations.js";

const now = new Date("2026-11-15T12:00:00.000Z");

test("повышает приоритет просроченной незавершённой задачи", () => {
  const result = applyAutomations([
    { id: "1", status: "todo", priority: "low", deadline: "2026-11-14", tags: [], checklist: [] },
  ], { overdueHigh: true }, now);

  assert.equal(result.changed, true);
  assert.equal(result.tasks[0].priority, "high");
});

test("завершает задачу с полностью выполненным чек-листом", () => {
  const result = applyAutomations([
    { id: "1", status: "progress", priority: "medium", tags: [], checklist: [{ done: true }] },
  ], { checklistDone: true }, now);

  assert.equal(result.tasks[0].status, "done");
  assert.equal(result.tasks[0].completedAt, now.toISOString());
});

test("добавляет тег today один раз в день срока", () => {
  const first = applyAutomations([
    { id: "1", status: "todo", priority: "low", deadline: "2026-11-15", tags: [], checklist: [] },
  ], { dueTodayTag: true }, now);
  const second = applyAutomations(first.tasks, { dueTodayTag: true }, now);

  assert.deepEqual(second.tasks[0].tags, ["today"]);
  assert.equal(second.changed, false);
});
