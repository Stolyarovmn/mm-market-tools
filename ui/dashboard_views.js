export const REPORT_KIND_LABELS = {
  weekly_operational: "Операционный отчёт",
  official_period_analysis: "Официальный анализ",
  cubejs_period_compare: "Сравнение периодов",
  competitor_market_analysis: "Рынок и конкуренты",
  dynamic_pricing: "Рекомендации по ценам",
  marketing_card_audit: "Маркетинг карточек",
  media_richness_report: "Медиа карточек",
  description_seo_report: "Описание карточек",
  paid_storage_report: "Платное хранение",
  sales_return_report: "Возвраты и причины",
  waybill_cost_layer: "Накладные и себестоимость",
};

export const REPORT_KIND_ORDER = [
  "weekly_operational",
  "official_period_analysis",
  "cubejs_period_compare",
  "competitor_market_analysis",
  "dynamic_pricing",
  "marketing_card_audit",
  "media_richness_report",
  "description_seo_report",
  "paid_storage_report",
  "sales_return_report",
  "waybill_cost_layer",
];

export function buildOperationalInsights(payload, helpers) {
  const { formatMoney, formatNumber, formatPercent } = helpers;
  const kpis = payload.kpis || {};
  const actions = payload.actions || {};
  const tables = payload.tables || {};
  const familyTables = payload.family_tables || {};
  const insights = [];
  const reorderCount = (actions.reorder_now || []).length;
  const markdownCount = (actions.markdown_candidates || []).length;
  const protectCount = (actions.protect_winners || []).length;
  const watchlistCount = (actions.watchlist_signals || []).length;
  const familyCount = kpis.family_count || 0;
  const multiVariantFamilyCount = kpis.multi_variant_family_count || 0;
  const winnerCount = (tables.current_winners || []).length;
  const softSignalCount = (tables.soft_signal_products || []).length;
  const familyWinnerCount = (familyTables.family_current_winners || []).length;
  const familySoftCount = (familyTables.family_soft_signal_products || []).length;

  if (reorderCount > 0) {
    insights.push({
      title: "Есть позиции на немедленную дозакупку",
      text: `В actionable-слое ${formatNumber(reorderCount)} SKU уже проходят жёсткий порог на дозакупку. Это приоритет выше любых общих гипотез по ассортименту.`,
      tone: "good",
    });
  } else if ((kpis.stockout_risk_count || 0) > 0) {
    insights.push({
      title: "Риск нехватки есть, но сигнал пока мягкий",
      text: `В окне видно ${formatNumber(kpis.stockout_risk_count)} SKU с риском out-of-stock, но жёсткий порог на дозакупку пока никто не прошёл. Это зона ручной проверки, а не автоматического заказа.`,
      tone: "warn",
    });
  }

  if ((kpis.stale_stock_count || 0) > 300) {
    insights.push({
      title: "Склад перегружен медленным товаром",
      text: `Без движения лежат ${formatNumber(kpis.stale_stock_count)} SKU. Это повод пересмотреть хвост ассортимента и уценку части позиций.`,
      tone: "warn",
    });
  }

  if (winnerCount > 0) {
    insights.push({
      title: "В окне уже есть подтверждённые победители",
      text: `Жёсткий winner-порог проходят ${formatNumber(winnerCount)} SKU. Это те позиции, где есть смысл защищать наличие, цену и карточку в первую очередь.`,
      tone: "good",
    });
  } else if (softSignalCount > 0) {
    insights.push({
      title: "Пока видны только ранние сигналы спроса",
      text: `Строгих winners в окне нет, но ${formatNumber(softSignalCount)} SKU уже дают живой сигнал. Их нужно смотреть вручную вместе с остатком, динамикой и качеством карточки.`,
      tone: "warn",
    });
  }

  if ((kpis.gross_profit_total || 0) > 0 && (kpis.revenue_total || 0) > 0 && (kpis.sold_skus || 0) > 0) {
    const margin = (kpis.gross_profit_total / kpis.revenue_total) * 100;
    insights.push({
      title: "Окно уже пригодно для оценки unit economics",
      text: `В текущем окне выручка ${formatMoney(kpis.revenue_total)}, валовая прибыль ${formatMoney(kpis.gross_profit_total)}, ориентир по валовой марже около ${formatPercent(Number(margin.toFixed(1)))}.`,
      tone: margin >= 40 ? "good" : "warn",
    });
  }

  if (multiVariantFamilyCount > 0) {
    insights.push({
      title: "Есть карточки, где смотреть нужно на семейство, а не на одну строку",
      text: `В окне видно ${formatNumber(familyCount)} семейств товаров, из них ${formatNumber(multiVariantFamilyCount)} содержат несколько вариантов или ШК. ${familyWinnerCount > 0 ? `На уровне семейств уже есть ${formatNumber(familyWinnerCount)} подтверждённых сигналов.` : familySoftCount > 0 ? `На уровне семейств пока преобладают ранние сигналы: ${formatNumber(familySoftCount)} семейств.` : "Для таких карточек решения по закупке лучше принимать на уровне семейства, а не одной строки CSV."}`,
      tone: "good",
    });
  }

  insights.push({
    title: "Что делать дальше",
    text: `Сейчас в actionable-слое ${formatNumber(reorderCount)} позиций на дозакупку, ${formatNumber(markdownCount)} кандидатов на уценку, ${formatNumber(protectCount)} позиций под защиту и ${formatNumber(watchlistCount)} сигналов на ручной контроль.`,
    tone: reorderCount > 0 || protectCount > 0 ? "good" : "warn",
  });

  return insights;
}

