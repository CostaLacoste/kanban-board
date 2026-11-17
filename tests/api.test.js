import assert from "node:assert/strict";
import test from "node:test";

import { getAttachmentUrl, mergeWorkspaceForConflict } from "../js/api.js";

test("при конфликте синхронизации сохраняет локальные задачи и новую ревизию", () => {
  const local = { boards: [{ id: "local" }], tasks: [{ id: "task-local" }], theme: "candy" };
  const remote = { revision: 7, boards: [{ id: "remote" }], tasks: [{ id: "task-remote" }], language: "en" };
  const merged = mergeWorkspaceForConflict(local, remote);
  assert.equal(merged.revision, 7);
  assert.deepEqual(merged.tasks, local.tasks);
  assert.deepEqual(merged.boards, local.boards);
  assert.equal(merged.language, "en");
  assert.equal(merged.theme, "candy");
});

test("использует встроенный data URL вложения без API", () => {
  assert.equal(getAttachmentUrl({ dataUrl: "data:text/plain,ok" }), "data:text/plain,ok");
});
