const API_URL_KEY = "flowboard-api-url";
const API_TOKEN_KEY = "flowboard-api-token";
const SYNC_QUEUE_KEY = "flowboard-api-sync-queue";
const REVISION_KEY = "flowboard-api-revision";
const CLIENT_ID_KEY = "flowboard-api-client-id";

let syncTimer = null;
let socket = null;

function storageGet(key, fallback = "") {
  if (typeof localStorage === "undefined") return fallback;
  return localStorage.getItem(key) ?? fallback;
}

function storageSet(key, value) {
  if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
}

function storageRemove(key) {
  if (typeof localStorage !== "undefined") localStorage.removeItem(key);
}

export function getApiBaseUrl() {
  return storageGet(API_URL_KEY).trim().replace(/\/$/, "");
}

export function setApiConfiguration(url, token = null) {
  storageSet(API_URL_KEY, String(url || "").trim().replace(/\/$/, ""));
  if (token !== null) storageSet(API_TOKEN_KEY, token);
}

export function getApiConfiguration() {
  return {
    url: getApiBaseUrl(),
    hasToken: Boolean(storageGet(API_TOKEN_KEY)),
  };
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

async function authenticate(path, payload) {
  const result = await apiRequest(path, { method: "POST", body: JSON.stringify(payload) });
  storageSet(API_TOKEN_KEY, result.accessToken);
  return result.user;
}

export function registerAccount(payload) {
  return authenticate("/auth/register", payload);
}

export function loginAccount(payload) {
  return authenticate("/auth/login", payload);
}

export async function getCurrentAccount() {
  if (!getApiBaseUrl() || !storageGet(API_TOKEN_KEY)) return null;
  try {
    return await apiRequest("/auth/me");
  } catch {
    return null;
  }
}

export async function getAccountMembers() {
  try {
    return await apiRequest("/members");
  } catch {
    return [];
  }
}

export function updateAccountMember(email, role) {
  return apiRequest("/members", {
    method: "PUT",
    body: JSON.stringify({ email, role }),
  });
}

export function logoutAccount() {
  storageRemove(API_TOKEN_KEY);
  storageRemove(REVISION_KEY);
  socket?.close();
  socket = null;
}

export async function createTaskComment(taskId, comment) {
  if (!getApiBaseUrl()) return null;
  try {
    return await apiRequest(`/tasks/${encodeURIComponent(taskId)}/comments`, {
      method: "POST",
      body: JSON.stringify(comment),
    });
  } catch {
    return null;
  }
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

export function connectRealtime(onUpdate, onEvent = () => {}) {
  const base = getApiBaseUrl();
  if (!base || typeof WebSocket === "undefined") return () => {};
  const token = storageGet(API_TOKEN_KEY);
  let clientId = storageGet(CLIENT_ID_KEY);
  if (!clientId) {
    clientId = globalThis.crypto?.randomUUID?.() ?? String(Date.now());
    storageSet(CLIENT_ID_KEY, clientId);
  }
  const url = base.replace(/^http/, "ws").replace(/\/api\/v1$/, "/api/v1/realtime");
  socket?.close();
  const params = new URLSearchParams({ clientId });
  if (token) params.set("token", token);
  socket = new WebSocket(`${url}?${params}`);
  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === "workspace.updated" && message.revision > getRemoteRevision()) {
        onUpdate(message);
      }
      onEvent(message);
    } catch { /* ignore malformed realtime events */ }
  });
  return () => socket?.close();
}

export function sendRealtime(message) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
    return true;
  }
  return false;
}