export function buildCubejsInsights(rawPayload, helpers) {
  const { formatMoney, formatNumber } = helpers;
  const periods = rawPayload.periods || {};
  const historyWindow = rawPayload.history_window || {};
  const current = periods.current_trailing_year || {};
  const currentMetrics = current.metrics || {};
  const previous = periods.previous_year_same_window || {};
  const previousMetrics = previous.metrics || {};
  const threeYear = periods.three_year_same_window || {};
  const previousYtd = periods.previous_ytd || {};
  const series = rawPayload.series_monthly || [];
  const insights = [];

  insights.push({
    title: "Текущая база уже видна",
    text: `За последние 365 дней в CubeJS видно ${formatMoney(currentMetrics.revenue_total || 0)} выручки, ${formatNumber(currentMetrics.orders_total || 0)} заказов и ${formatNumber(currentMetrics.items_sold_total || 0)} проданных единиц.`,
    tone: "good",
  });

  const hasPreviousYear = (previousMetrics.revenue_total || 0) > 0 || (previousMetrics.orders_total || 0) > 0 || (previousMetrics.items_sold_total || 0) > 0;
  if (!hasPreviousYear) {
    insights.push({
      title: "Год к году пока нельзя считать надёжно",
      text: "Референсное окно прошлого года в текущем CubeJS-слое пустое, поэтому YoY сейчас нужно читать как отсутствие данных, а не как реальное падение или рост.",
      tone: "warn",
    });
  }

  const hasThreeYear = (((threeYear.metrics || {}).revenue_total || 0) > 0);
  if (!hasThreeYear) {
    insights.push({
      title: "Сравнение с базой 3 года назад ограничено",
      text: "Запрос уходит на глубину 3 лет, но фактическая наполняемость по более старым окнам пока нулевая. Это инфраструктурно готово, но аналитически ещё не зрелое сравнение.",
      tone: "warn",
    });
  }

  if ((historyWindow.history_years || 0) >= 3) {
    insights.push({
      title: "История уже собирается длинным окном",
      text: `Long-range слой запрашивает историю с ${historyWindow.date_from || "н/д"} по ${historyWindow.date_to || "н/д"}, а monthly series уже можно использовать как базу для накопления настоящего time-series анализа.`,
      tone: "good",
    });
  }

  if (series.length < 12) {
    insights.push({
      title: "Месячная история ещё короткая",
      text: `В monthly series сейчас ${formatNumber(series.length)} заполненных месяцев. Для зрелого seasonal и YoY-анализа лучше накопить минимум 12–18 месяцев ненулевых значений.`,
      tone: "warn",
    });
  }

  const previousYtdMetrics = previousYtd.metrics || {};
  if ((previousYtdMetrics.revenue_total || 0) === 0) {
    insights.push({
      title: "С начала года сравнение пока одностороннее",
      text: "Current YTD уже виден, но previous YTD пустой. Значит слой полезен для накопления истории уже сейчас, но не для окончательных выводов о динамике к прошлому году.",
      tone: "bad",
    });
  }

  return insights;
}

