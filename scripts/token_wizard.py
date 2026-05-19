#!/usr/bin/env python3
"""MM Market Tools — Token Wizard

Prompts user to paste a fresh MM session token (JWT, ~5 min TTL).
Does NOT save to .env — token is written to .token_session for the
current run_daily.bat session only, then deleted by the bat file.

Usage (from run_daily.bat):
    py -3 scripts/token_wizard.py
    if errorlevel 2 (set SKIP_API=1) else (set /p KE_TOKEN=< .token_session & del .token_session)

Exit codes:
  0 — token valid, written to .token_session
  2 — user skipped; bat sets SKIP_API=1 and continues without API steps
"""
import base64
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from core.logging_config import get_logger
log = get_logger('scripts.token_wizard')

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / ".token_session"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ── JWT helpers ───────────────────────────────────────────────────────────────

def decode_jwt(token: str) -> dict:
    if not token or token.count(".") < 2:
        return {}
    seg = token.split(".")[1]
    seg += "=" * (-len(seg) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(seg).decode("utf-8"))
    except Exception:
        return {}


def token_info(token: str) -> dict:
    payload = decode_jwt(token)
    exp = payload.get("exp")
    now = dt.datetime.now(dt.timezone.utc)
    if not isinstance(exp, (int, float)):
        return {"status": "no_exp", "seconds_left": None, "expires_msk": None}
    expires_utc = dt.datetime.fromtimestamp(exp, tz=dt.timezone.utc)
    seconds_left = int((expires_utc - now).total_seconds())
    expires_msk = expires_utc.astimezone(MOSCOW_TZ).strftime("%d.%m %H:%M:%S МСК")
    if seconds_left <= 0:
        return {"status": "expired", "seconds_left": seconds_left, "expires_msk": expires_msk}
    return {"status": "valid", "seconds_left": seconds_left, "expires_msk": expires_msk}


def fmt_ttl(seconds: int) -> str:
    if seconds <= 0:
        return "истёк"
    h, m = divmod(seconds // 60, 60)
    s = seconds % 60
    if h:
        return f"{h}ч {m}м {s}с"
    if m:
        return f"{m}м {s}с"
    return f"{s}с"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("  Токен ММ живёт ~5 минут — нужен свежий для каждого запуска.")
    print()
    print("  Как получить токен:")
    print("  1. Открой https://seller-analytics.mm.ru и войди в аккаунт")
    print("  2. DevTools → Network → любой XHR-запрос → заголовок Authorization: Bearer <токен>")
    print("     или Application → Local Storage → seller-analytics.mm.ru")
    print("  3. Скопируй строку целиком (начинается с eyJ...)")
    print()
    try:
        raw = input("  Вставь токен (или Enter чтобы пропустить API-шаги): ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""

    if not raw:
        print("[token] ⏭️  Пропускаем — API-шаги будут недоступны в этом запуске")
        return 2

    info = token_info(raw)
    if info["status"] == "expired":
        print(f"[token] ⚠️  Токен уже истёк ({info['expires_msk']}). Запусти bat заново и вставь свежий.")
        return 2
    if info["status"] == "no_exp":
        print("[token] ⚠️  Не удалось определить срок действия — использую как есть.")
    else:
        ttl = fmt_ttl(info["seconds_left"])
        print(f"[token] ✅ Действителен ещё {ttl} (до {info['expires_msk']}) — достаточно для текущего запуска")

    # Write token to temp file — bat reads it, then deletes
    TOKEN_FILE.write_text(raw, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
