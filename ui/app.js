import {
  acknowledgeEntity,
  addActionItem,
  addWatchlistItem,
  fetchJson,
  loadEntityHistoryIndex,
  loadActionCenter,
  loadDashboardIndex,
  loadLocalCogsStore,
  loadRunnerJobs,
  loadRunnerRun,
  loadRunnerRuns,
  saveActionView,
  startRunnerJob,
  toggleActionItem,
  updateActionItem,
  validateRunnerToken,
} from "./api.js";
import {
  getStoredActionFilter,
  getStoredActionOwner,
  getStoredReportSelection,
  getStoredRefreshToken,
  initThemeToggle,
  setStoredActionFilter,
  setStoredActionOwner,
  setStoredReportSelection,
  setStoredRefreshToken,
} from "./state.js";
import {
  REPORT_KIND_LABELS,
  REPORT_KIND_ORDER,
  buildCubejsInsights,
  buildDescriptionInsights,
  buildMarketingInsights,
  buildMediaInsights,
  buildOperationalInsights,
  buildPaidStorageInsights,
  buildPricingInsights,
  buildSalesReturnInsights,
  buildWaybillInsights,
  normalizeCubejsComparePayload,
} from "./dashboard_views.js";
import {
  appendHeadingWithInfo,
  appendValueWithOptionalInfo,
  createInfoIcon,
  el,
  renderActionCard,
  renderBarChart,
  renderCompareCard,
  renderTableCard,
  renderTrendCard,
} from "./components.js";
let currentDashboardItem = null;
let actionCenterState = null;
let entityHistoryIndex = null;
let selectedEntityKey = null;
let selectedActionFilter = getStoredActionFilter();
let currentEntityRows = [];
let dashboardItems = [];
let dashboardSelects = [];
let cogsOverrideStore = null;
const DASHBOARD_INDEX_POLL_MS = 15000;
const RUNNER_STATUS_POLL_MS = 15000;
const SAFE_RUNNER_JOB_KEYS = [
  "validate_token",
  "weekly_operational",
  "paid_storage_report",
  "sales_return_report",
  "buyer_reviews",
  "dashboard_rebuild",
];
let runnerJobs = [];
let runnerRuns = [];
let runnerActiveJobId = null;
let runnerSharedToken = getStoredRefreshToken();
let runnerTokenHealth = null;

function formatMoney(value) {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value || 0);
}

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU").format(value || 0);
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "н/д";
  return `${value > 0 ? "+" : ""}${value}%`;
}

function formatShare(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "н/д";
  return `${Number(value).toFixed(1)}%`;
}

function formatWindow(window) {
  if (!window || !window.date_from || !window.date_to) return "нет окна";
  return `${window.date_from.slice(0, 10)} -> ${window.date_to.slice(0, 10)}`;
}

function detectSourceMode(sourceValue) {
  const raw = String(sourceValue || "");
  if (!raw) return "н/д";
  if (raw.startsWith("/")) return "локальные seller CSV";
  if (raw.startsWith("http://") || raw.startsWith("https://")) return "seller CSV URL";
  return "seller CSV";
}

function formatDateTime(value) {
  if (!value) return "н/д";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch (_) {
    return value;
  }
}

function formatEntityType(value) {
  const labels = {
    sku: "SKU",
    family: "семейство",
    seller: "продавец",
    market_segment: "рыночный сегмент",
    unknown: "сущность",
  };
  return labels[value] || value || "сущность";
}

function formatActionStatus(value) {
  const labels = {
    open: "новая",
    in_progress: "в работе",
    blocked: "блокер",
    done: "завершена",
  };
  return labels[value] || value || "новая";
}

function formatModeLabel(value) {
  const labels = {
    reused: "загружено из архива",
    created: "запрошено через API",
    downloaded: "скачано из seller-отчёта",
    online: "онлайн-запуск",
    offline: "локальная пересборка",
    "seller analytics": "аналитика продавца",
  };
  return labels[value] || value || "н/д";
}

function describeSourceInfo(label, sourceValue, modeValue = "") {
  const source = String(sourceValue || "");
  const mode = String(modeValue || "");
  if (!source) {
    return `${label}: источник не указан в metadata этого bundle.`;
  }
  if (mode === "reused") {
    return `${label}: данные взяты из уже существующего seller-отчёта, который был создан раньше и повторно использован без нового запроса в MM API.`;
  }
  if (source.startsWith("/")) {
    return `${label}: данные считаны из локально сохранённого файла, который был выпущен предыдущим pipeline или ручной выгрузкой seller-отчёта.`;
  }
  if (source.startsWith("http://") || source.startsWith("https://")) {
    return `${label}: данные были получены по сетевому URL seller-контурa и затем сохранены локально для повторного анализа.`;
  }
  return `${label}: источник передан как идентификатор или краткое имя внутри pipeline.`;
}

function summarizeSource(sourceValue) {
  const raw = String(sourceValue || "");
  if (!raw) return "н/д";
  try {
    if (raw.startsWith("http://") || raw.startsWith("https://")) {
      const url = new URL(raw);
      const decodedPath = decodeURIComponent(url.pathname || "");
      const fileName = decodedPath.split("/").filter(Boolean).pop() || url.hostname;
      return `${url.hostname} / ${fileName}`;
    }
  } catch (_) {
    return raw;
  }
  if (raw.startsWith("/")) {
    return raw.split("/").filter(Boolean).pop() || raw;
  }
  return raw;
}

function getPrimarySku(row) {
  return row?.sku || row?.seller_sku_id || row?.barcode || row?.product_id || "";
}

function metricLabel(key) {
  const labels = {
    total_skus: "SKU всего",
    sold_skus: "SKU с продажами",
    revenue_total: "Выручка net",
    gross_profit_total: "Валовая прибыль",
    stockout_risk_count: "Риск OOS",
    stale_stock_count: "Залежавшиеся",
    observed_seller_count: "Продавцов",
    observed_group_count: "Групп",
    observed_price_bands: "Ценовых коридоров",
    observed_idea_clusters: "Кластеров идей",
    overall_dominance_hhi: "HHI",
    novelty_proxy_index: "Индекс новизны",
    blind_spot_windows_count: "Слепых зон",
    entry_ready_windows_count: "Готовых окон входа",
    test_entry_windows_count: "Окон для теста",
    avoid_windows_count: "Окон no-go",
    priced_windows_count: "Окон с ценовой рекомендацией",
    aggressive_price_windows_count: "Агрессивный вход",
    market_price_windows_count: "Цена по рынку",
    test_price_windows_count: "Осторожный тест",
    do_not_discount_windows_count: "Не демпинговать",
    priority_cards_count: "Карточек в приоритете",
    price_trap_cards_count: "Ценовых ловушек",
    seo_needs_work_count: "Название требует работы",
    seo_priority_fix_count: "Критичных названий",
    market_supported_cards_count: "Карточек с рыночным контекстом",
    double_fix_count: "Двойных проблем",
    media_needs_work_count: "Медиа требует работы",
    photo_gap_count: "Отставание по фото",
    spec_gap_count: "Отставание по характеристикам",
    with_video_count: "Карточек с видео",
    description_needs_work_count: "Описание требует работы",
    thin_content_count: "Тонкое описание",
    description_gap_count: "Описание слабее группы",
    storage_rows_count: "Строк в отчёте",
    rows_with_amount_count: "Строк с суммой",
    rows_without_identity_count: "Строк без идентификации",
    total_amount: "Сумма начислений",
    penalty_total: "Штрафы и удержания",
    avg_amount_per_row: "Средняя сумма на строку",
  };
  return labels[key] || key;
}

async function loadJson(url) {
  return fetchJson(url);
}

function renderMeta(payload) {
  const root = document.getElementById("meta-grid");
  root.innerHTML = "";
  const metadata = payload.metadata || {};
  const window = metadata.window || {};
  const documents = metadata.documents || {};
  const marketScope = metadata.market_scope || {};
  const pricing = metadata.pricing || {};
  const sources = metadata.sources || {};
  const hasOfficialSources = sources.sells_report || sources.sells_csv || sources.left_out_report || sources.left_out_csv;
  const sellsSource = sources.sells_report || sources.sells_csv || "";
  const leftSource = sources.left_out_report || sources.left_out_csv || "";
  const sellsMode = documents.sells_mode || (hasOfficialSources ? detectSourceMode(sellsSource) : "seller analytics");
  const leftMode = documents.left_out_mode || (hasOfficialSources ? detectSourceMode(leftSource) : "seller analytics");
  const snapshotInfo = ["Срез данных", formatDateTime(currentDashboardItem?.generated_at), "Когда был сформирован именно этот bundle и от какой точки времени нужно читать его выводы."];
  const items = marketScope.category_id
    ? [
        snapshotInfo,
        ["Категория", marketScope.category_id],
        ["Сканировано страниц", marketScope.pages ?? "н/д"],
        ["Товаров на страницу", marketScope.page_size ?? "н/д"],
        ["Режим", "рыночная выборка"],
        ["Источник", "публичный market API", "Данные собраны из публичного каталога Магнит Маркета, а не из личного кабинета продавца."],
      ]
    : pricing.mode
    ? [
        snapshotInfo,
        ["Режим", formatModeLabel(pricing.mode), pricing.mode ? `Режим ценового слоя: ${formatModeLabel(pricing.mode)}.` : null],
        ["Целевая маржа", pricing.target_margin_pct != null ? `${pricing.target_margin_pct}%` : "н/д", "Целевая маржа, относительно которой подбирались безопасные ценовые решения."],
        ["Источник рынка", summarizeSource(pricing.generated_from), describeSourceInfo("Источник рынка", pricing.generated_from, pricing.mode)],
        ["Окно", formatWindow(window), window.date_from && window.date_to ? `${window.date_from} -> ${window.date_to}` : null],
      ]
    : metadata.marketing_audit
    ? [
        snapshotInfo,
        ["Режим", "маркетинговый аудит", "Единый управленческий слой, который сводит ценовой анализ, ценовые ловушки и SEO названий по карточкам."],
        ["Источник ценового слоя", summarizeSource(metadata.marketing_audit.pricing_json), describeSourceInfo("Источник ценового слоя", metadata.marketing_audit.pricing_json)],
        ["Источник price trap", summarizeSource(metadata.marketing_audit.price_trap_json), describeSourceInfo("Источник price trap", metadata.marketing_audit.price_trap_json)],
        ["Источник title SEO", summarizeSource(metadata.marketing_audit.title_seo_json), describeSourceInfo("Источник title SEO", metadata.marketing_audit.title_seo_json)],
        ["Источник normalized", summarizeSource(metadata.marketing_audit.normalized_json), describeSourceInfo("Источник normalized", metadata.marketing_audit.normalized_json)],
      ]
    : metadata.content_audit
    ? [
        snapshotInfo,
        ["Режим", "контент-аудит", "Слой проверки медиа или описаний карточки относительно группы и минимального quality bar."],
        ["Источник входа", summarizeSource(metadata.content_audit.input_json), describeSourceInfo("Источник входа", metadata.content_audit.input_json)],
        ["Кэш карточек", summarizeSource(metadata.content_audit.cache_json), describeSourceInfo("Кэш карточек", metadata.content_audit.cache_json)],
        ["Сеть", metadata.content_audit.cache_only ? "только кэш" : "кэш + публичный API", metadata.content_audit.cache_only ? "Сеть не использовалась: аудит построен только по локальному кэшу карточек." : "Аудит использовал локальный кэш и при необходимости публичный product API."],
      ]
    : metadata.paid_storage
    ? [
        snapshotInfo,
        ["Режим", formatModeLabel(documents.paid_storage_mode || metadata.paid_storage.mode || "reused"), "Берётся последний completed PAID_STORAGE_REPORT из seller documents и разворачивается в manager-facing экран затрат."],
        ["Источник файла", summarizeSource(metadata.paid_storage.xlsx_path || documents.paid_storage_file_name), describeSourceInfo("Источник файла", metadata.paid_storage.xlsx_path || documents.paid_storage_file_name, documents.paid_storage_mode)],
        ["Лист XLSX", metadata.paid_storage.sheet_name || "н/д", "Первый лист, который удалось прочитать из XLSX-отчёта."],
        ["Главная колонка суммы", metadata.paid_storage.amount_header || "н/д", "Эвристически выбранная основная денежная колонка, по которой отсортированы крупнейшие начисления."],
        ["Запрос seller documents", documents.paid_storage_request_id || "н/д", "Request ID из seller documents, если отчёт был подтянут online, а не передан локальным файлом."],
      ]
    : (() => {
        const baseItems = [
          snapshotInfo,
          ["Окно", formatWindow(window), window.date_from && window.date_to ? `Данные отчёта покрывают период ${window.date_from} -> ${window.date_to}.` : "У этого bundle нет явного окна дат в metadata."],
          ["Дней", window.window_days ?? "н/д", null],
          ["Режим", formatModeLabel(sellsMode), sellsMode ? `Как были получены данные продаж: ${formatModeLabel(sellsMode)}.` : null],
          ["Источник продаж", summarizeSource(sellsSource), describeSourceInfo("Источник продаж", sellsSource, documents.sells_mode)],
          ["Источник остатков", summarizeSource(leftSource), describeSourceInfo("Источник остатков", leftSource, documents.left_out_mode)],
        ];
        if (documents.sells_request_id) {
          baseItems.push(["Запрос продаж", documents.sells_request_id, null]);
        }
        if (documents.left_out_request_id) {
          baseItems.push(["Запрос остатков", documents.left_out_request_id, null]);
        }
        return baseItems;
      })();
  items.forEach(([label, value, info]) => {
    const card = el("div", "meta-item");
    const row = el("div", "label-row");
    row.append(el("span", "", label));
    card.append(row);
    appendValueWithOptionalInfo(card, value, info);
    root.append(card);
  });
}

function getDisplayTitle(row) {
  const title = (
    row.title ||
    row.seller_title ||
    row.group ||
    row.idea_cluster ||
    row.key ||
    "Без названия"
  );
  const sku = getPrimarySku(row);
  if (sku && title && !String(title).includes(String(sku))) {
    return `${sku} · ${title}`;
  }
  return title;
}

function pickEntityValue(latest, history, fallbackRow, keys, emptyValues = ["", null, undefined]) {
  const rows = [latest, fallbackRow, ...(history || [])];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    for (const key of keys) {
      const value = row[key];
      if (!emptyValues.includes(value)) {
        return value;
      }
    }
  }
  return null;
}

function decorateStaticPanelInfos() {
  const definitions = [
    ["#kpi-panel .panel-header h2", "Ключевые показатели это верхний числовой слой отчёта. Их задача не заменить весь анализ, а быстро показать масштаб проблемы, выборки и денег до перехода к действиям."],
    ["#priority-panel .panel-header h2", "Этот блок отвечает на вопрос: что делать первым. Он не перечисляет всё подряд, а поднимает решения, которые сейчас важнее остальных."],
    ["#change-panel .panel-header h2", "Сравнение с предыдущим отчётом того же типа. Здесь важно смотреть не только на рост, но и на то, за какой период и из какой выборки этот рост получен."],
    ["#insights-panel .panel-header h2", "Автоматические выводы это интерпретации поверх данных. Они должны помогать читать отчёт быстрее, но не подменяют ручную проверку управленческого решения."],
    ["#compare-panel .panel-header h2", "Этот блок нужен для длинной истории и сезонности. Его читают отдельно от коротких operational-окон."],
    ["#actions-panel .panel-header h2", "Здесь собраны прикладные очереди действий. Это рабочий слой, из которого менеджер берёт задачи в работу, а не просто читает цифры."],
    ["#action-center-panel .panel-header h2", "Центр действий это ручной слой поверх автоматических сигналов. Здесь менеджер сохраняет short-list, фиксирует задачу и ведёт статус до завершения."],
    ["#manager-queues-panel .panel-header h2", "Это агрегированные очереди по статусам, ответственным и сохранённым представлениям. Они нужны, чтобы видеть bottleneck ежедневного цикла, а не только отдельные задачи."],
    ["#entity-detail-panel .panel-header h2", "Детальная карточка сущности нужна для drilldown: посмотреть текущий сигнал, историю появления в отчётах и ручной follow-up по этой позиции."],
    ["#charts-panel .panel-header h2", "Распределения помогают увидеть структуру окна: где концентрируется результат, где длинный хвост и где шум. Это вспомогательный слой, а не приоритет сам по себе."],
    ["#trend-panel .panel-header h2", "История по месяцам нужна для накопления seasonality и сравнения длинных периодов. Этот блок полезен только если временной ряд уже достаточно длинный."],
    ["#meta-panel .panel-header h2", "Сводка отчёта показывает период, режим получения данных и происхождение источников. С неё надо начинать чтение любого отчёта, чтобы не путать окна и типы данных."],
    [".utility-panel .panel-header h2", "Навигация это вспомогательный сервисный блок: быстро перейти к другому отчёту, refresh runner или вернуться вверх страницы."],
  ];
  definitions.forEach(([selector, text]) => {
    const heading = document.querySelector(selector);
    if (!heading || heading.dataset.infoDecorated === "true") return;
    heading.append(createInfoIcon(text));
    heading.dataset.infoDecorated = "true";
  });
}

function collectArrayRows(source, target) {
  if (!source || typeof source !== "object") return;
  Object.values(source).forEach((value) => {
    if (Array.isArray(value)) {
      value.forEach((row) => {
        if (row && typeof row === "object") {
          target.push(row);
        }
      });
    }
  });
}

function buildEntityNavigationRows(payload) {
  const rows = [];
  collectArrayRows(payload.actions, rows);
  collectArrayRows(payload.tables, rows);
  collectArrayRows(payload.family_tables, rows);
  const deduped = [];
  const seen = new Set();
  rows.forEach((row) => {
    const entity = buildEntityPayload(row, row.group || row.idea_cluster || row.action_label || "report");
    if (seen.has(entity.entity_key)) return;
    seen.add(entity.entity_key);
    deduped.push({ entity_key: entity.entity_key, row });
  });
  return deduped;
}

function renderKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["SKU всего", formatNumber(kpis.total_skus), "Сколько строк или SKU попало в текущее окно отчёта. Это размер наблюдаемой выборки."],
    ["SKU с продажами", formatNumber(kpis.sold_skus), "Сколько SKU реально имели продажи в выбранном периоде. Это один из главных индикаторов живости ассортимента сейчас."],
    ["Выручка net", formatMoney(kpis.revenue_total), "Выручка за окно после вычета комиссии маркетплейса. Используйте для оценки реального денежного потока по периоду."],
    ["Валовая прибыль", formatMoney(kpis.gross_profit_total), "Net revenue минус себестоимость. Это ориентир, какие товары и окна реально зарабатывают деньги, а не только крутят оборот."],
    ["Риск OOS", formatNumber(kpis.stockout_risk_count), "Сколько SKU имеют риск закончиться по текущему среднесуточному темпу. Высокое значение требует приоритизации закупки."],
    ["Залежавшиеся", formatNumber(kpis.stale_stock_count), "Сколько SKU лежат без движения в текущем окне. Это кандидаты на чистку, пересборку оффера или уценку."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", value));
    root.append(card);
  });
}

function renderContentAuditKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Карточек в аудите", formatNumber(kpis.total_skus), "Сколько карточек попало в текущий контент-аудит."],
    ["С продажами", formatNumber(kpis.sold_skus), "Сколько карточек из выборки имели продажи в текущем операционном контексте."],
    ["В приоритете", formatNumber(kpis.priority_cards_count), "Сколько карточек требуют самого раннего внимания по этому слою аудита."],
    [kpis.media_needs_work_count !== undefined ? "Медиа требует работы" : "Описание требует работы", formatNumber(kpis.media_needs_work_count ?? kpis.description_needs_work_count), "Общий слой карточек со средним, но не критичным уровнем проблем."],
    [kpis.photo_gap_count !== undefined ? "Отставание по фото" : "Тонкое описание", formatNumber(kpis.photo_gap_count ?? kpis.thin_content_count), kpis.photo_gap_count !== undefined ? "Gap здесь означает отставание от своей группы: насколько карточке не хватает фото до типичного уровня похожих товаров." : "Сколько карточек имеют слишком короткое описание."],
    [kpis.spec_gap_count !== undefined ? "Отставание по характеристикам" : "Отставание от группы", formatNumber(kpis.spec_gap_count ?? kpis.description_gap_count), kpis.spec_gap_count !== undefined ? "Gap здесь означает отставание от своей группы: насколько карточке не хватает характеристик относительно похожих товаров." : "Gap здесь означает отставание от медианы своей группы по объёму описания."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", value));
    root.append(card);
  });
}

function renderMarketKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Товаров в выборке", formatNumber(kpis.total_skus), "Сколько товаров удалось наблюдать в текущем рыночном проходе. Это не весь рынок, а текущая выборка."],
    ["Продавцов", formatNumber(kpis.observed_seller_count ?? kpis.stockout_risk_count), "Сколько продавцов встретилось в наблюдаемой выборке категории."],
    ["Групп", formatNumber(kpis.observed_group_count ?? kpis.stale_stock_count), "Сколько товарных групп реально проявились в наблюдаемой выборке."],
    ["Ценовых коридоров", formatNumber(kpis.observed_price_bands), "Сколько ценовых диапазонов занято товарами с продажами в текущем market scan."],
    ["Кластеры идей", formatNumber(kpis.observed_idea_clusters), "Сколько повторяющихся товарных идей удалось выделить эвристически. Полезно для поиска направлений расширения."],
    ["HHI концентрации", kpis.overall_dominance_hhi ?? "н/д", "HHI показывает, насколько рынок собран у немногих продавцов. Ниже 1500 обычно легче заходить, выше 2500 рынок уже плотный и концентрированный."],
    ["Индекс новизны", kpis.novelty_proxy_index ?? "н/д", "Это прокси, а не реальный возраст карточек. Он строится по связке orders/reviews у лидеров и показывает, насколько в категории ещё могут быстро расти новые карточки."],
    ["Доля «Прочее»", formatShare(kpis.other_group_share_pct), "Чем ниже доля «Прочее», тем точнее market-классификатор и тем надёжнее выводы по нишам."],
    ["Покрытие экономики", `${formatShare(kpis.economics_coverage_windows_pct)} окон`, "На какой доле окон входа система уже может сопоставить рыночную цену с вашей себестоимостью. Низкое покрытие означает: рынок виден, но выводы по прибыли ещё неполные."],
    ["Целевая маржа", kpis.target_margin_pct != null ? `${kpis.target_margin_pct}%` : "н/д", "Порог маржи, относительно которого оценивается, насколько рыночная цена вообще совместима с вашей экономикой."],
    ["Слепые зоны", formatNumber(kpis.blind_spot_windows_count), "Сколько окон входа выглядят интересными по спросу, но ещё не покрыты вашими cost-данными. Это список того, где нельзя принимать решение вслепую."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", value));
    root.append(card);
  });
}

function renderCompareKpis(rawPayload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const current = ((rawPayload.periods || {}).current_trailing_year || {});
  const metrics = current.metrics || {};
  const series = rawPayload.series_monthly || [];
  const historyWindow = rawPayload.history_window || {};
  const items = [
    ["Выручка за 365 дней", formatMoney(metrics.revenue_total || 0), "Главная выручка за текущее trailing-year окно."],
    ["Заказы за 365 дней", formatNumber(metrics.orders_total || 0), "Сколько заказов накопилось в текущем trailing-year окне."],
    ["Проданные единицы", formatNumber(metrics.items_sold_total || 0), "Сколько единиц товара продано за последние 365 дней."],
    ["Заполнено месяцев", formatNumber(series.length), "Сколько месяцев в monthly series уже содержат данные. Чем больше, тем надёжнее сезонные выводы."],
    ["Глубина истории", `${formatNumber(historyWindow.history_years || 0)} г.`, "На какую глубину уже запрашивается long-range история в CubeJS."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", value));
    root.append(card);
  });
}

function renderPricingKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Окон с рекомендацией", formatNumber(kpis.priced_windows_count), "Сколько сочетаний группа + ценовой коридор уже получили ценовую рекомендацию."],
    ["Агрессивный вход", formatNumber(kpis.aggressive_price_windows_count), "Окна, где можно держаться чуть ниже рынка и всё ещё удерживать целевую маржу."],
    ["Цена по рынку", formatNumber(kpis.market_price_windows_count), "Окна, где средняя цена рынка уже совместима с вашей экономикой."],
    ["Осторожный тест", formatNumber(kpis.test_price_windows_count), "Окна, где вход возможен, но цена должна быть аккуратнее средней по рынку."],
    ["Не демпинговать", formatNumber(kpis.do_not_discount_windows_count), "Окна, где для целевой маржи нужна цена выше текущего рынка."],
    ["Средний margin fit", kpis.avg_margin_fit_pct == null ? "н/д" : `${kpis.avg_margin_fit_pct}%`, "Средняя оценка совместимости рыночной цены с вашей экономикой по окнам, где уже хватает данных."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", String(value)));
    root.append(card);
  });
}

function renderSalesReturnKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Возвратов в окне", formatNumber(kpis.total_returns_count || 0), "Сумма возвратов по основной мере SalesReturn в выбранном окне."],
    ["Причин возврата", formatNumber(kpis.unique_return_reasons_count || 0), "Сколько разных причин возврата уже видно в текущем окне."],
    ["Строк без причины", formatNumber(kpis.rows_without_reason_count || 0), "Строки, где причина возврата не пришла или не была распознана."],
    ["Без идентификации", formatNumber(kpis.rows_without_identity_count || 0), "Строки, где возврат нельзя уверенно привязать к SKU или товару."],
    ["Доля главной причины", formatPercent(kpis.top_reason_share_pct || 0), "Какая доля всех возвратов приходится на самую частую причину. Чем выше значение, тем проще найти первый узкий сценарий для исправления."],
    ["Среднее на строку", formatNumber(kpis.avg_returns_per_row || 0), "Среднее число возвратов на одну строку отчёта. Это ориентир на плотность проблемы, а не целевой KPI."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", String(value)));
    root.append(card);
  });
}

function renderWaybillKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Строк накладной", formatNumber(kpis.waybill_rows_count || 0), "Сколько batch-строк удалось нормализовать из накладной или синтетического файла."],
    ["Identity с cost-историей", formatNumber(kpis.historical_cogs_items_count || 0), "Сколько товаров уже получили исторический слой себестоимости по barcode / sku / product_id."],
    ["Суммарный batch-cost", formatMoney(kpis.total_amount || 0), "Сумма себестоимости по всем нормализованным строкам текущей накладной."],
    ["Всего единиц в поставке", formatNumber(kpis.total_quantity_supplied || 0), "Сколько единиц товара пришло в текущем batch-layer."],
    ["Без идентификации", formatNumber(kpis.rows_without_identity_count || 0), "Строки, где не хватило barcode / sku / product_id для нормальной cost-связки."],
    ["Средняя unit cost", formatMoney(kpis.avg_amount_per_row || 0), "Средняя себестоимость одной единицы по строкам с распознанным cost-полем."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", String(value)));
    root.append(card);
  });
}

function renderPaidStorageKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Строк в отчёте", formatNumber(kpis.storage_rows_count ?? kpis.total_skus), "Сколько строк удалось прочитать из актуального XLSX отчёта по платному хранению и услугам."],
    ["Строк с суммой", formatNumber(kpis.rows_with_amount_count ?? kpis.sold_skus), "Сколько строк содержат явное числовое начисление и участвуют в суммарном платном слое."],
    ["Сумма начислений", formatMoney(kpis.total_amount ?? kpis.revenue_total), "Сумма по основной денежной колонке, которую система выбрала как главный слой начислений."],
    ["Штрафы и удержания", formatMoney(kpis.penalty_total || 0), "Сумма колонок, где заголовок похож на удержание, штраф или пеню. Это отдельный слой проверки, а не обычное хранение."],
    ["Без идентификации", formatNumber(kpis.rows_without_identity_count ?? kpis.stockout_risk_count), "Строки, где не удалось вытащить внятный SKU, артикул или понятное название. Такие начисления хуже объясняются менеджеру."],
    ["Средняя сумма на строку", formatMoney(kpis.avg_amount_per_row || 0), "Среднее начисление на одну строку с суммой. Это быстрый ориентир на плотность затрат, а не целевой KPI сам по себе."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", String(value)));
    root.append(card);
  });
}

function renderMarketingKpis(payload) {
  const root = document.getElementById("kpi-grid");
  root.innerHTML = "";
  const kpis = payload.kpis || {};
  const items = [
    ["Карточек в приоритете", formatNumber(kpis.priority_cards_count), "Сколько карточек попало в единый manager-facing маркетинговый аудит."],
    ["Ценовых ловушек", formatNumber(kpis.price_trap_cards_count), "Карточки, где цена висит чуть выше психологического порога."],
    ["Название требует работы", formatNumber(kpis.seo_needs_work_count), "Карточки со слабым SEO-сигналом по названию."],
    ["Критичных названий", formatNumber(kpis.seo_priority_fix_count), "Наиболее проблемные названия, которые стоит править первыми."],
    ["Карточек с рыночным контекстом", formatNumber(kpis.market_supported_cards_count), "Карточки, попавшие в группы и ценовые коридоры, где ценовой слой уже даёт рыночный контекст."],
    ["Двойных проблем", formatNumber(kpis.double_fix_count), "Карточки, где одновременно видны и слабый title, и ценовой trap."],
  ];
  items.forEach(([label, value, info]) => {
    const card = el("div", "kpi-card");
    const row = el("div", "label-row");
    row.append(el("p", "", label));
    row.append(createInfoIcon(info));
    card.append(row);
    card.append(el("strong", "", String(value)));
    root.append(card);
  });
}

function renderInsights(items) {
  const root = document.getElementById("insights-grid");
  root.innerHTML = "";
  (items || []).forEach((item) => {
    const card = el("div", "insight-card");
    if (item.tone) {
      card.dataset.tone = item.tone;
    }
    card.append(el("h3", "", item.title));
    card.append(el("p", "", item.text));
    root.append(card);
  });
}