export function buildPricingInsights(payload, helpers) {
  const { formatNumber, formatMoney } = helpers;
  const kpis = payload.kpis || {};
  const actions = payload.actions || {};
  const metadata = payload.metadata || {};
  const targetMargin = metadata.pricing?.target_margin_pct ?? kpis.target_margin_pct;
  const insights = [];

  if ((actions.aggressive_price || []).length > 0) {
    insights.push({
      title: "Есть окна для агрессивного входа",
      text: `Нашлось ${formatNumber((actions.aggressive_price || []).length)} ценовых окон, где можно держаться чуть ниже рынка и всё ещё сохранять целевую маржу ${targetMargin ?? "н/д"}%.`,
      tone: "good",
    });
  }

  if ((actions.price_at_market || []).length > 0) {
    insights.push({
      title: "Часть окон уже совместима с ценой рынка",
      text: `В ${formatNumber((actions.price_at_market || []).length)} окнах средняя рыночная цена уже бьётся с вашей экономикой. Это хорошие кандидаты на быстрый тест без сложного позиционирования.`,
      tone: "good",
    });
  }

  if ((actions.test_carefully || []).length > 0) {
    insights.push({
      title: "Есть окна только для осторожного теста",
      text: `${formatNumber((actions.test_carefully || []).length)} окон требуют аккуратной цены выше среднего рынка или более сильного оффера, иначе маржа станет слишком тонкой.`,
      tone: "warn",
    });
  }

  if ((actions.protect_margin || []).length > 0) {
    const top = (actions.protect_margin || [])[0];
    insights.push({
      title: "Где нельзя демпинговать",
      text: `В ряде окон минимальная безопасная цена выше рынка. Например, ${top.group || "н/д"} / ${top.price_band || "н/д"} требует не меньше ${formatMoney(top.min_safe_price || 0)}, иначе целевая маржа не выдерживается.`,
      tone: "bad",
    });
  }

  insights.push({
    title: "Как читать этот экран",
    text: "Это recommendation-first слой. Он не меняет цены автоматически, а показывает, где можно входить агрессивно, где держаться рынка, где тестировать осторожно и где демпинг уже разрушает экономику.",
    tone: "neutral",
  });

  return insights;
}

export function buildMarketingInsights(payload, helpers) {
  const { formatNumber } = helpers;
  const kpis = payload.kpis || {};
  const actions = payload.actions || {};
  const insights = [];

  if ((kpis.double_fix_count || 0) > 0) {
    insights.push({
      title: "Есть карточки с двойной проблемой",
      text: `В ${formatNumber(kpis.double_fix_count)} карточках одновременно видны слабый title и ценовой trap. Это лучший список для быстрых изменений без смены ассортимента.`,
      tone: "warn",
    });
  }
  if ((kpis.price_trap_cards_count || 0) > 0) {
    insights.push({
      title: "Пороговые цены уже дают быстрые тесты",
      text: `${formatNumber(kpis.price_trap_cards_count)} карточек стоят чуть выше сильных психологических порогов. Это дешёвый тест по сравнению с новой закупкой.`,
      tone: "good",
    });
  }
  if ((kpis.seo_needs_work_count || 0) > 0) {
    insights.push({
      title: "Title-слой тоже даёт фронт работ",
      text: `${formatNumber(kpis.seo_needs_work_count)} карточек требуют улучшения title. Это content-резерв, который можно разбирать параллельно с ценовыми тестами.`,
      tone: "warn",
    });
  }
  if ((actions.market_supported || []).length > 0) {
    insights.push({
      title: "Часть карточек лежит в рабочих рыночных окнах",
      text: `${formatNumber((actions.market_supported || []).length)} карточек уже попали в подниши, где pricing-layer поддерживает тест или вход. Их стоит смотреть раньше случайных гипотез.`,
      tone: "good",
    });
  }
  return insights;
}

