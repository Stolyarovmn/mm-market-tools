# scripts/

Runnable analytics scripts. Called as subprocesses by `web_refresh_server.py`
(via `core/refresh_jobs.py`) or run manually: `python scripts/<name>.py`.

## Build — produce JSON reports → data/reports/
| File | Output |
|------|--------|
| `build_daily_action_plan.py` | Daily prioritised action plan |
| `build_dashboard_index.py` | `data/reports/dashboard/index.json` |
| `build_dynamic_pricing_report.py` | Dynamic pricing recommendations |
| `build_price_trap_report.py` | SKUs near psychological price thresholds |
| `build_quick_wins.py` | Quick-wins backlog for 15-30 min session |
| `build_paid_storage_report.py` | Paid storage cost analysis |
| `build_sales_return_report.py` | Returns analysis |
| `build_title_seo_report.py` | Title SEO quality audit |
| `build_description_seo_richness_report.py` | Description richness audit |
| `build_marketing_card_audit.py` | Card marketing quality |
| `build_media_richness_report.py` | Image/video richness |
| `build_market_margin_fit_report.py` | Margin fit vs market |
| `build_cost_coverage_backlog.py` | Cost coverage gaps |
| `build_entity_history_index.py` | Per-entity history index |
| `build_growth_plan.py` | Growth opportunity plan |
| `build_waybill_cost_layer.py` | Waybill cost layer |
| `build_zero_cogs_registry.py` | SKUs with missing COGS |

## Data collection — fetch from API → data/src/ or data/db/
| File | Source |
|------|--------|
| `weekly_operational_report.py` | Weekly sells + left-out report |
| `refresh_operational_dashboard.py` | Rebuild operational dashboard JSON |
| `fetch_buyer_reviews.py` | Buyer reviews and Q/A |
| `collect_sellers.py` | Competitor seller data |
| `get_sellers.py` | Seller list |
| `snapshot_shop.py` | Full shop snapshot |
| `request_document_report.py` | Trigger official document report |

## Analysis — read data, print insights (no output files)
| File | Purpose |
|------|---------|
| `analyze_competitor_market.py` | Competitor market analysis |
| `analyze_official_reports.py` | Official report analysis |
| `analyze_product_ideas.py` | Product opportunity ideas |
| `analyze_products.py` | Product performance analysis |
| `analyze_time_window.py` | Time window comparison |
| `analyze_variant_families.py` | Product variant family analysis |
| `ab_compare.py` | A/B test comparison |
| `compare_shops.py` | Multi-shop comparison |
| `compare_top_seller_overlaps.py` | Top seller product overlap |
| `benchmark_product_cards.py` | Card quality benchmark |
| `cubejs_meta_inspect.py` | CubeJS schema inspection |
| `cubejs_period_compare.py` | Period comparison via CubeJS |
| `cubejs_query.py` | Ad-hoc CubeJS query runner |

## Maintenance — schema, migrations, validation
| File | Purpose |
|------|---------|
| `migrate_dashboard_schema.py` | Dashboard schema migrations |
| `validate_token_integrations.py` | API token validation |
| `validate_zero_cogs_registry.py` | COGS registry validation |
| `export_cogs_fill_template.py` | Export COGS fill template |
| `ingest_cogs_fill.py` | Ingest filled COGS data |
| `rescore_market_after_cogs_fill.py` | Re-score market after COGS fill |
| `run_cogs_backfill_cycle.py` | Full COGS backfill cycle |

## Scripts (utility)
| File | Purpose |
|------|---------|
| `scripts/ingest.py` | File ingestion pipeline (CSV/XLSX detection + rebuild) |
| `inject_dashboard_data.py` | Inject test data into dashboard |

## Smoke tests — run after deploy to verify pipeline
| File | Tests |
|------|-------|
| `smoke_test_quick_wins_pipeline.py` | Quick wins build + state |
| `smoke_test_action_center_api.py` | Action center API endpoints |
| `smoke_test_ab_compare.py` | A/B compare logic |
| `smoke_test_competitor_market_extended.py` | Competitor market pipeline |
| `smoke_test_description_seo_richness_report.py` | Description SEO build |
| `smoke_test_entity_history_index.py` | Entity history build |
| `smoke_test_market_pipeline.py` | Market pipeline end-to-end |
| `smoke_test_marketing_card_audit.py` | Card audit build |
| `smoke_test_media_richness_report.py` | Media richness build |
| `smoke_test_official_pipeline.py` | Official report pipeline |
| `smoke_test_price_trap_report.py` | Price trap build |
| `smoke_test_pricing_pipeline.py` | Pricing pipeline |
| `smoke_test_quickwins_ui.py` | Quick wins UI integration |
| `smoke_test_title_seo_report.py` | Title SEO build |
| `smoke_test_waybill_cost_layer.py` | Waybill cost build |
| `smoke_test_zero_cogs_registry.py` | Zero COGS registry build |

## Entry points
`web_refresh_server.py` → `core/refresh_jobs.py` → `scripts/*.py` via subprocess.
Direct run: `python scripts/build_quick_wins.py`
