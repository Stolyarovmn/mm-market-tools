"""Logging config for mm-market-tools.

Usage: from core.logging_config import get_logger; log = get_logger(__name__)
Levels: TRACE(5) DEBUG INFO WARNING ERROR
.env:  LOG_LEVEL=INFO  (global)
       LOG_LEVEL_SCRIPTS_BUILD_X=DEBUG  (per-module, dots→underscores uppercase)
       LOG_TO_FILE=1  (writes to logs/mm-YYYY-MM-DD.log)
"""
from __future__ import annotations
import logging, os
from datetime import date
from pathlib import Path

TRACE = 5
logging.addLevelName(TRACE, "TRACE")
def _trace(self, msg, *a, **kw):
    if self.isEnabledFor(TRACE): self._log(TRACE, msg, a, **kw)
logging.Logger.trace = _trace  # type: ignore

_ENV: dict[str,str] = {}
def _load_env() -> dict[str,str]:
    global _ENV
    if _ENV: return _ENV
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for ln in p.read_text("utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k,_,v = ln.partition("="); _ENV[k.strip()]=v.strip()
    return _ENV

def _env(k:str, default:str="") -> str:
    return os.environ.get(k) or _load_env().get(k, default)

_LVLS = {"TRACE":TRACE,"DEBUG":10,"INFO":20,"WARNING":30,"WARN":30,"ERROR":40}

def _level(name:str) -> int:
    key = "LOG_LEVEL_" + name.upper().replace(".","_").replace("-","_")
    return _LVLS.get((_env(key) or _env("LOG_LEVEL","INFO")).upper(), 20)

_INIT = False
def _setup(logger:logging.Logger):
    global _INIT
    if _INIT: return
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s — %(message)s","%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(); ch.setFormatter(fmt); logging.root.addHandler(ch)
    if _env("LOG_TO_FILE","0") in ("1","true","yes"):
        d = Path(__file__).resolve().parent.parent / _env("LOG_DIR","logs")
        d.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(d/f"mm-{date.today().isoformat()}.log","a","utf-8")
        fh.setFormatter(fmt); logging.root.addHandler(fh)
    _INIT = True

def get_logger(name:str) -> logging.Logger:
    logger = logging.getLogger(name)
    lv = _level(name)
    logger.setLevel(lv)
    logging.root.setLevel(min(logging.root.level or TRACE, lv))
    _setup(logger)
    return logger
