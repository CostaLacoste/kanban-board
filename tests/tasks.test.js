import assert from "node:assert/strict";
import { beforeEach, describe, test } from "node:test";

import { getTasks, setTasks } from "../js/state.js";
import {
  createTask,
  areDependenciesComplete,
  deleteTask,
  getRecurringTaskData,
  getTaskById,
  moveTask,
  updateTask,
} from "../js/tasks.js";

beforeEach(() => {
  setTasks([]);
});

describe("задачи", () => {
  test("создаёт задачу и нормализует пользовательские данные", () => {
    const task = createTask({
      title: "  Подготовить релиз  ",
      description: "  Проверить сборку  ",
      status: "progress",
      priority: "high",
      deadline: "2026-12-01",
      tags: " Релиз, дизайн, релиз, важно, qa, команда, лишний ",
      checklist: [
        { text: "  Собрать проект  ", done: true },
        { text: "Проверить тесты", done: false },
        { text: "   ", done: true },
      ],
    });

    assert.equal(task.title, "Подготовить релиз");
    assert.equal(task.description, "Проверить сборку");
    assert.deepEqual(task.tags, ["релиз", "дизайн", "важно", "qa", "команда"]);
    assert.equal(task.checklist.length, 2);
    assert.equal(task.checklist[0].text, "Собрать проект");
    assert.equal(task.checklist[0].done, true);
    assert.ok(task.checklist.every((item) => item.id));
    assert.ok(task.id);
    assert.ok(task.createdAt);
    assert.equal(getTasks().length, 1);
  });

  test("сохраняет вложения и данные учёта времени", () => {
    const task = createTask({
      title: "Задача с файлами",
      estimatedMinutes: 90,
      timeSpentSeconds: 125,
      timerStartedAt: "2026-11-15T10:00:00.000Z",
      attachments: [{
        id: "file-1",
        name: "brief.txt",
        type: "text/plain",
        size: 12,
        dataUrl: "data:text/plain;base64,SGVsbG8=",
      }],
    });

    assert.equal(task.estimatedMinutes, 90);
    assert.equal(task.timeSpentSeconds, 125);
    assert.equal(task.timerStartedAt, "2026-11-15T10:00:00.000Z");
    assert.equal(task.attachments[0].name, "brief.txt");
    assert.equal(task.attachments[0].dataUrl, "data:text/plain;base64,SGVsbG8=");
  });

  test("сохраняет цель, даты дорожной карты и контрольную точку", () => {
    const task = createTask({
      title: "Milestone", startDate: "2030-01-01", deadline: "2030-02-01",
      goalId: "goal-1", milestone: true,
    });
    assert.equal(task.startDate, "2030-01-01");
    assert.equal(task.goalId, "goal-1");
    assert.equal(task.milestone, true);
  });

  test("сохраняет значения пользовательских полей", () => {
    const task = createTask({
      title: "Custom data",
      customValues: { cost: 42, channel: "GitHub" },
    });
    assert.deepEqual(task.customValues, { cost: 42, channel: "GitHub" });
    assert.deepEqual(updateTask(task.id, { customValues: { cost: 84 } }).customValues, { cost: 84 });
  });

  test("поддерживает пользовательский статус и нормализует приоритет", () => {
    const task = createTask({
      title: "Задача",
      status: "unknown",
      priority: "urgent",
    });

    assert.equal(task.status, "unknown");
    assert.equal(task.priority, "low");
  });

  test("проверяет завершение зависимостей", () => {
    setTasks([
      { id: "a", title: "A", status: "done", priority: "low" },
      { id: "b", title: "B", status: "todo", priority: "low", dependsOn: ["a"] },
      { id: "c", title: "C", status: "todo", priority: "low", dependsOn: ["missing"] },
    ]);

    assert.equal(areDependenciesComplete(getTasks()[1]), true);
    assert.equal(areDependenciesComplete(getTasks()[2]), false);
  });

  test("не создаёт задачу без названия", () => {
    assert.throws(
      () => createTask({ title: "   " }),
      /Название задачи не может быть пустым/,
    );
    assert.equal(getTasks().length, 0);
  });

  test("обновляет задачу, сохраняя идентификатор и дату создания", () => {
    const original = createTask({ title: "Черновик", tags: "идея" });
    const updated = updateTask(original.id, {
      title: "Готовый текст",
      checklist: [{ id: "step-1", text: "Вычитать", done: true }],
    });

    assert.equal(updated.id, original.id);
    assert.equal(updated.createdAt, original.createdAt);
    assert.equal(updated.title, "Готовый текст");
    assert.deepEqual(updated.tags, ["идея"]);
    assert.deepEqual(updated.checklist, [
      { id: "step-1", text: "Вычитать", done: true },
    ]);
  });

  test("возвращает null при обновлении отсутствующей задачи", () => {
    assert.equal(updateTask("missing", { title: "Нет" }), null);
  });

  test("находит и удаляет задачу", () => {
    const task = createTask({ title: "Удалить" });

    assert.equal(getTaskById(task.id)?.title, "Удалить");
    assert.equal(deleteTask(task.id), true);
    assert.equal(deleteTask(task.id), false);
    assert.equal(getTaskById(task.id), undefined);
  });

  test("создаёт данные следующей повторяющейся задачи", () => {
    const next = getRecurringTaskData({
      title: "Отчёт",
      recurrence: "weekly",
      deadline: "2026-11-14",
      checklist: [{ id: "1", text: "Собрать данные", done: true }],
    }, new Date(2026, 10, 14));

    assert.equal(next.status, "todo");
    assert.equal(next.deadline, "2026-11-21");
    assert.equal(next.checklist[0].done, false);
    assert.equal(next.checklist[0].id, "");
  });

  test("перемещает задачу и обновляет ручной порядок", () => {
    setTasks([
      { id: "a", title: "A", boardId: "default", status: "todo", priority: "low", order: 0 },
      { id: "b", title: "B", boardId: "default", status: "progress", priority: "low", order: 0 },
      { id: "c", title: "C", boardId: "default", status: "progress", priority: "low", order: 1 },
    ]);

    const moved = moveTask("a", "progress", "c");
    const progressTasks = getTasks()
      .filter((task) => task.status === "progress")
      .sort((first, second) => first.order - second.order);

    assert.equal(moved.status, "progress");
    assert.deepEqual(progressTasks.map((task) => task.id), ["b", "a", "c"]);
  });
});
