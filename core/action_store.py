#!/usr/bin/env python3
import datetime as dt
import uuid

from core.dashboard_schema import ACTION_CENTER_SCHEMA_VERSION
from core.io_utils import load_json, write_json
from core.paths import ACTION_CENTER_PATH, ensure_dir


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _default_store():
    return {
        "schema_version": ACTION_CENTER_SCHEMA_VERSION,
        "updated_at": _now_iso(),
        "watchlists": [],
        "actions": [],
        "acknowledgements": [],
        "events": [],
        "saved_views": [],
    }


def load_action_store(path=ACTION_CENTER_PATH):
    ensure_dir(path.parent)
    if not path.exists():
        store = _default_store()
        write_json(path, store)
        return store
    payload = load_json(path)
    payload.setdefault("schema_version", ACTION_CENTER_SCHEMA_VERSION)
    payload.setdefault("updated_at", _now_iso())
    payload.setdefault("watchlists", [])
    payload.setdefault("actions", [])
    payload.setdefault("acknowledgements", [])
    payload.setdefault("events", [])
    payload.setdefault("saved_views", [])
    return payload


def save_action_store(store, path=ACTION_CENTER_PATH):
    ensure_dir(path.parent)
    store["schema_version"] = ACTION_CENTER_SCHEMA_VERSION
    store["updated_at"] = _now_iso()
    write_json(path, store)
    return store


def _record_event(store, event_type, payload):
    entity_key = str(payload.get("entity_key") or payload.get("title") or "").strip()
    if not entity_key:
        return
    event = {
        "id": uuid.uuid4().hex[:12],
        "event_type": event_type,
        "entity_key": entity_key,
        "title": str(payload.get("title") or entity_key).strip(),
        "entity_type": payload.get("entity_type") or "unknown",
        "report_kind": payload.get("report_kind") or "unknown",
        "context": payload.get("context") or "",
        "note": payload.get("note") or "",
        "status": payload.get("status") or "",
        "created_at": _now_iso(),
    }
    store.setdefault("events", [])
    store["events"].insert(0, event)
    store["events"] = store["events"][:500]


