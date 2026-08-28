import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.models import Setting
from app.services.llm import (
    LLMError,
    _build_url,
    _is_reasoning_model,
    _load_available_models,
    _load_prompt,
    _load_prompt_model,
    chat_completion,
)


def test_llm_error_is_exception():
    assert issubclass(LLMError, Exception)


def test_load_prompt_default(db_session):
    result = _load_prompt("nonexistent_key", "default_value")
    assert result == "default_value"


def test_load_prompt_from_db(db_session):
    db_session.add(Setting(key="prompt_test", value="from_db"))
    db_session.commit()
    result = _load_prompt("prompt_test", "fallback")
    assert result == "from_db"


def test_load_prompt_returns_default_on_empty_value(db_session):
    db_session.add(Setting(key="prompt_test_empty", value=""))
    db_session.commit()
    result = _load_prompt("prompt_test_empty", "fallback")
    assert result == "fallback"


def test_load_available_models_default():
    models = _load_available_models()
    assert isinstance(models, list)
    assert len(models) > 0
    assert "llama3.2" in models


def test_load_available_models_invalid_json(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.llm_available_models", "not json")
    assert _load_available_models() == []


def test_load_available_models_not_a_list(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.llm_available_models", '"string"')
    assert _load_available_models() == []


def test_load_prompt_model_default():
    assert _load_prompt_model("nonexistent") is None


def test_load_prompt_model_from_db(db_session):
    db_session.add(Setting(key="model_test", value="gpt-4o"))
    db_session.commit()
    result = _load_prompt_model("model_test")
    assert result == "gpt-4o"


def test_load_prompt_model_empty_value(db_session):
    db_session.add(Setting(key="model_test_empty", value=""))
    db_session.commit()
    assert _load_prompt_model("model_test_empty") is None


def test_is_reasoning_model_gpt5():
    assert _is_reasoning_model("gpt-5") is True
    assert _is_reasoning_model("gpt-5-turbo") is True
    assert _is_reasoning_model("gpt-5-preview") is True


def test_is_reasoning_model_o_series():
    assert _is_reasoning_model("o1") is True
    assert _is_reasoning_model("o1-preview") is True
    assert _is_reasoning_model("o1-mini") is True
    assert _is_reasoning_model("o3") is True
    assert _is_reasoning_model("o3-mini") is True


def test_is_reasoning_model_false():
    assert _is_reasoning_model("gpt-4o") is False
    assert _is_reasoning_model("gpt-4") is False
    assert _is_reasoning_model("llama3.2") is False
    assert _is_reasoning_model("claude-3-opus") is False
    assert _is_reasoning_model("") is False
    assert _is_reasoning_model("o") is False
    assert _is_reasoning_model("oa") is False


def test_build_url_openai():
    url = _build_url()
    assert url == "http://test:1234/v1/chat/completions"


def test_build_url_openai_with_model():
    url = _build_url(model="gpt-4o")
    assert url == "http://test:1234/v1/chat/completions"


def test_build_url_databricks(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.llm_provider", "databricks")
    url = _build_url(model="databricks-model")
    assert url == "http://test:1234/v1/databricks-model/invocations"


def test_chat_completion_success(mock_httpx):
    messages = [{"role": "user", "content": "Hello"}]
    result = chat_completion(messages)
    data = json.loads(result)
    assert data["fit_score"] == 85
    assert data["reason"] == "Great match"
    mock_httpx.assert_called_once()


def test_chat_completion_with_json_response_format(mock_httpx):
    messages = [{"role": "user", "content": "Return JSON"}]
    result = chat_completion(messages, response_format="json")
    data = json.loads(result)
    assert data["fit_score"] == 85


def test_chat_completion_with_reasoning_model(monkeypatch, mock_httpx):
    monkeypatch.setattr("app.services.llm.settings.llm_model", "o1")
    messages = [{"role": "user", "content": "Hello"}]
    result = chat_completion(messages)
    data = json.loads(result)
    assert data["fit_score"] == 85
    call_kwargs = mock_httpx.call_args[1]
    assert "temperature" not in call_kwargs["json"]
    assert "max_tokens" not in call_kwargs["json"]
    assert call_kwargs["json"]["max_completion_tokens"] == 4096


def test_chat_completion_retry_on_http_error(monkeypatch):
    responses = [
        httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock(status_code=500)),
        httpx.HTTPStatusError("502", request=MagicMock(), response=MagicMock(status_code=502)),
        MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": '{"fit_score": 90, "reason": "After retry"}'}}]
            },
        ),
    ]
    mock_post = MagicMock(side_effect=responses)
    monkeypatch.setattr("httpx.post", mock_post)
    messages = [{"role": "user", "content": "Test"}]
    result = chat_completion(messages, max_retries=3)
    data = json.loads(result)
    assert data["fit_score"] == 90
    assert mock_post.call_count == 3


def test_chat_completion_raises_llm_error_after_max_retries(monkeypatch):
    error_response = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock(status_code=500)
    )
    mock_post = MagicMock(side_effect=error_response)
    monkeypatch.setattr("httpx.post", mock_post)
    messages = [{"role": "user", "content": "Test"}]
    with pytest.raises(LLMError, match="LLM call failed after 2 retries"):
        chat_completion(messages, max_retries=2)
    assert mock_post.call_count == 2


def test_chat_completion_retry_on_request_error(monkeypatch):
    responses = [
        httpx.RequestError("Connection error", request=MagicMock()),
        MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": '{"fit_score": 80, "reason": "Recovered"}'}}]
            },
        ),
    ]
    mock_post = MagicMock(side_effect=responses)
    monkeypatch.setattr("httpx.post", mock_post)
    messages = [{"role": "user", "content": "Test"}]
    result = chat_completion(messages, max_retries=3)
    data = json.loads(result)
    assert data["fit_score"] == 80
    assert mock_post.call_count == 2
