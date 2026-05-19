# core/

Library modules. Imported by `scripts/` and `web_refresh_server.py`. Never run directly.

| File | Purpose |
|------|---------|
| `paths.py` | **All path constants** — single source of truth for file locations |
| `logging_config.py` | `get_logger(__name__)` — TRACE/DEBUG/INFO/WARNING/ERROR, .env overrides |
| `refresh_jobs.py` | Maps job names → subprocess commands for `web_refresh_server.py` |
| `quick_wins_state.py` | Quick-wins state machine (pending → done → restored) |
| `action_store.py` | Action-center store: watchlist, manual tasks, queues |
| `auth.py` | JWT decode, token expiry helpers for KazanExpress API |
| `card_content.py` | Product card content fetcher (title, description, images) |
| `cubejs_api.py` | CubeJS REST query wrapper |
| `dashboard_index.py` | Builds `data/reports/dashboard/index.json` from all report JSONs |
| `dashboard_schema.py` | Schema validators for dashboard JSON |
| `dates.py` | Date utils: ISO week, period labels, range builders |
| `documents_api.py` | Seller document/report request API |
| `entity_history.py` | Per-entity time-series history builder |
| `history_metrics.py` | Historical KPI aggregation (monthly, weekly) |
| `http_client.py` | Session factory with retry + auth header injection |
| `io_utils.py` | JSON read/write helpers with atomic write |
| `market_analysis.py` | Competitor market analysis pipeline |
| `market_crosstab.py` | Cross-tabulation of market segment data |
| `market_dashboard.py` | Market dashboard JSON builder |
| `market_economics.py` | Margin/economics calculations |
| `official_reports.py` | Official seller report parser (sells, left-out CSV) |
| `operational_dashboard.py` | Weekly operational report builder |
| `product_identity.py` | SKU/product ID normalisation and deduplication |
| `reply_generator.py` | Auto-draft reply generator for buyer reviews/questions |
| `reviews_api.py` | KazanExpress buyer reviews & Q/A REST API wrapper |
| `waybill_costs.py` | Waybill/logistics cost parsing and normalisation |
| `xlsx_reader.py` | XLSX reader with sheet detection (paid storage etc.) |

## Key relationships
```
web_refresh_server.py → core/refresh_jobs.py → scripts/*.py (subprocess)
web_refresh_server.py → core/quick_wins_state.py  (/api/quick_wins/*)
web_refresh_server.py → core/reviews_api.py        (/api/reviews)
web_refresh_server.py → core/reply_generator.py    (/api/reply/*)
scripts/*.py          → core/paths.py              (all file paths)
scripts/*.py          → core/logging_config.py     (logging)
```
