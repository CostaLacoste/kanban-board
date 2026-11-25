import assert from "node:assert/strict";
import test from "node:test";

import { importExternalData } from "../js/importers.js";

test("импортирует карточки Trello", () => {
  const tasks = importExternalData("trello", {
    lists: [{ id: "done", name: "Done" }], labels: [{ id: "l1", name: "release" }],
    cards: [{ name: "Ship", desc: "Deploy", idList: "done", idLabels: ["l1"], due: "2030-01-01T00:00:00Z" }],
  }, "board-1");
  assert.equal(tasks[0].status, "done");
  assert.equal(tasks[0].boardId, "board-1");
  assert.deepEqual(tasks[0].tags, ["release"]);
});

test("импортирует задачи Jira и страницы Notion", () => {
  const jira = importExternalData("jira", { issues: [{ fields: { summary: "Fix", status: { name: "In Progress" }, priority: { name: "Highest" }, labels: ["bug"] } }] });
  assert.equal(jira[0].priority, "high");
  assert.equal(jira[0].status, "progress");
  const notion = importExternalData("notion", { results: [{ properties: { Name: { type: "title", title: [{ plain_text: "Plan" }] }, Tags: { type: "multi_select", multi_select: [{ name: "idea" }] } } }] });
  assert.equal(notion[0].title, "Plan");
  assert.deepEqual(notion[0].tags, ["idea"]);
});
