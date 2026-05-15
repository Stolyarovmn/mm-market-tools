// Atomic + composed components for the MM Market Tools dashboard kit.
// React 18, no JSX runtime, classNames mirror the source ui/styles.css.
const { useState, useMemo } = React;

/* =========================================================================
   Atoms
   ========================================================================= */

function Eyebrow({ children }) {
  return <p className="eyebrow">{children}</p>;
}

function InfoIcon({ text }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <span className="info-wrap" data-open={open ? "true" : undefined}>
      <button
        type="button"
        className="info-icon"
        aria-label="Пояснение"
        aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
      >i</button>
      {open ? (
        <span className="info-overlay" role="tooltip"
              style={{ position: "absolute", top: "calc(100% + 8px)", left: 0, width: 280 }}>
          <span className="info-overlay-body">
            <span className="info-overlay-text">{text}</span>
          </span>
        </span>
      ) : null}
    </span>
  );
}

function HeadingWithInfo({ tag: Tag = "h3", title, info }) {
  return (
    <Tag className="heading-with-info">
      <span>{title}</span>
      <InfoIcon text={info} />
    </Tag>
  );
}

function Badge({ tone = "neutral", caps = false, children }) {
  const cls = ["badge"];
  if (tone === "accent") cls.push("badge-online");
  if (tone === "good")   cls.push("badge-succeeded");
  if (tone === "warn")   cls.push("badge-partial");
  if (tone === "bad")    cls.push("badge-failed");
  return <span className={cls.join(" ")} style={caps ? { textTransform: "uppercase", letterSpacing: ".04em" } : null}>{children}</span>;
}

function Delta({ value, label = "Δ", unit = "%" }) {
  const tone = value == null || Number.isNaN(value)
    ? "neutral"
    : value > 0 ? "good" : value < 0 ? "bad" : "warn";
  const sign = value > 0 ? "+" : "";
  const display = value == null || Number.isNaN(value)
    ? "н/д"
    : unit === "%" ? `${sign}${value}%` : `${sign}${value} ${unit}`;
  return <div className={`delta ${tone}`}>{label ? `${label}: ` : ""}{display}</div>;
}

function MiniButton({ variant, children, onClick }) {
  const cls = ["mini-action-button"];
  if (variant === "primary") cls.push("primary");
  if (variant === "secondary") cls.push("secondary");
  return <button type="button" className={cls.join(" ")} onClick={onClick}>{children}</button>;
}

/* =========================================================================
   Panel chrome
   ========================================================================= */

