import json
import logging
import time
from typing import Any

import httpx
from sqlmodel import Session

from app.config import settings
from app.models import Setting

logger = logging.getLogger("apply-buddy.llm")


class LLMError(Exception):
    pass


def _load_prompt(key: str, default: str) -> str:
    from app.db import engine

    try:
        with Session(engine) as session:
            setting = session.get(Setting, key)
            if setting and setting.value:
                return setting.value
    except Exception:
        pass
    return default


def _load_llm_setting(key: str, default: str) -> str:
    from app.db import engine

    try:
        with Session(engine) as session:
            setting = session.get(Setting, key)
            if setting and setting.value:
                return setting.value
    except Exception:
        pass
    return default


def _load_llm_provider() -> str:
    return _load_llm_setting("llm_provider", settings.llm_provider)


def _load_llm_base_url() -> str:
    return _load_llm_setting("llm_base_url", settings.llm_base_url)


def _load_llm_api_key() -> str:
    return _load_llm_setting("llm_api_key", settings.llm_api_key)


def _load_llm_model() -> str:
    raw = _load_llm_setting("llm_model", "")
    if raw:
        return raw
    models = _load_available_models()
    return models[0] if models else settings.llm_model


def _load_llm_temperature() -> float:
    raw = _load_llm_setting("llm_temperature", str(settings.llm_temperature))
    try:
        return float(raw)
    except (ValueError, TypeError):
        return settings.llm_temperature


def _load_available_models() -> list[str]:
    raw = settings.llm_available_models
    try:
        models = json.loads(raw)
        return models if isinstance(models, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _load_prompt_model(key: str) -> str | None:
    from app.db import engine

    try:
        with Session(engine) as session:
            setting = session.get(Setting, key)
            if setting and setting.value:
                return setting.value
    except Exception:
        pass
    return None


def _is_reasoning_model(model_name: str) -> bool:
    return model_name.startswith("gpt-5") or (
        len(model_name) > 1 and model_name[0] == "o" and model_name[1].isdigit()
    )


def _build_url(model: str | None = None) -> str:
    base = _load_llm_base_url().rstrip("/")
    effective_model = model or _load_llm_model()
    if _load_llm_provider() == "databricks":
        return f"{base}/{effective_model}/invocations"
    return f"{base}/chat/completions"


def chat_completion(
    messages: list[dict[str, str]],
    response_format: str | None = None,
    max_retries: int = 3,
    model: str | None = None,
) -> str:
    api_key = _load_llm_api_key()
    provider = _load_llm_provider()
    effective_model = model or _load_llm_model()
    temperature = _load_llm_temperature()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    is_reasoning = _is_reasoning_model(effective_model)
    body: dict[str, Any] = {
        "messages": messages,
    }
    if not is_reasoning:
        body["temperature"] = temperature
        body["max_tokens"] = 4096
    else:
        body["max_completion_tokens"] = 4096
    if provider != "databricks":
        body["model"] = effective_model
    if response_format == "json":
        body["response_format"] = {"type": "json_object"}

    url = _build_url(model)
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = httpx.post(
                url,
                headers=headers,
                json=body,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(f"LLM HTTP {e.response.status_code} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(min(2**attempt, 30))
        except (httpx.RequestError, KeyError, json.JSONDecodeError) as e:
            last_error = e
            logger.warning(f"LLM error: {e} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(min(2**attempt, 30))

    raise LLMError(f"LLM call failed after {max_retries} retries: {last_error}")
