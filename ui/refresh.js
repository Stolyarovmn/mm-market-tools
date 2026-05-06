import { REPORT_STORAGE_KEY, getStoredRefreshToken, initThemeToggle, setStoredRefreshToken } from "./state.js";
import { createInfoIcon } from "./components.js";

let activeJobId = null;
let pollTimer = null;
let dashboardIndexPromise = null;
let sharedToken = "";
let sharedTokenHealth = null;
let jobCatalog = [];
let queueItems = [];
let queueRunning = false;
let queueStopRequested = false;
const QUEUE_DELAY_MS = 6000;
let controlRoomMode = false;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function actionControl(button, infoText) {
  const wrap = el("div", "action-with-info");
  wrap.append(button);
  if (infoText) {
    wrap.append(createInfoIcon(infoText));
  }
  return wrap;
}

function attachInfoIconToHeading(selector, text) {
  const heading = document.querySelector(selector);
  if (!heading || !text || heading.dataset.infoDecorated === "true") return;
  heading.append(createInfoIcon(text));
  heading.dataset.infoDecorated = "true";
}

async function loadJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function validateToken(token) {
  return loadJson("/api/token-health", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatDate(value) {
  if (!value) return "н/д";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch (_) {
    return value;
  }
}

async function loadDashboardIndex() {
  if (!dashboardIndexPromise) {
    dashboardIndexPromise = loadJson("/data/dashboard/index.json").catch(() => null);
  }
  return dashboardIndexPromise;
}

function getArtifactKind(path) {
  const lower = String(path || "").toLowerCase();
  if (lower.includes("/data/dashboard/")) return "dashboard_bundle";
  if (lower.endsWith(".md")) return "markdown_report";
  if (lower.endsWith(".csv")) return "csv_export";
  if (lower.endsWith(".json")) return "json_data";
  return "artifact";
}

function getArtifactKindLabel(kind) {
  if (kind === "dashboard_bundle") return "dashboard";
  if (kind === "markdown_report") return "markdown";
  if (kind === "csv_export") return "csv";
  if (kind === "json_data") return "json";
  return "artifact";
}

function fmtElapsed(startedAt) {
  if (!startedAt) return "";
  const sec = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  if (sec < 60) return `${sec}с`;
  return `${Math.floor(sec / 60)}м ${sec % 60}с`;
}

function renderProgressBar(status) {
  const wrap = el("div", "progress-wrap");
  const lbl = el("div", "progress-label");
  lbl.append(el("span", "", "Выполняется"));
  lbl.append(el("span", "progress-elapsed",
    `${fmtElapsed(status.started_at)} прошло · ${status.line_count || 0} строк лога`));
  const track = el("div", "progress-track");
  const fill = el("div", "progress-fill--indeterminate");
  track.append(fill);
  wrap.append(lbl, track);
  return wrap;
}

function toggleControlRoom() {
  controlRoomMode = !controlRoomMode;
  document.body.classList.toggle("ctrl-room", controlRoomMode);
  const btn = document.getElementById("ctrl-room-toggle");
  if (btn) btn.textContent = controlRoomMode ? "⊠ Развернуть" : "⊞ Фокус";
}

function getStatusTone(state) {
  if (state === "succeeded") return "good";
  if (state === "failed") return "bad";
  if (state === "running") return "warn";
  return "neutral";
}

function getStatusSummary(status) {
  if (!status) {
    return {
      tone: "neutral",
      title: "Нет активного запуска",
      text: "Открой job слева или запусти новый refresh, чтобы увидеть итог шага и следующие действия.",
    };
  }
  if (status.state === "succeeded") {
    return {
      tone: "good",
      title: "Шаг завершён успешно",
      text: "Проверь свежие артефакты ниже, затем открой связанный dashboard bundle и посмотри блок `Что Изменилось` перед тем как фиксировать follow-up задачи.",
    };
  }
  if (status.state === "failed") {
    return {
      tone: "bad",
      title: "Шаг завершился ошибкой",
      text: "Сначала разберись с логом и кодом возврата. Если причина неочевидна, сравни command, payload и последние сохранённые артефакты, затем повтори запуск или измени стратегию.",
    };
  }
  if (status.state === "running") {
    return {
      tone: "warn",
      title: "Шаг ещё выполняется",
      text: "Лог и прогресс обновляются автоматически. После `succeeded` здесь появятся свежие артефакты и прямые переходы к следующему шагу.",
    };
  }
  return {
    tone: "neutral",
    title: `Состояние: ${status.state || "unknown"}`,
    text: "Проверь лог запуска и сверь ожидаемый результат с фактическими артефактами.",
  };
}

function findDashboardMatch(indexPayload, artifact) {
  const fileName = String(artifact?.path || "").split("/").pop();
  if (!indexPayload || !fileName) return null;
  const items = indexPayload.items || indexPayload.reports || [];
  return items.find((item) => item.file_name === fileName) || null;
}

function openDashboardReport(fileName) {
  if (!fileName) return;
  localStorage.setItem(REPORT_STORAGE_KEY, fileName);
  window.location.href = "/";
}

function appendArtifactActions(card, artifact, dashboardMatch) {
  const actions = el("div", "job-actions");
  const openRaw = document.createElement("a");
  openRaw.className = "theme-toggle compact-button";
  openRaw.href = artifact.download_url;
  openRaw.target = "_blank";
  openRaw.rel = "noreferrer";
  openRaw.textContent = "Открыть файл";
  actions.append(actionControl(openRaw, "Открывает сам артефакт этого запуска: markdown, csv, json или bundle-файл."));

  if (dashboardMatch) {
    const openDashboard = el("button", "theme-toggle compact-button", "Открыть в дашборде");
    openDashboard.type = "button";
    openDashboard.addEventListener("click", () => openDashboardReport(dashboardMatch.file_name));
    actions.append(actionControl(openDashboard, "Открывает основной дашборд и сразу выбирает bundle, связанный с этим запуском."));
  }
  card.append(actions);
}

function renderArtifactSummary(card, artifact, dashboardMatch) {
  const meta = el("p", "job-card-text");
  const kind = dashboardMatch?.report_kind || getArtifactKind(artifact.path);
  meta.textContent = dashboardMatch
    ? `Связан с типом отчёта: ${dashboardMatch.report_kind}. Сгенерирован: ${formatDate(dashboardMatch.generated_at)}.`
    : `Тип артефакта: ${getArtifactKindLabel(kind)}.`;
  card.append(meta);

  if (dashboardMatch?.change_from_previous?.diffs) {
    const diffKeys = Object.keys(dashboardMatch.change_from_previous.diffs).slice(0, 3);
    const diffCard = el("p", "job-card-text");
    diffCard.textContent = diffKeys.length
      ? `Есть diff к предыдущему запуску: ${diffKeys.join(", ")}.`
      : "Есть сравнение с предыдущим запуском этого отчёта.";
    card.append(diffCard);
  } else if (dashboardMatch) {
    card.append(el("p", "job-card-text", "Для этого bundle можно сразу перейти в основной dashboard и проверить актуальные KPI и follow-up блоки."));
  } else {
    card.append(el("p", "job-card-text", artifact.path));
  }
}

async function renderResultSummary(status) {
  const root = document.getElementById("result-summary");
  root.innerHTML = "";
  const summary = getStatusSummary(status);
  const statusCard = el("div", "insight-card");
  statusCard.dataset.tone = summary.tone;
  statusCard.append(el("h3", "", summary.title), el("p", "", summary.text));

  if (status?.state === "failed") {
    const retryZone = el("div", "retry-zone");
    const retryBtn = el("button", "theme-toggle compact-button", "↩ Повторить");
    retryBtn.type = "button";
    retryBtn.addEventListener("click", async () => {
      const card = document.querySelector(`[data-job-key='${status.job_key}']`);
      if (!card) { alert("Карточка job не найдена. Попробуй запустить вручную из списка."); return; }
      retryBtn.disabled = true;
      try { await startJob(status.job_key, card); }
      catch (err) { alert(err.message); }
      finally { retryBtn.disabled = false; }
    });
    const hint = el("span", "retry-hint", "Рекомендуется подождать 30–60 с перед повтором. Если ошибка повторяется — проверь лог.");
    retryZone.append(retryBtn, hint);
    statusCard.append(retryZone);
  }

  root.append(statusCard);

  if (!status) return;
  if (status.job_payload && Object.keys(status.job_payload).length) {
    const payloadCard = el("div", "insight-card");
    payloadCard.append(el("h3", "", "Параметры шага"));
    const preview = Object.entries(status.job_payload)
      .slice(0, 4)
      .map(([key, value]) => `${key}: ${value}`)
      .join(" · ");
    payloadCard.append(el("p", "", preview || "Без параметров."));
    root.append(payloadCard);
  }

  const artifacts = status.artifacts || [];
  if (!artifacts.length) return;
  let indexPayload;
  try {
    indexPayload = await loadDashboardIndex();
  } catch {
    indexPayload = { items: [] };
  }
  artifacts.slice(0, 6).forEach((artifact) => {
    const dashboardMatch = findDashboardMatch(indexPayload, artifact);
    const card = el("div", "insight-card artifact-summary-card");
    card.dataset.tone = dashboardMatch ? "good" : "neutral";
    const header = el("div", "job-card-header");
    header.append(el("h3", "", artifact.label || artifact.path), el("span", "badge", dashboardMatch ? (dashboardMatch.report_kind || "dashboard") : getArtifactKindLabel(getArtifactKind(artifact.path))));
    card.append(header);
    renderArtifactSummary(card, artifact, dashboardMatch);
    appendArtifactActions(card, artifact, dashboardMatch);
    root.append(card);
  });
}

function renderWorkflow() {
  const root = document.getElementById("workflow-cards");
  [
    ["1. Подготовка", "Пишешь мне, я дорабатываю проект и говорю, какой refresh нужен."],
    ["2. Сетевой запуск", "Открываешь этот экран из подходящей сетевой сессии и запускаешь нужный online job."],
    ["3. Возврат к анализу", "После `succeeded` возвращаешься к анализу и продолжаешь работу со мной."],
  ].forEach(([title, text]) => {
    const card = el("div", "insight-card");
    card.append(el("h3", "", title), el("p", "", text));
    root.append(card);
  });
}

function decorateRefreshPanelInfos() {
  [
    ["#runner-control-title", "Здесь показывается самый важный оперативный слой: что сейчас выполняется, есть ли очередь и можно ли безопасно запускать следующую группу job."],
    ["#token-panel-title", "Токен нужен только для online job, которые ходят в MM API. Он хранится только в текущей сессии браузера."],
    ["#workflow-title", "Короткий операционный сценарий: открыть runner из подходящей сетевой сессии, обновить данные, дождаться завершения и вернуться в основной дашборд."],
    ["#jobs-panel-title", "Jobs разделены на online и offline группы. Online используют MM API, offline работают по уже сохранённым локальным файлам."],
    ["#run-panel-title", "Здесь живёт детальный статус последнего или текущего запуска. Если job завершился, здесь должен появиться итог, а не только running."],
    ["#runs-history-title", "История последних запусков на этой машине. Отсюда можно открыть любой завершённый или упавший run и посмотреть его лог."],
  ].forEach(([selector, text]) => attachInfoIconToHeading(selector, text));
}

function renderTokenMeta() {
  const root = document.getElementById("token-meta");
  root.innerHTML = "";
  const rows = !sharedToken
    ? [["Состояние", "Токен не задан"], ["Хранение", "Только в текущей вкладке браузера"]]
    : sharedTokenHealth
    ? [
        ["Состояние", sharedTokenHealth.token_health?.status === "valid" ? "Токен выглядит валидным" : "Токен не прошёл проверку"],
        ["Истекает", formatDate(sharedTokenHealth.token_health?.expires_at_moscow || sharedTokenHealth.token_health?.expires_at)],
        ["Осталось секунд", sharedTokenHealth.token_health?.seconds_left ?? "н/д"],
        ["UID", sharedTokenHealth.payload?.uid ?? "н/д"],
        ["Причина", sharedTokenHealth.error || "JWT декодирован успешно"],
      ]
    : [["Состояние", "Токен задан, но ещё не проверен"], ["Хранение", "Только в текущей вкладке браузера"]];
  rows.forEach(([label, value]) => {
    const card = el("div", "meta-item");
    card.append(el("span", "", label), el("strong", "", String(value)));
    root.append(card);
  });
}

function applySharedTokenToForms() {
  document.querySelectorAll("[data-field-name='token']").forEach((input) => {
    if (!input.value && sharedToken) {
      input.value = sharedToken;
    }
  });
}

function renderTokenToolbar() {
  const root = document.getElementById("token-toolbar");
  root.innerHTML = "";
  const wrap = el("div", "inline-form");
  const input = el("input", "inline-input");
  input.type = "password";
  input.placeholder = "Новый access token";
  input.value = sharedToken;
  input.style.minWidth = "360px";
  input.autocomplete = "off";
  input.spellcheck = false;

  const saveButton = el("button", "theme-toggle compact-button", "Сохранить и проверить");
  saveButton.type = "button";
  saveButton.addEventListener("click", async () => {
    const token = input.value.trim();
    if (!token) {
      alert("Сначала вставь access token.");
      return;
    }
    saveButton.disabled = true;
    try {
      const result = await validateToken(token);
      sharedToken = token;
      sharedTokenHealth = result;
      setStoredRefreshToken(sharedToken);
      applySharedTokenToForms();
      renderTokenMeta();
    } catch (error) {
      sharedToken = "";
      sharedTokenHealth = { error: error.message, token_health: { status: "invalid" }, payload: {} };
      setStoredRefreshToken("");
      applySharedTokenToForms();
      renderTokenMeta();
      alert(`Токен не прошёл проверку: ${error.message}`);
    } finally {
      saveButton.disabled = false;
    }
  });

  const checkButton = el("button", "theme-toggle compact-button", "Проверить токен");
  checkButton.type = "button";
  checkButton.addEventListener("click", async () => {
    const token = input.value.trim();
    if (!token) {
      alert("Сначала вставь access token.");
      return;
    }
    checkButton.disabled = true;
    try {
      const result = await validateToken(token);
      sharedTokenHealth = result;
      renderTokenMeta();
    } catch (error) {
      sharedTokenHealth = { error: error.message, token_health: { status: "invalid" }, payload: {} };
      renderTokenMeta();
      alert(`Токен не прошёл проверку: ${error.message}`);
    } finally {
      checkButton.disabled = false;
    }
  });

  const clearButton = el("button", "theme-toggle compact-button", "Очистить");
  clearButton.type = "button";
  clearButton.addEventListener("click", () => {
    sharedToken = "";
    sharedTokenHealth = null;
    setStoredRefreshToken("");
    input.value = "";
    document.querySelectorAll("[data-field-name='token']").forEach((field) => {
      field.value = "";
    });
    renderTokenMeta();
  });

  wrap.append(
    input,
    actionControl(saveButton, "Сохраняет токен в текущую сессию браузера только после успешной проверки JWT."),
    actionControl(checkButton, "Проверяет токен, но не сохраняет его в сессию."),
    actionControl(clearButton, "Удаляет токен из текущей сессии браузера и очищает поля в job-формах."),
  );
  root.append(wrap);
}

function renderQuickStatus(status = null) {
  const root = document.getElementById("quick-status-grid");
  if (!root) return;
  root.innerHTML = "";
  const queueLabel = queueRunning ? "очередь выполняется" : (queueItems.length ? "очередь собрана" : "очередь пуста");
  const rows = [
    ["Активный run", activeJobId || "нет"],
    ["Состояние", status?.state || "нет активного запуска"],
    ["Очередь", `${queueItems.length} в очереди · ${queueLabel}`],
    ["Пауза между job", `${Math.round(QUEUE_DELAY_MS / 1000)} сек`],
  ];
  rows.forEach(([label, value]) => {
    const card = el("div", "meta-item");
    card.append(el("span", "", label), el("strong", "", String(value)));
    root.append(card);
  });
}

function renderQueueToolbar() {
  const root = document.getElementById("queue-toolbar");
  if (!root) return;
  root.innerHTML = "";
  const copy = el("p", "job-card-text", "Групповой запуск идёт строго последовательно и с паузой между job. Это безопаснее для MM API, чем ручной частый клик по многим карточкам подряд.");
  const actions = el("div", "job-primary-actions");

  const runOnline = el("button", "theme-toggle compact-button", "Запустить online");
  runOnline.type = "button";
  runOnline.addEventListener("click", () => enqueueJobsByMode("online"));

  const runOffline = el("button", "theme-toggle compact-button", "Запустить offline");
  runOffline.type = "button";
  runOffline.addEventListener("click", () => enqueueJobsByMode("offline"));

  const runAll = el("button", "theme-toggle compact-button", "Запустить всё");
  runAll.type = "button";
  runAll.addEventListener("click", () => enqueueJobsByMode("all"));

  const stopQueue = el("button", "theme-toggle compact-button", "Остановить очередь");
  stopQueue.type = "button";
  stopQueue.addEventListener("click", () => {
    queueStopRequested = true;
    queueItems = [];
    renderQuickStatus();
  });

  actions.append(
    actionControl(runOnline, "Собирает в очередь только online jobs и запускает их строго последовательно с паузой."),
    actionControl(runOffline, "Собирает в очередь только offline jobs и запускает их по одному."),
    actionControl(runAll, "Собирает в общую очередь все доступные jobs. Используй это только когда действительно нужен полный прогон."),
    actionControl(stopQueue, "Очищает оставшуюся очередь. Уже запущенный job не убивает, но новые не стартуют."),
  );
  root.append(copy, actions);
}

function jobsByMode(mode) {
  if (mode === "all") return [...jobCatalog];
  return jobCatalog.filter((job) => String(job.mode || "").toLowerCase() === mode);
}

function enqueueJobsByMode(mode) {
  const jobs = jobsByMode(mode);
  if (!jobs.length) {
    alert("Для этой группы нет job.");
    return;
  }
  queueItems = jobs.map((job) => job.job_key);
  queueStopRequested = false;
  renderQuickStatus();
  void runQueue();
}

async function waitForJobTerminal(jobId) {
  while (true) {
    const payload = await loadJson(`/api/run?job_id=${encodeURIComponent(jobId)}`);
    renderRunMeta(payload.status);
    await renderResultSummary(payload.status);
    renderQuickStatus(payload.status);
    const log = document.getElementById("run-log");
    if (log) {
      log.textContent = payload.log || "Лог пока пуст.";
      log.scrollTop = log.scrollHeight;
    }
    if (payload.status?.state !== "running") {
      await refreshRuns();
      return payload.status;
    }
    await sleep(2000);
  }
}

async function runQueue() {
  if (queueRunning || !queueItems.length) return;
  queueRunning = true;
  renderQuickStatus();
  try {
    while (queueItems.length && !queueStopRequested) {
      const nextJobKey = queueItems.shift();
      const card = document.querySelector(`[data-job-key='${nextJobKey}']`);
      if (!card) continue;
      try {
        const status = await startJob(nextJobKey, card);
        renderQuickStatus(status);
        await waitForJobTerminal(status.job_id);
      } catch (error) {
        const log = document.getElementById("run-log");
        if (log) {
          log.textContent = `Очередь остановилась на ${nextJobKey}: ${error.message}`;
        }
      }
      renderQuickStatus();
      if (queueItems.length && !queueStopRequested) {
        await sleep(QUEUE_DELAY_MS);
      }
    }
  } finally {
    queueRunning = false;
    queueStopRequested = false;
    renderQuickStatus();
  }
}

function collectFormData(container) {
  const data = {};
  container.querySelectorAll("[data-field-name]").forEach((input) => {
    data[input.dataset.fieldName] = input.type === "checkbox" ? (input.checked ? "true" : "false") : input.value;
  });
  return data;
}

async function startJob(jobKey, container) {
  const tokenField = container.querySelector("[data-field-name='token']");
  if (tokenField && !tokenField.value && sharedToken) {
    tokenField.value = sharedToken;
  }
  if (tokenField) {
    const candidate = String(tokenField.value || "").trim();
    if (!candidate) {
      throw new Error("Для этого online job нужен access token. Вставь его в карточку job или задай в блоке 'Токен доступа'.");
    }
    const result = await validateToken(candidate);
    sharedToken = candidate;
    sharedTokenHealth = result;
    setStoredRefreshToken(sharedToken);
    renderTokenMeta();
  }
  const payload = await loadJson("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_key: jobKey, form_data: collectFormData(container) }),
  });
  activeJobId = payload.status.job_id;
  await refreshRuns();
  await refreshActiveRun();
  return payload.status;
}

function renderJobs(jobs) {
  const root = document.getElementById("jobs-grid");
  root.innerHTML = "";
  const groups = [
    {
      key: "online",
      title: "Online jobs",
      info: "Эти job ходят в MM API. Их лучше запускать из очереди с паузой, особенно если нужно прогнать несколько обновлений подряд.",
      rows: jobs.filter((job) => String(job.mode || "").toLowerCase() === "online"),
    },
    {
      key: "offline",
      title: "Offline jobs",
      info: "Эти job не стучатся в MM API и работают по уже сохранённым локальным данным. Их можно безопаснее запускать сериями.",
      rows: jobs.filter((job) => String(job.mode || "").toLowerCase() !== "online"),
    },
  ];
  groups.forEach((group) => {
    if (!group.rows.length) return;
    const wrap = el("section", "job-group");
    const heading = el("div", "job-group-header");
    const title = el("h3", "job-group-title", group.title);
    title.append(createInfoIcon(group.info));
    heading.append(title);
    wrap.append(heading);
    const grid = el("div", "jobs-grid");
    group.rows.forEach((job) => {
    const card = el("div", "job-card");
    card.dataset.jobKey = job.job_key;
    const header = el("div", "job-card-header");
    const badge = el("span", `badge badge-${job.mode}`, job.mode);
    const title = el("h3", "", job.title);
    title.append(createInfoIcon(job.description || "Описание job пока не заполнено."));
    header.append(title, badge);
    card.append(header, el("p", "job-card-text", job.description));
    const form = el("div", "job-form-grid");
    (job.fields || []).forEach((field) => {
      const label = el("label", "field");
      label.append(el("span", "", field.label));
      const input = document.createElement("input");
      input.dataset.fieldName = field.name;
      input.type = field.type === "checkbox" ? "checkbox" : (field.type || "text");
      if (field.type === "checkbox") {
        input.checked = String(field.default || "").toLowerCase() === "true";
      } else {
        input.value = field.default || "";
      }
      label.append(input);
      form.append(label);
    });
    card.append(form);
    const button = el("button", "theme-toggle", "Запустить");
    button.type = "button";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await startJob(job.job_key, card);
      } catch (error) {
        alert(error.message);
      } finally {
        button.disabled = false;
      }
    });
    card.append(actionControl(button, "Запускает только этот job. Если это online job, перед запуском проверяется токен."));
    grid.append(card);
    });
    wrap.append(grid);
    root.append(wrap);
  });
  applySharedTokenToForms();

  // Highlight targeted job card if deep-linked via ?job=
  if (window.__targetJobKey) {
    const target = document.querySelector(`[data-job-key='${window.__targetJobKey}']`);
    if (target) {
      target.classList.add("job-card--targeted");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    delete window.__targetJobKey;
  }
}

