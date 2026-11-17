import assert from "node:assert/strict";
import test from "node:test";

import {
  getApiConfiguration,
  getAttachmentUrl,
  logoutAccount,
  mergeWorkspaceForConflict,
  setApiConfiguration,
} from "../js/api.js";

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

test("сохраняет настройки аккаунта и удаляет токен при выходе", () => {
  const values = new Map();
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
  setApiConfiguration("https://api.example.com/api/v1/", "secret-token");
  assert.deepEqual(getApiConfiguration(), {
    url: "https://api.example.com/api/v1",
    hasToken: true,
  });
  logoutAccount();
  assert.equal(getApiConfiguration().hasToken, false);
  delete globalThis.localStorage;
});
