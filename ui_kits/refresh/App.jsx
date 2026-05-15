const { useState } = React;

function badgeForState(state) {
  if (state === "running")   return <span className="badge badge-online" style={{ textTransform: "uppercase", letterSpacing: ".04em" }}>Running</span>;
  if (state === "succeeded") return <span className="badge badge-succeeded" style={{ textTransform: "uppercase", letterSpacing: ".04em" }}>Succeeded</span>;
  if (state === "failed")    return <span className="badge badge-failed" style={{ textTransform: "uppercase", letterSpacing: ".04em" }}>Failed</span>;
  return <span className="badge">{state}</span>;
}

function JobCard({ name, subtitle, online = false }) {
  return (
    <div className="job-card">
      <div className="job-card-header">
        <h3>{name}</h3>
        {badgeForState(online ? "running" : "succeeded")}
      </div>
      <p className="job-card-text">{subtitle}</p>
      <div className="job-form-grid">
        <label className="field" style={{ minWidth: 0 }}>
          <span>Дата-от</span>
          <input className="inline-input" defaultValue="2026-04-02" />
        </label>
        <label className="field" style={{ minWidth: 0 }}>
          <span>Дата-до</span>
          <input className="inline-input" defaultValue="2026-04-08" />
        </label>
      </div>
      <div className="job-primary-actions">
        <button className="theme-toggle compact-button" type="button">▶ Запустить</button>
        <button className="theme-toggle compact-button" type="button">Параметры</button>
      </div>
    </div>
  );
}

function RunCard({ run }) {
  return (
    <div className="job-card">
      <div className="job-card-header">
        <h3>{run.name}</h3>
        {badgeForState(run.state)}
      </div>
      <p className="job-card-text">{run.at}</p>
    </div>
  );
}

function RefreshApp() {
  const data = window.RefreshData;
  const [theme, setTheme] = useState("light");
  React.useEffect(() => { document.body.dataset.theme = theme; }, [theme]);

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">MM Market Tools</p>
          <h1>Обновление данных</h1>
          <p className="subtitle">Локальный web-runner для online refresh: запуск jobs, статусы и живой лог.</p>
        </div>
        <div className="hero-actions">
          <button className="theme-toggle icon-toggle" type="button" aria-label="Переключить тему"
                  onClick={() => setTheme((t) => t === "light" ? "dark" : "light")}>
            <span>◐</span>
          </button>
          <button className="theme-toggle" type="button">⊞ Фокус</button>
          <a className="theme-toggle" href="../dashboard/index.html">К дашборду</a>
        </div>
      </header>

      <main className="layout">

        <section className="panel runner-control-panel">
          <div className="panel-header">
            <h2>Панель запуска</h2>
            <p>Быстрый статус, очередь запусков и групповые действия. Очередь идёт последовательно, чтобы не бить в API пачкой.</p>
          </div>
          <div className="meta-grid">
            {data.status.map((s) => (
              <div className="meta-item" key={s.label}>
                <span>{s.label}</span>
                <strong>{s.value}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Токен доступа</h2>
            <p>Единый токен для online jobs. Хранится только в браузерной сессии, перед запуском проверяется по JWT и не попадает в лог запуска.</p>
          </div>
          <div className="action-center-toolbar">
            <input className="inline-input" placeholder="Вставить bearer token…" style={{ minWidth: 320 }} />
            <button className="theme-toggle compact-button">Проверить</button>
            <button className="theme-toggle compact-button">Очистить</button>
          </div>
          <div className="meta-grid">
            <div className="meta-item"><span>JWT exp</span><strong>{data.token.jwt_exp}</strong></div>
            <div className="meta-item"><span>Хранилище</span><strong>{data.token.source}</strong></div>
            <div className="meta-item"><span>Безопасность</span><strong>{data.token.note}</strong></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Как использовать</h2>
            <p>Когда нужно обновить данные MM, открываешь этот экран из подходящей сетевой сессии, запускаешь нужный job и ждёшь succeeded.</p>
          </div>
          <div className="insights-grid">
            {data.workflow.map((w, i) => (
              <div className="insight-card" data-tone={w.tone} key={i}>
                <h3>{w.title}</h3>
                <p>{w.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Доступные jobs</h2>
            <p>Online jobs идут в MM API. Offline jobs работают только по локальным файлам.</p>
          </div>
          <div className="job-group">
            <div className="job-group-header">
              <h3 className="job-group-title">Online</h3>
              <span className="badge badge-online">{data.jobs_online.length} jobs</span>
            </div>
            <div className="jobs-grid">
              {data.jobs_online.map((j) => <JobCard key={j.name} {...j} online />)}
            </div>
          </div>
          <div className="job-group">
            <div className="job-group-header">
              <h3 className="job-group-title">Offline</h3>
              <span className="badge badge-offline">{data.jobs_offline.length} jobs</span>
            </div>
            <div className="jobs-grid">
              {data.jobs_offline.map((j) => <JobCard key={j.name} {...j} />)}
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Текущий запуск</h2>
            <p>Статус, параметры и live log. Токен в лог и status не сохраняется.</p>
          </div>
          <div className="meta-grid">
            <div className="meta-item"><span>Job</span><strong>{data.current.name}</strong></div>
            <div className="meta-item"><span>Статус</span><strong>{data.current.status}</strong></div>
            <div className="meta-item"><span>Старт</span><strong>{data.current.started}</strong></div>
            <div className="meta-item"><span>Прошло</span><strong>{data.current.elapsed}</strong></div>
          </div>
          <div className="progress-wrap" style={{ marginTop: 14 }}>
            <div className="progress-label">
              <span>weekly_operational_report</span>
              <span className="progress-elapsed">{data.current.elapsed}</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill--indeterminate" />
            </div>
          </div>
          <pre className="log-panel" style={{ marginTop: 14 }}>{data.current.log.join("\n")}</pre>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Последние запуски</h2>
            <p>История job run'ов на этой машине.</p>
          </div>
          <div className="jobs-grid">
            {data.recent_runs.map((r, i) => <RunCard key={i} run={r} />)}
          </div>
        </section>

      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<RefreshApp />);
