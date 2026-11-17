const API_URL_KEY = "flowboard-api-url";
const API_TOKEN_KEY = "flowboard-api-token";
const SYNC_QUEUE_KEY = "flowboard-api-sync-queue";
const REVISION_KEY = "flowboard-api-revision";

let syncTimer = null;
let socket = null;

function storageGet(key, fallback = "") {
  if (typeof localStorage === "undefined") return fallback;
  return localStorage.getItem(key) ?? fallback;
}

function storageSet(key, value) {
  if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
}

export function getApiBaseUrl() {
  return storageGet(API_URL_KEY).trim().replace(/\/$/, "");
}

export function setApiConfiguration(url, token = "") {
  storageSet(API_URL_KEY, String(url || "").trim().replace(/\/$/, ""));
  storageSet(API_TOKEN_KEY, token);
}

export function getRemoteRevision() {
  return Number(storageGet(REVISION_KEY, "0")) || 0;
}

function headers(extra = {}) {
  const token = storageGet(API_TOKEN_KEY);
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function apiRequest(path, options = {}) {
  const base = getApiBaseUrl();
  if (!base) throw new Error("API disabled");
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: headers(options.headers),
  });
  if (!response.ok) {
    const error = new Error(`API ${response.status}`);
    error.status = response.status;
    error.payload = await response.json().catch(() => null);
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function loadRemoteWorkspace() {
  try {
    const workspace = await apiRequest("/workspace");
    storageSet(REVISION_KEY, String(workspace.revision || 0));
    return workspace;
  } catch {
    return null;
  }
}

export function mergeWorkspaceForConflict(localWorkspace, remoteWorkspace) {
  return {
    ...remoteWorkspace,
    ...localWorkspace,
    revision: remoteWorkspace.revision || 0,
    boards: localWorkspace.boards,
    tasks: localWorkspace.tasks,
  };
}

async function uploadMissingAttachments(localWorkspace, remoteWorkspace) {
  const base = getApiBaseUrl();
  const token = storageGet(API_TOKEN_KEY);
  for (const task of localWorkspace.tasks || []) {
    const remoteTask = (remoteWorkspace.tasks || []).find((item) => item.id === task.id);
    const remoteFiles = remoteTask?.attachments || [];
    for (const attachment of task.attachments || []) {
      if (!attachment.dataUrl) continue;
      if (remoteFiles.some((item) => item.name === attachment.name && item.size === attachment.size)) continue;
      const blob = await fetch(attachment.dataUrl).then((response) => response.blob());
      const form = new FormData();
      form.append("file", blob, attachment.name);
      await fetch(`${base}/tasks/${encodeURIComponent(task.id)}/attachments`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
    }
  }
}

export async function syncWorkspace(workspace) {
  const base = getApiBaseUrl();
  if (!base) return null;
  storageSet(SYNC_QUEUE_KEY, JSON.stringify(workspace));
  let revision = getRemoteRevision();
  let payload = { ...workspace, revision };
  try {
    let remote;
    try {
      remote = await apiRequest("/workspace", {
        method: "PUT",
        headers: { "If-Match": `"${revision}"` },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      if (error.status !== 409) throw error;
      const current = await apiRequest("/workspace");
      payload = mergeWorkspaceForConflict(workspace, current);
      revision = current.revision || 0;
      remote = await apiRequest("/workspace", {
        method: "PUT",
        headers: { "If-Match": `"${revision}"` },
        body: JSON.stringify(payload),
      });
    }
    await uploadMissingAttachments(workspace, remote);
    storageSet(REVISION_KEY, String(remote.revision || 0));
    if (typeof localStorage !== "undefined") localStorage.removeItem(SYNC_QUEUE_KEY);
    return remote;
  } catch {
    return null;
  }
}

export function scheduleWorkspaceSync(workspace, delay = 500) {
  if (!getApiBaseUrl()) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => { void syncWorkspace(workspace); }, delay);
}

export async function flushWorkspaceQueue() {
  const queued = storageGet(SYNC_QUEUE_KEY);
  if (!queued) return null;
  try {
    return await syncWorkspace(JSON.parse(queued));
  } catch {
    return null;
  }
}

export function getAttachmentUrl(attachment) {
  if (attachment?.dataUrl) return attachment.dataUrl;
  if (!attachment?.url) return "#";
  if (/^https?:/i.test(attachment.url)) return attachment.url;
  const base = getApiBaseUrl();
  return base ? `${base.replace(/\/api\/v1$/, "")}${attachment.url}` : attachment.url;
}

export function connectRealtime(onUpdate) {
  const base = getApiBaseUrl();
  if (!base || typeof WebSocket === "undefined") return () => {};
  const token = storageGet(API_TOKEN_KEY);
  const url = base.replace(/^http/, "ws").replace(/\/api\/v1$/, "/api/v1/realtime");
  socket?.close();
  socket = new WebSocket(`${url}${token ? `?token=${encodeURIComponent(token)}` : ""}`);
  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message.revision > getRemoteRevision()) onUpdate(message);
    } catch { /* ignore malformed realtime events */ }
  });
  return () => socket?.close();
}