def add_watchlist_item(payload, path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Watchlist item requires title.")
    entity_key = str(payload.get("entity_key") or title).strip()
    existing = next((row for row in store["watchlists"] if row.get("entity_key") == entity_key), None)
    if existing:
        existing["updated_at"] = _now_iso()
        if payload.get("note"):
            existing["note"] = payload.get("note")
        if payload.get("report_kind"):
            existing["report_kind"] = payload.get("report_kind")
        if payload.get("context"):
            existing["context"] = payload.get("context")
        _record_event(store, "watchlist_updated", existing)
        save_action_store(store, path)
        return existing
    item = {
        "id": uuid.uuid4().hex[:12],
        "entity_key": entity_key,
        "title": title,
        "entity_type": payload.get("entity_type") or "unknown",
        "report_kind": payload.get("report_kind") or "unknown",
        "context": payload.get("context") or "",
        "note": payload.get("note") or "",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    store["watchlists"].insert(0, item)
    _record_event(store, "watchlist_added", item)
    save_action_store(store, path)
    return item


def add_action_item(payload, path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Action item requires title.")
    entity_key = str(payload.get("entity_key") or title).strip()
    context = payload.get("context") or ""
    note = payload.get("note") or ""
    existing = next(
        (
            row for row in store["actions"]
            if row.get("entity_key") == entity_key
            and row.get("context") == context
            and row.get("title") == title
            and row.get("status") != "done"
        ),
        None,
    )
    if existing:
        if note:
            existing["note"] = note
        existing["updated_at"] = _now_iso()
        _record_event(store, "action_updated", existing)
        save_action_store(store, path)
        return existing
    item = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "entity_key": entity_key,
        "entity_type": payload.get("entity_type") or "unknown",
        "report_kind": payload.get("report_kind") or "unknown",
        "context": context,
        "note": note,
        "owner": payload.get("owner") or "",
        "status": payload.get("status") or "open",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    store["actions"].insert(0, item)
    _record_event(store, "action_added", item)
    save_action_store(store, path)
    return item


def update_action_item(payload, path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    action_id = str(payload.get("id") or "").strip()
    if not action_id:
        raise ValueError("Action update requires id.")
    action = next((row for row in store["actions"] if row.get("id") == action_id), None)
    if not action:
        raise KeyError(f"Unknown action id: {action_id}")
    if "status" in payload:
        action["status"] = payload.get("status") or action.get("status") or "open"
    if "note" in payload:
        action["note"] = payload.get("note") or ""
    if "owner" in payload:
        action["owner"] = payload.get("owner") or ""
    action["updated_at"] = _now_iso()
    _record_event(store, "action_updated", action)
    save_action_store(store, path)
    return action


def acknowledge_entity(payload, path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    title = str(payload.get("title") or "").strip()
    entity_key = str(payload.get("entity_key") or title).strip()
    if not entity_key:
        raise ValueError("Acknowledgement requires entity_key or title.")
    existing = next((row for row in store["acknowledgements"] if row.get("entity_key") == entity_key), None)
    if existing:
        existing["title"] = title or existing.get("title") or entity_key
        existing["report_kind"] = payload.get("report_kind") or existing.get("report_kind") or "unknown"
        existing["entity_type"] = payload.get("entity_type") or existing.get("entity_type") or "unknown"
        existing["context"] = payload.get("context") or existing.get("context") or ""
        if "note" in payload:
            existing["note"] = payload.get("note") or ""
        existing["acknowledged_at"] = _now_iso()
        existing["updated_at"] = _now_iso()
        _record_event(store, "acknowledged", existing)
        save_action_store(store, path)
        return existing
    item = {
        "id": uuid.uuid4().hex[:12],
        "entity_key": entity_key,
        "title": title or entity_key,
        "entity_type": payload.get("entity_type") or "unknown",
        "report_kind": payload.get("report_kind") or "unknown",
        "context": payload.get("context") or "",
        "note": payload.get("note") or "",
        "acknowledged_at": _now_iso(),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    store["acknowledgements"].insert(0, item)
    _record_event(store, "acknowledged", item)
    save_action_store(store, path)
    return item


def toggle_action_status(action_id, path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    action = next((row for row in store["actions"] if row.get("id") == action_id), None)
    if not action:
        raise KeyError(f"Unknown action id: {action_id}")
    action["status"] = "done" if action.get("status") != "done" else "open"
    action["updated_at"] = _now_iso()
    _record_event(store, "action_toggled", action)
    save_action_store(store, path)
    return action


def add_saved_view(payload, path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    name = str(payload.get("name") or "").strip()
    filters = payload.get("filters") or {}
    if not name:
        raise ValueError("Saved view requires name.")
    existing = next((row for row in store["saved_views"] if row.get("name") == name), None)
    if existing:
        existing["filters"] = filters
        existing["updated_at"] = _now_iso()
        save_action_store(store, path)
        return existing
    item = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "filters": filters,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    store["saved_views"].insert(0, item)
    store["saved_views"] = store["saved_views"][:30]
    save_action_store(store, path)
    return item


def summarize_action_store(path=ACTION_CENTER_PATH):
    store = load_action_store(path)
    return {
        "schema_version": store.get("schema_version"),
        "updated_at": store.get("updated_at"),
        "watchlists": store.get("watchlists", []),
        "actions": store.get("actions", []),
        "acknowledgements": store.get("acknowledgements", []),
        "events": store.get("events", []),
        "saved_views": store.get("saved_views", []),
        "open_actions_count": sum(1 for row in store.get("actions", []) if row.get("status") != "done"),
        "done_actions_count": sum(1 for row in store.get("actions", []) if row.get("status") == "done"),
        "acknowledged_entities_count": len(store.get("acknowledgements", [])),
        "event_count": len(store.get("events", [])),
    }
