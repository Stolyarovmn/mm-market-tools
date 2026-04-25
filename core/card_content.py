#!/usr/bin/env python3
import datetime as dt
import html
import re
from pathlib import Path

from core.http_client import build_mm_public_headers, request_json
from core.io_utils import load_json, write_json


KE_PRODUCT_URL = "https://api.kazanexpress.ru/api/v2/product/{product_id}"


def strip_html(raw_html):
    cleaned = re.sub(r"<[^>]+>", " ", raw_html or "")
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def load_content_cache(path):
    path = Path(path)
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def save_content_cache(path, cache):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, cache)


def fetch_public_product(session, product_id, *, device_id="mm-market-tools-content-audit"):
    data = request_json(
        session,
        "GET",
        KE_PRODUCT_URL.format(product_id=product_id),
        headers=build_mm_public_headers(device_id=device_id),
        timeout=20,
    )
    return ((data or {}).get("payload") or {}).get("data") or {}


def get_cached_or_fetch_public_product(session, product_id, cache, *, cache_only=False, device_id="mm-market-tools-content-audit"):
    cache_key = str(product_id)
    cached = cache.get(cache_key)
    if cached and isinstance(cached, dict) and cached.get("product"):
        return cached["product"], True
    if cache_only:
        return None, False
    product = fetch_public_product(session, product_id, device_id=device_id)
    cache[cache_key] = {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "product": product,
    }
    return product, False


def content_metrics(public_product):
    description_text = strip_html(public_product.get("description", ""))
    photos = public_product.get("photos") or []
    attrs = public_product.get("attributes") or []
    chars = public_product.get("characteristics") or []
    videos = (
        public_product.get("videos")
        or public_product.get("video")
        or public_product.get("videoUrls")
        or public_product.get("videoUrlsList")
        or []
    )
    if isinstance(videos, dict):
        videos = [videos]
    if isinstance(videos, str):
        videos = [videos]
    specs_count = len(attrs) + len(chars)
    return {
        "title": public_product.get("title") or "",
        "description_text": description_text,
        "description_chars": len(description_text),
        "description_words": len(description_text.split()),
        "photo_count": len(photos),
        "attribute_count": len(attrs),
        "characteristic_count": len(chars),
        "spec_count": specs_count,
        "video_count": len(videos),
        "photos": photos,
        "attributes": attrs,
        "characteristics": chars,
        "videos": videos,
    }