function renderPriorityCards(item, payload, rawPayload) {
  const root = document.getElementById("priority-grid");
  const title = document.getElementById("priority-title");
  const subtitle = document.getElementById("priority-subtitle");
  root.innerHTML = "";
  const cards = [];
  if (item.report_kind === "competitor_market_analysis") {
    const actions = payload.actions || {};
    cards.push(
      {
        title: "Зайти в нишу",
        value: formatNumber((actions.enter_now_segments || []).length),
        subtitle: "Окон, где спрос и экономика уже выглядят рабочими",
        tone: (actions.enter_now_segments || []).length > 0 ? "good" : "warn",
      },
      {
        title: "Тестировать",
        value: formatNumber((actions.test_entry_segments || []).length),
        subtitle: "Окон, где уже можно делать точечные гипотезы",
        tone: (actions.test_entry_segments || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Добирать cost-данные",
        value: formatNumber((actions.blind_spots || []).length),
        subtitle: "Слепых зон, где решение нельзя принимать вслепую",
        tone: (actions.blind_spots || []).length > 0 ? "warn" : "good",
      },
      {
        title: "Не лезть / менять закупку",
        value: formatNumber((actions.sourcing_or_avoid_segments || []).length),
        subtitle: "Перегретых или экономически слабых окон",
        tone: (actions.sourcing_or_avoid_segments || []).length > 0 ? "bad" : "good",
      },
    );
    title.textContent = "Главные Рыночные Решения";
    subtitle.textContent = "Сначала выбери, куда входить, что тестировать и где экономика уже плохая.";
  } else if (item.report_kind === "dynamic_pricing") {
    const actions = payload.actions || {};
    cards.push(
      {
        title: "Входить агрессивно",
        value: formatNumber((actions.aggressive_price || []).length),
        subtitle: "Окна, где можно идти чуть ниже рынка и не ломать маржу",
        tone: (actions.aggressive_price || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Цена по рынку",
        value: formatNumber((actions.price_at_market || []).length),
        subtitle: "Окна, где средняя рыночная цена уже безопасна",
        tone: (actions.price_at_market || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Тестировать осторожно",
        value: formatNumber((actions.test_carefully || []).length),
        subtitle: "Окна, где цена должна быть выше рынка или оффер сильнее",
        tone: (actions.test_carefully || []).length > 0 ? "warn" : "neutral",
      },
      {
        title: "Не демпинговать",
        value: formatNumber((actions.protect_margin || []).length),
        subtitle: "Окна, где демпинг ломает целевую маржу",
        tone: (actions.protect_margin || []).length > 0 ? "bad" : "good",
      },
    );
    title.textContent = "Главные Решения По Ценам";
    subtitle.textContent = "Сначала раздели окна на агрессивный вход, цену по рынку, осторожный тест и no-discount.";
  } else if (item.report_kind === "marketing_card_audit") {
    const actions = payload.actions || {};
    cards.push(
      {
        title: "Исправить сейчас",
        value: formatNumber((actions.fix_now || []).length),
        subtitle: "Карточки с двойной проблемой: цена и title",
        tone: (actions.fix_now || []).length > 0 ? "warn" : "good",
      },
      {
        title: "Тест цены",
        value: formatNumber((actions.price_tests || []).length),
        subtitle: "Карточки рядом с сильными ценовыми порогами",
        tone: (actions.price_tests || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Переписать title",
        value: formatNumber((actions.title_fixes || []).length),
        subtitle: "Карточки со слабым поисковым сигналом",
        tone: (actions.title_fixes || []).length > 0 ? "warn" : "neutral",
      },
      {
        title: "Рынок поддерживает",
        value: formatNumber((actions.market_supported || []).length),
        subtitle: "Карточки в окнах с рабочим pricing context",
        tone: (actions.market_supported || []).length > 0 ? "good" : "neutral",
      },
    );
    title.textContent = "Главные Решения По Карточкам";
    subtitle.textContent = "Сначала выбери, где чинить цену, где переписывать title и где рынок уже поддерживает тест.";
  } else if (item.report_kind === "cubejs_period_compare") {
    const periods = rawPayload.periods || {};
    const current = (periods.current_trailing_year || {}).metrics || {};
    const previous = ((periods.previous_year_same_window || {}).metrics || {});
    const ytd = ((periods.current_ytd || {}).metrics || {});
    const previousYtd = ((periods.previous_ytd || {}).metrics || {});
    const seriesMonths = (rawPayload.series_monthly || []).length;
    cards.push(
      {
        title: "Trailing year",
        value: formatMoney(current.revenue_total || 0),
        subtitle: "Главная база выручки за последние 365 дней",
        tone: "good",
      },
      {
        title: "YoY готовность",
        value: previous.revenue_total ? "есть база" : "недостаточно",
        subtitle: "Можно ли уже честно читать год-к-году",
        tone: previous.revenue_total ? "good" : "warn",
      },
      {
        title: "YTD база",
        value: formatMoney(ytd.revenue_total || 0),
        subtitle: previousYtd.revenue_total ? "Есть и прошлый YTD" : "Предыдущий YTD ещё пустой",
        tone: previousYtd.revenue_total ? "good" : "warn",
      },
      {
        title: "Месяцев истории",
        value: formatNumber(seriesMonths),
        subtitle: "Для seasonality и YoY желательно 12-18 ненулевых месяцев",
        tone: seriesMonths >= 12 ? "good" : "warn",
      },
    );
    title.textContent = "Главные Сигналы Истории";
    subtitle.textContent = "Сначала смотри зрелость временного ряда, а уже потом делай выводы о динамике.";
  } else if (item.report_kind === "paid_storage_report") {
    const actions = payload.actions || {};
    const kpis = payload.kpis || {};
    cards.push(
      {
        title: "Крупные начисления",
        value: formatNumber((actions.reorder_now || []).length),
        subtitle: "Строки, которые нужно разбирать первыми",
        tone: (actions.reorder_now || []).length > 0 ? "warn" : "neutral",
      },
      {
        title: "Без идентификации",
        value: formatNumber(kpis.rows_without_identity_count || 0),
        subtitle: "Строки без понятного SKU или названия",
        tone: (kpis.rows_without_identity_count || 0) > 0 ? "warn" : "good",
      },
      {
        title: "Сумма начислений",
        value: formatMoney(kpis.total_amount || 0),
        subtitle: "Главный денежный слой текущего файла",
        tone: "good",
      },
      {
        title: "Удержания",
        value: formatMoney(kpis.penalty_total || 0),
        subtitle: "Похожие на штрафы и удержания колонки",
        tone: (kpis.penalty_total || 0) > 0 ? "warn" : "neutral",
      },
    );
    title.textContent = "Главные Решения По Платному Слою";
    subtitle.textContent = "Сначала разбери крупнейшие начисления и строки без идентификации, потом уходи в расшифровку колонок.";
  } else if (item.report_kind === "sales_return_report") {
    const actions = payload.actions || {};
    const kpis = payload.kpis || {};
    cards.push(
      {
        title: "Возвратов в окне",
        value: formatNumber(kpis.total_returns_count || 0),
        subtitle: "Сумма возвратов по основной мере CubeJS",
        tone: (kpis.total_returns_count || 0) > 0 ? "warn" : "neutral",
      },
      {
        title: "Причин возврата",
        value: formatNumber(kpis.unique_return_reasons_count || 0),
        subtitle: "Сколько разных причин видно в текущем окне",
        tone: (kpis.unique_return_reasons_count || 0) > 0 ? "good" : "neutral",
      },
      {
        title: "Главная причина",
        value: formatPercent(kpis.top_reason_share_pct || 0),
        subtitle: "Доля возвратов, которую даёт самая частая причина",
        tone: (kpis.top_reason_share_pct || 0) >= 40 ? "warn" : "good",
      },
      {
        title: "Без идентификации",
        value: formatNumber(kpis.rows_without_identity_count || 0),
        subtitle: "Строки, где возврат не удалось уверенно привязать к товару",
        tone: (kpis.rows_without_identity_count || 0) > 0 ? "warn" : "good",
      },
    );
    title.textContent = "Главные Решения По Возвратам";
    subtitle.textContent = "Сначала разбери доминирующую причину и самые тяжёлые SKU, потом уходи в хвост и пробелы данных.";
  } else {
    const actions = payload.actions || {};
    const kpis = payload.kpis || {};
    cards.push(
      {
        title: "Заказать",
        value: formatNumber((actions.reorder_now || []).length),
        subtitle: "SKU, которые уже проходят жёсткий порог на дозакупку",
        tone: (actions.reorder_now || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Снизить цену / чистить",
        value: formatNumber((actions.markdown_candidates || []).length),
        subtitle: "Кандидаты на уценку и расчистку хвоста",
        tone: (actions.markdown_candidates || []).length > 0 ? "warn" : "good",
      },
      {
        title: "Беречь",
        value: formatNumber((actions.protect_winners || []).length || (actions.watchlist_signals || []).length),
        subtitle: (actions.protect_winners || []).length ? "Победители по прибыли" : "Живые сигналы для ручного контроля",
        tone: (actions.protect_winners || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Потери из-за OOS",
        value: formatNumber(kpis.estimated_lost_units_oos_total || 0),
        subtitle: "Proxy-оценка потерянных единиц из-за отсутствия в наличии",
        tone: (kpis.estimated_lost_units_oos_total || 0) > 0 ? "warn" : "good",
      },
    );
    title.textContent = "Главные Операционные Действия";
    subtitle.textContent = "Сначала реши, что заказывать, что чистить и где магазин уже теряет спрос из-за отсутствия товара.";
  }
  cards.forEach((row) => {
    const card = el("div", "compare-card priority-card");
    if (row.tone) card.dataset.tone = row.tone;
    card.append(el("span", "badge", row.title));
    card.append(el("strong", "", row.value));
    card.append(el("p", "", row.subtitle));
    root.append(card);
  });
}

function renderActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Заказать сейчас", subtitle: "SKU с риском нехватки", rows: (actions.reorder_now || []).slice(0, 8), formatter: (row) => `остаток ${row.total_stock}, покрытие ${row.stock_cover_days ?? "∞"} дн., среднесуточно ${row.avg_daily_sales_official}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Кандидаты на уценку", subtitle: "Товары без движения", rows: (actions.markdown_candidates || []).slice(0, 8), formatter: (row) => `остаток ${row.total_stock}, стоимость ${formatMoney(row.stock_value_sale)}`, getDisplayTitle, createEntityActionButtons });
  const protectRows = (actions.protect_winners || []).length ? (actions.protect_winners || []) : (actions.watchlist_signals || []);
  const protectTitle = (actions.protect_winners || []).length ? "Беречь победителей" : "Смотреть сигналы";
  const protectSubtitle = (actions.protect_winners || []).length ? "Лидеры по текущей прибыли" : "Пока не победители, но уже живые позиции";
  renderActionCard({ root: document.getElementById("action-protect"), title: protectTitle, subtitle: protectSubtitle, rows: protectRows.slice(0, 8), formatter: (row) => `прибыль ${formatMoney(row.gross_profit)}, продано ${row.units_sold}`, getDisplayTitle, createEntityActionButtons });
}

function renderMarketActions(payload) {
  const actions = payload.actions || {};
  const enterRows = (actions.enter_now_segments || []).length ? actions.enter_now_segments : (actions.entry_watchlist || []);
  const testRows = (actions.test_entry_segments || []).length ? actions.test_entry_segments : [];
  const noGoRows = (actions.sourcing_or_avoid_segments || []).length
    ? actions.sourcing_or_avoid_segments
    : ((actions.weak_margin_segments || []).length ? actions.weak_margin_segments : (actions.too_hot_segments || []));
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Входить первым", subtitle: "Окна, где спрос, структура рынка и экономика уже выглядят рабочими", rows: enterRows.slice(0, 8), formatter: (row) => `${row.group} / ${row.price_band}, score ${row.entry_window_score}, решение ${row.entry_strategy_label || "н/д"}, margin fit ${row.market_margin_fit_pct ?? "н/д"}%`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Тестировать точечно", subtitle: "Окна, где вход возможен, но уже нужен контроль экономики или сильный оффер", rows: testRows.slice(0, 8), formatter: (row) => `${row.group} / ${row.price_band}, решение ${row.entry_strategy_label || "н/д"}, HHI ${row.dominance_hhi ?? "н/д"}, margin fit ${row.market_margin_fit_pct ?? "н/д"}%`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Не входить или менять закупку", subtitle: "Окна, где сегмент перегрет или рыночная цена не бьётся с вашей целевой маржой", rows: noGoRows.slice(0, 8), formatter: (row) => `${row.group} / ${row.price_band}, решение ${row.entry_strategy_label || "н/д"}, margin fit ${row.market_margin_fit_pct ?? "н/д"}%, HHI ${row.dominance_hhi ?? "н/д"}`, getDisplayTitle, createEntityActionButtons });
}

function renderPricingActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Агрессивно входить", subtitle: "Окна, где можно держаться чуть ниже рынка и всё ещё сохранять целевую маржу", rows: (actions.aggressive_price || []).slice(0, 8), formatter: (row) => `${row.group || "н/д"} / ${row.price_band || "н/д"}, рынок ${formatMoney(row.avg_market_price)}, безопасно от ${formatMoney(row.min_safe_price)}, рекомендация ${formatMoney(row.suggested_price)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Цена по рынку / осторожный тест", subtitle: "Окна, где можно держаться рынка или проверять более осторожный price point", rows: [...(actions.price_at_market || []), ...(actions.test_carefully || [])].slice(0, 8), formatter: (row) => `${row.group || "н/д"} / ${row.price_band || "н/д"}, ярлык ${row.pricing_label || "н/д"}, рынок ${formatMoney(row.avg_market_price)}, рекомендация ${formatMoney(row.suggested_price)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Беречь маржу", subtitle: "Окна, где нельзя демпинговать, иначе целевая маржа разрушается", rows: (actions.protect_margin || []).slice(0, 8), formatter: (row) => `${row.group || "н/д"} / ${row.price_band || "н/д"}, безопасно не ниже ${formatMoney(row.min_safe_price)}, рынок ${formatMoney(row.avg_market_price)}`, getDisplayTitle, createEntityActionButtons });
}

function renderMarketingActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Исправить сейчас", subtitle: "Карточки, где одновременно слабый title и неудачный ценовой point", rows: (actions.fix_now || []).slice(0, 8), formatter: (row) => `${row.group || "н/д"} / ${row.price_band || "н/д"}, ${row.action_reason || "н/д"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Тест цены", subtitle: "Карточки рядом с психологическими порогами", rows: (actions.price_tests || []).slice(0, 8), formatter: (row) => `цена ${formatMoney(row.sale_price)}, порог ${formatMoney(row.threshold || 0)}, тест ${formatMoney(row.suggested_threshold_price || row.sale_price)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Переписать title", subtitle: "Карточки, где контент даёт слабый поисковый сигнал", rows: (actions.title_fixes || []).slice(0, 8), formatter: (row) => `SEO ${row.seo_status || "н/д"} / ${row.seo_score ?? "н/д"}, issues: ${(row.seo_issues || []).join(", ") || "н/д"}`, getDisplayTitle, createEntityActionButtons });
}

function renderMediaActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Срочно усилить медиа", subtitle: "Карточки с самым явным отставанием по фото или характеристикам относительно своей группы", rows: (actions.fix_now || []).slice(0, 8), formatter: (row) => `media ${row.media_status || "н/д"} / ${row.media_score ?? "н/д"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Визуальные отставания", subtitle: "Gap здесь означает разницу с типичным уровнем своей группы", rows: (actions.visual_gaps || []).slice(0, 8), formatter: (row) => `отставание по фото ${row.photo_gap_vs_group ?? 0}, по характеристикам ${row.spec_gap_vs_group ?? 0}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Сильные примеры", subtitle: "Внутренние ориентиры по карточкам", rows: (actions.strong_examples || []).slice(0, 8), formatter: (row) => `фото ${row.photo_count}, spec ${row.spec_count}, видео ${row.video_count}`, getDisplayTitle, createEntityActionButtons });
}

function renderDescriptionActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Срочно переписать описание", subtitle: "Карточки с наиболее слабым description-layer", rows: (actions.fix_now || []).slice(0, 8), formatter: (row) => `description ${row.description_status || "н/д"} / ${row.description_score ?? "н/д"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Тонкие описания", subtitle: "Слишком короткие описания", rows: (actions.thin_content || []).slice(0, 8), formatter: (row) => `${row.description_chars ?? 0} симв., coverage ${row.title_term_coverage_pct ?? "н/д"}%`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Сильные примеры", subtitle: "Внутренние ориентиры по описаниям", rows: (actions.strong_examples || []).slice(0, 8), formatter: (row) => `${row.description_chars ?? 0} симв., coverage ${row.title_term_coverage_pct ?? "н/д"}%`, getDisplayTitle, createEntityActionButtons });
}

function renderSalesReturnActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Разобрать сейчас", subtitle: "SKU и причины, где возвраты концентрируются сильнее всего", rows: (actions.investigate_now || []).slice(0, 8), formatter: (row) => `${row.reason || "Без причины"} · возвратов ${formatNumber(row.return_count || 0)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Очаги по причинам", subtitle: "Причины возврата, которые уже формируют основную массу проблемы", rows: (actions.reason_hotspots || []).slice(0, 8), formatter: (row) => `возвратов ${formatNumber(row.return_count || 0)}${row.amount_value ? ` · сумма ${formatMoney(row.amount_value)}` : ""}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Пробелы данных", subtitle: "Строки без уверенной привязки к товару", rows: (actions.identity_gaps || []).slice(0, 8), formatter: (row) => `${row.reason || "Без причины"} · возвратов ${formatNumber(row.return_count || 0)}`, getDisplayTitle, createEntityActionButtons });
}

function renderWaybillActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Последние и дорогие партии", subtitle: "Batch-строки, которые первыми влияют на cost-layer и требуют сверки", rows: (actions.reorder_now || []).slice(0, 8), formatter: (row) => `batch ${formatMoney(row.batch_cogs_total || 0)} · qty ${formatNumber(row.quantity_supplied || 0)} · unit ${formatMoney(row.unit_cogs || 0)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Волатильность себестоимости", subtitle: "Identity, где себестоимость уже менялась между партиями", rows: (actions.markdown_candidates || []).slice(0, 8), formatter: (row) => `latest ${formatMoney(row.latest_unit_cogs || 0)} · avg ${formatMoney(row.avg_unit_cogs || 0)} · batches ${formatNumber(row.batch_count || 0)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Крупнейшие batch-cost строки", subtitle: "Самые тяжёлые по сумме строки текущего слоя накладных", rows: (actions.protect_winners || []).slice(0, 8), formatter: (row) => `batch ${formatMoney(row.batch_cogs_total || 0)} · qty ${formatNumber(row.quantity_supplied || 0)}`, getDisplayTitle, createEntityActionButtons });
}

function renderPaidStorageActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Крупнейшие начисления", subtitle: "Строки, где накопился наибольший платный слой", rows: (actions.reorder_now || []).slice(0, 8), formatter: (row) => `${row.amount_label || "сумма"} ${formatMoney(row.amount || 0)}${row.identity ? ` · ${row.identity}` : ""}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Проверить вручную", subtitle: "Строки без явного SKU или понятной идентификации", rows: (actions.markdown_candidates || []).slice(0, 8), formatter: (row) => `${row.amount_label || "сумма"} ${formatMoney(row.amount || 0)} · identity ${row.identity || "н/д"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Высокие начисления", subtitle: "Строки, где сумма уже явно выше основного массива", rows: (actions.protect_winners || []).slice(0, 8), formatter: (row) => `${row.amount_label || "сумма"} ${formatMoney(row.amount || 0)}${row.identity ? ` · ${row.identity}` : ""}`, getDisplayTitle, createEntityActionButtons });
}

function buildEntityPayload(row, context) {
  const title = getDisplayTitle(row);
  const hasSkuIdentity = Boolean(row.key || row.product_id || row.barcode);
  const hasSellerIdentity = Boolean(row.seller_title && !row.title);
  return {
    title,
    entity_key: String(
      row.family_key ||
      row.key ||
      row.product_id ||
      row.seller_id ||
      row.seller_title ||
      `${title}::${context || "general"}`
    ),
    entity_type: row.family_key ? "family" : hasSkuIdentity ? "sku" : hasSellerIdentity ? "seller" : row.group ? "market_segment" : "sku",
    report_kind: currentDashboardItem?.report_kind || "unknown",
    context: context || "",
  };
}

async function refreshActionCenter() {
  actionCenterState = await loadActionCenter();
  renderActionCenter();
  renderManagerQueues();
  renderEntityDetail();
}

function createActionButton(label, className, onClick) {
  const button = el("button", `mini-action-button ${className}`, label);
  button.type = "button";
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    button.disabled = true;
    try {
      await onClick();
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

function createEntityActionButtons(row, context) {
  const wrap = el("div", "entity-actions");
  wrap.append(
    createActionButton("Детали", "secondary", async () => {
      const payload = buildEntityPayload(row, context);
      selectedEntityKey = payload.entity_key;
      renderEntityDetail(row);
      const panel = document.getElementById("entity-detail-panel");
      if (panel) {
        panel.classList.remove("panel-pulse");
        void panel.offsetWidth;
        panel.classList.add("panel-pulse");
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }),
    createActionButton("В список", "secondary", async () => {
      const payload = buildEntityPayload(row, context);
      await addWatchlistItem(payload);
      await refreshActionCenter();
    }),
    createActionButton("Задача", "primary", async () => {
      const note = window.prompt("Короткая задача или заметка", "") || "";
      const owner = window.prompt("Ответственный по задаче", getStoredActionOwner()) || "";
      setStoredActionOwner(owner.trim());
      const payload = { ...buildEntityPayload(row, context), note, owner: owner.trim(), status: "open" };
      await addActionItem(payload);
      await refreshActionCenter();
    }),
  );
  return wrap;
}

function findEntityHistory(entityKey) {
  const entities = entityHistoryIndex?.entities || [];
  return entities.find((row) => row.entity_key === entityKey) || null;
}

function summarizeEntityActionState(entityKey) {
  const store = actionCenterState || {};
  const watch = (store.watchlists || []).find((row) => row.entity_key === entityKey) || null;
  const actions = (store.actions || []).filter((row) => row.entity_key === entityKey);
  const acknowledgement = (store.acknowledgements || []).find((row) => row.entity_key === entityKey) || null;
  const events = (store.events || []).filter((row) => row.entity_key === entityKey);
  return {
    watch,
    actions,
    acknowledgement,
    events,
    openCount: actions.filter((row) => row.status !== "done").length,
    doneCount: actions.filter((row) => row.status === "done").length,
  };
}

function filterActionRows(rows) {
  const filter = selectedActionFilter || "all";
  if (filter === "all") return rows;
  if (filter === "open") return rows.filter((row) => row.status === "open");
  if (filter === "in_progress") return rows.filter((row) => row.status === "in_progress");
  if (filter === "blocked") return rows.filter((row) => row.status === "blocked");
  if (filter === "done") return rows.filter((row) => row.status === "done");
  if (filter === "mine") {
    const owner = getStoredActionOwner();
    return owner ? rows.filter((row) => (row.owner || "") === owner) : rows;
  }
  return rows;
}

function summarizeActionOwners(rows) {
  const buckets = new Map();
  rows.forEach((row) => {
    const owner = row.owner || "без ответственного";
    const current = buckets.get(owner) || { owner, open: 0, in_progress: 0, blocked: 0, done: 0, total: 0 };
    current.total += 1;
    const status = row.status || "open";
    current[status] = (current[status] || 0) + 1;
    buckets.set(owner, current);
  });
  return Array.from(buckets.values()).sort((a, b) => (b.open + b.in_progress + b.blocked) - (a.open + a.in_progress + a.blocked));
}

function summarizeActionStatuses(rows) {
  const counts = { open: 0, in_progress: 0, blocked: 0, done: 0 };
  rows.forEach((row) => {
    const status = row.status || "open";
    counts[status] = (counts[status] || 0) + 1;
  });
  return [
    { key: "Новые", value: counts.open },
    { key: "В работе", value: counts.in_progress },
    { key: "Блокеры", value: counts.blocked },
    { key: "Готово", value: counts.done },
  ];
}

function renderActionCenterToolbar() {
  const root = document.getElementById("action-center-toolbar");
  if (!root) return;
  root.innerHTML = "";
  const wrap = el("div", "inline-form");
  const ownerInput = el("input", "inline-input");
  ownerInput.type = "text";
  ownerInput.placeholder = "Мой ответственный";
  ownerInput.value = getStoredActionOwner();
  ownerInput.addEventListener("change", () => {
    setStoredActionOwner(ownerInput.value.trim());
    renderActionCenter();
  });
  const filterSelect = el("select", "inline-select");
  [
    ["all", "Все задачи"],
    ["open", "Новые"],
    ["in_progress", "В работе"],
    ["blocked", "Блокеры"],
    ["done", "Готово"],
    ["mine", "Только мои"],
  ].forEach(([value, label]) => {
    const option = el("option", "", label);
    option.value = value;
    if (selectedActionFilter === value) option.selected = true;
    filterSelect.append(option);
  });
  filterSelect.addEventListener("change", () => {
    selectedActionFilter = filterSelect.value;
    setStoredActionFilter(selectedActionFilter);
    renderActionCenter();
  });
  const saveButton = createActionButton("Сохранить представление", "secondary", async () => {
    const name = window.prompt("Название сохранённого представления", "") || "";
    if (!name.trim()) return;
    await saveActionView({
      name: name.trim(),
      filters: { filter: selectedActionFilter, owner: getStoredActionOwner() },
    });
    await refreshActionCenter();
  });
  wrap.append(ownerInput, filterSelect, saveButton);
  root.append(wrap);
  root.append(el("p", "job-card-text", "Рабочий цикл сейчас такой: выбрал сущность в отчёте → добавил в список наблюдения или создал задачу → вручную перевёл статус → при фактическом завершении закрыл задачу."));
}

function renderManagerQueues() {
  const statusRoot = document.getElementById("queue-status-panel");
  const ownerRoot = document.getElementById("queue-owner-panel");
  const viewRoot = document.getElementById("queue-view-panel");
  [statusRoot, ownerRoot, viewRoot].forEach((node) => {
    if (node) node.innerHTML = "";
  });
  if (!statusRoot || !ownerRoot || !viewRoot || !actionCenterState) return;

  const allActions = actionCenterState.actions || [];

  const statusCard = el("div", "list-card");
  appendHeadingWithInfo(statusCard, "h3", "Очередь по статусам", "Показывает, где узкое место цикла: новые задачи, активная работа, блокеры или уже закрытые элементы.");
  const statusList = el("ul", "compact-list");
  summarizeActionStatuses(allActions).forEach((row) => {
    const item = el("li");
    item.append(el("strong", "", row.key));
    item.append(el("span", "", `${formatNumber(row.value)} задач`));
    statusList.append(item);
  });
  statusCard.append(statusList);
  statusRoot.append(statusCard);

  const ownerCard = el("div", "list-card");
  appendHeadingWithInfo(ownerCard, "h3", "Очередь по ответственным", "Показывает нагрузку и блокеры по ответственным. Даже в single-user режиме это полезно как задел под manager workflow.");
  const ownerRows = summarizeActionOwners(allActions);
  if (!ownerRows.length) {
    ownerCard.append(el("p", "empty-state", "Назначенных ответственных пока нет."));
  } else {
    const ownerList = el("ul", "compact-list");
    ownerRows.slice(0, 8).forEach((row) => {
      const item = el("li");
      item.append(el("strong", "", row.owner));
      item.append(el("span", "", `новые ${row.open}, в работе ${row.in_progress}, блокеры ${row.blocked}, завершено ${row.done}`));
      ownerList.append(item);
    });
    ownerCard.append(ownerList);
  }
  ownerRoot.append(ownerCard);

  const viewCard = el("div", "list-card");
  appendHeadingWithInfo(viewCard, "h3", "Сохранённые представления", "Сохранённые управленческие очереди. Это быстрые режимы работы для ежедневного follow-up.");
  const savedViews = actionCenterState.saved_views || [];
  if (!savedViews.length) {
    viewCard.append(el("p", "empty-state", "Сохранённых представлений пока нет."));
  } else {
    const viewList = el("ul", "compact-list");
    savedViews.slice(0, 8).forEach((row) => {
      const item = el("li");
      const content = el("div", "list-item-main");
      content.append(el("strong", "", row.name));
      content.append(el("span", "", `фильтр ${row.filters?.filter || "all"}${row.filters?.owner ? ` · ответственный ${row.filters.owner}` : ""}`));
      item.append(content);
      const jump = createActionButton("Открыть", "secondary", async () => {
        selectedActionFilter = row.filters?.filter || "all";
        setStoredActionFilter(selectedActionFilter);
        if (row.filters?.owner !== undefined) {
          setStoredActionOwner(row.filters.owner || "");
        }
        renderActionCenter();
        const panel = document.getElementById("action-center-panel");
        if (panel) {
          panel.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
      item.append(jump);
      viewList.append(item);
    });
    viewCard.append(viewList);
  }
  viewRoot.append(viewCard);
}

function formatEventType(eventType) {
  const labels = {
    watchlist_added: "Добавлено в список",
    watchlist_updated: "Обновлён список",
    action_added: "Создана задача",
    action_updated: "Обновлена задача",
    action_toggled: "Изменён статус задачи",
    acknowledged: "Подтверждён разбор",
  };
  return labels[eventType] || eventType || "Событие";
}

function renderHistorySparkline(history) {
  const wrap = el("div", "entity-spark-wrap");
  if (!history.length) return wrap;
  const scores = history.slice(0, 8).map((r) => Number(r.priority_score ?? 0));
  const max = Math.max(...scores, 1);
  scores.forEach((score, i) => {
    const bar = el("div", "entity-spark-bar");
    const pct = Math.max(10, Math.round((score / max) * 100));
    bar.style.height = `${pct}%`;
    bar.title = `${history[i]?.report_name?.slice(0, 20) || "отчёт"}: score ${score}`;
    wrap.append(bar);
  });
  return wrap;
}

function countCrossReportKinds(history) {
  const kinds = new Set(history.map((r) => r.report_kind || r.report_name).filter(Boolean));
  return kinds.size;
}

function renderEntityDetail(fallbackRow = null) {
  const root = document.getElementById("entity-detail-root");
  if (!root) return;
  root.innerHTML = "";
  if (!selectedEntityKey) {
    root.append(el("p", "empty-state", "Выбери «Детали» у строки отчёта, чтобы открыть историю сущности и её ручной статус."));
    return;
  }
  const entity = findEntityHistory(selectedEntityKey);
  const effectiveTitle = entity?.title || fallbackRow?.title || selectedEntityKey;
  const status = summarizeEntityActionState(selectedEntityKey);
  const history = entity?.history || [];
  const latest = entity?.latest && Object.keys(entity.latest || {}).length ? entity.latest : (history[0] || {});
  const resolvedSku = pickEntityValue(latest, history, fallbackRow, ["sku", "seller_sku_id", "barcode", "product_id"]);
  const resolvedActionLabel = pickEntityValue(latest, history, fallbackRow, ["action_label"]);
  const resolvedGroup = pickEntityValue(latest, history, fallbackRow, ["group"]);
  const resolvedPriceBand = pickEntityValue(latest, history, fallbackRow, ["price_band"]);
  const resolvedSeoStatus = pickEntityValue(latest, history, fallbackRow, ["seo_status"]);
  const resolvedPricingLabel = pickEntityValue(latest, history, fallbackRow, ["pricing_label"]);
  const resolvedPriceTrap = pickEntityValue(latest, history, fallbackRow, ["price_trap"], ["", null, undefined]);
  const navIndex = currentEntityRows.findIndex((item) => item.entity_key === selectedEntityKey);
  const prevEntity = navIndex > 0 ? currentEntityRows[navIndex - 1] : null;
  const nextEntity = navIndex >= 0 && navIndex < currentEntityRows.length - 1 ? currentEntityRows[navIndex + 1] : null;
  const renderEntityNavigator = () => {
    if (!prevEntity && !nextEntity) return null;
    const navRow = el("div", "entity-actions");
    if (prevEntity) {
      navRow.append(createActionButton("← Предыдущая", "secondary", async () => {
        selectedEntityKey = prevEntity.entity_key;
        renderEntityDetail(prevEntity.row);
      }));
    }
    if (nextEntity) {
      navRow.append(createActionButton("Следующая →", "secondary", async () => {
        selectedEntityKey = nextEntity.entity_key;
        renderEntityDetail(nextEntity.row);
      }));
    }
    return navRow;
  };

  const summaryGrid = el("div", "entity-detail-grid");
  const card1 = el("div", "list-card");

  // Header row: title + position indicator
  const titleRow = el("div", "entity-title-row");
  const titleEl = el("h3", "", effectiveTitle);
  titleRow.append(titleEl);
  if (navIndex >= 0) {
    const pos = el("span", "entity-position-badge", `${navIndex + 1} / ${currentEntityRows.length}`);
    pos.title = "Позиция в текущем списке сущностей";
    titleRow.append(pos);
  }
  const crossKindCount = countCrossReportKinds(history);
  if (crossKindCount > 1) {
    const badge = el("span", "entity-cross-badge", `${crossKindCount} отчёта`);
    badge.title = `Сущность встречалась в ${crossKindCount} разных типах отчётов`;
    titleRow.append(badge);
  }
  card1.append(titleRow);

  // (i) info icon via appendHeadingWithInfo — attach as sub-note
  const infoNote = el("p", "entity-info-note", "Текущий срез по сущности: latest marketing signal плюс ручной follow-up.");
  card1.append(infoNote);

  const topNavigator = renderEntityNavigator();
  if (topNavigator) {
    card1.append(topNavigator);
  }

  // Core fields
  card1.append(el("p", "", `Тип: ${latest.group ? "карточка / SKU" : "сущность"}`));
  if (resolvedSku) {
    card1.append(el("p", "", `SKU: ${resolvedSku}`));
  }
  card1.append(el("p", "", `Последний сигнал: ${resolvedActionLabel || "н/д"}`));
  card1.append(el("p", "", `Группа / коридор: ${resolvedGroup || "н/д"} / ${resolvedPriceBand || "н/д"}`));
  card1.append(el("p", "", `Ценовая ловушка: ${resolvedPriceTrap ? "да" : "нет"} · SEO: ${resolvedSeoStatus || "н/д"} · Ценовой статус: ${resolvedPricingLabel || "н/д"}`));
  if (!resolvedActionLabel || !resolvedGroup || !resolvedPricingLabel) {
    card1.append(el("p", "job-card-text", "Часть полей берётся из накопленной истории. Если в текущем срезе пусто, панель пытается восстановить последнее осмысленное значение."));
  }

  // History sparkline
  if (history.length > 1) {
    const sparkRow = el("div", "entity-spark-row");
    sparkRow.append(el("span", "entity-spark-label", "История score:"));
    sparkRow.append(renderHistorySparkline(history));
    const latest_score = history[0]?.priority_score;
    if (latest_score != null) {
      sparkRow.append(el("span", "entity-spark-value", String(latest_score)));
    }
    card1.append(sparkRow);
  }

  summaryGrid.append(card1);

  const card2 = el("div", "list-card");
  appendHeadingWithInfo(card2, "h3", "Ручной статус", "Показывает, что менеджер уже сделал по этой сущности: watchlist, открытые и закрытые задачи.");
  card2.append(el("p", "", `В списке наблюдения: ${status.watch ? "да" : "нет"}`));
  card2.append(el("p", "", `Открытых задач: ${formatNumber(status.openCount)}`));
  card2.append(el("p", "", `Закрытых задач: ${formatNumber(status.doneCount)}`));
  if (status.watch?.context) {
    card2.append(el("p", "", `Контекст watchlist: ${status.watch.context}`));
  }
  if (status.acknowledgement?.acknowledged_at) {
    card2.append(el("p", "", `Подтверждено: ${String(status.acknowledgement.acknowledged_at).slice(0, 19).replace("T", " ")}`));
  }
  if (status.acknowledgement?.note) {
    card2.append(el("p", "", `Комментарий разбора: ${status.acknowledgement.note}`));
  }
  if (status.actions[0]?.note) {
    card2.append(el("p", "", `Последняя заметка: ${status.actions[0].note}`));
  }
  const ackButton = createActionButton("Подтвердить разбор", "primary", async () => {
    const note = window.prompt("Короткий комментарий по разбору карточки", status.acknowledgement?.note || "") || "";
    await acknowledgeEntity({
      entity_key: selectedEntityKey,
      title: effectiveTitle,
      entity_type: latest.entity_key ? "sku" : "unknown",
      report_kind: currentDashboardItem?.report_kind || "unknown",
      context: latest.action_label || "",
      note,
    });
    await refreshActionCenter();
  });
  card2.append(ackButton);
  summaryGrid.append(card2);
  root.append(summaryGrid);

  // Keyboard hint (show only when there are neighbours)
  if (navIndex >= 0 && currentEntityRows.length > 1) {
    const hint = el("p", "entity-key-hint");
    hint.innerHTML = `Навигация: <kbd>←</kbd><kbd>→</kbd> — пред./след. сущность &nbsp;·&nbsp; <kbd>Esc</kbd> — закрыть`;
    root.append(hint);
  }

  const historyCard = el("div", "list-card");
  appendHeadingWithInfo(historyCard, "h3", "История сигналов", "Это лента появления сущности в отчётах. Она нужна, чтобы понять: сигнал новый, повторяющийся или устойчивый. По ней решают, усиливать карточку, ставить follow-up или считать шумом.");
  if (!history.length) {
    historyCard.append(el("p", "empty-state", "История по этой сущности пока не накоплена."));
  } else {
    const list = el("div", "entity-history-list");
    history.slice(0, 8).forEach((row) => {
      const item = el("div", "history-row");
      item.append(el("strong", "", `${row.report_name} · ${String(row.generated_at || "н/д").slice(0, 10)}`));
      item.append(el("span", "", `${row.action_label || "н/д"} · score ${row.priority_score ?? "н/д"} · ${row.group || "н/д"} / ${row.price_band || "н/д"}`));
      item.append(el("span", "", `ценовая ловушка: ${row.price_trap ? "да" : "нет"} · SEO: ${row.seo_status || "н/д"} · ценовой статус: ${row.pricing_label || "н/д"}`));
      list.append(item);
    });
    historyCard.append(list);
  }
  root.append(historyCard);

  const decisionCard = el("div", "list-card");
  appendHeadingWithInfo(decisionCard, "h3", "История управленческих решений", "Журнал ручных действий по сущности: watchlist, задачи, переключение статуса и подтверждение разбора.");
  if (!status.events.length) {
    decisionCard.append(el("p", "empty-state", "По этой сущности ещё нет ручной истории решений."));
  } else {
    const list = el("div", "entity-history-list");
    status.events.slice(0, 12).forEach((row) => {
      const item = el("div", "history-row");
      item.append(el("strong", "", `${formatEventType(row.event_type)} · ${String(row.created_at || "н/д").slice(0, 19).replace("T", " ")}`));
      item.append(el("span", "", `${row.context || "без контекста"}${row.status ? ` · статус ${row.status}` : ""}`));
      if (row.note) {
        item.append(el("span", "", `Комментарий: ${row.note}`));
      }
      list.append(item);
    });
    decisionCard.append(list);
  }
  root.append(decisionCard);

  const bottomNavigator = renderEntityNavigator();
  if (bottomNavigator) {
    const navCard = el("div", "list-card");
    navCard.classList.add("detail-nav-card");
    appendHeadingWithInfo(navCard, "h3", "Навигация по сущностям", "Нижняя навигация нужна, чтобы можно было идти по соседним SKU без возврата к верхней части detail-panel.");
    navCard.append(el("p", "", "Используй эти кнопки, если уже прочитал историю и хочешь сразу перейти к следующей позиции."));
    navCard.append(bottomNavigator);
    root.append(navCard);
  }
}

function renderChangeSummary(item) {
  const root = document.getElementById("change-grid");
  root.innerHTML = "";
  const change = item.change_from_previous;
  if (!change || !(change.summary || []).length) {
    const card = el("div", "insight-card");
    card.append(el("h3", "", "Сравнение пока недоступно"));
    card.append(el("p", "", change ? "Предыдущий отчёт найден, но заметных числовых изменений не зафиксировано." : "Для этого типа отчёта ещё нет предыдущего bundle для сравнения."));
    root.append(card);
    return;
  }
  (change.summary || []).forEach((row) => {
    const card = el("div", "insight-card");
    const deltaPct = row.delta_pct === null || row.delta_pct === undefined ? "н/д" : formatPercent(row.delta_pct);
    const deltaRaw = row.delta > 0 ? `+${formatNumber(row.delta)}` : formatNumber(row.delta);
    card.dataset.tone = row.delta > 0 ? "good" : "warn";
    card.append(el("h3", "", metricLabel(row.key)));
    card.append(el("p", "", `Сейчас ${formatNumber(row.current)}, раньше ${formatNumber(row.previous)}. Изменение: ${deltaRaw}, ${deltaPct}.`));
    root.append(card);
  });
}

function renderActionCenter() {
  renderActionCenterToolbar();
  const watchRoot = document.getElementById("watchlist-panel");
  const actionsRoot = document.getElementById("manual-actions-panel");
  const statusRoot = document.getElementById("action-center-status-panel");
  [watchRoot, actionsRoot, statusRoot].forEach((node) => {
    if (node) node.innerHTML = "";
  });
  if (!watchRoot || !actionsRoot || !statusRoot) return;
  if (!actionCenterState) {
    [watchRoot, actionsRoot, statusRoot].forEach((root) => {
      const card = el("div", "list-card");
      card.append(el("h3", "", "Центр действий недоступен"));
      card.append(el("p", "", "Запусти `web_refresh_server.py`, чтобы включить сохранение watchlist и ручных задач."));
      root.append(card);
    });
    return;
  }

  const watchCard = el("div", "list-card");
  appendHeadingWithInfo(watchCard, "h3", "Список наблюдения", "Сюда попадают сущности, к которым нужно вернуться: SKU, семейства, продавцы, ниши. Это не автоматическое действие, а ручной short-list менеджера.");
  const watchRows = actionCenterState.watchlists || [];
  if (!watchRows.length) {
    watchCard.append(el("p", "empty-state", "Список наблюдения пока пуст."));
  } else {
    const list = el("ul", "compact-list");
    watchRows.slice(0, 8).forEach((row) => {
      const item = el("li");
      item.append(el("strong", "", row.title));
      item.append(el("span", "", `${formatEntityType(row.entity_type)}, ${row.context || "без контекста"}`));
      list.append(item);
    });
    watchCard.append(list);
  }
  watchRoot.append(watchCard);

  const actionCard = el("div", "list-card");
  appendHeadingWithInfo(actionCard, "h3", "Ручные задачи", "Минимальный action-center: фиксирует решения менеджера поверх автоматических сигналов.");
  const actionRows = filterActionRows(actionCenterState.actions || []);
  if (!actionRows.length) {
    actionCard.append(el("p", "empty-state", "Ручных задач пока нет."));
  } else {
    const list = el("ul", "compact-list");
    actionRows.slice(0, 8).forEach((row) => {
      const item = el("li");
      const content = el("div", "list-item-main");
      content.append(el("strong", "", row.title));
      content.append(el("span", "", `${formatActionStatus(row.status || "open")}${row.owner ? ` · ответственный ${row.owner}` : ""}${row.note ? ` · ${row.note}` : ""}`));
      item.append(content);
      const controls = el("div", "entity-actions");
      controls.append(
        createActionButton("В работу", "secondary", async () => {
          await updateActionItem({ id: row.id, status: "in_progress" });
          await refreshActionCenter();
        }),
        createActionButton("Блокер", "secondary", async () => {
          await updateActionItem({ id: row.id, status: "blocked" });
          await refreshActionCenter();
        }),
        createActionButton(row.status === "done" ? "Открыть" : "Готово", "secondary", async () => {
          if (row.status === "done") {
            await toggleActionItem(row.id);
          } else {
            await updateActionItem({ id: row.id, status: "done" });
          }
          await refreshActionCenter();
        }),
      );
      item.append(controls);
      list.append(item);
    });
    actionCard.append(list);
  }
  actionsRoot.append(actionCard);

  const statusCard = el("div", "list-card");
  appendHeadingWithInfo(statusCard, "h3", "Состояние", "Показывает, жив ли local action-center, сколько уже накоплено ручных сущностей и насколько активно используется manager loop.");
  statusCard.append(el("p", "", `В списке наблюдения: ${formatNumber((actionCenterState.watchlists || []).length)}`));
  statusCard.append(el("p", "", `Открытых задач: ${formatNumber(actionCenterState.open_actions_count || 0)}`));
  statusCard.append(el("p", "", `Закрытых задач: ${formatNumber(actionCenterState.done_actions_count || 0)}`));
  statusCard.append(el("p", "", `Подтверждённых сущностей: ${formatNumber(actionCenterState.acknowledged_entities_count || 0)}`));
  statusCard.append(el("p", "", `Событий в журнале: ${formatNumber(actionCenterState.event_count || 0)}`));
  statusCard.append(el("p", "", `Сохранённых представлений: ${formatNumber((actionCenterState.saved_views || []).length)}`));
  statusCard.append(el("p", "", `Версия схемы: ${actionCenterState.schema_version || "н/д"}`));
  statusCard.append(el("p", "", "Статусы задач пока меняются вручную: новая → в работе → блокер/завершена. Автоматического закрытия, retry-счётчиков и SLA пока нет."));
  if ((actionCenterState.saved_views || []).length) {
    const savedList = el("div", "saved-view-list");
    actionCenterState.saved_views.slice(0, 8).forEach((row) => {
      const button = createActionButton(row.name, "secondary", async () => {
        selectedActionFilter = row.filters?.filter || "all";
        setStoredActionFilter(selectedActionFilter);
        if (row.filters?.owner !== undefined) {
          setStoredActionOwner(row.filters.owner || "");
        }
        renderActionCenter();
      });
      savedList.append(button);
    });
    statusCard.append(savedList);
  }
  statusRoot.append(statusCard);

  const lifecycleCard = el("div", "list-card");
  appendHeadingWithInfo(lifecycleCard, "h3", "Жизненный цикл задач", "Пока это ручной workflow. Система не закрывает задачу сама и не делает retry без решения менеджера.");
  lifecycleCard.append(el("p", "", "1. Новая: задача создана из сигнала или вручную и ещё не взята в работу."));
  lifecycleCard.append(el("p", "", "2. В работе: менеджер подтвердил, что задача реально исполняется."));
  lifecycleCard.append(el("p", "", "3. Блокер: есть внешняя причина, почему шаг нельзя закрыть сейчас."));
  lifecycleCard.append(el("p", "", "4. Завершена: менеджер вручную подтвердил, что шаг выполнен и можно закрывать контур."));
  lifecycleCard.append(el("p", "", "Пока нет auto-close, SLA, таймеров и счётчиков попыток. Это отдельный product-слой, который ещё не внедрён."));
  statusRoot.append(lifecycleCard);
}

function safeRunnerJobs() {
  return SAFE_RUNNER_JOB_KEYS
    .map((jobKey) => runnerJobs.find((job) => job.job_key === jobKey))
    .filter(Boolean);
}

function buildRunnerFormData(job) {
  const formData = {};
  let requiresToken = false;
  for (const field of job.fields || []) {
    if (field.name === "token") {
      requiresToken = true;
      continue;
    }
    if (field.default !== undefined && field.default !== "") {
      formData[field.name] = field.default;
      continue;
    }
    if (field.required) {
      throw new Error(`Job ${job.job_key} требует поле ${field.label || field.name}. Для кастомного запуска открой полный runner.`);
    }
  }
  if (requiresToken) {
    const token = String(runnerSharedToken || "").trim();
    if (!token) {
      throw new Error("Для этого online job нужен access token. Задай его в toolbar runtime-операций.");
    }
    formData.token = token;
  }
  return formData;
}

function formatRunnerDate(value) {
  return value ? formatDateTime(value) : "РЅ/Рґ";
}

function renderRuntimeOpsToolbar() {
  const root = document.getElementById("runtime-ops-toolbar");
  if (!root) return;
  root.innerHTML = "";
  const wrap = el("div", "inline-form");
  const tokenInput = document.createElement("input");
  tokenInput.type = "password";
  tokenInput.className = "inline-input";
  tokenInput.placeholder = "Access token для online jobs";
  tokenInput.value = runnerSharedToken || "";
  tokenInput.autocomplete = "off";
  tokenInput.style.minWidth = "280px";
  tokenInput.addEventListener("input", () => {
    runnerSharedToken = tokenInput.value.trim();
    setStoredRefreshToken(runnerSharedToken);
  });
  const validateBtn = el("button", "theme-toggle compact-button", "Проверить токен");
  validateBtn.type = "button";
  validateBtn.addEventListener("click", async () => {
    const token = String(tokenInput.value || "").trim();
    if (!token) {
      alert("Сначала задай access token.");
      return;
    }
    validateBtn.disabled = true;
    try {
      runnerTokenHealth = await validateRunnerToken(token);
      runnerSharedToken = token;
      setStoredRefreshToken(token);
      renderRuntimeOps();
    } catch (error) {
      alert(error.message);
    } finally {
      validateBtn.disabled = false;
    }
  });
  const reloadBtn = el("button", "theme-toggle compact-button", "Обновить runtime");
  reloadBtn.type = "button";
  reloadBtn.addEventListener("click", async () => {
    reloadBtn.disabled = true;
    try {
      await refreshRuntimeOps();
    } finally {
      reloadBtn.disabled = false;
    }
  });
  const openRunner = document.createElement("a");
  openRunner.className = "theme-toggle compact-button";
  openRunner.href = refreshUiUrl();
  openRunner.textContent = "Полный runner";
  wrap.append(tokenInput, validateBtn, reloadBtn, openRunner);
  root.append(wrap);
}

function renderRuntimeStatusCard(activeRun) {
  const root = document.getElementById("runtime-ops-status-panel");
  if (!root) return;
  root.innerHTML = "";
  const card = el("div", "list-card");
  appendHeadingWithInfo(card, "h3", "Runtime state", "Показывает, жив ли embedded runner-контур в основном UI, какой job активен и можно ли запускать следующий safe/manual сценарий без перехода в legacy refresh screen.");
  const latestRun = activeRun?.status || runnerRuns[0] || null;
  const tokenLine = runnerSharedToken
    ? (runnerTokenHealth?.token_health?.status === "valid" ? "Токен проверен и выглядит валидным." : "Токен задан, но не проверен в этой сессии.")
    : "Токен не задан. Offline job можно запускать и без него.";
  card.append(el("p", "", tokenLine));
  card.append(el("p", "", `Safe jobs в main UI: ${formatNumber(safeRunnerJobs().length)}`));
  card.append(el("p", "", `Последних запусков в истории: ${formatNumber(runnerRuns.length)}`));
  if (latestRun) {
    card.append(el("p", "", `Текущий фокус: ${latestRun.job_key} · ${latestRun.state || "unknown"}`));
    card.append(el("p", "", `Старт: ${formatRunnerDate(latestRun.started_at)} · Завершение: ${formatRunnerDate(latestRun.ended_at)}`));
    if (latestRun.progress_hint) {
      card.append(el("p", "", `Progress: ${latestRun.progress_hint}`));
    }
    const jump = document.createElement("a");
    jump.className = "theme-toggle compact-button";
    jump.href = runnerJobUrl(latestRun.job_key);
    jump.textContent = "Открыть в full runner";
    card.append(jump);
  } else {
    card.append(el("p", "empty-state", "История запусков пока пуста."));
  }
  root.append(card);
}

function renderRuntimeJobsCard() {
  const root = document.getElementById("runtime-ops-jobs-panel");
  if (!root) return;
  root.innerHTML = "";
  const card = el("div", "list-card");
  appendHeadingWithInfo(card, "h3", "Safe/manual jobs", "Первая волна переноса: только jobs с понятным manual workflow и дефолтными параметрами. Сложные кастомные сценарии по-прежнему доступны через full runner.");
  const jobs = safeRunnerJobs();
  if (!jobs.length) {
    card.append(el("p", "empty-state", "Runner API недоступен или safe jobs ещё не загружены."));
    root.append(card);
    return;
  }
  const list = el("ul", "compact-list");
  jobs.forEach((job) => {
    const item = el("li");
    const content = el("div", "list-item-main");
    const defaults = (job.fields || [])
      .filter((field) => field.name !== "token" && field.default !== undefined && field.default !== "")
      .slice(0, 3)
      .map((field) => `${field.label || field.name}: ${field.default}`)
      .join(" В· ");
    content.append(el("strong", "", job.title || job.job_key));
    content.append(el("span", "", `${job.mode || "unknown"}${defaults ? ` В· ${defaults}` : ""}`));
    item.append(content);
    const controls = el("div", "entity-actions");
    controls.append(
      createActionButton("Запустить", "secondary", async () => {
        const formData = buildRunnerFormData(job);
        if (formData.token) {
          runnerTokenHealth = await validateRunnerToken(formData.token);
        }
        const payload = await startRunnerJob(job.job_key, formData);
        runnerActiveJobId = payload.status?.job_id || null;
        await refreshRuntimeOps();
      }),
    );
    const fullRunnerLink = document.createElement("a");
    fullRunnerLink.className = "theme-toggle compact-button";
    fullRunnerLink.href = runnerJobUrl(job.job_key);
    fullRunnerLink.textContent = "Параметры";
    controls.append(fullRunnerLink);
    item.append(controls);
    list.append(item);
  });
  card.append(list);
  root.append(card);
}

function renderRuntimeRunsCard(activeRun) {
  const root = document.getElementById("runtime-ops-runs-panel");
  if (!root) return;
  root.innerHTML = "";
  const card = el("div", "list-card");
  appendHeadingWithInfo(card, "h3", "Последние run'ы", "Показывает короткую runtime-историю прямо в основном UI: что запускалось последним, чем закончилось и куда перейти за полным логом.");
  if (activeRun?.log) {
    const pre = document.createElement("pre");
    pre.className = "log-panel";
    pre.textContent = activeRun.log.slice(-1200) || "Лог пуст.";
    card.append(pre);
  }
  if (!runnerRuns.length) {
    card.append(el("p", "empty-state", "Запусков пока нет."));
    root.append(card);
    return;
  }
  const list = el("ul", "compact-list");
  runnerRuns.slice(0, 6).forEach((run) => {
    const item = el("li");
    const content = el("div", "list-item-main");
    content.append(el("strong", "", `${run.job_key} · ${run.state || "unknown"}`));
    content.append(el("span", "", `${formatRunnerDate(run.started_at)}${run.return_code !== null && run.return_code !== undefined ? ` В· code ${run.return_code}` : ""}`));
    item.append(content);
    const controls = el("div", "entity-actions");
    controls.append(
      createActionButton("Фокус", "secondary", async () => {
        runnerActiveJobId = run.job_id;
        await refreshRuntimeOps();
      }),
    );
    const link = document.createElement("a");
    link.className = "theme-toggle compact-button";
    link.href = runnerJobUrl(run.job_key);
    link.textContent = "Runner";
    controls.append(link);
    item.append(controls);
    list.append(item);
  });
  card.append(list);
  root.append(card);
}

function renderRuntimeOpsUnavailable(error) {
  renderRuntimeOpsToolbar();
  const targets = [
    document.getElementById("runtime-ops-status-panel"),
    document.getElementById("runtime-ops-jobs-panel"),
    document.getElementById("runtime-ops-runs-panel"),
  ];
  targets.forEach((root) => {
    if (!root) return;
    root.innerHTML = "";
  });
  const card = el("div", "list-card");
  card.append(el("h3", "", "Runner недоступен"));
  card.append(el("p", "", error.message));
  const link = document.createElement("a");
  link.className = "theme-toggle compact-button";
  link.href = refreshUiUrl();
  link.textContent = "Открыть legacy runner";
  card.append(link);
  targets[0]?.append(card);
}

function renderRuntimeOps(activeRun = null) {
  renderRuntimeOpsToolbar();
  renderRuntimeStatusCard(activeRun);
  renderRuntimeJobsCard();
  renderRuntimeRunsCard(activeRun);
}

async function refreshRuntimeOps() {
  try {
    const [jobsPayload, runsPayload] = await Promise.all([
      loadRunnerJobs(),
      loadRunnerRuns(),
    ]);
    runnerJobs = jobsPayload.jobs || [];
    runnerRuns = runsPayload.runs || [];
    if (!runnerActiveJobId || !runnerRuns.some((run) => run.job_id === runnerActiveJobId)) {
      runnerActiveJobId = runnerRuns[0]?.job_id || null;
    }
    const activePayload = runnerActiveJobId
      ? await loadRunnerRun(runnerActiveJobId).catch(() => null)
      : null;
    renderRuntimeOps(activePayload);
  } catch (error) {
    renderRuntimeOpsUnavailable(error);
  }
}
function renderTables(payload) {
  const tables = payload.tables || {};
  const currentRows = (tables.current_winners || []).length ? (tables.current_winners || []) : (tables.soft_signal_products || []);
  const currentTitle = (tables.current_winners || []).length ? "Что продаётся сейчас" : "Слабые, но живые сигналы";
  const currentInfo = (tables.current_winners || []).length
    ? "Это товары с осмысленным текущим сигналом в окне, а не исторические хиты. Используйте их как список того, что реально живо сейчас."
    : "Строгих победителей в окне нет, но здесь видны товары с продажами, которые уже подают сигнал. Это список для наблюдения и осторожного усиления.";
  renderTableCard({ root: document.getElementById("table-winners"), title: currentTitle, rows: currentRows, formatter: (row) => `продано ${row.units_sold}, выручка ${formatMoney(row.net_revenue)}, ABC ${row.abc_revenue}`, infoText: currentInfo, getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Лидеры по прибыли", rows: tables.profit_leaders || [], formatter: (row) => `прибыль ${formatMoney(row.gross_profit)}, маржа ${row.profit_margin_pct}%`, infoText: "Показывает товары, которые приносят больше всего валовой прибыли в текущем окне. Это приоритет для защиты наличия и качества карточки.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Риск закончиться", rows: tables.stockout_risk || [], formatter: (row) => `остаток ${row.total_stock}, покрытие ${row.stock_cover_days ?? "∞"} дн.`, infoText: "Список позиций, где остаток короткий относительно текущего темпа продаж. Смотрите сюда для приоритета закупки.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Лежит без движения", rows: tables.stale_stock || [], formatter: (row) => `остаток ${row.total_stock}, стоимость ${formatMoney(row.stock_value_sale)}`, infoText: "Позиции без движения в текущем окне. Это кандидаты на чистку, уценку, пересборку карточки или отключение.", getDisplayTitle, createEntityActionButtons });
}

function renderFamilyTables(payload) {
  const families = payload.family_tables || {};
  const familyCurrentRows = (families.family_current_winners || []).length ? (families.family_current_winners || []) : (families.family_soft_signal_products || []);
  const familyCurrentTitle = (families.family_current_winners || []).length ? "Семейства, которые продаются" : "Семейства с ранним сигналом";
  const familyCurrentInfo = (families.family_current_winners || []).length
    ? "Семейства помогают смотреть на карточку целиком, если в ней несколько ШК или вариантов. Это полезно там, где одна строка CSV вводит в заблуждение."
    : "Строгих семей-победителей в окне нет. Здесь видны карточки, у которых уже есть первые продажи на уровне семейства, но сигнал ещё слабый.";
  renderTableCard({ root: document.getElementById("family-winners"), title: familyCurrentTitle, rows: familyCurrentRows, formatter: (row) => `вариантов ${row.variant_count}, продано ${row.sold_units_sum}, выручка ${formatMoney(row.net_revenue_sum)}`, infoText: familyCurrentInfo, getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("family-reorder"), title: "Семейства на дозакупку", rows: families.family_reorder_now || [], formatter: (row) => `вариантов ${row.variant_count}, остаток ${row.stock_units_sum}, покрытие ${row.stock_cover_days ?? "∞"} дн.`, infoText: "Показывает карточки, где проблема уже не в одном SKU, а на уровне всего семейства товара.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("family-variants"), title: "Крупные карточки с вариантами", rows: families.largest_multi_variant_families || [], formatter: (row) => `вариантов ${row.variant_count}, ШК ${row.barcode_count}, остаток ${row.stock_units_sum}`, infoText: "Сюда смотрят, когда нужно понять: карточка в целом жива или продажи и остатки размазаны по вариантам.", getDisplayTitle, createEntityActionButtons });
}

function getAbcHelpText(metricLabel) {
  return `ABC по ${metricLabel} делит ассортимент на три слоя: A — ядро, которое даёт основную долю результата; B — поддерживающий средний слой; C — длинный хвост. Практически это читается так: A держать в наличии и контролировать ежедневно, B оптимизировать и масштабировать выборочно, C чистить, перерабатывать оффер или выводить.`;
}

function summarizeAbc(countsRows, valuesRows) {
  const countsMap = Object.fromEntries((countsRows || []).map((row) => [row.key, Number(row.count || 0)]));
  const valuesMap = Object.fromEntries((valuesRows || []).map((row) => [row.key, Number(row.value || 0)]));
  const totalCount = Object.values(countsMap).reduce((acc, value) => acc + value, 0);
  const totalValue = Object.values(valuesMap).reduce((acc, value) => acc + value, 0);
  return ["A", "B", "C"].map((key) => {
    const count = countsMap[key] || 0;
    const value = valuesMap[key] || 0;
    return {
      key,
      count,
      value,
      countShare: totalCount ? (count / totalCount) * 100 : null,
      valueShare: totalValue ? (value / totalValue) * 100 : null,
    };
  });
}

function renderAbcInterpretationCard(title, metricLabel, countsRows, valuesRows, formatter) {
  const card = el("div", "chart-card abc-card");
  appendHeadingWithInfo(card, "h3", title, getAbcHelpText(metricLabel));
  const summaryRows = summarizeAbc(countsRows, valuesRows);
  const explainer = el("p", "abc-explainer", "Не просто шкала: смотрите, какую долю результата даёт каждая зона и как распределён ассортимент.");
  card.append(explainer);
  const grid = el("div", "abc-grid");
  summaryRows.forEach((row) => {
    const item = el("div", `abc-cell abc-${row.key.toLowerCase()}`);
    item.append(el("strong", "", row.key));
    item.append(el("span", "", `SKU: ${formatNumber(row.count)} (${formatShare(row.countShare)})`));
    item.append(el("span", "", `${metricLabel}: ${formatter(row.value)} (${formatShare(row.valueShare)})`));
    grid.append(item);
  });
  card.append(grid);
  const notes = el("div", "abc-notes");
  notes.append(el("p", "", "A: держать в наличии, контролировать фото, рейтинг и цену, не терять наличие."));
  notes.append(el("p", "", "B: кандидаты на развитие и тесты продвижения, если экономика уже нормальная."));
  notes.append(el("p", "", "C: длинный хвост. Сюда смотрят для чистки, уценки, переработки карточки или вывода."));
  card.append(notes);
  return card;
}

function renderAbcExamplesCard(title, metricLabel, examplesByBucket, formatter) {
  const card = el("div", "chart-card abc-card");
  appendHeadingWithInfo(card, "h3", title, `Показывает конкретные SKU внутри зон A/B/C по метрике "${metricLabel}". Это уже рабочий список для действий, а не только агрегированная шкала.`);
  const buckets = examplesByBucket || {};
  const zones = ["A", "B", "C"];
  const anyRows = zones.some((zone) => (buckets[zone] || []).length);
  if (!anyRows) {
    card.append(el("p", "empty-state", "Нет данных для этого блока."));
    return card;
  }
  zones.forEach((zone) => {
    const rows = buckets[zone] || [];
    const section = el("div", "abc-example-zone");
    section.append(el("strong", "", `Зона ${zone}`));
    if (!rows.length) {
      section.append(el("p", "empty-state", "Нет SKU в этой зоне."));
      card.append(section);
      return;
    }
    const list = el("ul", "compact-list");
    rows.forEach((row) => {
      const item = el("li");
      item.append(el("strong", "", getDisplayTitle(row)));
      item.append(el("span", "", `${metricLabel}: ${formatter(metricLabel === "прибыль" ? row.gross_profit : row.net_revenue)}, продано ${formatNumber(row.units_sold)}`));
      list.append(item);
    });
    section.append(list);
    card.append(section);
  });
  return card;
}

function renderCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderAbcInterpretationCard("ABC по выручке", "выручка", charts.abc_revenue_counts || [], charts.revenue_by_abc || [], formatMoney));
  root.append(renderAbcInterpretationCard("ABC по прибыли", "прибыль", charts.abc_profit_counts || [], charts.profit_by_abc || [], formatMoney));
  root.append(renderAbcExamplesCard("Какие SKU входят в ABC по выручке", "выручка", charts.abc_revenue_examples || {}, formatMoney));
  root.append(renderAbcExamplesCard("Какие SKU входят в ABC по прибыли", "прибыль", charts.abc_profit_examples || {}, formatMoney));
  root.append(renderBarChart("Статусы", charts.status_counts || [], formatNumber, "Показывает, сколько SKU сейчас находится в каждом operational-статусе. Это не история, а снимок текущего окна."));
  root.append(renderBarChart("Выручка по ABC", charts.revenue_by_abc || [], formatMoney, "Сколько выручки приносит каждая зона A/B/C. Полезно, чтобы не путать число SKU с реальным вкладом в деньги."));
}

function renderMarketCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Заказы по ценовым коридорам", charts.price_bands || [], formatNumber, "Показывает, в каких ценовых диапазонах сосредоточен спрос в наблюдаемом рынке за выбранный срез."));
  root.append(renderBarChart("Заказы по группам", charts.group_orders || [], formatNumber, "Показывает, какие товарные группы собирают больше всего видимых заказов в текущем рыночном срезе."));
}

function renderPricingCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Структура pricing-рекомендаций", charts.pricing_labels || [], formatNumber, "Как распределяются ценовые решения: держать цену, тестировать, входить агрессивнее или не демпинговать."));
  root.append(renderBarChart("Средняя цена рынка по окнам", charts.avg_market_price_by_band || [], formatMoney, "Средняя рыночная цена по каждому ценовому коридору. Это опорный слой, а не готовая цена для авто-применения."));
}

function renderMarketingCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Типы маркетинговых действий", charts.priority_buckets || [], formatNumber, "Показывает, какие действия чаще всего требуются сейчас: цена, title, фото, описание или комбинированный fix."));
  root.append(renderBarChart("Статусы title SEO", charts.seo_status_counts || [], formatNumber, "Показывает распределение title по качеству: норм, требует работы или критичный priority fix."));
  root.append(renderBarChart("Типы проблем", charts.issue_type_counts || [], formatNumber, "Агрегирует, что именно чаще всего ломает карточки в этом отчёте."));
}

function renderMediaCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Статусы media-аудита", charts.media_status_counts || [], formatNumber, "Сводка по качеству медиа: где карточки уже нормальные, а где фото или характеристики отстают от группы."));
  root.append(renderBarChart("Фото по корзинам", charts.photo_bucket_counts || [], formatNumber, "Распределение по числу фото. Полезно, когда нужно быстро понять, упираемся ли мы в бедные карточки."));
  root.append(renderBarChart("Плотность характеристик", charts.spec_bucket_counts || [], formatNumber, "Показывает, насколько полно заполнены характеристики. Чем больше пустот, тем хуже карточка держится в сравнении."));
}

function renderDescriptionCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Статусы description-аудита", charts.description_status_counts || [], formatNumber, "Сводка по качеству описаний: где описания уже достаточные, а где они слишком слабые для карточки."));
  root.append(renderBarChart("Длина описаний", charts.description_length_counts || [], formatNumber, "Распределение по длине описаний. Это помогает быстро увидеть слой тонкого контента."));
  root.append(renderBarChart("Покрытие title-термов", charts.title_term_coverage_counts || [], formatNumber, "Показывает, насколько описание поддерживает ключевые слова из title, а не расходится с ним."));
}

function renderSalesReturnCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Главные причины возврата", charts.reason_distribution || [], formatNumber, "Показывает, какие причины уже дают основную массу возвратов. Если одна причина доминирует, её нужно чинить раньше длинного хвоста."));
  root.append(renderBarChart("Дневная динамика возвратов", charts.daily_returns || [], formatNumber, "Динамика возвратов по дням внутри окна. Полезна, чтобы отделять системную проблему от единичного всплеска."));
}

function renderWaybillCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Концентрация batch-cost", charts.cost_distribution || [], formatMoney, "Показывает, сколько себестоимости сосредоточено в верхних строках партии, а сколько размазано по хвосту."));
  root.append(renderBarChart("Покрытие cost-layer", charts.numeric_columns || [], formatNumber, "Быстрый срез по тому, насколько слой накладных уже пригоден для построения historical COGS."));
  root.append(renderBarChart("Единицы по датам поставки", charts.daily_returns || [], formatNumber, "Показывает распределение поставленных единиц по датам партий. Это база для чтения batch-history."));
}

function renderPaidStorageCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Концентрация начислений", charts.cost_distribution || [], formatMoney, "Показывает, какая доля платного слоя приходится на крупнейшие строки, а какая размазана по хвосту."));
  root.append(renderBarChart("Крупнейшие numeric-колонки", charts.numeric_columns || [], formatMoney, "Помогает понять, какие числовые колонки в XLSX реально формируют основную массу начислений."));
}

function showSection(id, visible) {
  const node = document.getElementById(id);
  if (!node) return;
  node.hidden = !visible;
  node.style.display = visible ? "" : "none";
}

function refreshUiUrl() {
  const origin = window.location.origin || "";
  if (origin.endsWith(":8000") || origin.endsWith(":8040")) {
    return `${origin}/refresh.html`;
  }
  const host = window.location.hostname || "127.0.0.1";
  return `http://${host}:8040/refresh.html`;
}

