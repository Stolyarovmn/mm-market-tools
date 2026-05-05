export const DASHBOARD_INDEX_URL = "../data/dashboard/index.json";
export const ENTITY_HISTORY_INDEX_URL = "../data/local/entity_history_index.json";
export const THEME_STORAGE_KEY = "mm-market-tools-theme";

function buildRunnerCandidates() {
  const host = window.location.hostname || "127.0.0.1";
  const candidates = [
    window.location.origin,
    `http://${host}:8040`,
    "http://127.0.0.1:8040",
    "http://localhost:8040",
  ];
  return [...new Set(candidates)];
}

export function actionCenterUrl(path = "/api/action-center") {
  return buildRunnerCandidates().map((base) => `${base}${path}`);
}

export async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

export async function fetchJsonWithFallback(urls, options) {
  let lastError = null;
  for (const url of urls) {
    try {
      return await fetchJson(url, options);
    } catch (error) {
      lastError = error;
    }
  }
  const message = lastError?.message || "Runner API unavailable";
  throw new Error(
    `Action Center / runner недоступен. Проверь, что запущен web_refresh_server.py на :8040 и после обновления кода он был перезапущен. Техническая ошибка: ${message}`
  );
}

export async function loadDashboardIndex() {
  return fetchJson(DASHBOARD_INDEX_URL);
}

export async function loadEntityHistoryIndex() {
  return fetchJson(ENTITY_HISTORY_INDEX_URL);
}

export async function loadLocalCogsStore() {
  return fetchJson("../data/local/cogs_overrides.json");
}

export async function loadActionCenter() {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center"));
}

export async function addWatchlistItem(payload) {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center/watchlist"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function addActionItem(payload) {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center/action"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function acknowledgeEntity(payload) {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center/acknowledge"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateActionItem(payload) {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center/action/update"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function toggleActionItem(id) {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center/toggle"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
}

export async function saveActionView(payload) {
  return fetchJsonWithFallback(actionCenterUrl("/api/action-center/view"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function loadRunnerJobs() {
  return fetchJsonWithFallback(actionCenterUrl("/api/jobs"));
}

export async function loadRunnerRuns() {
  return fetchJsonWithFallback(actionCenterUrl("/api/runs"));
}

export async function loadRunnerRun(jobId) {
  return fetchJsonWithFallback(actionCenterUrl(`/api/run?job_id=${encodeURIComponent(jobId)}`));
}

export async function startRunnerJob(jobKey, formData = {}) {
  return fetchJsonWithFallback(actionCenterUrl("/api/run"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_key: jobKey, form_data: formData }),
  });
}

export async function validateRunnerToken(token) {
  return fetchJsonWithFallback(actionCenterUrl("/api/token-health"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}
