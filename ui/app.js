import {
  acknowledgeEntity,
  addActionItem,
  addWatchlistItem,
  fetchJson,
  loadEntityHistoryIndex,
  loadActionCenter,
  loadDashboardIndex,
  loadLocalCogsStore,
  saveActionView,
  toggleActionItem,
  updateActionItem,
} from "./api.js";
import {
  getStoredActionFilter,
  getStoredActionOwner,
  getStoredReportSelection,
  initThemeToggle,
  setStoredActionFilter,
  setStoredActionOwner,
  setStoredReportSelection,
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

function formatMoney(value) {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value || 0);
}

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU").format(value || 0);
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "РЅ/Рґ";
  return `${value > 0 ? "+" : ""}${value}%`;
}

function formatShare(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "РЅ/Рґ";
  return `${Number(value).toFixed(1)}%`;
}

function formatWindow(window) {
  if (!window || !window.date_from || !window.date_to) return "РЅРµС‚ РѕРєРЅР°";
  return `${window.date_from.slice(0, 10)} -> ${window.date_to.slice(0, 10)}`;
}

function detectSourceMode(sourceValue) {
  const raw = String(sourceValue || "");
  if (!raw) return "РЅ/Рґ";
  if (raw.startsWith("/")) return "Р»РѕРєР°Р»СЊРЅС‹Рµ seller CSV";
  if (raw.startsWith("http://") || raw.startsWith("https://")) return "seller CSV URL";
  return "seller CSV";
}

function formatDateTime(value) {
  if (!value) return "РЅ/Рґ";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch (_) {
    return value;
  }
}

function formatEntityType(value) {
  const labels = {
    sku: "SKU",
    family: "СЃРµРјРµР№СЃС‚РІРѕ",
    seller: "РїСЂРѕРґР°РІРµС†",
    market_segment: "СЂС‹РЅРѕС‡РЅС‹Р№ СЃРµРіРјРµРЅС‚",
    unknown: "СЃСѓС‰РЅРѕСЃС‚СЊ",
  };
  return labels[value] || value || "СЃСѓС‰РЅРѕСЃС‚СЊ";
}

function formatActionStatus(value) {
  const labels = {
    open: "РЅРѕРІР°СЏ",
    in_progress: "РІ СЂР°Р±РѕС‚Рµ",
    blocked: "Р±Р»РѕРєРµСЂ",
    done: "Р·Р°РІРµСЂС€РµРЅР°",
  };
  return labels[value] || value || "РЅРѕРІР°СЏ";
}

function formatModeLabel(value) {
  const labels = {
    reused: "Р·Р°РіСЂСѓР¶РµРЅРѕ РёР· Р°СЂС…РёРІР°",
    created: "Р·Р°РїСЂРѕС€РµРЅРѕ С‡РµСЂРµР· API",
    downloaded: "СЃРєР°С‡Р°РЅРѕ РёР· seller-РѕС‚С‡С‘С‚Р°",
    online: "РѕРЅР»Р°Р№РЅ-Р·Р°РїСѓСЃРє",
    offline: "Р»РѕРєР°Р»СЊРЅР°СЏ РїРµСЂРµСЃР±РѕСЂРєР°",
    "seller analytics": "Р°РЅР°Р»РёС‚РёРєР° РїСЂРѕРґР°РІС†Р°",
  };
  return labels[value] || value || "РЅ/Рґ";
}

function describeSourceInfo(label, sourceValue, modeValue = "") {
  const source = String(sourceValue || "");
  const mode = String(modeValue || "");
  if (!source) {
    return `${label}: РёСЃС‚РѕС‡РЅРёРє РЅРµ СѓРєР°Р·Р°РЅ РІ metadata СЌС‚РѕРіРѕ bundle.`;
  }
  if (mode === "reused") {
    return `${label}: РґР°РЅРЅС‹Рµ РІР·СЏС‚С‹ РёР· СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ seller-РѕС‚С‡С‘С‚Р°, РєРѕС‚РѕСЂС‹Р№ Р±С‹Р» СЃРѕР·РґР°РЅ СЂР°РЅСЊС€Рµ Рё РїРѕРІС‚РѕСЂРЅРѕ РёСЃРїРѕР»СЊР·РѕРІР°РЅ Р±РµР· РЅРѕРІРѕРіРѕ Р·Р°РїСЂРѕСЃР° РІ MM API.`;
  }
  if (source.startsWith("/")) {
    return `${label}: РґР°РЅРЅС‹Рµ СЃС‡РёС‚Р°РЅС‹ РёР· Р»РѕРєР°Р»СЊРЅРѕ СЃРѕС…СЂР°РЅС‘РЅРЅРѕРіРѕ С„Р°Р№Р»Р°, РєРѕС‚РѕСЂС‹Р№ Р±С‹Р» РІС‹РїСѓС‰РµРЅ РїСЂРµРґС‹РґСѓС‰РёРј pipeline РёР»Рё СЂСѓС‡РЅРѕР№ РІС‹РіСЂСѓР·РєРѕР№ seller-РѕС‚С‡С‘С‚Р°.`;
  }
  if (source.startsWith("http://") || source.startsWith("https://")) {
    return `${label}: РґР°РЅРЅС‹Рµ Р±С‹Р»Рё РїРѕР»СѓС‡РµРЅС‹ РїРѕ СЃРµС‚РµРІРѕРјСѓ URL seller-РєРѕРЅС‚СѓСЂa Рё Р·Р°С‚РµРј СЃРѕС…СЂР°РЅРµРЅС‹ Р»РѕРєР°Р»СЊРЅРѕ РґР»СЏ РїРѕРІС‚РѕСЂРЅРѕРіРѕ Р°РЅР°Р»РёР·Р°.`;
  }
  return `${label}: РёСЃС‚РѕС‡РЅРёРє РїРµСЂРµРґР°РЅ РєР°Рє РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ РёР»Рё РєСЂР°С‚РєРѕРµ РёРјСЏ РІРЅСѓС‚СЂРё pipeline.`;
}