const REPORT_KIND_TO_JOB = {
  competitor_market_analysis: "market_scan",
  dynamic_pricing: "dynamic_pricing",
  marketing_card_audit: "marketing_card_audit",
  media_richness_report: "media_richness_audit",
  description_seo_report: "description_seo_richness_audit",
  paid_storage_report: "paid_storage_report",
  sales_return_report: "sales_return_report",
  waybill_cost_layer: "waybill_cost_layer",
  cubejs_period_compare: "weekly_operational",
};

function refreshJobUrl(reportKind) {
  const jobKey = REPORT_KIND_TO_JOB[reportKind];
  const base = refreshUiUrl();
  return jobKey ? `${base}?job=${encodeURIComponent(jobKey)}` : base;
}

function runnerJobUrl(jobKey) {
  const base = refreshUiUrl();
  return jobKey ? `${base}?job=${encodeURIComponent(jobKey)}` : base;
}

function findLatestReportByKind(items, kind) {
  return (items || []).find((item) => item.report_kind === kind) || null;
}

function findLatestReportByName(items, pattern) {
  return (items || []).find((item) => String(item.file_name || "").includes(pattern)) || null;
}

async function activateReport(fileName) {
  const item = dashboardItems.find((entry) => entry.file_name === fileName);
  if (!item) return;
  setStoredReportSelection(item.file_name);
  dashboardSelects.forEach((targetSelect) => {
    targetSelect.value = item.file_name;
  });
  await renderDashboard(item);
}

