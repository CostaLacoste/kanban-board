import {
  createBoard,
  deleteBoard,
  getBoardById,
  getBoards,
  renameBoard,
  setBoards,
} from "./boards.js";
import { initDragAndDrop } from "./drag-drop.js";
import { filterTasks } from "./filters.js";
import { sortTasks } from "./sorting.js";
import { getTasks, setTasks } from "./state.js";
import {
  loadBoards,
  loadSetting,
  loadTasks,
  saveBoards,
  saveSetting,
  saveTasks,
} from "./storage.js";
import {
  areDependenciesComplete,
  createTask,
  deleteTask,
  getRecurringTaskData,
  getTaskById,
  moveTask,
  updateTask,
} from "./tasks.js";
import { renderArchive, renderBoard, renderCalendar, showNotification } from "./ui.js";
import { setLanguage, t, translateDocument } from "./i18n.js";
import { applyAutomations, createAutomationRule, defaultAutomations } from "./automations.js";
import { importExternalData } from "./importers.js";
import {
  connectRealtime,
  completeOAuthLogin,
  createAutomationRuleRemote,
  deleteAutomationRuleRemote,
  createBackup,
  createCloudWorkspace,
  createCustomField,
  createGoal,
  createIntegration,
  createInvitation,
  createPublicShare,
  createTaskComment,
  enablePushNotifications,
  enableTotp,
  flushWorkspaceQueue,
  getAccountMembers,
  getActiveWorkspaceId,
  getApiConfiguration,
  getAuditLog,
  getCurrentAccount,
  getMyTasks,
  getGoals,
  getInvitations,
  getSecurityStatus,
  getNotifications,
  getNotificationSchedule,
  getSessions,
  listCloudWorkspaces,
  listBackups,
  listCustomFields,
  listIntegrations,
  listAttachmentVersions,
  loginAccount,
  loginWithPasskey,
  loadRemoteWorkspace,
  logoutAccount,
  markAllNotificationsRead,
  markNotificationRead,
  resolveSyncConflict,
  reactToComment,
  registerPasskey,
  registerAccount,
  requestPasswordReset,
  revokeSession,
  scheduleWorkspaceSync,
  sendEmailVerification,
  sendRealtime,
  setActiveWorkspaceId,
  setApiConfiguration,
  setTaskWatching,
  setupTotp,
  testIntegration,
  runAssistant,
  setNotificationSchedule,
  startOAuth,
  restoreBackup,
  replaceAttachmentVersion,
  downloadBackup,
  updateComment,
  updateAccountMember,
} from "./api.js";
import {
  addColumn,
  getDefaultColumns,
  normalizeColumns,
  removeColumn,
  renameColumn,
} from "./workflow.js";

const board = document.querySelector(".kanban-board");
const form = document.querySelector("#task-form");
const taskDialog = document.querySelector("#task-dialog");
const deleteDialog = document.querySelector("#delete-dialog");
const archiveDialog = document.querySelector("#archive-dialog");
const taskDialogTitle = document.querySelector("#task-dialog-title");
const searchInput = document.querySelector("#task-search");
const prioritySelect = document.querySelector("#priority-filter");
const tagSelect = document.querySelector("#tag-filter");
const assigneeFilter = document.querySelector("#assignee-filter");
const deadlineFromFilter = document.querySelector("#deadline-from-filter");
const deadlineToFilter = document.querySelector("#deadline-to-filter");
const sortSelect = document.querySelector("#sort-select");
const themeSelect = document.querySelector("#theme-select");
const languageSelect = document.querySelector("#language-select");
const boardSelect = document.querySelector("#board-select");
const boardTitle = document.querySelector("#active-board-name");
const importInput = document.querySelector("#workspace-import");
const undoButton = document.querySelector('[data-action="undo"]');
const checklistEditor = document.querySelector("#checklist-editor-items");
const checklistEditorTemplate = document.querySelector(
  "#checklist-editor-item-template",
);
const productivityDialog = document.querySelector("#productivity-dialog");
const calendarView = document.querySelector("[data-calendar-view]");
const calendarMonth = document.querySelector("#calendar-month");
const workflowEditor = document.querySelector("[data-workflow-editor]");
const memberList = document.querySelector("[data-member-list]");
const activityList = document.querySelector("[data-activity-list]");
const focusClock = document.querySelector("[data-focus-clock]");
const focusTaskSelect = document.querySelector("#focus-task");
const templateSelect = document.querySelector("#task-template");
const assigneeSelect = document.querySelector("#task-assignee");
const dependencySelect = document.querySelector("#task-dependencies");
const syncPackage = document.querySelector("#sync-package");
const installButton = document.querySelector('[data-action="install-app"]');
const commandDialog = document.querySelector("#command-dialog");
const commandSearch = document.querySelector("#command-search");
const commandList = document.querySelector("[data-command-list]");
const batchBar = document.querySelector("[data-batch-bar]");
const batchStatus = document.querySelector("#batch-status");
const batchPriority = document.querySelector("#batch-priority");
const attachmentInput = document.querySelector("#task-attachments");
const attachmentEditor = document.querySelector("[data-attachment-editor]");
const accountDialog = document.querySelector("#account-dialog");
const accountApiUrl = document.querySelector("#account-api-url");
const accountStatus = document.querySelector("[data-account-status]");
const accountAuth = document.querySelector("[data-account-auth]");
const accountProfile = document.querySelector("[data-account-profile]");
const accountMembers = document.querySelector("[data-account-members]");
const accountButton = document.querySelector("[data-account-button]");
const commentList = document.querySelector("[data-comment-list]");
const collaborationStatus = document.querySelector("[data-collaboration-status]");
const notificationsDialog = document.querySelector("#notifications-dialog");
const notificationList = document.querySelector("[data-notification-list]");
const notificationCount = document.querySelector("[data-notification-count]");
const notificationFilter = document.querySelector("#notification-filter");
const invitationsList = document.querySelector("[data-invitations]");
const sessionsList = document.querySelector("[data-sessions]");
const ownerTools = document.querySelector("[data-owner-tools]");
const goalList = document.querySelector("[data-goal-list]");
const roadmap = document.querySelector("[data-roadmap]");
const goalSelect = document.querySelector("#task-goal");
const platformDialog = document.querySelector("#platform-dialog");
const platformStatus = document.querySelector("[data-platform-status]");
const cloudWorkspaceControl = document.querySelector("[data-cloud-workspace-control]");
const cloudWorkspaceSelect = document.querySelector("#cloud-workspace-select");
const workspaceList = document.querySelector("[data-workspace-list]");
const myTaskList = document.querySelector("[data-my-tasks]");
const securityStatus = document.querySelector("[data-security-status]");
const integrationList = document.querySelector("[data-integration-list]");
const customFieldList = document.querySelector("[data-custom-field-list]");
const auditList = document.querySelector("[data-audit-list]");
const customFieldsEditor = document.querySelector("[data-custom-fields-editor]");
const customFieldsInputs = document.querySelector("[data-custom-fields-inputs]");
const backupList = document.querySelector("[data-backup-list]");
const syncStatus = document.querySelector("[data-sync-status]");
const syncConflictDialog = document.querySelector("#sync-conflict-dialog");
const automationRuleList = document.querySelector("[data-automation-rules]");
const dashboardWidgets = document.querySelector("[data-dashboard-widgets]");

let activeBoardId = "default";
let sortMode = "manual";
let history = [];
let columns = getDefaultColumns();
let templates = [];
let members = [];
let activity = [];
let accessibility = { highContrast: false, reduceMotion: false, fontScale: 100 };
let currentView = "board";
let focusSeconds = 25 * 60;
let focusTimer = null;
let deferredInstallPrompt = null;
let selectedTaskIds = new Set();
let pendingAttachments = [];
let automations = { ...defaultAutomations };
let applyingRemoteWorkspace = false;
let localWorkspaceGeneration = 0;
let currentAccount = null;
let remoteMembers = [];
let draftTimer = null;
let goals = [];
let remoteNotifications = [];
let invitations = [];
let sessions = [];
let cloudWorkspaces = [];
let cloudMyTasks = [];
let cloudIntegrations = [];
let cloudCustomFields = [];
let security = null;
let auditEntries = [];
let collaborationLamport = 0;
let cloudBackups = [];
let notificationSchedule = { leadMinutes: 60, digestFrequency: "daily", digestHour: 9, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone };
let dashboardPreferences = { overview: true, deadlines: true, workload: true, goals: true };

function getBoardTasks({ archived = false } = {}) {
  return getTasks().filter(
    (task) => task.boardId === activeBoardId && task.archived === archived,
  );
}

function syncBoardSelect() {
  const boards = getBoards();
  boardSelect.replaceChildren();
  boards.forEach((item) => {
    const name = item.id === "default" && item.name === "Основная доска"
      ? t("board.default")
      : item.name;
    boardSelect.add(new Option(name, item.id));
  });

  if (!getBoardById(activeBoardId)) {
    activeBoardId = boards[0].id;
  }

  boardSelect.value = activeBoardId;
  const activeBoard = getBoardById(activeBoardId);
  boardTitle.textContent = activeBoard?.id === "default" && activeBoard.name === "Основная доска"
    ? t("board.default")
    : activeBoard?.name ?? t("workspace.board");
}

function syncTagFilter(tasks) {
  const selectedTag = tagSelect.value;
  const tags = [...new Set(tasks.flatMap((task) => task.tags ?? []))].sort(
    (first, second) => first.localeCompare(second),
  );

  tagSelect.replaceChildren(new Option(t("filter.allTags"), "all"));
  tags.forEach((tag) => tagSelect.add(new Option(`#${tag}`, tag)));
  tagSelect.value = tags.includes(selectedTag) ? selectedTag : "all";
  const selectedAssignee = assigneeFilter.value;
  const assignees = [...new Set(tasks.map((task) => task.assignee).filter(Boolean))].sort();
  assigneeFilter.replaceChildren(new Option(t("filter.allAssignees"), "all"));
  assignees.forEach((assignee) => assigneeFilter.add(new Option(assignee, assignee)));
  assigneeFilter.value = assignees.includes(selectedAssignee) ? selectedAssignee : "all";
}

function getVisibleTasks(tasks) {
  return sortTasks(
    filterTasks(
      tasks,
      searchInput.value,
      prioritySelect.value,
      tagSelect.value,
      {
        assignee: assigneeFilter.value,
        currentUser: currentAccount?.name || currentAccount?.email || "",
        deadlineFrom: deadlineFromFilter.value,
        deadlineTo: deadlineToFilter.value,
      },
    ),
    sortMode,
  );
}

function refreshBoard() {
  syncBoardSelect();
  const tasks = getBoardTasks();
  syncTagFilter(tasks);
  renderBoard(getVisibleTasks(tasks), tasks, columns);
  renderArchive(getBoardTasks({ archived: true }));
  renderCalendar(tasks, calendarMonth.value, openEditDialog);
  renderProductivityHub();
  syncBatchBar();
}

function persistWorkspace() {
  const saved = [
    saveTasks(getTasks()),
    saveBoards(getBoards()),
    saveSetting("activeBoard", activeBoardId),
    saveSetting("sort", sortMode),
    saveSetting("columns", columns),
    saveSetting("templates", templates),
    saveSetting("members", members),
    saveSetting("activity", activity),
    saveSetting("accessibility", accessibility),
    saveSetting("automations", automations),
    saveSetting("dashboard", dashboardPreferences),
    saveSetting("goals", goals),
  ].every(Boolean);
  if (saved && !applyingRemoteWorkspace) {
    localWorkspaceGeneration += 1;
    scheduleWorkspaceSync(createSyncPayload());
  }
  return saved;
}

