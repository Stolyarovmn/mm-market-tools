/**
 * Quick Wins section — ported from ui_kits/dashboard/components.jsx.
 * ES-module, plain DOM (no JSX/React).
 */
import { el } from "./components.js";
import {
  loadQuickWins,
  loadQuickWinsState,
  completeQuickWin,
  restoreQuickWin,
  reorderQuickWins,
} from "./api.js";

// ---------------------------------------------------------------------------
// Time estimates — mirrors estimateMin() in ui_kits/dashboard/components.jsx
// ---------------------------------------------------------------------------
export function estimateMin({ kind, count }) {
  switch (kind) {
    case "reorder":             return Math.max(2, Math.round(count * 0.3));
    case "markdown":            return Math.max(3, Math.round(count * 0.6));
    case "reviews":             return count * 2;
    case "questions":           return count * 3;
    case "run_job":             return 6;
    case "title_seo":           return Math.max(2, count * 1);
    case "price_trap":          return Math.max(2, Math.round(count * 0.5));
    case "watchlist":           return Math.max(2, Math.round(count * 0.3));
    case "high_views_low_conv": return Math.max(5, count * 3);
    case "zero_views":          return Math.max(3, Math.round(count * 0.5));
    case "run_fetch_stats":     return 4;
    default:                    return 5;
  }
}

export function impactText({ kind, count }) {
  switch (kind) {
    case "reorder":             return `${count} SKU могут уйти в ноль без закупки`;
    case "markdown":            return `${count} stale карточек тянут полку`;
    case "reviews":             return `${count} отзыва без ответа`;
    case "questions":           return `${count} вопрос покупателя без ответа`;
    case "run_job":             return "Свежие данные за неделю";
    case "title_seo":           return `${count} слабых title — теряют CTR`;
    case "price_trap":          return `${count} SKU чуть выше психопорогов 199/299/499`;
    case "watchlist":           return `${count} карточек ждут проверки`;
    case "high_views_low_conv": return `${count} товаров: есть трафик, но конверсия < 1.5%`;
    case "zero_views":          return `${count} активных товаров без единого просмотра`;
    case "run_fetch_stats":     return "Данные по просмотрам и конверсии ещё не загружены";
    default:                    return "";
  }
}

// ---------------------------------------------------------------------------
// Button action handler
// ---------------------------------------------------------------------------
function resolveAction(win) {
  const route = win.route || "";
  if (route.startsWith("refresh:")) {
    const jobName = route.slice("refresh:".length);
    return () => { window.location.href = `/refresh.html?target=${encodeURIComponent(jobName)}`; };
  }
  if (route === "buyer_reviews" || route === "buyer-reviews-panel") {
    return () => {
      const panel = document.getElementById("buyer-reviews-panel");
      if (panel) {
        panel.scrollIntoView({ behavior: "smooth" });
        const first = panel.querySelector("textarea");
        if (first) setTimeout(() => first.focus(), 400);
      }
    };
  }
  if (route === "action-center-panel") {
    return () => {
      const panel = document.getElementById("action-center-panel");
      if (panel) panel.scrollIntoView({ behavior: "smooth" });
    };
  }
  return () => {
    const panel = document.getElementById(route) || document.querySelector(`[data-route="${route}"]`);
    if (panel) {
      panel.scrollIntoView({ behavior: "smooth" });
      panel.classList.add("panel-pulse");
      panel.addEventListener("animationend", () => panel.classList.remove("panel-pulse"), { once: true });
    }
  };
}