function renderFlowMap(items, cogsStore) {
  const root = document.getElementById("flow-map-grid");
  if (!root) return;
  root.innerHTML = "";

  const pricing = findLatestReportByKind(items, "dynamic_pricing");
  const marketing = findLatestReportByKind(items, "marketing_card_audit");
  const paidStorage = findLatestReportByKind(items, "paid_storage_report");
  const waybill = findLatestReportByKind(items, "waybill_cost_layer");
  const rescoredMarket = findLatestReportByName(items, "market_rescored_after_cogs");
  const cogsSummary = cogsStore?.summary || {};
  const cogsRows = cogsStore?.items || [];

  const flows = [
    {
      title: "Pricing",
      state: pricing ? "available" : "runner",
      badge: pricing ? "Доступно" : "Runner only",
      summary: pricing
        ? "Отдельный report/view уже есть в основном UI."
        : "Отчёт ещё не попал в dashboard index, но job уже заведён в runner.",
      meta: [
        pricing ? `Последний артефакт: ${reportOptionLabel(pricing)}` : "Артефакт в основном UI пока не найден.",
        "Режим: read-only report + локальный rebuild через refresh runner.",
      ],
      reportFile: pricing?.file_name,
      jobKey: "dynamic_pricing",
    },
    {
      title: "Marketing audit",
      state: marketing ? "available" : "runner",
      badge: marketing ? "Доступно" : "Runner only",
      summary: marketing
        ? "Price trap, title SEO и рыночный контекст уже сведены в единый экран."
        : "Unified marketing surface ещё не найден в dashboard index.",
      meta: [
        marketing ? `Последний артефакт: ${reportOptionLabel(marketing)}` : "Артефакт в основном UI пока не найден.",
        "Режим: read-only report + локальный rebuild через refresh runner.",
      ],
      reportFile: marketing?.file_name,
      jobKey: "marketing_card_audit",
    },
    {
      title: "Paid storage",
      state: paidStorage ? "available" : "runner",
      badge: paidStorage ? "Доступно" : "Runner only",
      summary: paidStorage
        ? "Крупные начисления и строки без identity уже читаются в основном UI."
        : "В основном UI ещё нет текущего paid storage bundle.",
      meta: [
        paidStorage ? `Последний артефакт: ${reportOptionLabel(paidStorage)}` : "Артефакт в основном UI пока не найден.",
        "Режим: read-only report, сам seller-documents refresh остаётся runner-driven.",
      ],
      reportFile: paidStorage?.file_name,
      jobKey: "paid_storage_report",
    },
    {
      title: "Waybill / historical COGS",
      state: waybill ? "available" : "runner",
      badge: waybill ? "Доступно" : "Runner only",
      summary: waybill
        ? "Batch-cost и historical COGS слой уже вынесены в основной интерфейс."
        : "Waybill слой ещё не найден в dashboard index.",
      meta: [
        waybill ? `Последний артефакт: ${reportOptionLabel(waybill)}` : "Артефакт в основном UI пока не найден.",
        "Режим: read-only report + interactive rebuild через runner job.",
      ],
      reportFile: waybill?.file_name,
      jobKey: "waybill_cost_layer",
    },
    {
      title: "Zero COGS cycle",
      state: cogsRows.length || rescoredMarket ? "partial" : "runner",
      badge: cogsRows.length || rescoredMarket ? "Partial" : "Runner only",
      summary: cogsRows.length
        ? "Локальное хранилище overrides уже заполнено, но inline fill/edit в основном UI пока нет."
        : "Цикл registry -> fill -> rescore уже существует, но запускается через refresh runner.",
      meta: [
        cogsStore?.generated_at
          ? `Локальный store: ${formatDateTime(cogsStore.generated_at)} · rows ${formatNumber(cogsSummary.items_total || cogsRows.length)} · imported ${formatNumber(cogsSummary.fill_rows_imported || 0)}`
          : "Локальный store COGS пока не найден или ещё не был собран.",
        rescoredMarket
          ? `Связанный артефакт: ${reportOptionLabel(rescoredMarket)}`
          : "Rescored market bundle после COGS пока не найден в dashboard index.",
        "Режим: partial. Артефакты видны, но сам fill/rescore цикл пока runner-driven.",
      ],
      reportFile: rescoredMarket?.file_name,
      jobKey: "cogs_backfill_cycle",
    },
  ];

  flows.forEach((flow) => {
    const card = el("article", "list-card flow-card");
    const header = el("div", "flow-card-header");
    const headingWrap = el("div", "");
    headingWrap.append(el("h3", "flow-card-title", flow.title));
    headingWrap.append(el("p", "flow-card-subtitle", flow.summary));
    header.append(headingWrap);
    header.append(el("span", `badge badge-${flow.state === "available" ? "available" : flow.state === "partial" ? "partial" : "runner"}`, flow.badge));
    card.append(header);

    const meta = el("div", "flow-card-meta");
    flow.meta.forEach((line) => meta.append(el("p", "", line)));
    card.append(meta);

    const actions = el("div", "flow-card-actions");
    if (flow.reportFile) {
      const openBtn = el("button", "theme-toggle compact-button", "Открыть в UI");
      openBtn.type = "button";
      openBtn.addEventListener("click", async () => {
        openBtn.disabled = true;
        openBtn.textContent = "Загрузка…";
        try {
          await activateReport(flow.reportFile);
          document.getElementById("report-select")?.scrollIntoView({ behavior: "smooth", block: "center" });
        } finally {
          openBtn.disabled = false;
          openBtn.textContent = "Перейти к UI";
        }
      });
      actions.append(openBtn);
    }
    if (flow.jobKey) {
      const runnerLink = document.createElement("a");
      runnerLink.className = "theme-toggle compact-button";
      runnerLink.href = runnerJobUrl(flow.jobKey);
      runnerLink.textContent = flow.jobKey === "cogs_backfill_cycle" ? "Открыть COGS cycle" : "Открыть runner";
      actions.append(runnerLink);
    }
    card.append(actions);
    root.append(card);
  });
}

function clearNode(id) {
  const node = document.getElementById(id);
  if (node) {
    node.innerHTML = "";
  }
}

function clearOperationalPanels() {
  [
    "action-reorder",
    "action-markdown",
    "action-protect",
    "table-winners",
    "table-profit",
    "table-risk",
    "table-stale",
    "family-winners",
    "family-reorder",
    "family-variants",
    "chart-grid",
  ].forEach(clearNode);
}

function renderCubejsCompare(rawPayload) {
  const periods = rawPayload.periods || {};
  const root = document.getElementById("compare-grid");
  const trendRoot = document.getElementById("trend-grid");
  root.innerHTML = "";
  trendRoot.innerHTML = "";

  const current = periods.current_trailing_year || {};
  const currentMetrics = current.metrics || {};
  const previous = periods.previous_year_same_window || {};
  const threeYear = periods.three_year_same_window || {};
  const ytd = periods.current_ytd || {};
  const previousYtd = periods.previous_ytd || {};

  renderCompareCard(
    root,
    "Выручка за 365 дней",
    formatMoney(currentMetrics.revenue_total || 0),
    `${current.date_from || "н/д"} -> ${current.date_to || "н/д"}`,
    previous.delta_vs_current?.revenue_total_pct,
    "Год к году"
  );
  renderCompareCard(
    root,
    "Заказы за 365 дней",
    formatNumber(currentMetrics.orders_total || 0),
    "Заказы за 365 дней",
    previous.delta_vs_current?.orders_total_pct,
    "Год к году"
  );
  renderCompareCard(
    root,
    "Проданные единицы за 365 дней",
    formatNumber(currentMetrics.items_sold_total || 0),
    "Проданные единицы за 365 дней",
    previous.delta_vs_current?.items_sold_total_pct,
    "Год к году"
  );
  renderCompareCard(
    root,
    "Выручка с начала года",
    formatMoney((ytd.metrics || {}).revenue_total || 0),
    `${ytd.date_from || "н/д"} -> ${ytd.date_to || "н/д"}`,
    previousYtd.delta_vs_current?.revenue_total_pct,
    "С начала года к прошлому"
  );
  renderCompareCard(
    root,
    "База 3 года назад",
    formatMoney((threeYear.metrics || {}).revenue_total || 0),
    `${threeYear.date_from || "н/д"} -> ${threeYear.date_to || "н/д"}`,
    threeYear.delta_vs_current?.revenue_total_pct,
    "Сдвиг к базе"
  );
  renderCompareCard(
    root,
    "Глубина истории",
    `${rawPayload.history_window?.history_years || 0} года`,
    `${rawPayload.history_window?.date_from || "н/д"} -> ${rawPayload.history_window?.date_to || "н/д"}`,
    null,
    "Покрытие"
  );

  const monthly = rawPayload.series_monthly || [];
  renderTrendCard(trendRoot, "Выручка по месяцам", monthly, "Sales.seller_revenue_without_delivery_measure", formatMoney);
  renderTrendCard(trendRoot, "Заказы по месяцам", monthly, "Sales.orders_number", formatNumber);
  renderTrendCard(trendRoot, "Проданные единицы по месяцам", monthly, "Sales.item_sold_number", formatNumber);
}

function renderMarketTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Топ продавцы", rows: tables.top_sellers || [], formatter: (row) => `заказы ${formatNumber(row.orders_sum)}, доля ${formatShare(row.share_of_observed_orders_pct)}, товаров ${formatNumber(row.products_seen)}, ядро ${row.top_group || "н/д"}, новизна ${row.novelty_proxy_index ?? "н/д"}`, infoText: "Это лидеры внутри наблюдаемой рыночной выборки, а не абсолютный рейтинг всего маркетплейса. Используйте как ориентир для того, кто доминирует в видимой части категории.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Что продаётся в рынке", rows: tables.top_products || [], formatter: (row) => `продавец ${row.seller_title || "н/д"}, заказы ${formatNumber(row.orders)}, цена ${formatMoney(row.price)}, отзывы ${formatNumber(row.reviews)}, новизна ${row.novelty_proxy_score ?? "н/д"}`, infoText: "Список заметных товаров в текущем market scan. Это помогает понять, какие офферы и цены уже подтверждены рынком.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Сильнейшие группы", rows: tables.groups || [], formatter: (row) => `заказы ${formatNumber(row.orders_sum)}, продавцов ${formatNumber(row.seller_count)}, avg ${formatMoney(row.avg_price)}, HHI ${row.dominance_hhi ?? "н/д"}, margin fit ${row.market_margin_fit_pct ?? "н/д"}%, разница до цели ${row.margin_vs_target_pct ?? "н/д"} п.п.`, infoText: "Показывает, какие товарные группы в выборке несут основной спрос, насколько они насыщены продавцами и насколько рыночная цена вообще совместима с вашей экономикой. Gap здесь означает разницу между фактической совместимостью рынка и вашей целевой маржой.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Окна входа", rows: tables.entry_windows || [], formatter: (row) => `группа ${row.group || "н/д"}, коридор ${row.price_band || "н/д"}, score ${row.entry_window_score ?? "н/д"}, решение ${row.entry_strategy_label || "н/д"}, margin fit ${row.market_margin_fit_pct ?? "н/д"}%`, infoText: "Это сочетания группа + ценовой коридор. Здесь уже виден не только спрос, но и управленческое решение: входить, тестировать, ждать или не лезть.", getDisplayTitle, createEntityActionButtons });
}

function renderPricingTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Все pricing-окна", rows: tables.priced_windows || [], formatter: (row) => `группа ${row.group || "н/д"}, коридор ${row.price_band || "н/д"}, рынок ${formatMoney(row.avg_market_price)}, безопасно ${formatMoney(row.min_safe_price)}, рекомендация ${formatMoney(row.suggested_price)}`, infoText: "Все окна, где уже хватает экономических данных, чтобы дать ценовую рекомендацию.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Где входить агрессивно", rows: tables.aggressive_entry || [], formatter: (row) => `рынок ${formatMoney(row.avg_market_price)}, рекомендация ${formatMoney(row.suggested_price)}, margin fit ${row.market_margin_fit_pct ?? "н/д"}%`, infoText: "Окна, где можно идти чуть ниже рынка и всё ещё не разрушать экономику.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Где держать цену рынка", rows: (payload.actions || {}).price_at_market || [], formatter: (row) => `рынок ${formatMoney(row.avg_market_price)}, рекомендация ${formatMoney(row.suggested_price)}, разница к рынку ${row.price_gap_pct ?? "н/д"}%`, infoText: "Окна, где средняя рыночная цена уже достаточна для целевой маржи. Gap здесь означает, на сколько процентов ваша цена выше или ниже средней цены рынка.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Где нельзя демпинговать", rows: tables.margin_protection || [], formatter: (row) => `безопасно не ниже ${formatMoney(row.min_safe_price)}, рынок ${formatMoney(row.avg_market_price)}, причина: ${row.pricing_reason || "н/д"}`, infoText: "Это окно не для ценовой войны. Если входить, то только с более сильным оффером или иной закупкой.", getDisplayTitle, createEntityActionButtons });
}

function renderMarketingTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Приоритетные карточки", rows: tables.priority_cards || [], formatter: (row) => `${row.action_label || "н/д"}, score ${row.priority_score ?? "н/д"}, группа ${row.group || "н/д"} / ${row.price_band || "н/д"}`, infoText: "Главная очередь карточек, где уже сведены price trap, title SEO и рыночный pricing context.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Где тестировать цену", rows: tables.price_traps || [], formatter: (row) => `цена ${formatMoney(row.sale_price)}, порог ${formatMoney(row.threshold || 0)}, переплата ${row.overshoot_rub ?? "н/д"} ₽`, infoText: "Карточки чуть выше сильных психологических порогов. Это дешёвый слой быстрых ценовых тестов.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Где править title", rows: tables.seo_fixes || [], formatter: (row) => `SEO ${row.seo_status || "н/д"} / ${row.seo_score ?? "н/д"}, issues: ${(row.seo_issues || []).join(", ") || "н/д"}`, infoText: "Карточки, где содержание title уже выглядит слабым по эвристическому SEO-аудиту.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Карточки с рыночным контекстом", rows: tables.market_context || [], formatter: (row) => `pricing: ${row.pricing_label || "н/д"}, рынок ${formatMoney(row.avg_market_price || 0)}, рекомендация ${formatMoney(row.pricing_suggested_price || row.sale_price)}`, infoText: "Карточки, попавшие в группы и коридоры, где ценовой слой уже даёт поддерживающий рыночный контекст.", getDisplayTitle, createEntityActionButtons });
}

function renderMediaTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Приоритетные карточки", rows: tables.priority_media || [], formatter: (row) => `media ${row.media_status || "н/д"} / ${row.media_score ?? "н/д"}, фото ${row.photo_count}, spec ${row.spec_count}`, infoText: "Карточки, где media-layer уже выглядит слабее полезного минимума или уступает группе.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Визуальные отставания", rows: tables.visual_gaps || [], formatter: (row) => `отставание по фото ${row.photo_gap_vs_group ?? 0}, по характеристикам ${row.spec_gap_vs_group ?? 0}`, infoText: "Карточки, где проблема видна именно относительно своей группы, а не только по абсолютному числу фото. Gap здесь означает отставание от типичного уровня похожих карточек.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Сильные примеры", rows: tables.strong_examples || [], formatter: (row) => `фото ${row.photo_count}, spec ${row.spec_count}, видео ${row.video_count}`, infoText: "Внутренние эталоны по visual/content layer, на которые можно равняться.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Пустые места по медиа", rows: (tables.priority_media || []).filter((row) => (row.photo_count || 0) < 5 || (row.spec_count || 0) < 4), formatter: (row) => `фото ${row.photo_count}, spec ${row.spec_count}, рекомендации: ${(row.recommendations || []).join("; ") || "н/д"}`, infoText: "Где именно не хватает фото/характеристик, чтобы карточка перестала выглядеть слабой.", getDisplayTitle, createEntityActionButtons });
}

function renderDescriptionTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Приоритетные карточки", rows: tables.priority_descriptions || [], formatter: (row) => `description ${row.description_status || "н/д"} / ${row.description_score ?? "н/д"}, ${row.description_chars} симв.`, infoText: "Карточки, где описание уже выглядит слишком слабым для уверенной карточки и базового SEO.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Тонкие описания", rows: tables.thin_content || [], formatter: (row) => `${row.description_chars} симв., ${row.description_words} слов, coverage ${row.title_term_coverage_pct ?? "н/д"}%`, infoText: "Карточки с самыми короткими и бедными описаниями. Это первый фронт контентной доработки.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Сильные примеры", rows: tables.strong_examples || [], formatter: (row) => `${row.description_chars} симв., coverage ${row.title_term_coverage_pct ?? "н/д"}%`, infoText: "Внутренние эталоны по описаниям, от которых можно отталкиваться при переписывании слабых карточек.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Где текст слабее группы", rows: (tables.priority_descriptions || []).filter((row) => (row.description_gap_vs_group || 0) >= 100), formatter: (row) => `отставание ${row.description_gap_vs_group} симв., медиана группы ${row.group_median_description_chars}`, infoText: "Карточки, у которых описание заметно уступает даже медиане своей группы по объёму. Gap здесь означает, сколько символов не хватает до типичного уровня группы.", getDisplayTitle, createEntityActionButtons });
}

function renderSalesReturnTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "SKU и причины с максимальным ущербом", rows: tables.current_winners || [], formatter: (row) => `${row.reason || "Без причины"} · возвратов ${formatNumber(row.return_count || 0)}${row.amount_value ? ` · сумма ${formatMoney(row.amount_value)}` : ""}`, infoText: "Начинать нужно с тех сочетаний SKU и причины, где возвраты уже концентрируются сильнее всего. Это самый короткий путь к снижению потерь.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Причины возврата", rows: tables.profit_leaders || [], formatter: (row) => `возвратов ${formatNumber(row.return_count || 0)}${row.amount_value ? ` · сумма ${formatMoney(row.amount_value)}` : ""}`, infoText: "Агрегация по причинам показывает, что именно ломает товарный поток чаще всего: брак, описание, ожидания покупателя или логистика.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Строки без идентификации", rows: tables.stockout_risk || [], formatter: (row) => `${row.reason || "Без причины"} · возвратов ${formatNumber(row.return_count || 0)}`, infoText: "Это слой, где возврат уже виден, но его плохо получается привязать к конкретному товару. Здесь нельзя ограничиваться автоматическим выводом, нужен ручной разбор.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Полный список возвратов", rows: tables.stale_stock || [], formatter: (row) => `${row.reason || "Без причины"} · возвратов ${formatNumber(row.return_count || 0)}${row.amount_value ? ` · сумма ${formatMoney(row.amount_value)}` : ""}`, infoText: "Полный список строк текущего слоя SalesReturn, отсортированный по числу возвратов. Нужен для хвоста и повторной проверки после первых fixes.", getDisplayTitle, createEntityActionButtons });
}

function renderWaybillTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Крупнейшие batch-строки", rows: tables.current_winners || [], formatter: (row) => `batch ${formatMoney(row.batch_cogs_total || 0)} · qty ${formatNumber(row.quantity_supplied || 0)} · unit ${formatMoney(row.unit_cogs || 0)}`, infoText: "Самые тяжёлые строки по суммарной себестоимости партии. С них нужно начинать проверку batch-layer.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Историческая себестоимость по identity", rows: tables.profit_leaders || [], formatter: (row) => `latest ${formatMoney(row.gross_profit || 0)} · avg ${formatMoney(row.profit_margin_pct || 0)}`, infoText: "Сводка по последней и средней себестоимости на уровне identity. Это первый слой будущего historical COGS.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Строки без идентификации", rows: tables.stockout_risk || [], formatter: (row) => `qty ${formatNumber(row.quantity_supplied || 0)} · unit ${formatMoney(row.unit_cogs || 0)}`, infoText: "Строки, где cost есть, но нормальной привязки к товару пока нет. Их нужно чинить раньше глубокого анализа прибыли.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Все строки batch-layer", rows: tables.stale_stock || [], formatter: (row) => `qty ${formatNumber(row.quantity_supplied || 0)} · unit ${formatMoney(row.unit_cogs || 0)} · batch ${formatMoney(row.batch_cogs_total || 0)}`, infoText: "Полный список строк текущей накладной, отсортированный по объёму и себестоимости партии.", getDisplayTitle, createEntityActionButtons });
}

function renderPaidStorageTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Крупнейшие начисления", rows: tables.current_winners || [], formatter: (row) => `${row.amount_label || "сумма"} ${formatMoney(row.amount || 0)}${row.identity ? ` · ${row.identity}` : ""}`, infoText: "Строки с самым большим начислением по основной денежной колонке. С них нужно начинать разбор storage/service слоя.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Итоги по numeric-колонкам", rows: tables.profit_leaders || [], formatter: (row) => `итого ${formatMoney(row.gross_profit || 0)}, среднее ${formatMoney(row.profit_margin_pct || 0)}`, infoText: "Суммы по числовым колонкам XLSX. Нужны, чтобы понять структуру начислений и отделить хранение от удержаний.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Строки без идентификации", rows: tables.stockout_risk || [], formatter: (row) => `${row.amount_label || "сумма"} ${formatMoney(row.amount || 0)} · identity ${row.identity || "н/д"}`, infoText: "Самый проблемный слой объяснимости: начисление есть, а нормального SKU или понятного названия нет.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Все строки платного слоя", rows: tables.stale_stock || [], formatter: (row) => `${row.amount_label || "сумма"} ${formatMoney(row.amount || 0)}${row.identity ? ` · ${row.identity}` : ""}`, infoText: "Полный список строк из текущего PAID_STORAGE_REPORT, отсортированный по сумме убывания.", getDisplayTitle, createEntityActionButtons });
}

function reportOptionLabel(item) {
  const kind = REPORT_KIND_LABELS[item.report_kind] || item.report_kind;
  const variant = item.report_variant ? ` · ${item.report_variant}` : "";
  const window = item.window && item.window.date_from && item.window.date_to ? ` · ${item.window.date_from.slice(0, 10)} -> ${item.window.date_to.slice(0, 10)}` : "";
  return `${kind}${variant}${window}`;
}

function populateReportSelects(selects, items) {
  selects.forEach((targetSelect) => {
    targetSelect.innerHTML = "";
  });
  REPORT_KIND_ORDER.forEach((kind) => {
    const kindItems = items.filter((item) => item.report_kind === kind);
    if (!kindItems.length) return;
    selects.forEach((targetSelect) => {
      const optgroup = document.createElement("optgroup");
      optgroup.label = REPORT_KIND_LABELS[kind] || kind;
      kindItems.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.file_name;
        option.textContent = reportOptionLabel(item);
        optgroup.append(option);
      });
      targetSelect.append(optgroup);
    });
  });
}

async function renderDashboard(item) {
  currentDashboardItem = item;
  const jobKey = REPORT_KIND_TO_JOB[item.report_kind];
  const jobUrl = refreshJobUrl(item.report_kind);
  const jobTitle = jobKey
    ? `Открыть refresh runner и выделить job: ${jobKey}`
    : "Открыть refresh runner";
  ["refresh-link-report", "refresh-link-report-top"].forEach((id) => {
    const link = document.getElementById(id);
    if (!link) return;
    link.href = jobUrl;
    link.title = jobTitle;
    link.style.display = "";
  });
  const _dashMetaGrid = document.getElementById("meta-grid");
  if (_dashMetaGrid) _dashMetaGrid.innerHTML = '<p class="empty-state">Загрузка отчёта…</p>';
  let rawPayload;
  try {
    rawPayload = await loadJson(`../data/dashboard/${item.file_name}`);
  } catch (e) {
    if (_dashMetaGrid) _dashMetaGrid.innerHTML = `<p class="empty-state">Не удалось загрузить отчёт: ${e.message}</p>`;
    return;
  }
  const payload = item.report_kind === "cubejs_period_compare" ? normalizeCubejsComparePayload(rawPayload) : rawPayload;
  currentEntityRows = buildEntityNavigationRows(payload);
  const isCompare = item.report_kind === "cubejs_period_compare";
  const isMarket = item.report_kind === "competitor_market_analysis";
  const isPricing = item.report_kind === "dynamic_pricing";
  const isMarketing = item.report_kind === "marketing_card_audit";
  const isMedia = item.report_kind === "media_richness_report";
  const isDescription = item.report_kind === "description_seo_report";
  const isPaidStorage = item.report_kind === "paid_storage_report";
  const isSalesReturn = item.report_kind === "sales_return_report";
  const isWaybill = item.report_kind === "waybill_cost_layer";
  const subtitle = document.getElementById("hero-subtitle");
  const titleNode = document.getElementById("report-select-label");
  const actionsTitle = document.getElementById("actions-title");
  const actionsSubtitle = document.getElementById("actions-subtitle");
  const chartsTitle = document.getElementById("charts-title");
  const chartsSubtitle = document.getElementById("charts-subtitle");
  const insightsTitle = document.getElementById("insights-title");
  const insightsSubtitle = document.getElementById("insights-subtitle");
  showSection("compare-panel", isCompare);
  showSection("trend-panel", isCompare);
  showSection("actions-panel", !isCompare);
  showSection("tables-panel", !isCompare);
  showSection("family-panel", !isCompare && !isMarket && !isPricing && !isMarketing && !isMedia && !isDescription && !isPaidStorage && !isSalesReturn && !isWaybill);
  showSection("charts-panel", !isCompare);
  if (isCompare) {
    clearOperationalPanels();
  }
  subtitle.textContent = isCompare
    ? "Интерактивный просмотр длинных периодов, сравнения год к году и истории по месяцам."
    : isMarket
    ? "Интерактивный просмотр рыночной выборки: продавцы, группы, ценовые коридоры и кластеры товарных идей."
    : isPricing
    ? "Интерактивный просмотр рекомендаций по ценам относительно рынка и вашей целевой маржи."
    : isMarketing
    ? "Интерактивный маркетинговый аудит карточек: price traps, title SEO и рыночный pricing context в одном экране."
    : isMedia
    ? "Интерактивный аудит фото, видео и характеристик карточек с привязкой к группе и приоритету действий."
    : isDescription
    ? "Интерактивный аудит description-layer: thin content, плотность текста и связь описания с title."
    : isPaidStorage
    ? "Интерактивный разбор платного хранения и услуг из seller documents с фокусом на крупнейшие начисления."
    : isSalesReturn
    ? "Интерактивный разбор возвратов и причин через CubeJS / SalesReturn с фокусом на потери и explainability."
    : isWaybill
    ? "Интерактивный слой накладных: партии поставки, batch-cost и будущая историческая себестоимость по товарам."
    : "Интерактивный просмотр операционных и исторических отчётов из слоя аналитических данных.";
  if (titleNode) {
    titleNode.textContent = REPORT_KIND_LABELS[item.report_kind] || "Отчёт";
  }
  actionsTitle.textContent = "Действия";
  actionsSubtitle.textContent = isMarket
    ? "Приоритетные списки для выбора подниш и оценки входа."
    : isPricing
    ? "Рекомендации по тому, где можно входить агрессивно, а где нужно беречь маржу."
    : isMarketing
    ? "Очереди исправлений по карточкам: цена, title и manager-facing приоритет."
    : isMedia
    ? "Приоритетные очереди по усилению фото, характеристик и визуальных отставаний относительно группы."
    : isDescription
    ? "Приоритетные очереди по переписыванию и уплотнению описаний."
    : isPaidStorage
    ? "Очереди разбора крупнейших начислений и строк, которые пока плохо идентифицируются."
    : isSalesReturn
    ? "Очереди разбора причин возврата, товарных hotspot и строк без уверенной идентификации."
    : isWaybill
    ? "Очереди сверки партий, волатильности себестоимости и пробелов identity в накладных."
    : "Приоритетные списки для weekly цикла.";
  chartsTitle.textContent = isMarket ? "Структура Рынка" : isPricing ? "Структура Ценовых Решений" : isMarketing ? "Структура Маркетинговых Сигналов" : isMedia ? "Структура Медиа-Сигналов" : isDescription ? "Структура Description-Сигналов" : isPaidStorage ? "Структура Платного Слоя" : isSalesReturn ? "Структура Возвратов" : isWaybill ? "Структура Себестоимости По Накладным" : "Распределения";
  chartsSubtitle.textContent = isMarket
    ? "Быстрый взгляд на ценовые коридоры и группы в наблюдаемой выборке."
    : isPricing
    ? "Сводка по типам ценовых рекомендаций и уровню рынка в окнах с economics coverage."
    : isMarketing
    ? "Сводка по типам карточечных проблем и очередям исправлений."
    : isMedia
    ? "Сводка по фото-стеку, плотности характеристик и визуальным отставаниям относительно группы."
    : isDescription
    ? "Сводка по длине описаний, thin content и покрытию title-термов."
    : isPaidStorage
    ? "Быстрый взгляд на концентрацию начислений и numeric-колонки, которые формируют платный слой."
    : isSalesReturn
    ? "Быстрый взгляд на доминирующие причины возврата и дневную динамику возвратов в окне."
    : isWaybill
    ? "Быстрый взгляд на концентрацию batch-cost, покрытие identity и даты поставок по накладным."
    : "Быстрый взгляд на структуру текущего окна.";
  insightsTitle.textContent = isCompare ? "Автоматические Выводы По Истории" : isMarket ? "Автоматические Выводы По Рынку" : isPricing ? "Автоматические Выводы По Ценам" : isMarketing ? "Автоматические Выводы По Карточкам" : isMedia ? "Автоматические Выводы По Медиа" : isDescription ? "Автоматические Выводы По Описаниям" : isPaidStorage ? "Автоматические Выводы По Платному Слою" : isSalesReturn ? "Автоматические Выводы По Возвратам" : isWaybill ? "Автоматические Выводы По Накладным" : "Автоматические Выводы По Окну";
  insightsSubtitle.textContent = isCompare
    ? "Что уже можно утверждать по длинному периоду, а где данных ещё недостаточно."
    : isMarket
    ? "Короткие выводы по структуре наблюдаемого рынка, продавцам и ценовым коридорам."
    : isPricing
    ? "Короткие выводы о том, где цена рынка совместима с вашей экономикой, а где демпинг опасен."
    : isMarketing
    ? "Где маркетинговые правки по карточкам могут дать самый быстрый эффект без новой закупки."
    : isMedia
    ? "Где карточки уже проигрывают по фото и характеристикам и что чинить раньше."
    : isDescription
    ? "Где description-layer слишком тонкий и как понимать силу/слабость текста."
    : isPaidStorage
    ? "Какие начисления уже выделяются, что не удаётся нормально сопоставить с SKU и где нужен ручной разбор."
    : isSalesReturn
    ? "Какая причина доминирует, где возвраты плохо объясняются и какие SKU требуют первого ручного разбора."
    : isWaybill
    ? "Где cost-layer уже собран, какие партии самые тяжёлые и где не хватает identity для полноценной historical COGS модели."
    : "Короткие интерпретации по запасам, прибыли и рискам текущего окна.";
  renderPriorityCards(item, payload, rawPayload);
  renderChangeSummary(item);
  renderMeta(payload);
  if (isMarket) {
    renderMarketKpis(payload);
  } else if (isPricing) {
    renderPricingKpis(payload);
  } else if (isPaidStorage) {
    renderPaidStorageKpis(payload);
  } else if (isSalesReturn) {
    renderSalesReturnKpis(payload);
  } else if (isWaybill) {
    renderWaybillKpis(payload);
  } else if (isMarketing) {
    renderMarketingKpis(payload);
  } else if (isMedia || isDescription) {
    renderContentAuditKpis(payload);
  } else if (isCompare) {
    renderCompareKpis(rawPayload);
  } else {
    renderKpis(payload);
  }
  if (!isCompare) {
    if (isMarket) {
      renderInsights(payload.insights || []);
      renderMarketActions(payload);
      renderMarketTables(payload);
      renderMarketCharts(payload);
    } else if (isPricing) {
      renderInsights(buildPricingInsights(payload, { formatNumber, formatMoney }));
      renderPricingActions(payload);
      renderPricingTables(payload);
      renderPricingCharts(payload);
    } else if (isMarketing) {
      renderInsights(buildMarketingInsights(payload, { formatNumber }));
      renderMarketingActions(payload);
      renderMarketingTables(payload);
      renderMarketingCharts(payload);
    } else if (isMedia) {
      renderInsights(buildMediaInsights(payload, { formatNumber }));
      renderMediaActions(payload);
      renderMediaTables(payload);
      renderMediaCharts(payload);
    } else if (isDescription) {
      renderInsights(buildDescriptionInsights(payload, { formatNumber }));
      renderDescriptionActions(payload);
      renderDescriptionTables(payload);
      renderDescriptionCharts(payload);
    } else if (isPaidStorage) {
      renderInsights(buildPaidStorageInsights(payload, { formatNumber, formatMoney }));
      renderPaidStorageActions(payload);
      renderPaidStorageTables(payload);
      renderPaidStorageCharts(payload);
    } else if (isSalesReturn) {
      renderInsights(buildSalesReturnInsights(payload, { formatNumber, formatPercent }));
      renderSalesReturnActions(payload);
      renderSalesReturnTables(payload);
      renderSalesReturnCharts(payload);
    } else if (isWaybill) {
      renderInsights(buildWaybillInsights(payload, { formatNumber, formatMoney }));
      renderWaybillActions(payload);
      renderWaybillTables(payload);
      renderWaybillCharts(payload);
    } else {
      renderInsights(buildOperationalInsights(payload, { formatNumber, formatMoney, formatPercent }));
      renderActions(payload);
      renderTables(payload);
      renderFamilyTables(payload);
      renderCharts(payload);
    }
  }
  if (isCompare) {
    renderInsights(buildCubejsInsights(rawPayload, { formatNumber, formatMoney }));
    renderCubejsCompare(rawPayload);
  }
  await refreshActionCenter().catch(() => {
    actionCenterState = null;
    renderActionCenter();
    renderEntityDetail();
  });
}

