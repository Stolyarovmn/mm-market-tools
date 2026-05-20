#!/usr/bin/env python3
"""
Seller product list API — per-product stats.

Endpoint:
  GET /api/seller/shop/{shop_id}/product/getProducts
  Returns productList[] with viewers, clicks, conversion, roi, quantitySold, etc.

This is the same data that powers the product cards in the seller cabinet
(Товары → карточки с «Просмотры / Конверсия / ROI»).

Fields of interest per product:
  - productId        str
  - title            str
  - viewers          int | None   — органические просмотры
  - clicks           int | None   — клики
  - conversion       float | None — конверсия просмотр→заказ, %
  - roi              float | None — ROI, %
  - quantitySold     int
  - quantityReturned int
  - returnedPercentage float
  - rating           float
  - commission       float | None
"""
import math
from core.auth import bearer_headers
from core.http_client import request_json

from core.logging_config import get_logger
log = get_logger('core.product_stats_api')

DEFAULT_BASE_URL = "https://api.business.kazanexpress.ru/api/seller"
DEFAULT_PAGE_SIZE = 50


def _headers(token):
    return bearer_headers(token)


def fetch_product_page(session, token, shop_id, *, page=0, size=DEFAULT_PAGE_SIZE,
                       filter_="all", sort_by="id", order="descending",
                       base_url=DEFAULT_BASE_URL):
    """Fetch one page of product list. Returns raw response dict."""
    return request_json(
        session,
        "GET",
        f"{base_url}/shop/{shop_id}/product/getProducts",
        headers=_headers(token),
        params={
            "searchQuery": "",
            "filter": filter_,
            "sortBy": sort_by,
            "order": order,
            "size": size,
            "page": page,
        },
        timeout=30,
    )


def fetch_all_product_stats(session, token, shop_id, *, max_pages=50,
                             base_url=DEFAULT_BASE_URL):
    """
    Iterate all pages and return list of normalised product stat dicts.
    Stops when a page returns fewer products than page_size or max_pages reached.
    """
    results = []
    size = DEFAULT_PAGE_SIZE
    for page in range(max_pages):
        raw = fetch_product_page(session, token, shop_id, page=page, size=size,
                                 base_url=base_url)
        items = raw.get("productList") or []
        if not items:
            break
        results.extend(_normalize(p) for p in items)
        total = raw.get("totalProductsAmount")
        if total is not None:
            total_pages = math.ceil(total / size)
            if page + 1 >= total_pages:
                break
        if len(items) < size:
            break
    log.info("Fetched %d products for shop %s", len(results), shop_id)
    return results


def _normalize(p):
    def _float(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    def _int(v):
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "product_id":         str(p.get("productId") or ""),
        "title":              p.get("title") or p.get("skuTitle") or "",
        "status":             p.get("status") or "",
        "rating":             _float(p.get("rating")),
        # Traffic / funnel
        "viewers":            _int(p.get("viewers")),      # просмотры
        "clicks":             _int(p.get("clicks")),       # клики
        "conversion":         _float(p.get("conversion")), # конверсия %
        # Economics
        "roi":                _float(p.get("roi")),
        "commission":         _float(p.get("commission")),
        # Sales
        "qty_sold":           _int(p.get("quantitySold")),
        "qty_returned":       _int(p.get("quantityReturned")),
        "return_pct":         _float(p.get("returnedPercentage")),
        "qty_defected":       _int(p.get("quantityDefected")),
        # Stock
        "qty_active":         _int(p.get("quantityActive")),
        "qty_fbs":            _int(p.get("quantityFbs")),
        # Meta
        "category":           p.get("category") or "",
        "price_min":          _float((p.get("price") or {}).get("min")),
        "raw":                p,
    }