// ---------------------------------------------------------------------------
// QuickWinCard — matches reference components.jsx QuickWinCard
// ---------------------------------------------------------------------------
function buildQuickWinCard(win, { done, onComplete, onRestore, draggable }) {
  const mins = estimateMin(win);
  const card = el("div", "kpi-card quick-win-card" + (done ? " qw-done" : ""));
  card.dataset.winId = win.id;
  card.dataset.kind = win.kind;
  // Card layout matches reference: display:grid, gap:8
  card.style.cssText = [
    "position:relative",
    "display:grid",
    "gap:8px",
    `opacity:${done ? "0.55" : "1"}`,
    `cursor:${draggable && !done ? "grab" : "default"}`,
    "outline:none",
    "transition:outline 120ms ease,opacity 120ms ease",
  ].join(";");
  if (draggable && !done) card.draggable = true;

  // 1. Drag handle (only when draggable and not done)
  if (draggable && !done) {
    const handle = el("span", "");
    handle.setAttribute("aria-hidden", "true");
    handle.title = "Перетащите для смены приоритета";
    handle.style.cssText = "position:absolute;top:10px;right:10px;color:var(--muted);font-size:16px;line-height:1;letter-spacing:-0.2em;pointer-events:none;user-select:none";
    handle.textContent = "⋮⋮";
    card.appendChild(handle);
  }

  // 2. Label row: label span + minutes badge (FIRST per reference)
  const labelRow = el("div", "label-row");
  const labelSpan = el("span", "");
  labelSpan.style.cssText = `color:var(--muted);font-size:13px;text-decoration:${done ? "line-through" : "none"}`;
  labelSpan.textContent = win.label;
  const minBadge = el("span", "badge badge-online");
  minBadge.style.cssText = "padding:4px 8px;font-size:11px;white-space:nowrap";
  minBadge.textContent = `~${mins} мин`;
  labelRow.appendChild(labelSpan);
  labelRow.appendChild(minBadge);
  card.appendChild(labelRow);

  // 3. Count — large numeric (SECOND per reference)
  const countEl = el("strong", "");
  countEl.style.cssText = "font-size:28px;font-variant-numeric:tabular-nums;letter-spacing:-0.03em";
  countEl.textContent = String(win.count ?? "");
  card.appendChild(countEl);

  // 4. Impact text
  const impact = el("p", "");
  impact.style.cssText = "margin:0;color:var(--muted);font-size:13px;line-height:1.45";
  impact.textContent = impactText(win);
  card.appendChild(impact);

  // 5. Action buttons in grid
  if (!done) {
    const actionsGrid = el("div", "");
    actionsGrid.style.cssText = "display:grid;gap:6px;margin-top:4px";

    const openBtn = el("button", "theme-toggle compact-button", win.action);
    openBtn.style.cssText = "text-decoration:none;text-align:center";
    openBtn.addEventListener("click", resolveAction(win));
    actionsGrid.appendChild(openBtn);

    const doneBtn = el("button", "mini-action-button secondary", "✓ Готово");
    doneBtn.style.textAlign = "center";
    doneBtn.addEventListener("click", onComplete);
    actionsGrid.appendChild(doneBtn);

    card.appendChild(actionsGrid);
  } else {
    const restoreBtn = el("button", "theme-toggle compact-button", "↺ Вернуть в очередь");
    restoreBtn.style.cssText = "margin-top:4px;text-decoration:none;text-align:center";
    restoreBtn.addEventListener("click", onRestore);
    card.appendChild(restoreBtn);
  }

  return card;
}

// ---------------------------------------------------------------------------
// QuickWinsSection — top-level render
// ---------------------------------------------------------------------------
let _state = null;        // { done_ids, custom_order, version }
let _backlog = null;      // raw items from quick_wins_<date>.json
let _date = null;
let _container = null;
let _expandedPanel = null; // separate sibling section.panel for expanded list
let _expanded = false;
let _dragState = { dragId: null, overId: null };
let _reorderTimer = null;

function _isCustomOrder() {
  return _state && _state.custom_order && _state.custom_order.length > 0;
}

function _ordered() {
  if (!_backlog) return [];
  if (!_isCustomOrder()) return [..._backlog];
  const orderMap = {};
  _state.custom_order.forEach((id, i) => { orderMap[id] = i; });
  return [..._backlog].sort((a, b) => {
    const ia = orderMap[a.id] ?? 9999;
    const ib = orderMap[b.id] ?? 9999;
    return ia - ib;
  });
}

function _doneSet() {
  return new Set((_state && _state.done_ids) || []);
}

export function renderQuickWinsSection(container, date) {
  _container = container;
  _date = date || new Date().toISOString().slice(0, 10);
  container.innerHTML = '<p class="empty-state">Загрузка быстрых действий…</p>';

  Promise.all([
    loadQuickWins(_date).catch(() => null),
    loadQuickWinsState(_date).catch(() => null),
  ]).then(([backlogData, stateData]) => {
    _backlog = (backlogData && backlogData.items) || [];
    _state = (stateData && stateData.state) || { done_ids: [], custom_order: [], version: 0 };
    _redraw();
  });
}

