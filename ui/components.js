let activeInfoWrap = null;
let overlayNode = null;
let overlayTextNode = null;

function ensureInfoOverlay() {
  if (overlayNode && overlayTextNode) {
    return { overlayNode, overlayTextNode };
  }
  overlayNode = document.createElement("div");
  overlayNode.className = "info-overlay";
  overlayNode.hidden = true;

  const body = document.createElement("div");
  body.className = "info-overlay-body";
  overlayTextNode = document.createElement("div");
  overlayTextNode.className = "info-overlay-text";
  body.append(overlayTextNode);
  overlayNode.append(body);
  document.body.append(overlayNode);
  return { overlayNode, overlayTextNode };
}

function closeActiveInfo() {
  if (activeInfoWrap) {
    delete activeInfoWrap.dataset.open;
    delete activeInfoWrap.dataset.pinned;
    activeInfoWrap.querySelector(".info-icon")?.setAttribute("aria-expanded", "false");
  }
  const { overlayNode: node } = ensureInfoOverlay();
  node.hidden = true;
  node.style.removeProperty("top");
  node.style.removeProperty("left");
  activeInfoWrap = null;
}

function positionOverlay(button) {
  const { overlayNode: node } = ensureInfoOverlay();
  const rect = button.getBoundingClientRect();
  const margin = 12;
  const maxWidth = Math.min(360, window.innerWidth - margin * 2);
  node.style.maxWidth = `${maxWidth}px`;
  node.hidden = false;

  const overlayRect = node.getBoundingClientRect();
  let left = rect.left + rect.width / 2 - overlayRect.width / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - overlayRect.width - margin));

  let top = rect.top - overlayRect.height - margin;
  if (top < margin) {
    top = Math.min(window.innerHeight - overlayRect.height - margin, rect.bottom + margin);
  }

  node.style.left = `${left + window.scrollX}px`;
  node.style.top = `${top + window.scrollY}px`;
}

function openInfo(wrap) {
  const button = wrap.querySelector(".info-icon");
  const text = wrap.dataset.infoText || "";
  const { overlayNode: node, overlayTextNode: textNode } = ensureInfoOverlay();
  if (!button || !text) return;
  if (activeInfoWrap && activeInfoWrap !== wrap) {
    closeActiveInfo();
  }
  activeInfoWrap = wrap;
  wrap.dataset.open = "true";
  button.setAttribute("aria-expanded", "true");
  textNode.textContent = text;
  node.hidden = false;
  positionOverlay(button);
}

function toggleInfoPin(wrap) {
  if (activeInfoWrap === wrap && wrap.dataset.pinned === "true") {
    closeActiveInfo();
    return;
  }
  wrap.dataset.pinned = "true";
  openInfo(wrap);
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".info-icon");
  if (button) {
    event.preventDefault();
    event.stopPropagation();
    toggleInfoPin(button.closest(".info-wrap"));
    return;
  }
  if (!event.target.closest(".info-overlay")) {
    closeActiveInfo();
  }
});

document.addEventListener("mouseover", (event) => {
  const button = event.target.closest(".info-icon");
  if (!button) return;
  const wrap = button.closest(".info-wrap");
  if (!wrap || wrap.dataset.pinned === "true") return;
  openInfo(wrap);
});

document.addEventListener("mouseout", (event) => {
  const wrap = event.target.closest(".info-wrap");
  if (!wrap || wrap.dataset.pinned === "true") return;
  const next = event.relatedTarget;
  if (next && wrap.contains(next)) return;
  if (activeInfoWrap === wrap) {
    closeActiveInfo();
  }
});

document.addEventListener("focusin", (event) => {
  const button = event.target.closest(".info-icon");
  if (!button) return;
  openInfo(button.closest(".info-wrap"));
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeActiveInfo();
  }
});

window.addEventListener("scroll", () => {
  if (!activeInfoWrap) return;
  const button = activeInfoWrap.querySelector(".info-icon");
  if (button) positionOverlay(button);
}, { passive: true });

window.addEventListener("resize", () => {
  if (!activeInfoWrap) return;
  const button = activeInfoWrap.querySelector(".info-icon");
  if (button) positionOverlay(button);
}, { passive: true });

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function createInfoIcon(text) {
  const wrap = el("span", "info-wrap");
  wrap.dataset.infoText = text || "";
  const button = el("button", "info-icon", "i");
  button.type = "button";
  button.setAttribute("aria-label", "Пояснение");
  button.setAttribute("aria-expanded", "false");
  button.title = "Показать пояснение";
  wrap.append(button);
  return wrap;
}