function summarizeSource(sourceValue) {
  const raw = String(sourceValue || "");
  if (!raw) return "РЅ/Рґ";
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
    total_skus: "SKU РІСЃРµРіРѕ",
    sold_skus: "SKU СЃ РїСЂРѕРґР°Р¶Р°РјРё",
    revenue_total: "Р’С‹СЂСѓС‡РєР° net",
    gross_profit_total: "Р’Р°Р»РѕРІР°СЏ РїСЂРёР±С‹Р»СЊ",
    stockout_risk_count: "Р РёСЃРє OOS",
    stale_stock_count: "Р—Р°Р»РµР¶Р°РІС€РёРµСЃСЏ",
    observed_seller_count: "РџСЂРѕРґР°РІС†РѕРІ",
    observed_group_count: "Р“СЂСѓРїРї",
    observed_price_bands: "Р¦РµРЅРѕРІС‹С… РєРѕСЂРёРґРѕСЂРѕРІ",
    observed_idea_clusters: "РљР»Р°СЃС‚РµСЂРѕРІ РёРґРµР№",
    overall_dominance_hhi: "HHI",
    novelty_proxy_index: "РРЅРґРµРєСЃ РЅРѕРІРёР·РЅС‹",
    blind_spot_windows_count: "РЎР»РµРїС‹С… Р·РѕРЅ",
    entry_ready_windows_count: "Р“РѕС‚РѕРІС‹С… РѕРєРѕРЅ РІС…РѕРґР°",
    test_entry_windows_count: "РћРєРѕРЅ РґР»СЏ С‚РµСЃС‚Р°",
    avoid_windows_count: "РћРєРѕРЅ no-go",
    priced_windows_count: "РћРєРѕРЅ СЃ С†РµРЅРѕРІРѕР№ СЂРµРєРѕРјРµРЅРґР°С†РёРµР№",
    aggressive_price_windows_count: "РђРіСЂРµСЃСЃРёРІРЅС‹Р№ РІС…РѕРґ",
    market_price_windows_count: "Р¦РµРЅР° РїРѕ СЂС‹РЅРєСѓ",
    test_price_windows_count: "РћСЃС‚РѕСЂРѕР¶РЅС‹Р№ С‚РµСЃС‚",
    do_not_discount_windows_count: "РќРµ РґРµРјРїРёРЅРіРѕРІР°С‚СЊ",
    priority_cards_count: "РљР°СЂС‚РѕС‡РµРє РІ РїСЂРёРѕСЂРёС‚РµС‚Рµ",
    price_trap_cards_count: "Р¦РµРЅРѕРІС‹С… Р»РѕРІСѓС€РµРє",
    seo_needs_work_count: "РќР°Р·РІР°РЅРёРµ С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹",
    seo_priority_fix_count: "РљСЂРёС‚РёС‡РЅС‹С… РЅР°Р·РІР°РЅРёР№",
    market_supported_cards_count: "РљР°СЂС‚РѕС‡РµРє СЃ СЂС‹РЅРѕС‡РЅС‹Рј РєРѕРЅС‚РµРєСЃС‚РѕРј",
    double_fix_count: "Р”РІРѕР№РЅС‹С… РїСЂРѕР±Р»РµРј",
    media_needs_work_count: "РњРµРґРёР° С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹",
    photo_gap_count: "РћС‚СЃС‚Р°РІР°РЅРёРµ РїРѕ С„РѕС‚Рѕ",
    spec_gap_count: "РћС‚СЃС‚Р°РІР°РЅРёРµ РїРѕ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°Рј",
    with_video_count: "РљР°СЂС‚РѕС‡РµРє СЃ РІРёРґРµРѕ",
    description_needs_work_count: "РћРїРёСЃР°РЅРёРµ С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹",
    thin_content_count: "РўРѕРЅРєРѕРµ РѕРїРёСЃР°РЅРёРµ",
    description_gap_count: "РћРїРёСЃР°РЅРёРµ СЃР»Р°Р±РµРµ РіСЂСѓРїРїС‹",
    storage_rows_count: "РЎС‚СЂРѕРє РІ РѕС‚С‡С‘С‚Рµ",
    rows_with_amount_count: "РЎС‚СЂРѕРє СЃ СЃСѓРјРјРѕР№",
    rows_without_identity_count: "РЎС‚СЂРѕРє Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё",
    total_amount: "РЎСѓРјРјР° РЅР°С‡РёСЃР»РµРЅРёР№",
    penalty_total: "РЁС‚СЂР°С„С‹ Рё СѓРґРµСЂР¶Р°РЅРёСЏ",
    avg_amount_per_row: "РЎСЂРµРґРЅСЏСЏ СЃСѓРјРјР° РЅР° СЃС‚СЂРѕРєСѓ",
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
  const snapshotInfo = ["РЎСЂРµР· РґР°РЅРЅС‹С…", formatDateTime(currentDashboardItem?.generated_at), "РљРѕРіРґР° Р±С‹Р» СЃС„РѕСЂРјРёСЂРѕРІР°РЅ РёРјРµРЅРЅРѕ СЌС‚РѕС‚ bundle Рё РѕС‚ РєР°РєРѕР№ С‚РѕС‡РєРё РІСЂРµРјРµРЅРё РЅСѓР¶РЅРѕ С‡РёС‚Р°С‚СЊ РµРіРѕ РІС‹РІРѕРґС‹."];
  const items = marketScope.category_id
    ? [
        snapshotInfo,
        ["РљР°С‚РµРіРѕСЂРёСЏ", marketScope.category_id],
        ["РЎРєР°РЅРёСЂРѕРІР°РЅРѕ СЃС‚СЂР°РЅРёС†", marketScope.pages ?? "РЅ/Рґ"],
        ["РўРѕРІР°СЂРѕРІ РЅР° СЃС‚СЂР°РЅРёС†Сѓ", marketScope.page_size ?? "РЅ/Рґ"],
        ["Р РµР¶РёРј", "СЂС‹РЅРѕС‡РЅР°СЏ РІС‹Р±РѕСЂРєР°"],
        ["РСЃС‚РѕС‡РЅРёРє", "РїСѓР±Р»РёС‡РЅС‹Р№ market API", "Р”Р°РЅРЅС‹Рµ СЃРѕР±СЂР°РЅС‹ РёР· РїСѓР±Р»РёС‡РЅРѕРіРѕ РєР°С‚Р°Р»РѕРіР° РњР°РіРЅРёС‚ РњР°СЂРєРµС‚Р°, Р° РЅРµ РёР· Р»РёС‡РЅРѕРіРѕ РєР°Р±РёРЅРµС‚Р° РїСЂРѕРґР°РІС†Р°."],
      ]
    : pricing.mode
    ? [
        snapshotInfo,
        ["Р РµР¶РёРј", formatModeLabel(pricing.mode), pricing.mode ? `Р РµР¶РёРј С†РµРЅРѕРІРѕРіРѕ СЃР»РѕСЏ: ${formatModeLabel(pricing.mode)}.` : null],
        ["Р¦РµР»РµРІР°СЏ РјР°СЂР¶Р°", pricing.target_margin_pct != null ? `${pricing.target_margin_pct}%` : "РЅ/Рґ", "Р¦РµР»РµРІР°СЏ РјР°СЂР¶Р°, РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РєРѕС‚РѕСЂРѕР№ РїРѕРґР±РёСЂР°Р»РёСЃСЊ Р±РµР·РѕРїР°СЃРЅС‹Рµ С†РµРЅРѕРІС‹Рµ СЂРµС€РµРЅРёСЏ."],
        ["РСЃС‚РѕС‡РЅРёРє СЂС‹РЅРєР°", summarizeSource(pricing.generated_from), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє СЂС‹РЅРєР°", pricing.generated_from, pricing.mode)],
        ["РћРєРЅРѕ", formatWindow(window), window.date_from && window.date_to ? `${window.date_from} -> ${window.date_to}` : null],
      ]
    : metadata.marketing_audit
    ? [
        snapshotInfo,
        ["Р РµР¶РёРј", "РјР°СЂРєРµС‚РёРЅРіРѕРІС‹Р№ Р°СѓРґРёС‚", "Р•РґРёРЅС‹Р№ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРёР№ СЃР»РѕР№, РєРѕС‚РѕСЂС‹Р№ СЃРІРѕРґРёС‚ С†РµРЅРѕРІРѕР№ Р°РЅР°Р»РёР·, С†РµРЅРѕРІС‹Рµ Р»РѕРІСѓС€РєРё Рё SEO РЅР°Р·РІР°РЅРёР№ РїРѕ РєР°СЂС‚РѕС‡РєР°Рј."],
        ["РСЃС‚РѕС‡РЅРёРє С†РµРЅРѕРІРѕРіРѕ СЃР»РѕСЏ", summarizeSource(metadata.marketing_audit.pricing_json), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє С†РµРЅРѕРІРѕРіРѕ СЃР»РѕСЏ", metadata.marketing_audit.pricing_json)],
        ["РСЃС‚РѕС‡РЅРёРє price trap", summarizeSource(metadata.marketing_audit.price_trap_json), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє price trap", metadata.marketing_audit.price_trap_json)],
        ["РСЃС‚РѕС‡РЅРёРє title SEO", summarizeSource(metadata.marketing_audit.title_seo_json), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє title SEO", metadata.marketing_audit.title_seo_json)],
        ["РСЃС‚РѕС‡РЅРёРє normalized", summarizeSource(metadata.marketing_audit.normalized_json), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє normalized", metadata.marketing_audit.normalized_json)],
      ]
    : metadata.content_audit
    ? [
        snapshotInfo,
        ["Р РµР¶РёРј", "РєРѕРЅС‚РµРЅС‚-Р°СѓРґРёС‚", "РЎР»РѕР№ РїСЂРѕРІРµСЂРєРё РјРµРґРёР° РёР»Рё РѕРїРёСЃР°РЅРёР№ РєР°СЂС‚РѕС‡РєРё РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РіСЂСѓРїРїС‹ Рё РјРёРЅРёРјР°Р»СЊРЅРѕРіРѕ quality bar."],
        ["РСЃС‚РѕС‡РЅРёРє РІС…РѕРґР°", summarizeSource(metadata.content_audit.input_json), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє РІС…РѕРґР°", metadata.content_audit.input_json)],
        ["РљСЌС€ РєР°СЂС‚РѕС‡РµРє", summarizeSource(metadata.content_audit.cache_json), describeSourceInfo("РљСЌС€ РєР°СЂС‚РѕС‡РµРє", metadata.content_audit.cache_json)],
        ["РЎРµС‚СЊ", metadata.content_audit.cache_only ? "С‚РѕР»СЊРєРѕ РєСЌС€" : "РєСЌС€ + РїСѓР±Р»РёС‡РЅС‹Р№ API", metadata.content_audit.cache_only ? "РЎРµС‚СЊ РЅРµ РёСЃРїРѕР»СЊР·РѕРІР°Р»Р°СЃСЊ: Р°СѓРґРёС‚ РїРѕСЃС‚СЂРѕРµРЅ С‚РѕР»СЊРєРѕ РїРѕ Р»РѕРєР°Р»СЊРЅРѕРјСѓ РєСЌС€Сѓ РєР°СЂС‚РѕС‡РµРє." : "РђСѓРґРёС‚ РёСЃРїРѕР»СЊР·РѕРІР°Р» Р»РѕРєР°Р»СЊРЅС‹Р№ РєСЌС€ Рё РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё РїСѓР±Р»РёС‡РЅС‹Р№ product API."],
      ]
    : metadata.paid_storage
    ? [
        snapshotInfo,
        ["Р РµР¶РёРј", formatModeLabel(documents.paid_storage_mode || metadata.paid_storage.mode || "reused"), "Р‘РµСЂС‘С‚СЃСЏ РїРѕСЃР»РµРґРЅРёР№ completed PAID_STORAGE_REPORT РёР· seller documents Рё СЂР°Р·РІРѕСЂР°С‡РёРІР°РµС‚СЃСЏ РІ manager-facing СЌРєСЂР°РЅ Р·Р°С‚СЂР°С‚."],
        ["РСЃС‚РѕС‡РЅРёРє С„Р°Р№Р»Р°", summarizeSource(metadata.paid_storage.xlsx_path || documents.paid_storage_file_name), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє С„Р°Р№Р»Р°", metadata.paid_storage.xlsx_path || documents.paid_storage_file_name, documents.paid_storage_mode)],
        ["Р›РёСЃС‚ XLSX", metadata.paid_storage.sheet_name || "РЅ/Рґ", "РџРµСЂРІС‹Р№ Р»РёСЃС‚, РєРѕС‚РѕСЂС‹Р№ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ РёР· XLSX-РѕС‚С‡С‘С‚Р°."],
        ["Р“Р»Р°РІРЅР°СЏ РєРѕР»РѕРЅРєР° СЃСѓРјРјС‹", metadata.paid_storage.amount_header || "РЅ/Рґ", "Р­РІСЂРёСЃС‚РёС‡РµСЃРєРё РІС‹Р±СЂР°РЅРЅР°СЏ РѕСЃРЅРѕРІРЅР°СЏ РґРµРЅРµР¶РЅР°СЏ РєРѕР»РѕРЅРєР°, РїРѕ РєРѕС‚РѕСЂРѕР№ РѕС‚СЃРѕСЂС‚РёСЂРѕРІР°РЅС‹ РєСЂСѓРїРЅРµР№С€РёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ."],
        ["Р—Р°РїСЂРѕСЃ seller documents", documents.paid_storage_request_id || "РЅ/Рґ", "Request ID РёР· seller documents, РµСЃР»Рё РѕС‚С‡С‘С‚ Р±С‹Р» РїРѕРґС‚СЏРЅСѓС‚ online, Р° РЅРµ РїРµСЂРµРґР°РЅ Р»РѕРєР°Р»СЊРЅС‹Рј С„Р°Р№Р»РѕРј."],
      ]
    : (() => {
        const baseItems = [
          snapshotInfo,
          ["РћРєРЅРѕ", formatWindow(window), window.date_from && window.date_to ? `Р”Р°РЅРЅС‹Рµ РѕС‚С‡С‘С‚Р° РїРѕРєСЂС‹РІР°СЋС‚ РїРµСЂРёРѕРґ ${window.date_from} -> ${window.date_to}.` : "РЈ СЌС‚РѕРіРѕ bundle РЅРµС‚ СЏРІРЅРѕРіРѕ РѕРєРЅР° РґР°С‚ РІ metadata."],
          ["Р”РЅРµР№", window.window_days ?? "РЅ/Рґ", null],
          ["Р РµР¶РёРј", formatModeLabel(sellsMode), sellsMode ? `РљР°Рє Р±С‹Р»Рё РїРѕР»СѓС‡РµРЅС‹ РґР°РЅРЅС‹Рµ РїСЂРѕРґР°Р¶: ${formatModeLabel(sellsMode)}.` : null],
          ["РСЃС‚РѕС‡РЅРёРє РїСЂРѕРґР°Р¶", summarizeSource(sellsSource), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє РїСЂРѕРґР°Р¶", sellsSource, documents.sells_mode)],
          ["РСЃС‚РѕС‡РЅРёРє РѕСЃС‚Р°С‚РєРѕРІ", summarizeSource(leftSource), describeSourceInfo("РСЃС‚РѕС‡РЅРёРє РѕСЃС‚Р°С‚РєРѕРІ", leftSource, documents.left_out_mode)],
        ];
        if (documents.sells_request_id) {
          baseItems.push(["Р—Р°РїСЂРѕСЃ РїСЂРѕРґР°Р¶", documents.sells_request_id, null]);
        }
        if (documents.left_out_request_id) {
          baseItems.push(["Р—Р°РїСЂРѕСЃ РѕСЃС‚Р°С‚РєРѕРІ", documents.left_out_request_id, null]);
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
    "Р‘РµР· РЅР°Р·РІР°РЅРёСЏ"
  );
  const sku = getPrimarySku(row);
  if (sku && title && !String(title).includes(String(sku))) {
    return `${sku} В· ${title}`;
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
    ["#kpi-panel .panel-header h2", "РљР»СЋС‡РµРІС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё СЌС‚Рѕ РІРµСЂС…РЅРёР№ С‡РёСЃР»РѕРІРѕР№ СЃР»РѕР№ РѕС‚С‡С‘С‚Р°. РС… Р·Р°РґР°С‡Р° РЅРµ Р·Р°РјРµРЅРёС‚СЊ РІРµСЃСЊ Р°РЅР°Р»РёР·, Р° Р±С‹СЃС‚СЂРѕ РїРѕРєР°Р·Р°С‚СЊ РјР°СЃС€С‚Р°Р± РїСЂРѕР±Р»РµРјС‹, РІС‹Р±РѕСЂРєРё Рё РґРµРЅРµРі РґРѕ РїРµСЂРµС…РѕРґР° Рє РґРµР№СЃС‚РІРёСЏРј."],
    ["#priority-panel .panel-header h2", "Р­С‚РѕС‚ Р±Р»РѕРє РѕС‚РІРµС‡Р°РµС‚ РЅР° РІРѕРїСЂРѕСЃ: С‡С‚Рѕ РґРµР»Р°С‚СЊ РїРµСЂРІС‹Рј. РћРЅ РЅРµ РїРµСЂРµС‡РёСЃР»СЏРµС‚ РІСЃС‘ РїРѕРґСЂСЏРґ, Р° РїРѕРґРЅРёРјР°РµС‚ СЂРµС€РµРЅРёСЏ, РєРѕС‚РѕСЂС‹Рµ СЃРµР№С‡Р°СЃ РІР°Р¶РЅРµРµ РѕСЃС‚Р°Р»СЊРЅС‹С…."],
    ["#change-panel .panel-header h2", "РЎСЂР°РІРЅРµРЅРёРµ СЃ РїСЂРµРґС‹РґСѓС‰РёРј РѕС‚С‡С‘С‚РѕРј С‚РѕРіРѕ Р¶Рµ С‚РёРїР°. Р—РґРµСЃСЊ РІР°Р¶РЅРѕ СЃРјРѕС‚СЂРµС‚СЊ РЅРµ С‚РѕР»СЊРєРѕ РЅР° СЂРѕСЃС‚, РЅРѕ Рё РЅР° С‚Рѕ, Р·Р° РєР°РєРѕР№ РїРµСЂРёРѕРґ Рё РёР· РєР°РєРѕР№ РІС‹Р±РѕСЂРєРё СЌС‚РѕС‚ СЂРѕСЃС‚ РїРѕР»СѓС‡РµРЅ."],
    ["#insights-panel .panel-header h2", "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ РІС‹РІРѕРґС‹ СЌС‚Рѕ РёРЅС‚РµСЂРїСЂРµС‚Р°С†РёРё РїРѕРІРµСЂС… РґР°РЅРЅС‹С…. РћРЅРё РґРѕР»Р¶РЅС‹ РїРѕРјРѕРіР°С‚СЊ С‡РёС‚Р°С‚СЊ РѕС‚С‡С‘С‚ Р±С‹СЃС‚СЂРµРµ, РЅРѕ РЅРµ РїРѕРґРјРµРЅСЏСЋС‚ СЂСѓС‡РЅСѓСЋ РїСЂРѕРІРµСЂРєСѓ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРѕРіРѕ СЂРµС€РµРЅРёСЏ."],
    ["#compare-panel .panel-header h2", "Р­С‚РѕС‚ Р±Р»РѕРє РЅСѓР¶РµРЅ РґР»СЏ РґР»РёРЅРЅРѕР№ РёСЃС‚РѕСЂРёРё Рё СЃРµР·РѕРЅРЅРѕСЃС‚Рё. Р•РіРѕ С‡РёС‚Р°СЋС‚ РѕС‚РґРµР»СЊРЅРѕ РѕС‚ РєРѕСЂРѕС‚РєРёС… operational-РѕРєРѕРЅ."],
    ["#actions-panel .panel-header h2", "Р—РґРµСЃСЊ СЃРѕР±СЂР°РЅС‹ РїСЂРёРєР»Р°РґРЅС‹Рµ РѕС‡РµСЂРµРґРё РґРµР№СЃС‚РІРёР№. Р­С‚Рѕ СЂР°Р±РѕС‡РёР№ СЃР»РѕР№, РёР· РєРѕС‚РѕСЂРѕРіРѕ РјРµРЅРµРґР¶РµСЂ Р±РµСЂС‘С‚ Р·Р°РґР°С‡Рё РІ СЂР°Р±РѕС‚Сѓ, Р° РЅРµ РїСЂРѕСЃС‚Рѕ С‡РёС‚Р°РµС‚ С†РёС„СЂС‹."],
    ["#action-center-panel .panel-header h2", "Р¦РµРЅС‚СЂ РґРµР№СЃС‚РІРёР№ СЌС‚Рѕ СЂСѓС‡РЅРѕР№ СЃР»РѕР№ РїРѕРІРµСЂС… Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёС… СЃРёРіРЅР°Р»РѕРІ. Р—РґРµСЃСЊ РјРµРЅРµРґР¶РµСЂ СЃРѕС…СЂР°РЅСЏРµС‚ short-list, С„РёРєСЃРёСЂСѓРµС‚ Р·Р°РґР°С‡Сѓ Рё РІРµРґС‘С‚ СЃС‚Р°С‚СѓСЃ РґРѕ Р·Р°РІРµСЂС€РµРЅРёСЏ."],
    ["#manager-queues-panel .panel-header h2", "Р­С‚Рѕ Р°РіСЂРµРіРёСЂРѕРІР°РЅРЅС‹Рµ РѕС‡РµСЂРµРґРё РїРѕ СЃС‚Р°С‚СѓСЃР°Рј, РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Рј Рё СЃРѕС…СЂР°РЅС‘РЅРЅС‹Рј РїСЂРµРґСЃС‚Р°РІР»РµРЅРёСЏРј. РћРЅРё РЅСѓР¶РЅС‹, С‡С‚РѕР±С‹ РІРёРґРµС‚СЊ bottleneck РµР¶РµРґРЅРµРІРЅРѕРіРѕ С†РёРєР»Р°, Р° РЅРµ С‚РѕР»СЊРєРѕ РѕС‚РґРµР»СЊРЅС‹Рµ Р·Р°РґР°С‡Рё."],
    ["#entity-detail-panel .panel-header h2", "Р”РµС‚Р°Р»СЊРЅР°СЏ РєР°СЂС‚РѕС‡РєР° СЃСѓС‰РЅРѕСЃС‚Рё РЅСѓР¶РЅР° РґР»СЏ drilldown: РїРѕСЃРјРѕС‚СЂРµС‚СЊ С‚РµРєСѓС‰РёР№ СЃРёРіРЅР°Р», РёСЃС‚РѕСЂРёСЋ РїРѕСЏРІР»РµРЅРёСЏ РІ РѕС‚С‡С‘С‚Р°С… Рё СЂСѓС‡РЅРѕР№ follow-up РїРѕ СЌС‚РѕР№ РїРѕР·РёС†РёРё."],
    ["#charts-panel .panel-header h2", "Р Р°СЃРїСЂРµРґРµР»РµРЅРёСЏ РїРѕРјРѕРіР°СЋС‚ СѓРІРёРґРµС‚СЊ СЃС‚СЂСѓРєС‚СѓСЂСѓ РѕРєРЅР°: РіРґРµ РєРѕРЅС†РµРЅС‚СЂРёСЂСѓРµС‚СЃСЏ СЂРµР·СѓР»СЊС‚Р°С‚, РіРґРµ РґР»РёРЅРЅС‹Р№ С…РІРѕСЃС‚ Рё РіРґРµ С€СѓРј. Р­С‚Рѕ РІСЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Р№ СЃР»РѕР№, Р° РЅРµ РїСЂРёРѕСЂРёС‚РµС‚ СЃР°Рј РїРѕ СЃРµР±Рµ."],
    ["#trend-panel .panel-header h2", "РСЃС‚РѕСЂРёСЏ РїРѕ РјРµСЃСЏС†Р°Рј РЅСѓР¶РЅР° РґР»СЏ РЅР°РєРѕРїР»РµРЅРёСЏ seasonality Рё СЃСЂР°РІРЅРµРЅРёСЏ РґР»РёРЅРЅС‹С… РїРµСЂРёРѕРґРѕРІ. Р­С‚РѕС‚ Р±Р»РѕРє РїРѕР»РµР·РµРЅ С‚РѕР»СЊРєРѕ РµСЃР»Рё РІСЂРµРјРµРЅРЅРѕР№ СЂСЏРґ СѓР¶Рµ РґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР»РёРЅРЅС‹Р№."],
    ["#meta-panel .panel-header h2", "РЎРІРѕРґРєР° РѕС‚С‡С‘С‚Р° РїРѕРєР°Р·С‹РІР°РµС‚ РїРµСЂРёРѕРґ, СЂРµР¶РёРј РїРѕР»СѓС‡РµРЅРёСЏ РґР°РЅРЅС‹С… Рё РїСЂРѕРёСЃС…РѕР¶РґРµРЅРёРµ РёСЃС‚РѕС‡РЅРёРєРѕРІ. РЎ РЅРµС‘ РЅР°РґРѕ РЅР°С‡РёРЅР°С‚СЊ С‡С‚РµРЅРёРµ Р»СЋР±РѕРіРѕ РѕС‚С‡С‘С‚Р°, С‡С‚РѕР±С‹ РЅРµ РїСѓС‚Р°С‚СЊ РѕРєРЅР° Рё С‚РёРїС‹ РґР°РЅРЅС‹С…."],
    [".utility-panel .panel-header h2", "РќР°РІРёРіР°С†РёСЏ СЌС‚Рѕ РІСЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Р№ СЃРµСЂРІРёСЃРЅС‹Р№ Р±Р»РѕРє: Р±С‹СЃС‚СЂРѕ РїРµСЂРµР№С‚Рё Рє РґСЂСѓРіРѕРјСѓ РѕС‚С‡С‘С‚Сѓ, refresh runner РёР»Рё РІРµСЂРЅСѓС‚СЊСЃСЏ РІРІРµСЂС… СЃС‚СЂР°РЅРёС†С‹."],
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
    ["SKU РІСЃРµРіРѕ", formatNumber(kpis.total_skus), "РЎРєРѕР»СЊРєРѕ СЃС‚СЂРѕРє РёР»Рё SKU РїРѕРїР°Р»Рѕ РІ С‚РµРєСѓС‰РµРµ РѕРєРЅРѕ РѕС‚С‡С‘С‚Р°. Р­С‚Рѕ СЂР°Р·РјРµСЂ РЅР°Р±Р»СЋРґР°РµРјРѕР№ РІС‹Р±РѕСЂРєРё."],
    ["SKU СЃ РїСЂРѕРґР°Р¶Р°РјРё", formatNumber(kpis.sold_skus), "РЎРєРѕР»СЊРєРѕ SKU СЂРµР°Р»СЊРЅРѕ РёРјРµР»Рё РїСЂРѕРґР°Р¶Рё РІ РІС‹Р±СЂР°РЅРЅРѕРј РїРµСЂРёРѕРґРµ. Р­С‚Рѕ РѕРґРёРЅ РёР· РіР»Р°РІРЅС‹С… РёРЅРґРёРєР°С‚РѕСЂРѕРІ Р¶РёРІРѕСЃС‚Рё Р°СЃСЃРѕСЂС‚РёРјРµРЅС‚Р° СЃРµР№С‡Р°СЃ."],
    ["Р’С‹СЂСѓС‡РєР° net", formatMoney(kpis.revenue_total), "Р’С‹СЂСѓС‡РєР° Р·Р° РѕРєРЅРѕ РїРѕСЃР»Рµ РІС‹С‡РµС‚Р° РєРѕРјРёСЃСЃРёРё РјР°СЂРєРµС‚РїР»РµР№СЃР°. РСЃРїРѕР»СЊР·СѓР№С‚Рµ РґР»СЏ РѕС†РµРЅРєРё СЂРµР°Р»СЊРЅРѕРіРѕ РґРµРЅРµР¶РЅРѕРіРѕ РїРѕС‚РѕРєР° РїРѕ РїРµСЂРёРѕРґСѓ."],
    ["Р’Р°Р»РѕРІР°СЏ РїСЂРёР±С‹Р»СЊ", formatMoney(kpis.gross_profit_total), "Net revenue РјРёРЅСѓСЃ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚СЊ. Р­С‚Рѕ РѕСЂРёРµРЅС‚РёСЂ, РєР°РєРёРµ С‚РѕРІР°СЂС‹ Рё РѕРєРЅР° СЂРµР°Р»СЊРЅРѕ Р·Р°СЂР°Р±Р°С‚С‹РІР°СЋС‚ РґРµРЅСЊРіРё, Р° РЅРµ С‚РѕР»СЊРєРѕ РєСЂСѓС‚СЏС‚ РѕР±РѕСЂРѕС‚."],
    ["Р РёСЃРє OOS", formatNumber(kpis.stockout_risk_count), "РЎРєРѕР»СЊРєРѕ SKU РёРјРµСЋС‚ СЂРёСЃРє Р·Р°РєРѕРЅС‡РёС‚СЊСЃСЏ РїРѕ С‚РµРєСѓС‰РµРјСѓ СЃСЂРµРґРЅРµСЃСѓС‚РѕС‡РЅРѕРјСѓ С‚РµРјРїСѓ. Р’С‹СЃРѕРєРѕРµ Р·РЅР°С‡РµРЅРёРµ С‚СЂРµР±СѓРµС‚ РїСЂРёРѕСЂРёС‚РёР·Р°С†РёРё Р·Р°РєСѓРїРєРё."],
    ["Р—Р°Р»РµР¶Р°РІС€РёРµСЃСЏ", formatNumber(kpis.stale_stock_count), "РЎРєРѕР»СЊРєРѕ SKU Р»РµР¶Р°С‚ Р±РµР· РґРІРёР¶РµРЅРёСЏ РІ С‚РµРєСѓС‰РµРј РѕРєРЅРµ. Р­С‚Рѕ РєР°РЅРґРёРґР°С‚С‹ РЅР° С‡РёСЃС‚РєСѓ, РїРµСЂРµСЃР±РѕСЂРєСѓ РѕС„С„РµСЂР° РёР»Рё СѓС†РµРЅРєСѓ."],
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
    ["РљР°СЂС‚РѕС‡РµРє РІ Р°СѓРґРёС‚Рµ", formatNumber(kpis.total_skus), "РЎРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РµРє РїРѕРїР°Р»Рѕ РІ С‚РµРєСѓС‰РёР№ РєРѕРЅС‚РµРЅС‚-Р°СѓРґРёС‚."],
    ["РЎ РїСЂРѕРґР°Р¶Р°РјРё", formatNumber(kpis.sold_skus), "РЎРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РµРє РёР· РІС‹Р±РѕСЂРєРё РёРјРµР»Рё РїСЂРѕРґР°Р¶Рё РІ С‚РµРєСѓС‰РµРј РѕРїРµСЂР°С†РёРѕРЅРЅРѕРј РєРѕРЅС‚РµРєСЃС‚Рµ."],
    ["Р’ РїСЂРёРѕСЂРёС‚РµС‚Рµ", formatNumber(kpis.priority_cards_count), "РЎРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РµРє С‚СЂРµР±СѓСЋС‚ СЃР°РјРѕРіРѕ СЂР°РЅРЅРµРіРѕ РІРЅРёРјР°РЅРёСЏ РїРѕ СЌС‚РѕРјСѓ СЃР»РѕСЋ Р°СѓРґРёС‚Р°."],
    [kpis.media_needs_work_count !== undefined ? "РњРµРґРёР° С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹" : "РћРїРёСЃР°РЅРёРµ С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹", formatNumber(kpis.media_needs_work_count ?? kpis.description_needs_work_count), "РћР±С‰РёР№ СЃР»РѕР№ РєР°СЂС‚РѕС‡РµРє СЃРѕ СЃСЂРµРґРЅРёРј, РЅРѕ РЅРµ РєСЂРёС‚РёС‡РЅС‹Рј СѓСЂРѕРІРЅРµРј РїСЂРѕР±Р»РµРј."],
    [kpis.photo_gap_count !== undefined ? "РћС‚СЃС‚Р°РІР°РЅРёРµ РїРѕ С„РѕС‚Рѕ" : "РўРѕРЅРєРѕРµ РѕРїРёСЃР°РЅРёРµ", formatNumber(kpis.photo_gap_count ?? kpis.thin_content_count), kpis.photo_gap_count !== undefined ? "Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚ РѕС‚СЃС‚Р°РІР°РЅРёРµ РѕС‚ СЃРІРѕРµР№ РіСЂСѓРїРїС‹: РЅР°СЃРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РєРµ РЅРµ С…РІР°С‚Р°РµС‚ С„РѕС‚Рѕ РґРѕ С‚РёРїРёС‡РЅРѕРіРѕ СѓСЂРѕРІРЅСЏ РїРѕС…РѕР¶РёС… С‚РѕРІР°СЂРѕРІ." : "РЎРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РµРє РёРјРµСЋС‚ СЃР»РёС€РєРѕРј РєРѕСЂРѕС‚РєРѕРµ РѕРїРёСЃР°РЅРёРµ."],
    [kpis.spec_gap_count !== undefined ? "РћС‚СЃС‚Р°РІР°РЅРёРµ РїРѕ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°Рј" : "РћС‚СЃС‚Р°РІР°РЅРёРµ РѕС‚ РіСЂСѓРїРїС‹", formatNumber(kpis.spec_gap_count ?? kpis.description_gap_count), kpis.spec_gap_count !== undefined ? "Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚ РѕС‚СЃС‚Р°РІР°РЅРёРµ РѕС‚ СЃРІРѕРµР№ РіСЂСѓРїРїС‹: РЅР°СЃРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РєРµ РЅРµ С…РІР°С‚Р°РµС‚ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РїРѕС…РѕР¶РёС… С‚РѕРІР°СЂРѕРІ." : "Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚ РѕС‚СЃС‚Р°РІР°РЅРёРµ РѕС‚ РјРµРґРёР°РЅС‹ СЃРІРѕРµР№ РіСЂСѓРїРїС‹ РїРѕ РѕР±СЉС‘РјСѓ РѕРїРёСЃР°РЅРёСЏ."],
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
    ["РўРѕРІР°СЂРѕРІ РІ РІС‹Р±РѕСЂРєРµ", formatNumber(kpis.total_skus), "РЎРєРѕР»СЊРєРѕ С‚РѕРІР°СЂРѕРІ СѓРґР°Р»РѕСЃСЊ РЅР°Р±Р»СЋРґР°С‚СЊ РІ С‚РµРєСѓС‰РµРј СЂС‹РЅРѕС‡РЅРѕРј РїСЂРѕС…РѕРґРµ. Р­С‚Рѕ РЅРµ РІРµСЃСЊ СЂС‹РЅРѕРє, Р° С‚РµРєСѓС‰Р°СЏ РІС‹Р±РѕСЂРєР°."],
    ["РџСЂРѕРґР°РІС†РѕРІ", formatNumber(kpis.observed_seller_count ?? kpis.stockout_risk_count), "РЎРєРѕР»СЊРєРѕ РїСЂРѕРґР°РІС†РѕРІ РІСЃС‚СЂРµС‚РёР»РѕСЃСЊ РІ РЅР°Р±Р»СЋРґР°РµРјРѕР№ РІС‹Р±РѕСЂРєРµ РєР°С‚РµРіРѕСЂРёРё."],
    ["Р“СЂСѓРїРї", formatNumber(kpis.observed_group_count ?? kpis.stale_stock_count), "РЎРєРѕР»СЊРєРѕ С‚РѕРІР°СЂРЅС‹С… РіСЂСѓРїРї СЂРµР°Р»СЊРЅРѕ РїСЂРѕСЏРІРёР»РёСЃСЊ РІ РЅР°Р±Р»СЋРґР°РµРјРѕР№ РІС‹Р±РѕСЂРєРµ."],
    ["Р¦РµРЅРѕРІС‹С… РєРѕСЂРёРґРѕСЂРѕРІ", formatNumber(kpis.observed_price_bands), "РЎРєРѕР»СЊРєРѕ С†РµРЅРѕРІС‹С… РґРёР°РїР°Р·РѕРЅРѕРІ Р·Р°РЅСЏС‚Рѕ С‚РѕРІР°СЂР°РјРё СЃ РїСЂРѕРґР°Р¶Р°РјРё РІ С‚РµРєСѓС‰РµРј market scan."],
    ["РљР»Р°СЃС‚РµСЂС‹ РёРґРµР№", formatNumber(kpis.observed_idea_clusters), "РЎРєРѕР»СЊРєРѕ РїРѕРІС‚РѕСЂСЏСЋС‰РёС…СЃСЏ С‚РѕРІР°СЂРЅС‹С… РёРґРµР№ СѓРґР°Р»РѕСЃСЊ РІС‹РґРµР»РёС‚СЊ СЌРІСЂРёСЃС‚РёС‡РµСЃРєРё. РџРѕР»РµР·РЅРѕ РґР»СЏ РїРѕРёСЃРєР° РЅР°РїСЂР°РІР»РµРЅРёР№ СЂР°СЃС€РёСЂРµРЅРёСЏ."],
    ["HHI РєРѕРЅС†РµРЅС‚СЂР°С†РёРё", kpis.overall_dominance_hhi ?? "РЅ/Рґ", "HHI РїРѕРєР°Р·С‹РІР°РµС‚, РЅР°СЃРєРѕР»СЊРєРѕ СЂС‹РЅРѕРє СЃРѕР±СЂР°РЅ Сѓ РЅРµРјРЅРѕРіРёС… РїСЂРѕРґР°РІС†РѕРІ. РќРёР¶Рµ 1500 РѕР±С‹С‡РЅРѕ Р»РµРіС‡Рµ Р·Р°С…РѕРґРёС‚СЊ, РІС‹С€Рµ 2500 СЂС‹РЅРѕРє СѓР¶Рµ РїР»РѕС‚РЅС‹Р№ Рё РєРѕРЅС†РµРЅС‚СЂРёСЂРѕРІР°РЅРЅС‹Р№."],
    ["РРЅРґРµРєСЃ РЅРѕРІРёР·РЅС‹", kpis.novelty_proxy_index ?? "РЅ/Рґ", "Р­С‚Рѕ РїСЂРѕРєСЃРё, Р° РЅРµ СЂРµР°Р»СЊРЅС‹Р№ РІРѕР·СЂР°СЃС‚ РєР°СЂС‚РѕС‡РµРє. РћРЅ СЃС‚СЂРѕРёС‚СЃСЏ РїРѕ СЃРІСЏР·РєРµ orders/reviews Сѓ Р»РёРґРµСЂРѕРІ Рё РїРѕРєР°Р·С‹РІР°РµС‚, РЅР°СЃРєРѕР»СЊРєРѕ РІ РєР°С‚РµРіРѕСЂРёРё РµС‰С‘ РјРѕРіСѓС‚ Р±С‹СЃС‚СЂРѕ СЂР°СЃС‚Рё РЅРѕРІС‹Рµ РєР°СЂС‚РѕС‡РєРё."],
    ["Р”РѕР»СЏ В«РџСЂРѕС‡РµРµВ»", formatShare(kpis.other_group_share_pct), "Р§РµРј РЅРёР¶Рµ РґРѕР»СЏ В«РџСЂРѕС‡РµРµВ», С‚РµРј С‚РѕС‡РЅРµРµ market-РєР»Р°СЃСЃРёС„РёРєР°С‚РѕСЂ Рё С‚РµРј РЅР°РґС‘Р¶РЅРµРµ РІС‹РІРѕРґС‹ РїРѕ РЅРёС€Р°Рј."],
    ["РџРѕРєСЂС‹С‚РёРµ СЌРєРѕРЅРѕРјРёРєРё", `${formatShare(kpis.economics_coverage_windows_pct)} РѕРєРѕРЅ`, "РќР° РєР°РєРѕР№ РґРѕР»Рµ РѕРєРѕРЅ РІС…РѕРґР° СЃРёСЃС‚РµРјР° СѓР¶Рµ РјРѕР¶РµС‚ СЃРѕРїРѕСЃС‚Р°РІРёС‚СЊ СЂС‹РЅРѕС‡РЅСѓСЋ С†РµРЅСѓ СЃ РІР°С€РµР№ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚СЊСЋ. РќРёР·РєРѕРµ РїРѕРєСЂС‹С‚РёРµ РѕР·РЅР°С‡Р°РµС‚: СЂС‹РЅРѕРє РІРёРґРµРЅ, РЅРѕ РІС‹РІРѕРґС‹ РїРѕ РїСЂРёР±С‹Р»Рё РµС‰С‘ РЅРµРїРѕР»РЅС‹Рµ."],
    ["Р¦РµР»РµРІР°СЏ РјР°СЂР¶Р°", kpis.target_margin_pct != null ? `${kpis.target_margin_pct}%` : "РЅ/Рґ", "РџРѕСЂРѕРі РјР°СЂР¶Рё, РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РєРѕС‚РѕСЂРѕРіРѕ РѕС†РµРЅРёРІР°РµС‚СЃСЏ, РЅР°СЃРєРѕР»СЊРєРѕ СЂС‹РЅРѕС‡РЅР°СЏ С†РµРЅР° РІРѕРѕР±С‰Рµ СЃРѕРІРјРµСЃС‚РёРјР° СЃ РІР°С€РµР№ СЌРєРѕРЅРѕРјРёРєРѕР№."],
    ["РЎР»РµРїС‹Рµ Р·РѕРЅС‹", formatNumber(kpis.blind_spot_windows_count), "РЎРєРѕР»СЊРєРѕ РѕРєРѕРЅ РІС…РѕРґР° РІС‹РіР»СЏРґСЏС‚ РёРЅС‚РµСЂРµСЃРЅС‹РјРё РїРѕ СЃРїСЂРѕСЃСѓ, РЅРѕ РµС‰С‘ РЅРµ РїРѕРєСЂС‹С‚С‹ РІР°С€РёРјРё cost-РґР°РЅРЅС‹РјРё. Р­С‚Рѕ СЃРїРёСЃРѕРє С‚РѕРіРѕ, РіРґРµ РЅРµР»СЊР·СЏ РїСЂРёРЅРёРјР°С‚СЊ СЂРµС€РµРЅРёРµ РІСЃР»РµРїСѓСЋ."],
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
    ["Р’С‹СЂСѓС‡РєР° Р·Р° 365 РґРЅРµР№", formatMoney(metrics.revenue_total || 0), "Р“Р»Р°РІРЅР°СЏ РІС‹СЂСѓС‡РєР° Р·Р° С‚РµРєСѓС‰РµРµ trailing-year РѕРєРЅРѕ."],
    ["Р—Р°РєР°Р·С‹ Р·Р° 365 РґРЅРµР№", formatNumber(metrics.orders_total || 0), "РЎРєРѕР»СЊРєРѕ Р·Р°РєР°Р·РѕРІ РЅР°РєРѕРїРёР»РѕСЃСЊ РІ С‚РµРєСѓС‰РµРј trailing-year РѕРєРЅРµ."],
    ["РџСЂРѕРґР°РЅРЅС‹Рµ РµРґРёРЅРёС†С‹", formatNumber(metrics.items_sold_total || 0), "РЎРєРѕР»СЊРєРѕ РµРґРёРЅРёС† С‚РѕРІР°СЂР° РїСЂРѕРґР°РЅРѕ Р·Р° РїРѕСЃР»РµРґРЅРёРµ 365 РґРЅРµР№."],
    ["Р—Р°РїРѕР»РЅРµРЅРѕ РјРµСЃСЏС†РµРІ", formatNumber(series.length), "РЎРєРѕР»СЊРєРѕ РјРµСЃСЏС†РµРІ РІ monthly series СѓР¶Рµ СЃРѕРґРµСЂР¶Р°С‚ РґР°РЅРЅС‹Рµ. Р§РµРј Р±РѕР»СЊС€Рµ, С‚РµРј РЅР°РґС‘Р¶РЅРµРµ СЃРµР·РѕРЅРЅС‹Рµ РІС‹РІРѕРґС‹."],
    ["Р“Р»СѓР±РёРЅР° РёСЃС‚РѕСЂРёРё", `${formatNumber(historyWindow.history_years || 0)} Рі.`, "РќР° РєР°РєСѓСЋ РіР»СѓР±РёРЅСѓ СѓР¶Рµ Р·Р°РїСЂР°С€РёРІР°РµС‚СЃСЏ long-range РёСЃС‚РѕСЂРёСЏ РІ CubeJS."],
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
    ["РћРєРѕРЅ СЃ СЂРµРєРѕРјРµРЅРґР°С†РёРµР№", formatNumber(kpis.priced_windows_count), "РЎРєРѕР»СЊРєРѕ СЃРѕС‡РµС‚Р°РЅРёР№ РіСЂСѓРїРїР° + С†РµРЅРѕРІРѕР№ РєРѕСЂРёРґРѕСЂ СѓР¶Рµ РїРѕР»СѓС‡РёР»Рё С†РµРЅРѕРІСѓСЋ СЂРµРєРѕРјРµРЅРґР°С†РёСЋ."],
    ["РђРіСЂРµСЃСЃРёРІРЅС‹Р№ РІС…РѕРґ", formatNumber(kpis.aggressive_price_windows_count), "РћРєРЅР°, РіРґРµ РјРѕР¶РЅРѕ РґРµСЂР¶Р°С‚СЊСЃСЏ С‡СѓС‚СЊ РЅРёР¶Рµ СЂС‹РЅРєР° Рё РІСЃС‘ РµС‰С‘ СѓРґРµСЂР¶РёРІР°С‚СЊ С†РµР»РµРІСѓСЋ РјР°СЂР¶Сѓ."],
    ["Р¦РµРЅР° РїРѕ СЂС‹РЅРєСѓ", formatNumber(kpis.market_price_windows_count), "РћРєРЅР°, РіРґРµ СЃСЂРµРґРЅСЏСЏ С†РµРЅР° СЂС‹РЅРєР° СѓР¶Рµ СЃРѕРІРјРµСЃС‚РёРјР° СЃ РІР°С€РµР№ СЌРєРѕРЅРѕРјРёРєРѕР№."],
    ["РћСЃС‚РѕСЂРѕР¶РЅС‹Р№ С‚РµСЃС‚", formatNumber(kpis.test_price_windows_count), "РћРєРЅР°, РіРґРµ РІС…РѕРґ РІРѕР·РјРѕР¶РµРЅ, РЅРѕ С†РµРЅР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р°РєРєСѓСЂР°С‚РЅРµРµ СЃСЂРµРґРЅРµР№ РїРѕ СЂС‹РЅРєСѓ."],
    ["РќРµ РґРµРјРїРёРЅРіРѕРІР°С‚СЊ", formatNumber(kpis.do_not_discount_windows_count), "РћРєРЅР°, РіРґРµ РґР»СЏ С†РµР»РµРІРѕР№ РјР°СЂР¶Рё РЅСѓР¶РЅР° С†РµРЅР° РІС‹С€Рµ С‚РµРєСѓС‰РµРіРѕ СЂС‹РЅРєР°."],
    ["РЎСЂРµРґРЅРёР№ margin fit", kpis.avg_margin_fit_pct == null ? "РЅ/Рґ" : `${kpis.avg_margin_fit_pct}%`, "РЎСЂРµРґРЅСЏСЏ РѕС†РµРЅРєР° СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЂС‹РЅРѕС‡РЅРѕР№ С†РµРЅС‹ СЃ РІР°С€РµР№ СЌРєРѕРЅРѕРјРёРєРѕР№ РїРѕ РѕРєРЅР°Рј, РіРґРµ СѓР¶Рµ С…РІР°С‚Р°РµС‚ РґР°РЅРЅС‹С…."],
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
    ["Р’РѕР·РІСЂР°С‚РѕРІ РІ РѕРєРЅРµ", formatNumber(kpis.total_returns_count || 0), "РЎСѓРјРјР° РІРѕР·РІСЂР°С‚РѕРІ РїРѕ РѕСЃРЅРѕРІРЅРѕР№ РјРµСЂРµ SalesReturn РІ РІС‹Р±СЂР°РЅРЅРѕРј РѕРєРЅРµ."],
    ["РџСЂРёС‡РёРЅ РІРѕР·РІСЂР°С‚Р°", formatNumber(kpis.unique_return_reasons_count || 0), "РЎРєРѕР»СЊРєРѕ СЂР°Р·РЅС‹С… РїСЂРёС‡РёРЅ РІРѕР·РІСЂР°С‚Р° СѓР¶Рµ РІРёРґРЅРѕ РІ С‚РµРєСѓС‰РµРј РѕРєРЅРµ."],
    ["РЎС‚СЂРѕРє Р±РµР· РїСЂРёС‡РёРЅС‹", formatNumber(kpis.rows_without_reason_count || 0), "РЎС‚СЂРѕРєРё, РіРґРµ РїСЂРёС‡РёРЅР° РІРѕР·РІСЂР°С‚Р° РЅРµ РїСЂРёС€Р»Р° РёР»Рё РЅРµ Р±С‹Р»Р° СЂР°СЃРїРѕР·РЅР°РЅР°."],
    ["Р‘РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё", formatNumber(kpis.rows_without_identity_count || 0), "РЎС‚СЂРѕРєРё, РіРґРµ РІРѕР·РІСЂР°С‚ РЅРµР»СЊР·СЏ СѓРІРµСЂРµРЅРЅРѕ РїСЂРёРІСЏР·Р°С‚СЊ Рє SKU РёР»Рё С‚РѕРІР°СЂСѓ."],
    ["Р”РѕР»СЏ РіР»Р°РІРЅРѕР№ РїСЂРёС‡РёРЅС‹", formatPercent(kpis.top_reason_share_pct || 0), "РљР°РєР°СЏ РґРѕР»СЏ РІСЃРµС… РІРѕР·РІСЂР°С‚РѕРІ РїСЂРёС…РѕРґРёС‚СЃСЏ РЅР° СЃР°РјСѓСЋ С‡Р°СЃС‚СѓСЋ РїСЂРёС‡РёРЅСѓ. Р§РµРј РІС‹С€Рµ Р·РЅР°С‡РµРЅРёРµ, С‚РµРј РїСЂРѕС‰Рµ РЅР°Р№С‚Рё РїРµСЂРІС‹Р№ СѓР·РєРёР№ СЃС†РµРЅР°СЂРёР№ РґР»СЏ РёСЃРїСЂР°РІР»РµРЅРёСЏ."],
    ["РЎСЂРµРґРЅРµРµ РЅР° СЃС‚СЂРѕРєСѓ", formatNumber(kpis.avg_returns_per_row || 0), "РЎСЂРµРґРЅРµРµ С‡РёСЃР»Рѕ РІРѕР·РІСЂР°С‚РѕРІ РЅР° РѕРґРЅСѓ СЃС‚СЂРѕРєСѓ РѕС‚С‡С‘С‚Р°. Р­С‚Рѕ РѕСЂРёРµРЅС‚РёСЂ РЅР° РїР»РѕС‚РЅРѕСЃС‚СЊ РїСЂРѕР±Р»РµРјС‹, Р° РЅРµ С†РµР»РµРІРѕР№ KPI."],
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
    ["РЎС‚СЂРѕРє РЅР°РєР»Р°РґРЅРѕР№", formatNumber(kpis.waybill_rows_count || 0), "РЎРєРѕР»СЊРєРѕ batch-СЃС‚СЂРѕРє СѓРґР°Р»РѕСЃСЊ РЅРѕСЂРјР°Р»РёР·РѕРІР°С‚СЊ РёР· РЅР°РєР»Р°РґРЅРѕР№ РёР»Рё СЃРёРЅС‚РµС‚РёС‡РµСЃРєРѕРіРѕ С„Р°Р№Р»Р°."],
    ["Identity СЃ cost-РёСЃС‚РѕСЂРёРµР№", formatNumber(kpis.historical_cogs_items_count || 0), "РЎРєРѕР»СЊРєРѕ С‚РѕРІР°СЂРѕРІ СѓР¶Рµ РїРѕР»СѓС‡РёР»Рё РёСЃС‚РѕСЂРёС‡РµСЃРєРёР№ СЃР»РѕР№ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё РїРѕ barcode / sku / product_id."],
    ["РЎСѓРјРјР°СЂРЅС‹Р№ batch-cost", formatMoney(kpis.total_amount || 0), "РЎСѓРјРјР° СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё РїРѕ РІСЃРµРј РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Рј СЃС‚СЂРѕРєР°Рј С‚РµРєСѓС‰РµР№ РЅР°РєР»Р°РґРЅРѕР№."],
    ["Р’СЃРµРіРѕ РµРґРёРЅРёС† РІ РїРѕСЃС‚Р°РІРєРµ", formatNumber(kpis.total_quantity_supplied || 0), "РЎРєРѕР»СЊРєРѕ РµРґРёРЅРёС† С‚РѕРІР°СЂР° РїСЂРёС€Р»Рѕ РІ С‚РµРєСѓС‰РµРј batch-layer."],
    ["Р‘РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё", formatNumber(kpis.rows_without_identity_count || 0), "РЎС‚СЂРѕРєРё, РіРґРµ РЅРµ С…РІР°С‚РёР»Рѕ barcode / sku / product_id РґР»СЏ РЅРѕСЂРјР°Р»СЊРЅРѕР№ cost-СЃРІСЏР·РєРё."],
    ["РЎСЂРµРґРЅСЏСЏ unit cost", formatMoney(kpis.avg_amount_per_row || 0), "РЎСЂРµРґРЅСЏСЏ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚СЊ РѕРґРЅРѕР№ РµРґРёРЅРёС†С‹ РїРѕ СЃС‚СЂРѕРєР°Рј СЃ СЂР°СЃРїРѕР·РЅР°РЅРЅС‹Рј cost-РїРѕР»РµРј."],
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
    ["РЎС‚СЂРѕРє РІ РѕС‚С‡С‘С‚Рµ", formatNumber(kpis.storage_rows_count ?? kpis.total_skus), "РЎРєРѕР»СЊРєРѕ СЃС‚СЂРѕРє СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ РёР· Р°РєС‚СѓР°Р»СЊРЅРѕРіРѕ XLSX РѕС‚С‡С‘С‚Р° РїРѕ РїР»Р°С‚РЅРѕРјСѓ С…СЂР°РЅРµРЅРёСЋ Рё СѓСЃР»СѓРіР°Рј."],
    ["РЎС‚СЂРѕРє СЃ СЃСѓРјРјРѕР№", formatNumber(kpis.rows_with_amount_count ?? kpis.sold_skus), "РЎРєРѕР»СЊРєРѕ СЃС‚СЂРѕРє СЃРѕРґРµСЂР¶Р°С‚ СЏРІРЅРѕРµ С‡РёСЃР»РѕРІРѕРµ РЅР°С‡РёСЃР»РµРЅРёРµ Рё СѓС‡Р°СЃС‚РІСѓСЋС‚ РІ СЃСѓРјРјР°СЂРЅРѕРј РїР»Р°С‚РЅРѕРј СЃР»РѕРµ."],
    ["РЎСѓРјРјР° РЅР°С‡РёСЃР»РµРЅРёР№", formatMoney(kpis.total_amount ?? kpis.revenue_total), "РЎСѓРјРјР° РїРѕ РѕСЃРЅРѕРІРЅРѕР№ РґРµРЅРµР¶РЅРѕР№ РєРѕР»РѕРЅРєРµ, РєРѕС‚РѕСЂСѓСЋ СЃРёСЃС‚РµРјР° РІС‹Р±СЂР°Р»Р° РєР°Рє РіР»Р°РІРЅС‹Р№ СЃР»РѕР№ РЅР°С‡РёСЃР»РµРЅРёР№."],
    ["РЁС‚СЂР°С„С‹ Рё СѓРґРµСЂР¶Р°РЅРёСЏ", formatMoney(kpis.penalty_total || 0), "РЎСѓРјРјР° РєРѕР»РѕРЅРѕРє, РіРґРµ Р·Р°РіРѕР»РѕРІРѕРє РїРѕС…РѕР¶ РЅР° СѓРґРµСЂР¶Р°РЅРёРµ, С€С‚СЂР°С„ РёР»Рё РїРµРЅСЋ. Р­С‚Рѕ РѕС‚РґРµР»СЊРЅС‹Р№ СЃР»РѕР№ РїСЂРѕРІРµСЂРєРё, Р° РЅРµ РѕР±С‹С‡РЅРѕРµ С…СЂР°РЅРµРЅРёРµ."],
    ["Р‘РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё", formatNumber(kpis.rows_without_identity_count ?? kpis.stockout_risk_count), "РЎС‚СЂРѕРєРё, РіРґРµ РЅРµ СѓРґР°Р»РѕСЃСЊ РІС‹С‚Р°С‰РёС‚СЊ РІРЅСЏС‚РЅС‹Р№ SKU, Р°СЂС‚РёРєСѓР» РёР»Рё РїРѕРЅСЏС‚РЅРѕРµ РЅР°Р·РІР°РЅРёРµ. РўР°РєРёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ С…СѓР¶Рµ РѕР±СЉСЏСЃРЅСЏСЋС‚СЃСЏ РјРµРЅРµРґР¶РµСЂСѓ."],
    ["РЎСЂРµРґРЅСЏСЏ СЃСѓРјРјР° РЅР° СЃС‚СЂРѕРєСѓ", formatMoney(kpis.avg_amount_per_row || 0), "РЎСЂРµРґРЅРµРµ РЅР°С‡РёСЃР»РµРЅРёРµ РЅР° РѕРґРЅСѓ СЃС‚СЂРѕРєСѓ СЃ СЃСѓРјРјРѕР№. Р­С‚Рѕ Р±С‹СЃС‚СЂС‹Р№ РѕСЂРёРµРЅС‚РёСЂ РЅР° РїР»РѕС‚РЅРѕСЃС‚СЊ Р·Р°С‚СЂР°С‚, Р° РЅРµ С†РµР»РµРІРѕР№ KPI СЃР°Рј РїРѕ СЃРµР±Рµ."],
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
    ["РљР°СЂС‚РѕС‡РµРє РІ РїСЂРёРѕСЂРёС‚РµС‚Рµ", formatNumber(kpis.priority_cards_count), "РЎРєРѕР»СЊРєРѕ РєР°СЂС‚РѕС‡РµРє РїРѕРїР°Р»Рѕ РІ РµРґРёРЅС‹Р№ manager-facing РјР°СЂРєРµС‚РёРЅРіРѕРІС‹Р№ Р°СѓРґРёС‚."],
    ["Р¦РµРЅРѕРІС‹С… Р»РѕРІСѓС€РµРє", formatNumber(kpis.price_trap_cards_count), "РљР°СЂС‚РѕС‡РєРё, РіРґРµ С†РµРЅР° РІРёСЃРёС‚ С‡СѓС‚СЊ РІС‹С€Рµ РїСЃРёС…РѕР»РѕРіРёС‡РµСЃРєРѕРіРѕ РїРѕСЂРѕРіР°."],
    ["РќР°Р·РІР°РЅРёРµ С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹", formatNumber(kpis.seo_needs_work_count), "РљР°СЂС‚РѕС‡РєРё СЃРѕ СЃР»Р°Р±С‹Рј SEO-СЃРёРіРЅР°Р»РѕРј РїРѕ РЅР°Р·РІР°РЅРёСЋ."],
    ["РљСЂРёС‚РёС‡РЅС‹С… РЅР°Р·РІР°РЅРёР№", formatNumber(kpis.seo_priority_fix_count), "РќР°РёР±РѕР»РµРµ РїСЂРѕР±Р»РµРјРЅС‹Рµ РЅР°Р·РІР°РЅРёСЏ, РєРѕС‚РѕСЂС‹Рµ СЃС‚РѕРёС‚ РїСЂР°РІРёС‚СЊ РїРµСЂРІС‹РјРё."],
    ["РљР°СЂС‚РѕС‡РµРє СЃ СЂС‹РЅРѕС‡РЅС‹Рј РєРѕРЅС‚РµРєСЃС‚РѕРј", formatNumber(kpis.market_supported_cards_count), "РљР°СЂС‚РѕС‡РєРё, РїРѕРїР°РІС€РёРµ РІ РіСЂСѓРїРїС‹ Рё С†РµРЅРѕРІС‹Рµ РєРѕСЂРёРґРѕСЂС‹, РіРґРµ С†РµРЅРѕРІРѕР№ СЃР»РѕР№ СѓР¶Рµ РґР°С‘С‚ СЂС‹РЅРѕС‡РЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚."],
    ["Р”РІРѕР№РЅС‹С… РїСЂРѕР±Р»РµРј", formatNumber(kpis.double_fix_count), "РљР°СЂС‚РѕС‡РєРё, РіРґРµ РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ РІРёРґРЅС‹ Рё СЃР»Р°Р±С‹Р№ title, Рё С†РµРЅРѕРІРѕР№ trap."],
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
        title: "Р—Р°Р№С‚Рё РІ РЅРёС€Сѓ",
        value: formatNumber((actions.enter_now_segments || []).length),
        subtitle: "РћРєРѕРЅ, РіРґРµ СЃРїСЂРѕСЃ Рё СЌРєРѕРЅРѕРјРёРєР° СѓР¶Рµ РІС‹РіР»СЏРґСЏС‚ СЂР°Р±РѕС‡РёРјРё",
        tone: (actions.enter_now_segments || []).length > 0 ? "good" : "warn",
      },
      {
        title: "РўРµСЃС‚РёСЂРѕРІР°С‚СЊ",
        value: formatNumber((actions.test_entry_segments || []).length),
        subtitle: "РћРєРѕРЅ, РіРґРµ СѓР¶Рµ РјРѕР¶РЅРѕ РґРµР»Р°С‚СЊ С‚РѕС‡РµС‡РЅС‹Рµ РіРёРїРѕС‚РµР·С‹",
        tone: (actions.test_entry_segments || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Р”РѕР±РёСЂР°С‚СЊ cost-РґР°РЅРЅС‹Рµ",
        value: formatNumber((actions.blind_spots || []).length),
        subtitle: "РЎР»РµРїС‹С… Р·РѕРЅ, РіРґРµ СЂРµС€РµРЅРёРµ РЅРµР»СЊР·СЏ РїСЂРёРЅРёРјР°С‚СЊ РІСЃР»РµРїСѓСЋ",
        tone: (actions.blind_spots || []).length > 0 ? "warn" : "good",
      },
      {
        title: "РќРµ Р»РµР·С‚СЊ / РјРµРЅСЏС‚СЊ Р·Р°РєСѓРїРєСѓ",
        value: formatNumber((actions.sourcing_or_avoid_segments || []).length),
        subtitle: "РџРµСЂРµРіСЂРµС‚С‹С… РёР»Рё СЌРєРѕРЅРѕРјРёС‡РµСЃРєРё СЃР»Р°Р±С‹С… РѕРєРѕРЅ",
        tone: (actions.sourcing_or_avoid_segments || []).length > 0 ? "bad" : "good",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ Р С‹РЅРѕС‡РЅС‹Рµ Р РµС€РµРЅРёСЏ";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° РІС‹Р±РµСЂРё, РєСѓРґР° РІС…РѕРґРёС‚СЊ, С‡С‚Рѕ С‚РµСЃС‚РёСЂРѕРІР°С‚СЊ Рё РіРґРµ СЌРєРѕРЅРѕРјРёРєР° СѓР¶Рµ РїР»РѕС…Р°СЏ.";
  } else if (item.report_kind === "dynamic_pricing") {
    const actions = payload.actions || {};
    cards.push(
      {
        title: "Р’С…РѕРґРёС‚СЊ Р°РіСЂРµСЃСЃРёРІРЅРѕ",
        value: formatNumber((actions.aggressive_price || []).length),
        subtitle: "РћРєРЅР°, РіРґРµ РјРѕР¶РЅРѕ РёРґС‚Рё С‡СѓС‚СЊ РЅРёР¶Рµ СЂС‹РЅРєР° Рё РЅРµ Р»РѕРјР°С‚СЊ РјР°СЂР¶Сѓ",
        tone: (actions.aggressive_price || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "Р¦РµРЅР° РїРѕ СЂС‹РЅРєСѓ",
        value: formatNumber((actions.price_at_market || []).length),
        subtitle: "РћРєРЅР°, РіРґРµ СЃСЂРµРґРЅСЏСЏ СЂС‹РЅРѕС‡РЅР°СЏ С†РµРЅР° СѓР¶Рµ Р±РµР·РѕРїР°СЃРЅР°",
        tone: (actions.price_at_market || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "РўРµСЃС‚РёСЂРѕРІР°С‚СЊ РѕСЃС‚РѕСЂРѕР¶РЅРѕ",
        value: formatNumber((actions.test_carefully || []).length),
        subtitle: "РћРєРЅР°, РіРґРµ С†РµРЅР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ РІС‹С€Рµ СЂС‹РЅРєР° РёР»Рё РѕС„С„РµСЂ СЃРёР»СЊРЅРµРµ",
        tone: (actions.test_carefully || []).length > 0 ? "warn" : "neutral",
      },
      {
        title: "РќРµ РґРµРјРїРёРЅРіРѕРІР°С‚СЊ",
        value: formatNumber((actions.protect_margin || []).length),
        subtitle: "РћРєРЅР°, РіРґРµ РґРµРјРїРёРЅРі Р»РѕРјР°РµС‚ С†РµР»РµРІСѓСЋ РјР°СЂР¶Сѓ",
        tone: (actions.protect_margin || []).length > 0 ? "bad" : "good",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ Р РµС€РµРЅРёСЏ РџРѕ Р¦РµРЅР°Рј";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° СЂР°Р·РґРµР»Рё РѕРєРЅР° РЅР° Р°РіСЂРµСЃСЃРёРІРЅС‹Р№ РІС…РѕРґ, С†РµРЅСѓ РїРѕ СЂС‹РЅРєСѓ, РѕСЃС‚РѕСЂРѕР¶РЅС‹Р№ С‚РµСЃС‚ Рё no-discount.";
  } else if (item.report_kind === "marketing_card_audit") {
    const actions = payload.actions || {};
    cards.push(
      {
        title: "РСЃРїСЂР°РІРёС‚СЊ СЃРµР№С‡Р°СЃ",
        value: formatNumber((actions.fix_now || []).length),
        subtitle: "РљР°СЂС‚РѕС‡РєРё СЃ РґРІРѕР№РЅРѕР№ РїСЂРѕР±Р»РµРјРѕР№: С†РµРЅР° Рё title",
        tone: (actions.fix_now || []).length > 0 ? "warn" : "good",
      },
      {
        title: "РўРµСЃС‚ С†РµРЅС‹",
        value: formatNumber((actions.price_tests || []).length),
        subtitle: "РљР°СЂС‚РѕС‡РєРё СЂСЏРґРѕРј СЃ СЃРёР»СЊРЅС‹РјРё С†РµРЅРѕРІС‹РјРё РїРѕСЂРѕРіР°РјРё",
        tone: (actions.price_tests || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "РџРµСЂРµРїРёСЃР°С‚СЊ title",
        value: formatNumber((actions.title_fixes || []).length),
        subtitle: "РљР°СЂС‚РѕС‡РєРё СЃРѕ СЃР»Р°Р±С‹Рј РїРѕРёСЃРєРѕРІС‹Рј СЃРёРіРЅР°Р»РѕРј",
        tone: (actions.title_fixes || []).length > 0 ? "warn" : "neutral",
      },
      {
        title: "Р С‹РЅРѕРє РїРѕРґРґРµСЂР¶РёРІР°РµС‚",
        value: formatNumber((actions.market_supported || []).length),
        subtitle: "РљР°СЂС‚РѕС‡РєРё РІ РѕРєРЅР°С… СЃ СЂР°Р±РѕС‡РёРј pricing context",
        tone: (actions.market_supported || []).length > 0 ? "good" : "neutral",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ Р РµС€РµРЅРёСЏ РџРѕ РљР°СЂС‚РѕС‡РєР°Рј";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° РІС‹Р±РµСЂРё, РіРґРµ С‡РёРЅРёС‚СЊ С†РµРЅСѓ, РіРґРµ РїРµСЂРµРїРёСЃС‹РІР°С‚СЊ title Рё РіРґРµ СЂС‹РЅРѕРє СѓР¶Рµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚ С‚РµСЃС‚.";
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
        subtitle: "Р“Р»Р°РІРЅР°СЏ Р±Р°Р·Р° РІС‹СЂСѓС‡РєРё Р·Р° РїРѕСЃР»РµРґРЅРёРµ 365 РґРЅРµР№",
        tone: "good",
      },
      {
        title: "YoY РіРѕС‚РѕРІРЅРѕСЃС‚СЊ",
        value: previous.revenue_total ? "РµСЃС‚СЊ Р±Р°Р·Р°" : "РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ",
        subtitle: "РњРѕР¶РЅРѕ Р»Рё СѓР¶Рµ С‡РµСЃС‚РЅРѕ С‡РёС‚Р°С‚СЊ РіРѕРґ-Рє-РіРѕРґСѓ",
        tone: previous.revenue_total ? "good" : "warn",
      },
      {
        title: "YTD Р±Р°Р·Р°",
        value: formatMoney(ytd.revenue_total || 0),
        subtitle: previousYtd.revenue_total ? "Р•СЃС‚СЊ Рё РїСЂРѕС€Р»С‹Р№ YTD" : "РџСЂРµРґС‹РґСѓС‰РёР№ YTD РµС‰С‘ РїСѓСЃС‚РѕР№",
        tone: previousYtd.revenue_total ? "good" : "warn",
      },
      {
        title: "РњРµСЃСЏС†РµРІ РёСЃС‚РѕСЂРёРё",
        value: formatNumber(seriesMonths),
        subtitle: "Р”Р»СЏ seasonality Рё YoY Р¶РµР»Р°С‚РµР»СЊРЅРѕ 12-18 РЅРµРЅСѓР»РµРІС‹С… РјРµСЃСЏС†РµРІ",
        tone: seriesMonths >= 12 ? "good" : "warn",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ РЎРёРіРЅР°Р»С‹ РСЃС‚РѕСЂРёРё";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° СЃРјРѕС‚СЂРё Р·СЂРµР»РѕСЃС‚СЊ РІСЂРµРјРµРЅРЅРѕРіРѕ СЂСЏРґР°, Р° СѓР¶Рµ РїРѕС‚РѕРј РґРµР»Р°Р№ РІС‹РІРѕРґС‹ Рѕ РґРёРЅР°РјРёРєРµ.";
  } else if (item.report_kind === "paid_storage_report") {
    const actions = payload.actions || {};
    const kpis = payload.kpis || {};
    cards.push(
      {
        title: "РљСЂСѓРїРЅС‹Рµ РЅР°С‡РёСЃР»РµРЅРёСЏ",
        value: formatNumber((actions.reorder_now || []).length),
        subtitle: "РЎС‚СЂРѕРєРё, РєРѕС‚РѕСЂС‹Рµ РЅСѓР¶РЅРѕ СЂР°Р·Р±РёСЂР°С‚СЊ РїРµСЂРІС‹РјРё",
        tone: (actions.reorder_now || []).length > 0 ? "warn" : "neutral",
      },
      {
        title: "Р‘РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё",
        value: formatNumber(kpis.rows_without_identity_count || 0),
        subtitle: "РЎС‚СЂРѕРєРё Р±РµР· РїРѕРЅСЏС‚РЅРѕРіРѕ SKU РёР»Рё РЅР°Р·РІР°РЅРёСЏ",
        tone: (kpis.rows_without_identity_count || 0) > 0 ? "warn" : "good",
      },
      {
        title: "РЎСѓРјРјР° РЅР°С‡РёСЃР»РµРЅРёР№",
        value: formatMoney(kpis.total_amount || 0),
        subtitle: "Р“Р»Р°РІРЅС‹Р№ РґРµРЅРµР¶РЅС‹Р№ СЃР»РѕР№ С‚РµРєСѓС‰РµРіРѕ С„Р°Р№Р»Р°",
        tone: "good",
      },
      {
        title: "РЈРґРµСЂР¶Р°РЅРёСЏ",
        value: formatMoney(kpis.penalty_total || 0),
        subtitle: "РџРѕС…РѕР¶РёРµ РЅР° С€С‚СЂР°С„С‹ Рё СѓРґРµСЂР¶Р°РЅРёСЏ РєРѕР»РѕРЅРєРё",
        tone: (kpis.penalty_total || 0) > 0 ? "warn" : "neutral",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ Р РµС€РµРЅРёСЏ РџРѕ РџР»Р°С‚РЅРѕРјСѓ РЎР»РѕСЋ";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° СЂР°Р·Р±РµСЂРё РєСЂСѓРїРЅРµР№С€РёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ Рё СЃС‚СЂРѕРєРё Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё, РїРѕС‚РѕРј СѓС…РѕРґРё РІ СЂР°СЃС€РёС„СЂРѕРІРєСѓ РєРѕР»РѕРЅРѕРє.";
  } else if (item.report_kind === "sales_return_report") {
    const actions = payload.actions || {};
    const kpis = payload.kpis || {};
    cards.push(
      {
        title: "Р’РѕР·РІСЂР°С‚РѕРІ РІ РѕРєРЅРµ",
        value: formatNumber(kpis.total_returns_count || 0),
        subtitle: "РЎСѓРјРјР° РІРѕР·РІСЂР°С‚РѕРІ РїРѕ РѕСЃРЅРѕРІРЅРѕР№ РјРµСЂРµ CubeJS",
        tone: (kpis.total_returns_count || 0) > 0 ? "warn" : "neutral",
      },
      {
        title: "РџСЂРёС‡РёРЅ РІРѕР·РІСЂР°С‚Р°",
        value: formatNumber(kpis.unique_return_reasons_count || 0),
        subtitle: "РЎРєРѕР»СЊРєРѕ СЂР°Р·РЅС‹С… РїСЂРёС‡РёРЅ РІРёРґРЅРѕ РІ С‚РµРєСѓС‰РµРј РѕРєРЅРµ",
        tone: (kpis.unique_return_reasons_count || 0) > 0 ? "good" : "neutral",
      },
      {
        title: "Р“Р»Р°РІРЅР°СЏ РїСЂРёС‡РёРЅР°",
        value: formatPercent(kpis.top_reason_share_pct || 0),
        subtitle: "Р”РѕР»СЏ РІРѕР·РІСЂР°С‚РѕРІ, РєРѕС‚РѕСЂСѓСЋ РґР°С‘С‚ СЃР°РјР°СЏ С‡Р°СЃС‚Р°СЏ РїСЂРёС‡РёРЅР°",
        tone: (kpis.top_reason_share_pct || 0) >= 40 ? "warn" : "good",
      },
      {
        title: "Р‘РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё",
        value: formatNumber(kpis.rows_without_identity_count || 0),
        subtitle: "РЎС‚СЂРѕРєРё, РіРґРµ РІРѕР·РІСЂР°С‚ РЅРµ СѓРґР°Р»РѕСЃСЊ СѓРІРµСЂРµРЅРЅРѕ РїСЂРёРІСЏР·Р°С‚СЊ Рє С‚РѕРІР°СЂСѓ",
        tone: (kpis.rows_without_identity_count || 0) > 0 ? "warn" : "good",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ Р РµС€РµРЅРёСЏ РџРѕ Р’РѕР·РІСЂР°С‚Р°Рј";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° СЂР°Р·Р±РµСЂРё РґРѕРјРёРЅРёСЂСѓСЋС‰СѓСЋ РїСЂРёС‡РёРЅСѓ Рё СЃР°РјС‹Рµ С‚СЏР¶С‘Р»С‹Рµ SKU, РїРѕС‚РѕРј СѓС…РѕРґРё РІ С…РІРѕСЃС‚ Рё РїСЂРѕР±РµР»С‹ РґР°РЅРЅС‹С….";
  } else {
    const actions = payload.actions || {};
    const kpis = payload.kpis || {};
    cards.push(
      {
        title: "Р—Р°РєР°Р·Р°С‚СЊ",
        value: formatNumber((actions.reorder_now || []).length),
        subtitle: "SKU, РєРѕС‚РѕСЂС‹Рµ СѓР¶Рµ РїСЂРѕС…РѕРґСЏС‚ Р¶С‘СЃС‚РєРёР№ РїРѕСЂРѕРі РЅР° РґРѕР·Р°РєСѓРїРєСѓ",
        tone: (actions.reorder_now || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "РЎРЅРёР·РёС‚СЊ С†РµРЅСѓ / С‡РёСЃС‚РёС‚СЊ",
        value: formatNumber((actions.markdown_candidates || []).length),
        subtitle: "РљР°РЅРґРёРґР°С‚С‹ РЅР° СѓС†РµРЅРєСѓ Рё СЂР°СЃС‡РёСЃС‚РєСѓ С…РІРѕСЃС‚Р°",
        tone: (actions.markdown_candidates || []).length > 0 ? "warn" : "good",
      },
      {
        title: "Р‘РµСЂРµС‡СЊ",
        value: formatNumber((actions.protect_winners || []).length || (actions.watchlist_signals || []).length),
        subtitle: (actions.protect_winners || []).length ? "РџРѕР±РµРґРёС‚РµР»Рё РїРѕ РїСЂРёР±С‹Р»Рё" : "Р–РёРІС‹Рµ СЃРёРіРЅР°Р»С‹ РґР»СЏ СЂСѓС‡РЅРѕРіРѕ РєРѕРЅС‚СЂРѕР»СЏ",
        tone: (actions.protect_winners || []).length > 0 ? "good" : "neutral",
      },
      {
        title: "РџРѕС‚РµСЂРё РёР·-Р·Р° OOS",
        value: formatNumber(kpis.estimated_lost_units_oos_total || 0),
        subtitle: "Proxy-РѕС†РµРЅРєР° РїРѕС‚РµСЂСЏРЅРЅС‹С… РµРґРёРЅРёС† РёР·-Р·Р° РѕС‚СЃСѓС‚СЃС‚РІРёСЏ РІ РЅР°Р»РёС‡РёРё",
        tone: (kpis.estimated_lost_units_oos_total || 0) > 0 ? "warn" : "good",
      },
    );
    title.textContent = "Р“Р»Р°РІРЅС‹Рµ РћРїРµСЂР°С†РёРѕРЅРЅС‹Рµ Р”РµР№СЃС‚РІРёСЏ";
    subtitle.textContent = "РЎРЅР°С‡Р°Р»Р° СЂРµС€Рё, С‡С‚Рѕ Р·Р°РєР°Р·С‹РІР°С‚СЊ, С‡С‚Рѕ С‡РёСЃС‚РёС‚СЊ Рё РіРґРµ РјР°РіР°Р·РёРЅ СѓР¶Рµ С‚РµСЂСЏРµС‚ СЃРїСЂРѕСЃ РёР·-Р·Р° РѕС‚СЃСѓС‚СЃС‚РІРёСЏ С‚РѕРІР°СЂР°.";
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
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Р—Р°РєР°Р·Р°С‚СЊ СЃРµР№С‡Р°СЃ", subtitle: "SKU СЃ СЂРёСЃРєРѕРј РЅРµС…РІР°С‚РєРё", rows: (actions.reorder_now || []).slice(0, 8), formatter: (row) => `РѕСЃС‚Р°С‚РѕРє ${row.total_stock}, РїРѕРєСЂС‹С‚РёРµ ${row.stock_cover_days ?? "в€ћ"} РґРЅ., СЃСЂРµРґРЅРµСЃСѓС‚РѕС‡РЅРѕ ${row.avg_daily_sales_official}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "РљР°РЅРґРёРґР°С‚С‹ РЅР° СѓС†РµРЅРєСѓ", subtitle: "РўРѕРІР°СЂС‹ Р±РµР· РґРІРёР¶РµРЅРёСЏ", rows: (actions.markdown_candidates || []).slice(0, 8), formatter: (row) => `РѕСЃС‚Р°С‚РѕРє ${row.total_stock}, СЃС‚РѕРёРјРѕСЃС‚СЊ ${formatMoney(row.stock_value_sale)}`, getDisplayTitle, createEntityActionButtons });
  const protectRows = (actions.protect_winners || []).length ? (actions.protect_winners || []) : (actions.watchlist_signals || []);
  const protectTitle = (actions.protect_winners || []).length ? "Р‘РµСЂРµС‡СЊ РїРѕР±РµРґРёС‚РµР»РµР№" : "РЎРјРѕС‚СЂРµС‚СЊ СЃРёРіРЅР°Р»С‹";
  const protectSubtitle = (actions.protect_winners || []).length ? "Р›РёРґРµСЂС‹ РїРѕ С‚РµРєСѓС‰РµР№ РїСЂРёР±С‹Р»Рё" : "РџРѕРєР° РЅРµ РїРѕР±РµРґРёС‚РµР»Рё, РЅРѕ СѓР¶Рµ Р¶РёРІС‹Рµ РїРѕР·РёС†РёРё";
  renderActionCard({ root: document.getElementById("action-protect"), title: protectTitle, subtitle: protectSubtitle, rows: protectRows.slice(0, 8), formatter: (row) => `РїСЂРёР±С‹Р»СЊ ${formatMoney(row.gross_profit)}, РїСЂРѕРґР°РЅРѕ ${row.units_sold}`, getDisplayTitle, createEntityActionButtons });
}

function renderMarketActions(payload) {
  const actions = payload.actions || {};
  const enterRows = (actions.enter_now_segments || []).length ? actions.enter_now_segments : (actions.entry_watchlist || []);
  const testRows = (actions.test_entry_segments || []).length ? actions.test_entry_segments : [];
  const noGoRows = (actions.sourcing_or_avoid_segments || []).length
    ? actions.sourcing_or_avoid_segments
    : ((actions.weak_margin_segments || []).length ? actions.weak_margin_segments : (actions.too_hot_segments || []));
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Р’С…РѕРґРёС‚СЊ РїРµСЂРІС‹Рј", subtitle: "РћРєРЅР°, РіРґРµ СЃРїСЂРѕСЃ, СЃС‚СЂСѓРєС‚СѓСЂР° СЂС‹РЅРєР° Рё СЌРєРѕРЅРѕРјРёРєР° СѓР¶Рµ РІС‹РіР»СЏРґСЏС‚ СЂР°Р±РѕС‡РёРјРё", rows: enterRows.slice(0, 8), formatter: (row) => `${row.group} / ${row.price_band}, score ${row.entry_window_score}, СЂРµС€РµРЅРёРµ ${row.entry_strategy_label || "РЅ/Рґ"}, margin fit ${row.market_margin_fit_pct ?? "РЅ/Рґ"}%`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "РўРµСЃС‚РёСЂРѕРІР°С‚СЊ С‚РѕС‡РµС‡РЅРѕ", subtitle: "РћРєРЅР°, РіРґРµ РІС…РѕРґ РІРѕР·РјРѕР¶РµРЅ, РЅРѕ СѓР¶Рµ РЅСѓР¶РµРЅ РєРѕРЅС‚СЂРѕР»СЊ СЌРєРѕРЅРѕРјРёРєРё РёР»Рё СЃРёР»СЊРЅС‹Р№ РѕС„С„РµСЂ", rows: testRows.slice(0, 8), formatter: (row) => `${row.group} / ${row.price_band}, СЂРµС€РµРЅРёРµ ${row.entry_strategy_label || "РЅ/Рґ"}, HHI ${row.dominance_hhi ?? "РЅ/Рґ"}, margin fit ${row.market_margin_fit_pct ?? "РЅ/Рґ"}%`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "РќРµ РІС…РѕРґРёС‚СЊ РёР»Рё РјРµРЅСЏС‚СЊ Р·Р°РєСѓРїРєСѓ", subtitle: "РћРєРЅР°, РіРґРµ СЃРµРіРјРµРЅС‚ РїРµСЂРµРіСЂРµС‚ РёР»Рё СЂС‹РЅРѕС‡РЅР°СЏ С†РµРЅР° РЅРµ Р±СЊС‘С‚СЃСЏ СЃ РІР°С€РµР№ С†РµР»РµРІРѕР№ РјР°СЂР¶РѕР№", rows: noGoRows.slice(0, 8), formatter: (row) => `${row.group} / ${row.price_band}, СЂРµС€РµРЅРёРµ ${row.entry_strategy_label || "РЅ/Рґ"}, margin fit ${row.market_margin_fit_pct ?? "РЅ/Рґ"}%, HHI ${row.dominance_hhi ?? "РЅ/Рґ"}`, getDisplayTitle, createEntityActionButtons });
}

function renderPricingActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "РђРіСЂРµСЃСЃРёРІРЅРѕ РІС…РѕРґРёС‚СЊ", subtitle: "РћРєРЅР°, РіРґРµ РјРѕР¶РЅРѕ РґРµСЂР¶Р°С‚СЊСЃСЏ С‡СѓС‚СЊ РЅРёР¶Рµ СЂС‹РЅРєР° Рё РІСЃС‘ РµС‰С‘ СЃРѕС…СЂР°РЅСЏС‚СЊ С†РµР»РµРІСѓСЋ РјР°СЂР¶Сѓ", rows: (actions.aggressive_price || []).slice(0, 8), formatter: (row) => `${row.group || "РЅ/Рґ"} / ${row.price_band || "РЅ/Рґ"}, СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}, Р±РµР·РѕРїР°СЃРЅРѕ РѕС‚ ${formatMoney(row.min_safe_price)}, СЂРµРєРѕРјРµРЅРґР°С†РёСЏ ${formatMoney(row.suggested_price)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Р¦РµРЅР° РїРѕ СЂС‹РЅРєСѓ / РѕСЃС‚РѕСЂРѕР¶РЅС‹Р№ С‚РµСЃС‚", subtitle: "РћРєРЅР°, РіРґРµ РјРѕР¶РЅРѕ РґРµСЂР¶Р°С‚СЊСЃСЏ СЂС‹РЅРєР° РёР»Рё РїСЂРѕРІРµСЂСЏС‚СЊ Р±РѕР»РµРµ РѕСЃС‚РѕСЂРѕР¶РЅС‹Р№ price point", rows: [...(actions.price_at_market || []), ...(actions.test_carefully || [])].slice(0, 8), formatter: (row) => `${row.group || "РЅ/Рґ"} / ${row.price_band || "РЅ/Рґ"}, СЏСЂР»С‹Рє ${row.pricing_label || "РЅ/Рґ"}, СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}, СЂРµРєРѕРјРµРЅРґР°С†РёСЏ ${formatMoney(row.suggested_price)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Р‘РµСЂРµС‡СЊ РјР°СЂР¶Сѓ", subtitle: "РћРєРЅР°, РіРґРµ РЅРµР»СЊР·СЏ РґРµРјРїРёРЅРіРѕРІР°С‚СЊ, РёРЅР°С‡Рµ С†РµР»РµРІР°СЏ РјР°СЂР¶Р° СЂР°Р·СЂСѓС€Р°РµС‚СЃСЏ", rows: (actions.protect_margin || []).slice(0, 8), formatter: (row) => `${row.group || "РЅ/Рґ"} / ${row.price_band || "РЅ/Рґ"}, Р±РµР·РѕРїР°СЃРЅРѕ РЅРµ РЅРёР¶Рµ ${formatMoney(row.min_safe_price)}, СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}`, getDisplayTitle, createEntityActionButtons });
}

function renderMarketingActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "РСЃРїСЂР°РІРёС‚СЊ СЃРµР№С‡Р°СЃ", subtitle: "РљР°СЂС‚РѕС‡РєРё, РіРґРµ РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ СЃР»Р°Р±С‹Р№ title Рё РЅРµСѓРґР°С‡РЅС‹Р№ С†РµРЅРѕРІРѕР№ point", rows: (actions.fix_now || []).slice(0, 8), formatter: (row) => `${row.group || "РЅ/Рґ"} / ${row.price_band || "РЅ/Рґ"}, ${row.action_reason || "РЅ/Рґ"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "РўРµСЃС‚ С†РµРЅС‹", subtitle: "РљР°СЂС‚РѕС‡РєРё СЂСЏРґРѕРј СЃ РїСЃРёС…РѕР»РѕРіРёС‡РµСЃРєРёРјРё РїРѕСЂРѕРіР°РјРё", rows: (actions.price_tests || []).slice(0, 8), formatter: (row) => `С†РµРЅР° ${formatMoney(row.sale_price)}, РїРѕСЂРѕРі ${formatMoney(row.threshold || 0)}, С‚РµСЃС‚ ${formatMoney(row.suggested_threshold_price || row.sale_price)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "РџРµСЂРµРїРёСЃР°С‚СЊ title", subtitle: "РљР°СЂС‚РѕС‡РєРё, РіРґРµ РєРѕРЅС‚РµРЅС‚ РґР°С‘С‚ СЃР»Р°Р±С‹Р№ РїРѕРёСЃРєРѕРІС‹Р№ СЃРёРіРЅР°Р»", rows: (actions.title_fixes || []).slice(0, 8), formatter: (row) => `SEO ${row.seo_status || "РЅ/Рґ"} / ${row.seo_score ?? "РЅ/Рґ"}, issues: ${(row.seo_issues || []).join(", ") || "РЅ/Рґ"}`, getDisplayTitle, createEntityActionButtons });
}

function renderMediaActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "РЎСЂРѕС‡РЅРѕ СѓСЃРёР»РёС‚СЊ РјРµРґРёР°", subtitle: "РљР°СЂС‚РѕС‡РєРё СЃ СЃР°РјС‹Рј СЏРІРЅС‹Рј РѕС‚СЃС‚Р°РІР°РЅРёРµРј РїРѕ С„РѕС‚Рѕ РёР»Рё С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°Рј РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЃРІРѕРµР№ РіСЂСѓРїРїС‹", rows: (actions.fix_now || []).slice(0, 8), formatter: (row) => `media ${row.media_status || "РЅ/Рґ"} / ${row.media_score ?? "РЅ/Рґ"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Р’РёР·СѓР°Р»СЊРЅС‹Рµ РѕС‚СЃС‚Р°РІР°РЅРёСЏ", subtitle: "Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚ СЂР°Р·РЅРёС†Сѓ СЃ С‚РёРїРёС‡РЅС‹Рј СѓСЂРѕРІРЅРµРј СЃРІРѕРµР№ РіСЂСѓРїРїС‹", rows: (actions.visual_gaps || []).slice(0, 8), formatter: (row) => `РѕС‚СЃС‚Р°РІР°РЅРёРµ РїРѕ С„РѕС‚Рѕ ${row.photo_gap_vs_group ?? 0}, РїРѕ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°Рј ${row.spec_gap_vs_group ?? 0}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "РЎРёР»СЊРЅС‹Рµ РїСЂРёРјРµСЂС‹", subtitle: "Р’РЅСѓС‚СЂРµРЅРЅРёРµ РѕСЂРёРµРЅС‚РёСЂС‹ РїРѕ РєР°СЂС‚РѕС‡РєР°Рј", rows: (actions.strong_examples || []).slice(0, 8), formatter: (row) => `С„РѕС‚Рѕ ${row.photo_count}, spec ${row.spec_count}, РІРёРґРµРѕ ${row.video_count}`, getDisplayTitle, createEntityActionButtons });
}

function renderDescriptionActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "РЎСЂРѕС‡РЅРѕ РїРµСЂРµРїРёСЃР°С‚СЊ РѕРїРёСЃР°РЅРёРµ", subtitle: "РљР°СЂС‚РѕС‡РєРё СЃ РЅР°РёР±РѕР»РµРµ СЃР»Р°Р±С‹Рј description-layer", rows: (actions.fix_now || []).slice(0, 8), formatter: (row) => `description ${row.description_status || "РЅ/Рґ"} / ${row.description_score ?? "РЅ/Рґ"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "РўРѕРЅРєРёРµ РѕРїРёСЃР°РЅРёСЏ", subtitle: "РЎР»РёС€РєРѕРј РєРѕСЂРѕС‚РєРёРµ РѕРїРёСЃР°РЅРёСЏ", rows: (actions.thin_content || []).slice(0, 8), formatter: (row) => `${row.description_chars ?? 0} СЃРёРјРІ., coverage ${row.title_term_coverage_pct ?? "РЅ/Рґ"}%`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "РЎРёР»СЊРЅС‹Рµ РїСЂРёРјРµСЂС‹", subtitle: "Р’РЅСѓС‚СЂРµРЅРЅРёРµ РѕСЂРёРµРЅС‚РёСЂС‹ РїРѕ РѕРїРёСЃР°РЅРёСЏРј", rows: (actions.strong_examples || []).slice(0, 8), formatter: (row) => `${row.description_chars ?? 0} СЃРёРјРІ., coverage ${row.title_term_coverage_pct ?? "РЅ/Рґ"}%`, getDisplayTitle, createEntityActionButtons });
}

function renderSalesReturnActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "Р Р°Р·РѕР±СЂР°С‚СЊ СЃРµР№С‡Р°СЃ", subtitle: "SKU Рё РїСЂРёС‡РёРЅС‹, РіРґРµ РІРѕР·РІСЂР°С‚С‹ РєРѕРЅС†РµРЅС‚СЂРёСЂСѓСЋС‚СЃСЏ СЃРёР»СЊРЅРµРµ РІСЃРµРіРѕ", rows: (actions.investigate_now || []).slice(0, 8), formatter: (row) => `${row.reason || "Р‘РµР· РїСЂРёС‡РёРЅС‹"} В· РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "РћС‡Р°РіРё РїРѕ РїСЂРёС‡РёРЅР°Рј", subtitle: "РџСЂРёС‡РёРЅС‹ РІРѕР·РІСЂР°С‚Р°, РєРѕС‚РѕСЂС‹Рµ СѓР¶Рµ С„РѕСЂРјРёСЂСѓСЋС‚ РѕСЃРЅРѕРІРЅСѓСЋ РјР°СЃСЃСѓ РїСЂРѕР±Р»РµРјС‹", rows: (actions.reason_hotspots || []).slice(0, 8), formatter: (row) => `РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}${row.amount_value ? ` В· СЃСѓРјРјР° ${formatMoney(row.amount_value)}` : ""}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "РџСЂРѕР±РµР»С‹ РґР°РЅРЅС‹С…", subtitle: "РЎС‚СЂРѕРєРё Р±РµР· СѓРІРµСЂРµРЅРЅРѕР№ РїСЂРёРІСЏР·РєРё Рє С‚РѕРІР°СЂСѓ", rows: (actions.identity_gaps || []).slice(0, 8), formatter: (row) => `${row.reason || "Р‘РµР· РїСЂРёС‡РёРЅС‹"} В· РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}`, getDisplayTitle, createEntityActionButtons });
}

function renderWaybillActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "РџРѕСЃР»РµРґРЅРёРµ Рё РґРѕСЂРѕРіРёРµ РїР°СЂС‚РёРё", subtitle: "Batch-СЃС‚СЂРѕРєРё, РєРѕС‚РѕСЂС‹Рµ РїРµСЂРІС‹РјРё РІР»РёСЏСЋС‚ РЅР° cost-layer Рё С‚СЂРµР±СѓСЋС‚ СЃРІРµСЂРєРё", rows: (actions.reorder_now || []).slice(0, 8), formatter: (row) => `batch ${formatMoney(row.batch_cogs_total || 0)} В· qty ${formatNumber(row.quantity_supplied || 0)} В· unit ${formatMoney(row.unit_cogs || 0)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "Р’РѕР»Р°С‚РёР»СЊРЅРѕСЃС‚СЊ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё", subtitle: "Identity, РіРґРµ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚СЊ СѓР¶Рµ РјРµРЅСЏР»Р°СЃСЊ РјРµР¶РґСѓ РїР°СЂС‚РёСЏРјРё", rows: (actions.markdown_candidates || []).slice(0, 8), formatter: (row) => `latest ${formatMoney(row.latest_unit_cogs || 0)} В· avg ${formatMoney(row.avg_unit_cogs || 0)} В· batches ${formatNumber(row.batch_count || 0)}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "РљСЂСѓРїРЅРµР№С€РёРµ batch-cost СЃС‚СЂРѕРєРё", subtitle: "РЎР°РјС‹Рµ С‚СЏР¶С‘Р»С‹Рµ РїРѕ СЃСѓРјРјРµ СЃС‚СЂРѕРєРё С‚РµРєСѓС‰РµРіРѕ СЃР»РѕСЏ РЅР°РєР»Р°РґРЅС‹С…", rows: (actions.protect_winners || []).slice(0, 8), formatter: (row) => `batch ${formatMoney(row.batch_cogs_total || 0)} В· qty ${formatNumber(row.quantity_supplied || 0)}`, getDisplayTitle, createEntityActionButtons });
}

function renderPaidStorageActions(payload) {
  const actions = payload.actions || {};
  renderActionCard({ root: document.getElementById("action-reorder"), title: "РљСЂСѓРїРЅРµР№С€РёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ", subtitle: "РЎС‚СЂРѕРєРё, РіРґРµ РЅР°РєРѕРїРёР»СЃСЏ РЅР°РёР±РѕР»СЊС€РёР№ РїР»Р°С‚РЅС‹Р№ СЃР»РѕР№", rows: (actions.reorder_now || []).slice(0, 8), formatter: (row) => `${row.amount_label || "СЃСѓРјРјР°"} ${formatMoney(row.amount || 0)}${row.identity ? ` В· ${row.identity}` : ""}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-markdown"), title: "РџСЂРѕРІРµСЂРёС‚СЊ РІСЂСѓС‡РЅСѓСЋ", subtitle: "РЎС‚СЂРѕРєРё Р±РµР· СЏРІРЅРѕРіРѕ SKU РёР»Рё РїРѕРЅСЏС‚РЅРѕР№ РёРґРµРЅС‚РёС„РёРєР°С†РёРё", rows: (actions.markdown_candidates || []).slice(0, 8), formatter: (row) => `${row.amount_label || "СЃСѓРјРјР°"} ${formatMoney(row.amount || 0)} В· identity ${row.identity || "РЅ/Рґ"}`, getDisplayTitle, createEntityActionButtons });
  renderActionCard({ root: document.getElementById("action-protect"), title: "Р’С‹СЃРѕРєРёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ", subtitle: "РЎС‚СЂРѕРєРё, РіРґРµ СЃСѓРјРјР° СѓР¶Рµ СЏРІРЅРѕ РІС‹С€Рµ РѕСЃРЅРѕРІРЅРѕРіРѕ РјР°СЃСЃРёРІР°", rows: (actions.protect_winners || []).slice(0, 8), formatter: (row) => `${row.amount_label || "СЃСѓРјРјР°"} ${formatMoney(row.amount || 0)}${row.identity ? ` В· ${row.identity}` : ""}`, getDisplayTitle, createEntityActionButtons });
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
    createActionButton("Р”РµС‚Р°Р»Рё", "secondary", async () => {
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
    createActionButton("Р’ СЃРїРёСЃРѕРє", "secondary", async () => {
      const payload = buildEntityPayload(row, context);
      await addWatchlistItem(payload);
      await refreshActionCenter();
    }),
    createActionButton("Р—Р°РґР°С‡Р°", "primary", async () => {
      const note = window.prompt("РљРѕСЂРѕС‚РєР°СЏ Р·Р°РґР°С‡Р° РёР»Рё Р·Р°РјРµС‚РєР°", "") || "";
      const owner = window.prompt("РћС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Р№ РїРѕ Р·Р°РґР°С‡Рµ", getStoredActionOwner()) || "";
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
    const owner = row.owner || "Р±РµР· РѕС‚РІРµС‚СЃС‚РІРµРЅРЅРѕРіРѕ";
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
    { key: "РќРѕРІС‹Рµ", value: counts.open },
    { key: "Р’ СЂР°Р±РѕС‚Рµ", value: counts.in_progress },
    { key: "Р‘Р»РѕРєРµСЂС‹", value: counts.blocked },
    { key: "Р“РѕС‚РѕРІРѕ", value: counts.done },
  ];
}

function renderActionCenterToolbar() {
  const root = document.getElementById("action-center-toolbar");
  if (!root) return;
  root.innerHTML = "";
  const wrap = el("div", "inline-form");
  const ownerInput = el("input", "inline-input");
  ownerInput.type = "text";
  ownerInput.placeholder = "РњРѕР№ РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Р№";
  ownerInput.value = getStoredActionOwner();
  ownerInput.addEventListener("change", () => {
    setStoredActionOwner(ownerInput.value.trim());
    renderActionCenter();
  });
  const filterSelect = el("select", "inline-select");
  [
    ["all", "Р’СЃРµ Р·Р°РґР°С‡Рё"],
    ["open", "РќРѕРІС‹Рµ"],
    ["in_progress", "Р’ СЂР°Р±РѕС‚Рµ"],
    ["blocked", "Р‘Р»РѕРєРµСЂС‹"],
    ["done", "Р“РѕС‚РѕРІРѕ"],
    ["mine", "РўРѕР»СЊРєРѕ РјРѕРё"],
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
  const saveButton = createActionButton("РЎРѕС…СЂР°РЅРёС‚СЊ РїСЂРµРґСЃС‚Р°РІР»РµРЅРёРµ", "secondary", async () => {
    const name = window.prompt("РќР°Р·РІР°РЅРёРµ СЃРѕС…СЂР°РЅС‘РЅРЅРѕРіРѕ РїСЂРµРґСЃС‚Р°РІР»РµРЅРёСЏ", "") || "";
    if (!name.trim()) return;
    await saveActionView({
      name: name.trim(),
      filters: { filter: selectedActionFilter, owner: getStoredActionOwner() },
    });
    await refreshActionCenter();
  });
  wrap.append(ownerInput, filterSelect, saveButton);
  root.append(wrap);
  root.append(el("p", "job-card-text", "Р Р°Р±РѕС‡РёР№ С†РёРєР» СЃРµР№С‡Р°СЃ С‚Р°РєРѕР№: РІС‹Р±СЂР°Р» СЃСѓС‰РЅРѕСЃС‚СЊ РІ РѕС‚С‡С‘С‚Рµ в†’ РґРѕР±Р°РІРёР» РІ СЃРїРёСЃРѕРє РЅР°Р±Р»СЋРґРµРЅРёСЏ РёР»Рё СЃРѕР·РґР°Р» Р·Р°РґР°С‡Сѓ в†’ РІСЂСѓС‡РЅСѓСЋ РїРµСЂРµРІС‘Р» СЃС‚Р°С‚СѓСЃ в†’ РїСЂРё С„Р°РєС‚РёС‡РµСЃРєРѕРј Р·Р°РІРµСЂС€РµРЅРёРё Р·Р°РєСЂС‹Р» Р·Р°РґР°С‡Сѓ."));
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
  appendHeadingWithInfo(statusCard, "h3", "РћС‡РµСЂРµРґСЊ РїРѕ СЃС‚Р°С‚СѓСЃР°Рј", "РџРѕРєР°Р·С‹РІР°РµС‚, РіРґРµ СѓР·РєРѕРµ РјРµСЃС‚Рѕ С†РёРєР»Р°: РЅРѕРІС‹Рµ Р·Р°РґР°С‡Рё, Р°РєС‚РёРІРЅР°СЏ СЂР°Р±РѕС‚Р°, Р±Р»РѕРєРµСЂС‹ РёР»Рё СѓР¶Рµ Р·Р°РєСЂС‹С‚С‹Рµ СЌР»РµРјРµРЅС‚С‹.");
  const statusList = el("ul", "compact-list");
  summarizeActionStatuses(allActions).forEach((row) => {
    const item = el("li");
    item.append(el("strong", "", row.key));
    item.append(el("span", "", `${formatNumber(row.value)} Р·Р°РґР°С‡`));
    statusList.append(item);
  });
  statusCard.append(statusList);
  statusRoot.append(statusCard);

  const ownerCard = el("div", "list-card");
  appendHeadingWithInfo(ownerCard, "h3", "РћС‡РµСЂРµРґСЊ РїРѕ РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Рј", "РџРѕРєР°Р·С‹РІР°РµС‚ РЅР°РіСЂСѓР·РєСѓ Рё Р±Р»РѕРєРµСЂС‹ РїРѕ РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Рј. Р”Р°Р¶Рµ РІ single-user СЂРµР¶РёРјРµ СЌС‚Рѕ РїРѕР»РµР·РЅРѕ РєР°Рє Р·Р°РґРµР» РїРѕРґ manager workflow.");
  const ownerRows = summarizeActionOwners(allActions);
  if (!ownerRows.length) {
    ownerCard.append(el("p", "empty-state", "РќР°Р·РЅР°С‡РµРЅРЅС‹С… РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹С… РїРѕРєР° РЅРµС‚."));
  } else {
    const ownerList = el("ul", "compact-list");
    ownerRows.slice(0, 8).forEach((row) => {
      const item = el("li");
      item.append(el("strong", "", row.owner));
      item.append(el("span", "", `РЅРѕРІС‹Рµ ${row.open}, РІ СЂР°Р±РѕС‚Рµ ${row.in_progress}, Р±Р»РѕРєРµСЂС‹ ${row.blocked}, Р·Р°РІРµСЂС€РµРЅРѕ ${row.done}`));
      ownerList.append(item);
    });
    ownerCard.append(ownerList);
  }
  ownerRoot.append(ownerCard);

  const viewCard = el("div", "list-card");
  appendHeadingWithInfo(viewCard, "h3", "РЎРѕС…СЂР°РЅС‘РЅРЅС‹Рµ РїСЂРµРґСЃС‚Р°РІР»РµРЅРёСЏ", "РЎРѕС…СЂР°РЅС‘РЅРЅС‹Рµ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРёРµ РѕС‡РµСЂРµРґРё. Р­С‚Рѕ Р±С‹СЃС‚СЂС‹Рµ СЂРµР¶РёРјС‹ СЂР°Р±РѕС‚С‹ РґР»СЏ РµР¶РµРґРЅРµРІРЅРѕРіРѕ follow-up.");
  const savedViews = actionCenterState.saved_views || [];
  if (!savedViews.length) {
    viewCard.append(el("p", "empty-state", "РЎРѕС…СЂР°РЅС‘РЅРЅС‹С… РїСЂРµРґСЃС‚Р°РІР»РµРЅРёР№ РїРѕРєР° РЅРµС‚."));
  } else {
    const viewList = el("ul", "compact-list");
    savedViews.slice(0, 8).forEach((row) => {
      const item = el("li");
      const content = el("div", "list-item-main");
      content.append(el("strong", "", row.name));
      content.append(el("span", "", `С„РёР»СЊС‚СЂ ${row.filters?.filter || "all"}${row.filters?.owner ? ` В· РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Р№ ${row.filters.owner}` : ""}`));
      item.append(content);
      const jump = createActionButton("РћС‚РєСЂС‹С‚СЊ", "secondary", async () => {
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
    watchlist_added: "Р”РѕР±Р°РІР»РµРЅРѕ РІ СЃРїРёСЃРѕРє",
    watchlist_updated: "РћР±РЅРѕРІР»С‘РЅ СЃРїРёСЃРѕРє",
    action_added: "РЎРѕР·РґР°РЅР° Р·Р°РґР°С‡Р°",
    action_updated: "РћР±РЅРѕРІР»РµРЅР° Р·Р°РґР°С‡Р°",
    action_toggled: "РР·РјРµРЅС‘РЅ СЃС‚Р°С‚СѓСЃ Р·Р°РґР°С‡Рё",
    acknowledged: "РџРѕРґС‚РІРµСЂР¶РґС‘РЅ СЂР°Р·Р±РѕСЂ",
  };
  return labels[eventType] || eventType || "РЎРѕР±С‹С‚РёРµ";
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
    bar.title = `${history[i]?.report_name?.slice(0, 20) || "РѕС‚С‡С‘С‚"}: score ${score}`;
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
    root.append(el("p", "empty-state", "Р’С‹Р±РµСЂРё В«Р”РµС‚Р°Р»РёВ» Сѓ СЃС‚СЂРѕРєРё РѕС‚С‡С‘С‚Р°, С‡С‚РѕР±С‹ РѕС‚РєСЂС‹С‚СЊ РёСЃС‚РѕСЂРёСЋ СЃСѓС‰РЅРѕСЃС‚Рё Рё РµС‘ СЂСѓС‡РЅРѕР№ СЃС‚Р°С‚СѓСЃ."));
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
      navRow.append(createActionButton("в†ђ РџСЂРµРґС‹РґСѓС‰Р°СЏ", "secondary", async () => {
        selectedEntityKey = prevEntity.entity_key;
        renderEntityDetail(prevEntity.row);
      }));
    }
    if (nextEntity) {
      navRow.append(createActionButton("РЎР»РµРґСѓСЋС‰Р°СЏ в†’", "secondary", async () => {
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
    pos.title = "РџРѕР·РёС†РёСЏ РІ С‚РµРєСѓС‰РµРј СЃРїРёСЃРєРµ СЃСѓС‰РЅРѕСЃС‚РµР№";
    titleRow.append(pos);
  }
  const crossKindCount = countCrossReportKinds(history);
  if (crossKindCount > 1) {
    const badge = el("span", "entity-cross-badge", `${crossKindCount} РѕС‚С‡С‘С‚Р°`);
    badge.title = `РЎСѓС‰РЅРѕСЃС‚СЊ РІСЃС‚СЂРµС‡Р°Р»Р°СЃСЊ РІ ${crossKindCount} СЂР°Р·РЅС‹С… С‚РёРїР°С… РѕС‚С‡С‘С‚РѕРІ`;
    titleRow.append(badge);
  }
  card1.append(titleRow);

  // (i) info icon via appendHeadingWithInfo вЂ” attach as sub-note
  const infoNote = el("p", "entity-info-note", "РўРµРєСѓС‰РёР№ СЃСЂРµР· РїРѕ СЃСѓС‰РЅРѕСЃС‚Рё: latest marketing signal РїР»СЋСЃ СЂСѓС‡РЅРѕР№ follow-up.");
  card1.append(infoNote);

  const topNavigator = renderEntityNavigator();
  if (topNavigator) {
    card1.append(topNavigator);
  }

  // Core fields
  card1.append(el("p", "", `РўРёРї: ${latest.group ? "РєР°СЂС‚РѕС‡РєР° / SKU" : "СЃСѓС‰РЅРѕСЃС‚СЊ"}`));
  if (resolvedSku) {
    card1.append(el("p", "", `SKU: ${resolvedSku}`));
  }
  card1.append(el("p", "", `РџРѕСЃР»РµРґРЅРёР№ СЃРёРіРЅР°Р»: ${resolvedActionLabel || "РЅ/Рґ"}`));
  card1.append(el("p", "", `Р“СЂСѓРїРїР° / РєРѕСЂРёРґРѕСЂ: ${resolvedGroup || "РЅ/Рґ"} / ${resolvedPriceBand || "РЅ/Рґ"}`));
  card1.append(el("p", "", `Р¦РµРЅРѕРІР°СЏ Р»РѕРІСѓС€РєР°: ${resolvedPriceTrap ? "РґР°" : "РЅРµС‚"} В· SEO: ${resolvedSeoStatus || "РЅ/Рґ"} В· Р¦РµРЅРѕРІРѕР№ СЃС‚Р°С‚СѓСЃ: ${resolvedPricingLabel || "РЅ/Рґ"}`));
  if (!resolvedActionLabel || !resolvedGroup || !resolvedPricingLabel) {
    card1.append(el("p", "job-card-text", "Р§Р°СЃС‚СЊ РїРѕР»РµР№ Р±РµСЂС‘С‚СЃСЏ РёР· РЅР°РєРѕРїР»РµРЅРЅРѕР№ РёСЃС‚РѕСЂРёРё. Р•СЃР»Рё РІ С‚РµРєСѓС‰РµРј СЃСЂРµР·Рµ РїСѓСЃС‚Рѕ, РїР°РЅРµР»СЊ РїС‹С‚Р°РµС‚СЃСЏ РІРѕСЃСЃС‚Р°РЅРѕРІРёС‚СЊ РїРѕСЃР»РµРґРЅРµРµ РѕСЃРјС‹СЃР»РµРЅРЅРѕРµ Р·РЅР°С‡РµРЅРёРµ."));
  }

  // History sparkline
  if (history.length > 1) {
    const sparkRow = el("div", "entity-spark-row");
    sparkRow.append(el("span", "entity-spark-label", "РСЃС‚РѕСЂРёСЏ score:"));
    sparkRow.append(renderHistorySparkline(history));
    const latest_score = history[0]?.priority_score;
    if (latest_score != null) {
      sparkRow.append(el("span", "entity-spark-value", String(latest_score)));
    }
    card1.append(sparkRow);
  }

  summaryGrid.append(card1);

  const card2 = el("div", "list-card");
  appendHeadingWithInfo(card2, "h3", "Р СѓС‡РЅРѕР№ СЃС‚Р°С‚СѓСЃ", "РџРѕРєР°Р·С‹РІР°РµС‚, С‡С‚Рѕ РјРµРЅРµРґР¶РµСЂ СѓР¶Рµ СЃРґРµР»Р°Р» РїРѕ СЌС‚РѕР№ СЃСѓС‰РЅРѕСЃС‚Рё: watchlist, РѕС‚РєСЂС‹С‚С‹Рµ Рё Р·Р°РєСЂС‹С‚С‹Рµ Р·Р°РґР°С‡Рё.");
  card2.append(el("p", "", `Р’ СЃРїРёСЃРєРµ РЅР°Р±Р»СЋРґРµРЅРёСЏ: ${status.watch ? "РґР°" : "РЅРµС‚"}`));
  card2.append(el("p", "", `РћС‚РєСЂС‹С‚С‹С… Р·Р°РґР°С‡: ${formatNumber(status.openCount)}`));
  card2.append(el("p", "", `Р—Р°РєСЂС‹С‚С‹С… Р·Р°РґР°С‡: ${formatNumber(status.doneCount)}`));
  if (status.watch?.context) {
    card2.append(el("p", "", `РљРѕРЅС‚РµРєСЃС‚ watchlist: ${status.watch.context}`));
  }
  if (status.acknowledgement?.acknowledged_at) {
    card2.append(el("p", "", `РџРѕРґС‚РІРµСЂР¶РґРµРЅРѕ: ${String(status.acknowledgement.acknowledged_at).slice(0, 19).replace("T", " ")}`));
  }
  if (status.acknowledgement?.note) {
    card2.append(el("p", "", `РљРѕРјРјРµРЅС‚Р°СЂРёР№ СЂР°Р·Р±РѕСЂР°: ${status.acknowledgement.note}`));
  }
  if (status.actions[0]?.note) {
    card2.append(el("p", "", `РџРѕСЃР»РµРґРЅСЏСЏ Р·Р°РјРµС‚РєР°: ${status.actions[0].note}`));
  }
  const ackButton = createActionButton("РџРѕРґС‚РІРµСЂРґРёС‚СЊ СЂР°Р·Р±РѕСЂ", "primary", async () => {
    const note = window.prompt("РљРѕСЂРѕС‚РєРёР№ РєРѕРјРјРµРЅС‚Р°СЂРёР№ РїРѕ СЂР°Р·Р±РѕСЂСѓ РєР°СЂС‚РѕС‡РєРё", status.acknowledgement?.note || "") || "";
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
    hint.innerHTML = `РќР°РІРёРіР°С†РёСЏ: <kbd>в†ђ</kbd><kbd>в†’</kbd> вЂ” РїСЂРµРґ./СЃР»РµРґ. СЃСѓС‰РЅРѕСЃС‚СЊ &nbsp;В·&nbsp; <kbd>Esc</kbd> вЂ” Р·Р°РєСЂС‹С‚СЊ`;
    root.append(hint);
  }

  const historyCard = el("div", "list-card");
  appendHeadingWithInfo(historyCard, "h3", "РСЃС‚РѕСЂРёСЏ СЃРёРіРЅР°Р»РѕРІ", "Р­С‚Рѕ Р»РµРЅС‚Р° РїРѕСЏРІР»РµРЅРёСЏ СЃСѓС‰РЅРѕСЃС‚Рё РІ РѕС‚С‡С‘С‚Р°С…. РћРЅР° РЅСѓР¶РЅР°, С‡С‚РѕР±С‹ РїРѕРЅСЏС‚СЊ: СЃРёРіРЅР°Р» РЅРѕРІС‹Р№, РїРѕРІС‚РѕСЂСЏСЋС‰РёР№СЃСЏ РёР»Рё СѓСЃС‚РѕР№С‡РёРІС‹Р№. РџРѕ РЅРµР№ СЂРµС€Р°СЋС‚, СѓСЃРёР»РёРІР°С‚СЊ РєР°СЂС‚РѕС‡РєСѓ, СЃС‚Р°РІРёС‚СЊ follow-up РёР»Рё СЃС‡РёС‚Р°С‚СЊ С€СѓРјРѕРј.");
  if (!history.length) {
    historyCard.append(el("p", "empty-state", "РСЃС‚РѕСЂРёСЏ РїРѕ СЌС‚РѕР№ СЃСѓС‰РЅРѕСЃС‚Рё РїРѕРєР° РЅРµ РЅР°РєРѕРїР»РµРЅР°."));
  } else {
    const list = el("div", "entity-history-list");
    history.slice(0, 8).forEach((row) => {
      const item = el("div", "history-row");
      item.append(el("strong", "", `${row.report_name} В· ${String(row.generated_at || "РЅ/Рґ").slice(0, 10)}`));
      item.append(el("span", "", `${row.action_label || "РЅ/Рґ"} В· score ${row.priority_score ?? "РЅ/Рґ"} В· ${row.group || "РЅ/Рґ"} / ${row.price_band || "РЅ/Рґ"}`));
      item.append(el("span", "", `С†РµРЅРѕРІР°СЏ Р»РѕРІСѓС€РєР°: ${row.price_trap ? "РґР°" : "РЅРµС‚"} В· SEO: ${row.seo_status || "РЅ/Рґ"} В· С†РµРЅРѕРІРѕР№ СЃС‚Р°С‚СѓСЃ: ${row.pricing_label || "РЅ/Рґ"}`));
      list.append(item);
    });
    historyCard.append(list);
  }
  root.append(historyCard);

  const decisionCard = el("div", "list-card");
  appendHeadingWithInfo(decisionCard, "h3", "РСЃС‚РѕСЂРёСЏ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРёС… СЂРµС€РµРЅРёР№", "Р–СѓСЂРЅР°Р» СЂСѓС‡РЅС‹С… РґРµР№СЃС‚РІРёР№ РїРѕ СЃСѓС‰РЅРѕСЃС‚Рё: watchlist, Р·Р°РґР°С‡Рё, РїРµСЂРµРєР»СЋС‡РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° Рё РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ СЂР°Р·Р±РѕСЂР°.");
  if (!status.events.length) {
    decisionCard.append(el("p", "empty-state", "РџРѕ СЌС‚РѕР№ СЃСѓС‰РЅРѕСЃС‚Рё РµС‰С‘ РЅРµС‚ СЂСѓС‡РЅРѕР№ РёСЃС‚РѕСЂРёРё СЂРµС€РµРЅРёР№."));
  } else {
    const list = el("div", "entity-history-list");
    status.events.slice(0, 12).forEach((row) => {
      const item = el("div", "history-row");
      item.append(el("strong", "", `${formatEventType(row.event_type)} В· ${String(row.created_at || "РЅ/Рґ").slice(0, 19).replace("T", " ")}`));
      item.append(el("span", "", `${row.context || "Р±РµР· РєРѕРЅС‚РµРєСЃС‚Р°"}${row.status ? ` В· СЃС‚Р°С‚СѓСЃ ${row.status}` : ""}`));
      if (row.note) {
        item.append(el("span", "", `РљРѕРјРјРµРЅС‚Р°СЂРёР№: ${row.note}`));
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
    appendHeadingWithInfo(navCard, "h3", "РќР°РІРёРіР°С†РёСЏ РїРѕ СЃСѓС‰РЅРѕСЃС‚СЏРј", "РќРёР¶РЅСЏСЏ РЅР°РІРёРіР°С†РёСЏ РЅСѓР¶РЅР°, С‡С‚РѕР±С‹ РјРѕР¶РЅРѕ Р±С‹Р»Рѕ РёРґС‚Рё РїРѕ СЃРѕСЃРµРґРЅРёРј SKU Р±РµР· РІРѕР·РІСЂР°С‚Р° Рє РІРµСЂС…РЅРµР№ С‡Р°СЃС‚Рё detail-panel.");
    navCard.append(el("p", "", "РСЃРїРѕР»СЊР·СѓР№ СЌС‚Рё РєРЅРѕРїРєРё, РµСЃР»Рё СѓР¶Рµ РїСЂРѕС‡РёС‚Р°Р» РёСЃС‚РѕСЂРёСЋ Рё С…РѕС‡РµС€СЊ СЃСЂР°Р·Сѓ РїРµСЂРµР№С‚Рё Рє СЃР»РµРґСѓСЋС‰РµР№ РїРѕР·РёС†РёРё."));
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
    card.append(el("h3", "", "РЎСЂР°РІРЅРµРЅРёРµ РїРѕРєР° РЅРµРґРѕСЃС‚СѓРїРЅРѕ"));
    card.append(el("p", "", change ? "РџСЂРµРґС‹РґСѓС‰РёР№ РѕС‚С‡С‘С‚ РЅР°Р№РґРµРЅ, РЅРѕ Р·Р°РјРµС‚РЅС‹С… С‡РёСЃР»РѕРІС‹С… РёР·РјРµРЅРµРЅРёР№ РЅРµ Р·Р°С„РёРєСЃРёСЂРѕРІР°РЅРѕ." : "Р”Р»СЏ СЌС‚РѕРіРѕ С‚РёРїР° РѕС‚С‡С‘С‚Р° РµС‰С‘ РЅРµС‚ РїСЂРµРґС‹РґСѓС‰РµРіРѕ bundle РґР»СЏ СЃСЂР°РІРЅРµРЅРёСЏ."));
    root.append(card);
    return;
  }
  (change.summary || []).forEach((row) => {
    const card = el("div", "insight-card");
    const deltaPct = row.delta_pct === null || row.delta_pct === undefined ? "РЅ/Рґ" : formatPercent(row.delta_pct);
    const deltaRaw = row.delta > 0 ? `+${formatNumber(row.delta)}` : formatNumber(row.delta);
    card.dataset.tone = row.delta > 0 ? "good" : "warn";
    card.append(el("h3", "", metricLabel(row.key)));
    card.append(el("p", "", `РЎРµР№С‡Р°СЃ ${formatNumber(row.current)}, СЂР°РЅСЊС€Рµ ${formatNumber(row.previous)}. РР·РјРµРЅРµРЅРёРµ: ${deltaRaw}, ${deltaPct}.`));
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
      card.append(el("h3", "", "Р¦РµРЅС‚СЂ РґРµР№СЃС‚РІРёР№ РЅРµРґРѕСЃС‚СѓРїРµРЅ"));
      card.append(el("p", "", "Р—Р°РїСѓСЃС‚Рё `web_refresh_server.py`, С‡С‚РѕР±С‹ РІРєР»СЋС‡РёС‚СЊ СЃРѕС…СЂР°РЅРµРЅРёРµ watchlist Рё СЂСѓС‡РЅС‹С… Р·Р°РґР°С‡."));
      root.append(card);
    });
    return;
  }

  const watchCard = el("div", "list-card");
  appendHeadingWithInfo(watchCard, "h3", "РЎРїРёСЃРѕРє РЅР°Р±Р»СЋРґРµРЅРёСЏ", "РЎСЋРґР° РїРѕРїР°РґР°СЋС‚ СЃСѓС‰РЅРѕСЃС‚Рё, Рє РєРѕС‚РѕСЂС‹Рј РЅСѓР¶РЅРѕ РІРµСЂРЅСѓС‚СЊСЃСЏ: SKU, СЃРµРјРµР№СЃС‚РІР°, РїСЂРѕРґР°РІС†С‹, РЅРёС€Рё. Р­С‚Рѕ РЅРµ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРµ РґРµР№СЃС‚РІРёРµ, Р° СЂСѓС‡РЅРѕР№ short-list РјРµРЅРµРґР¶РµСЂР°.");
  const watchRows = actionCenterState.watchlists || [];
  if (!watchRows.length) {
    watchCard.append(el("p", "empty-state", "РЎРїРёСЃРѕРє РЅР°Р±Р»СЋРґРµРЅРёСЏ РїРѕРєР° РїСѓСЃС‚."));
  } else {
    const list = el("ul", "compact-list");
    watchRows.slice(0, 8).forEach((row) => {
      const item = el("li");
      item.append(el("strong", "", row.title));
      item.append(el("span", "", `${formatEntityType(row.entity_type)}, ${row.context || "Р±РµР· РєРѕРЅС‚РµРєСЃС‚Р°"}`));
      list.append(item);
    });
    watchCard.append(list);
  }
  watchRoot.append(watchCard);

  const actionCard = el("div", "list-card");
  appendHeadingWithInfo(actionCard, "h3", "Р СѓС‡РЅС‹Рµ Р·Р°РґР°С‡Рё", "РњРёРЅРёРјР°Р»СЊРЅС‹Р№ action-center: С„РёРєСЃРёСЂСѓРµС‚ СЂРµС€РµРЅРёСЏ РјРµРЅРµРґР¶РµСЂР° РїРѕРІРµСЂС… Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёС… СЃРёРіРЅР°Р»РѕРІ.");
  const actionRows = filterActionRows(actionCenterState.actions || []);
  if (!actionRows.length) {
    actionCard.append(el("p", "empty-state", "Р СѓС‡РЅС‹С… Р·Р°РґР°С‡ РїРѕРєР° РЅРµС‚."));
  } else {
    const list = el("ul", "compact-list");
    actionRows.slice(0, 8).forEach((row) => {
      const item = el("li");
      const content = el("div", "list-item-main");
      content.append(el("strong", "", row.title));
      content.append(el("span", "", `${formatActionStatus(row.status || "open")}${row.owner ? ` В· РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹Р№ ${row.owner}` : ""}${row.note ? ` В· ${row.note}` : ""}`));
      item.append(content);
      const controls = el("div", "entity-actions");
      controls.append(
        createActionButton("Р’ СЂР°Р±РѕС‚Сѓ", "secondary", async () => {
          await updateActionItem({ id: row.id, status: "in_progress" });
          await refreshActionCenter();
        }),
        createActionButton("Р‘Р»РѕРєРµСЂ", "secondary", async () => {
          await updateActionItem({ id: row.id, status: "blocked" });
          await refreshActionCenter();
        }),
        createActionButton(row.status === "done" ? "РћС‚РєСЂС‹С‚СЊ" : "Р“РѕС‚РѕРІРѕ", "secondary", async () => {
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
  appendHeadingWithInfo(statusCard, "h3", "РЎРѕСЃС‚РѕСЏРЅРёРµ", "РџРѕРєР°Р·С‹РІР°РµС‚, Р¶РёРІ Р»Рё local action-center, СЃРєРѕР»СЊРєРѕ СѓР¶Рµ РЅР°РєРѕРїР»РµРЅРѕ СЂСѓС‡РЅС‹С… СЃСѓС‰РЅРѕСЃС‚РµР№ Рё РЅР°СЃРєРѕР»СЊРєРѕ Р°РєС‚РёРІРЅРѕ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ manager loop.");
  statusCard.append(el("p", "", `Р’ СЃРїРёСЃРєРµ РЅР°Р±Р»СЋРґРµРЅРёСЏ: ${formatNumber((actionCenterState.watchlists || []).length)}`));
  statusCard.append(el("p", "", `РћС‚РєСЂС‹С‚С‹С… Р·Р°РґР°С‡: ${formatNumber(actionCenterState.open_actions_count || 0)}`));
  statusCard.append(el("p", "", `Р—Р°РєСЂС‹С‚С‹С… Р·Р°РґР°С‡: ${formatNumber(actionCenterState.done_actions_count || 0)}`));
  statusCard.append(el("p", "", `РџРѕРґС‚РІРµСЂР¶РґС‘РЅРЅС‹С… СЃСѓС‰РЅРѕСЃС‚РµР№: ${formatNumber(actionCenterState.acknowledged_entities_count || 0)}`));
  statusCard.append(el("p", "", `РЎРѕР±С‹С‚РёР№ РІ Р¶СѓСЂРЅР°Р»Рµ: ${formatNumber(actionCenterState.event_count || 0)}`));
  statusCard.append(el("p", "", `РЎРѕС…СЂР°РЅС‘РЅРЅС‹С… РїСЂРµРґСЃС‚Р°РІР»РµРЅРёР№: ${formatNumber((actionCenterState.saved_views || []).length)}`));
  statusCard.append(el("p", "", `Р’РµСЂСЃРёСЏ СЃС…РµРјС‹: ${actionCenterState.schema_version || "РЅ/Рґ"}`));
  statusCard.append(el("p", "", "РЎС‚Р°С‚СѓСЃС‹ Р·Р°РґР°С‡ РїРѕРєР° РјРµРЅСЏСЋС‚СЃСЏ РІСЂСѓС‡РЅСѓСЋ: РЅРѕРІР°СЏ в†’ РІ СЂР°Р±РѕС‚Рµ в†’ Р±Р»РѕРєРµСЂ/Р·Р°РІРµСЂС€РµРЅР°. РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРіРѕ Р·Р°РєСЂС‹С‚РёСЏ, retry-СЃС‡С‘С‚С‡РёРєРѕРІ Рё SLA РїРѕРєР° РЅРµС‚."));
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
  appendHeadingWithInfo(lifecycleCard, "h3", "Р–РёР·РЅРµРЅРЅС‹Р№ С†РёРєР» Р·Р°РґР°С‡", "РџРѕРєР° СЌС‚Рѕ СЂСѓС‡РЅРѕР№ workflow. РЎРёСЃС‚РµРјР° РЅРµ Р·Р°РєСЂС‹РІР°РµС‚ Р·Р°РґР°С‡Сѓ СЃР°РјР° Рё РЅРµ РґРµР»Р°РµС‚ retry Р±РµР· СЂРµС€РµРЅРёСЏ РјРµРЅРµРґР¶РµСЂР°.");
  lifecycleCard.append(el("p", "", "1. РќРѕРІР°СЏ: Р·Р°РґР°С‡Р° СЃРѕР·РґР°РЅР° РёР· СЃРёРіРЅР°Р»Р° РёР»Рё РІСЂСѓС‡РЅСѓСЋ Рё РµС‰С‘ РЅРµ РІР·СЏС‚Р° РІ СЂР°Р±РѕС‚Сѓ."));
  lifecycleCard.append(el("p", "", "2. Р’ СЂР°Р±РѕС‚Рµ: РјРµРЅРµРґР¶РµСЂ РїРѕРґС‚РІРµСЂРґРёР», С‡С‚Рѕ Р·Р°РґР°С‡Р° СЂРµР°Р»СЊРЅРѕ РёСЃРїРѕР»РЅСЏРµС‚СЃСЏ."));
  lifecycleCard.append(el("p", "", "3. Р‘Р»РѕРєРµСЂ: РµСЃС‚СЊ РІРЅРµС€РЅСЏСЏ РїСЂРёС‡РёРЅР°, РїРѕС‡РµРјСѓ С€Р°Рі РЅРµР»СЊР·СЏ Р·Р°РєСЂС‹С‚СЊ СЃРµР№С‡Р°СЃ."));
  lifecycleCard.append(el("p", "", "4. Р—Р°РІРµСЂС€РµРЅР°: РјРµРЅРµРґР¶РµСЂ РІСЂСѓС‡РЅСѓСЋ РїРѕРґС‚РІРµСЂРґРёР», С‡С‚Рѕ С€Р°Рі РІС‹РїРѕР»РЅРµРЅ Рё РјРѕР¶РЅРѕ Р·Р°РєСЂС‹РІР°С‚СЊ РєРѕРЅС‚СѓСЂ."));
  lifecycleCard.append(el("p", "", "РџРѕРєР° РЅРµС‚ auto-close, SLA, С‚Р°Р№РјРµСЂРѕРІ Рё СЃС‡С‘С‚С‡РёРєРѕРІ РїРѕРїС‹С‚РѕРє. Р­С‚Рѕ РѕС‚РґРµР»СЊРЅС‹Р№ product-СЃР»РѕР№, РєРѕС‚РѕСЂС‹Р№ РµС‰С‘ РЅРµ РІРЅРµРґСЂС‘РЅ."));
  statusRoot.append(lifecycleCard);
}

function renderTables(payload) {
  const tables = payload.tables || {};
  const currentRows = (tables.current_winners || []).length ? (tables.current_winners || []) : (tables.soft_signal_products || []);
  const currentTitle = (tables.current_winners || []).length ? "Р§С‚Рѕ РїСЂРѕРґР°С‘С‚СЃСЏ СЃРµР№С‡Р°СЃ" : "РЎР»Р°Р±С‹Рµ, РЅРѕ Р¶РёРІС‹Рµ СЃРёРіРЅР°Р»С‹";
  const currentInfo = (tables.current_winners || []).length
    ? "Р­С‚Рѕ С‚РѕРІР°СЂС‹ СЃ РѕСЃРјС‹СЃР»РµРЅРЅС‹Рј С‚РµРєСѓС‰РёРј СЃРёРіРЅР°Р»РѕРј РІ РѕРєРЅРµ, Р° РЅРµ РёСЃС‚РѕСЂРёС‡РµСЃРєРёРµ С…РёС‚С‹. РСЃРїРѕР»СЊР·СѓР№С‚Рµ РёС… РєР°Рє СЃРїРёСЃРѕРє С‚РѕРіРѕ, С‡С‚Рѕ СЂРµР°Р»СЊРЅРѕ Р¶РёРІРѕ СЃРµР№С‡Р°СЃ."
    : "РЎС‚СЂРѕРіРёС… РїРѕР±РµРґРёС‚РµР»РµР№ РІ РѕРєРЅРµ РЅРµС‚, РЅРѕ Р·РґРµСЃСЊ РІРёРґРЅС‹ С‚РѕРІР°СЂС‹ СЃ РїСЂРѕРґР°Р¶Р°РјРё, РєРѕС‚РѕСЂС‹Рµ СѓР¶Рµ РїРѕРґР°СЋС‚ СЃРёРіРЅР°Р». Р­С‚Рѕ СЃРїРёСЃРѕРє РґР»СЏ РЅР°Р±Р»СЋРґРµРЅРёСЏ Рё РѕСЃС‚РѕСЂРѕР¶РЅРѕРіРѕ СѓСЃРёР»РµРЅРёСЏ.";
  renderTableCard({ root: document.getElementById("table-winners"), title: currentTitle, rows: currentRows, formatter: (row) => `РїСЂРѕРґР°РЅРѕ ${row.units_sold}, РІС‹СЂСѓС‡РєР° ${formatMoney(row.net_revenue)}, ABC ${row.abc_revenue}`, infoText: currentInfo, getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Р›РёРґРµСЂС‹ РїРѕ РїСЂРёР±С‹Р»Рё", rows: tables.profit_leaders || [], formatter: (row) => `РїСЂРёР±С‹Р»СЊ ${formatMoney(row.gross_profit)}, РјР°СЂР¶Р° ${row.profit_margin_pct}%`, infoText: "РџРѕРєР°Р·С‹РІР°РµС‚ С‚РѕРІР°СЂС‹, РєРѕС‚РѕСЂС‹Рµ РїСЂРёРЅРѕСЃСЏС‚ Р±РѕР»СЊС€Рµ РІСЃРµРіРѕ РІР°Р»РѕРІРѕР№ РїСЂРёР±С‹Р»Рё РІ С‚РµРєСѓС‰РµРј РѕРєРЅРµ. Р­С‚Рѕ РїСЂРёРѕСЂРёС‚РµС‚ РґР»СЏ Р·Р°С‰РёС‚С‹ РЅР°Р»РёС‡РёСЏ Рё РєР°С‡РµСЃС‚РІР° РєР°СЂС‚РѕС‡РєРё.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Р РёСЃРє Р·Р°РєРѕРЅС‡РёС‚СЊСЃСЏ", rows: tables.stockout_risk || [], formatter: (row) => `РѕСЃС‚Р°С‚РѕРє ${row.total_stock}, РїРѕРєСЂС‹С‚РёРµ ${row.stock_cover_days ?? "в€ћ"} РґРЅ.`, infoText: "РЎРїРёСЃРѕРє РїРѕР·РёС†РёР№, РіРґРµ РѕСЃС‚Р°С‚РѕРє РєРѕСЂРѕС‚РєРёР№ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ С‚РµРєСѓС‰РµРіРѕ С‚РµРјРїР° РїСЂРѕРґР°Р¶. РЎРјРѕС‚СЂРёС‚Рµ СЃСЋРґР° РґР»СЏ РїСЂРёРѕСЂРёС‚РµС‚Р° Р·Р°РєСѓРїРєРё.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Р›РµР¶РёС‚ Р±РµР· РґРІРёР¶РµРЅРёСЏ", rows: tables.stale_stock || [], formatter: (row) => `РѕСЃС‚Р°С‚РѕРє ${row.total_stock}, СЃС‚РѕРёРјРѕСЃС‚СЊ ${formatMoney(row.stock_value_sale)}`, infoText: "РџРѕР·РёС†РёРё Р±РµР· РґРІРёР¶РµРЅРёСЏ РІ С‚РµРєСѓС‰РµРј РѕРєРЅРµ. Р­С‚Рѕ РєР°РЅРґРёРґР°С‚С‹ РЅР° С‡РёСЃС‚РєСѓ, СѓС†РµРЅРєСѓ, РїРµСЂРµСЃР±РѕСЂРєСѓ РєР°СЂС‚РѕС‡РєРё РёР»Рё РѕС‚РєР»СЋС‡РµРЅРёРµ.", getDisplayTitle, createEntityActionButtons });
}

function renderFamilyTables(payload) {
  const families = payload.family_tables || {};
  const familyCurrentRows = (families.family_current_winners || []).length ? (families.family_current_winners || []) : (families.family_soft_signal_products || []);
  const familyCurrentTitle = (families.family_current_winners || []).length ? "РЎРµРјРµР№СЃС‚РІР°, РєРѕС‚РѕСЂС‹Рµ РїСЂРѕРґР°СЋС‚СЃСЏ" : "РЎРµРјРµР№СЃС‚РІР° СЃ СЂР°РЅРЅРёРј СЃРёРіРЅР°Р»РѕРј";
  const familyCurrentInfo = (families.family_current_winners || []).length
    ? "РЎРµРјРµР№СЃС‚РІР° РїРѕРјРѕРіР°СЋС‚ СЃРјРѕС‚СЂРµС‚СЊ РЅР° РєР°СЂС‚РѕС‡РєСѓ С†РµР»РёРєРѕРј, РµСЃР»Рё РІ РЅРµР№ РЅРµСЃРєРѕР»СЊРєРѕ РЁРљ РёР»Рё РІР°СЂРёР°РЅС‚РѕРІ. Р­С‚Рѕ РїРѕР»РµР·РЅРѕ С‚Р°Рј, РіРґРµ РѕРґРЅР° СЃС‚СЂРѕРєР° CSV РІРІРѕРґРёС‚ РІ Р·Р°Р±Р»СѓР¶РґРµРЅРёРµ."
    : "РЎС‚СЂРѕРіРёС… СЃРµРјРµР№-РїРѕР±РµРґРёС‚РµР»РµР№ РІ РѕРєРЅРµ РЅРµС‚. Р—РґРµСЃСЊ РІРёРґРЅС‹ РєР°СЂС‚РѕС‡РєРё, Сѓ РєРѕС‚РѕСЂС‹С… СѓР¶Рµ РµСЃС‚СЊ РїРµСЂРІС‹Рµ РїСЂРѕРґР°Р¶Рё РЅР° СѓСЂРѕРІРЅРµ СЃРµРјРµР№СЃС‚РІР°, РЅРѕ СЃРёРіРЅР°Р» РµС‰С‘ СЃР»Р°Р±С‹Р№.";
  renderTableCard({ root: document.getElementById("family-winners"), title: familyCurrentTitle, rows: familyCurrentRows, formatter: (row) => `РІР°СЂРёР°РЅС‚РѕРІ ${row.variant_count}, РїСЂРѕРґР°РЅРѕ ${row.sold_units_sum}, РІС‹СЂСѓС‡РєР° ${formatMoney(row.net_revenue_sum)}`, infoText: familyCurrentInfo, getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("family-reorder"), title: "РЎРµРјРµР№СЃС‚РІР° РЅР° РґРѕР·Р°РєСѓРїРєСѓ", rows: families.family_reorder_now || [], formatter: (row) => `РІР°СЂРёР°РЅС‚РѕРІ ${row.variant_count}, РѕСЃС‚Р°С‚РѕРє ${row.stock_units_sum}, РїРѕРєСЂС‹С‚РёРµ ${row.stock_cover_days ?? "в€ћ"} РґРЅ.`, infoText: "РџРѕРєР°Р·С‹РІР°РµС‚ РєР°СЂС‚РѕС‡РєРё, РіРґРµ РїСЂРѕР±Р»РµРјР° СѓР¶Рµ РЅРµ РІ РѕРґРЅРѕРј SKU, Р° РЅР° СѓСЂРѕРІРЅРµ РІСЃРµРіРѕ СЃРµРјРµР№СЃС‚РІР° С‚РѕРІР°СЂР°.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("family-variants"), title: "РљСЂСѓРїРЅС‹Рµ РєР°СЂС‚РѕС‡РєРё СЃ РІР°СЂРёР°РЅС‚Р°РјРё", rows: families.largest_multi_variant_families || [], formatter: (row) => `РІР°СЂРёР°РЅС‚РѕРІ ${row.variant_count}, РЁРљ ${row.barcode_count}, РѕСЃС‚Р°С‚РѕРє ${row.stock_units_sum}`, infoText: "РЎСЋРґР° СЃРјРѕС‚СЂСЏС‚, РєРѕРіРґР° РЅСѓР¶РЅРѕ РїРѕРЅСЏС‚СЊ: РєР°СЂС‚РѕС‡РєР° РІ С†РµР»РѕРј Р¶РёРІР° РёР»Рё РїСЂРѕРґР°Р¶Рё Рё РѕСЃС‚Р°С‚РєРё СЂР°Р·РјР°Р·Р°РЅС‹ РїРѕ РІР°СЂРёР°РЅС‚Р°Рј.", getDisplayTitle, createEntityActionButtons });
}

function getAbcHelpText(metricLabel) {
  return `ABC РїРѕ ${metricLabel} РґРµР»РёС‚ Р°СЃСЃРѕСЂС‚РёРјРµРЅС‚ РЅР° С‚СЂРё СЃР»РѕСЏ: A вЂ” СЏРґСЂРѕ, РєРѕС‚РѕСЂРѕРµ РґР°С‘С‚ РѕСЃРЅРѕРІРЅСѓСЋ РґРѕР»СЋ СЂРµР·СѓР»СЊС‚Р°С‚Р°; B вЂ” РїРѕРґРґРµСЂР¶РёРІР°СЋС‰РёР№ СЃСЂРµРґРЅРёР№ СЃР»РѕР№; C вЂ” РґР»РёРЅРЅС‹Р№ С…РІРѕСЃС‚. РџСЂР°РєС‚РёС‡РµСЃРєРё СЌС‚Рѕ С‡РёС‚Р°РµС‚СЃСЏ С‚Р°Рє: A РґРµСЂР¶Р°С‚СЊ РІ РЅР°Р»РёС‡РёРё Рё РєРѕРЅС‚СЂРѕР»РёСЂРѕРІР°С‚СЊ РµР¶РµРґРЅРµРІРЅРѕ, B РѕРїС‚РёРјРёР·РёСЂРѕРІР°С‚СЊ Рё РјР°СЃС€С‚Р°Р±РёСЂРѕРІР°С‚СЊ РІС‹Р±РѕСЂРѕС‡РЅРѕ, C С‡РёСЃС‚РёС‚СЊ, РїРµСЂРµСЂР°Р±Р°С‚С‹РІР°С‚СЊ РѕС„С„РµСЂ РёР»Рё РІС‹РІРѕРґРёС‚СЊ.`;
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
  const explainer = el("p", "abc-explainer", "РќРµ РїСЂРѕСЃС‚Рѕ С€РєР°Р»Р°: СЃРјРѕС‚СЂРёС‚Рµ, РєР°РєСѓСЋ РґРѕР»СЋ СЂРµР·СѓР»СЊС‚Р°С‚Р° РґР°С‘С‚ РєР°Р¶РґР°СЏ Р·РѕРЅР° Рё РєР°Рє СЂР°СЃРїСЂРµРґРµР»С‘РЅ Р°СЃСЃРѕСЂС‚РёРјРµРЅС‚.");
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
  notes.append(el("p", "", "A: РґРµСЂР¶Р°С‚СЊ РІ РЅР°Р»РёС‡РёРё, РєРѕРЅС‚СЂРѕР»РёСЂРѕРІР°С‚СЊ С„РѕС‚Рѕ, СЂРµР№С‚РёРЅРі Рё С†РµРЅСѓ, РЅРµ С‚РµСЂСЏС‚СЊ РЅР°Р»РёС‡РёРµ."));
  notes.append(el("p", "", "B: РєР°РЅРґРёРґР°С‚С‹ РЅР° СЂР°Р·РІРёС‚РёРµ Рё С‚РµСЃС‚С‹ РїСЂРѕРґРІРёР¶РµРЅРёСЏ, РµСЃР»Рё СЌРєРѕРЅРѕРјРёРєР° СѓР¶Рµ РЅРѕСЂРјР°Р»СЊРЅР°СЏ."));
  notes.append(el("p", "", "C: РґР»РёРЅРЅС‹Р№ С…РІРѕСЃС‚. РЎСЋРґР° СЃРјРѕС‚СЂСЏС‚ РґР»СЏ С‡РёСЃС‚РєРё, СѓС†РµРЅРєРё, РїРµСЂРµСЂР°Р±РѕС‚РєРё РєР°СЂС‚РѕС‡РєРё РёР»Рё РІС‹РІРѕРґР°."));
  card.append(notes);
  return card;
}

function renderAbcExamplesCard(title, metricLabel, examplesByBucket, formatter) {
  const card = el("div", "chart-card abc-card");
  appendHeadingWithInfo(card, "h3", title, `РџРѕРєР°Р·С‹РІР°РµС‚ РєРѕРЅРєСЂРµС‚РЅС‹Рµ SKU РІРЅСѓС‚СЂРё Р·РѕРЅ A/B/C РїРѕ РјРµС‚СЂРёРєРµ "${metricLabel}". Р­С‚Рѕ СѓР¶Рµ СЂР°Р±РѕС‡РёР№ СЃРїРёСЃРѕРє РґР»СЏ РґРµР№СЃС‚РІРёР№, Р° РЅРµ С‚РѕР»СЊРєРѕ Р°РіСЂРµРіРёСЂРѕРІР°РЅРЅР°СЏ С€РєР°Р»Р°.`);
  const buckets = examplesByBucket || {};
  const zones = ["A", "B", "C"];
  const anyRows = zones.some((zone) => (buckets[zone] || []).length);
  if (!anyRows) {
    card.append(el("p", "empty-state", "РќРµС‚ РґР°РЅРЅС‹С… РґР»СЏ СЌС‚РѕРіРѕ Р±Р»РѕРєР°."));
    return card;
  }
  zones.forEach((zone) => {
    const rows = buckets[zone] || [];
    const section = el("div", "abc-example-zone");
    section.append(el("strong", "", `Р—РѕРЅР° ${zone}`));
    if (!rows.length) {
      section.append(el("p", "empty-state", "РќРµС‚ SKU РІ СЌС‚РѕР№ Р·РѕРЅРµ."));
      card.append(section);
      return;
    }
    const list = el("ul", "compact-list");
    rows.forEach((row) => {
      const item = el("li");
      item.append(el("strong", "", getDisplayTitle(row)));
      item.append(el("span", "", `${metricLabel}: ${formatter(metricLabel === "РїСЂРёР±С‹Р»СЊ" ? row.gross_profit : row.net_revenue)}, РїСЂРѕРґР°РЅРѕ ${formatNumber(row.units_sold)}`));
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
  root.append(renderAbcInterpretationCard("ABC РїРѕ РІС‹СЂСѓС‡РєРµ", "РІС‹СЂСѓС‡РєР°", charts.abc_revenue_counts || [], charts.revenue_by_abc || [], formatMoney));
  root.append(renderAbcInterpretationCard("ABC РїРѕ РїСЂРёР±С‹Р»Рё", "РїСЂРёР±С‹Р»СЊ", charts.abc_profit_counts || [], charts.profit_by_abc || [], formatMoney));
  root.append(renderAbcExamplesCard("РљР°РєРёРµ SKU РІС…РѕРґСЏС‚ РІ ABC РїРѕ РІС‹СЂСѓС‡РєРµ", "РІС‹СЂСѓС‡РєР°", charts.abc_revenue_examples || {}, formatMoney));
  root.append(renderAbcExamplesCard("РљР°РєРёРµ SKU РІС…РѕРґСЏС‚ РІ ABC РїРѕ РїСЂРёР±С‹Р»Рё", "РїСЂРёР±С‹Р»СЊ", charts.abc_profit_examples || {}, formatMoney));
  root.append(renderBarChart("РЎС‚Р°С‚СѓСЃС‹", charts.status_counts || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, СЃРєРѕР»СЊРєРѕ SKU СЃРµР№С‡Р°СЃ РЅР°С…РѕРґРёС‚СЃСЏ РІ РєР°Р¶РґРѕРј operational-СЃС‚Р°С‚СѓСЃРµ. Р­С‚Рѕ РЅРµ РёСЃС‚РѕСЂРёСЏ, Р° СЃРЅРёРјРѕРє С‚РµРєСѓС‰РµРіРѕ РѕРєРЅР°."));
  root.append(renderBarChart("Р’С‹СЂСѓС‡РєР° РїРѕ ABC", charts.revenue_by_abc || [], formatMoney, "РЎРєРѕР»СЊРєРѕ РІС‹СЂСѓС‡РєРё РїСЂРёРЅРѕСЃРёС‚ РєР°Р¶РґР°СЏ Р·РѕРЅР° A/B/C. РџРѕР»РµР·РЅРѕ, С‡С‚РѕР±С‹ РЅРµ РїСѓС‚Р°С‚СЊ С‡РёСЃР»Рѕ SKU СЃ СЂРµР°Р»СЊРЅС‹Рј РІРєР»Р°РґРѕРј РІ РґРµРЅСЊРіРё."));
}

function renderMarketCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Р—Р°РєР°Р·С‹ РїРѕ С†РµРЅРѕРІС‹Рј РєРѕСЂРёРґРѕСЂР°Рј", charts.price_bands || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, РІ РєР°РєРёС… С†РµРЅРѕРІС‹С… РґРёР°РїР°Р·РѕРЅР°С… СЃРѕСЃСЂРµРґРѕС‚РѕС‡РµРЅ СЃРїСЂРѕСЃ РІ РЅР°Р±Р»СЋРґР°РµРјРѕРј СЂС‹РЅРєРµ Р·Р° РІС‹Р±СЂР°РЅРЅС‹Р№ СЃСЂРµР·."));
  root.append(renderBarChart("Р—Р°РєР°Р·С‹ РїРѕ РіСЂСѓРїРїР°Рј", charts.group_orders || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, РєР°РєРёРµ С‚РѕРІР°СЂРЅС‹Рµ РіСЂСѓРїРїС‹ СЃРѕР±РёСЂР°СЋС‚ Р±РѕР»СЊС€Рµ РІСЃРµРіРѕ РІРёРґРёРјС‹С… Р·Р°РєР°Р·РѕРІ РІ С‚РµРєСѓС‰РµРј СЂС‹РЅРѕС‡РЅРѕРј СЃСЂРµР·Рµ."));
}

function renderPricingCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("РЎС‚СЂСѓРєС‚СѓСЂР° pricing-СЂРµРєРѕРјРµРЅРґР°С†РёР№", charts.pricing_labels || [], formatNumber, "РљР°Рє СЂР°СЃРїСЂРµРґРµР»СЏСЋС‚СЃСЏ С†РµРЅРѕРІС‹Рµ СЂРµС€РµРЅРёСЏ: РґРµСЂР¶Р°С‚СЊ С†РµРЅСѓ, С‚РµСЃС‚РёСЂРѕРІР°С‚СЊ, РІС…РѕРґРёС‚СЊ Р°РіСЂРµСЃСЃРёРІРЅРµРµ РёР»Рё РЅРµ РґРµРјРїРёРЅРіРѕРІР°С‚СЊ."));
  root.append(renderBarChart("РЎСЂРµРґРЅСЏСЏ С†РµРЅР° СЂС‹РЅРєР° РїРѕ РѕРєРЅР°Рј", charts.avg_market_price_by_band || [], formatMoney, "РЎСЂРµРґРЅСЏСЏ СЂС‹РЅРѕС‡РЅР°СЏ С†РµРЅР° РїРѕ РєР°Р¶РґРѕРјСѓ С†РµРЅРѕРІРѕРјСѓ РєРѕСЂРёРґРѕСЂСѓ. Р­С‚Рѕ РѕРїРѕСЂРЅС‹Р№ СЃР»РѕР№, Р° РЅРµ РіРѕС‚РѕРІР°СЏ С†РµРЅР° РґР»СЏ Р°РІС‚Рѕ-РїСЂРёРјРµРЅРµРЅРёСЏ."));
}

function renderMarketingCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("РўРёРїС‹ РјР°СЂРєРµС‚РёРЅРіРѕРІС‹С… РґРµР№СЃС‚РІРёР№", charts.priority_buckets || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, РєР°РєРёРµ РґРµР№СЃС‚РІРёСЏ С‡Р°С‰Рµ РІСЃРµРіРѕ С‚СЂРµР±СѓСЋС‚СЃСЏ СЃРµР№С‡Р°СЃ: С†РµРЅР°, title, С„РѕС‚Рѕ, РѕРїРёСЃР°РЅРёРµ РёР»Рё РєРѕРјР±РёРЅРёСЂРѕРІР°РЅРЅС‹Р№ fix."));
  root.append(renderBarChart("РЎС‚Р°С‚СѓСЃС‹ title SEO", charts.seo_status_counts || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚ СЂР°СЃРїСЂРµРґРµР»РµРЅРёРµ title РїРѕ РєР°С‡РµСЃС‚РІСѓ: РЅРѕСЂРј, С‚СЂРµР±СѓРµС‚ СЂР°Р±РѕС‚С‹ РёР»Рё РєСЂРёС‚РёС‡РЅС‹Р№ priority fix."));
  root.append(renderBarChart("РўРёРїС‹ РїСЂРѕР±Р»РµРј", charts.issue_type_counts || [], formatNumber, "РђРіСЂРµРіРёСЂСѓРµС‚, С‡С‚Рѕ РёРјРµРЅРЅРѕ С‡Р°С‰Рµ РІСЃРµРіРѕ Р»РѕРјР°РµС‚ РєР°СЂС‚РѕС‡РєРё РІ СЌС‚РѕРј РѕС‚С‡С‘С‚Рµ."));
}

function renderMediaCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("РЎС‚Р°С‚СѓСЃС‹ media-Р°СѓРґРёС‚Р°", charts.media_status_counts || [], formatNumber, "РЎРІРѕРґРєР° РїРѕ РєР°С‡РµСЃС‚РІСѓ РјРµРґРёР°: РіРґРµ РєР°СЂС‚РѕС‡РєРё СѓР¶Рµ РЅРѕСЂРјР°Р»СЊРЅС‹Рµ, Р° РіРґРµ С„РѕС‚Рѕ РёР»Рё С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё РѕС‚СЃС‚Р°СЋС‚ РѕС‚ РіСЂСѓРїРїС‹."));
  root.append(renderBarChart("Р¤РѕС‚Рѕ РїРѕ РєРѕСЂР·РёРЅР°Рј", charts.photo_bucket_counts || [], formatNumber, "Р Р°СЃРїСЂРµРґРµР»РµРЅРёРµ РїРѕ С‡РёСЃР»Сѓ С„РѕС‚Рѕ. РџРѕР»РµР·РЅРѕ, РєРѕРіРґР° РЅСѓР¶РЅРѕ Р±С‹СЃС‚СЂРѕ РїРѕРЅСЏС‚СЊ, СѓРїРёСЂР°РµРјСЃСЏ Р»Рё РјС‹ РІ Р±РµРґРЅС‹Рµ РєР°СЂС‚РѕС‡РєРё."));
  root.append(renderBarChart("РџР»РѕС‚РЅРѕСЃС‚СЊ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє", charts.spec_bucket_counts || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, РЅР°СЃРєРѕР»СЊРєРѕ РїРѕР»РЅРѕ Р·Р°РїРѕР»РЅРµРЅС‹ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєРё. Р§РµРј Р±РѕР»СЊС€Рµ РїСѓСЃС‚РѕС‚, С‚РµРј С…СѓР¶Рµ РєР°СЂС‚РѕС‡РєР° РґРµСЂР¶РёС‚СЃСЏ РІ СЃСЂР°РІРЅРµРЅРёРё."));
}

function renderDescriptionCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("РЎС‚Р°С‚СѓСЃС‹ description-Р°СѓРґРёС‚Р°", charts.description_status_counts || [], formatNumber, "РЎРІРѕРґРєР° РїРѕ РєР°С‡РµСЃС‚РІСѓ РѕРїРёСЃР°РЅРёР№: РіРґРµ РѕРїРёСЃР°РЅРёСЏ СѓР¶Рµ РґРѕСЃС‚Р°С‚РѕС‡РЅС‹Рµ, Р° РіРґРµ РѕРЅРё СЃР»РёС€РєРѕРј СЃР»Р°Р±С‹Рµ РґР»СЏ РєР°СЂС‚РѕС‡РєРё."));
  root.append(renderBarChart("Р”Р»РёРЅР° РѕРїРёСЃР°РЅРёР№", charts.description_length_counts || [], formatNumber, "Р Р°СЃРїСЂРµРґРµР»РµРЅРёРµ РїРѕ РґР»РёРЅРµ РѕРїРёСЃР°РЅРёР№. Р­С‚Рѕ РїРѕРјРѕРіР°РµС‚ Р±С‹СЃС‚СЂРѕ СѓРІРёРґРµС‚СЊ СЃР»РѕР№ С‚РѕРЅРєРѕРіРѕ РєРѕРЅС‚РµРЅС‚Р°."));
  root.append(renderBarChart("РџРѕРєСЂС‹С‚РёРµ title-С‚РµСЂРјРѕРІ", charts.title_term_coverage_counts || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, РЅР°СЃРєРѕР»СЊРєРѕ РѕРїРёСЃР°РЅРёРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚ РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РёР· title, Р° РЅРµ СЂР°СЃС…РѕРґРёС‚СЃСЏ СЃ РЅРёРј."));
}

function renderSalesReturnCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("Р“Р»Р°РІРЅС‹Рµ РїСЂРёС‡РёРЅС‹ РІРѕР·РІСЂР°С‚Р°", charts.reason_distribution || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚, РєР°РєРёРµ РїСЂРёС‡РёРЅС‹ СѓР¶Рµ РґР°СЋС‚ РѕСЃРЅРѕРІРЅСѓСЋ РјР°СЃСЃСѓ РІРѕР·РІСЂР°С‚РѕРІ. Р•СЃР»Рё РѕРґРЅР° РїСЂРёС‡РёРЅР° РґРѕРјРёРЅРёСЂСѓРµС‚, РµС‘ РЅСѓР¶РЅРѕ С‡РёРЅРёС‚СЊ СЂР°РЅСЊС€Рµ РґР»РёРЅРЅРѕРіРѕ С…РІРѕСЃС‚Р°."));
  root.append(renderBarChart("Р”РЅРµРІРЅР°СЏ РґРёРЅР°РјРёРєР° РІРѕР·РІСЂР°С‚РѕРІ", charts.daily_returns || [], formatNumber, "Р”РёРЅР°РјРёРєР° РІРѕР·РІСЂР°С‚РѕРІ РїРѕ РґРЅСЏРј РІРЅСѓС‚СЂРё РѕРєРЅР°. РџРѕР»РµР·РЅР°, С‡С‚РѕР±С‹ РѕС‚РґРµР»СЏС‚СЊ СЃРёСЃС‚РµРјРЅСѓСЋ РїСЂРѕР±Р»РµРјСѓ РѕС‚ РµРґРёРЅРёС‡РЅРѕРіРѕ РІСЃРїР»РµСЃРєР°."));
}

function renderWaybillCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("РљРѕРЅС†РµРЅС‚СЂР°С†РёСЏ batch-cost", charts.cost_distribution || [], formatMoney, "РџРѕРєР°Р·С‹РІР°РµС‚, СЃРєРѕР»СЊРєРѕ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё СЃРѕСЃСЂРµРґРѕС‚РѕС‡РµРЅРѕ РІ РІРµСЂС…РЅРёС… СЃС‚СЂРѕРєР°С… РїР°СЂС‚РёРё, Р° СЃРєРѕР»СЊРєРѕ СЂР°Р·РјР°Р·Р°РЅРѕ РїРѕ С…РІРѕСЃС‚Сѓ."));
  root.append(renderBarChart("РџРѕРєСЂС‹С‚РёРµ cost-layer", charts.numeric_columns || [], formatNumber, "Р‘С‹СЃС‚СЂС‹Р№ СЃСЂРµР· РїРѕ С‚РѕРјСѓ, РЅР°СЃРєРѕР»СЊРєРѕ СЃР»РѕР№ РЅР°РєР»Р°РґРЅС‹С… СѓР¶Рµ РїСЂРёРіРѕРґРµРЅ РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ historical COGS."));
  root.append(renderBarChart("Р•РґРёРЅРёС†С‹ РїРѕ РґР°С‚Р°Рј РїРѕСЃС‚Р°РІРєРё", charts.daily_returns || [], formatNumber, "РџРѕРєР°Р·С‹РІР°РµС‚ СЂР°СЃРїСЂРµРґРµР»РµРЅРёРµ РїРѕСЃС‚Р°РІР»РµРЅРЅС‹С… РµРґРёРЅРёС† РїРѕ РґР°С‚Р°Рј РїР°СЂС‚РёР№. Р­С‚Рѕ Р±Р°Р·Р° РґР»СЏ С‡С‚РµРЅРёСЏ batch-history."));
}

function renderPaidStorageCharts(payload) {
  const root = document.getElementById("chart-grid");
  root.innerHTML = "";
  const charts = payload.charts || {};
  root.append(renderBarChart("РљРѕРЅС†РµРЅС‚СЂР°С†РёСЏ РЅР°С‡РёСЃР»РµРЅРёР№", charts.cost_distribution || [], formatMoney, "РџРѕРєР°Р·С‹РІР°РµС‚, РєР°РєР°СЏ РґРѕР»СЏ РїР»Р°С‚РЅРѕРіРѕ СЃР»РѕСЏ РїСЂРёС…РѕРґРёС‚СЃСЏ РЅР° РєСЂСѓРїРЅРµР№С€РёРµ СЃС‚СЂРѕРєРё, Р° РєР°РєР°СЏ СЂР°Р·РјР°Р·Р°РЅР° РїРѕ С…РІРѕСЃС‚Сѓ."));
  root.append(renderBarChart("РљСЂСѓРїРЅРµР№С€РёРµ numeric-РєРѕР»РѕРЅРєРё", charts.numeric_columns || [], formatMoney, "РџРѕРјРѕРіР°РµС‚ РїРѕРЅСЏС‚СЊ, РєР°РєРёРµ С‡РёСЃР»РѕРІС‹Рµ РєРѕР»РѕРЅРєРё РІ XLSX СЂРµР°Р»СЊРЅРѕ С„РѕСЂРјРёСЂСѓСЋС‚ РѕСЃРЅРѕРІРЅСѓСЋ РјР°СЃСЃСѓ РЅР°С‡РёСЃР»РµРЅРёР№."));
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
      badge: pricing ? "Р”РѕСЃС‚СѓРїРЅРѕ" : "Runner only",
      summary: pricing
        ? "РћС‚РґРµР»СЊРЅС‹Р№ report/view СѓР¶Рµ РµСЃС‚СЊ РІ РѕСЃРЅРѕРІРЅРѕРј UI."
        : "РћС‚С‡С‘С‚ РµС‰С‘ РЅРµ РїРѕРїР°Р» РІ dashboard index, РЅРѕ job СѓР¶Рµ Р·Р°РІРµРґС‘РЅ РІ runner.",
      meta: [
        pricing ? `РџРѕСЃР»РµРґРЅРёР№ Р°СЂС‚РµС„Р°РєС‚: ${reportOptionLabel(pricing)}` : "РђСЂС‚РµС„Р°РєС‚ РІ РѕСЃРЅРѕРІРЅРѕРј UI РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅ.",
        "Р РµР¶РёРј: read-only report + Р»РѕРєР°Р»СЊРЅС‹Р№ rebuild С‡РµСЂРµР· refresh runner.",
      ],
      reportFile: pricing?.file_name,
      jobKey: "dynamic_pricing",
    },
    {
      title: "Marketing audit",
      state: marketing ? "available" : "runner",
      badge: marketing ? "Р”РѕСЃС‚СѓРїРЅРѕ" : "Runner only",
      summary: marketing
        ? "Price trap, title SEO Рё СЂС‹РЅРѕС‡РЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚ СѓР¶Рµ СЃРІРµРґРµРЅС‹ РІ РµРґРёРЅС‹Р№ СЌРєСЂР°РЅ."
        : "Unified marketing surface РµС‰С‘ РЅРµ РЅР°Р№РґРµРЅ РІ dashboard index.",
      meta: [
        marketing ? `РџРѕСЃР»РµРґРЅРёР№ Р°СЂС‚РµС„Р°РєС‚: ${reportOptionLabel(marketing)}` : "РђСЂС‚РµС„Р°РєС‚ РІ РѕСЃРЅРѕРІРЅРѕРј UI РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅ.",
        "Р РµР¶РёРј: read-only report + Р»РѕРєР°Р»СЊРЅС‹Р№ rebuild С‡РµСЂРµР· refresh runner.",
      ],
      reportFile: marketing?.file_name,
      jobKey: "marketing_card_audit",
    },
    {
      title: "Paid storage",
      state: paidStorage ? "available" : "runner",
      badge: paidStorage ? "Р”РѕСЃС‚СѓРїРЅРѕ" : "Runner only",
      summary: paidStorage
        ? "РљСЂСѓРїРЅС‹Рµ РЅР°С‡РёСЃР»РµРЅРёСЏ Рё СЃС‚СЂРѕРєРё Р±РµР· identity СѓР¶Рµ С‡РёС‚Р°СЋС‚СЃСЏ РІ РѕСЃРЅРѕРІРЅРѕРј UI."
        : "Р’ РѕСЃРЅРѕРІРЅРѕРј UI РµС‰С‘ РЅРµС‚ С‚РµРєСѓС‰РµРіРѕ paid storage bundle.",
      meta: [
        paidStorage ? `РџРѕСЃР»РµРґРЅРёР№ Р°СЂС‚РµС„Р°РєС‚: ${reportOptionLabel(paidStorage)}` : "РђСЂС‚РµС„Р°РєС‚ РІ РѕСЃРЅРѕРІРЅРѕРј UI РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅ.",
        "Р РµР¶РёРј: read-only report, СЃР°Рј seller-documents refresh РѕСЃС‚Р°С‘С‚СЃСЏ runner-driven.",
      ],
      reportFile: paidStorage?.file_name,
      jobKey: "paid_storage_report",
    },
    {
      title: "Waybill / historical COGS",
      state: waybill ? "available" : "runner",
      badge: waybill ? "Р”РѕСЃС‚СѓРїРЅРѕ" : "Runner only",
      summary: waybill
        ? "Batch-cost Рё historical COGS СЃР»РѕР№ СѓР¶Рµ РІС‹РЅРµСЃРµРЅС‹ РІ РѕСЃРЅРѕРІРЅРѕР№ РёРЅС‚РµСЂС„РµР№СЃ."
        : "Waybill СЃР»РѕР№ РµС‰С‘ РЅРµ РЅР°Р№РґРµРЅ РІ dashboard index.",
      meta: [
        waybill ? `РџРѕСЃР»РµРґРЅРёР№ Р°СЂС‚РµС„Р°РєС‚: ${reportOptionLabel(waybill)}` : "РђСЂС‚РµС„Р°РєС‚ РІ РѕСЃРЅРѕРІРЅРѕРј UI РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅ.",
        "Р РµР¶РёРј: read-only report + interactive rebuild С‡РµСЂРµР· runner job.",
      ],
      reportFile: waybill?.file_name,
      jobKey: "waybill_cost_layer",
    },
    {
      title: "Zero COGS cycle",
      state: cogsRows.length || rescoredMarket ? "partial" : "runner",
      badge: cogsRows.length || rescoredMarket ? "Partial" : "Runner only",
      summary: cogsRows.length
        ? "Р›РѕРєР°Р»СЊРЅРѕРµ С…СЂР°РЅРёР»РёС‰Рµ overrides СѓР¶Рµ Р·Р°РїРѕР»РЅРµРЅРѕ, РЅРѕ inline fill/edit РІ РѕСЃРЅРѕРІРЅРѕРј UI РїРѕРєР° РЅРµС‚."
        : "Р¦РёРєР» registry -> fill -> rescore СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚, РЅРѕ Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ С‡РµСЂРµР· refresh runner.",
      meta: [
        cogsStore?.generated_at
          ? `Р›РѕРєР°Р»СЊРЅС‹Р№ store: ${formatDateTime(cogsStore.generated_at)} В· rows ${formatNumber(cogsSummary.items_total || cogsRows.length)} В· imported ${formatNumber(cogsSummary.fill_rows_imported || 0)}`
          : "Р›РѕРєР°Р»СЊРЅС‹Р№ store COGS РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РµС‰С‘ РЅРµ Р±С‹Р» СЃРѕР±СЂР°РЅ.",
        rescoredMarket
          ? `РЎРІСЏР·Р°РЅРЅС‹Р№ Р°СЂС‚РµС„Р°РєС‚: ${reportOptionLabel(rescoredMarket)}`
          : "Rescored market bundle РїРѕСЃР»Рµ COGS РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅ РІ dashboard index.",
        "Р РµР¶РёРј: partial. РђСЂС‚РµС„Р°РєС‚С‹ РІРёРґРЅС‹, РЅРѕ СЃР°Рј fill/rescore С†РёРєР» РїРѕРєР° runner-driven.",
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
      const openBtn = el("button", "theme-toggle compact-button", "РћС‚РєСЂС‹С‚СЊ РІ UI");
      openBtn.type = "button";
      openBtn.addEventListener("click", async () => {
        await activateReport(flow.reportFile);
        document.getElementById("report-select")?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      actions.append(openBtn);
    }
    if (flow.jobKey) {
      const runnerLink = document.createElement("a");
      runnerLink.className = "theme-toggle compact-button";
      runnerLink.href = runnerJobUrl(flow.jobKey);
      runnerLink.textContent = flow.jobKey === "cogs_backfill_cycle" ? "РћС‚РєСЂС‹С‚СЊ COGS cycle" : "РћС‚РєСЂС‹С‚СЊ runner";
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
    "Р’С‹СЂСѓС‡РєР° Р·Р° 365 РґРЅРµР№",
    formatMoney(currentMetrics.revenue_total || 0),
    `${current.date_from || "РЅ/Рґ"} -> ${current.date_to || "РЅ/Рґ"}`,
    previous.delta_vs_current?.revenue_total_pct,
    "Р“РѕРґ Рє РіРѕРґСѓ"
  );
  renderCompareCard(
    root,
    "Р—Р°РєР°Р·С‹ Р·Р° 365 РґРЅРµР№",
    formatNumber(currentMetrics.orders_total || 0),
    "Р—Р°РєР°Р·С‹ Р·Р° 365 РґРЅРµР№",
    previous.delta_vs_current?.orders_total_pct,
    "Р“РѕРґ Рє РіРѕРґСѓ"
  );
  renderCompareCard(
    root,
    "РџСЂРѕРґР°РЅРЅС‹Рµ РµРґРёРЅРёС†С‹ Р·Р° 365 РґРЅРµР№",
    formatNumber(currentMetrics.items_sold_total || 0),
    "РџСЂРѕРґР°РЅРЅС‹Рµ РµРґРёРЅРёС†С‹ Р·Р° 365 РґРЅРµР№",
    previous.delta_vs_current?.items_sold_total_pct,
    "Р“РѕРґ Рє РіРѕРґСѓ"
  );
  renderCompareCard(
    root,
    "Р’С‹СЂСѓС‡РєР° СЃ РЅР°С‡Р°Р»Р° РіРѕРґР°",
    formatMoney((ytd.metrics || {}).revenue_total || 0),
    `${ytd.date_from || "РЅ/Рґ"} -> ${ytd.date_to || "РЅ/Рґ"}`,
    previousYtd.delta_vs_current?.revenue_total_pct,
    "РЎ РЅР°С‡Р°Р»Р° РіРѕРґР° Рє РїСЂРѕС€Р»РѕРјСѓ"
  );
  renderCompareCard(
    root,
    "Р‘Р°Р·Р° 3 РіРѕРґР° РЅР°Р·Р°Рґ",
    formatMoney((threeYear.metrics || {}).revenue_total || 0),
    `${threeYear.date_from || "РЅ/Рґ"} -> ${threeYear.date_to || "РЅ/Рґ"}`,
    threeYear.delta_vs_current?.revenue_total_pct,
    "РЎРґРІРёРі Рє Р±Р°Р·Рµ"
  );
  renderCompareCard(
    root,
    "Р“Р»СѓР±РёРЅР° РёСЃС‚РѕСЂРёРё",
    `${rawPayload.history_window?.history_years || 0} РіРѕРґР°`,
    `${rawPayload.history_window?.date_from || "РЅ/Рґ"} -> ${rawPayload.history_window?.date_to || "РЅ/Рґ"}`,
    null,
    "РџРѕРєСЂС‹С‚РёРµ"
  );

  const monthly = rawPayload.series_monthly || [];
  renderTrendCard(trendRoot, "Р’С‹СЂСѓС‡РєР° РїРѕ РјРµСЃСЏС†Р°Рј", monthly, "Sales.seller_revenue_without_delivery_measure", formatMoney);
  renderTrendCard(trendRoot, "Р—Р°РєР°Р·С‹ РїРѕ РјРµСЃСЏС†Р°Рј", monthly, "Sales.orders_number", formatNumber);
  renderTrendCard(trendRoot, "РџСЂРѕРґР°РЅРЅС‹Рµ РµРґРёРЅРёС†С‹ РїРѕ РјРµСЃСЏС†Р°Рј", monthly, "Sales.item_sold_number", formatNumber);
}

function renderMarketTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "РўРѕРї РїСЂРѕРґР°РІС†С‹", rows: tables.top_sellers || [], formatter: (row) => `Р·Р°РєР°Р·С‹ ${formatNumber(row.orders_sum)}, РґРѕР»СЏ ${formatShare(row.share_of_observed_orders_pct)}, С‚РѕРІР°СЂРѕРІ ${formatNumber(row.products_seen)}, СЏРґСЂРѕ ${row.top_group || "РЅ/Рґ"}, РЅРѕРІРёР·РЅР° ${row.novelty_proxy_index ?? "РЅ/Рґ"}`, infoText: "Р­С‚Рѕ Р»РёРґРµСЂС‹ РІРЅСѓС‚СЂРё РЅР°Р±Р»СЋРґР°РµРјРѕР№ СЂС‹РЅРѕС‡РЅРѕР№ РІС‹Р±РѕСЂРєРё, Р° РЅРµ Р°Р±СЃРѕР»СЋС‚РЅС‹Р№ СЂРµР№С‚РёРЅРі РІСЃРµРіРѕ РјР°СЂРєРµС‚РїР»РµР№СЃР°. РСЃРїРѕР»СЊР·СѓР№С‚Рµ РєР°Рє РѕСЂРёРµРЅС‚РёСЂ РґР»СЏ С‚РѕРіРѕ, РєС‚Рѕ РґРѕРјРёРЅРёСЂСѓРµС‚ РІ РІРёРґРёРјРѕР№ С‡Р°СЃС‚Рё РєР°С‚РµРіРѕСЂРёРё.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Р§С‚Рѕ РїСЂРѕРґР°С‘С‚СЃСЏ РІ СЂС‹РЅРєРµ", rows: tables.top_products || [], formatter: (row) => `РїСЂРѕРґР°РІРµС† ${row.seller_title || "РЅ/Рґ"}, Р·Р°РєР°Р·С‹ ${formatNumber(row.orders)}, С†РµРЅР° ${formatMoney(row.price)}, РѕС‚Р·С‹РІС‹ ${formatNumber(row.reviews)}, РЅРѕРІРёР·РЅР° ${row.novelty_proxy_score ?? "РЅ/Рґ"}`, infoText: "РЎРїРёСЃРѕРє Р·Р°РјРµС‚РЅС‹С… С‚РѕРІР°СЂРѕРІ РІ С‚РµРєСѓС‰РµРј market scan. Р­С‚Рѕ РїРѕРјРѕРіР°РµС‚ РїРѕРЅСЏС‚СЊ, РєР°РєРёРµ РѕС„С„РµСЂС‹ Рё С†РµРЅС‹ СѓР¶Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅС‹ СЂС‹РЅРєРѕРј.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "РЎРёР»СЊРЅРµР№С€РёРµ РіСЂСѓРїРїС‹", rows: tables.groups || [], formatter: (row) => `Р·Р°РєР°Р·С‹ ${formatNumber(row.orders_sum)}, РїСЂРѕРґР°РІС†РѕРІ ${formatNumber(row.seller_count)}, avg ${formatMoney(row.avg_price)}, HHI ${row.dominance_hhi ?? "РЅ/Рґ"}, margin fit ${row.market_margin_fit_pct ?? "РЅ/Рґ"}%, СЂР°Р·РЅРёС†Р° РґРѕ С†РµР»Рё ${row.margin_vs_target_pct ?? "РЅ/Рґ"} Рї.Рї.`, infoText: "РџРѕРєР°Р·С‹РІР°РµС‚, РєР°РєРёРµ С‚РѕРІР°СЂРЅС‹Рµ РіСЂСѓРїРїС‹ РІ РІС‹Р±РѕСЂРєРµ РЅРµСЃСѓС‚ РѕСЃРЅРѕРІРЅРѕР№ СЃРїСЂРѕСЃ, РЅР°СЃРєРѕР»СЊРєРѕ РѕРЅРё РЅР°СЃС‹С‰РµРЅС‹ РїСЂРѕРґР°РІС†Р°РјРё Рё РЅР°СЃРєРѕР»СЊРєРѕ СЂС‹РЅРѕС‡РЅР°СЏ С†РµРЅР° РІРѕРѕР±С‰Рµ СЃРѕРІРјРµСЃС‚РёРјР° СЃ РІР°С€РµР№ СЌРєРѕРЅРѕРјРёРєРѕР№. Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚ СЂР°Р·РЅРёС†Сѓ РјРµР¶РґСѓ С„Р°РєС‚РёС‡РµСЃРєРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊСЋ СЂС‹РЅРєР° Рё РІР°С€РµР№ С†РµР»РµРІРѕР№ РјР°СЂР¶РѕР№.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "РћРєРЅР° РІС…РѕРґР°", rows: tables.entry_windows || [], formatter: (row) => `РіСЂСѓРїРїР° ${row.group || "РЅ/Рґ"}, РєРѕСЂРёРґРѕСЂ ${row.price_band || "РЅ/Рґ"}, score ${row.entry_window_score ?? "РЅ/Рґ"}, СЂРµС€РµРЅРёРµ ${row.entry_strategy_label || "РЅ/Рґ"}, margin fit ${row.market_margin_fit_pct ?? "РЅ/Рґ"}%`, infoText: "Р­С‚Рѕ СЃРѕС‡РµС‚Р°РЅРёСЏ РіСЂСѓРїРїР° + С†РµРЅРѕРІРѕР№ РєРѕСЂРёРґРѕСЂ. Р—РґРµСЃСЊ СѓР¶Рµ РІРёРґРµРЅ РЅРµ С‚РѕР»СЊРєРѕ СЃРїСЂРѕСЃ, РЅРѕ Рё СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРѕРµ СЂРµС€РµРЅРёРµ: РІС…РѕРґРёС‚СЊ, С‚РµСЃС‚РёСЂРѕРІР°С‚СЊ, Р¶РґР°С‚СЊ РёР»Рё РЅРµ Р»РµР·С‚СЊ.", getDisplayTitle, createEntityActionButtons });
}

function renderPricingTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "Р’СЃРµ pricing-РѕРєРЅР°", rows: tables.priced_windows || [], formatter: (row) => `РіСЂСѓРїРїР° ${row.group || "РЅ/Рґ"}, РєРѕСЂРёРґРѕСЂ ${row.price_band || "РЅ/Рґ"}, СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}, Р±РµР·РѕРїР°СЃРЅРѕ ${formatMoney(row.min_safe_price)}, СЂРµРєРѕРјРµРЅРґР°С†РёСЏ ${formatMoney(row.suggested_price)}`, infoText: "Р’СЃРµ РѕРєРЅР°, РіРґРµ СѓР¶Рµ С…РІР°С‚Р°РµС‚ СЌРєРѕРЅРѕРјРёС‡РµСЃРєРёС… РґР°РЅРЅС‹С…, С‡С‚РѕР±С‹ РґР°С‚СЊ С†РµРЅРѕРІСѓСЋ СЂРµРєРѕРјРµРЅРґР°С†РёСЋ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Р“РґРµ РІС…РѕРґРёС‚СЊ Р°РіСЂРµСЃСЃРёРІРЅРѕ", rows: tables.aggressive_entry || [], formatter: (row) => `СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}, СЂРµРєРѕРјРµРЅРґР°С†РёСЏ ${formatMoney(row.suggested_price)}, margin fit ${row.market_margin_fit_pct ?? "РЅ/Рґ"}%`, infoText: "РћРєРЅР°, РіРґРµ РјРѕР¶РЅРѕ РёРґС‚Рё С‡СѓС‚СЊ РЅРёР¶Рµ СЂС‹РЅРєР° Рё РІСЃС‘ РµС‰С‘ РЅРµ СЂР°Р·СЂСѓС€Р°С‚СЊ СЌРєРѕРЅРѕРјРёРєСѓ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Р“РґРµ РґРµСЂР¶Р°С‚СЊ С†РµРЅСѓ СЂС‹РЅРєР°", rows: (payload.actions || {}).price_at_market || [], formatter: (row) => `СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}, СЂРµРєРѕРјРµРЅРґР°С†РёСЏ ${formatMoney(row.suggested_price)}, СЂР°Р·РЅРёС†Р° Рє СЂС‹РЅРєСѓ ${row.price_gap_pct ?? "РЅ/Рґ"}%`, infoText: "РћРєРЅР°, РіРґРµ СЃСЂРµРґРЅСЏСЏ СЂС‹РЅРѕС‡РЅР°СЏ С†РµРЅР° СѓР¶Рµ РґРѕСЃС‚Р°С‚РѕС‡РЅР° РґР»СЏ С†РµР»РµРІРѕР№ РјР°СЂР¶Рё. Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚, РЅР° СЃРєРѕР»СЊРєРѕ РїСЂРѕС†РµРЅС‚РѕРІ РІР°С€Р° С†РµРЅР° РІС‹С€Рµ РёР»Рё РЅРёР¶Рµ СЃСЂРµРґРЅРµР№ С†РµРЅС‹ СЂС‹РЅРєР°.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Р“РґРµ РЅРµР»СЊР·СЏ РґРµРјРїРёРЅРіРѕРІР°С‚СЊ", rows: tables.margin_protection || [], formatter: (row) => `Р±РµР·РѕРїР°СЃРЅРѕ РЅРµ РЅРёР¶Рµ ${formatMoney(row.min_safe_price)}, СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price)}, РїСЂРёС‡РёРЅР°: ${row.pricing_reason || "РЅ/Рґ"}`, infoText: "Р­С‚Рѕ РѕРєРЅРѕ РЅРµ РґР»СЏ С†РµРЅРѕРІРѕР№ РІРѕР№РЅС‹. Р•СЃР»Рё РІС…РѕРґРёС‚СЊ, С‚Рѕ С‚РѕР»СЊРєРѕ СЃ Р±РѕР»РµРµ СЃРёР»СЊРЅС‹Рј РѕС„С„РµСЂРѕРј РёР»Рё РёРЅРѕР№ Р·Р°РєСѓРїРєРѕР№.", getDisplayTitle, createEntityActionButtons });
}

function renderMarketingTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ РєР°СЂС‚РѕС‡РєРё", rows: tables.priority_cards || [], formatter: (row) => `${row.action_label || "РЅ/Рґ"}, score ${row.priority_score ?? "РЅ/Рґ"}, РіСЂСѓРїРїР° ${row.group || "РЅ/Рґ"} / ${row.price_band || "РЅ/Рґ"}`, infoText: "Р“Р»Р°РІРЅР°СЏ РѕС‡РµСЂРµРґСЊ РєР°СЂС‚РѕС‡РµРє, РіРґРµ СѓР¶Рµ СЃРІРµРґРµРЅС‹ price trap, title SEO Рё СЂС‹РЅРѕС‡РЅС‹Р№ pricing context.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Р“РґРµ С‚РµСЃС‚РёСЂРѕРІР°С‚СЊ С†РµРЅСѓ", rows: tables.price_traps || [], formatter: (row) => `С†РµРЅР° ${formatMoney(row.sale_price)}, РїРѕСЂРѕРі ${formatMoney(row.threshold || 0)}, РїРµСЂРµРїР»Р°С‚Р° ${row.overshoot_rub ?? "РЅ/Рґ"} в‚Ѕ`, infoText: "РљР°СЂС‚РѕС‡РєРё С‡СѓС‚СЊ РІС‹С€Рµ СЃРёР»СЊРЅС‹С… РїСЃРёС…РѕР»РѕРіРёС‡РµСЃРєРёС… РїРѕСЂРѕРіРѕРІ. Р­С‚Рѕ РґРµС€С‘РІС‹Р№ СЃР»РѕР№ Р±С‹СЃС‚СЂС‹С… С†РµРЅРѕРІС‹С… С‚РµСЃС‚РѕРІ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "Р“РґРµ РїСЂР°РІРёС‚СЊ title", rows: tables.seo_fixes || [], formatter: (row) => `SEO ${row.seo_status || "РЅ/Рґ"} / ${row.seo_score ?? "РЅ/Рґ"}, issues: ${(row.seo_issues || []).join(", ") || "РЅ/Рґ"}`, infoText: "РљР°СЂС‚РѕС‡РєРё, РіРґРµ СЃРѕРґРµСЂР¶Р°РЅРёРµ title СѓР¶Рµ РІС‹РіР»СЏРґРёС‚ СЃР»Р°Р±С‹Рј РїРѕ СЌРІСЂРёСЃС‚РёС‡РµСЃРєРѕРјСѓ SEO-Р°СѓРґРёС‚Сѓ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "РљР°СЂС‚РѕС‡РєРё СЃ СЂС‹РЅРѕС‡РЅС‹Рј РєРѕРЅС‚РµРєСЃС‚РѕРј", rows: tables.market_context || [], formatter: (row) => `pricing: ${row.pricing_label || "РЅ/Рґ"}, СЂС‹РЅРѕРє ${formatMoney(row.avg_market_price || 0)}, СЂРµРєРѕРјРµРЅРґР°С†РёСЏ ${formatMoney(row.pricing_suggested_price || row.sale_price)}`, infoText: "РљР°СЂС‚РѕС‡РєРё, РїРѕРїР°РІС€РёРµ РІ РіСЂСѓРїРїС‹ Рё РєРѕСЂРёРґРѕСЂС‹, РіРґРµ С†РµРЅРѕРІРѕР№ СЃР»РѕР№ СѓР¶Рµ РґР°С‘С‚ РїРѕРґРґРµСЂР¶РёРІР°СЋС‰РёР№ СЂС‹РЅРѕС‡РЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚.", getDisplayTitle, createEntityActionButtons });
}

function renderMediaTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ РєР°СЂС‚РѕС‡РєРё", rows: tables.priority_media || [], formatter: (row) => `media ${row.media_status || "РЅ/Рґ"} / ${row.media_score ?? "РЅ/Рґ"}, С„РѕС‚Рѕ ${row.photo_count}, spec ${row.spec_count}`, infoText: "РљР°СЂС‚РѕС‡РєРё, РіРґРµ media-layer СѓР¶Рµ РІС‹РіР»СЏРґРёС‚ СЃР»Р°Р±РµРµ РїРѕР»РµР·РЅРѕРіРѕ РјРёРЅРёРјСѓРјР° РёР»Рё СѓСЃС‚СѓРїР°РµС‚ РіСЂСѓРїРїРµ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "Р’РёР·СѓР°Р»СЊРЅС‹Рµ РѕС‚СЃС‚Р°РІР°РЅРёСЏ", rows: tables.visual_gaps || [], formatter: (row) => `РѕС‚СЃС‚Р°РІР°РЅРёРµ РїРѕ С„РѕС‚Рѕ ${row.photo_gap_vs_group ?? 0}, РїРѕ С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°Рј ${row.spec_gap_vs_group ?? 0}`, infoText: "РљР°СЂС‚РѕС‡РєРё, РіРґРµ РїСЂРѕР±Р»РµРјР° РІРёРґРЅР° РёРјРµРЅРЅРѕ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЃРІРѕРµР№ РіСЂСѓРїРїС‹, Р° РЅРµ С‚РѕР»СЊРєРѕ РїРѕ Р°Р±СЃРѕР»СЋС‚РЅРѕРјСѓ С‡РёСЃР»Сѓ С„РѕС‚Рѕ. Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚ РѕС‚СЃС‚Р°РІР°РЅРёРµ РѕС‚ С‚РёРїРёС‡РЅРѕРіРѕ СѓСЂРѕРІРЅСЏ РїРѕС…РѕР¶РёС… РєР°СЂС‚РѕС‡РµРє.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "РЎРёР»СЊРЅС‹Рµ РїСЂРёРјРµСЂС‹", rows: tables.strong_examples || [], formatter: (row) => `С„РѕС‚Рѕ ${row.photo_count}, spec ${row.spec_count}, РІРёРґРµРѕ ${row.video_count}`, infoText: "Р’РЅСѓС‚СЂРµРЅРЅРёРµ СЌС‚Р°Р»РѕРЅС‹ РїРѕ visual/content layer, РЅР° РєРѕС‚РѕСЂС‹Рµ РјРѕР¶РЅРѕ СЂР°РІРЅСЏС‚СЊСЃСЏ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "РџСѓСЃС‚С‹Рµ РјРµСЃС‚Р° РїРѕ РјРµРґРёР°", rows: (tables.priority_media || []).filter((row) => (row.photo_count || 0) < 5 || (row.spec_count || 0) < 4), formatter: (row) => `С„РѕС‚Рѕ ${row.photo_count}, spec ${row.spec_count}, СЂРµРєРѕРјРµРЅРґР°С†РёРё: ${(row.recommendations || []).join("; ") || "РЅ/Рґ"}`, infoText: "Р“РґРµ РёРјРµРЅРЅРѕ РЅРµ С…РІР°С‚Р°РµС‚ С„РѕС‚Рѕ/С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє, С‡С‚РѕР±С‹ РєР°СЂС‚РѕС‡РєР° РїРµСЂРµСЃС‚Р°Р»Р° РІС‹РіР»СЏРґРµС‚СЊ СЃР»Р°Р±РѕР№.", getDisplayTitle, createEntityActionButtons });
}

function renderDescriptionTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ РєР°СЂС‚РѕС‡РєРё", rows: tables.priority_descriptions || [], formatter: (row) => `description ${row.description_status || "РЅ/Рґ"} / ${row.description_score ?? "РЅ/Рґ"}, ${row.description_chars} СЃРёРјРІ.`, infoText: "РљР°СЂС‚РѕС‡РєРё, РіРґРµ РѕРїРёСЃР°РЅРёРµ СѓР¶Рµ РІС‹РіР»СЏРґРёС‚ СЃР»РёС€РєРѕРј СЃР»Р°Р±С‹Рј РґР»СЏ СѓРІРµСЂРµРЅРЅРѕР№ РєР°СЂС‚РѕС‡РєРё Рё Р±Р°Р·РѕРІРѕРіРѕ SEO.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "РўРѕРЅРєРёРµ РѕРїРёСЃР°РЅРёСЏ", rows: tables.thin_content || [], formatter: (row) => `${row.description_chars} СЃРёРјРІ., ${row.description_words} СЃР»РѕРІ, coverage ${row.title_term_coverage_pct ?? "РЅ/Рґ"}%`, infoText: "РљР°СЂС‚РѕС‡РєРё СЃ СЃР°РјС‹РјРё РєРѕСЂРѕС‚РєРёРјРё Рё Р±РµРґРЅС‹РјРё РѕРїРёСЃР°РЅРёСЏРјРё. Р­С‚Рѕ РїРµСЂРІС‹Р№ С„СЂРѕРЅС‚ РєРѕРЅС‚РµРЅС‚РЅРѕР№ РґРѕСЂР°Р±РѕС‚РєРё.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "РЎРёР»СЊРЅС‹Рµ РїСЂРёРјРµСЂС‹", rows: tables.strong_examples || [], formatter: (row) => `${row.description_chars} СЃРёРјРІ., coverage ${row.title_term_coverage_pct ?? "РЅ/Рґ"}%`, infoText: "Р’РЅСѓС‚СЂРµРЅРЅРёРµ СЌС‚Р°Р»РѕРЅС‹ РїРѕ РѕРїРёСЃР°РЅРёСЏРј, РѕС‚ РєРѕС‚РѕСЂС‹С… РјРѕР¶РЅРѕ РѕС‚С‚Р°Р»РєРёРІР°С‚СЊСЃСЏ РїСЂРё РїРµСЂРµРїРёСЃС‹РІР°РЅРёРё СЃР»Р°Р±С‹С… РєР°СЂС‚РѕС‡РµРє.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Р“РґРµ С‚РµРєСЃС‚ СЃР»Р°Р±РµРµ РіСЂСѓРїРїС‹", rows: (tables.priority_descriptions || []).filter((row) => (row.description_gap_vs_group || 0) >= 100), formatter: (row) => `РѕС‚СЃС‚Р°РІР°РЅРёРµ ${row.description_gap_vs_group} СЃРёРјРІ., РјРµРґРёР°РЅР° РіСЂСѓРїРїС‹ ${row.group_median_description_chars}`, infoText: "РљР°СЂС‚РѕС‡РєРё, Сѓ РєРѕС‚РѕСЂС‹С… РѕРїРёСЃР°РЅРёРµ Р·Р°РјРµС‚РЅРѕ СѓСЃС‚СѓРїР°РµС‚ РґР°Р¶Рµ РјРµРґРёР°РЅРµ СЃРІРѕРµР№ РіСЂСѓРїРїС‹ РїРѕ РѕР±СЉС‘РјСѓ. Gap Р·РґРµСЃСЊ РѕР·РЅР°С‡Р°РµС‚, СЃРєРѕР»СЊРєРѕ СЃРёРјРІРѕР»РѕРІ РЅРµ С…РІР°С‚Р°РµС‚ РґРѕ С‚РёРїРёС‡РЅРѕРіРѕ СѓСЂРѕРІРЅСЏ РіСЂСѓРїРїС‹.", getDisplayTitle, createEntityActionButtons });
}

function renderSalesReturnTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "SKU Рё РїСЂРёС‡РёРЅС‹ СЃ РјР°РєСЃРёРјР°Р»СЊРЅС‹Рј СѓС‰РµСЂР±РѕРј", rows: tables.current_winners || [], formatter: (row) => `${row.reason || "Р‘РµР· РїСЂРёС‡РёРЅС‹"} В· РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}${row.amount_value ? ` В· СЃСѓРјРјР° ${formatMoney(row.amount_value)}` : ""}`, infoText: "РќР°С‡РёРЅР°С‚СЊ РЅСѓР¶РЅРѕ СЃ С‚РµС… СЃРѕС‡РµС‚Р°РЅРёР№ SKU Рё РїСЂРёС‡РёРЅС‹, РіРґРµ РІРѕР·РІСЂР°С‚С‹ СѓР¶Рµ РєРѕРЅС†РµРЅС‚СЂРёСЂСѓСЋС‚СЃСЏ СЃРёР»СЊРЅРµРµ РІСЃРµРіРѕ. Р­С‚Рѕ СЃР°РјС‹Р№ РєРѕСЂРѕС‚РєРёР№ РїСѓС‚СЊ Рє СЃРЅРёР¶РµРЅРёСЋ РїРѕС‚РµСЂСЊ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "РџСЂРёС‡РёРЅС‹ РІРѕР·РІСЂР°С‚Р°", rows: tables.profit_leaders || [], formatter: (row) => `РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}${row.amount_value ? ` В· СЃСѓРјРјР° ${formatMoney(row.amount_value)}` : ""}`, infoText: "РђРіСЂРµРіР°С†РёСЏ РїРѕ РїСЂРёС‡РёРЅР°Рј РїРѕРєР°Р·С‹РІР°РµС‚, С‡С‚Рѕ РёРјРµРЅРЅРѕ Р»РѕРјР°РµС‚ С‚РѕРІР°СЂРЅС‹Р№ РїРѕС‚РѕРє С‡Р°С‰Рµ РІСЃРµРіРѕ: Р±СЂР°Рє, РѕРїРёСЃР°РЅРёРµ, РѕР¶РёРґР°РЅРёСЏ РїРѕРєСѓРїР°С‚РµР»СЏ РёР»Рё Р»РѕРіРёСЃС‚РёРєР°.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "РЎС‚СЂРѕРєРё Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё", rows: tables.stockout_risk || [], formatter: (row) => `${row.reason || "Р‘РµР· РїСЂРёС‡РёРЅС‹"} В· РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}`, infoText: "Р­С‚Рѕ СЃР»РѕР№, РіРґРµ РІРѕР·РІСЂР°С‚ СѓР¶Рµ РІРёРґРµРЅ, РЅРѕ РµРіРѕ РїР»РѕС…Рѕ РїРѕР»СѓС‡Р°РµС‚СЃСЏ РїСЂРёРІСЏР·Р°С‚СЊ Рє РєРѕРЅРєСЂРµС‚РЅРѕРјСѓ С‚РѕРІР°СЂСѓ. Р—РґРµСЃСЊ РЅРµР»СЊР·СЏ РѕРіСЂР°РЅРёС‡РёРІР°С‚СЊСЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёРј РІС‹РІРѕРґРѕРј, РЅСѓР¶РµРЅ СЂСѓС‡РЅРѕР№ СЂР°Р·Р±РѕСЂ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "РџРѕР»РЅС‹Р№ СЃРїРёСЃРѕРє РІРѕР·РІСЂР°С‚РѕРІ", rows: tables.stale_stock || [], formatter: (row) => `${row.reason || "Р‘РµР· РїСЂРёС‡РёРЅС‹"} В· РІРѕР·РІСЂР°С‚РѕРІ ${formatNumber(row.return_count || 0)}${row.amount_value ? ` В· СЃСѓРјРјР° ${formatMoney(row.amount_value)}` : ""}`, infoText: "РџРѕР»РЅС‹Р№ СЃРїРёСЃРѕРє СЃС‚СЂРѕРє С‚РµРєСѓС‰РµРіРѕ СЃР»РѕСЏ SalesReturn, РѕС‚СЃРѕСЂС‚РёСЂРѕРІР°РЅРЅС‹Р№ РїРѕ С‡РёСЃР»Сѓ РІРѕР·РІСЂР°С‚РѕРІ. РќСѓР¶РµРЅ РґР»СЏ С…РІРѕСЃС‚Р° Рё РїРѕРІС‚РѕСЂРЅРѕР№ РїСЂРѕРІРµСЂРєРё РїРѕСЃР»Рµ РїРµСЂРІС‹С… fixes.", getDisplayTitle, createEntityActionButtons });
}

function renderWaybillTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "РљСЂСѓРїРЅРµР№С€РёРµ batch-СЃС‚СЂРѕРєРё", rows: tables.current_winners || [], formatter: (row) => `batch ${formatMoney(row.batch_cogs_total || 0)} В· qty ${formatNumber(row.quantity_supplied || 0)} В· unit ${formatMoney(row.unit_cogs || 0)}`, infoText: "РЎР°РјС‹Рµ С‚СЏР¶С‘Р»С‹Рµ СЃС‚СЂРѕРєРё РїРѕ СЃСѓРјРјР°СЂРЅРѕР№ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё РїР°СЂС‚РёРё. РЎ РЅРёС… РЅСѓР¶РЅРѕ РЅР°С‡РёРЅР°С‚СЊ РїСЂРѕРІРµСЂРєСѓ batch-layer.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "РСЃС‚РѕСЂРёС‡РµСЃРєР°СЏ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚СЊ РїРѕ identity", rows: tables.profit_leaders || [], formatter: (row) => `latest ${formatMoney(row.gross_profit || 0)} В· avg ${formatMoney(row.profit_margin_pct || 0)}`, infoText: "РЎРІРѕРґРєР° РїРѕ РїРѕСЃР»РµРґРЅРµР№ Рё СЃСЂРµРґРЅРµР№ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё РЅР° СѓСЂРѕРІРЅРµ identity. Р­С‚Рѕ РїРµСЂРІС‹Р№ СЃР»РѕР№ Р±СѓРґСѓС‰РµРіРѕ historical COGS.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "РЎС‚СЂРѕРєРё Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё", rows: tables.stockout_risk || [], formatter: (row) => `qty ${formatNumber(row.quantity_supplied || 0)} В· unit ${formatMoney(row.unit_cogs || 0)}`, infoText: "РЎС‚СЂРѕРєРё, РіРґРµ cost РµСЃС‚СЊ, РЅРѕ РЅРѕСЂРјР°Р»СЊРЅРѕР№ РїСЂРёРІСЏР·РєРё Рє С‚РѕРІР°СЂСѓ РїРѕРєР° РЅРµС‚. РС… РЅСѓР¶РЅРѕ С‡РёРЅРёС‚СЊ СЂР°РЅСЊС€Рµ РіР»СѓР±РѕРєРѕРіРѕ Р°РЅР°Р»РёР·Р° РїСЂРёР±С‹Р»Рё.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Р’СЃРµ СЃС‚СЂРѕРєРё batch-layer", rows: tables.stale_stock || [], formatter: (row) => `qty ${formatNumber(row.quantity_supplied || 0)} В· unit ${formatMoney(row.unit_cogs || 0)} В· batch ${formatMoney(row.batch_cogs_total || 0)}`, infoText: "РџРѕР»РЅС‹Р№ СЃРїРёСЃРѕРє СЃС‚СЂРѕРє С‚РµРєСѓС‰РµР№ РЅР°РєР»Р°РґРЅРѕР№, РѕС‚СЃРѕСЂС‚РёСЂРѕРІР°РЅРЅС‹Р№ РїРѕ РѕР±СЉС‘РјСѓ Рё СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё РїР°СЂС‚РёРё.", getDisplayTitle, createEntityActionButtons });
}

function renderPaidStorageTables(payload) {
  const tables = payload.tables || {};
  renderTableCard({ root: document.getElementById("table-winners"), title: "РљСЂСѓРїРЅРµР№С€РёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ", rows: tables.current_winners || [], formatter: (row) => `${row.amount_label || "СЃСѓРјРјР°"} ${formatMoney(row.amount || 0)}${row.identity ? ` В· ${row.identity}` : ""}`, infoText: "РЎС‚СЂРѕРєРё СЃ СЃР°РјС‹Рј Р±РѕР»СЊС€РёРј РЅР°С‡РёСЃР»РµРЅРёРµРј РїРѕ РѕСЃРЅРѕРІРЅРѕР№ РґРµРЅРµР¶РЅРѕР№ РєРѕР»РѕРЅРєРµ. РЎ РЅРёС… РЅСѓР¶РЅРѕ РЅР°С‡РёРЅР°С‚СЊ СЂР°Р·Р±РѕСЂ storage/service СЃР»РѕСЏ.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-profit"), title: "РС‚РѕРіРё РїРѕ numeric-РєРѕР»РѕРЅРєР°Рј", rows: tables.profit_leaders || [], formatter: (row) => `РёС‚РѕРіРѕ ${formatMoney(row.gross_profit || 0)}, СЃСЂРµРґРЅРµРµ ${formatMoney(row.profit_margin_pct || 0)}`, infoText: "РЎСѓРјРјС‹ РїРѕ С‡РёСЃР»РѕРІС‹Рј РєРѕР»РѕРЅРєР°Рј XLSX. РќСѓР¶РЅС‹, С‡С‚РѕР±С‹ РїРѕРЅСЏС‚СЊ СЃС‚СЂСѓРєС‚СѓСЂСѓ РЅР°С‡РёСЃР»РµРЅРёР№ Рё РѕС‚РґРµР»РёС‚СЊ С…СЂР°РЅРµРЅРёРµ РѕС‚ СѓРґРµСЂР¶Р°РЅРёР№.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-risk"), title: "РЎС‚СЂРѕРєРё Р±РµР· РёРґРµРЅС‚РёС„РёРєР°С†РёРё", rows: tables.stockout_risk || [], formatter: (row) => `${row.amount_label || "СЃСѓРјРјР°"} ${formatMoney(row.amount || 0)} В· identity ${row.identity || "РЅ/Рґ"}`, infoText: "РЎР°РјС‹Р№ РїСЂРѕР±Р»РµРјРЅС‹Р№ СЃР»РѕР№ РѕР±СЉСЏСЃРЅРёРјРѕСЃС‚Рё: РЅР°С‡РёСЃР»РµРЅРёРµ РµСЃС‚СЊ, Р° РЅРѕСЂРјР°Р»СЊРЅРѕРіРѕ SKU РёР»Рё РїРѕРЅСЏС‚РЅРѕРіРѕ РЅР°Р·РІР°РЅРёСЏ РЅРµС‚.", getDisplayTitle, createEntityActionButtons });
  renderTableCard({ root: document.getElementById("table-stale"), title: "Р’СЃРµ СЃС‚СЂРѕРєРё РїР»Р°С‚РЅРѕРіРѕ СЃР»РѕСЏ", rows: tables.stale_stock || [], formatter: (row) => `${row.amount_label || "СЃСѓРјРјР°"} ${formatMoney(row.amount || 0)}${row.identity ? ` В· ${row.identity}` : ""}`, infoText: "РџРѕР»РЅС‹Р№ СЃРїРёСЃРѕРє СЃС‚СЂРѕРє РёР· С‚РµРєСѓС‰РµРіРѕ PAID_STORAGE_REPORT, РѕС‚СЃРѕСЂС‚РёСЂРѕРІР°РЅРЅС‹Р№ РїРѕ СЃСѓРјРјРµ СѓР±С‹РІР°РЅРёСЏ.", getDisplayTitle, createEntityActionButtons });
}

function reportOptionLabel(item) {
  const kind = REPORT_KIND_LABELS[item.report_kind] || item.report_kind;
  const variant = item.report_variant ? ` В· ${item.report_variant}` : "";
  const window = item.window && item.window.date_from && item.window.date_to ? ` В· ${item.window.date_from.slice(0, 10)} -> ${item.window.date_to.slice(0, 10)}` : "";
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
    ? `РћС‚РєСЂС‹С‚СЊ refresh runner Рё РІС‹РґРµР»РёС‚СЊ job: ${jobKey}`
    : "РћС‚РєСЂС‹С‚СЊ refresh runner";
  ["refresh-link-report", "refresh-link-report-top"].forEach((id) => {
    const link = document.getElementById(id);
    if (!link) return;
    link.href = jobUrl;
    link.title = jobTitle;
    link.style.display = "";
  });
  const rawPayload = await loadJson(`../data/dashboard/${item.file_name}`);
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
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ РґР»РёРЅРЅС‹С… РїРµСЂРёРѕРґРѕРІ, СЃСЂР°РІРЅРµРЅРёСЏ РіРѕРґ Рє РіРѕРґСѓ Рё РёСЃС‚РѕСЂРёРё РїРѕ РјРµСЃСЏС†Р°Рј."
    : isMarket
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ СЂС‹РЅРѕС‡РЅРѕР№ РІС‹Р±РѕСЂРєРё: РїСЂРѕРґР°РІС†С‹, РіСЂСѓРїРїС‹, С†РµРЅРѕРІС‹Рµ РєРѕСЂРёРґРѕСЂС‹ Рё РєР»Р°СЃС‚РµСЂС‹ С‚РѕРІР°СЂРЅС‹С… РёРґРµР№."
    : isPricing
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ СЂРµРєРѕРјРµРЅРґР°С†РёР№ РїРѕ С†РµРЅР°Рј РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ СЂС‹РЅРєР° Рё РІР°С€РµР№ С†РµР»РµРІРѕР№ РјР°СЂР¶Рё."
    : isMarketing
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ РјР°СЂРєРµС‚РёРЅРіРѕРІС‹Р№ Р°СѓРґРёС‚ РєР°СЂС‚РѕС‡РµРє: price traps, title SEO Рё СЂС‹РЅРѕС‡РЅС‹Р№ pricing context РІ РѕРґРЅРѕРј СЌРєСЂР°РЅРµ."
    : isMedia
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ Р°СѓРґРёС‚ С„РѕС‚Рѕ, РІРёРґРµРѕ Рё С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє РєР°СЂС‚РѕС‡РµРє СЃ РїСЂРёРІСЏР·РєРѕР№ Рє РіСЂСѓРїРїРµ Рё РїСЂРёРѕСЂРёС‚РµС‚Сѓ РґРµР№СЃС‚РІРёР№."
    : isDescription
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ Р°СѓРґРёС‚ description-layer: thin content, РїР»РѕС‚РЅРѕСЃС‚СЊ С‚РµРєСЃС‚Р° Рё СЃРІСЏР·СЊ РѕРїРёСЃР°РЅРёСЏ СЃ title."
    : isPaidStorage
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ СЂР°Р·Р±РѕСЂ РїР»Р°С‚РЅРѕРіРѕ С…СЂР°РЅРµРЅРёСЏ Рё СѓСЃР»СѓРі РёР· seller documents СЃ С„РѕРєСѓСЃРѕРј РЅР° РєСЂСѓРїРЅРµР№С€РёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ."
    : isSalesReturn
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ СЂР°Р·Р±РѕСЂ РІРѕР·РІСЂР°С‚РѕРІ Рё РїСЂРёС‡РёРЅ С‡РµСЂРµР· CubeJS / SalesReturn СЃ С„РѕРєСѓСЃРѕРј РЅР° РїРѕС‚РµСЂРё Рё explainability."
    : isWaybill
    ? "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ СЃР»РѕР№ РЅР°РєР»Р°РґРЅС‹С…: РїР°СЂС‚РёРё РїРѕСЃС‚Р°РІРєРё, batch-cost Рё Р±СѓРґСѓС‰Р°СЏ РёСЃС‚РѕСЂРёС‡РµСЃРєР°СЏ СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚СЊ РїРѕ С‚РѕРІР°СЂР°Рј."
    : "РРЅС‚РµСЂР°РєС‚РёРІРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ РѕРїРµСЂР°С†РёРѕРЅРЅС‹С… Рё РёСЃС‚РѕСЂРёС‡РµСЃРєРёС… РѕС‚С‡С‘С‚РѕРІ РёР· СЃР»РѕСЏ Р°РЅР°Р»РёС‚РёС‡РµСЃРєРёС… РґР°РЅРЅС‹С….";
  if (titleNode) {
    titleNode.textContent = REPORT_KIND_LABELS[item.report_kind] || "РћС‚С‡С‘С‚";
  }
  actionsTitle.textContent = "Р”РµР№СЃС‚РІРёСЏ";
  actionsSubtitle.textContent = isMarket
    ? "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ СЃРїРёСЃРєРё РґР»СЏ РІС‹Р±РѕСЂР° РїРѕРґРЅРёС€ Рё РѕС†РµРЅРєРё РІС…РѕРґР°."
    : isPricing
    ? "Р РµРєРѕРјРµРЅРґР°С†РёРё РїРѕ С‚РѕРјСѓ, РіРґРµ РјРѕР¶РЅРѕ РІС…РѕРґРёС‚СЊ Р°РіСЂРµСЃСЃРёРІРЅРѕ, Р° РіРґРµ РЅСѓР¶РЅРѕ Р±РµСЂРµС‡СЊ РјР°СЂР¶Сѓ."
    : isMarketing
    ? "РћС‡РµСЂРµРґРё РёСЃРїСЂР°РІР»РµРЅРёР№ РїРѕ РєР°СЂС‚РѕС‡РєР°Рј: С†РµРЅР°, title Рё manager-facing РїСЂРёРѕСЂРёС‚РµС‚."
    : isMedia
    ? "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ РѕС‡РµСЂРµРґРё РїРѕ СѓСЃРёР»РµРЅРёСЋ С„РѕС‚Рѕ, С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє Рё РІРёР·СѓР°Р»СЊРЅС‹С… РѕС‚СЃС‚Р°РІР°РЅРёР№ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РіСЂСѓРїРїС‹."
    : isDescription
    ? "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ РѕС‡РµСЂРµРґРё РїРѕ РїРµСЂРµРїРёСЃС‹РІР°РЅРёСЋ Рё СѓРїР»РѕС‚РЅРµРЅРёСЋ РѕРїРёСЃР°РЅРёР№."
    : isPaidStorage
    ? "РћС‡РµСЂРµРґРё СЂР°Р·Р±РѕСЂР° РєСЂСѓРїРЅРµР№С€РёС… РЅР°С‡РёСЃР»РµРЅРёР№ Рё СЃС‚СЂРѕРє, РєРѕС‚РѕСЂС‹Рµ РїРѕРєР° РїР»РѕС…Рѕ РёРґРµРЅС‚РёС„РёС†РёСЂСѓСЋС‚СЃСЏ."
    : isSalesReturn
    ? "РћС‡РµСЂРµРґРё СЂР°Р·Р±РѕСЂР° РїСЂРёС‡РёРЅ РІРѕР·РІСЂР°С‚Р°, С‚РѕРІР°СЂРЅС‹С… hotspot Рё СЃС‚СЂРѕРє Р±РµР· СѓРІРµСЂРµРЅРЅРѕР№ РёРґРµРЅС‚РёС„РёРєР°С†РёРё."
    : isWaybill
    ? "РћС‡РµСЂРµРґРё СЃРІРµСЂРєРё РїР°СЂС‚РёР№, РІРѕР»Р°С‚РёР»СЊРЅРѕСЃС‚Рё СЃРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё Рё РїСЂРѕР±РµР»РѕРІ identity РІ РЅР°РєР»Р°РґРЅС‹С…."
    : "РџСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ СЃРїРёСЃРєРё РґР»СЏ weekly С†РёРєР»Р°.";
  chartsTitle.textContent = isMarket ? "РЎС‚СЂСѓРєС‚СѓСЂР° Р С‹РЅРєР°" : isPricing ? "РЎС‚СЂСѓРєС‚СѓСЂР° Р¦РµРЅРѕРІС‹С… Р РµС€РµРЅРёР№" : isMarketing ? "РЎС‚СЂСѓРєС‚СѓСЂР° РњР°СЂРєРµС‚РёРЅРіРѕРІС‹С… РЎРёРіРЅР°Р»РѕРІ" : isMedia ? "РЎС‚СЂСѓРєС‚СѓСЂР° РњРµРґРёР°-РЎРёРіРЅР°Р»РѕРІ" : isDescription ? "РЎС‚СЂСѓРєС‚СѓСЂР° Description-РЎРёРіРЅР°Р»РѕРІ" : isPaidStorage ? "РЎС‚СЂСѓРєС‚СѓСЂР° РџР»Р°С‚РЅРѕРіРѕ РЎР»РѕСЏ" : isSalesReturn ? "РЎС‚СЂСѓРєС‚СѓСЂР° Р’РѕР·РІСЂР°С‚РѕРІ" : isWaybill ? "РЎС‚СЂСѓРєС‚СѓСЂР° РЎРµР±РµСЃС‚РѕРёРјРѕСЃС‚Рё РџРѕ РќР°РєР»Р°РґРЅС‹Рј" : "Р Р°СЃРїСЂРµРґРµР»РµРЅРёСЏ";
  chartsSubtitle.textContent = isMarket
    ? "Р‘С‹СЃС‚СЂС‹Р№ РІР·РіР»СЏРґ РЅР° С†РµРЅРѕРІС‹Рµ РєРѕСЂРёРґРѕСЂС‹ Рё РіСЂСѓРїРїС‹ РІ РЅР°Р±Р»СЋРґР°РµРјРѕР№ РІС‹Р±РѕСЂРєРµ."
    : isPricing
    ? "РЎРІРѕРґРєР° РїРѕ С‚РёРїР°Рј С†РµРЅРѕРІС‹С… СЂРµРєРѕРјРµРЅРґР°С†РёР№ Рё СѓСЂРѕРІРЅСЋ СЂС‹РЅРєР° РІ РѕРєРЅР°С… СЃ economics coverage."
    : isMarketing
    ? "РЎРІРѕРґРєР° РїРѕ С‚РёРїР°Рј РєР°СЂС‚РѕС‡РµС‡РЅС‹С… РїСЂРѕР±Р»РµРј Рё РѕС‡РµСЂРµРґСЏРј РёСЃРїСЂР°РІР»РµРЅРёР№."
    : isMedia
    ? "РЎРІРѕРґРєР° РїРѕ С„РѕС‚Рѕ-СЃС‚РµРєСѓ, РїР»РѕС‚РЅРѕСЃС‚Рё С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРє Рё РІРёР·СѓР°Р»СЊРЅС‹Рј РѕС‚СЃС‚Р°РІР°РЅРёСЏРј РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅРѕ РіСЂСѓРїРїС‹."
    : isDescription
    ? "РЎРІРѕРґРєР° РїРѕ РґР»РёРЅРµ РѕРїРёСЃР°РЅРёР№, thin content Рё РїРѕРєСЂС‹С‚РёСЋ title-С‚РµСЂРјРѕРІ."
    : isPaidStorage
    ? "Р‘С‹СЃС‚СЂС‹Р№ РІР·РіР»СЏРґ РЅР° РєРѕРЅС†РµРЅС‚СЂР°С†РёСЋ РЅР°С‡РёСЃР»РµРЅРёР№ Рё numeric-РєРѕР»РѕРЅРєРё, РєРѕС‚РѕСЂС‹Рµ С„РѕСЂРјРёСЂСѓСЋС‚ РїР»Р°С‚РЅС‹Р№ СЃР»РѕР№."
    : isSalesReturn
    ? "Р‘С‹СЃС‚СЂС‹Р№ РІР·РіР»СЏРґ РЅР° РґРѕРјРёРЅРёСЂСѓСЋС‰РёРµ РїСЂРёС‡РёРЅС‹ РІРѕР·РІСЂР°С‚Р° Рё РґРЅРµРІРЅСѓСЋ РґРёРЅР°РјРёРєСѓ РІРѕР·РІСЂР°С‚РѕРІ РІ РѕРєРЅРµ."
    : isWaybill
    ? "Р‘С‹СЃС‚СЂС‹Р№ РІР·РіР»СЏРґ РЅР° РєРѕРЅС†РµРЅС‚СЂР°С†РёСЋ batch-cost, РїРѕРєСЂС‹С‚РёРµ identity Рё РґР°С‚С‹ РїРѕСЃС‚Р°РІРѕРє РїРѕ РЅР°РєР»Р°РґРЅС‹Рј."
    : "Р‘С‹СЃС‚СЂС‹Р№ РІР·РіР»СЏРґ РЅР° СЃС‚СЂСѓРєС‚СѓСЂСѓ С‚РµРєСѓС‰РµРіРѕ РѕРєРЅР°.";
  insightsTitle.textContent = isCompare ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РСЃС‚РѕСЂРёРё" : isMarket ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ Р С‹РЅРєСѓ" : isPricing ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ Р¦РµРЅР°Рј" : isMarketing ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РљР°СЂС‚РѕС‡РєР°Рј" : isMedia ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РњРµРґРёР°" : isDescription ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РћРїРёСЃР°РЅРёСЏРј" : isPaidStorage ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РџР»Р°С‚РЅРѕРјСѓ РЎР»РѕСЋ" : isSalesReturn ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ Р’РѕР·РІСЂР°С‚Р°Рј" : isWaybill ? "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РќР°РєР»Р°РґРЅС‹Рј" : "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ Р’С‹РІРѕРґС‹ РџРѕ РћРєРЅСѓ";
  insightsSubtitle.textContent = isCompare
    ? "Р§С‚Рѕ СѓР¶Рµ РјРѕР¶РЅРѕ СѓС‚РІРµСЂР¶РґР°С‚СЊ РїРѕ РґР»РёРЅРЅРѕРјСѓ РїРµСЂРёРѕРґСѓ, Р° РіРґРµ РґР°РЅРЅС‹С… РµС‰С‘ РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ."
    : isMarket
    ? "РљРѕСЂРѕС‚РєРёРµ РІС‹РІРѕРґС‹ РїРѕ СЃС‚СЂСѓРєС‚СѓСЂРµ РЅР°Р±Р»СЋРґР°РµРјРѕРіРѕ СЂС‹РЅРєР°, РїСЂРѕРґР°РІС†Р°Рј Рё С†РµРЅРѕРІС‹Рј РєРѕСЂРёРґРѕСЂР°Рј."
    : isPricing
    ? "РљРѕСЂРѕС‚РєРёРµ РІС‹РІРѕРґС‹ Рѕ С‚РѕРј, РіРґРµ С†РµРЅР° СЂС‹РЅРєР° СЃРѕРІРјРµСЃС‚РёРјР° СЃ РІР°С€РµР№ СЌРєРѕРЅРѕРјРёРєРѕР№, Р° РіРґРµ РґРµРјРїРёРЅРі РѕРїР°СЃРµРЅ."
    : isMarketing
    ? "Р“РґРµ РјР°СЂРєРµС‚РёРЅРіРѕРІС‹Рµ РїСЂР°РІРєРё РїРѕ РєР°СЂС‚РѕС‡РєР°Рј РјРѕРіСѓС‚ РґР°С‚СЊ СЃР°РјС‹Р№ Р±С‹СЃС‚СЂС‹Р№ СЌС„С„РµРєС‚ Р±РµР· РЅРѕРІРѕР№ Р·Р°РєСѓРїРєРё."
    : isMedia
    ? "Р“РґРµ РєР°СЂС‚РѕС‡РєРё СѓР¶Рµ РїСЂРѕРёРіСЂС‹РІР°СЋС‚ РїРѕ С„РѕС‚Рѕ Рё С…Р°СЂР°РєС‚РµСЂРёСЃС‚РёРєР°Рј Рё С‡С‚Рѕ С‡РёРЅРёС‚СЊ СЂР°РЅСЊС€Рµ."
    : isDescription
    ? "Р“РґРµ description-layer СЃР»РёС€РєРѕРј С‚РѕРЅРєРёР№ Рё РєР°Рє РїРѕРЅРёРјР°С‚СЊ СЃРёР»Сѓ/СЃР»Р°Р±РѕСЃС‚СЊ С‚РµРєСЃС‚Р°."
    : isPaidStorage
    ? "РљР°РєРёРµ РЅР°С‡РёСЃР»РµРЅРёСЏ СѓР¶Рµ РІС‹РґРµР»СЏСЋС‚СЃСЏ, С‡С‚Рѕ РЅРµ СѓРґР°С‘С‚СЃСЏ РЅРѕСЂРјР°Р»СЊРЅРѕ СЃРѕРїРѕСЃС‚Р°РІРёС‚СЊ СЃ SKU Рё РіРґРµ РЅСѓР¶РµРЅ СЂСѓС‡РЅРѕР№ СЂР°Р·Р±РѕСЂ."
    : isSalesReturn
    ? "РљР°РєР°СЏ РїСЂРёС‡РёРЅР° РґРѕРјРёРЅРёСЂСѓРµС‚, РіРґРµ РІРѕР·РІСЂР°С‚С‹ РїР»РѕС…Рѕ РѕР±СЉСЏСЃРЅСЏСЋС‚СЃСЏ Рё РєР°РєРёРµ SKU С‚СЂРµР±СѓСЋС‚ РїРµСЂРІРѕРіРѕ СЂСѓС‡РЅРѕРіРѕ СЂР°Р·Р±РѕСЂР°."
    : isWaybill
    ? "Р“РґРµ cost-layer СѓР¶Рµ СЃРѕР±СЂР°РЅ, РєР°РєРёРµ РїР°СЂС‚РёРё СЃР°РјС‹Рµ С‚СЏР¶С‘Р»С‹Рµ Рё РіРґРµ РЅРµ С…РІР°С‚Р°РµС‚ identity РґР»СЏ РїРѕР»РЅРѕС†РµРЅРЅРѕР№ historical COGS РјРѕРґРµР»Рё."
    : "РљРѕСЂРѕС‚РєРёРµ РёРЅС‚РµСЂРїСЂРµС‚Р°С†РёРё РїРѕ Р·Р°РїР°СЃР°Рј, РїСЂРёР±С‹Р»Рё Рё СЂРёСЃРєР°Рј С‚РµРєСѓС‰РµРіРѕ РѕРєРЅР°.";
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
  tokenInput.placeholder = "Access token (РґР»СЏ РѕС‚РїСЂР°РІРєРё РѕС‚РІРµС‚РѕРІ)";
  tokenInput.style.minWidth = "300px";
  tokenInput.autocomplete = "off";
  tokenInput.addEventListener("input", () => { reviewsToken = tokenInput.value.trim(); });

  const llmInput = document.createElement("input");
  llmInput.type = "password";
  llmInput.className = "inline-input";
  llmInput.placeholder = "LLM API key (Gemini/DeepSeek вЂ” РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)";
  llmInput.style.minWidth = "260px";
  llmInput.autocomplete = "off";
  llmInput.addEventListener("input", () => { reviewsLlmKey = llmInput.value.trim(); });

  const reloadBtn = el("button", "theme-toggle compact-button", "в†» РћР±РЅРѕРІРёС‚СЊ СЃРїРёСЃРѕРє");
  reloadBtn.type = "button";
  reloadBtn.addEventListener("click", loadBuyerReviews);

  wrap.append(tokenInput, llmInput, reloadBtn);
  root.append(wrap);
}

async function loadBuyerReviews() {
  const root = document.getElementById("buyer-reviews-list");
  if (!root) return;
  root.innerHTML = "";
  try {
    const resp = await fetch("/api/reviews");
    const data = await resp.json();
    const items = data.items || [];
    if (!items.length) {
      const empty = el("p", "empty-state",
        data.status === "no_data"
          ? "РќРµС‚ РґР°РЅРЅС‹С…. Р—Р°РїСѓСЃС‚Рё job В«РћС‚Р·С‹РІС‹ Рё РІРѕРїСЂРѕСЃС‹ РїРѕРєСѓРїР°С‚РµР»РµР№В» РІ refresh runner, С‡С‚РѕР±С‹ СЃРєР°С‡Р°С‚СЊ РѕС‚Р·С‹РІС‹."
          : "РќРµС‚ РѕС‚Р·С‹РІРѕРІ РёР»Рё РІРѕРїСЂРѕСЃРѕРІ Р±РµР· РѕС‚РІРµС‚Р°.");
      root.append(empty);
      return;
    }
    const meta = el("p", "job-card-text",
      `${items.length} СЌР»РµРјРµРЅС‚РѕРІ В· РѕР±РЅРѕРІР»РµРЅРѕ ${String(data.fetched_at || "").slice(0, 19).replace("T", " ") || "РЅ/Рґ"}`);
    root.append(meta);
    items.forEach((item) => root.append(renderReviewCard(item)));
  } catch {
    root.append(el("p", "empty-state", "Refresh runner РЅРµРґРѕСЃС‚СѓРїРµРЅ. Р—Р°РїСѓСЃС‚Рё web_refresh_server.py, С‡С‚РѕР±С‹ Р·Р°РіСЂСѓР·РёС‚СЊ РѕС‚Р·С‹РІС‹."));
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
  const index = await loadDashboardIndex();
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
    document.getElementById("meta-grid").textContent = "РќРµС‚ dashboard JSON. РЎРЅР°С‡Р°Р»Р° Р·Р°РїСѓСЃС‚Рё build_dashboard_index.py.";
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

