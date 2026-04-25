async function loadSnapshot() {
  const response = await fetch("./process_snapshot.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function itemCard(item, extra = "") {
  const chips = (item.labels || []).map((label) => `<span class="chip">${label}</span>`).join("");
  return `
    <article class="item">
      <div class="item-top">
        <div>
          <div class="item-title"><a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a></div>
          <div class="item-meta">${item.meta || ""}</div>
        </div>
      </div>
      ${extra}
      ${chips ? `<div class="chips">${chips}</div>` : ""}
    </article>
  `;
}

function renderSummary(summary) {
  const root = document.getElementById("summary-grid");
  const cards = [
    ["Open tasks", summary.open_tasks],
    ["Review queue", summary.review_queue],
    ["Open disputes", summary.open_disputes],
    ["Open PRs", summary.open_prs],
    ["Failed workflows", summary.failed_workflows],
    ["Warnings", summary.warning_count],
  ];
  root.innerHTML = cards.map(([label, value]) => `
    <section class="summary-card">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
    </section>
  `).join("");
}

function renderList(id, items, formatter) {
  const root = document.getElementById(id);
  if (!items.length) {
    root.innerHTML = '<div class="empty">Пока пусто.</div>';
    return;
  }
  root.innerHTML = items.map(formatter).join("");
}

function renderLinks(meta) {
  document.getElementById("new-task-link").href = meta.new_task_url;
  document.getElementById("new-dispute-link").href = meta.new_dispute_url;
  document.getElementById("project-link").href = meta.project_url;
}

function formatWorkflow(run) {
  const statusClass = run.conclusion === "success" ? "ok" : (run.conclusion === "failure" ? "danger" : "warn");
  return itemCard(run, `<div class="chips"><span class="chip ${statusClass}">${run.conclusion || run.status || "unknown"}</span></div>`);
}

async function main() {
  try {
    const snapshot = await loadSnapshot();
    renderSummary(snapshot.summary);
    renderLinks(snapshot.meta);
    renderList("tasks-list", snapshot.tasks, itemCard);
    renderList("audit-list", snapshot.review_queue, itemCard);
    renderList("disputes-list", snapshot.disputes, itemCard);
    renderList("prs-list", snapshot.pull_requests, itemCard);
    renderList("workflows-list", snapshot.workflows, formatWorkflow);
    renderList("memory-list", snapshot.memory_docs, itemCard);
    renderList("warnings-list", snapshot.warnings, (warning) => `
      <article class="item">
        <div class="item-title">${warning.title}</div>
        <div class="item-meta">${warning.body}</div>
      </article>
    `);
  } catch (error) {
    document.body.innerHTML = `<main class="page"><section class="panel"><h1>Process View</h1><p class="empty">Не удалось загрузить process snapshot: ${error.message}</p></section></main>`;
  }
}

main();