export function buildPaidStorageInsights(payload, helpers) {
  const { formatMoney, formatNumber } = helpers;
  const kpis = payload.kpis || {};
  const insights = [];
  insights.push({
    title: "Платный storage/service слой теперь виден",
    text: `В текущем отчёте ${formatNumber(kpis.storage_rows_count || kpis.total_skus || 0)} строк и суммарно ${formatMoney(kpis.total_amount || kpis.revenue_total || 0)} начислений.`,
    tone: "good",
  });
  if ((kpis.rows_without_identity_count || 0) > 0) {
    insights.push({
      title: "Часть начислений требует ручной сверки",
      text: `${formatNumber(kpis.rows_without_identity_count)} строк не имеют явного SKU или понятной идентификации. Это риск потери объяснимости затрат.`,
      tone: "warn",
    });
  }
  if ((kpis.penalty_total || 0) > 0) {
    insights.push({
      title: "Есть слой удержаний / штрафов",
      text: `По numeric-колонкам найдено около ${formatMoney(kpis.penalty_total || 0)} удержаний. Их нужно отделять от регулярного хранения.`,
      tone: "warn",
    });
  }
  insights.push({
    title: "Как читать этот экран",
    text: "Сначала смотри крупнейшие начисления, затем строки без идентификации и только потом уходи в расшифровку колонок. Это экран затрат, а не оборота.",
    tone: "neutral",
  });
  return insights;
}

export function buildMediaInsights(payload, helpers) {
  const { formatNumber } = helpers;
  const kpis = payload.kpis || {};
  const insights = [];
  if ((kpis.priority_cards_count || 0) > 0) {
    insights.push({
      title: "Есть карточки с явным визуальным отставанием",
      text: `${formatNumber(kpis.priority_cards_count)} карточек уже выглядят как кандидаты на срочное усиление фото-стека или характеристик. Gap здесь означает отставание от типичного уровня похожих карточек, а не просто маленькое абсолютное число фото.`,
      tone: "warn",
    });
  }
  if ((kpis.photo_gap_count || 0) > 0) {
    insights.push({
      title: "Отставание видно не только по абсолютным числам",
      text: `У ${formatNumber(kpis.photo_gap_count)} карточек фото-стек слабее медианы своей группы. Gap здесь означает, сколько фото не хватает до типичного уровня похожих товаров.`,
      tone: "warn",
    });
  }
  if ((kpis.with_video_count || 0) > 0) {
    insights.push({
      title: "Видео есть, но это не первый приоритет",
      text: `Видео найдено у ${formatNumber(kpis.with_video_count)} карточек. В toy-категориях чаще выгоднее сначала добить фото и характеристики, а потом уже думать о видео.`,
      tone: "good",
    });
  }
  return insights;
}

export function buildWaybillInsights(payload, helpers) {
  const { formatMoney, formatNumber } = helpers;
  const kpis = payload.kpis || {};
  const insights = [];
  insights.push({
    title: "Слой накладных и batch-cost уже собран",
    text: `В текущем слое ${formatNumber(kpis.waybill_rows_count || 0)} строк накладных, ${formatNumber(kpis.historical_cogs_items_count || 0)} identity с историей себестоимости и суммарный batch-cost ${formatMoney(kpis.total_amount || 0)}.`,
    tone: "good",
  });
  if ((kpis.rows_without_identity_count || 0) > 0) {
    insights.push({
      title: "Часть строк пока нельзя надёжно привязать к товару",
      text: `${formatNumber(kpis.rows_without_identity_count || 0)} строк не имеют достаточной identity-связки. Их нужно добивать через barcode / sku, иначе historical COGS останется дырявым.`,
      tone: "warn",
    });
  }
  insights.push({
    title: "Как читать этот экран",
    text: "Сначала смотри последние и самые дорогие партии, затем волатильность себестоимости по одному identity и только потом разбирай хвост строк. Это cost-layer, а не слой продаж.",
    tone: "neutral",
  });
  return insights;
}

export function buildDescriptionInsights(payload, helpers) {
  const { formatNumber } = helpers;
  const kpis = payload.kpis || {};
  const insights = [];
  if ((kpis.thin_content_count || 0) > 0) {
    insights.push({
      title: "Есть карточки с реально тонким описанием",
      text: `В ${formatNumber(kpis.thin_content_count)} карточках описание слишком короткое, чтобы нормально раскрывать пользу товара и поддерживать SEO слоя поиска.`,
      tone: "warn",
    });
  }
  if ((kpis.description_gap_count || 0) > 0) {
    insights.push({
      title: "Часть карточек слабее группы по описанию",
      text: `${formatNumber(kpis.description_gap_count)} карточек отстают от медианы своей группы по плотности description-layer. Gap здесь означает разницу между текущим описанием и типичным объёмом текста у похожих карточек.`,
      tone: "warn",
    });
  }
  if ((kpis.priority_cards_count || 0) > 0) {
    insights.push({
      title: "Есть карточки для быстрого content-фронта",
      text: `${formatNumber(kpis.priority_cards_count)} карточек уже выглядят как прямые кандидаты на переписывание описания.`,
      tone: "good",
    });
  }
  return insights;
}

