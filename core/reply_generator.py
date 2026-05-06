#!/usr/bin/env python3
"""
Reply draft generator for buyer reviews and questions.

Strategy:
  - "typical" items  → template-based (fast, free, no LLM needed)
  - "complex" items  → LLM prompt (Gemini / DeepSeek / local ollama)

Tone and templates are configured in data/reply_config.default.json with optional overrides from data/reply_config.local.json.
The LLM endpoint and API key are never stored on disk — they come from
the caller (e.g. the web server passes them from the browser session).
"""
import json
import re
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "data" / "reply_config.default.json"
LOCAL_CONFIG_PATH = Path(__file__).parent.parent / "data" / "reply_config.local.json"
LEGACY_CONFIG_PATH = Path(__file__).parent.parent / "data" / "reply_config.json"

# ---------------------------------------------------------------------------
# Default built-in config (used if repo files are absent)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "reply_tone": "neutral",
    "classify_threshold_stars": 3,   # reviews with rating <= this get LLM treatment
    "classify_keywords_complex": [   # keywords that force LLM treatment regardless of rating
        "брак", "не работает", "обман", "ложь", "сломан", "плохое качество",
        "не соответствует", "возврат", "хочу вернуть", "угроза",
    ],
    "templates": {
        "review_positive_neutral": {
            "neutral": "Спасибо за ваш отзыв и оценку! Рады, что {product} вам понравился. Будем рады видеть вас снова.",
            "warm":    "Большое спасибо за тёплый отзыв! 🙌 Очень рады, что {product} оправдал ожидания. Ждём вас снова!",
            "formal":  "Благодарим вас за оставленный отзыв. Ваше мнение важно для нас. Надеемся на продолжение сотрудничества.",
        },
        "question_general": {
            "neutral": "Добрый день! По вашему вопросу о {product}: {answer_placeholder}. Если остались вопросы — пишите.",
            "warm":    "Привет! Спасибо за вопрос о {product}. {answer_placeholder} Если нужна дополнительная информация — с удовольствием поможем! 😊",
            "formal":  "Уважаемый покупатель, благодарим за обращение. По вопросу о {product}: {answer_placeholder}. Готовы ответить на дальнейшие вопросы.",
        },
    },
    "llm": {
        "provider": "none",      # "none" | "gemini" | "deepseek" | "ollama"
        "model":    "",
        "endpoint": "",
        "system_prompt_neutral": (
            "Ты — вежливый менеджер интернет-магазина на Мегамаркет. "
            "Пиши ответы на русском языке, коротко (2–4 предложения), без лишних эмодзи. "
            "Не обещай конкретных сроков и не упоминай конкурентов."
        ),
        "system_prompt_warm": (
            "Ты — дружелюбный менеджер интернет-магазина на Мегамаркет. "
            "Пиши тёплые, искренние ответы на русском, 2–4 предложения. "
            "Можно использовать 1–2 уместных эмодзи. Не обещай конкретных сроков."
        ),
        "system_prompt_formal": (
            "Вы — официальный представитель интернет-магазина на Мегамаркет. "
            "Отвечайте на русском языке в официальном стиле, 2–4 предложения. "
            "Не используйте разговорные выражения и эмодзи."
        ),
    },
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _deep_merge(base, override):
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json_config(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_config(config_path=None, local_config_path=None):
    if config_path is not None:
        return _deep_merge(DEFAULT_CONFIG, _load_json_config(Path(config_path)))

    base_path = DEFAULT_CONFIG_PATH if DEFAULT_CONFIG_PATH.exists() else LEGACY_CONFIG_PATH
    merged = _deep_merge(DEFAULT_CONFIG, _load_json_config(base_path))
    merged = _deep_merge(merged, _load_json_config(Path(local_config_path or LOCAL_CONFIG_PATH)))
    return merged


def save_config(config, config_path=None):
    path = Path(config_path or LOCAL_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never save LLM keys ? strip them
    safe = {k: v for k, v in config.items() if k != "llm_api_key"}
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_item(item, config):
    """
    Returns 'typical' or 'complex'.
    Complex = low rating OR contains problematic keywords.
    """
    threshold = config.get("classify_threshold_stars", 3)
    keywords = config.get("classify_keywords_complex", [])

    rating = item.get("rating")
    text = (item.get("text") or "").lower()

    if rating is not None and int(rating) <= threshold:
        return "complex"
    for kw in keywords:
        if kw.lower() in text:
            return "complex"
    return "typical"


# ---------------------------------------------------------------------------
# Template-based generation
# ---------------------------------------------------------------------------

def _fill_template(template, item):
    product = item.get("product_title") or "товар"
    # Truncate long product names
    if len(product) > 40:
        product = product[:37] + "…"
    filled = template.replace("{product}", product)
    filled = filled.replace("{answer_placeholder}", "уточняем информацию и ответим подробнее")
    return filled


def generate_template_reply(item, config):
    tone = config.get("reply_tone", "neutral")
    templates = config.get("templates", DEFAULT_CONFIG["templates"])

    if item.get("kind") == "question":
        tpl_set = templates.get("question_general", {})
    else:
        tpl_set = templates.get("review_positive_neutral", {})

    template = tpl_set.get(tone) or tpl_set.get("neutral") or ""
    if not template:
        return ""
    return _fill_template(template, item)


# ---------------------------------------------------------------------------
# LLM-based generation
# ---------------------------------------------------------------------------

def _build_llm_prompt(item, config):
    tone = config.get("reply_tone", "neutral")
    llm_cfg = config.get("llm", {})
    system_key = f"system_prompt_{tone}"
    system_prompt = llm_cfg.get(system_key) or llm_cfg.get("system_prompt_neutral", "")

    kind_label = "отзыв" if item.get("kind") == "review" else "вопрос"
    rating_line = f"Оценка покупателя: {item['rating']} / 5\n" if item.get("rating") else ""
    product_line = f"Товар: {item.get('product_title') or 'неизвестен'}\n"

    user_prompt = (
        f"Напиши ответ от имени магазина на следующий {kind_label}:\n\n"
        f"{product_line}"
        f"{rating_line}"
        f"Текст:\n{item.get('text') or ''}\n\n"
        "Ответ должен быть вежливым, конкретным и не длиннее 4 предложений."
    )
    return system_prompt, user_prompt


def generate_llm_reply(item, config, llm_api_key=None):
    """
    Call configured LLM to generate a reply draft.
    Returns (text, provider_used) or raises RuntimeError on failure.
    """
    llm_cfg = config.get("llm", {})
    provider = (llm_cfg.get("provider") or "none").lower()

    if provider == "none":
        raise RuntimeError(
            "LLM provider не настроен. "
            "Установи provider в data/reply_config.json: 'gemini', 'deepseek' или 'ollama'."
        )

    system_prompt, user_prompt = _build_llm_prompt(item, config)

    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, llm_cfg, llm_api_key)
    if provider == "deepseek":
        return _call_openai_compat(system_prompt, user_prompt, llm_cfg, llm_api_key,
                                   default_endpoint="https://api.deepseek.com/v1/chat/completions",
                                   default_model="deepseek-chat")
    if provider == "ollama":
        return _call_openai_compat(system_prompt, user_prompt, llm_cfg, llm_api_key,
                                   default_endpoint="http://localhost:11434/v1/chat/completions",
                                   default_model=llm_cfg.get("model") or "llama3")
    raise RuntimeError(f"Неизвестный LLM provider: {provider}")


def _call_gemini(system_prompt, user_prompt, llm_cfg, api_key):
    import urllib.request
    model = llm_cfg.get("model") or "gemini-1.5-flash"
    endpoint = llm_cfg.get("endpoint") or f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    key = api_key or llm_cfg.get("api_key") or ""
    url = f"{endpoint}?key={key}" if key else endpoint

    body = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": 256, "temperature": 0.7},
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text = (
        ((data.get("candidates") or [{}])[0].get("content") or {})
        .get("parts", [{}])[0]
        .get("text", "")
    ).strip()
    if not text:
        raise RuntimeError("Gemini вернул пустой ответ.")
    return text, "gemini"


def _call_openai_compat(system_prompt, user_prompt, llm_cfg, api_key,
                        default_endpoint, default_model):
    import urllib.request
    endpoint = llm_cfg.get("endpoint") or default_endpoint
    model = llm_cfg.get("model") or default_model
    key = api_key or llm_cfg.get("api_key") or ""

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 256,
        "temperature": 0.7,
    }).encode("utf-8")

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text = (
        (data.get("choices") or [{}])[0]
        .get("message", {})
        .get("content", "")
    ).strip()
    if not text:
        raise RuntimeError("LLM вернул пустой ответ.")
    provider = "ollama" if "localhost" in endpoint else "deepseek"
    return text, provider


# ---------------------------------------------------------------------------
# Top-level: generate best available draft
# ---------------------------------------------------------------------------

def generate_draft(item, config, llm_api_key=None):
    """
    Returns dict:
      {text, strategy, provider, classify}
    strategy: 'template' | 'llm'
    """
    kind = classify_item(item, config)

    # Always try template first for typical
    if kind == "typical":
        text = generate_template_reply(item, config)
        return {"text": text, "strategy": "template", "provider": "template", "classify": kind}

    # Complex: try LLM, fall back to template
    try:
        text, provider = generate_llm_reply(item, config, llm_api_key=llm_api_key)
        return {"text": text, "strategy": "llm", "provider": provider, "classify": kind}
    except RuntimeError as e:
        # LLM not configured — fall back to template with a note
        text = generate_template_reply(item, config)
        return {
            "text": text,
            "strategy": "template_fallback",
            "provider": "template",
            "classify": kind,
            "llm_error": str(e),
        }