function _redraw() {
  if (!_container) return;
  _container.innerHTML = "";

  const ordered = _ordered();
  const doneSet = _doneSet();
  const active = ordered.filter((i) => !doneSet.has(i.id));
  const done = ordered.filter((i) => doneSet.has(i.id));
  const visible = active.slice(0, 4);
  const moreActive = active.length - visible.length;
  const totalMin = visible.reduce((s, w) => s + estimateMin(w), 0);
  const isCustomOrder = _isCustomOrder();

  const allDone = visible.length === 0;
  const subtitle = allDone
    ? "Всё закрыто за сессию. Можно проверить полный список ниже или открыть полный режим."
    : `${visible.length} ${visible.length === 1 ? "действие" : "действия"} в очереди — примерно ${totalMin} мин на всё.`;

  // Header
  const header = el("div", "panel-header");
  header.appendChild(el("h2", "", "Сейчас — быстрые действия"));
  header.appendChild(el("p", "", subtitle));
  _container.appendChild(header);

  // Top 4 cards (or done-state)
  if (allDone) {
    const card = el("div", "insight-card");
    card.dataset.tone = "good";
    card.appendChild(el("h3", "", "Цикл закрыт"));
    card.appendChild(el("p", "", "Все быстрые действия за эту сессию выполнены. Если что-то нажал случайно — открой «Все действия» ниже и верни в очередь."));
    _container.appendChild(card);
  } else {
    const grid = el("div", "kpi-grid");
    visible.forEach((win) => {
      const card = buildQuickWinCard(win, {
        done: false,
        onComplete: () => _handleComplete(win.id),
        onRestore: () => _handleRestore(win.id),
        draggable: false,
      });
      grid.appendChild(card);
    });
    _container.appendChild(grid);
  }

  // Footer strip — only show if there's something to show
  const doneCount = (_backlog ? _backlog.length : 0) - active.length;
  if (moreActive > 0 || doneCount > 0 || isCustomOrder) {
    const footer = el("div", "qw-footer");
    footer.style.cssText = "border-top:1px solid var(--line);padding-top:14px;margin-top:14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap";

    if (moreActive > 0) {
      const moreEl = el("span", "");
      moreEl.style.cssText = "color:var(--muted);font-size:13px";
      moreEl.innerHTML = `Ещё доступно: <strong style="color:var(--ink)">${moreActive}</strong>`;
      footer.appendChild(moreEl);
    }

    if (doneCount > 0) {
      const doneEl = el("span", "");
      doneEl.style.cssText = "color:var(--good,#4caf50);font-size:13px";
      doneEl.innerHTML = `Готово за сессию: <strong>${doneCount}</strong>`;
      footer.appendChild(doneEl);
    }

    if (isCustomOrder) {
      const customEl = el("span", "");
      customEl.style.cssText = "color:var(--accent);font-size:13px";
      customEl.textContent = "Порядок изменён вручную";
      footer.appendChild(customEl);
    }

    const expandBtn = _buildExpandBtn(ordered, doneSet, isCustomOrder);
    expandBtn.style.marginLeft = "auto";
    footer.appendChild(expandBtn);
    _container.appendChild(footer);
  } else {
    const expandWrap = el("div", "");
    expandWrap.style.marginTop = "14px";
    expandWrap.appendChild(_buildExpandBtn(ordered, doneSet, isCustomOrder));
    _container.appendChild(expandWrap);
  }

  // If expanded panel is open, refresh it with updated state
  if (_expanded) _syncExpandedPanel(ordered, doneSet, isCustomOrder);
}

function _buildExpandBtn(ordered, doneSet, isCustomOrder) {
  const btn = el("button", "theme-toggle compact-button",
    _expanded ? "Свернуть" : "Показать все действия за цикл");
  btn.style.textDecoration = "none";
  btn.addEventListener("click", () => {
    _expanded = !_expanded;
    btn.textContent = _expanded ? "Свернуть" : "Показать все действия за цикл";
    _syncExpandedPanel(ordered, doneSet, isCustomOrder);
  });
  return btn;
}

