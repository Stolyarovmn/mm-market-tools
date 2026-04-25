#!/usr/bin/env python3
import json

from core.auth import bearer_headers
from core.http_client import create_session, request_json


DEFAULT_BASE_URL = "https://seller-analytics.mm.ru/cubejs-api/v1/load"
DEFAULT_META_URL = "https://seller-analytics.mm.ru/cubejs-api/v1/meta"


def build_headers(token=None, cookie=None):
    headers = {}
    if token:
        headers.update(bearer_headers(token))
    if cookie:
        headers["Cookie"] = cookie
    return headers


def run_cubejs_query(query, token=None, cookie=None, base_url=DEFAULT_BASE_URL, timeout=30):
    with create_session() as session:
        return request_json(
            session,
            "GET",
            base_url,
            headers=build_headers(token, cookie),
            params={"query": json.dumps(query, ensure_ascii=False), "queryType": "multi"},
            timeout=timeout,
        )


def fetch_cubejs_meta(token=None, cookie=None, meta_url=DEFAULT_META_URL, timeout=30):
    with create_session() as session:
        return request_json(
            session,
            "GET",
            meta_url,
            headers=build_headers(token, cookie),
            timeout=timeout,
        )


def flatten_results(payload):
    if isinstance(payload, dict) and "results" in payload:
        rows = []
        for item in payload.get("results") or []:
            rows.extend(item.get("data") or [])
        return rows
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data") or []
    return []