function updateUndoButton() {
  undoButton.disabled = history.length === 0;
  undoButton.title = history.length > 0
    ? `${t("app.undo")}: ${t(history.at(-1).label)}`
    : t("app.undo");
}

function rememberState(label) {
  history.push({
    label,
    tasks: getTasks(),
    boards: getBoards(),
    activeBoardId,
  });
  history = history.slice(-20);
  updateUndoButton();
}

function discardLastSnapshot() {
  history.pop();
  updateUndoButton();
}

function commitChanges(message) {
  const actionKey = history.at(-1)?.label;
  if (actionKey) {
    activity = [{
      id: globalThis.crypto?.randomUUID?.() ?? String(Date.now()),
      action: actionKey,
      createdAt: new Date().toISOString(),
    }, ...activity].slice(0, 50);
  }
  const automated = applyAutomations(getTasks(), automations);
  if (automated.changed) setTasks(automated.tasks);
  const saved = persistWorkspace();
  refreshBoard();
  showNotification(
    saved ? message : t("notice.saveError"),
    saved ? "success" : "error",
  );
}

function getColumnName(column) {
  const defaultColumnNames = { todo: "Нужно сделать", progress: "В работе", done: "Готово" };
  return defaultColumnNames[column.id] === column.name
    ? t(`column.${column.id}`)
    : column.name;
}

function syncBatchBar() {
  selectedTaskIds = new Set([...selectedTaskIds].filter((id) => getTaskById(id) && !getTaskById(id).archived));
  batchBar.hidden = selectedTaskIds.size === 0;
  batchBar.querySelector("[data-batch-count]").textContent = String(selectedTaskIds.size);
  batchStatus.replaceChildren(new Option(t("batch.status"), ""));
  columns.forEach((column) => batchStatus.add(new Option(getColumnName(column), column.id)));
  document.querySelectorAll(".task-card").forEach((card) => {
    const selected = selectedTaskIds.has(card.dataset.taskId);
    card.classList.toggle("is-selected", selected);
    const checkbox = card.querySelector('[data-action="select-task"]');
    if (checkbox) checkbox.checked = selected;
  });
}

function renderAttachmentEditor() {
  attachmentEditor.replaceChildren();
  pendingAttachments.forEach((attachment) => {
    const row = document.createElement("div");
    row.className = "attachment-editor__item";
    const name = document.createElement("span");
    name.textContent = `📎 ${attachment.name} · ${Math.ceil(attachment.size / 1024)} KB`;
    const remove = document.createElement("button");
    remove.className = "mini-button";
    remove.type = "button";
    remove.dataset.action = "remove-attachment";
    remove.dataset.attachmentId = attachment.id;
    remove.textContent = "×";
    row.append(name);
    if (attachment.url) {
      const historyButton = document.createElement("button"); historyButton.className = "mini-button"; historyButton.type = "button";
      historyButton.dataset.action = "attachment-history"; historyButton.dataset.attachmentId = attachment.id; historyButton.textContent = "v";
      const replace = document.createElement("button"); replace.className = "mini-button"; replace.type = "button";
      replace.dataset.action = "replace-attachment"; replace.dataset.attachmentId = attachment.id; replace.textContent = "↻";
      row.append(historyButton, replace);
    }
    row.append(remove);
    attachmentEditor.append(row);
  });
}

function roleLabel(role) {
  return t(`account.role.${role}`);
}

function renderAccountPanel() {
  const configuration = getApiConfiguration();
  accountApiUrl.value = configuration.url;
  accountAuth.hidden = Boolean(currentAccount);
  accountProfile.hidden = !currentAccount;
  accountStatus.textContent = currentAccount
    ? t("account.connected", { name: currentAccount.name })
    : t("account.offline");
  accountButton.textContent = currentAccount ? `◎ ${currentAccount.name}` : t("account.open");
  accountMembers.replaceChildren();
  invitationsList.replaceChildren();
  sessionsList.replaceChildren();
  ownerTools.hidden = currentAccount?.role !== "owner";
  if (!currentAccount) return;
  accountProfile.querySelector("[data-account-name]").textContent = currentAccount.name;
  accountProfile.querySelector("[data-account-email]").textContent = currentAccount.email;
  accountProfile.querySelector("[data-account-role]").textContent = roleLabel(currentAccount.role);
  remoteMembers.forEach((member) => {
    const row = document.createElement("div");
    row.className = "account-member";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = member.name;
    const email = document.createElement("span");
    email.textContent = member.email;
    identity.append(name, email);
    if (currentAccount.role === "owner") {
      const select = document.createElement("select");
      ["owner", "editor", "viewer"].forEach((role) => {
        select.add(new Option(roleLabel(role), role));
      });
      select.value = member.role;
      select.setAttribute("aria-label", `${member.name}: ${roleLabel(member.role)}`);
      select.addEventListener("change", async () => {
        try {
          await updateAccountMember(member.email, select.value);
          await refreshAccount();
        } catch {
          select.value = member.role;
          showNotification(t("account.error"), "error");
        }
      });
      row.append(identity, select);
    } else {
      const role = document.createElement("span");
      role.textContent = roleLabel(member.role);
      row.append(identity, role);
    }
    accountMembers.append(row);
  });
  invitations.forEach((invitation) => {
    const row = document.createElement("div");
    row.className = "account-member";
    const status = invitation.acceptedAt ? t("account.inviteAccepted") : t("account.invitePending");
    row.innerHTML = `<div><strong></strong><span></span></div><span></span>`;
    row.querySelector("strong").textContent = invitation.email;
    row.querySelector("div span").textContent = roleLabel(invitation.role);
    row.lastElementChild.textContent = status;
    invitationsList.append(row);
  });
  sessions.forEach((session) => {
    const row = document.createElement("div");
    row.className = "account-member";
    const identity = document.createElement("div");
    const agent = document.createElement("strong");
    agent.textContent = session.current ? `${t("account.currentSession")} · ${session.userAgent}` : session.userAgent;
    const address = document.createElement("span");
    address.textContent = `${session.ipAddress} · ${new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(session.lastSeenAt))}`;
    identity.append(agent, address);
    const revoke = document.createElement("button");
    revoke.className = "mini-button";
    revoke.type = "button";
    revoke.dataset.action = "revoke-session";
    revoke.dataset.sessionId = session.id;
    revoke.textContent = t("account.revokeSession");
    row.append(identity, revoke);
    sessionsList.append(row);
  });
}

async function refreshAccount() {
  currentAccount = await getCurrentAccount();
  cloudWorkspaces = currentAccount ? await listCloudWorkspaces().catch(() => []) : [];
  if (cloudWorkspaces.length > 0 && !cloudWorkspaces.some((item) => item.id === getActiveWorkspaceId())) {
    setActiveWorkspaceId(cloudWorkspaces[0].id);
  }
  cloudWorkspaceControl.hidden = cloudWorkspaces.length === 0;
  cloudWorkspaceSelect.replaceChildren();
  cloudWorkspaces.forEach((workspace) => cloudWorkspaceSelect.add(new Option(workspace.name, workspace.id)));
  cloudWorkspaceSelect.value = getActiveWorkspaceId();
  cloudCustomFields = currentAccount && getActiveWorkspaceId()
    ? await listCustomFields(getActiveWorkspaceId()).catch(() => [])
    : [];
  remoteMembers = currentAccount ? await getAccountMembers() : [];
  [invitations, sessions, remoteNotifications, goals] = currentAccount
    ? await Promise.all([
      currentAccount.role === "owner" ? getInvitations().catch(() => []) : [],
      getSessions().catch(() => []),
      getNotifications().catch(() => []),
      getGoals().catch(() => goals),
    ])
    : [[], [], [], goals];
  if (remoteMembers.length > 0) {
    members = remoteMembers.map((member) => member.name);
    saveSetting("members", members);
    syncTaskFormOptions(form.elements.taskId.value);
  }
  renderAccountPanel();
  renderNotificationCenter();
  renderPlanning();
  syncTaskFormOptions(form.elements.taskId.value);
}

function platformRow(title, detail = "") {
  const row = document.createElement("div");
  row.className = "account-member";
  const identity = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = title;
  const span = document.createElement("span");
  span.textContent = detail;
  identity.append(strong, span);
  row.append(identity);
  return row;
}

function renderPlatformConsole() {
  const workspaceId = getActiveWorkspaceId();
  workspaceList.replaceChildren(...cloudWorkspaces.map((workspace) => {
    const row = platformRow(workspace.name, workspace.role);
    const open = document.createElement("button");
    open.type = "button";
    open.className = "mini-button";
    open.dataset.action = "select-workspace";
    open.dataset.workspaceId = workspace.id;
    open.textContent = workspace.id === workspaceId ? "✓" : "→";
    row.append(open);
    return row;
  }));
  myTaskList.replaceChildren(...cloudMyTasks.map((task) => platformRow(task.title, task.workspaceName)));
  if (cloudMyTasks.length === 0) myTaskList.append(platformRow(t("platform.empty")));
  securityStatus.textContent = security
    ? `${t("security.email")}: ${security.emailVerified ? "✓" : "—"} · 2FA: ${security.totpEnabled ? "✓" : "—"} · Passkeys: ${security.passkeys}`
    : t("platform.empty");
  integrationList.replaceChildren(...cloudIntegrations.map((item) => {
    const row = platformRow(item.name, item.kind);
    if (["slack", "telegram"].includes(item.kind)) {
      const testButton = document.createElement("button");
      testButton.type = "button";
      testButton.className = "mini-button";
      testButton.dataset.action = "test-integration";
      testButton.dataset.integrationId = item.id;
      testButton.textContent = "TEST";
      row.append(testButton);
    }
    return row;
  }));
  customFieldList.replaceChildren(...cloudCustomFields.map((item) => platformRow(item.name, item.fieldType)));
  auditList.replaceChildren(...auditEntries.slice(0, 50).map((item) => platformRow(
    `${item.action.toUpperCase()} ${item.resource}`,
    `${item.user} · ${new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(item.createdAt))}`,
  )));
  backupList.replaceChildren(...cloudBackups.map((backup) => {
    const row = platformRow(backup.name, new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(backup.createdAt)));
    for (const [action, label] of [["download-cloud-backup", "↓"], ["restore-cloud-backup", "↺"]]) {
      const control = document.createElement("button"); control.type = "button"; control.className = "mini-button";
      control.dataset.action = action; control.dataset.backupId = backup.id; control.textContent = label; row.append(control);
    }
    return row;
  }));
}

function renderCustomFieldsEditor(task = null) {
  customFieldsInputs.replaceChildren();
  customFieldsEditor.hidden = cloudCustomFields.length === 0;
  cloudCustomFields.forEach((field) => {
    const label = document.createElement("label");
    label.className = "form-field";
    const title = document.createElement("span");
    title.textContent = field.name;
    let input;
    if (field.fieldType === "select") {
      input = document.createElement("select");
      input.add(new Option("—", ""));
      (field.options || []).forEach((option) => input.add(new Option(option, option)));
    } else {
      input = document.createElement("input");
      input.type = { number: "number", date: "date" }[field.fieldType] || "text";
    }
    input.dataset.customFieldId = field.id;
    input.required = Boolean(field.required);
    input.value = task?.customValues?.[field.id] ?? "";
    label.append(title, input);
    customFieldsInputs.append(label);
  });
}