function renderRuns(runs) {
  const root = document.getElementById("runs-grid");
  root.innerHTML = "";
  runs.forEach((run) => {
    const card = el("div", "job-card");
    const header = el("div", "job-card-header");
    header.append(el("h3", "", `${run.job_key} · ${run.job_id}`), el("span", `badge badge-${run.state || "offline"}`, run.state || "unknown"));
    card.append(header);
    [
      `Запуск: ${formatDate(run.started_at)}`,
      `Завершение: ${formatDate(run.ended_at)}`,
      `Код: ${run.return_code ?? "н/д"}`,
      `Лог строк: ${run.line_count ?? 0}`,
      `Последний сигнал: ${run.progress_hint || "н/д"}`,
    ].forEach((line) => card.append(el("p", "job-card-text", line)));
    const open = el("button", "theme-toggle", "Открыть");
    open.type = "button";
    open.addEventListener("click", async () => {
      activeJobId = run.job_id;
      await refreshActiveRun();
    });
    card.append(actionControl(open, "Открывает лог и итог именно этого запуска в нижнем блоке страницы."));
    root.append(card);
  });
}

function renderRunMeta(status) {
  const root = document.getElementById("run-meta");
  root.innerHTML = "";
  if (!status) {
    const card = el("div", "meta-item");
    card.append(el("span", "", "Статус"), el("strong", "", "Нет активного запуска"));
    root.append(card);
    return;
  }
  [
    ["Job", status.job_key],
    ["ID", status.job_id],
    ["Статус", status.state],
    ["Старт", formatDate(status.started_at)],
    ["Финиш", formatDate(status.ended_at)],
    ["Код возврата", status.return_code ?? "н/д"],
    ["Лог строк", status.line_count ?? 0],
    ["Последний сигнал", status.progress_hint || "н/д"],
  ].forEach(([label, value]) => {
    const card = el("div", "meta-item");
    card.append(el("span", "", label), el("strong", "", String(value)));
    root.append(card);
  });
  if (status.state === "running") {
    const progressRow = el("div", "meta-item");
    progressRow.style.gridColumn = "1 / -1";
    progressRow.append(renderProgressBar(status));
    root.append(progressRow);
  }

  const artifactCard = el("div", "meta-item");
  artifactCard.append(el("span", "", "Артефакты"));
  const artifactCount = (status.artifacts || []).length;
  artifactCard.append(el("strong", "", artifactCount ? String(artifactCount) : "нет"));
  if (artifactCount) {
    const list = el("div", "artifact-list");
    (status.artifacts || []).slice(0, 8).forEach((artifact) => {
      const link = document.createElement("a");
      link.href = artifact.download_url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = artifact.label || artifact.path;
      list.append(link);
    });
    artifactCard.append(list);
  }
  root.append(artifactCard);
  renderQuickStatus(status);
}