// ---------------------------------------------------------------------------
// Buyer Reviews
// ---------------------------------------------------------------------------

let reviewsToken = "";
let reviewsLlmKey = "";

function starsHtml(rating) {
  if (rating == null) return "";
  const n = Math.max(0, Math.min(5, Math.round(Number(rating))));
  return "★".repeat(n) + "☆".repeat(5 - n);
}

function getReplyLifecycleStatus(item) {
  if (item.has_answer) return "sent";
  if (!item.id || !["review", "question"].includes(item.kind)) return "unsupported";
  return "draft";
}

function replyStatusMeta(status) {
  const labels = {
    draft: { text: "draft", note: "Черновик можно править и генерировать заново до ручного approve." },
    approved: { text: "approved", note: "Текст вручную подтверждён и готов к отправке в Seller API." },
    sent: { text: "sent", note: "Ответ уже отправлен. Карточка остаётся read-only как подтверждение результата." },
    unsupported: { text: "unsupported", note: "Для этой записи send-flow недоступен: нет корректного идентификатора или тип записи не поддержан." },
  };
  return labels[status] || labels.draft;
}

function renderReviewCard(item) {
  const card = el("div", "review-card");
  card.dataset.kind = item.kind;
  if (item.rating != null) card.dataset.rating = String(item.rating);
  let replyStatus = getReplyLifecycleStatus(item);

  const header = el("div", "review-header");
  const title = el("h3", "", item.product_title || (item.kind === "question" ? "Вопрос" : "Отзыв"));
  header.append(title);
  if (item.rating != null) {
    const stars = el("span", "review-stars", starsHtml(item.rating));
    stars.title = `Оценка: ${item.rating} / 5`;
    header.append(stars);
  }
  const badge = el("span", `badge badge-${item.kind === "question" ? "offline" : "online"}`,
    item.kind === "question" ? "Вопрос" : "Отзыв");
  header.append(badge);
  const statusBadge = el("span", "", "");
  const note = el("p", "reply-note", "");
  const syncStatus = () => {
    const metaInfo = replyStatusMeta(replyStatus);
    statusBadge.className = `reply-status-badge reply-status-${replyStatus}`;
    statusBadge.textContent = metaInfo.text;
    note.textContent = metaInfo.note;
  };
  syncStatus();
  header.append(statusBadge);
  card.append(header);

  const meta = el("div", "review-meta",
    `${item.author || "Покупатель"} · ${String(item.created_at || "").slice(0, 10) || "дата н/д"} · ID ${item.id}${item.has_answer ? " · has_answer" : ""}`);
  card.append(meta);

  const text = el("p", "review-text", item.text || "(текст отсутствует)");
  card.append(text);

  const existing = el("div", "reply-existing");
  existing.append(el("span", "reply-existing-label", "Существующий ответ"));
  const existingText = el("div", "", item.answer_text || "");
  existing.append(existingText);
  existing.hidden = !item.answer_text;
  card.append(existing);

  const textarea = document.createElement("textarea");
  textarea.className = "reply-editor";
  textarea.placeholder = "Черновик ответа появится здесь после нажатия «Сгенерировать»…";
  if (item.answer_text) {
    textarea.value = item.answer_text;
  }
  card.append(textarea);

  const actions = el("div", "reply-actions");
  const strategyLabel = el("span", "reply-strategy", "");
  const approveBtn = el("button", "theme-toggle compact-button", "✓ Approve");
  approveBtn.type = "button";
  const genBtn = el("button", "theme-toggle compact-button", "✦ Сгенерировать");
  genBtn.type = "button";
  const sendBtn = el("button", "theme-toggle compact-button", "↑ Отправить");
  sendBtn.type = "button";
  const sentBadge = el("span", "reply-sent-badge", "✓ Отправлено");

  const syncButtons = () => {
    const hasDraft = Boolean(textarea.value.trim());
    const isLocked = replyStatus === "sent" || replyStatus === "unsupported";
    textarea.disabled = isLocked;
    genBtn.disabled = isLocked;
    approveBtn.disabled = isLocked || !hasDraft;
    sendBtn.disabled = isLocked || replyStatus !== "approved" || !hasDraft;
    approveBtn.textContent = replyStatus === "approved" ? "✓ Approved" : "✓ Approve";
    sentBadge.hidden = replyStatus !== "sent";
  };

  textarea.addEventListener("input", () => {
    if (replyStatus === "approved") {
      replyStatus = "draft";
      syncStatus();
    }
    syncButtons();
  });

  approveBtn.addEventListener("click", () => {
    if (replyStatus === "unsupported" || replyStatus === "sent") return;
    if (!textarea.value.trim()) {
      alert("Черновик пуст.");
      return;
    }
    replyStatus = "approved";
    syncStatus();
    syncButtons();
  });

  genBtn.addEventListener("click", async () => {
    if (replyStatus === "unsupported" || replyStatus === "sent") return;
    genBtn.disabled = true;
    genBtn.textContent = "Генерирую…";
    strategyLabel.textContent = "";
    try {
      const resp = await fetch("/api/reviews/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item, llm_api_key: reviewsLlmKey || undefined }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
      textarea.value = data.draft?.text || "";
      const strat = data.draft?.strategy || "";
      const prov = data.draft?.provider || "";
      strategyLabel.textContent = strat === "llm" ? `LLM: ${prov}` : strat === "template_fallback" ? `шаблон (LLM: ${data.draft?.llm_error || "не настроен"})` : "шаблон";
      replyStatus = "draft";
      syncStatus();
      syncButtons();
    } catch (e) {
      strategyLabel.textContent = `Ошибка: ${e.message}`;
    } finally {
      genBtn.disabled = false;
      genBtn.textContent = "✦ Сгенерировать";
      syncButtons();
    }
  });

  sendBtn.addEventListener("click", async () => {
    if (replyStatus === "unsupported" || replyStatus === "sent") return;
    const text = textarea.value.trim();
    if (!text) { alert("Черновик пуст."); return; }
    if (replyStatus !== "approved") {
      alert("Сначала подтверди черновик через Approve.");
      return;
    }
    const token = reviewsToken || (window.prompt("Access token для отправки ответа:") || "").trim();
    if (!token) { alert("Токен не задан."); return; }
    reviewsToken = token;
    approveBtn.disabled = true;
    sendBtn.disabled = true;
    sendBtn.textContent = "Отправляю…";
    try {
      const resp = await fetch("/api/reviews/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, item, text }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
      item.has_answer = true;
      item.answer_text = text;
      existingText.textContent = text;
      existing.hidden = false;
      replyStatus = "sent";
      syncStatus();
      syncButtons();
      strategyLabel.textContent = data.status === "ok" ? "Seller API: sent" : strategyLabel.textContent;
    } catch (e) {
      alert(`Ошибка отправки: ${e.message}`);
      syncButtons();
      sendBtn.textContent = "↑ Отправить";
    }
  });

  syncButtons();
  actions.append(genBtn, approveBtn, sendBtn, sentBadge, strategyLabel);
  card.append(note);
  card.append(actions);
  return card;
}

function renderBuyerReviewsToolbar() {
  const root = document.getElementById("buyer-reviews-toolbar");
  if (!root) return;
  root.innerHTML = "";

  const wrap = el("div", "inline-form");

  const tokenInput = document.createElement("input");
  tokenInput.type = "password";
  tokenInput.className = "inline-input";
  tokenInput.placeholder = "Access token (для отправки ответов)";
  tokenInput.style.minWidth = "300px";
  tokenInput.autocomplete = "off";
  tokenInput.addEventListener("input", () => { reviewsToken = tokenInput.value.trim(); });

  const llmInput = document.createElement("input");
  llmInput.type = "password";
  llmInput.className = "inline-input";
  llmInput.placeholder = "LLM API key (Gemini/DeepSeek — опционально)";
  llmInput.style.minWidth = "260px";
  llmInput.autocomplete = "off";
  llmInput.addEventListener("input", () => { reviewsLlmKey = llmInput.value.trim(); });

  const reloadBtn = el("button", "theme-toggle compact-button", "↻ Обновить список");
  reloadBtn.type = "button";
  reloadBtn.addEventListener("click", loadBuyerReviews);

  wrap.append(tokenInput, llmInput, reloadBtn);
  root.append(wrap);
}

async function loadBuyerReviews() {
  const root = document.getElementById("buyer-reviews-list");
  if (!root) return;
  root.innerHTML = '<p class="empty-state">Загрузка отзывов…</p>';
  const reloadBtn = document.querySelector("#buyer-reviews-wrap .compact-button");
  if (reloadBtn) { reloadBtn.disabled = true; reloadBtn.textContent = "Загрузка…"; }
  try {
    const resp = await fetch("/api/reviews");
    const data = await resp.json();
    const items = data.items || [];
    if (!items.length) {
      const empty = el("p", "empty-state",
        data.status === "no_data"
          ? "Нет данных. Запусти job «Отзывы и вопросы покупателей» в refresh runner, чтобы скачать отзывы."
          : "Нет отзывов или вопросов без ответа.");
      root.append(empty);
      return;
    }
    const meta = el("p", "job-card-text",
      `${items.length} элементов · обновлено ${String(data.fetched_at || "").slice(0, 19).replace("T", " ") || "н/д"}`);
    root.append(meta);
    items.forEach((item) => root.append(renderReviewCard(item)));
  } catch {
    root.append(el("p", "empty-state", "Refresh runner недоступен. Запусти web_refresh_server.py, чтобы загрузить отзывы."));
  } finally {
    if (reloadBtn) { reloadBtn.disabled = false; reloadBtn.textContent = "↻ Обновить список"; }
  }
}

function initEntityKeyNav() {
  document.addEventListener("keydown", (e) => {
    // Skip when focus is on an input/textarea/select
    if (e.target.matches("input, textarea, select")) return;
    if (!selectedEntityKey) return;
    const panel = document.getElementById("entity-detail-panel");
    if (!panel || panel.hidden) return;
    const navIndex = currentEntityRows.findIndex((item) => item.entity_key === selectedEntityKey);
    if (e.key === "ArrowRight" || e.key === "k") {
      const next = navIndex >= 0 && navIndex < currentEntityRows.length - 1 ? currentEntityRows[navIndex + 1] : null;
      if (next) { selectedEntityKey = next.entity_key; renderEntityDetail(next.row); e.preventDefault(); }
    } else if (e.key === "ArrowLeft" || e.key === "j") {
      const prev = navIndex > 0 ? currentEntityRows[navIndex - 1] : null;
      if (prev) { selectedEntityKey = prev.entity_key; renderEntityDetail(prev.row); e.preventDefault(); }
    } else if (e.key === "Escape") {
      selectedEntityKey = null;
      renderEntityDetail();
      e.preventDefault();
    }
  });
}

async function init() {
  initThemeToggle();
  initEntityKeyNav();
  decorateStaticPanelInfos();
  document.getElementById("refresh-link-top")?.setAttribute("href", refreshUiUrl());
  document.getElementById("refresh-link-bottom")?.setAttribute("href", refreshUiUrl());
  let index;
  try {
    index = await loadDashboardIndex();
  } catch (e) {
    const _initMetaGrid = document.getElementById("meta-grid");
    if (_initMetaGrid) _initMetaGrid.innerHTML = `<p class="empty-state">Не удалось загрузить индекс отчётов: ${e.message}. Запустите <code>build_dashboard_index.py</code>.</p>`;
    return;
  }
  entityHistoryIndex = await loadEntityHistoryIndex().catch(() => ({ entities: [] }));
  cogsOverrideStore = await loadLocalCogsStore().catch(() => null);
  const select = document.getElementById("report-select");
  const selectBottom = document.getElementById("report-select-bottom");
  let items = index.items || [];
  const selects = [select, selectBottom].filter(Boolean);
  dashboardItems = items;
  dashboardSelects = selects;
  populateReportSelects(selects, items);
  renderFlowMap(items, cogsOverrideStore);

  const storedFile = getStoredReportSelection();
  const initial = items.find((item) => item.file_name === storedFile) || index.latest || items[0];
  if (!initial) {
    document.getElementById("meta-grid").textContent = "Нет dashboard JSON. Сначала запусти build_dashboard_index.py.";
    return;
  }
  selects.forEach((targetSelect) => {
    targetSelect.value = initial.file_name;
  });
  await renderDashboard(initial);
  renderEntityDetail();
  const onSelectChange = async (value) => {
    const item = items.find((entry) => entry.file_name === value);
    if (!item) return;
    setStoredReportSelection(item.file_name);
    selects.forEach((targetSelect) => {
      targetSelect.value = item.file_name;
    });
    await renderDashboard(item);
  };
  selects.forEach((targetSelect) => {
    targetSelect.addEventListener("change", async () => {
      await onSelectChange(targetSelect.value);
    });
  });
  window.setInterval(async () => {
    try {
      const nextIndex = await loadDashboardIndex();
      const nextItems = nextIndex.items || [];
      const currentSignature = items.map((item) => item.file_name).join("|");
      const nextSignature = nextItems.map((item) => item.file_name).join("|");
      if (nextSignature === currentSignature) return;
      items = nextItems;
      dashboardItems = nextItems;
      const currentValue = selects[0]?.value || "";
      populateReportSelects(selects, nextItems);
      renderFlowMap(nextItems, cogsOverrideStore);
      const fallbackValue = nextItems.some((item) => item.file_name === currentValue)
        ? currentValue
        : (nextIndex.latest?.file_name || nextItems[0]?.file_name || "");
      selects.forEach((targetSelect) => {
        targetSelect.value = fallbackValue;
      });
    } catch (_) {
      // Keep the current dashboard visible if index polling fails.
    }
  }, DASHBOARD_INDEX_POLL_MS);
  const scrollTopButton = document.getElementById("scroll-top-button");
  const syncScrollTopButton = () => {
    if (!scrollTopButton) return;
    scrollTopButton.classList.toggle("visible", window.scrollY > 520);
  };
  scrollTopButton?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  window.addEventListener("scroll", syncScrollTopButton, { passive: true });
  syncScrollTopButton();
}

init().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<pre style="padding:20px">${error.message}</pre>`;
});
