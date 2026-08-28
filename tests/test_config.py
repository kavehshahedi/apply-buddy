import json
from pathlib import Path
from unittest.mock import mock_open, patch

from app.config import Settings, _load_yaml_config
from app.services.llm import _is_reasoning_model


class TestSettingsDefaults:
    def test_default_values(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
        monkeypatch.setenv("LLM_API_KEY", "sk-dummy")
        monkeypatch.setenv("LLM_MODEL", "llama3.2")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///data/apply_buddy.db")
        monkeypatch.setenv("MIN_FIT_SCORE", "30")
        monkeypatch.setenv("LLM_MAX_CONCURRENCY", "4")
        monkeypatch.setenv("OUTPUT_DIR", "data/output")

        settings = Settings()
        assert settings.llm_provider == "openai"
        assert settings.llm_base_url == "http://localhost:11434/v1"
        assert settings.llm_api_key == "sk-dummy"
        assert settings.llm_model == "llama3.2"
        assert settings.llm_temperature == 0.3
        assert settings.database_url == "sqlite:///data/apply_buddy.db"
        assert settings.cv_tex_path == "data/cv/cv.tex"
        assert settings.cover_letter_template_path == "data/cover-letter/cover_letter.md"
        assert settings.output_dir == "data/output"
        assert settings.chrome_profile_dir == "chrome-profile"
        assert settings.min_fit_score == 30
        assert settings.match_keywords == "{}"
        assert settings.min_keyword_score == 0
        assert settings.llm_max_concurrency == 4
        assert isinstance(json.loads(settings.llm_available_models), list)

    def test_path_properties(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_DIR", "data/output")
        monkeypatch.setenv("CV_TEX_PATH", "data/cv/cv.tex")
        monkeypatch.setenv("COVER_LETTER_TEMPLATE_PATH", "data/cover-letter/cover_letter.md")
        monkeypatch.setenv("CHROME_PROFILE_DIR", "chrome-profile")

        settings = Settings()
        assert isinstance(settings.output_path, Path)
        assert settings.output_path == Path("data/output")
        assert settings.cv_tex_path_resolved == Path("data/cv/cv.tex")
        assert settings.chrome_profile_path == Path("chrome-profile")
        assert settings.cover_letter_template_path_resolved == Path(
            "data/cover-letter/cover_letter.md"
        )


class TestSettingsEnvOverrides:
    def test_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "databricks")
        monkeypatch.setenv("LLM_BASE_URL", "https://custom.api.com/v1")
        monkeypatch.setenv("LLM_API_KEY", "real-key")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
        monkeypatch.setenv("MIN_FIT_SCORE", "50")
        monkeypatch.setenv("LLM_MAX_CONCURRENCY", "8")

        settings = Settings()
        assert settings.llm_provider == "databricks"
        assert settings.llm_base_url == "https://custom.api.com/v1"
        assert settings.llm_api_key == "real-key"
        assert settings.llm_model == "gpt-4o"
        assert settings.llm_temperature == 0.7
        assert settings.database_url == "sqlite:///custom.db"
        assert settings.min_fit_score == 50
        assert settings.llm_max_concurrency == 8

    def test_path_properties_reflect_env(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_DIR", "custom/output")
        monkeypatch.setenv("CV_TEX_PATH", "custom/cv.tex")
        monkeypatch.setenv("COVER_LETTER_TEMPLATE_PATH", "custom/cl.md")
        monkeypatch.setenv("CHROME_PROFILE_DIR", "custom-chrome")

        settings = Settings()
        assert settings.output_path == Path("custom/output")
        assert settings.cv_tex_path_resolved == Path("custom/cv.tex")
        assert settings.cover_letter_template_path_resolved == Path("custom/cl.md")
        assert settings.chrome_profile_path == Path("custom-chrome")


class TestYamlConfig:
    def test_load_yaml_config_not_found(self):
        with patch("app.config.Path.exists", return_value=False):
            result = _load_yaml_config()
        assert result == {}

    def test_load_yaml_config_empty(self):
        with (
            patch("app.config.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="")),
        ):
            result = _load_yaml_config()
        assert result == {}

    def test_load_yaml_config_with_data(self):
        yaml_content = "llm_provider: openai\nllm_model: gpt-4o\nmin_fit_score: 50\n"
        with (
            patch("app.config.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=yaml_content)),
        ):
            result = _load_yaml_config()
        assert result["llm_provider"] == "openai"
        assert result["llm_model"] == "gpt-4o"
        assert result["min_fit_score"] == 50

    def test_load_yaml_config_match_keywords(self):
        yaml_content = "match_keywords:\n  python: 10\n  fastapi: 8\n"
        with (
            patch("app.config.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=yaml_content)),
        ):
            result = _load_yaml_config()
        assert "match_keywords" in result
        parsed = json.loads(result["match_keywords"])
        assert parsed == {"python": 10, "fastapi": 8}


class TestReasoningModelDetection:
    def test_gpt_5_detection(self):
        assert _is_reasoning_model("gpt-5") is True
        assert _is_reasoning_model("gpt-5-turbo") is True
        assert _is_reasoning_model("gpt-5o") is True

    def test_o_model_detection(self):
        assert _is_reasoning_model("o1") is True
        assert _is_reasoning_model("o3") is True
        assert _is_reasoning_model("o1-mini") is True
        assert _is_reasoning_model("o1-preview") is True

    def test_non_reasoning_models(self):
        assert _is_reasoning_model("gpt-4o") is False
        assert _is_reasoning_model("gpt-4") is False
        assert _is_reasoning_model("gpt-3.5-turbo") is False
        assert _is_reasoning_model("llama3.2") is False
        assert _is_reasoning_model("claude-3-opus") is False
        assert _is_reasoning_model("") is False

    def test_o_model_edge_cases(self):
        assert _is_reasoning_model("o") is False
        assert _is_reasoning_model("oa") is False
        assert _is_reasoning_model("o.") is False
        assert _is_reasoning_model("only") is False