function Panel({ title, subtitle, info, children, id }) {
  return (
    <section className="panel" id={id}>
      {title || subtitle ? (
        <div className="panel-header">
          {title ? <HeadingWithInfo tag="h2" title={title} info={info} /> : null}
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

function Hero({ eyebrow, title, subtitle, theme, onTheme, reportOptions, selected, onSelect }) {
  return (
    <header className="hero">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
      <div className="hero-actions">
        <button className="theme-toggle icon-toggle" type="button" aria-label="Переключить тему" onClick={onTheme}>
          <span>◐</span>
        </button>
        <a className="theme-toggle compact-button" href="#" title="Запустить refresh для текущего отчёта">▶ Обновить</a>
        <a className="theme-toggle" href="#">Обновить данные</a>
        <label className="field">
          <span>Отчёт</span>
          <select value={selected} onChange={(e) => onSelect(e.target.value)}>
            {reportOptions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
      </div>
    </header>
  );
}

/* =========================================================================
   Cards
   ========================================================================= */

function MetaItem({ label, value }) {
  return (
    <div className="meta-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function KpiCard({ label, value, info, delta, deltaUnit = "%" }) {
  return (
    <div className="kpi-card">
      <div className="label-row">
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{label}</span>
        <InfoIcon text={info} />
      </div>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{value}</strong>
      {delta !== undefined ? <Delta value={delta} label="" unit={deltaUnit} /> : null}
    </div>
  );
}

function PriorityCard({ tone, badge, value, text }) {
  return (
    <div className="compare-card priority-card" data-tone={tone}>
      <Badge tone={tone}>{badge}</Badge>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{value}</strong>
      <p>{text}</p>
    </div>
  );
}

function InsightCard({ tone, title, text }) {
  return (
    <div className="insight-card" data-tone={tone}>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

function CompareCard({ badge, value, subtitle, delta, deltaLabel }) {
  return (
    <div className="compare-card">
      <Badge tone="accent">{badge}</Badge>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{value}</strong>
      <p>{subtitle}</p>
      <Delta value={delta} label={deltaLabel} />
    </div>
  );
}

function FlowCard({ title, subtitle, state, note }) {
  const stateLabel = state === "available" ? "available" : state === "partial" ? "partial" : "runner";
  return (
    <div className="compare-card">
      <div className="flow-card-header">
        <div>
          <strong className="flow-card-title" style={{ display: "block" }}>{title}</strong>
          <span className="flow-card-subtitle">{subtitle}</span>
        </div>
        <Badge tone={state === "available" ? "good" : state === "partial" ? "warn" : "accent"}>{stateLabel}</Badge>
      </div>
      <p style={{ margin: "10px 0 0", color: "var(--muted)", fontSize: 13 }}>{note}</p>
    </div>
  );
}

/* =========================================================================
   Lists & tables
   ========================================================================= */

function ActionList({ title, subtitle, info, rows }) {
  return (
    <div className="list-card">
      <HeadingWithInfo tag="h3" title={title} info={info} />
      <p>{subtitle}</p>
      {rows.length === 0 ? (
        <p className="empty-state">Нет данных для этого блока.</p>
      ) : (
        <ul className="compact-list">
          {rows.map((r, i) => (
            <li key={i}>
              <div className="list-item-main">
                <strong>{r.title}</strong>
                <span>{r.meta}</span>
              </div>
              <div className="entity-actions">
                <MiniButton variant="primary">В список</MiniButton>
                <MiniButton>Задача</MiniButton>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MiniTableCard({ title, info, rows }) {
  return (
    <div className="table-card">
      <HeadingWithInfo tag="h3" title={title} info={info} />
      {rows.length === 0 ? (
        <p className="empty-state">Нет данных для этого блока.</p>
      ) : (
        <div className="mini-table">
          {rows.slice(0, 6).map((r, i) => (
            <div className="mini-row" key={i}>
              <div className="list-item-main">
                <strong>{r.title}</strong>
                <span>{r.meta}</span>
              </div>
              <div className="entity-actions">
                <MiniButton variant="primary">В список</MiniButton>
                <MiniButton>Задача</MiniButton>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   Charts
   ========================================================================= */

function BarChartCard({ title, rows, format }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="chart-card">
      <HeadingWithInfo tag="h3" title={title} />
      <div className="bars">
        {rows.map((r) => (
          <div className="bar-row" key={r.key}>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>{r.key}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
            <strong style={{ fontVariantNumeric: "tabular-nums" }}>{format ? format(r.value) : r.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function SparklineCard({ title, rows, format }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="sparkline-card">
      <h3>{title}</h3>
      <div className="sparkline">
        {rows.map((r) => (
          <div className="spark-bar" key={r.month}>
            <div className="spark-column" style={{ height: Math.max(10, (r.value / max) * 180) }} />
            <span>{format ? format(r.value) : r.value}</span>
            <span>{r.month}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AbcCard({ a, b, c }) {
  return (
    <div className="chart-card">
      <HeadingWithInfo tag="h3" title="ABC по выручке" info="A — 80% выручки, B — 15%, C — 5%. Считается по фактическим продажам в окне." />
      <p className="abc-explainer">A — ядро ассортимента, B — наполняющие, C — длинный хвост.</p>
      <div className="abc-grid">
        <div className="abc-cell abc-a"><strong>{a}%</strong><span>SKU дают 80% выручки</span></div>
        <div className="abc-cell abc-b"><strong>{b}%</strong><span>SKU дают 15% выручки</span></div>
        <div className="abc-cell abc-c"><strong>{c}%</strong><span>SKU дают 5% выручки</span></div>
      </div>
    </div>
  );
}

/* =========================================================================
   Reviews
   ========================================================================= */

function ReviewCard({ kind, rating, title, meta, text, status }) {
  const stars = rating ? "★".repeat(rating) + "☆".repeat(5 - rating) : null;
  const statusCls = {
    sent:     "reply-status-sent",
    draft:    "reply-status-draft",
    approved: "reply-status-approved",
    unsupported: "reply-status-unsupported",
  }[status] || "reply-status-draft";
  const statusLabel = { sent: "SENT", draft: "DRAFT", approved: "APPROVED", unsupported: "UNSUPPORTED" }[status] || "DRAFT";

  return (
    <div className="review-card" data-kind={kind} data-rating={rating}>
      <div className="review-header">
        <h3>{title}</h3>
        {stars ? <span className="review-stars">{stars}</span> : null}
        <span className="review-meta">{meta}</span>
      </div>
      <p className="review-text">{text}</p>
      <textarea className="reply-editor" defaultValue={
        kind === "question"
          ? "Здравствуйте! Под ноутбук 15.6\" подходит — основное отделение 39 × 28 см. Отдельного отсека под зонт нет, но есть боковой сетчатый карман."
          : rating <= 2
            ? "Здравствуйте! Спасибо, что написали — это важный сигнал. Передали в проверку упаковку партии, проверим закрутку крышки и фото-референс цвета. Если можно — напишите нам в чат заказа, оформим возврат или замену."
            : "Спасибо за добрый отзыв! Рады, что конструктор понравился ребёнку. Возвращайтесь — у нас вышли новые серии на 64 и 96 деталей."
      } />
      <div className="reply-actions">
        <button className="theme-toggle compact-button" type="button">Сохранить черновик</button>
        <button className="theme-toggle compact-button" type="button">Отправить</button>
        <span className={`reply-status-badge ${statusCls}`}>{statusLabel}</span>
      </div>
    </div>
  );
}

/* =========================================================================
   Quick wins — 15-30 minute session entry point
   ========================================================================= */

/**
 * Per-action time estimate, in minutes.
 * Calibrated against real cycle observations on the WONDERS shop:
 *   - reorder/markdown/price_trap/watchlist: SKU-by-SKU click-through review.
 *   - reviews/questions: read + edit auto-draft + send.
 *   - run_job: poll cycle for weekly_operational_report (~14s avg + buffer).
 *   - title_seo: per-card SEO rewrite by hand.
 * If new kinds are added, update this table — don't hard-code minutes in data.
 */
function estimateMin({ kind, count }) {
  switch (kind) {
    case "reorder":    return Math.max(2, Math.round(count * 0.3));   // ≈18 s / SKU
    case "markdown":   return Math.max(3, Math.round(count * 0.6));   // ≈36 s / SKU (price decision)
    case "reviews":    return count * 2;                              // 2 min / review
    case "questions":  return count * 3;                              // 3 min / answer
    case "run_job":    return 6;                                      // poll + verify
    case "title_seo":  return Math.max(2, count * 1);                 // 1 min / title
    case "price_trap": return Math.max(2, Math.round(count * 0.5));   // 30 s / SKU
    case "watchlist":  return Math.max(2, Math.round(count * 0.3));   // 18 s / item
    default:           return 5;
  }
}

function impactText({ kind, count }) {
  switch (kind) {
    case "reorder":    return `${count} SKU могут уйти в ноль без закупки`;
    case "markdown":   return `${count} stale карточек тянут полку`;
    case "reviews":    return `${count} отзыва без ответа`;
    case "questions":  return `${count} вопрос покупателя без ответа`;
    case "run_job":    return "Свежие данные за неделю";
    case "title_seo":  return `${count} слабых title — теряют CTR`;
    case "price_trap": return `${count} SKU чуть выше психопорогов 199/299/499`;
    case "watchlist":  return `${count} карточек ждут проверки`;
    default:           return "";
  }
}

function QuickWinCard({ win, done, onComplete, onRestore, draggable, dragState, dragHandlers }) {
  const mins = estimateMin(win);
  const isDragging = dragState && dragState.dragId === win.id;
  const isOver     = dragState && dragState.overId === win.id && dragState.dragId !== win.id;

  return (
    <div
      className="kpi-card"
      draggable={!!draggable}
      onDragStart={draggable && dragHandlers ? (e) => dragHandlers.onDragStart(e, win.id) : undefined}
      onDragOver ={draggable && dragHandlers ? (e) => dragHandlers.onDragOver(e, win.id)  : undefined}
      onDragLeave={draggable && dragHandlers ? (e) => dragHandlers.onDragLeave(e, win.id) : undefined}
      onDrop     ={draggable && dragHandlers ? (e) => dragHandlers.onDrop(e, win.id)      : undefined}
      onDragEnd  ={draggable && dragHandlers ? (e) => dragHandlers.onDragEnd(e)           : undefined}
      style={{
        position: "relative",
        display: "grid", gap: 8,
        opacity: done ? 0.55 : (isDragging ? 0.4 : 1),
        cursor: draggable ? "grab" : "default",
        outline: isOver ? "2px solid var(--accent)" : "none",
        outlineOffset: isOver ? 4 : 0,
        transition: "outline 120ms ease, opacity 120ms ease",
      }}
    >
      {draggable ? (
        <span
          aria-hidden="true"
          title="Перетащите для смены приоритета"
          style={{
            position: "absolute", top: 10, right: 10,
            color: "var(--muted)", fontSize: 16, lineHeight: 1,
            letterSpacing: "-0.2em", pointerEvents: "none", userSelect: "none",
          }}
        >⋮⋮</span>
      ) : null}
      <div className="label-row">
        <span style={{ color: "var(--muted)", fontSize: 13, textDecoration: done ? "line-through" : "none" }}>{win.label}</span>
        <span className="badge badge-online" style={{ padding: "4px 8px", fontSize: 11, whiteSpace: "nowrap" }}>~{mins} мин</span>
      </div>
      <strong style={{ fontSize: 28, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.03em" }}>{win.count}</strong>
      <p style={{ margin: 0, color: "var(--muted)", fontSize: 13, lineHeight: 1.45 }}>{impactText(win)}</p>
      {done ? (
        <button className="theme-toggle compact-button" type="button"
                style={{ marginTop: 4, textDecoration: "none", textAlign: "center" }}
                onClick={() => onRestore && onRestore(win.id)}>
          ↺ Вернуть в очередь
        </button>
      ) : (
        <div style={{ display: "grid", gap: 6, marginTop: 4 }}>
          <button className="theme-toggle compact-button" type="button"
                  style={{ textDecoration: "none", textAlign: "center" }}>
            {win.action}
          </button>
          <button className="mini-action-button secondary" type="button"
                  style={{ textAlign: "center" }}
                  onClick={() => onComplete && onComplete(win.id)}>
            ✓ Готово
          </button>
        </div>
      )}
    </div>
  );
}

function QuickWinsSection({ items }) {
  const initialOrder = React.useMemo(() => items.map((i) => i.id), [items]);
  const [order, setOrder] = useState(initialOrder);
  const [doneIds, setDoneIds] = useState(() => new Set());
  const [expanded, setExpanded] = useState(false);
  const [dragState, setDragState] = useState({ dragId: null, overId: null });

  const complete = (id) => setDoneIds((s) => { const n = new Set(s); n.add(id); return n; });
  const restore  = (id) => setDoneIds((s) => { const n = new Set(s); n.delete(id); return n; });

  const itemsById = React.useMemo(() => {
    const m = new Map(); items.forEach((i) => m.set(i.id, i)); return m;
  }, [items]);
  const ordered = order.map((id) => itemsById.get(id)).filter(Boolean);
  const isCustomOrder = order.join("|") !== initialOrder.join("|");

  /* HTML5 drag handlers — only used inside the expanded panel. */
  const dragHandlers = {
    onDragStart: (e, id) => {
      setDragState({ dragId: id, overId: null });
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", id); } catch (_) { /* IE */ }
    },
    onDragOver: (e, id) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      if (dragState.overId !== id) setDragState((s) => ({ ...s, overId: id }));
    },
    onDragLeave: (e, id) => {
      if (dragState.overId === id) setDragState((s) => ({ ...s, overId: null }));
    },
    onDrop: (e, id) => {
      e.preventDefault();
      const src = dragState.dragId;
      setDragState({ dragId: null, overId: null });
      if (!src || src === id) return;
      setOrder((prev) => {
        const next = prev.filter((x) => x !== src);
        const dstIdx = next.indexOf(id);
        if (dstIdx < 0) return prev;
        next.splice(dstIdx, 0, src);
        return next;
      });
    },
    onDragEnd: () => setDragState({ dragId: null, overId: null }),
  };

  const active = ordered.filter((i) => !doneIds.has(i.id));
  const visible = active.slice(0, 4);
  const moreActive = active.length - visible.length;
  const doneCount = items.length - active.length;
  const totalMin = visible.reduce((s, w) => s + estimateMin(w), 0);

  const allDone = visible.length === 0;
  const subtitle = allDone
    ? "Всё закрыто за сессию. Можно проверить полный список ниже или открыть полный режим."
    : `${visible.length} ${visible.length === 1 ? "действие" : "действия"} в очереди — примерно ${totalMin} мин на всё.`;

  return (
    <>
      <Panel title="Сейчас — быстрые действия" subtitle={subtitle}>
        {allDone ? (
          <div className="insight-card" data-tone="good">
            <h3>Цикл закрыт</h3>
            <p>Все быстрые действия за эту сессию выполнены. Если что-то нажал случайно — открой «Все действия» ниже и верни в очередь.</p>
          </div>
        ) : (
          <div className="kpi-grid">
            {visible.map((w) => (
              <QuickWinCard key={w.id} win={w} onComplete={complete} />
            ))}
          </div>
        )}
        {(moreActive > 0 || doneCount > 0 || isCustomOrder) ? (
          <div style={{
            marginTop: 14, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
            paddingTop: 14, borderTop: "1px solid var(--line)",
          }}>
            {moreActive > 0 ? (
              <span style={{ color: "var(--muted)", fontSize: 13 }}>
                Ещё доступно: <strong style={{ color: "var(--ink)" }}>{moreActive}</strong>
              </span>
            ) : null}
            {doneCount > 0 ? (
              <span style={{ color: "var(--good)", fontSize: 13 }}>
                Готово за сессию: <strong>{doneCount}</strong>
              </span>
            ) : null}
            {isCustomOrder ? (
              <span style={{ color: "var(--accent)", fontSize: 13 }}>
                Порядок изменён вручную
              </span>
            ) : null}
            <button className="theme-toggle compact-button" type="button"
                    style={{ textDecoration: "none", marginLeft: "auto" }}
                    onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Свернуть" : "Показать все действия за цикл"}
            </button>
          </div>
        ) : null}
      </Panel>

      {expanded ? (
        <Panel
          title={`Все действия за цикл — ${items.length}`}
          subtitle="Перетащи карточку, чтобы поднять её в строку наверху. Готовые можно вернуть в очередь."
        >
          {isCustomOrder ? (
            <div style={{ marginBottom: 14 }}>
              <button className="theme-toggle compact-button" type="button"
                      style={{ textDecoration: "none" }}
                      onClick={() => setOrder(initialOrder)}>
                ↺ Сбросить к приоритету из данных
              </button>
            </div>
          ) : null}
          <div className="kpi-grid">
            {ordered.map((w) => (
              <QuickWinCard
                key={w.id}
                win={w}
                done={doneIds.has(w.id)}
                onComplete={complete}
                onRestore={restore}
                draggable={!doneIds.has(w.id)}
                dragState={dragState}
                dragHandlers={dragHandlers}
              />
            ))}
          </div>
        </Panel>
      ) : null}
    </>
  );
}

/* =========================================================================
   Action Center
   ========================================================================= */

function WatchlistCard({ rows }) {
  return (
    <div className="list-card">
      <HeadingWithInfo tag="h3" title="Watchlist" info="Карточки, которые менеджер вручную поставил на наблюдение. Сохраняется в браузере." />
      <p>Сущности, которые менеджер держит под наблюдением между weekly циклами.</p>
      <ul className="compact-list">
        {rows.map((r, i) => (
          <li key={i}>
            <div className="list-item-main">
              <strong>{r.title}</strong>
              <span>{r.meta} · owner: {r.owner}</span>
            </div>
            <div className="entity-actions">
              <MiniButton variant="secondary">Снять</MiniButton>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ManualActionsCard({ rows }) {
  const dot = (status) => {
    const map = { todo: "var(--muted)", in_progress: "var(--accent)", blocked: "var(--bad)", done: "var(--good)" };
    return (
      <span style={{
        display: "inline-block", width: 8, height: 8, borderRadius: 999,
        background: map[status] || "var(--muted)", marginRight: 6,
      }} />
    );
  };
  return (
    <div className="list-card">
      <HeadingWithInfo tag="h3" title="Ручные задачи" info="Локальные задачи менеджера: TODO, в работе, заблокировано, сделано." />
      <p>Локальные задачи менеджера со статусом и ответственным.</p>
      <ul className="compact-list">
        {rows.map((r, i) => (
          <li key={i}>
            <div className="list-item-main">
              <strong>{dot(r.status)}{r.title}</strong>
              <span>{r.meta} · owner: {r.owner}</span>
            </div>
            <div className="entity-actions">
              <MiniButton variant="primary">Открыть</MiniButton>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ActionCenterStatusCard({ items }) {
  return (
    <div className="list-card">
      <HeadingWithInfo tag="h3" title="Сводка центра действий" info="Быстрые счётчики по локальному action store." />
      <p>Текущая нагрузка по управленческому циклу.</p>
      <div className="meta-grid" style={{ marginTop: 8 }}>
        {items.map((i) => (
          <div className="meta-item" key={i.label}>
            <span>{i.label}</span>
            <strong>{i.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =========================================================================
   Manager Queues
   ========================================================================= */

function QueueByBars({ title, rows, info }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="list-card">
      <HeadingWithInfo tag="h3" title={title} info={info} />
      <div className="bars" style={{ marginTop: 12 }}>
        {rows.map((r) => (
          <div className="bar-row" key={r.key}>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>{r.key}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
            </div>
            <strong style={{ fontVariantNumeric: "tabular-nums" }}>{r.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function SavedViewsCard({ rows }) {
  return (
    <div className="list-card">
      <HeadingWithInfo tag="h3" title="Сохранённые представления" info="Именованные фильтры по очередям задач." />
      <p>Быстрые сохранённые срезы по фильтрам.</p>
      <ul className="compact-list">
        {rows.map((r, i) => (
          <li key={i}>
            <div className="list-item-main">
              <strong>{r.name}</strong>
              <span>{r.filters}</span>
            </div>
            <div className="entity-actions">
              <span className="badge">{r.count}</span>
              <MiniButton variant="primary">Открыть</MiniButton>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* =========================================================================
   Entity Detail drawer
   ========================================================================= */

function EntityDetail({ data }) {
  const max = Math.max(1, ...data.history.map((h) => h.value));
  return (
    <div className="entity-detail-root">
      <div>
        <div className="entity-title-row">
          <h3 style={{ margin: 0, flex: "1 1 auto", fontSize: 18 }}>{data.title}</h3>
          <span className="entity-position-badge"
                style={{ fontSize: 11, padding: "3px 8px", borderRadius: 999, background: "var(--accent-soft)", color: "var(--accent)", fontWeight: 700 }}>
            {data.position_label}
          </span>
          <span className="entity-cross-badge"
                style={{ fontSize: 11, padding: "3px 8px", borderRadius: 999, background: "var(--surface-strong)", color: "var(--muted)", fontWeight: 700, border: "1px solid var(--line)" }}>
            {data.cross_label}
          </span>
        </div>
        <p className="entity-info-note" style={{ margin: "4px 0 8px", fontSize: 13, color: "var(--muted)" }}>
          {data.sku}
        </p>
        <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.5 }}>{data.note}</p>

        <div className="entity-spark-row" style={{ display: "flex", alignItems: "flex-end", gap: 8, marginTop: 14 }}>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>{data.history_label}</span>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 32 }}>
            {data.history.map((h) => (
              <div key={h.week} title={`${h.week}: ${h.value}`}
                   style={{
                     width: 8, borderRadius: "2px 2px 0 0",
                     height: Math.max(3, (h.value / max) * 32),
                     background: "var(--accent)", opacity: 0.7,
                   }} />
            ))}
          </div>
          <span style={{ fontSize: 12, fontWeight: 700 }}>{data.history[data.history.length - 1].value}</span>
        </div>
        <p style={{ marginTop: 6, fontSize: 11, color: "var(--muted)" }}>
          ← / → переключают карточку · Esc закрывает
        </p>
      </div>

      <div className="entity-history-list" style={{ display: "grid", gap: 10 }}>
        {data.log.map((e, i) => (
          <div className="history-row" key={i}
               style={{
                 display: "grid", gap: 4, padding: 12,
                 border: "1px solid var(--line)", borderRadius: 18,
                 background: "var(--surface-muted)",
               }}>
            <strong style={{ fontSize: 13 }}>{e.when}</strong>
            <span style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.45 }}>{e.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* Export to window for other scripts */
Object.assign(window, {
  QuickWinCard, QuickWinsSection, estimateMin, impactText,
  WatchlistCard, ManualActionsCard, ActionCenterStatusCard,
  QueueByBars, SavedViewsCard,
  EntityDetail,
  Eyebrow, InfoIcon, HeadingWithInfo, Badge, Delta, MiniButton,
  Panel, Hero,
  MetaItem, KpiCard, PriorityCard, InsightCard, CompareCard, FlowCard,
  ActionList, MiniTableCard,
  BarChartCard, SparklineCard, AbcCard,
  ReviewCard,
});
