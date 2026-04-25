#!/usr/bin/env python3
"""
Seller API client for buyer reviews and questions.

Endpoints (KazanExpress / Megamarket seller API):
  GET  /api/seller/product/reviews   — paginated list of reviews
  POST /api/seller/product/reviews/{reviewId}/answer  — post reply to a review
  GET  /api/seller/product/questions — paginated list of questions
  POST /api/seller/product/questions/{questionId}/answer — post reply to a question
"""
from core.auth import bearer_headers
from core.http_client import request_json

DEFAULT_BASE_URL = "https://api.business.kazanexpress.ru/api/seller/product"


def _headers(token):
    return bearer_headers(token)


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def fetch_reviews(session, token, page=0, size=20, status=None, base_url=DEFAULT_BASE_URL):
    """
    Fetch a page of reviews.
    status: None (all), 'WITHOUT_ANSWER', 'WITH_ANSWER'
    Returns raw API response dict.
    """
    params = {"page": page, "size": size}
    if status:
        params["status"] = status
    return request_json(
        session,
        "GET",
        f"{base_url}/reviews",
        headers=_headers(token),
        params=params,
        timeout=30,
    )


def fetch_all_reviews(session, token, status="WITHOUT_ANSWER", max_pages=10, base_url=DEFAULT_BASE_URL):
    """
    Iterate pages until empty or max_pages reached.
    Returns list of normalised review dicts.
    """
    results = []
    for page in range(max_pages):
        raw = fetch_reviews(session, token, page=page, size=20, status=status, base_url=base_url)
        rows = _extract_reviews(raw)
        if not rows:
            break
        results.extend(rows)
        total = _total_pages(raw)
        if total is not None and page + 1 >= total:
            break
    return results


def post_review_answer(session, token, review_id, text, base_url=DEFAULT_BASE_URL):
    """Post a text reply to a review. Returns raw API response."""
    return request_json(
        session,
        "POST",
        f"{base_url}/reviews/{review_id}/answer",
        headers=_headers(token),
        json_body={"text": text},
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def fetch_questions(session, token, page=0, size=20, answered=False, base_url=DEFAULT_BASE_URL):
    params = {"page": page, "size": size, "answered": str(answered).lower()}
    return request_json(
        session,
        "GET",
        f"{base_url}/questions",
        headers=_headers(token),
        params=params,
        timeout=30,
    )


def fetch_all_questions(session, token, answered=False, max_pages=10, base_url=DEFAULT_BASE_URL):
    results = []
    for page in range(max_pages):
        raw = fetch_questions(session, token, page=page, size=20, answered=answered, base_url=base_url)
        rows = _extract_questions(raw)
        if not rows:
            break
        results.extend(rows)
        total = _total_pages(raw)
        if total is not None and page + 1 >= total:
            break
    return results


def post_question_answer(session, token, question_id, text, base_url=DEFAULT_BASE_URL):
    return request_json(
        session,
        "POST",
        f"{base_url}/questions/{question_id}/answer",
        headers=_headers(token),
        json_body={"text": text},
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _total_pages(raw):
    payload = raw.get("payload") or raw
    if isinstance(payload, dict):
        return payload.get("totalPages") or payload.get("total_pages")
    return None


def _extract_reviews(raw):
    payload = raw.get("payload") or raw
    if isinstance(payload, dict):
        items = payload.get("reviews") or payload.get("content") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [_normalize_review(r) for r in items]


def _extract_questions(raw):
    payload = raw.get("payload") or raw
    if isinstance(payload, dict):
        items = payload.get("questions") or payload.get("content") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [_normalize_question(q) for q in items]


def _normalize_review(r):
    return {
        "id":          str(r.get("reviewId") or r.get("id") or ""),
        "kind":        "review",
        "product_id":  str(r.get("productId") or r.get("product_id") or ""),
        "product_title": r.get("productTitle") or r.get("product_title") or "",
        "rating":      int(r.get("rating") or 0),
        "text":        r.get("text") or r.get("comment") or "",
        "author":      r.get("authorName") or r.get("author") or "Покупатель",
        "created_at":  r.get("createdAt") or r.get("created_at") or "",
        "has_answer":  bool(r.get("hasAnswer") or r.get("has_answer") or r.get("answer")),
        "answer_text": r.get("answerText") or (r.get("answer") or {}).get("text") or "",
        "photos":      r.get("photos") or [],
        "raw":         r,
    }


def _normalize_question(q):
    return {
        "id":          str(q.get("questionId") or q.get("id") or ""),
        "kind":        "question",
        "product_id":  str(q.get("productId") or q.get("product_id") or ""),
        "product_title": q.get("productTitle") or q.get("product_title") or "",
        "rating":      None,
        "text":        q.get("text") or q.get("question") or "",
        "author":      q.get("authorName") or q.get("author") or "Покупатель",
        "created_at":  q.get("createdAt") or q.get("created_at") or "",
        "has_answer":  bool(q.get("answered") or q.get("has_answer") or q.get("answer")),
        "answer_text": q.get("answerText") or (q.get("answer") or {}).get("text") or "",
        "photos":      [],
        "raw":         q,
    }