function _syncExpandedPanel(ordered, doneSet, isCustomOrder) {
  if (!_container) return;
  if (!_expanded) {
    if (_expandedPanel) { _expandedPanel.remove(); _expandedPanel = null; }
    return;
  }
  if (!_expandedPanel) {
    _expandedPanel = document.createElement("section");
    _expandedPanel.className = "panel";
    // Insert immediately after the quick-wins-panel
    const qwPanel = _container.closest(".panel") || _container.parentElement;
    if (qwPanel && qwPanel.nextSibling) {
      qwPanel.parentElement.insertBefore(_expandedPanel, qwPanel.nextSibling);
    } else if (qwPanel) {
      qwPanel.parentElement.appendChild(_expandedPanel);
    }
  }
  _renderExpandPanel(_expandedPanel, ordered, doneSet, isCustomOrder);
}

function _renderExpandPanel(panel, ordered, doneSet, isCustomOrder) {
  panel.innerHTML = "";

  const header = el("div", "panel-header");
  header.appendChild(el("h2", "", `Все действия за цикл — ${ordered.length}`));
  header.appendChild(el("p", "", "Перетащи карточку, чтобы поднять её в строку наверху. Готовые можно вернуть в очередь."));
  panel.appendChild(header);

  if (isCustomOrder) {
    const resetWrap = el("div", "");
    resetWrap.style.marginBottom = "14px";
    const resetBtn = el("button", "theme-toggle compact-button", "↺ Сбросить к приоритету из данных");
    resetBtn.style.textDecoration = "none";
    resetBtn.addEventListener("click", () => { _handleReorder([]); });
    resetWrap.appendChild(resetBtn);
    panel.appendChild(resetWrap);
  }

  const grid = el("div", "kpi-grid");
  ordered.forEach((win) => {
    const isDone = doneSet.has(win.id);
    const card = buildQuickWinCard(win, {
      done: isDone,
      onComplete: () => _handleComplete(win.id),
      onRestore: () => _handleRestore(win.id),
      draggable: !isDone,
    });
    if (!isDone) _attachDrag(card, win.id, grid);
    grid.appendChild(card);
  });
  panel.appendChild(grid);
}

// ---------------------------------------------------------------------------
// Drag & Drop
// ---------------------------------------------------------------------------
function _attachDrag(card, id, list) {
  card.addEventListener("dragstart", (e) => {
    _dragState.dragId = id;
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", id); } catch (_) { /* IE */ }
    card.style.opacity = "0.4";
  });
  card.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    _dragState.overId = id;
    card.style.outline = "2px solid var(--accent)";
    card.style.outlineOffset = "4px";
  });
  card.addEventListener("dragleave", () => {
    _dragState.overId = null;
    card.style.outline = "";
    card.style.outlineOffset = "";
  });
  card.addEventListener("drop", (e) => {
    e.preventDefault();
    const src = _dragState.dragId;
    _dragState = { dragId: null, overId: null };
    card.style.outline = "";
    if (!src || src === id) return;
    const cards = [...list.querySelectorAll("[data-win-id]")];
    const ids = cards.map((c) => c.dataset.winId);
    const srcIdx = ids.indexOf(src);
    const dstIdx = ids.indexOf(id);
    if (srcIdx < 0 || dstIdx < 0) return;
    const next = [...ids];
    next.splice(srcIdx, 1);
    next.splice(dstIdx, 0, src);
    clearTimeout(_reorderTimer);
    _reorderTimer = setTimeout(() => _handleReorder(next), 300);
  });
  card.addEventListener("dragend", () => {
    _dragState = { dragId: null, overId: null };
    card.style.opacity = "";
    card.style.outline = "";
    card.style.outlineOffset = "";
  });
}

// ---------------------------------------------------------------------------
// State mutations with optimistic updates
// ---------------------------------------------------------------------------
async function _handleComplete(id) {
  const prev = JSON.stringify(_state);
  _state.done_ids = [...(_state.done_ids || [])];
  if (!_state.done_ids.includes(id)) _state.done_ids.push(id);
  _redraw();
  try {
    const res = await completeQuickWin(id, _date);
    if (res && res.state) _state = res.state;
    _redraw();
  } catch (_) {
    _state = JSON.parse(prev);
    _redraw();
    _showError("Не удалось отметить как выполнено. Попробуй ещё раз.");
  }
}

async function _handleRestore(id) {
  const prev = JSON.stringify(_state);
  _state.done_ids = (_state.done_ids || []).filter((x) => x !== id);
  _redraw();
  try {
    const res = await restoreQuickWin(id, _date);
    if (res && res.state) _state = res.state;
    _redraw();
  } catch (_) {