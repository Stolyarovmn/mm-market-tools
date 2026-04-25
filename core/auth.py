#!/usr/bin/env python3
import base64
import datetime as dt
import json
import os
import warnings

from zoneinfo import ZoneInfo


DEFAULT_TOKEN_ENV = "KAZANEXPRESS_TOKEN"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DEFAULT_MIN_TTL_SECONDS = 30
DEFAULT_WARN_TTL_SECONDS = 15 * 60


def get_access_token(token=None, env_var=DEFAULT_TOKEN_ENV):
    return token or os.getenv(env_var)


def token_expiry_info(token, now=None):
    payload = decode_jwt_payload(token)
    exp = payload.get("exp")
    now_dt = now or dt.datetime.now(dt.timezone.utc)
    info = {
        "has_exp": False,
        "exp": exp,
        "expires_at": None,
        "expires_at_moscow": None,
        "seconds_left": None,
        "status": "unknown",
    }
    if not isinstance(exp, (int, float)):
        return info
    expires_at = dt.datetime.fromtimestamp(exp, tz=dt.timezone.utc)
    seconds_left = int((expires_at - now_dt).total_seconds())
    info.update(
        {
            "has_exp": True,
            "expires_at": expires_at.isoformat(),
            "expires_at_moscow": expires_at.astimezone(MOSCOW_TZ).isoformat(),
            "seconds_left": seconds_left,
            "status": "expired" if seconds_left <= 0 else "valid",
        }
    )
    return info


def ensure_token_health(token, *, min_ttl_seconds=DEFAULT_MIN_TTL_SECONDS, warn_ttl_seconds=DEFAULT_WARN_TTL_SECONDS, emit_warning=True):
    info = token_expiry_info(token)
    if not info.get("has_exp"):
        return info
    seconds_left = int(info.get("seconds_left") or 0)
    if seconds_left <= 0:
        raise ValueError(
            f"Token already expired at {info.get('expires_at_moscow')}. Pass a fresh access token."
        )
    if seconds_left <= min_ttl_seconds:
        raise ValueError(
            f"Token expires too soon ({seconds_left}s left, until {info.get('expires_at_moscow')}). Pass a fresh access token before running the command."
        )
    if emit_warning and seconds_left <= warn_ttl_seconds:
        warnings.warn(
            f"Access token expires soon: {seconds_left}s left (until {info.get('expires_at_moscow')}). Long-running commands may fail before completion.",
            stacklevel=2,
        )
    return info


def require_access_token(token=None, env_var=DEFAULT_TOKEN_ENV, *, min_ttl_seconds=DEFAULT_MIN_TTL_SECONDS, warn_ttl_seconds=DEFAULT_WARN_TTL_SECONDS, emit_warning=True):
    resolved = get_access_token(token=token, env_var=env_var)
    if not resolved:
        raise ValueError(f"Missing token. Pass --token or set {env_var}.")
    ensure_token_health(
        resolved,
        min_ttl_seconds=min_ttl_seconds,
        warn_ttl_seconds=warn_ttl_seconds,
        emit_warning=emit_warning,
    )
    return resolved


def bearer_headers(token=None, env_var=DEFAULT_TOKEN_ENV, **kwargs):
    resolved = require_access_token(token=token, env_var=env_var, **kwargs)
    return {"Authorization": f"Bearer {resolved}"}


def decode_jwt_payload(token):
    if not token or token.count(".") < 2:
        return {}
    payload_segment = token.split(".")[1]
    padding = "=" * (-len(payload_segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
