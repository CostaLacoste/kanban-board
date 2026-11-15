import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test("полный сценарий: доска, задача, повторение, архив и undo", async ({ page }) => {
  page.once("dialog", (dialog) => dialog.accept("Работа"));
  await page.getByRole("button", { name: "+ Доска" }).click();
  await expect(page.locator("#active-board-name")).toHaveText("Работа");

  await page.getByRole("button", { name: "Новая задача" }).click();
  await page.locator("#task-title").fill("Подготовить релиз");
  await page.locator("#task-tags").fill("релиз, команда");
  await page.locator("#task-deadline").fill("2026-11-14");
  await page.locator("#task-recurrence").selectOption("weekly");
  await page.getByRole("button", { name: "+ Добавить пункт" }).click();
  await page.locator(".checklist-editor__text").fill("Проверить сборку");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Подготовить релиз" })).toBeVisible();
  await expect(page.locator("#tag-filter option")).toHaveCount(3);
  await page.locator(".task-checklist__item input").check();
  await expect(page.locator('[data-stat="checklist"]')).toHaveText("1/1");

  await page.getByRole("button", { name: "Изменить" }).click();
  await page.locator("#task-status").selectOption("done");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(page.locator('[data-stat="done"]')).toHaveText("1");
  await expect(page.locator(".task-card")).toHaveCount(2);

  await page.getByRole("button", { name: "Архив", exact: true }).click();
  await expect(page.locator("#archive-count")).toHaveText("1");
  await page.getByRole("button", { name: /Архив 1/ }).click();
  await page.getByRole("button", { name: "Восстановить" }).click();
  await page.getByRole("button", { name: "Закрыть архив" }).click();
  await expect(page.locator('[data-stat="done"]')).toHaveText("1");

  await page.getByRole("button", { name: /Отменить/ }).click();
  await expect(page.locator("#archive-count")).toHaveText("1");
});

test("центр продуктивности, колонки, шаблоны и календарь", async ({ page }) => {
  await page.getByRole("button", { name: /Центр/ }).click();

  page.once("dialog", (dialog) => dialog.accept("Проверка"));
  await page.getByRole("button", { name: "+ Колонка" }).click();
  await expect(page.locator("[data-workflow-editor]")).toContainText("Проверка");

  page.once("dialog", (dialog) => dialog.accept("Анна"));
  await page.getByRole("button", { name: "+ Участник" }).click();
  await expect(page.locator("[data-member-list]")).toContainText("Анна");

  await page.locator('[data-setting="highContrast"]').check();
  await expect(page.locator("html")).toHaveAttribute("data-high-contrast", "true");
  await page.getByRole("button", { name: "Закрыть" }).click();

  await page.getByRole("button", { name: "Новая задача" }).click();
  await page.locator("#task-title").fill("Проверить релиз");
  await page.locator("#task-template").selectOption("template-release");
  await expect(page.locator("#task-cover")).toHaveValue("🚀");
  await page.locator("#task-assignee").selectOption("Анна");
  await page.locator("#task-deadline").fill("2026-11-14");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(page.locator(".task-card__cover")).toHaveText("🚀");

  await page.getByRole("button", { name: "Календарь" }).click();
  await page.locator("#calendar-month").fill("2026-11");
  await expect(page.locator("[data-calendar-grid]")).toContainText("Проверить релиз");
});

