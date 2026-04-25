#!/usr/bin/env python3
import time

from core.auth import bearer_headers
from core.http_client import download_bytes, request_json

DEFAULT_BASE_URL = "https://api.business.kazanexpress.ru/api/seller/documents"


def seller_headers(token):
    return bearer_headers(token)


def create_request(session, token, payload, base_url=DEFAULT_BASE_URL):
    return request_json(
        session,
        "POST",
        f"{base_url}/create",
        headers=seller_headers(token),
        json_body=payload,
        timeout=30,
    )


def fetch_requests(session, token, page=0, size=20, base_url=DEFAULT_BASE_URL):
    return request_json(
        session,
        "GET",
        f"{base_url}/requests",
        headers=seller_headers(token),
        params={"page": page, "size": size},
        timeout=30,
    )


def find_request(requests_payload, request_id):
    requests_list = ((requests_payload.get("payload") or {}).get("requests") or [])
    for row in requests_list:
        if int(row.get("requestId")) == int(request_id):
            return row
    return None


def _normalize_param_value(value):
    if isinstance(value, list):
        return sorted(value)
    return value


def request_matches(row, job_type, params):
    if (row or {}).get("jobType") != job_type:
        return False
    row_params = (row or {}).get("params") or {}
    for key, value in (params or {}).items():
        if _normalize_param_value(row_params.get(key)) != _normalize_param_value(value):
            return False
    return True


def find_latest_matching_request(requests_payload, job_type, params, allowed_statuses=None):
    allowed_statuses = allowed_statuses or {"COMPLETED"}
    requests_list = ((requests_payload.get("payload") or {}).get("requests") or [])
    for row in requests_list:
        if row.get("status") in allowed_statuses and request_matches(row, job_type, params):
            return row
    return None


def wait_for_request(session, token, request_id, poll_interval=3.0, timeout_seconds=120.0, base_url=DEFAULT_BASE_URL):
    started = time.time()
    while time.time() - started <= timeout_seconds:
        requests_payload = fetch_requests(session, token, base_url=base_url)
        found = find_request(requests_payload, request_id)
        if found and found.get("status") in {"COMPLETED", "FAILED"}:
            return found
        time.sleep(poll_interval)
    raise TimeoutError(f"Timed out waiting for request {request_id}")


def download_file(session, url, output_path):
    output_path.write_bytes(download_bytes(session, url, timeout=60))
    return output_path
