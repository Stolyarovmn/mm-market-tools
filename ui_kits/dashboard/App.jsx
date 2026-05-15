// MM Market Tools — Dashboard recreation, composed view.
// Two modes:
//  - "quick"  — 15-30 min session entry: Today's quick wins + top KPIs + actions.
//  - "deep"   — full analyst dashboard: every panel the live UI exposes.
const { useState } = React;

function fmtRub(value) {
  return `${value.toFixed(1)} M ₽`;
}

function ModeSwitch({ mode, onChange }) {
  const opts = [
    { key: "quick", label: "Сейчас" },
    { key: "deep",  label: "Полный режим" },
  ];
  return (
    <div role="tablist" aria-label="Режим"
         style={{
           display: "inline-flex", padding: 4, gap: 4,
           background: "var(--surface-strong)", border: "1px solid var(--line)",
           borderRadius: 999, boxShadow: "0 8px 24px rgba(0,0,0,.06)",
         }}>
      {opts.map((o) => (
        <button key={o.key} type="button" role="tab" aria-selected={mode === o.key}
                onClick={() => onChange(o.key)}
                style={{
                  appearance: "none", border: 0, cursor: "pointer",
                  padding: "10px 16px", borderRadius: 999, fontWeight: 600, fontSize: 14,
                  background: mode === o.key ? "var(--accent)" : "transparent",
                  color: mode === o.key ? "white" : "var(--ink)",
                  transition: "background 180ms ease, color 180ms ease",
                  fontFamily: "var(--font-ui)",
                  whiteSpace: "nowrap",
                }}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function DashboardApp() {
  const data = window.DashboardData;
  const [theme, setTheme] = useState("light");
  const [mode, setMode]   = useState("quick");
  const [report, setReport] = useState(data.report.available_reports[0]);

  React.useEffect(() => { document.body.dataset.theme = theme; }, [theme]);

  const deep = mode === "deep";

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">MM Market Tools</p>
          <h1>Дашборд магазина</h1>
          <p className="subtitle">
            {deep
              ? "Интерактивный просмотр операционных и исторических отчётов из слоя аналитических данных."
              : "Быстрый цикл на 15-30 минут. Сделать главное, не утонуть в данных."}
          </p>
        </div>
        <div className="hero-actions">
          <ModeSwitch mode={mode} onChange={setMode} />
          <button className="theme-toggle icon-toggle" type="button" aria-label="Переключить тему"
                  onClick={() => setTheme((t) => t === "light" ? "dark" : "light")}>
            <span>◐</span>
          </button>
          <a className="theme-toggle compact-button" href="../refresh/index.html" style={{ textDecoration: "none" }}>▶ Обновить</a>
          {deep ? (
            <label className="field">
              <span>Отчёт</span>
              <select value={report} onChange={(e) => setReport(e.target.value)}>
                {data.report.available_reports.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
          ) : null}
        </div>
      </header>

      <main className="layout">

        {/* =========================== QUICK MODE =========================== */}

        <QuickWinsSection items={data.quick_wins_backlog} />

        <Panel title="Сводка отчёта" subtitle={`${data.report.kind} · период ${data.meta[0].value}`}>
          <div className="meta-grid">
            {data.meta.map((m) => <MetaItem key={m.label} {...m} />)}
          </div>
        </Panel>

        <Panel title="Ключевые показатели" subtitle="Главные числа за окно.">
          <div className="kpi-grid">
            {data.kpis.slice(0, deep ? data.kpis.length : 4).map((k) => (
              <KpiCard key={k.label} {...k} deltaUnit={k.deltaUnit} />
            ))}
          </div>
        </Panel>

        <Panel title="Приоритеты Сейчас" subtitle="Главные управленческие действия по текущему отчёту.">
          <div className="compare-grid">
            {data.priorities.map((p, i) => <PriorityCard key={i} {...p} />)}
          </div>
        </Panel>

        <Panel title="Действия" subtitle="Приоритетные списки для текущего цикла.">
          <div className="action-grid">
            <ActionList title="reorder_now"        subtitle="Темп пробивает остаток."           rows={data.reorder_now} />
            <ActionList title="markdown_candidates" subtitle="Стоковый запас выше нормы."        rows={data.markdown_candidates} />
            <ActionList title="protect_winners"     subtitle="Хитам нельзя дать провалиться."    rows={data.protect_winners} />
          </div>
        </Panel>

        <Panel title="Покупатели" subtitle="Отзывы и вопросы без ответа. Черновик подставлен автоматически.">
          <div className="buyer-reviews-list">
            {data.reviews.slice(0, deep ? data.reviews.length : 2).map((r, i) => <ReviewCard key={i} {...r} />)}
          </div>
        </Panel>

        {!deep ? (
          <Panel>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16 }}>Нужен глубокий разбор?</h3>
                <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 14 }}>
                  Перейди в полный режим — там сравнение периодов, ABC, история по месяцам, центр действий и очереди.
                </p>
              </div>
              <button className="theme-toggle" type="button" onClick={() => setMode("deep")} style={{ textDecoration: "none" }}>
                Открыть полный режим →
              </button>
            </div>
          </Panel>
        ) : null}

        {/* =========================== DEEP MODE =========================== */}

        {deep ? (
          <>
            <Panel title="Карта Flow'ов" subtitle="Что уже доступно в UI, что остаётся runner-driven, и где слой пока partial.">
              <div className="compare-grid">
                {data.flow_map.map((f) => <FlowCard key={f.title} {...f} />)}
              </div>
            </Panel>

            <Panel title="Что Изменилось" subtitle="Сравнение текущего отчёта с предыдущим того же типа.">
              <div className="insights-grid">
                {data.changes.map((c, i) => <InsightCard key={i} {...c} />)}
              </div>
            </Panel>

            <Panel title="Сравнение Периодов" subtitle="Год к году, с начала года и сдвиг к базе по long-range данным CubeJS.">
              <div className="compare-grid">
                {data.compare.map((c, i) => <CompareCard key={i} {...c} />)}
              </div>
            </Panel>

            <Panel title="Центр действий" subtitle="Сохранённые списки наблюдения и ручные задачи менеджера.">
              <div className="action-grid">
                <WatchlistCard rows={data.watchlist} />
                <ManualActionsCard rows={data.manual_actions} />
                <ActionCenterStatusCard items={data.action_center_status} />
              </div>
            </Panel>

            <Panel title="Очереди дальнейших действий" subtitle="Срезы по статусам, ответственным и сохранённым представлениям.">
              <div className="action-grid">
                <QueueByBars title="По статусам" rows={data.queue_status} info="todo / in_progress / blocked / done." />
                <QueueByBars title="По ответственным" rows={data.queue_owner} info="Кто закрывает задачи в этом цикле." />
                <SavedViewsCard rows={data.saved_views} />
              </div>
            </Panel>

            <Panel title="Карточка и история" subtitle="Детальная карточка сущности: текущие сигналы, история и ручной follow-up.">
              <EntityDetail data={data.entity_detail} />
            </Panel>

            <section className="table-grid">
              <Panel><MiniTableCard title="Текущие победители" rows={data.current_winners} /></Panel>
              <Panel><MiniTableCard title="Profit leaders"      rows={data.profit_leaders} /></Panel>
              <Panel><MiniTableCard title="Stock risk"          rows={data.stock_risk} /></Panel>
              <Panel><MiniTableCard title="Stale stock"         rows={data.stale_stock} /></Panel>
            </section>

            <Panel title="Распределения" subtitle="Быстрый взгляд на структуру текущего окна.">
              <div className="chart-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
                <BarChartCard title="Распределение по статусам" rows={data.status_bars} />
                <AbcCard {...data.abc} />
              </div>
            </Panel>

            <Panel title="История По Месяцам" subtitle="Временной ряд по выручке без доставки.">
              <SparklineCard title="Sales.seller_revenue_without_delivery" rows={data.trend} format={fmtRub} />
            </Panel>
          </>
        ) : null}

      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<DashboardApp />);
