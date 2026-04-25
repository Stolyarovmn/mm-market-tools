export const THEME_STORAGE_KEY = "mm-market-tools-theme";
export const REPORT_STORAGE_KEY = "mm-market-tools-last-report";
export const ACTION_OWNER_STORAGE_KEY = "mm-market-tools-action-owner";
export const ACTION_FILTER_STORAGE_KEY = "mm-market-tools-action-filter";
export const REFRESH_TOKEN_STORAGE_KEY = "mm-market-tools-refresh-token";

export function getStoredTheme() {
  return localStorage.getItem(THEME_STORAGE_KEY) || "light";
}

export function setStoredTheme(theme) {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

export function applyTheme(theme) {
  document.body.dataset.theme = theme;
  const label = document.getElementById("theme-toggle-label");
  const button = document.getElementById("theme-toggle");
  if (label) {
    label.textContent = theme === "dark" ? "☀" : "☾";
  }
  if (button) {
    button.title = theme === "dark" ? "Светлая тема" : "Тёмная тема";
  }
}

export function initThemeToggle(buttonId = "theme-toggle") {
  applyTheme(getStoredTheme());
  const button = document.getElementById(buttonId);
  if (!button) return;
  button.addEventListener("click", () => {
    const nextTheme = document.body.dataset.theme === "dark" ? "light" : "dark";
    setStoredTheme(nextTheme);
    applyTheme(nextTheme);
  });
}

export function getStoredReportSelection() {
  return localStorage.getItem(REPORT_STORAGE_KEY) || "";
}

export function setStoredReportSelection(fileName) {
  if (fileName) {
    localStorage.setItem(REPORT_STORAGE_KEY, fileName);
  }
}

export function getStoredActionOwner() {
  return localStorage.getItem(ACTION_OWNER_STORAGE_KEY) || "";
}

export function setStoredActionOwner(owner) {
  localStorage.setItem(ACTION_OWNER_STORAGE_KEY, owner || "");
}

export function getStoredActionFilter() {
  return localStorage.getItem(ACTION_FILTER_STORAGE_KEY) || "all";
}

export function setStoredActionFilter(filterValue) {
  localStorage.setItem(ACTION_FILTER_STORAGE_KEY, filterValue || "all");
}

export function getStoredRefreshToken() {
  return sessionStorage.getItem(REFRESH_TOKEN_STORAGE_KEY) || "";
}

export function setStoredRefreshToken(token) {
  if (token) {
    sessionStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
    return;
  }
  sessionStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
}
