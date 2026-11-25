const API_URL_KEY = "flowboard-api-url";
const API_TOKEN_KEY = "flowboard-api-token";
const SYNC_QUEUE_KEY = "flowboard-api-sync-queue";
const REVISION_KEY = "flowboard-api-revision";
const CLIENT_ID_KEY = "flowboard-api-client-id";
const ACTIVE_WORKSPACE_KEY = "flowboard-active-workspace";
const SYNC_CONFLICT_KEY = "flowboard-api-sync-conflict";

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

export function getActiveWorkspaceId() {
  return storageGet(ACTIVE_WORKSPACE_KEY);
}

export function setActiveWorkspaceId(workspaceId) {
  workspaceId ? storageSet(ACTIVE_WORKSPACE_KEY, workspaceId) : storageRemove(ACTIVE_WORKSPACE_KEY);
  storageSet(REVISION_KEY, "0");
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

function syncEvent(status, detail = {}) {
  globalThis.dispatchEvent?.(new CustomEvent("flowboard:sync", { detail: { status, ...detail } }));
}

export function completeOAuthLogin() {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  const token = params.get("oauthToken");
  if (token) {
    storageSet(API_TOKEN_KEY, token);
    history.replaceState(null, "", `${location.pathname}${location.search}`);
    return true;
  }
  return false;
}

export async function startOAuth(provider) {
  const result = await apiRequest(`/auth/oauth/${encodeURIComponent(provider)}/start`);
  location.assign(result.url);
}

export function listBackups(workspaceId) { return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/backups`); }
export function createBackup(workspaceId, name = "Manual backup") {
  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/backups`, { method: "POST", body: JSON.stringify({ name }) });
}
export function restoreBackup(workspaceId, backupId) {
  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/backups/${encodeURIComponent(backupId)}/restore`, { method: "POST" });
}
export function downloadBackup(workspaceId, backupId) {
  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/backups/${encodeURIComponent(backupId)}`);
}
export function getNotificationSchedule() { return apiRequest("/notification-schedule"); }
export function setNotificationSchedule(payload) { return apiRequest("/notification-schedule", { method: "PUT", body: JSON.stringify(payload) }); }
export function listAutomationRules(workspaceId) { return apiRequest(`/automation-rules?workspaceId=${encodeURIComponent(workspaceId)}`); }
export function createAutomationRuleRemote(payload) { return apiRequest("/automation-rules", { method: "POST", body: JSON.stringify(payload) }); }
export function deleteAutomationRuleRemote(workspaceId, ruleId) { return apiRequest(`/automation-rules/${encodeURIComponent(ruleId)}?workspaceId=${encodeURIComponent(workspaceId)}`, { method: "DELETE" }); }
export function listAttachmentVersions(attachmentId) { return apiRequest(`/attachments/${encodeURIComponent(attachmentId)}/versions`); }
export async function replaceAttachmentVersion(attachmentId, file) {
  const base = getApiBaseUrl();
  const token = storageGet(API_TOKEN_KEY);
  const form = new FormData(); form.append("file", file);
  const response = await fetch(`${base}/attachments/${encodeURIComponent(attachmentId)}/versions`, {
    method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form,
  });
  if (!response.ok) throw new Error(`API ${response.status}`);
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

export function listCloudWorkspaces() { return apiRequest("/workspaces"); }
export function createCloudWorkspace(name) {
  return apiRequest("/workspaces", { method: "POST", body: JSON.stringify({ name }) });
}
export function getMyTasks() { return apiRequest("/my/tasks"); }
export function getSecurityStatus() { return apiRequest("/security/status"); }
export function setupTotp() { return apiRequest("/security/totp/setup", { method: "POST" }); }
export function enableTotp(code) {
  return apiRequest("/security/totp/enable", { method: "POST", body: JSON.stringify({ code }) });
}
export function sendEmailVerification() {
  return apiRequest("/security/email/send-verification", { method: "POST" });
}
export function listIntegrations(workspaceId) {
  return apiRequest(`/integrations?workspaceId=${encodeURIComponent(workspaceId)}`);
}
export function createIntegration(payload) {
  return apiRequest("/integrations", { method: "POST", body: JSON.stringify(payload) });
}
export function testIntegration(integrationId, text = "Flowboard integration connected") {
  return apiRequest(`/integrations/${encodeURIComponent(integrationId)}/test`, {
    method: "POST", body: JSON.stringify({ text }),
  });
}
export function listCustomFields(workspaceId) {
  return apiRequest(`/custom-fields?workspaceId=${encodeURIComponent(workspaceId)}`);
}
export function createCustomField(payload) {
  return apiRequest("/custom-fields", { method: "POST", body: JSON.stringify(payload) });
}
export function createPublicShare(payload) {
  return apiRequest("/public-shares", { method: "POST", body: JSON.stringify(payload) });
}
export function runAssistant(payload) {
  return apiRequest("/assistant", { method: "POST", body: JSON.stringify(payload) });
}
export function getAuditLog(workspaceId) {
  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/audit`);
}

function decodeBase64Url(value) {
  const binary = atob(String(value).replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "="));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function encodeBase64Url(value) {
  const bytes = new Uint8Array(value);
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function preparePublicKey(options) {
  return {
    ...options,
    challenge: decodeBase64Url(options.challenge),
    ...(options.user ? { user: { ...options.user, id: decodeBase64Url(options.user.id) } } : {}),
    ...(options.allowCredentials ? { allowCredentials: options.allowCredentials.map((item) => ({ ...item, id: decodeBase64Url(item.id) })) } : {}),
    ...(options.excludeCredentials ? { excludeCredentials: options.excludeCredentials.map((item) => ({ ...item, id: decodeBase64Url(item.id) })) } : {}),
  };
}

function serializeCredential(credential) {
  const response = credential.response;
  return {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: encodeBase64Url(response.clientDataJSON),
      ...(response.attestationObject ? { attestationObject: encodeBase64Url(response.attestationObject) } : {}),
      ...(response.authenticatorData ? { authenticatorData: encodeBase64Url(response.authenticatorData) } : {}),
      ...(response.signature ? { signature: encodeBase64Url(response.signature) } : {}),
      ...(response.userHandle ? { userHandle: encodeBase64Url(response.userHandle) } : {}),
      ...(response.getTransports ? { transports: response.getTransports() } : {}),
    },
  };
}

export async function registerPasskey(deviceName = "Passkey") {
  if (!navigator.credentials) throw new Error("WebAuthn is not supported");
  const start = await apiRequest("/security/passkeys/registration/start", { method: "POST" });
  const credential = await navigator.credentials.create({ publicKey: preparePublicKey(start.publicKey) });
  return apiRequest("/security/passkeys/registration/complete", {
    method: "POST",
    body: JSON.stringify({ challengeId: start.challengeId, credential: serializeCredential(credential), deviceName }),
  });
}

export async function loginWithPasskey(email) {
  if (!navigator.credentials) throw new Error("WebAuthn is not supported");
  const start = await apiRequest("/auth/passkeys/start", { method: "POST", body: JSON.stringify({ email }) });
  const credential = await navigator.credentials.get({ publicKey: preparePublicKey(start.publicKey) });
  return authenticate("/auth/passkeys/complete", {
    challengeId: start.challengeId, credential: serializeCredential(credential),
  });
}

export async function enablePushNotifications(registration) {
  const { publicKey } = await apiRequest("/push/public-key");
  if (!publicKey) throw new Error("VAPID key is not configured");
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true, applicationServerKey: decodeBase64Url(publicKey),
  });
  return apiRequest("/push/subscriptions", {
    method: "POST", body: JSON.stringify(subscription.toJSON()),
  });
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

export function createInvitation(email, role = "editor") {
  return apiRequest("/invitations", { method: "POST", body: JSON.stringify({ email, role }) });
}

export function getInvitations() {
  return apiRequest("/invitations");
}

export function getSessions() {
  return apiRequest("/auth/sessions");
}

export function revokeSession(sessionId) {
  return apiRequest(`/auth/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export function requestPasswordReset(email) {
  return apiRequest("/auth/password-reset/request", {
    method: "POST", body: JSON.stringify({ email }),
  });
}

export function getNotifications() {
  return apiRequest("/notifications");
}

export function getNotificationSummary() {
  return apiRequest("/notifications/summary");
}

export function markNotificationRead(notificationId) {
  return apiRequest(`/notifications/${encodeURIComponent(notificationId)}/read`, { method: "POST" });
}

export function markAllNotificationsRead() {
  return apiRequest("/notifications/read-all", { method: "POST" });
}

export function updateComment(commentId, changes) {
  return apiRequest(`/comments/${encodeURIComponent(commentId)}`, {
    method: "PATCH", body: JSON.stringify(changes),
  });
}

export function reactToComment(commentId, emoji) {
  return apiRequest(`/comments/${encodeURIComponent(commentId)}/reactions`, {
    method: "POST", body: JSON.stringify({ emoji }),
  });
}

export function setTaskWatching(taskId, watching) {
  return apiRequest(`/tasks/${encodeURIComponent(taskId)}/watchers/me`, {
    method: "PUT", body: JSON.stringify({ watching }),
  });
}

export function getGoals() {
  return apiRequest("/goals");
}

export function createGoal(payload) {
  return apiRequest("/goals", { method: "POST", body: JSON.stringify(payload) });
}

export function getPlanningTimeline() {
  return apiRequest("/planning/timeline");
}

export function getPlanningWorkload() {
  return apiRequest("/planning/workload");
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
    const workspaceId = getActiveWorkspaceId();
    const path = workspaceId ? `/workspaces/${encodeURIComponent(workspaceId)}/snapshot` : "/workspace";
    const workspace = await apiRequest(path);
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
  syncEvent(navigator.onLine === false ? "offline" : "syncing");
  let revision = getRemoteRevision();
  let payload = { ...workspace, revision };
  const workspaceId = getActiveWorkspaceId();
  const path = workspaceId ? `/workspaces/${encodeURIComponent(workspaceId)}/snapshot` : "/workspace";
  const workspaceHeaders = workspaceId ? { "X-Workspace-ID": workspaceId } : {};
  try {
    let remote;
    try {
      remote = await apiRequest(path, {
        method: "PUT",
        headers: { "If-Match": `"${revision}"`, ...workspaceHeaders },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      if (error.status !== 409) throw error;
      const current = await apiRequest(path);
      storageSet(SYNC_CONFLICT_KEY, JSON.stringify({ local: workspace, remote: current }));
      syncEvent("conflict", { local: workspace, remote: current });
      return null;
    }
    if (!workspaceId) await uploadMissingAttachments(workspace, remote);
    storageSet(REVISION_KEY, String(remote.revision || 0));
    if (typeof localStorage !== "undefined") localStorage.removeItem(SYNC_QUEUE_KEY);
    syncEvent("synced", { revision: remote.revision || 0 });
    return remote;
  } catch {
    syncEvent(navigator.onLine === false ? "offline" : "queued");
    return null;
  }
}

export async function resolveSyncConflict(strategy = "merge") {
  const raw = storageGet(SYNC_CONFLICT_KEY);
  if (!raw) return null;
  const conflict = JSON.parse(raw);
  if (strategy === "remote") {
    storageSet(REVISION_KEY, String(conflict.remote.revision || 0));
    storageRemove(SYNC_QUEUE_KEY); storageRemove(SYNC_CONFLICT_KEY);
    syncEvent("synced", { workspace: conflict.remote });
    return conflict.remote;
  }
  const payload = strategy === "local" ? conflict.local : mergeWorkspaceForConflict(conflict.local, conflict.remote);
  storageSet(REVISION_KEY, String(conflict.remote.revision || 0));
  storageRemove(SYNC_CONFLICT_KEY);
  return syncWorkspace(payload);
}

export function scheduleWorkspaceSync(workspace, delay = 500) {
  if (!getApiBaseUrl()) return;
  clearTimeout(syncTimer);
  syncEvent(navigator.onLine === false ? "offline" : "queued");
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
  const workspaceId = getActiveWorkspaceId();
  if (workspaceId) params.set("workspaceId", workspaceId);
  let stopped = false;
  let reconnectTimer = null;
  let attempts = 0;
  const open = () => {
    if (stopped) return;
    socket = new WebSocket(`${url}?${params}`);
    socket.addEventListener("open", () => { attempts = 0; });
    socket.addEventListener("message", (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "workspace.updated" && message.revision > getRemoteRevision()) {
          onUpdate(message);
        }
        onEvent(message);
      } catch { /* ignore malformed realtime events */ }
    });
    socket.addEventListener("close", () => {
      if (stopped) return;
      attempts += 1;
      const delay = Math.min(30000, 500 * (2 ** Math.min(attempts, 6)));
      reconnectTimer = setTimeout(open, delay);
    });
  };
  open();
  return () => {
    stopped = true;
    clearTimeout(reconnectTimer);
    socket?.close();
  };
}

export function sendRealtime(message) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
    return true;
  }
  return false;
}