test("темы, сортировка и клавиатурные команды", async ({ page }) => {
  await page.locator("#theme-select").selectOption("dark");
  await expect(page.locator("body")).toHaveAttribute("data-theme", "dark");

  for (const theme of ["cyberpunk", "newspaper", "blueprint", "candy"]) {
    await page.locator("#theme-select").selectOption(theme);
    await expect(page.locator("body")).toHaveAttribute("data-theme", theme);
    expect(await page.evaluate(() => localStorage.getItem("flowboard-theme")))
      .toBe(JSON.stringify(theme));
  }

  await page.keyboard.press("n");
  await expect(page.locator("#task-dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("/");
  await expect(page.locator("#task-search")).toBeFocused();

  await page.locator("#sort-select").selectOption("priority");
  await expect(page.locator("#sort-select")).toHaveValue("priority");
});

test("переключает все языки, сохраняет выбор и включает RTL", async ({ page }) => {
  const languages = [
    ["en", "Main board", "ltr", "Productivity hub", "Process"],
    ["ig", "Bọdụ bụ isi", "ltr", "Ebe nrụpụta", "Usoro"],
    ["uz", "Asosiy doska", "ltr", "Samaradorlik markazi", "Jarayon"],
    ["uk", "Основна дошка", "ltr", "Центр продуктивності", "Процес"],
    ["he", "לוח ראשי", "rtl", "מרכז פרודוקטיביות", "תהליך"],
    ["yi", "הויפּט־ברעט", "rtl", "פּראָדוקטיוויטעט־צענטער", "פּראָצעס"],
  ];

  for (const [language, boardName, direction, hubTitle, processLabel] of languages) {
    await page.locator("#language-select").selectOption(language);
    await expect(page.locator("html")).toHaveAttribute("lang", language);
    await expect(page.locator("html")).toHaveAttribute("dir", direction);
    await expect(page.locator("#active-board-name")).toHaveText(boardName);
    expect(await page.evaluate(() => localStorage.getItem("flowboard-language")))
      .toBe(JSON.stringify(language));
    await page.locator('[data-action="open-productivity-hub"]').click();
    await expect(page.locator("#productivity-title")).toHaveText(hubTitle);
    await expect(page.locator('[data-i18n="hub.processLabel"]')).toHaveText(processLabel);
    await page.locator('[data-action="close-productivity-hub"]').click();
  }

  await page.reload();
  await expect(page.locator("#language-select")).toHaveValue("yi");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});

test("экспортирует и импортирует рабочее пространство", async ({ page }) => {
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Экспорт" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^flowboard-\d{4}-\d{2}-\d{2}\.json$/);

  const payload = {
    version: 2,
    activeBoardId: "imported",
    boards: [{ id: "imported", name: "Импортированная", createdAt: new Date().toISOString() }],
    tasks: [{
      id: "task-imported",
      boardId: "imported",
      title: "Задача из файла",
      description: "",
      status: "todo",
      priority: "medium",
      deadline: "",
      tags: ["импорт"],
      checklist: [],
      order: 0,
      archived: false,
      recurrence: "none",
      createdAt: new Date().toISOString(),
    }],
  };
  await page.locator("#workspace-import").setInputFiles({
    name: "flowboard-backup.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(payload)),
  });

  await expect(page.locator("#active-board-name")).toHaveText("Импортированная");
  await expect(page.getByRole("heading", { name: "Задача из файла" })).toBeVisible();
});

test("командная палитра, пакетные операции, время, автоматизации и вложения", async ({ page }) => {
  await page.getByRole("button", { name: "Новая задача" }).click();
  await page.locator("#task-title").fill("Задача с вложением");
  await page.locator("#task-estimate").fill("60");
  await page.locator("#task-deadline").fill("2000-01-01");
  await page.locator("#task-attachments").setInputFiles({
    name: "brief.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Flowboard brief"),
  });
  await expect(page.locator("[data-attachment-editor]")).toContainText("brief.txt");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();

  const firstCard = page.locator(".task-card").filter({ hasText: "Задача с вложением" });
  await expect(firstCard.getByRole("link", { name: /brief\.txt/ })).toBeVisible();
  await expect(firstCard.locator(".task-time")).toContainText("60m");
  await firstCard.getByRole("button", { name: "Старт" }).click();
  await expect(firstCard.getByRole("button", { name: "Стоп" })).toBeVisible();
  await firstCard.getByRole("button", { name: "Стоп" }).click();

  await page.getByRole("button", { name: "Новая задача" }).click();
  await page.locator("#task-title").fill("Вторая задача");
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();

  await page.locator('[data-action="select-task"]').nth(0).check();
  await page.locator('[data-action="select-task"]').nth(1).check();
  await expect(page.locator("[data-batch-count]")).toHaveText("2");
  await page.locator("#batch-priority").selectOption("high");
  await page.locator('[data-action="apply-batch"]').click();
  await expect(page.locator(".priority-badge--high")).toHaveCount(2);

  await page.keyboard.press("ControlOrMeta+K");
  await expect(page.locator("#command-dialog")).toBeVisible();
  await page.locator("#command-search").fill("календар");
  await page.locator('[data-command="show-calendar"]').click();
  await expect(page.locator("[data-calendar-view]")).toBeVisible();

  await page.locator('[data-action="open-productivity-hub"]').click();
  await page.locator('[data-automation="overdueHigh"]').check();
  await page.locator('[data-action="close-productivity-hub"]').click();
  await page.getByRole("button", { name: "Доска", exact: true }).click();
  await expect(firstCard.locator(".priority-badge--high")).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("flowboard-automations"))))
    .toMatchObject({ overdueHigh: true });
});

test("новые инструменты помещаются на мобильном экране", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('[data-action="open-command-palette"]')).toBeVisible();

  await page.keyboard.press("ControlOrMeta+K");
  await expect(page.locator("#command-dialog")).toBeVisible();
  const commandBox = await page.locator("#command-dialog").boundingBox();
  expect(commandBox.x).toBeGreaterThanOrEqual(0);
  expect(commandBox.x + commandBox.width).toBeLessThanOrEqual(390);
  await page.keyboard.press("Escape");

  await page.locator('[data-action="open-productivity-hub"]').click();
  await expect(page.locator('[data-automation="overdueHigh"]')).toBeAttached();
  const hasHorizontalOverflow = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});