async function refreshActiveRun() {
  const log = document.getElementById("run-log");
  if (!activeJobId) {
    renderRunMeta(null);
    await renderResultSummary(null);
    renderQuickStatus();
    log.textContent = "Нет активного запуска.";
    return;
  }
  let payload;
  try {
    payload = await loadJson(`/api/run?job_id=${encodeURIComponent(activeJobId)}`);
  } catch (e) {
    log.textContent = `Ошибка поллинга: ${e.message}`;
    return;
  }
  renderRunMeta(payload.status);
  await renderResultSummary(payload.status);
  log.textContent = payload.log || "Лог пока пуст.";
  log.scrollTop = log.scrollHeight;
  if (payload.status?.state === "running" && !queueRunning) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(async () => {
      await refreshRuns();
      await refreshActiveRun();
    }, 2000);
  }
}

async function refreshRuns() {
  const payload = await loadJson("/api/runs");
  renderRuns(payload.runs || []);
  if (!activeJobId && payload.runs?.length) {
    activeJobId = payload.runs[0].job_id;
  }
}

async function main() {
  initThemeToggle();
  decorateRefreshPanelInfos();
  document.getElementById("ctrl-room-toggle")?.addEventListener("click", toggleControlRoom);

  // Deep-link: ?job=<job_key> → scroll to and highlight the matching job card
  const targetJobKey = new URLSearchParams(window.location.search).get("job");
  if (targetJobKey) {
    // Jobs render asynchronously, so defer the highlight until after renderJobs
    window.__targetJobKey = targetJobKey;
  }
  sharedToken = getStoredRefreshToken();
  renderQueueToolbar();
  renderQuickStatus();
  renderTokenToolbar();
  renderTokenMeta();
  renderWorkflow();
  try {
    const jobs = await loadJson("/api/jobs");
    jobCatalog = jobs.jobs || [];
    renderJobs(jobs.jobs || []);
    await refreshRuns();
    await refreshActiveRun();
  } catch (error) {
    document.getElementById("jobs-grid").innerHTML = "";
    document.getElementById("run-meta").innerHTML = "";
    document.getElementById("run-log").textContent = [
      "Refresh runner недоступен.",
      "",
      "Что проверить:",
      "1. Запущен ли `web_refresh_server.py` на том порту, откуда открыта страница",
      "2. После обновления кода был ли перезапущен локальный web-сервер",
      "3. Подходит ли текущая сетевая сессия для запуска online jobs в MM",
      "",
      `Техническая ошибка: ${error.message}`,
    ].join("\n");
  }
}

main().catch((error) => {
  document.getElementById("run-log").textContent = error.message;
});
