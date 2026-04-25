#!/usr/bin/env python3
import time
import uuid

import requests
from requests import HTTPError


RETRYABLE_STATUS_CODES = {403, 408, 409, 425, 429, 500, 502, 503, 504}
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_SLEEP_SECONDS = 0.5


def create_session():
    return requests.Session()


def build_mm_public_headers(device_id=None, store_code="000"):
    return {
        "x-service": "market",
        "x-device-id": device_id or str(uuid.uuid4()),
        "X-Device-Platform": "Web",
        "x-app-type": "mm",
        "X-Store-Code": store_code,
        "x-app-version": "1.0.0",
    }


def merge_headers(*header_sets):
    merged = {}
    for header_set in header_sets:
        if header_set:
            merged.update(header_set)
    return merged


def request(
    session,
    method,
    url,
    *,
    headers=None,
    params=None,
    json_body=None,
    data=None,
    timeout=DEFAULT_TIMEOUT,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
    retryable_status_codes=None,
    backoff_base=0.5,
):
    retryable_status_codes = retryable_status_codes or RETRYABLE_STATUS_CODES
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                data=data,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            last_error = exc
            if status_code not in retryable_status_codes or attempt >= max_attempts:
                raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_attempts:
                raise
        time.sleep(min(8.0, backoff_base * (2 ** (attempt - 1))))
    raise last_error


def request_json(session, method, url, **kwargs):
    response = request(session, method, url, **kwargs)
    return response.json()


def download_bytes(session, url, *, headers=None, timeout=60, max_attempts=DEFAULT_MAX_ATTEMPTS):
    response = request(
        session,
        "GET",
        url,
        headers=headers,
        timeout=timeout,
        max_attempts=max_attempts,
    )
    return response.content
