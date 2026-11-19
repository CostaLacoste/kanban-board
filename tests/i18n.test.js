import assert from "node:assert/strict";
import test from "node:test";

import { getLanguage, getLocale, getTranslationKeys, hasTranslation, setLanguage, t } from "../js/i18n.js";

test("переключает язык и подставляет переменные", () => {
  setLanguage("en");

  assert.equal(getLanguage(), "en");
  assert.equal(getLocale(), "en-US");
  assert.equal(t("board.default"), "Main board");
  assert.equal(t("notice.archived", { count: 3 }), "Archived: 3");
});

test("поддерживает Igbo, узбекский, украинский, иврит и идиш", () => {
  const translations = {
    ig: "Bọdụ bụ isi",
    uz: "Asosiy doska",
    uk: "Основна дошка",
    he: "לוח ראשי",
    yi: "הויפּט־ברעט",
  };

  Object.entries(translations).forEach(([language, expected]) => {
    setLanguage(language);
    assert.equal(t("board.default"), expected);
  });
});

test("использует русский для неизвестного языка", () => {
  setLanguage("unknown");

  assert.equal(getLanguage(), "ru");
  assert.equal(t("board.default"), "Основная доска");
});

test("центр продуктивности полностью переведён на все языки", () => {
  const hubKeys = getTranslationKeys("ru").filter((key) => key.startsWith("hub."));

  for (const language of ["ru", "ig", "en", "uz", "uk", "he", "yi"]) {
    const missing = hubKeys.filter((key) => !hasTranslation(language, key));
    assert.deepEqual(missing, [], `${language}: ${missing.join(", ")}`);
  }
});

test("новые инструменты полностью переведены на все языки", () => {
  const prefixes = [
    "command.", "batch.", "time.", "attachment.", "automation.",
    "account.", "comment.", "collaboration.",
    "notifications.", "planning.",
    "platform.", "security.",
  ];
  const featureKeys = getTranslationKeys("ru").filter((key) =>
    prefixes.some((prefix) => key.startsWith(prefix)),
  );

  for (const language of ["ru", "ig", "en", "uz", "uk", "he", "yi"]) {
    const missing = featureKeys.filter((key) => !hasTranslation(language, key));
    assert.deepEqual(missing, [], `${language}: ${missing.join(", ")}`);
  }
});