export function appendHeadingWithInfo(container, tag, title, infoText) {
  const heading = el(tag, "heading-with-info");
  heading.append(el("span", "", title));
  if (infoText) {
    heading.append(createInfoIcon(infoText));
  }
  container.append(heading);
  return heading;
}

export function appendValueWithOptionalInfo(container, value, infoText) {
  const row = el("div", "value-row");
  row.append(el("strong", "", String(value)));
  if (infoText && infoText !== value) {
    row.append(createInfoIcon(infoText));
  }
  container.append(row);
}

export function renderActionCard({ root, title, subtitle, rows, formatter, getDisplayTitle, createEntityActionButtons }) {
  root.innerHTML = "";
  const card = el("div", "list-card");
  appendHeadingWithInfo(card, "h3", title, subtitle);
  card.append(el("p", "", subtitle));
  if (!rows.length) {
    card.append(el("p", "empty-state", "Нет данных для этого блока."));
    root.append(card);
    return;
  }
  const list = el("ul", "compact-list");
  rows.forEach((row) => {
    const item = el("li");
    const content = el("div", "list-item-main");
    content.append(el("strong", "", getDisplayTitle(row)));
    content.append(el("span", "", formatter(row)));
    item.append(content);
    item.append(createEntityActionButtons(row, title));
    list.append(item);
  });
  card.append(list);
  root.append(card);
}

export function renderTableCard({ root, title, rows, formatter, infoText, getDisplayTitle, createEntityActionButtons }) {
  root.innerHTML = "";
  const card = el("div", "table-card");
  appendHeadingWithInfo(card, "h3", title, infoText);
  if (!rows.length) {
    card.append(el("p", "empty-state", "Нет данных для этого блока."));
    root.append(card);
    return;
  }
  const table = el("div", "mini-table");
  rows.slice(0, 8).forEach((row) => {
    const item = el("div", "mini-row");
    const content = el("div", "list-item-main");
    content.append(el("strong", "", getDisplayTitle(row)));
    content.append(el("span", "", formatter(row)));
    item.append(content);
    item.append(createEntityActionButtons(row, title));
    table.append(item);
  });
  card.append(table);
  root.append(card);
}

export function renderBarChart(title, rows, valueFormatter, infoText = "") {
  const card = el("div", "chart-card");
  appendHeadingWithInfo(card, "h3", title, infoText);
  if (!rows.length) {
    card.append(el("p", "", "Нет данных"));
    return card;
  }
  const bars = el("div", "bars");
  const max = Math.max(...rows.map((row) => row.value ?? row.count ?? 0), 1);
  rows.forEach((row) => {
    const value = row.value ?? row.count ?? 0;
    const barRow = el("div", "bar-row");
    barRow.append(el("span", "", row.key));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    fill.style.width = `${(value / max) * 100}%`;
    track.append(fill);
    barRow.append(track);
    barRow.append(el("strong", "", valueFormatter(value)));
    bars.append(barRow);
  });
  card.append(bars);
  return card;
}

export function deltaClass(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "neutral";
  if (value > 0) return "good";
  if (value < 0) return "bad";
  return "warn";
}

export function renderCompareCard(root, title, mainValue, subtitle, deltaValue, deltaLabel) {
  const card = el("div", "compare-card");
  card.append(el("span", "badge", title));
  card.append(el("strong", "", mainValue));
  card.append(el("p", "", subtitle));
  const delta = el("div", `delta ${deltaClass(deltaValue)}`, `${deltaLabel}: ${deltaValue === null || deltaValue === undefined || Number.isNaN(deltaValue) ? "н/д" : `${deltaValue > 0 ? "+" : ""}${deltaValue}%`}`);
  card.append(delta);
  root.append(card);
}

export function renderTrendCard(root, title, rows, valueKey, formatter) {
  const card = el("div", "sparkline-card");
  card.append(el("h3", "", title));
  if (!rows.length) {
    card.append(el("p", "", "Нет данных"));
    root.append(card);
    return;
  }
  const spark = el("div", "sparkline");
  const max = Math.max(...rows.map((row) => Number(row[valueKey] || 0)), 1);
  rows.forEach((row) => {
    const value = Number(row[valueKey] || 0);
    const bar = el("div", "spark-bar");
    const column = el("div", "spark-column");
    column.style.height = `${Math.max(10, (value / max) * 180)}px`;
    bar.append(column);
    bar.append(el("span", "", formatter(value)));
    bar.append(el("span", "", (row["Sales.created_at.month"] || "").slice(0, 7)));
    spark.append(bar);
  });
  card.append(spark);
  root.append(card);
}
