#!/usr/bin/env python3
from core.paths import PROJECT_ROOT, REPORTS_DIR


def _bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


JOB_DEFINITIONS = {
    "validate_token": {
        "title": "Проверка токена и интеграций",
        "mode": "online",
        "description": "Проверяет CubeJS, documents API и seller-интеграции перед большим refresh.",
        "fields": [
            {"name": "token", "label": "Access token", "type": "password", "required": True},
            {"name": "shop_id", "label": "Shop ID", "type": "number", "default": "98"},
        ],
    },
    "weekly_operational": {
        "title": "Weekly operational refresh",
        "mode": "online",
        "description": "Запрашивает official seller CSV и пересобирает weekly dashboard bundle.",
        "fields": [
            {"name": "token", "label": "Access token", "type": "password", "required": True},
            {"name": "shop_id", "label": "Shop ID", "type": "number", "default": "98"},
            {"name": "window_days", "label": "Окно, дней", "type": "number", "default": "7"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "paid_storage_report": {
        "title": "Платное хранение и услуги",
        "mode": "online",
        "description": "Берёт последний completed PAID_STORAGE_REPORT из seller documents и строит manager-facing экран затрат.",
        "fields": [
            {"name": "token", "label": "Access token", "type": "password", "required": True},
            {"name": "request_id", "label": "Request ID", "type": "number", "default": ""},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "sales_return_report": {
        "title": "Возвраты и причины",
        "mode": "online",
        "description": "Строит manager-facing экран возвратов и причин через CubeJS / SalesReturn.",
        "fields": [
            {"name": "token", "label": "Access token", "type": "password", "required": True},
            {"name": "shop_id", "label": "Shop ID", "type": "number", "default": "98"},
            {"name": "window_days", "label": "Окно, дней", "type": "number", "default": "30"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "buyer_reviews": {
        "title": "Отзывы и вопросы покупателей",
        "mode": "online",
        "description": "Скачивает отзывы и вопросы без ответа из Seller API и сохраняет в data/reviews/reviews.json.",
        "fields": [
            {"name": "token", "label": "Access token", "type": "password", "default": ""},
            {"name": "status", "label": "Фильтр статуса", "type": "text", "default": "WITHOUT_ANSWER"},
            {"name": "max_pages", "label": "Макс. страниц", "type": "number", "default": "10"},
        ],
    },
    "waybill_cost_layer": {
        "title": "Себестоимость из накладных",
        "mode": "offline",
        "description": "Загружает накладные Excel, парсит себестоимость и количество товаров, строит historical COGS snapshot.",
        "fields": [
            {"name": "waybill_xlsx", "label": "Путь к Excel накладной", "type": "text", "default": ""},
            {"name": "input_json", "label": "Или синтетический JSON", "type": "text", "default": ""},
            {"name": "sheet_name", "label": "Имя листа (опционально)", "type": "text", "default": ""},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "market_scan": {
        "title": "Market scan по категории",
        "mode": "online",
        "description": "Обходит публичный каталог MM и обновляет market/competitor bundle.",
        "fields": [
            {"name": "category_id", "label": "Category ID", "type": "number", "default": "10162"},
            {"name": "pages", "label": "Страниц", "type": "number", "default": "8"},
            {"name": "page_size", "label": "Товаров на страницу", "type": "number", "default": "50"},
            {"name": "target_margin_pct", "label": "Целевая маржа, %", "type": "number", "default": "35"},
        ],
    },
    "sellers_scan": {
        "title": "Сбор продавцов категории",
        "mode": "online",
        "description": "Долгий обход подкатегорий с checkpoint и сохранением списка продавцов.",
        "fields": [
            {"name": "category_id", "label": "Category ID", "type": "number", "default": "10162"},
            {"name": "page_size", "label": "Page size", "type": "number", "default": "50"},
            {"name": "output_path", "label": "Output JSON", "type": "text", "default": "/home/user/mm_sellers_10162.json"},
            {"name": "progress", "label": "Печатать прогресс", "type": "checkbox", "default": "true"},
        ],
    },
    "dashboard_rebuild": {
        "title": "Пересобрать index dashboard",
        "mode": "offline",
        "description": "Быстро обновляет index для browser dashboard без новых сетевых запросов.",
        "fields": [],
    },
    "cogs_backfill_cycle": {
        "title": "COGS backfill cycle",
        "mode": "offline",
        "description": "Подмешивает локальный filled COGS CSV и пересчитывает market decisions.",
        "fields": [
            {"name": "fill_csv", "label": "Путь к filled COGS CSV", "type": "text", "default": str(REPORTS_DIR / "cogs_fill_template_2026-04-09a.csv")},
            {"name": "date_tag", "label": "Date tag", "type": "text", "default": ""},
        ],
    },
    "dynamic_pricing": {
        "title": "Dynamic pricing report",
        "mode": "offline",
        "description": "Строит recommendation-first отчёт по ценам из свежего market dashboard bundle.",
        "fields": [
            {"name": "market_json", "label": "Market dashboard JSON", "type": "text", "default": str(PROJECT_ROOT / "data/dashboard/market_rescored_after_cogs_2026-04-09b.json")},
            {"name": "target_margin_pct", "label": "Целевая маржа, %", "type": "number", "default": "35"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "price_trap_audit": {
        "title": "Price trap audit",
        "mode": "offline",
        "description": "Ищет SKU чуть выше психологических ценовых порогов.",
        "fields": [
            {"name": "input_json", "label": "Normalized operational JSON", "type": "text", "default": str(PROJECT_ROOT / "data/normalized/weekly_operational_report_2026-04-08.json")},
            {"name": "max_overshoot", "label": "Макс. переплата над порогом, ₽", "type": "number", "default": "15"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "title_seo_audit": {
        "title": "Title SEO audit",
        "mode": "offline",
        "description": "Проверяет, вынесены ли важные ключевые слова в начало title.",
        "fields": [
            {"name": "input_json", "label": "Normalized operational JSON", "type": "text", "default": str(PROJECT_ROOT / "data/normalized/weekly_operational_report_2026-04-08.json")},
            {"name": "top_rows", "label": "Сколько строк анализировать", "type": "number", "default": "150"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "marketing_card_audit": {
        "title": "Marketing card audit",
        "mode": "offline",
        "description": "Собирает единый manager-facing аудит карточек: цена, psychological traps, title SEO и рыночный pricing context.",
        "fields": [
            {"name": "normalized_json", "label": "Normalized operational JSON", "type": "text", "default": str(PROJECT_ROOT / "data/normalized/weekly_operational_report_2026-04-08.json")},
            {"name": "pricing_json", "label": "Dynamic pricing JSON", "type": "text", "default": str(PROJECT_ROOT / "reports/dynamic_pricing_2026-04-10.json")},
            {"name": "price_trap_json", "label": "Price trap JSON", "type": "text", "default": str(PROJECT_ROOT / "reports/price_trap_report_2026-04-10.json")},
            {"name": "title_seo_json", "label": "Title SEO JSON", "type": "text", "default": str(PROJECT_ROOT / "reports/title_seo_report_2026-04-10.json")},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "media_richness_audit": {
        "title": "Media richness audit",
        "mode": "online",
        "description": "Проверяет фото/видео/характеристики карточек и visual gaps относительно группы.",
        "fields": [
            {"name": "input_json", "label": "Marketing card audit JSON", "type": "text", "default": str(PROJECT_ROOT / "reports/marketing_card_audit_2026-04-10.json")},
            {"name": "cache_json", "label": "Кэш product content", "type": "text", "default": str(PROJECT_ROOT / "data/local/product_content_cache.json")},
            {"name": "top_rows", "label": "Сколько карточек анализировать", "type": "number", "default": "60"},
            {"name": "cache_only", "label": "Только кэш, без сети", "type": "checkbox", "default": "false"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
    "description_seo_richness_audit": {
        "title": "Description SEO richness audit",
        "mode": "online",
        "description": "Проверяет thin content, плотность описания и связь description с title.",
        "fields": [
            {"name": "input_json", "label": "Marketing card audit JSON", "type": "text", "default": str(PROJECT_ROOT / "reports/marketing_card_audit_2026-04-10.json")},
            {"name": "cache_json", "label": "Кэш product content", "type": "text", "default": str(PROJECT_ROOT / "data/local/product_content_cache.json")},
            {"name": "top_rows", "label": "Сколько карточек анализировать", "type": "number", "default": "60"},
            {"name": "cache_only", "label": "Только кэш, без сети", "type": "checkbox", "default": "false"},
            {"name": "report_prefix", "label": "Префикс отчёта", "type": "text", "default": ""},
        ],
    },
}


def list_jobs():
    return [
        {
            "job_key": key,
            "title": spec["title"],
            "mode": spec["mode"],
            "description": spec["description"],
            "fields": spec["fields"],
        }
        for key, spec in JOB_DEFINITIONS.items()
    ]


def build_job_command(job_key, form_data):
    python = "python3"
    form_data = form_data or {}
    if job_key == "validate_token":
        return [
            python,
            str(PROJECT_ROOT / "validate_token_integrations.py"),
            "--token",
            form_data["token"],
            "--shop-id",
            str(form_data.get("shop_id") or 98),
        ]
    if job_key == "weekly_operational":
        command = [
            python,
            str(PROJECT_ROOT / "weekly_operational_report.py"),
            "--token",
            form_data["token"],
            "--shop-id",
            str(form_data.get("shop_id") or 98),
            "--window-days",
            str(form_data.get("window_days") or 7),
        ]
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "paid_storage_report":
        command = [
            python,
            str(PROJECT_ROOT / "build_paid_storage_report.py"),
            "--token",
            form_data["token"],
        ]
        if form_data.get("request_id"):
            command.extend(["--request-id", str(form_data["request_id"])])
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "sales_return_report":
        command = [
            python,
            str(PROJECT_ROOT / "build_sales_return_report.py"),
            "--token",
            form_data["token"],
            "--shop-id",
            str(form_data.get("shop_id") or 98),
            "--window-days",
            str(form_data.get("window_days") or 30),
        ]
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "buyer_reviews":
        command = [
            python,
            str(PROJECT_ROOT / "fetch_buyer_reviews.py"),
        ]
        token = form_data.get("token", "")
        if token:
            command.extend(["--token", token])
        else:
            command.append("--offline")
        if form_data.get("status"):
            command.extend(["--status", form_data["status"]])
        if form_data.get("max_pages"):
            command.extend(["--max-pages", form_data["max_pages"]])
        return command
    if job_key == "waybill_cost_layer":
        command = [
            python,
            str(PROJECT_ROOT / "build_waybill_cost_layer.py"),
        ]
        if form_data.get("waybill_xlsx"):
            command.extend(["--waybill-xlsx", form_data["waybill_xlsx"]])
        if form_data.get("input_json"):
            command.extend(["--input-json", form_data["input_json"]])
        if form_data.get("sheet_name"):
            command.extend(["--sheet-name", form_data["sheet_name"]])
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "market_scan":
        return [
            python,
            str(PROJECT_ROOT / "analyze_competitor_market.py"),
            "--category-id",
            str(form_data.get("category_id") or 10162),
            "--pages",
            str(form_data.get("pages") or 8),
            "--page-size",
            str(form_data.get("page_size") or 50),
            "--target-margin-pct",
            str(form_data.get("target_margin_pct") or 35),
        ]
    if job_key == "sellers_scan":
        command = [
            python,
            str(PROJECT_ROOT / "get_sellers.py"),
            "--category-id",
            str(form_data.get("category_id") or 10162),
            "--page-size",
            str(form_data.get("page_size") or 50),
            "--output",
            str(form_data.get("output_path") or "/home/user/mm_sellers_10162.json"),
        ]
        if _bool(form_data.get("progress", "true")):
            command.append("--progress")
        return command
    if job_key == "dashboard_rebuild":
        return [python, str(PROJECT_ROOT / "build_dashboard_index.py")]
    if job_key == "cogs_backfill_cycle":
        command = [
            python,
            str(PROJECT_ROOT / "run_cogs_backfill_cycle.py"),
            "--fill-csv",
            str(form_data.get("fill_csv") or ""),
        ]
        if form_data.get("date_tag"):
            command.extend(["--date-tag", form_data["date_tag"]])
        return command
    if job_key == "dynamic_pricing":
        command = [
            python,
            str(PROJECT_ROOT / "build_dynamic_pricing_report.py"),
            "--market-json",
            str(form_data.get("market_json") or PROJECT_ROOT / "data/dashboard/market_rescored_after_cogs_2026-04-09b.json"),
            "--target-margin-pct",
            str(form_data.get("target_margin_pct") or 35),
        ]
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "price_trap_audit":
        command = [
            python,
            str(PROJECT_ROOT / "build_price_trap_report.py"),
            "--input-json",
            str(form_data.get("input_json") or PROJECT_ROOT / "data/normalized/weekly_operational_report_2026-04-08.json"),
            "--max-overshoot",
            str(form_data.get("max_overshoot") or 15),
        ]
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "title_seo_audit":
        command = [
            python,
            str(PROJECT_ROOT / "build_title_seo_report.py"),
            "--input-json",
            str(form_data.get("input_json") or PROJECT_ROOT / "data/normalized/weekly_operational_report_2026-04-08.json"),
            "--top-rows",
            str(form_data.get("top_rows") or 150),
        ]
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "marketing_card_audit":
        command = [
            python,
            str(PROJECT_ROOT / "build_marketing_card_audit.py"),
            "--normalized-json",
            str(form_data.get("normalized_json") or PROJECT_ROOT / "data/normalized/weekly_operational_report_2026-04-08.json"),
            "--pricing-json",
            str(form_data.get("pricing_json") or PROJECT_ROOT / "reports/dynamic_pricing_2026-04-10.json"),
            "--price-trap-json",
            str(form_data.get("price_trap_json") or PROJECT_ROOT / "reports/price_trap_report_2026-04-10.json"),
            "--title-seo-json",
            str(form_data.get("title_seo_json") or PROJECT_ROOT / "reports/title_seo_report_2026-04-10.json"),
        ]
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "media_richness_audit":
        command = [
            python,
            str(PROJECT_ROOT / "build_media_richness_report.py"),
            "--input-json",
            str(form_data.get("input_json") or PROJECT_ROOT / "reports/marketing_card_audit_2026-04-10.json"),
            "--cache-json",
            str(form_data.get("cache_json") or PROJECT_ROOT / "data/local/product_content_cache.json"),
            "--top-rows",
            str(form_data.get("top_rows") or 60),
        ]
        if _bool(form_data.get("cache_only", "false")):
            command.append("--cache-only")
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    if job_key == "description_seo_richness_audit":
        command = [
            python,
            str(PROJECT_ROOT / "build_description_seo_richness_report.py"),
            "--input-json",
            str(form_data.get("input_json") or PROJECT_ROOT / "reports/marketing_card_audit_2026-04-10.json"),
            "--cache-json",
            str(form_data.get("cache_json") or PROJECT_ROOT / "data/local/product_content_cache.json"),
            "--top-rows",
            str(form_data.get("top_rows") or 60),
        ]
        if _bool(form_data.get("cache_only", "false")):
            command.append("--cache-only")
        if form_data.get("report_prefix"):
            command.extend(["--report-prefix", form_data["report_prefix"]])
        return command
    raise KeyError(f"Unknown job: {job_key}")


def sanitize_payload(job_key, form_data):
    safe = {}
    for field in JOB_DEFINITIONS[job_key]["fields"]:
        name = field["name"]
        if name not in form_data:
            continue
        safe[name] = "***redacted***" if name == "token" else form_data[name]
    return safe
