function cleanText(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((item) => item.plain_text || item.text?.content || "").join("");
  if (value?.content) return value.content.map((item) => item.plain_text || item.text?.content || "").join("");
  return "";
}

function statusFrom(value = "") {
  const text = String(value).toLowerCase();
  if (/done|closed|complete|готов|заверш/.test(text)) return "done";
  if (/progress|doing|review|работ/.test(text)) return "progress";
  return "todo";
}

function task(base, boardId) {
  return {
    id: globalThis.crypto?.randomUUID?.() || `import-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    boardId, title: String(base.title || "Imported task").slice(0, 100),
    description: String(base.description || "").slice(0, 2000), status: base.status || "todo",
    priority: base.priority || "medium", deadline: String(base.deadline || "").slice(0, 10),
    tags: [...new Set(base.tags || [])].map(String).slice(0, 5), assignee: String(base.assignee || ""),
    checklist: [], attachments: [], archived: false, createdAt: new Date().toISOString(),
  };
}

export function importExternalData(provider, payload, boardId = "default") {
  if (provider === "trello") {
    const lists = new Map((payload.lists || []).map((item) => [item.id, item.name]));
    const labels = new Map((payload.labels || []).map((item) => [item.id, item.name || item.color]));
    return (payload.cards || []).filter((item) => !item.closed).map((item) => task({
      title: item.name, description: item.desc, status: statusFrom(lists.get(item.idList)), deadline: item.due,
      tags: (item.idLabels || []).map((id) => labels.get(id)).filter(Boolean),
    }, boardId));
  }
  if (provider === "jira") {
    return (payload.issues || []).map((item) => task({
      title: item.fields?.summary, description: item.fields?.description?.content ? JSON.stringify(item.fields.description.content) : item.fields?.description,
      status: statusFrom(item.fields?.status?.name), deadline: item.fields?.duedate,
      priority: /high|highest/i.test(item.fields?.priority?.name) ? "high" : /low|lowest/i.test(item.fields?.priority?.name) ? "low" : "medium",
      tags: item.fields?.labels || [], assignee: item.fields?.assignee?.displayName || "",
    }, boardId));
  }
  if (provider === "notion") {
    return (payload.results || []).map((item) => {
      const props = item.properties || {};
      const titleProp = Object.values(props).find((value) => value.type === "title")?.title;
      const statusProp = Object.values(props).find((value) => ["status", "select"].includes(value.type))?.status
        || Object.values(props).find((value) => value.type === "select")?.select;
      const tagsProp = Object.values(props).find((value) => value.type === "multi_select")?.multi_select || [];
      const dateProp = Object.values(props).find((value) => value.type === "date")?.date;
      return task({ title: cleanText(titleProp), status: statusFrom(statusProp?.name), tags: tagsProp.map((tag) => tag.name), deadline: dateProp?.start }, boardId);
    });
  }
  throw new Error(`Unsupported import provider: ${provider}`);
}