async function refreshPlatformData() {
  if (!currentAccount) {
    platformStatus.textContent = t("platform.signIn");
    renderPlatformConsole();
    return;
  }
  const workspaceId = getActiveWorkspaceId();
  [cloudMyTasks, security, cloudIntegrations, cloudCustomFields, auditEntries, cloudBackups] = await Promise.all([
    getMyTasks().catch(() => []),
    getSecurityStatus().catch(() => null),
    workspaceId ? listIntegrations(workspaceId).catch(() => []) : [],
    workspaceId ? listCustomFields(workspaceId).catch(() => []) : [],
    workspaceId && currentAccount.role === "owner" ? getAuditLog(workspaceId).catch(() => []) : [],
    workspaceId ? listBackups(workspaceId).catch(() => []) : [],
  ]);
  platformStatus.textContent = cloudWorkspaces.find((item) => item.id === workspaceId)?.name || t("platform.empty");
  renderPlatformConsole();
}

async function authenticateAccount(mode) {
  const email = document.querySelector("#account-email").value.trim();
  const password = document.querySelector("#account-password").value;
  const name = document.querySelector("#account-name").value.trim();
  const otp = document.querySelector("#account-otp").value.trim();
  try {
    currentAccount = mode === "register"
      ? await registerAccount({ email, password, name })
      : await loginAccount({ email, password, otp: otp || null });
    document.querySelector("#account-password").value = "";
    document.querySelector("#account-otp").value = "";
    await refreshAccount();
    void initializeRemoteWorkspace();
  } catch (error) {
    accountStatus.textContent = `${t("account.error")}: ${error.message}`;
    showNotification(t("account.error"), "error");
  }
}

function renderNotificationCenter() {
  const unread = remoteNotifications.filter((item) => !item.readAt).length;
  notificationCount.textContent = String(unread);
  notificationCount.hidden = unread === 0;
  notificationList.replaceChildren();
  const selectedKind = notificationFilter.value;
  const visible = remoteNotifications.filter((item) => !selectedKind || item.kind === selectedKind);
  if (visible.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = t("notifications.empty");
    notificationList.append(empty);
    return;
  }
  visible.forEach((notification) => {
    const item = document.createElement("article");
    item.className = `notification-center__item${notification.readAt ? "" : " is-unread"}`;
    const title = document.createElement("strong");
    title.textContent = notification.title;
    const body = document.createElement("p");
    body.textContent = notification.body;
    const footer = document.createElement("div");
    footer.className = "comment-item__meta";
    const date = document.createElement("time");
    date.textContent = new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(notification.createdAt));
    footer.append(date);
    if (!notification.readAt) {
      const read = document.createElement("button");
      read.className = "mini-button";
      read.type = "button";
      read.dataset.action = "read-notification";
      read.dataset.notificationId = notification.id;
      read.textContent = t("notifications.read");
      footer.append(read);
    }
    item.append(title, body, footer);
    notificationList.append(item);
  });
}

function renderAutomationRules() {
  automationRuleList.replaceChildren(...(automations.rules || []).map((rule) => {
    const row = platformRow(rule.name, `${rule.trigger}${rule.triggerValue ? `:${rule.triggerValue}` : ""} → ${rule.action}:${rule.actionValue}`);
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "mini-button";
    remove.dataset.action = "delete-automation-rule"; remove.dataset.ruleId = rule.id; remove.textContent = "×"; row.append(remove);
    return row;
  }));
}

function renderDashboard() {
  dashboardWidgets.replaceChildren();
  const tasks = getBoardTasks();
  const today = new Date().toISOString().slice(0, 10);
  const values = {
    overview: [t("feature.overview"), `${tasks.filter((item) => item.status === "done").length}/${tasks.length}`],
    deadlines: [t("feature.deadlines"), tasks.filter((item) => item.deadline && item.deadline <= today && item.status !== "done").length],
    workload: [t("feature.workload"), `${tasks.filter((item) => item.status !== "done").reduce((sum, item) => sum + Number(item.estimatedMinutes || 0), 0)}m`],
    goals: [t("feature.goals"), goals.length],
  };
  Object.entries(values).forEach(([key, [label, value]]) => {
    if (!dashboardPreferences[key]) return;
    const card = document.createElement("div"); card.className = "dashboard-widget";
    const span = document.createElement("span"); span.textContent = label;
    const strong = document.createElement("strong"); strong.textContent = String(value); card.append(span, strong); dashboardWidgets.append(card);
  });
  document.querySelectorAll("[data-dashboard-widget]").forEach((input) => { input.checked = dashboardPreferences[input.dataset.dashboardWidget] !== false; });
}

function renderPlanning() {
  if (!goalList || !roadmap) return;
  goalList.replaceChildren();
  goals.forEach((goal) => {
    const item = document.createElement("article");
    item.className = "goal-item";
    const header = document.createElement("div");
    header.className = "comment-item__meta";
    const title = document.createElement("strong");
    title.textContent = goal.title;
    const target = document.createElement("span");
    target.textContent = goal.targetDate || t("planning.noDate");
    header.append(title, target);
    const bar = document.createElement("div");
    bar.className = "goal-progress";
    const completed = getTasks().filter((task) => task.goalId === goal.id && task.status === "done").length;
    const linked = getTasks().filter((task) => task.goalId === goal.id).length;
    const progress = linked ? Math.round(completed / linked * 100) : (goal.progress ?? 0);
    bar.innerHTML = `<span style="--goal-progress:${progress}%"></span><strong>${progress}%</strong>`;
    item.append(header, bar);
    goalList.append(item);
  });
  roadmap.replaceChildren();
  getTasks()
    .filter((task) => !task.archived && (task.startDate || task.deadline || task.milestone))
    .sort((a, b) => String(a.startDate || a.deadline).localeCompare(String(b.startDate || b.deadline)))
    .forEach((task) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "roadmap-item";
      row.dataset.action = "edit-task";
      row.dataset.taskId = task.id;
      const marker = task.milestone ? "◆" : "━";
      row.textContent = `${marker} ${task.startDate || "…"} → ${task.deadline || "…"} · ${task.title}`;
      roadmap.append(row);
    });
}

function appendCommentText(container, text) {
  const parts = String(text).split(/(@[^\s]+)/g);
  parts.forEach((part) => {
    if (part.startsWith("@")) {
      const mention = document.createElement("mark");
      mention.className = "comment-mention";
      mention.textContent = part;
      container.append(mention);
    } else {
      container.append(document.createTextNode(part));
    }
  });
}

function renderTaskComments(task) {
  commentList.replaceChildren();
  const comments = task?.comments ?? [];
  commentList.hidden = !task;
  if (!task) return;
  if (comments.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = t("comment.empty");
    commentList.append(empty);
    return;
  }
  comments.forEach((comment) => {
    const item = document.createElement("article");
    item.className = "comment-item";
    item.dataset.commentId = comment.id;
    if (comment.parentId) item.classList.add("comment-item--reply");
    if (comment.resolvedAt) item.classList.add("is-resolved");
    const meta = document.createElement("div");
    meta.className = "comment-item__meta";
    const author = document.createElement("strong");
    author.textContent = comment.author;
    const date = document.createElement("time");
    date.dateTime = comment.createdAt;
    date.textContent = new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" })
      .format(new Date(comment.createdAt));
    const body = document.createElement("p");
    appendCommentText(body, comment.text);
    meta.append(author, date);
    const actions = document.createElement("div");
    actions.className = "comment-actions";
    if (currentAccount) {
      const reply = document.createElement("button");
      reply.className = "mini-button";
      reply.type = "button";
      reply.dataset.action = "reply-comment";
      reply.dataset.commentId = comment.id;
      reply.textContent = t("comment.reply");
      const react = document.createElement("button");
      react.className = "mini-button";
      react.type = "button";
      react.dataset.action = "react-comment";
      react.dataset.commentId = comment.id;
      react.textContent = `👍 ${comment.reactions?.["👍"]?.length || ""}`;
      actions.append(reply, react);
      if (currentAccount.role === "owner" || comment.authorId === currentAccount.id) {
        const resolve = document.createElement("button");
        resolve.className = "mini-button";
        resolve.type = "button";
        resolve.dataset.action = "resolve-comment";
        resolve.dataset.commentId = comment.id;
        resolve.dataset.resolved = String(Boolean(comment.resolvedAt));
        resolve.textContent = t(comment.resolvedAt ? "comment.reopen" : "comment.resolve");
        actions.append(resolve);
      }
    }
    item.append(meta, body, actions);
    commentList.append(item);
  });
}

function handleRealtimeEvent(message) {
  const activeTaskId = form.elements.taskId.value;
  if (message.type === "presence.updated" && message.taskId === activeTaskId) {
    const names = [...new Set((message.users || []).map((user) => user.name))];
    collaborationStatus.hidden = names.length < 2;
    collaborationStatus.textContent = names.length >= 2
      ? t("collaboration.editing", { names: names.join(", ") })
      : "";
  }
  if (message.type === "task.draft" && message.taskId === activeTaskId) {
    const input = form.elements[message.field];
    if (input && document.activeElement !== input) {
      const value = Array.isArray(message.value) ? message.value.join(", ") : message.value;
      if (input instanceof HTMLSelectElement && ![...input.options].some((option) => option.value === value)) {
        input.add(new Option(value, value));
      }
      input.value = value;
    }
    collaborationStatus.hidden = false;
    collaborationStatus.textContent = t("collaboration.remoteDraft", { name: message.actor.name });
  }
  if (message.type === "task.operation" && message.taskId === activeTaskId) {
    collaborationLamport = Math.max(collaborationLamport, Number(message.lamport) || 0) + 1;
    const input = form.elements[message.field];
    const value = message.operation?.value;
    if (input && value !== undefined && document.activeElement !== input) input.value = value;
  }
  if (message.type === "comment.created") {
    const task = getTaskById(message.taskId);
    if (!task || task.comments?.some((comment) => comment.id === message.comment.id)) return;
    setTasks(getTasks().map((item) => item.id === task.id
      ? { ...item, comments: [...(item.comments || []), message.comment].slice(-30) }
      : item));
    saveTasks(getTasks());
    if (activeTaskId === task.id) renderTaskComments(getTaskById(task.id));
    refreshBoard();
  }
  if (message.type === "comment.updated") {
    setTasks(getTasks().map((task) => ({
      ...task,
      comments: (task.comments || []).map((comment) => comment.id === message.comment.id ? message.comment : comment),
    })));
    saveTasks(getTasks());
    if (activeTaskId) renderTaskComments(getTaskById(activeTaskId));
  }
  if (message.type === "comment.deleted") {
    setTasks(getTasks().map((task) => ({
      ...task, comments: (task.comments || []).filter((comment) => comment.id !== message.commentId),
    })));
    saveTasks(getTasks());
    if (activeTaskId) renderTaskComments(getTaskById(activeTaskId));
  }
}

