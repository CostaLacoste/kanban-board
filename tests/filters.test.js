import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { filterTasks } from "../js/filters.js";

const tasks = [
  {
    id: "1",
    title: "Подготовить релиз",
    description: "Проверить интерфейс",
    priority: "high",
    tags: ["релиз", "дизайн"],
    checklist: [{ text: "Обновить документацию", done: false }],
    assignee: "Анна",
    deadline: "2030-05-20",
  },
  {
    id: "2",
    title: "Купить кофе",
    description: "Для команды",
    priority: "low",
    tags: ["личное"],
    checklist: [],
    assignee: "Борис",
    deadline: "2030-06-10",
  },
];

describe("фильтрация задач", () => {
  test("ищет по названию и описанию без учёта регистра", () => {
    assert.deepEqual(filterTasks(tasks, "РЕЛИЗ", "all").map((task) => task.id), ["1"]);
    assert.deepEqual(filterTasks(tasks, "команды", "all").map((task) => task.id), ["2"]);
  });

  test("ищет по тегам и пунктам чек-листа", () => {
    assert.deepEqual(filterTasks(tasks, "дизайн", "all").map((task) => task.id), ["1"]);
    assert.deepEqual(filterTasks(tasks, "документацию", "all").map((task) => task.id), ["1"]);
  });

  test("совмещает поиск, приоритет и тег", () => {
    assert.deepEqual(filterTasks(tasks, "проверить", "high", "релиз").map((task) => task.id), ["1"]);
    assert.deepEqual(filterTasks(tasks, "проверить", "low", "релиз"), []);
  });

  test("возвращает все задачи при пустом поиске и фильтрах all", () => {
    assert.equal(filterTasks(tasks, "", "all", "all").length, 2);
  });

  test("поддерживает старые задачи без тегов и чек-листа", () => {
    const legacyTask = { title: "Старая", description: "", priority: "low" };
    assert.deepEqual(filterTasks([legacyTask], "старая", "all", "all"), [legacyTask]);
  });

  test("фильтрует по исполнителю и диапазону срока", () => {
    const result = filterTasks(tasks, "", "all", "all", {
      assignee: "Анна", deadlineFrom: "2030-05-01", deadlineTo: "2030-05-31",
    });
    assert.deepEqual(result.map((task) => task.id), ["1"]);
  });
});
