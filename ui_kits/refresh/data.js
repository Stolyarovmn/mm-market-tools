window.RefreshData = {
  status: [
    { label: "Запущено сейчас", value: "0" },
    { label: "Последний succeeded", value: "weekly · 09:14" },
    { label: "Последний failed", value: "—" },
    { label: "Очередь", value: "3 jobs" },
  ],
  token: { jwt_exp: "2026-04-30 18:00", source: "browser session", note: "Токен не уходит в лог запуска." },
  workflow: [
    { tone: "good", title: "1. Подключиться к MM", text: "Откройте этот экран из сетевой сессии с доступом к seller API." },
    { tone: "good", title: "2. Запустить job",        text: "Выберите online или offline pipeline и нажмите ▶ — параметры подтянутся из defaults." },
    { tone: "warn", title: "3. Дождаться succeeded",   text: "Очередь идёт последовательно: бить в API пачкой запрещено." },
    { tone: "good", title: "4. Вернуться к дашборду",  text: "Артефакты автоматически появятся в data/dashboard/." },
  ],
  jobs_online: [
    { name: "weekly_operational_report", subtitle: "SELLS_REPORT + LEFT_OUT_REPORT → operational bundle." },
    { name: "marketing_card_audit",       subtitle: "dynamic_pricing + price_trap + title_seo в одном слое." },
    { name: "cubejs_period_compare",      subtitle: "Trailing year + YoY + 3Y compare через CubeJS." },
  ],
  jobs_offline: [
    { name: "dynamic_pricing",            subtitle: "Безопасные ценовые рекомендации поверх market + economics." },
    { name: "price_trap_report",          subtitle: "SKU чуть выше психологических порогов 199/299/499." },
    { name: "title_seo_report",           subtitle: "Audit первого слова в названии карточки." },
    { name: "build_dashboard_index",      subtitle: "Индекс dashboard-отчётов + entity history." },
  ],
  current: {
    name: "weekly_operational_report",
    status: "running",
    started: "09:14:02",
    elapsed: "0:00:14",
    log: [
      "[09:14:02] weekly_operational_report — started",
      "[09:14:03] documents/create … 202 Accepted",
      "[09:14:04] polling job 7e4f… status=running",
      "[09:14:18] polling job 7e4f… status=running",
      "[09:14:32] polling job 7e4f… status=succeeded",
      "[09:14:33] Saved: data/raw_reports/sells-report.csv",
    ],
  },
  recent_runs: [
    { name: "weekly_operational_report",  state: "succeeded", at: "09:14 · 14 сек" },
    { name: "marketing_card_audit",        state: "succeeded", at: "08:52 · 22 сек" },
    { name: "cubejs_period_compare",       state: "failed",    at: "08:30 · 401" },
    { name: "dynamic_pricing",             state: "succeeded", at: "08:21 · 6 сек" },
  ],
};