export function normalizeCubejsComparePayload(payload) {
  const periods = payload.periods || {};
  const current = periods.current_trailing_year || {};
  const metrics = current.metrics || {};
  const previous = periods.previous_year_same_window || {};
  const threeYear = periods.three_year_same_window || {};
  const monthly = payload.series_monthly || [];
  return {
    metadata: {
      window: {
        date_from: current.date_from,
        date_to: current.date_to,
        window_days: 365,
      },
      documents: {
        sells_mode: "CubeJS",
        left_out_mode: "CubeJS",
        sells_request_id: "н/д",
        left_out_request_id: "н/д",
      },
    },
    kpis: {
      total_skus: 0,
      sold_skus: metrics.items_sold_total || 0,
      revenue_total: metrics.revenue_total || 0,
      gross_profit_total: 0,
      stockout_risk_count: 0,
      stale_stock_count: 0,
    },
    actions: {
      reorder_now: [],
      markdown_candidates: [],
      protect_winners: [
        {
          title: "YoY revenue delta",
          gross_profit: 0,
          units_sold: previous.delta_vs_current?.revenue_total_pct ?? 0,
        },
        {
          title: "3Y revenue delta",
          gross_profit: 0,
          units_sold: threeYear.delta_vs_current?.revenue_total_pct ?? 0,
        },
      ],
    },
    tables: {
      current_winners: [
        {
          title: "Выручка за 365 дней",
          units_sold: metrics.items_sold_total || 0,
          net_revenue: metrics.revenue_total || 0,
          abc_revenue: "н/д",
        },
        {
          title: "Заказы за 365 дней",
          units_sold: metrics.orders_total || 0,
          net_revenue: 0,
          abc_revenue: "н/д",
        },
      ],
      profit_leaders: [],
      stockout_risk: [],
      stale_stock: [],
    },
    charts: {
      abc_revenue_counts: [],
      abc_profit_counts: [],
      status_counts: [],
      revenue_by_abc: (monthly || []).map((row) => ({
        key: (row["Sales.created_at.month"] || "").slice(0, 7),
        value: Number(row["Sales.seller_revenue_without_delivery_measure"] || 0),
      })),
    },
  };
}


export function buildSalesReturnInsights(payload, helpers) {
  const { formatNumber, formatPercent } = helpers;
  const kpis = payload.kpis || {};
  const insights = [];
  insights.push({
    title: "Возвраты вынесены в отдельный управленческий слой",
    text: `В текущем окне найдено ${formatNumber(kpis.total_returns_count || 0)} возвратов и ${formatNumber(kpis.unique_return_reasons_count || 0)} причин. Это отдельный экран, который нужен не для выручки, а для разборов потерь и качества оффера.`,
    tone: "warn",
  });
  if ((kpis.top_reason_share_pct || 0) > 40) {
    insights.push({
      title: "Одна причина уже доминирует",
      text: `Главная причина даёт около ${formatPercent(kpis.top_reason_share_pct || 0)} всех возвратов. Значит сначала нужно разбирать не весь хвост, а именно этот узкий сценарий.`,
      tone: "warn",
    });
  }
  if ((kpis.rows_without_reason_count || 0) > 0) {
    insights.push({
      title: "Часть возвратов плохо объясняется",
      text: `${formatNumber(kpis.rows_without_reason_count || 0)} строк пришли без явной причины возврата. Это снижает объяснимость отчёта и требует ручной сверки по карточкам.`,
      tone: "warn",
    });
  }
  if ((kpis.rows_without_identity_count || 0) > 0) {
    insights.push({
      title: "Есть строки без уверенной привязки к SKU",
      text: `${formatNumber(kpis.rows_without_identity_count || 0)} строк не содержат надёжной идентификации товара. Их нужно смотреть отдельно, иначе разбор причин возврата будет неполным.`,
      tone: "bad",
    });
  }
  return insights;
}