function readAttachment(file) {
  return new Promise((resolve, reject) => {
    if (file.size > 750 * 1024) {
      reject(new Error(t("attachment.tooLarge", { name: file.name })));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve({
      id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${file.name}`,
      name: file.name,
      type: file.type,
      size: file.size,
      dataUrl: reader.result,
    });
    reader.onerror = () => reject(new Error(t("attachment.readError")));
    reader.readAsDataURL(file);
  });
}

function commandDefinitions() {
  return [
    ["new-task", "command.newTask", "N"],
    ["show-board", "command.board", "B"],
    ["show-calendar", "command.calendar", "C"],
    ["open-hub", "command.hub", "H"],
    ["export", "command.export", "E"],
    ["clear-filters", "command.clearFilters", "R"],
  ];
}

function renderCommandPalette() {
  const query = commandSearch.value.trim().toLowerCase();
  commandList.replaceChildren();
  commandDefinitions()
    .filter(([, key]) => t(key).toLowerCase().includes(query))
    .forEach(([id, key, shortcut]) => {
      const button = document.createElement("button");
      button.className = "command-item";
      button.type = "button";
      button.dataset.command = id;
      button.innerHTML = `<span></span><kbd>${shortcut}</kbd>`;
      button.querySelector("span").textContent = t(key);
      commandList.append(button);
    });
}

function runCommand(command) {
  commandDialog.close();
  if (command === "new-task") openCreateDialog();
  else if (command === "show-board") setView("board");
  else if (command === "show-calendar") setView("calendar");
  else if (command === "open-hub") { renderProductivityHub(); productivityDialog.showModal(); }
  else if (command === "export") exportWorkspace();
  else if (command === "clear-filters") {
    searchInput.value = ""; prioritySelect.value = "all"; tagSelect.value = "all"; refreshBoard();
  }
}

function todayMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function syncTaskFormOptions(taskId = "") {
  const selectedStatus = form.elements.status.value;
  form.elements.status.replaceChildren(...columns.map((column) => new Option(column.name, column.id)));
  form.elements.status.value = columns.some((column) => column.id === selectedStatus)
    ? selectedStatus
    : columns[0].id;

  assigneeSelect.replaceChildren(new Option(t("extra.unassigned"), ""));
  members.forEach((member) => assigneeSelect.add(new Option(member, member)));

  dependencySelect.replaceChildren();
  getBoardTasks()
    .filter((task) => task.id !== taskId && !task.archived)
    .forEach((task) => dependencySelect.add(new Option(task.title, task.id)));

  templateSelect.replaceChildren(new Option(t("extra.noTemplate"), ""));
  templates.forEach((template) => templateSelect.add(new Option(template.name, template.id)));

  const selectedGoal = goalSelect.value;
  goalSelect.replaceChildren(new Option(t("planning.noGoal"), ""));
  goals.forEach((goal) => goalSelect.add(new Option(goal.title, goal.id)));
  goalSelect.value = goals.some((goal) => goal.id === selectedGoal) ? selectedGoal : "";
}

function applyAccessibility() {
  document.documentElement.dataset.highContrast = String(Boolean(accessibility.highContrast));
  document.documentElement.dataset.reduceMotion = String(Boolean(accessibility.reduceMotion));
  document.documentElement.style.fontSize = `${Number(accessibility.fontScale) || 100}%`;
  document.querySelectorAll("[data-setting]").forEach((input) => {
    const key = input.dataset.setting;
    if (input.type === "checkbox") input.checked = Boolean(accessibility[key]);
    else input.value = accessibility[key] ?? 100;
  });
}

function formatFocusTime() {
  const minutes = Math.floor(focusSeconds / 60);
  const seconds = focusSeconds % 60;
  focusClock.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function renderProductivityHub() {
  if (!workflowEditor) return;
  workflowEditor.replaceChildren();
  columns.forEach((column) => {
    const row = document.createElement("div");
    row.className = "workflow-row";
    const marker = document.createElement("span");
    marker.className = "workflow-row__color";
    marker.style.setProperty("--column-color", `var(--color-${column.color})`);
    const name = document.createElement("span");
    name.textContent = getColumnName(column);
    const actions = document.createElement("div");
    const rename = document.createElement("button");
    rename.className = "mini-button";
    rename.type = "button";
    rename.dataset.action = "rename-column";
    rename.dataset.columnId = column.id;
    rename.textContent = "✎";
    actions.append(rename);
    if (!["todo", "done"].includes(column.id)) {
      const remove = document.createElement("button");
      remove.className = "mini-button";
      remove.type = "button";
      remove.dataset.action = "remove-column";
      remove.dataset.columnId = column.id;
      remove.textContent = "×";
      actions.append(remove);
    }
    row.append(marker, name, actions);
    workflowEditor.append(row);
  });

  memberList.replaceChildren();
  if (members.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = t("hub.emptyMembers");
    memberList.append(empty);
  }
  members.forEach((member) => {
    const row = document.createElement("div");
    row.className = "member-row";
    row.textContent = member;
    const remove = document.createElement("button");
    remove.className = "mini-button";
    remove.type = "button";
    remove.dataset.action = "remove-member";
    remove.dataset.member = member;
    remove.textContent = "×";
    row.append(remove);
    memberList.append(row);
  });

  focusTaskSelect.replaceChildren(new Option(t("hub.chooseTask"), ""));
  getBoardTasks().filter((task) => task.status !== "done").forEach((task) => {
    focusTaskSelect.add(new Option(task.title, task.id));
  });
  formatFocusTime();

  const tasks = getBoardTasks();
  const completed = tasks.filter((task) => task.completedAt);
  const durations = completed.map((task) =>
    Math.max(0, (new Date(task.completedAt) - new Date(task.createdAt)) / 86400000),
  );
  const average = durations.length
    ? t("hub.days", { count: (durations.reduce((sum, value) => sum + value, 0) / durations.length).toFixed(1) })
    : "—";
  const weekAgo = Date.now() - 7 * 86400000;
  const velocity = completed.filter((task) => new Date(task.completedAt).getTime() >= weekAgo).length;
  const blocked = tasks.filter((task) => !areDependenciesComplete(task, tasks)).length;
  document.querySelector('[data-insight="average"]').textContent = average;
  document.querySelector('[data-insight="velocity"]').textContent = String(velocity);
  document.querySelector('[data-insight="blocked"]').textContent = String(blocked);
  document.querySelector('[data-insight="activity"]').textContent = String(activity.length);

  const flowBars = document.querySelector("[data-flow-bars]");
  flowBars.replaceChildren();
  const max = Math.max(1, ...columns.map((column) => tasks.filter((task) => task.status === column.id).length));
  columns.forEach((column) => {
    const count = tasks.filter((task) => task.status === column.id).length;
    const row = document.createElement("div");
    row.className = "flow-bar";
    row.innerHTML = `<span></span><i></i><strong>${count}</strong>`;
    row.querySelector("span").textContent = getColumnName(column);
    row.querySelector("i").style.setProperty("--flow-width", `${Math.max(4, (count / max) * 100)}%`);
    flowBars.append(row);
  });

  activityList.replaceChildren();
  activity.slice(0, 12).forEach((entry) => {
    const item = document.createElement("li");
    const action = String(entry.action).startsWith("action.") ? t(entry.action) : entry.action;
    item.textContent = `${action} · ${new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(entry.createdAt))}`;
    activityList.append(item);
  });
  document.querySelectorAll("[data-automation]").forEach((input) => {
    input.checked = Boolean(automations[input.dataset.automation]);
  });
  renderAutomationRules();
  renderDashboard();
  applyAccessibility();
  renderPlanning();
}

function setView(view) {
  currentView = view === "calendar" ? "calendar" : "board";
  board.hidden = currentView !== "board";
  calendarView.hidden = currentView !== "calendar";
  document.querySelector('[data-action="show-board"]').classList.toggle("is-active", currentView === "board");
  document.querySelector('[data-action="show-calendar"]').classList.toggle("is-active", currentView === "calendar");
  if (currentView === "calendar") {
    renderCalendar(getBoardTasks(), calendarMonth.value, openEditDialog);
  }
}

function toggleFocusTimer(button) {
  if (focusTimer) {
    clearInterval(focusTimer);
    focusTimer = null;
    button.textContent = t("hub.start");
    return;
  }
  if (!focusTaskSelect.value) {
    showNotification(t("hub.focusChoose"), "error");
    return;
  }
  button.textContent = t("hub.pause");
  focusTimer = window.setInterval(() => {
    focusSeconds = Math.max(0, focusSeconds - 1);
    formatFocusTime();
    if (focusSeconds === 0) {
      clearInterval(focusTimer);
      focusTimer = null;
      button.textContent = t("hub.start");
      showNotification(t("hub.focusComplete"));
      if (Notification.permission === "granted") {
        new Notification("Flowboard", { body: t("hub.focusComplete") });
      }
    }
  }, 1000);
}

function encodeSyncPayload(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary);
}

function decodeSyncPayload(value) {
  const binary = atob(String(value).trim());
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

function createSyncPayload() {
  return {
    version: 4,
    boards: getBoards(),
    tasks: getTasks(),
    columns,
    templates,
    members,
    activity,
    accessibility,
    activeBoardId,
    theme: themeSelect.value || "classic",
    language: languageSelect.value || "ru",
    sort: sortMode,
    automations,
    goals,
    dashboard: dashboardPreferences,
  };
}

function applyRemoteWorkspace(payload) {
  if (!Array.isArray(payload?.boards) || !Array.isArray(payload?.tasks)) return;
  applyingRemoteWorkspace = true;
  setBoards(payload.boards);
  setTasks(payload.tasks);
  columns = normalizeColumns(payload.columns ?? columns);
  templates = Array.isArray(payload.templates) ? payload.templates : templates;
  members = Array.isArray(payload.members) ? payload.members : members;
  activity = Array.isArray(payload.activity) ? payload.activity : activity;
  accessibility = { ...accessibility, ...(payload.accessibility || {}) };
  automations = { ...defaultAutomations, ...(payload.automations || {}) };
  dashboardPreferences = { ...dashboardPreferences, ...(payload.dashboard || {}) };
  goals = Array.isArray(payload.goals) ? payload.goals : goals;
  activeBoardId = getBoardById(payload.activeBoardId) ? payload.activeBoardId : getBoards()[0].id;
  sortMode = payload.sort || sortMode;
  sortSelect.value = sortMode;
  if (payload.theme) {
    themeSelect.value = payload.theme;
    document.body.dataset.theme = payload.theme;
  }
  if (payload.language) {
    setLanguage(payload.language);
    languageSelect.value = payload.language;
    translateDocument();
  }
  persistWorkspace();
  applyingRemoteWorkspace = false;
  applyAccessibility();
  refreshBoard();
}

async function initializeRemoteWorkspace() {
  const initialGeneration = localWorkspaceGeneration;
  const remote = await loadRemoteWorkspace();
  if (remote && localWorkspaceGeneration === initialGeneration) {
    applyRemoteWorkspace(remote);
  }
  await flushWorkspaceQueue();
  connectRealtime(async () => {
    const generationBeforeLoad = localWorkspaceGeneration;
    const latest = await loadRemoteWorkspace();
    if (latest && localWorkspaceGeneration === generationBeforeLoad) {
      applyRemoteWorkspace(latest);
    }
  }, handleRealtimeEvent);
}

function checkDeadlineReminders() {
  if (Notification.permission !== "granted") return;
  const today = new Date().toISOString().slice(0, 10);
  const due = getTasks().filter((task) => task.deadline === today && task.status !== "done" && !task.archived);
  if (due.length > 0) {
    new Notification("Flowboard", { body: t("hub.dueToday", { tasks: due.map((task) => task.title).join(", ") }) });
  }
}

function undoLastAction() {
  const snapshot = history.pop();

  if (!snapshot) return;

  setTasks(snapshot.tasks);
  setBoards(snapshot.boards);
  activeBoardId = snapshot.activeBoardId;
  persistWorkspace();
  refreshBoard();
  updateUndoButton();
  showNotification(t("notice.undo", { action: t(snapshot.label) }));
}

function updateChecklistEditorEmptyState() {
  checklistEditor.querySelector("[data-checklist-editor-empty]").hidden =
    checklistEditor.querySelectorAll("[data-checklist-editor-item]").length > 0;
}

function addChecklistEditorItem(item = {}) {
  const row = checklistEditorTemplate.content.firstElementChild.cloneNode(true);
  row.dataset.checklistId = item.id ?? "";
  row.querySelector(".checklist-editor__checkbox").checked = Boolean(item.done);
  row.querySelector(".checklist-editor__text").value = item.text ?? "";
  checklistEditor.append(row);
  updateChecklistEditorEmptyState();
  row.querySelector(".checklist-editor__text").focus();
}

function renderChecklistEditor(items = []) {
  checklistEditor
    .querySelectorAll("[data-checklist-editor-item]")
    .forEach((item) => item.remove());
  items.forEach(addChecklistEditorItem);
  updateChecklistEditorEmptyState();
}

function collectChecklist() {
  return [...checklistEditor.querySelectorAll("[data-checklist-editor-item]")]
    .map((row) => ({
      id: row.dataset.checklistId,
      text: row.querySelector(".checklist-editor__text").value,
      done: row.querySelector(".checklist-editor__checkbox").checked,
    }))
    .filter((item) => item.text.trim());
}

function nextOrder(status = "todo") {
  const orders = getBoardTasks()
    .filter((task) => task.status === status)
    .map((task) => Number(task.order) || 0);
  return Math.max(-1, ...orders) + 1;
}

function createRecurringCopyIfNeeded(previousTask, updatedTask) {
  if (previousTask?.status === "done" || updatedTask?.status !== "done") {
    return null;
  }

  const recurringData = getRecurringTaskData(updatedTask);
  if (!recurringData) return null;

  return createTask({
    ...recurringData,
    boardId: updatedTask.boardId,
    order: nextOrder("todo"),
  });
}

function updateTaskWithRecurrence(taskId, changes) {
  const previousTask = getTaskById(taskId);
  const updatedTask = updateTask(taskId, changes);
  createRecurringCopyIfNeeded(previousTask, updatedTask);
  return updatedTask;
}

function openCreateDialog() {
  form.reset();
  form.elements.taskId.value = "";
  syncTaskFormOptions();
  renderChecklistEditor([]);
  pendingAttachments = [];
  renderAttachmentEditor();
  document.querySelector("[data-comment-field]").hidden = true;
  commentList.hidden = true;
  collaborationStatus.hidden = true;
  form.elements.milestone.checked = false;
  goalSelect.value = "";
  renderCustomFieldsEditor();
  taskDialogTitle.textContent = t("task.new");
  taskDialog.showModal();
  form.elements.title.focus();
}

function openEditDialog(taskId) {
  const task = getTaskById(taskId);

  if (!task) {
    showNotification(t("notice.taskNotFound"), "error");
    return;
  }

  form.elements.taskId.value = task.id;
  syncTaskFormOptions(task.id);
  form.elements.title.value = task.title;
  form.elements.description.value = task.description;
  form.elements.status.value = task.status;
  form.elements.priority.value = task.priority;
  form.elements.deadline.value = task.deadline;
  form.elements.recurrence.value = task.recurrence ?? "none";
  form.elements.tags.value = (task.tags ?? []).join(", ");
  form.elements.assignee.value = task.assignee ?? "";
  form.elements.color.value = task.color ?? "default";
  form.elements.cover.value = task.cover ?? "";
  form.elements.estimatedMinutes.value = task.estimatedMinutes || "";
  form.elements.startDate.value = task.startDate ?? "";
  form.elements.goalId.value = task.goalId ?? "";
  form.elements.milestone.checked = Boolean(task.milestone);
  renderCustomFieldsEditor(task);
  [...form.elements.dependsOn.options].forEach((option) => {
    option.selected = task.dependsOn?.includes(option.value);
  });
  renderChecklistEditor(task.checklist ?? []);
  pendingAttachments = [...(task.attachments ?? [])];
  renderAttachmentEditor();
  document.querySelector("[data-comment-field]").hidden = false;
  form.elements.comment.value = "";
  renderTaskComments(task);
  collaborationStatus.hidden = true;
  taskDialogTitle.textContent = t("task.edit");
  taskDialog.showModal();
  sendRealtime({ type: "presence", taskId: task.id });
  form.elements.title.focus();
}

function openDeleteDialog(taskId) {
  if (!getTaskById(taskId)) {
    showNotification(t("notice.taskNotFound"), "error");
    return;
  }

  deleteDialog.dataset.taskId = taskId;
  deleteDialog.showModal();
}

function closeDeleteDialog() {
  delete deleteDialog.dataset.taskId;
  deleteDialog.close();
}

function createNewBoard() {
  const name = window.prompt(t("prompt.newBoard"), t("prompt.newBoardDefault"));
  if (!name?.trim()) return;

  rememberState("action.createBoard");
  const newBoard = createBoard(name);
  activeBoardId = newBoard.id;
  commitChanges(t("notice.boardCreated"));
}

function renameActiveBoard() {
  const currentBoard = getBoardById(activeBoardId);
  const name = window.prompt(t("prompt.renameBoard"), currentBoard?.name ?? "");
  if (!name?.trim()) return;

  rememberState("action.renameBoard");
  if (renameBoard(activeBoardId, name)) {
    commitChanges(t("notice.boardRenamed"));
  } else {
    discardLastSnapshot();
  }
}

function removeActiveBoard() {
  if (getBoards().length === 1) {
    showNotification(t("notice.onlyBoard"), "error");
    return;
  }

  const currentBoard = getBoardById(activeBoardId);
  if (!window.confirm(t("prompt.deleteBoard", { name: currentBoard?.name }))) return;

  rememberState("action.deleteBoard");
  setTasks(getTasks().filter((task) => task.boardId !== activeBoardId));
  deleteBoard(activeBoardId);
  activeBoardId = getBoards()[0].id;
  commitChanges(t("notice.boardDeleted"));
}

function exportWorkspace() {
  const payload = {
    version: 4,
    exportedAt: new Date().toISOString(),
    activeBoardId,
    boards: getBoards(),
    tasks: getTasks(),
    columns,
    templates,
    members,
    activity,
    automations,
    dashboard: dashboardPreferences,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `flowboard-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
  showNotification(t("notice.exported"));
}

async function importWorkspace(file) {
  try {
    const payload = JSON.parse(await file.text());
    if (!Array.isArray(payload.boards) || !Array.isArray(payload.tasks)) {
      throw new Error(t("notice.invalidFile"));
    }

    rememberState("action.import");
    setBoards(payload.boards);
    setTasks(payload.tasks);
    columns = normalizeColumns(payload.columns ?? columns);
    templates = Array.isArray(payload.templates) ? payload.templates : templates;
    members = Array.isArray(payload.members) ? payload.members : members;
    activity = Array.isArray(payload.activity) ? payload.activity : activity;
    automations = { ...defaultAutomations, ...(payload.automations || {}) };
    dashboardPreferences = { ...dashboardPreferences, ...(payload.dashboard || {}) };
    activeBoardId = getBoardById(payload.activeBoardId)
      ? payload.activeBoardId
      : getBoards()[0].id;
    commitChanges(t("notice.imported"));
  } catch (error) {
    showNotification(error.message || t("notice.importError"), "error");
  } finally {
    importInput.value = "";
  }
}

function archiveCompletedTasks() {
  const completed = getBoardTasks().filter((task) => task.status === "done");
  if (completed.length === 0) {
    showNotification(t("notice.archiveEmpty"), "error");
    return;
  }

  rememberState("action.archive");
  const completedIds = new Set(completed.map((task) => task.id));
  setTasks(getTasks().map((task) =>
    completedIds.has(task.id) ? { ...task, archived: true } : task,
  ));
  commitChanges(t("notice.archived", { count: completed.length }));
}

function restoreArchivedTask(taskId) {
  const task = getTaskById(taskId);
  if (!task?.archived) return;

  rememberState("action.restore");
  updateTask(taskId, { archived: false });
  commitChanges(t("notice.restored"));
}

function moveCardWithKeyboard(card, key) {
  const task = getTaskById(card.dataset.taskId);
  if (!task) return;

  const statuses = columns.map((column) => column.id);
  const statusIndex = statuses.indexOf(task.status);

  if (key === "ArrowLeft" || key === "ArrowRight") {
    const targetStatus = statuses[statusIndex + (key === "ArrowLeft" ? -1 : 1)];
    if (!targetStatus) return;
    if (targetStatus === "done" && !areDependenciesComplete(task, getTasks())) {
      showNotification("Сначала завершите связанные задачи", "error");
      return;
    }

    rememberState("action.move");
    const previousTask = getTaskById(task.id);
    const movedTask = moveTask(task.id, targetStatus);
    createRecurringCopyIfNeeded(previousTask, movedTask);
    sortMode = "manual";
    sortSelect.value = sortMode;
    commitChanges(t("notice.taskMoved"));
    document.querySelector(`[data-task-id="${task.id}"]`)?.focus();
    return;
  }

  const peers = sortTasks(
    getBoardTasks().filter((item) => item.status === task.status),
    "manual",
  );
  const currentIndex = peers.findIndex((item) => item.id === task.id);
  const swapTask = peers[currentIndex + (key === "ArrowUp" ? -1 : 1)];
  if (!swapTask) return;

  rememberState("action.order");
  const currentOrder = task.order;
  setTasks(getTasks().map((item) => {
    if (item.id === task.id) return { ...item, order: swapTask.order };
    if (item.id === swapTask.id) return { ...item, order: currentOrder };
    return item;
  }));
  sortMode = "manual";
  sortSelect.value = sortMode;
  commitChanges(t("notice.orderChanged"));
  document.querySelector(`[data-task-id="${task.id}"]`)?.focus();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const taskData = Object.fromEntries(new FormData(form).entries());
  taskData.dependsOn = [...dependencySelect.selectedOptions].map((option) => option.value);
  taskData.milestone = form.elements.milestone.checked;
  taskData.customValues = Object.fromEntries(
    [...customFieldsInputs.querySelectorAll("[data-custom-field-id]")]
      .map((input) => [input.dataset.customFieldId, input.value])
      .filter(([, value]) => value !== ""),
  );
  taskData.checklist = collectChecklist();
  taskData.boardId = activeBoardId;
  const isEditing = Boolean(taskData.taskId);
  const currentTask = isEditing ? getTaskById(taskData.taskId) : null;
  const comment = String(taskData.comment ?? "").trim();
  let newComment = null;
  taskData.comments = [...(currentTask?.comments ?? [])];
  taskData.attachments = pendingAttachments;
  taskData.timeSpentSeconds = currentTask?.timeSpentSeconds ?? 0;
  taskData.timerStartedAt = currentTask?.timerStartedAt ?? "";
  if (comment) {
    newComment = {
      id: globalThis.crypto?.randomUUID?.() ?? String(Date.now()),
      author: currentAccount?.name ?? loadSetting("profile", "User"),
      authorId: currentAccount?.id ?? null,
      text: comment,
      mentions: [],
      parentId: form.elements.comment.dataset.parentId || null,
      createdAt: new Date().toISOString(),
      editedAt: null,
    };
    taskData.comments.push(newComment);
  }
  delete taskData.comment;

  if (taskData.status === "done" && !areDependenciesComplete(taskData, getTasks())) {
    showNotification("Сначала завершите связанные задачи", "error");
    return;
  }

  try {
    rememberState(isEditing ? "action.edit" : "action.create");
    if (isEditing) {
      updateTaskWithRecurrence(taskData.taskId, taskData);
    } else {
      taskData.order = nextOrder(taskData.status);
      createTask(taskData);
    }
    taskDialog.close();
    commitChanges(t(isEditing ? "notice.taskUpdated" : "notice.taskCreated"));
    if (isEditing && newComment) {
      void createTaskComment(taskData.taskId, {
        id: newComment.id,
        text: newComment.text,
        parentId: newComment.parentId,
      });
    }
    delete form.elements.comment.dataset.parentId;
  } catch (error) {
    discardLastSnapshot();
    showNotification(error.message, "error");
  }
});

form.addEventListener("input", (event) => {
  const taskId = form.elements.taskId.value;
  const field = event.target?.name;
  const allowed = new Set(["title", "description", "status", "priority", "deadline", "assignee", "tags"]);
  if (!taskId || !allowed.has(field)) return;
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    sendRealtime({ type: "task.draft", taskId, field, value: event.target.value });
    collaborationLamport += 1;
    sendRealtime({
      type: "task.operation", workspaceId: getActiveWorkspaceId() || null, taskId, field,
      operation: { kind: "set", value: event.target.value }, lamport: collaborationLamport,
    });
  }, 180);
});

templateSelect.addEventListener("change", () => {
  const template = templates.find((item) => item.id === templateSelect.value);
  if (!template) return;
  const data = template.data;
  form.elements.description.value = data.description ?? "";
  form.elements.priority.value = data.priority ?? "medium";
  form.elements.recurrence.value = data.recurrence ?? "none";
  form.elements.tags.value = (data.tags ?? []).join(", ");
  form.elements.color.value = data.color ?? "default";
  form.elements.cover.value = data.cover ?? "";
  renderChecklistEditor(data.checklist ?? []);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;

  const taskId = button.closest(".task-card, .archive-item")?.dataset.taskId ?? button.dataset.taskId;

  switch (button.dataset.action) {
    case "open-task-dialog": openCreateDialog(); break;
    case "mobile-new-task": openCreateDialog(); break;
    case "open-account":
      renderAccountPanel();
      accountDialog.showModal();
      void refreshAccount();
      break;
    case "open-platform":
      platformDialog.showModal();
      void refreshPlatformData();
      break;
    case "close-platform": platformDialog.close(); break;
    case "select-workspace":
      setActiveWorkspaceId(button.dataset.workspaceId);
      cloudWorkspaceSelect.value = button.dataset.workspaceId;
      void initializeRemoteWorkspace();
      void refreshPlatformData();
      break;
    case "create-workspace": {
      const input = document.querySelector("#workspace-name");
      const name = input.value.trim();
      if (!name) break;
      void createCloudWorkspace(name).then(async (workspace) => {
        input.value = "";
        setActiveWorkspaceId(workspace.id);
        await refreshAccount();
        await initializeRemoteWorkspace();
        await refreshPlatformData();
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "import-external": {
      const file = document.querySelector("#external-import-file").files[0];
      const provider = document.querySelector("#external-import-provider").value;
      if (!file) break;
      void file.text().then((text) => {
        const imported = importExternalData(provider, JSON.parse(text), activeBoardId);
        rememberState("action.import"); setTasks([...getTasks(), ...imported]); commitChanges(t("notice.imported"));
        document.querySelector("#external-import-file").value = "";
      }).catch((error) => showNotification(error.message || t("notice.importError"), "error"));
      break;
    }
    case "create-cloud-backup": {
      const workspaceId = getActiveWorkspaceId(); if (!workspaceId) break;
      void createBackup(workspaceId, `Flowboard ${new Date().toLocaleString()}`).then(refreshPlatformData).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "restore-cloud-backup": {
      const workspaceId = getActiveWorkspaceId(); if (!workspaceId) break;
      void restoreBackup(workspaceId, button.dataset.backupId).then(async () => { await initializeRemoteWorkspace(); showNotification(t("feature.restored")); }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "download-cloud-backup": {
      const workspaceId = getActiveWorkspaceId(); if (!workspaceId) break;
      void downloadBackup(workspaceId, button.dataset.backupId).then((payload) => {
        const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = `flowboard-backup-${button.dataset.backupId}.json`; link.click(); URL.revokeObjectURL(url);
      });
      break;
    }
    case "setup-totp":
      void setupTotp().then(async (result) => {
        const code = window.prompt(`${result.uri}\n\n${t("security.enterCode")}`, "");
        if (!code) return;
        await enableTotp(code);
        await refreshPlatformData();
        showNotification(t("security.enabled"));
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    case "register-passkey":
      void registerPasskey().then(() => refreshPlatformData()).catch((error) => showNotification(error.message, "error"));
      break;
    case "passkey-login": {
      const email = document.querySelector("#account-email").value.trim();
      if (!email) break;
      void loginWithPasskey(email).then(async (account) => {
        currentAccount = account;
        await refreshAccount();
        await initializeRemoteWorkspace();
      }).catch((error) => showNotification(error.message, "error"));
      break;
    }
    case "verify-email":
      void sendEmailVerification().then((result) => {
        platformStatus.textContent = result.verificationToken
          ? `${t("security.verificationToken")}: ${result.verificationToken}`
          : t("security.verificationSent");
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    case "enable-push":
      void (async () => {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") throw new Error(t("hub.notificationsDenied"));
        const registration = await navigator.serviceWorker.ready;
        await enablePushNotifications(registration);
        showNotification(t("hub.notificationsEnabled"));
      })().catch((error) => showNotification(error.message, "error"));
      break;
    case "create-integration": {
      const workspaceId = getActiveWorkspaceId();
      const nameInput = document.querySelector("#integration-name");
      const kind = document.querySelector("#integration-kind").value;
      const endpointInput = document.querySelector("#integration-endpoint");
      if (!workspaceId || !nameInput.value.trim()) break;
      const [botToken, chatId] = endpointInput.value.split("|", 2);
      const config = kind === "slack" ? { webhookUrl: endpointInput.value.trim() }
        : kind === "telegram" ? { botToken: botToken?.trim(), chatId: chatId?.trim() } : {};
      void createIntegration({ workspaceId, kind, name: nameInput.value.trim(), config }).then(async (item) => {
        nameInput.value = "";
        endpointInput.value = "";
        await refreshPlatformData();
        if (item.secret) platformStatus.textContent = `${t("platform.webhookSecret")}: ${item.secret}`;
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "test-integration":
      void testIntegration(button.dataset.integrationId)
        .then(() => showNotification("Integration OK"))
        .catch(() => showNotification(t("account.error"), "error"));
      break;
    case "create-custom-field": {
      const workspaceId = getActiveWorkspaceId();
      const nameInput = document.querySelector("#custom-field-name");
      const fieldType = document.querySelector("#custom-field-type").value;
      if (!workspaceId || !nameInput.value.trim()) break;
      void createCustomField({ workspaceId, name: nameInput.value.trim(), fieldType, options: [], required: false }).then(async () => {
        nameInput.value = "";
        await refreshPlatformData();
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "create-share": {
      const workspaceId = getActiveWorkspaceId();
      if (!workspaceId) break;
      void createPublicShare({
        workspaceId, boardId: activeBoardId, mode: document.querySelector("#share-mode").value,
        password: document.querySelector("#share-password").value || null,
      }).then((share) => {
        const base = getApiConfiguration().url;
        document.querySelector("[data-share-result]").textContent = `${base}/public/${share.token}`;
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "close-account": accountDialog.close(); break;
    case "save-api-url":
      setApiConfiguration(accountApiUrl.value);
      accountStatus.textContent = t("account.apiSaved");
      void refreshAccount().then(() => initializeRemoteWorkspace());
      break;
    case "account-login": void authenticateAccount("login"); break;
    case "account-register": void authenticateAccount("register"); break;
    case "request-password-reset": {
      const email = document.querySelector("#account-email").value.trim();
      if (!email) break;
      void requestPasswordReset(email).then((result) => {
        accountStatus.textContent = result.resetToken
          ? `${t("account.resetSent")} · ${result.resetToken}`
          : t("account.resetSent");
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "send-invitation": {
      const email = document.querySelector("#invite-email").value.trim();
      const role = document.querySelector("#invite-role").value;
      if (!email) break;
      void createInvitation(email, role).then(async (invitation) => {
        document.querySelector("#invite-email").value = "";
        await refreshAccount();
        showNotification(invitation.token ? `${t("account.inviteCreated")}: ${invitation.token}` : t("account.inviteCreated"));
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "revoke-session":
      void revokeSession(button.dataset.sessionId).then(() => refreshAccount());
      break;
    case "account-logout":
      logoutAccount();
      currentAccount = null;
      remoteMembers = [];
      cloudWorkspaces = [];
      setActiveWorkspaceId("");
      cloudWorkspaceControl.hidden = true;
      renderAccountPanel();
      break;
    case "open-notifications":
      renderNotificationCenter();
      notificationsDialog.showModal();
      if (currentAccount) void getNotificationSchedule().then((schedule) => {
        notificationSchedule = schedule;
        document.querySelector("#notification-lead").value = schedule.leadMinutes;
        document.querySelector("#notification-digest").value = schedule.digestFrequency;
        document.querySelector("#notification-hour").value = schedule.digestHour;
      });
      break;
    case "close-notifications": notificationsDialog.close(); break;
    case "read-notification":
      void markNotificationRead(button.dataset.notificationId).then(async () => {
        remoteNotifications = await getNotifications().catch(() => remoteNotifications);
        renderNotificationCenter();
      });
      break;
    case "read-all-notifications":
      void markAllNotificationsRead().then(async () => {
        remoteNotifications = await getNotifications().catch(() => remoteNotifications);
        renderNotificationCenter();
      });
      break;
    case "save-notification-schedule":
      notificationSchedule = {
        leadMinutes: Number(document.querySelector("#notification-lead").value),
        digestFrequency: document.querySelector("#notification-digest").value,
        digestHour: Number(document.querySelector("#notification-hour").value),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };
      void setNotificationSchedule(notificationSchedule).then(() => showNotification(t("feature.scheduleSaved"))).catch(() => showNotification(t("account.error"), "error"));
      break;
    case "create-goal": {
      const title = document.querySelector("#goal-title").value.trim();
      const targetDate = document.querySelector("#goal-date").value;
      if (!title) break;
      const localGoal = { id: globalThis.crypto?.randomUUID?.() ?? String(Date.now()), title, description: "", targetDate, color: "lime", progress: 0 };
      void (currentAccount ? createGoal({ title, targetDate, description: "", color: "lime" }) : Promise.resolve(localGoal))
        .then((goal) => {
          goals = [...goals, goal];
          saveSetting("goals", goals);
          document.querySelector("#goal-title").value = "";
          document.querySelector("#goal-date").value = "";
          syncTaskFormOptions(form.elements.taskId.value);
          renderPlanning();
        }).catch(() => showNotification(t("account.error"), "error"));
      break;
    }
    case "reply-comment":
      form.elements.comment.dataset.parentId = button.dataset.commentId;
      form.elements.comment.placeholder = t("comment.replyPlaceholder");
      form.elements.comment.focus();
      break;
    case "react-comment":
      void reactToComment(button.dataset.commentId, "👍").then((updated) => {
        const activeTask = getTaskById(form.elements.taskId.value);
        if (!activeTask) return;
        updateTask(activeTask.id, { comments: activeTask.comments.map((item) => item.id === updated.id ? updated : item) });
        saveTasks(getTasks());
        renderTaskComments(getTaskById(activeTask.id));
      });
      break;
    case "resolve-comment":
      void updateComment(button.dataset.commentId, { resolved: button.dataset.resolved !== "true" }).then((updated) => {
        const activeTask = getTaskById(form.elements.taskId.value);
        if (!activeTask) return;
        updateTask(activeTask.id, { comments: activeTask.comments.map((item) => item.id === updated.id ? updated : item) });
        saveTasks(getTasks());
        renderTaskComments(getTaskById(activeTask.id));
      });
      break;
    case "toggle-watch-task": {
      const activeTaskId = form.elements.taskId.value;
      if (!activeTaskId || !currentAccount) break;
      const watching = button.dataset.watching !== "true";
      void setTaskWatching(activeTaskId, watching).then(() => {
        button.dataset.watching = String(watching);
        button.textContent = t(watching ? "comment.unwatch" : "comment.watch");
      });
      break;
    }
    case "open-command-palette":
      commandSearch.value = "";
      renderCommandPalette();
      commandDialog.showModal();
      commandSearch.focus();
      break;
    case "close-command-palette": commandDialog.close(); break;
    case "open-productivity-hub":
      renderProductivityHub();
      productivityDialog.showModal();
      break;
    case "mobile-open-hub": renderProductivityHub(); productivityDialog.showModal(); break;
    case "add-automation-rule": {
      const rule = createAutomationRule({
        name: document.querySelector("#rule-name").value || t("feature.rule"),
        trigger: document.querySelector("#rule-trigger").value,
        triggerValue: document.querySelector("#rule-trigger-value").value,
        action: document.querySelector("#rule-action").value,
        actionValue: document.querySelector("#rule-action-value").value,
      });
      automations = { ...automations, rules: [...(automations.rules || []), rule] };
      saveSetting("automations", automations); renderProductivityHub();
      const workspaceId = getActiveWorkspaceId();
      if (workspaceId && currentAccount) void createAutomationRuleRemote({ workspaceId, ...rule }).then((remoteRule) => {
        automations = { ...automations, rules: (automations.rules || []).map((item) => item.id === rule.id ? { ...item, id: remoteRule.id } : item) };
        saveSetting("automations", automations); renderProductivityHub();
      }).catch(() => {});
      break;
    }
    case "delete-automation-rule": {
      const workspaceId = getActiveWorkspaceId();
      if (workspaceId && currentAccount) void deleteAutomationRuleRemote(workspaceId, button.dataset.ruleId).catch(() => {});
      automations = { ...automations, rules: (automations.rules || []).filter((rule) => rule.id !== button.dataset.ruleId) };
      saveSetting("automations", automations); renderProductivityHub();
      break;
    }
    case "focus-search": searchInput.focus(); searchInput.scrollIntoView({ behavior: "smooth", block: "center" }); break;
    case "close-productivity-hub": productivityDialog.close(); break;
    case "show-board": setView("board"); break;
    case "show-calendar": setView("calendar"); break;
    case "mobile-show-board": setView("board"); break;
    case "mobile-show-calendar": setView("calendar"); break;
    case "close-task-dialog": taskDialog.close(); break;
    case "edit-task": openEditDialog(taskId); break;
    case "delete-task": openDeleteDialog(taskId); break;
    case "add-checklist-item":
      if (checklistEditor.querySelectorAll("[data-checklist-editor-item]").length < 8) {
        addChecklistEditorItem();
      } else {
        showNotification(t("notice.checklistLimit"), "error");
      }
      break;
    case "remove-checklist-item":
      button.closest("[data-checklist-editor-item]")?.remove();
      updateChecklistEditorEmptyState();
      break;
    case "cancel-delete": closeDeleteDialog(); break;
    case "confirm-delete": {
      const deletingTaskId = deleteDialog.dataset.taskId;
      if (deletingTaskId && getTaskById(deletingTaskId)) {
        rememberState("action.delete");
        deleteTask(deletingTaskId);
        closeDeleteDialog();
        commitChanges(t("notice.taskDeleted"));
      }
      break;
    }
    case "reset-filters":
      searchInput.value = "";
      prioritySelect.value = "all";
      tagSelect.value = "all";
      assigneeFilter.value = "all";
      deadlineFromFilter.value = "";
      deadlineToFilter.value = "";
      refreshBoard();
      break;
    case "undo": undoLastAction(); break;
    case "create-board": createNewBoard(); break;
    case "rename-board": renameActiveBoard(); break;
    case "delete-board": removeActiveBoard(); break;
    case "export-workspace": exportWorkspace(); break;
    case "import-workspace": importInput.click(); break;
    case "archive-done": archiveCompletedTasks(); break;
    case "open-archive": archiveDialog.showModal(); break;
    case "close-archive": archiveDialog.close(); break;
    case "restore-task": restoreArchivedTask(taskId); break;
    case "remove-attachment":
      pendingAttachments = pendingAttachments.filter((attachment) => attachment.id !== button.dataset.attachmentId);
      renderAttachmentEditor();
      break;
    case "attachment-history":
      void listAttachmentVersions(button.dataset.attachmentId).then((versions) => {
        showNotification(versions.map((item) => `v${item.version} ${item.name}`).join(" · ") || "No versions");
      }).catch(() => showNotification(t("account.error"), "error"));
      break;
    case "replace-attachment": {
      const picker = document.createElement("input"); picker.type = "file";
      picker.addEventListener("change", () => {
        const file = picker.files[0]; if (!file) return;
        void replaceAttachmentVersion(button.dataset.attachmentId, file).then(() => {
          const item = pendingAttachments.find((attachment) => attachment.id === button.dataset.attachmentId);
          if (item) Object.assign(item, { name: file.name, size: file.size, type: file.type });
          renderAttachmentEditor(); showNotification(t("notice.taskUpdated"));
        }).catch(() => showNotification(t("account.error"), "error"));
      });
      picker.click(); break;
    }
    case "track-time": {
      const task = getTaskById(taskId);
      if (!task) break;
      rememberState("action.edit");
      if (task.timerStartedAt) {
        const elapsed = Math.max(0, Math.floor((Date.now() - new Date(task.timerStartedAt).getTime()) / 1000));
        updateTask(taskId, { timeSpentSeconds: (task.timeSpentSeconds || 0) + elapsed, timerStartedAt: "" });
        commitChanges(t("time.stopped"));
      } else {
        updateTask(taskId, { timerStartedAt: new Date().toISOString() });
        commitChanges(t("time.started"));
      }
      break;
    }
    case "apply-batch": {
      rememberState("action.edit");
      const completedAt = new Date().toISOString();
      setTasks(getTasks().map((task) => {
        if (!selectedTaskIds.has(task.id)) return task;
        const status = batchStatus.value || task.status;
        return {
          ...task,
          status,
          completedAt: status === "done" ? task.completedAt || completedAt : "",
          ...(batchPriority.value ? { priority: batchPriority.value } : {}),
        };
      }));
      selectedTaskIds.clear();
      commitChanges(t("batch.updated"));
      break;
    }
    case "archive-batch":
      rememberState("action.archive");
      setTasks(getTasks().map((task) => selectedTaskIds.has(task.id) ? { ...task, archived: true } : task));
      selectedTaskIds.clear();
      commitChanges(t("batch.archived"));
      break;
    case "delete-batch":
      if (!window.confirm(t("batch.deleteConfirm", { count: selectedTaskIds.size }))) break;
      rememberState("action.delete");
      setTasks(getTasks().filter((task) => !selectedTaskIds.has(task.id)));
      selectedTaskIds.clear();
      commitChanges(t("batch.deleted"));
      break;
    case "clear-batch":
      selectedTaskIds.clear();
      syncBatchBar();
      break;
    case "save-template": {
      const name = window.prompt("Название шаблона:", form.elements.title.value || "Новый шаблон");
      if (!name?.trim()) break;
      templates = [...templates, {
        id: globalThis.crypto?.randomUUID?.() ?? String(Date.now()),
        name: name.trim().slice(0, 40),
        data: {
          description: form.elements.description.value,
          priority: form.elements.priority.value,
          recurrence: form.elements.recurrence.value,
          tags: form.elements.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
          color: form.elements.color.value,
          cover: form.elements.cover.value,
          checklist: collectChecklist(),
        },
      }].slice(-20);
      saveSetting("templates", templates);
      syncTaskFormOptions(form.elements.taskId.value);
      showNotification("Шаблон сохранён");
      break;
    }
    case "add-column": {
      const name = window.prompt(t("hub.columnPrompt"), t("hub.columnDefault"));
      if (!name?.trim()) break;
      columns = addColumn(columns, name);
      persistWorkspace();
      refreshBoard();
      break;
    }
    case "rename-column": {
      const column = columns.find((item) => item.id === button.dataset.columnId);
      const name = window.prompt(t("hub.renameColumnPrompt"), column?.name ?? "");
      if (!name?.trim()) break;
      columns = renameColumn(columns, button.dataset.columnId, name);
      persistWorkspace();
      refreshBoard();
      break;
    }
    case "remove-column": {
      const columnId = button.dataset.columnId;
      setTasks(getTasks().map((task) => task.status === columnId ? { ...task, status: "todo" } : task));
      columns = removeColumn(columns, columnId);
      persistWorkspace();
      refreshBoard();
      break;
    }
    case "add-member": {
      const member = window.prompt(t("hub.memberPrompt"), "");
      if (!member?.trim()) break;
      members = [...new Set([...members, member.trim().slice(0, 50)])];
      persistWorkspace();
      refreshBoard();
      break;
    }
    case "remove-member":
      members = members.filter((member) => member !== button.dataset.member);
      persistWorkspace();
      refreshBoard();
      break;
    case "toggle-focus": toggleFocusTimer(button); break;
    case "reset-focus":
      clearInterval(focusTimer);
      focusTimer = null;
      focusSeconds = 25 * 60;
      formatFocusTime();
      productivityDialog.querySelector('[data-action="toggle-focus"]').textContent = t("hub.start");
      break;
    case "enable-reminders":
      if (!("Notification" in window)) {
        showNotification(t("hub.notificationsUnsupported"), "error");
      } else {
        Notification.requestPermission().then((permission) => {
          showNotification(t(permission === "granted" ? "hub.notificationsEnabled" : "hub.notificationsDenied"), permission === "granted" ? "success" : "error");
          checkDeadlineReminders();
        });
      }
      break;
    case "install-app":
      deferredInstallPrompt?.prompt();
      deferredInstallPrompt = null;
      installButton.hidden = true;
      break;
    case "create-sync-package":
      syncPackage.value = encodeSyncPayload(createSyncPayload());
      syncPackage.select();
      navigator.clipboard?.writeText(syncPackage.value).catch(() => {});
      showNotification(t("hub.syncCreated"));
      break;
    case "apply-sync-package":
      try {
        const payload = decodeSyncPayload(syncPackage.value);
        if (!Array.isArray(payload.boards) || !Array.isArray(payload.tasks)) throw new Error();
        rememberState("action.import");
        setBoards(payload.boards);
        setTasks(payload.tasks);
        columns = normalizeColumns(payload.columns);
        templates = Array.isArray(payload.templates) ? payload.templates : [];
        members = Array.isArray(payload.members) ? payload.members : [];
        activity = Array.isArray(payload.activity) ? payload.activity : [];
        automations = { ...defaultAutomations, ...(payload.automations || {}) };
        activeBoardId = getBoards()[0].id;
        commitChanges(t("hub.syncApplied"));
      } catch {
        showNotification(t("hub.syncInvalid"), "error");
      }
      break;
  }
});

searchInput.addEventListener("input", refreshBoard);
prioritySelect.addEventListener("change", refreshBoard);
tagSelect.addEventListener("change", refreshBoard);
assigneeFilter.addEventListener("change", refreshBoard);
deadlineFromFilter.addEventListener("change", refreshBoard);
deadlineToFilter.addEventListener("change", refreshBoard);

sortSelect.addEventListener("change", () => {
  sortMode = sortSelect.value;
  saveSetting("sort", sortMode);
  refreshBoard();
});

cloudWorkspaceSelect.addEventListener("change", () => {
  setActiveWorkspaceId(cloudWorkspaceSelect.value);
  void initializeRemoteWorkspace();
  void refreshPlatformData();
});

platformDialog.addEventListener("click", (event) => {
  const action = event.target.closest("[data-assistant-action]")?.dataset.assistantAction;
  if (!action) return;
  const output = document.querySelector("[data-assistant-result]");
  output.textContent = t("platform.loading");
  void runAssistant({
    action,
    workspaceId: getActiveWorkspaceId() || null,
    text: document.querySelector("#assistant-text").value,
  }).then((result) => { output.textContent = JSON.stringify(result, null, 2); })
    .catch((error) => { output.textContent = error.message; });
});

boardSelect.addEventListener("change", () => {
  activeBoardId = boardSelect.value;
  saveSetting("activeBoard", activeBoardId);
  refreshBoard();
});

themeSelect.addEventListener("change", () => {
  document.body.dataset.theme = themeSelect.value;
  saveSetting("theme", themeSelect.value);
});

languageSelect.addEventListener("change", () => {
  setLanguage(languageSelect.value);
  saveSetting("language", languageSelect.value);
  translateDocument();
  updateUndoButton();
  refreshBoard();
  renderAccountPanel();
  renderNotificationCenter();
  renderPlanning();
});

notificationFilter.addEventListener("change", renderNotificationCenter);

importInput.addEventListener("change", () => {
  const [file] = importInput.files;
  if (file) importWorkspace(file);
});

attachmentInput.addEventListener("change", async () => {
  try {
    const available = Math.max(0, 5 - pendingAttachments.length);
    const additions = await Promise.all([...attachmentInput.files].slice(0, available).map(readAttachment));
    pendingAttachments = [...pendingAttachments, ...additions];
    renderAttachmentEditor();
  } catch (error) {
    showNotification(error.message, "error");
  } finally {
    attachmentInput.value = "";
  }
});

commandSearch.addEventListener("input", renderCommandPalette);
commandList.addEventListener("click", (event) => {
  const command = event.target.closest("[data-command]")?.dataset.command;
  if (command) runCommand(command);
});

document.querySelectorAll("[data-automation]").forEach((input) => {
  input.addEventListener("change", () => {
    automations = { ...automations, [input.dataset.automation]: input.checked };
    const result = applyAutomations(getTasks(), automations);
    if (result.changed) setTasks(result.tasks);
    persistWorkspace();
    refreshBoard();
  });
});

document.querySelectorAll("[data-oauth-provider]").forEach((button) => {
  button.addEventListener("click", () => void startOAuth(button.dataset.oauthProvider).catch((error) => showNotification(error.message, "error")));
});

document.querySelectorAll("[data-dashboard-widget]").forEach((input) => {
  input.addEventListener("change", () => {
    dashboardPreferences = { ...dashboardPreferences, [input.dataset.dashboardWidget]: input.checked };
    saveSetting("dashboard", dashboardPreferences); renderDashboard();
  });
});

document.querySelectorAll("[data-sync-resolution]").forEach((button) => {
  button.addEventListener("click", () => void resolveSyncConflict(button.dataset.syncResolution).then((workspace) => {
    syncConflictDialog.close();
    if (button.dataset.syncResolution === "remote" && workspace) applyRemoteWorkspace(workspace);
  }));
});

window.addEventListener("flowboard:sync", (event) => {
  const labels = { queued: "◌ Queued", syncing: "↻ Syncing", synced: "● Synced", offline: "○ Offline", conflict: "! Conflict" };
  syncStatus.dataset.state = event.detail.status;
  syncStatus.textContent = labels[event.detail.status] || "● Local";
  if (event.detail.status === "conflict" && !syncConflictDialog.open) syncConflictDialog.showModal();
});

let touchStart = null;
board.addEventListener("touchstart", (event) => {
  const card = event.target.closest(".task-card");
  if (card && event.touches.length === 1) touchStart = { x: event.touches[0].clientX, y: event.touches[0].clientY, taskId: card.dataset.taskId };
}, { passive: true });
board.addEventListener("touchend", (event) => {
  if (!touchStart || !event.changedTouches.length) return;
  const dx = event.changedTouches[0].clientX - touchStart.x;
  const dy = event.changedTouches[0].clientY - touchStart.y;
  if (Math.abs(dx) > 80 && Math.abs(dx) > Math.abs(dy) * 1.5) {
    const task = getTaskById(touchStart.taskId); const index = columns.findIndex((column) => column.id === task?.status);
    const target = columns[index + (dx > 0 ? 1 : -1)];
    if (task && target) { rememberState("action.move"); moveTask(task.id, target.id); commitChanges(t("notice.taskMoved")); }
  }
  touchStart = null;
}, { passive: true });

calendarMonth.addEventListener("change", () => {
  renderCalendar(getBoardTasks(), calendarMonth.value, openEditDialog);
});

document.querySelectorAll("[data-setting]").forEach((input) => {
  input.addEventListener("input", () => {
    const key = input.dataset.setting;
    accessibility = {
      ...accessibility,
      [key]: input.type === "checkbox" ? input.checked : Number(input.value),
    };
    saveSetting("accessibility", accessibility);
    applyAccessibility();
  });
});

board.addEventListener("change", (event) => {
  const selector = event.target.closest('[data-action="select-task"]');
  if (selector) {
    const id = selector.closest(".task-card")?.dataset.taskId;
    if (id) selector.checked ? selectedTaskIds.add(id) : selectedTaskIds.delete(id);
    syncBatchBar();
    return;
  }
  const checkbox = event.target.closest('[data-action="toggle-checklist"]');
  if (!checkbox) return;

  const task = getTaskById(checkbox.closest(".task-card")?.dataset.taskId);
  if (!task) return;

  rememberState("action.checklist");
  const checklist = (task.checklist ?? []).map((item) =>
    item.id === checkbox.dataset.checklistId
      ? { ...item, done: checkbox.checked }
      : item,
  );
  updateTask(task.id, { checklist });
  commitChanges(t("notice.checklistUpdated"));
});

document.addEventListener("keydown", (event) => {
  const isTyping = event.target.matches("input, textarea, select") || event.target.isContentEditable;

  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
    event.preventDefault();
    undoLastAction();
    return;
  }

  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    commandSearch.value = "";
    renderCommandPalette();
    commandDialog.showModal();
    commandSearch.focus();
    return;
  }

  const card = event.target.closest(".task-card");
  if (card && event.altKey && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
    event.preventDefault();
    moveCardWithKeyboard(card, event.key);
    return;
  }

  if (isTyping) return;
  if (event.key.toLowerCase() === "n") {
    event.preventDefault();
    openCreateDialog();
  } else if (event.key === "/") {
    event.preventDefault();
    searchInput.focus();
  }
});

[taskDialog, deleteDialog, archiveDialog, productivityDialog, commandDialog, accountDialog, notificationsDialog].forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

taskDialog.addEventListener("close", () => {
  clearTimeout(draftTimer);
  sendRealtime({ type: "presence", taskId: null });
  collaborationStatus.hidden = true;
});

initDragAndDrop(board, (taskId, newStatus, beforeTaskId) => {
  const previousTask = getTaskById(taskId);
  if (!previousTask) return;
  if (newStatus === "done" && !areDependenciesComplete(previousTask, getTasks())) {
    showNotification("Сначала завершите связанные задачи", "error");
    return;
  }

  rememberState("action.move");
  const movedTask = moveTask(taskId, newStatus, beforeTaskId);
  createRecurringCopyIfNeeded(previousTask, movedTask);
  sortMode = "manual";
  sortSelect.value = sortMode;
  commitChanges(t("notice.positionChanged"));
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  installButton.hidden = false;
});

window.addEventListener("storage", (event) => {
  if (!event.key?.startsWith("flowboard-")) return;
  setBoards(loadBoards());
  setTasks(loadTasks());
  columns = normalizeColumns(loadSetting("columns", getDefaultColumns()));
  templates = loadSetting("templates", []);
  members = loadSetting("members", []);
  activity = loadSetting("activity", []);
  automations = { ...defaultAutomations, ...(loadSetting("automations", {}) || {}) };
  goals = Array.isArray(loadSetting("goals", [])) ? loadSetting("goals", []) : [];
  refreshBoard();
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./service-worker.js").catch(() => {}));
}

setBoards(loadBoards());
setTasks(loadTasks());
columns = normalizeColumns(loadSetting("columns", getDefaultColumns()));
templates = Array.isArray(loadSetting("templates", [])) ? loadSetting("templates", []) : [];
if (templates.length === 0) {
  templates = [
    { id: "template-release", name: "Релиз", data: { priority: "high", tags: ["релиз"], color: "purple", cover: "🚀", checklist: [{ text: "Проверить сборку" }, { text: "Обновить документацию" }] } },
    { id: "template-meeting", name: "Встреча", data: { priority: "medium", tags: ["встреча"], color: "yellow", cover: "💬", checklist: [{ text: "Подготовить повестку" }, { text: "Записать решения" }] } },
    { id: "template-bug", name: "Исправление ошибки", data: { priority: "high", tags: ["bug"], color: "pink", cover: "🐞", checklist: [{ text: "Воспроизвести" }, { text: "Добавить тест" }] } },
  ];
}
members = Array.isArray(loadSetting("members", [])) ? loadSetting("members", []) : [];
activity = Array.isArray(loadSetting("activity", [])) ? loadSetting("activity", []) : [];
accessibility = {
  ...accessibility,
  ...(loadSetting("accessibility", {}) || {}),
};
automations = {
  ...defaultAutomations,
  ...(loadSetting("automations", {}) || {}),
};
dashboardPreferences = { ...dashboardPreferences, ...(loadSetting("dashboard", {}) || {}) };
goals = Array.isArray(loadSetting("goals", [])) ? loadSetting("goals", []) : [];
calendarMonth.value = todayMonth();
const language = loadSetting("language", "ru");
setLanguage(language);
languageSelect.value = language;
translateDocument();
activeBoardId = loadSetting("activeBoard", getBoards()[0].id);
sortMode = loadSetting("sort", "manual");
sortSelect.value = sortMode;
const theme = loadSetting("theme", "classic");
themeSelect.value = theme;
document.body.dataset.theme = theme;
applyAccessibility();
updateUndoButton();
refreshBoard();
renderAccountPanel();
completeOAuthLogin();
window.setInterval(checkDeadlineReminders, 60 * 60 * 1000);
void refreshAccount().then(() => initializeRemoteWorkspace());
