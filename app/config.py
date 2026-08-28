import json
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml_config() -> dict[str, Any]:
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data.get("match_keywords"), dict):
        data["match_keywords"] = json.dumps(data["match_keywords"])
    return data


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "openai"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "sk-dummy"
    llm_model: str = "llama3.2"
    llm_temperature: float = 0.3

    database_url: str = "sqlite:///data/apply_buddy.db"

    cv_tex_path: str = "data/cv/cv.tex"
    cover_letter_template_path: str = "data/cover-letter/cover_letter.md"
    output_dir: str = "data/output"
    chrome_profile_dir: str = "chrome-profile"
    min_fit_score: int = 30
    match_keywords: str = "{}"
    min_keyword_score: int = 0
    llm_max_concurrency: int = 4
    llm_available_models: str = (
        '["llama3.2", "gpt-4o", "gpt-4o-mini", "claude-3-opus", "claude-3-sonnet", "mistral-large"]'
    )

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def cv_tex_path_resolved(self) -> Path:
        return Path(self.cv_tex_path)

    @property
    def chrome_profile_path(self) -> Path:
        return Path(self.chrome_profile_dir)

    @property
    def cover_letter_template_path_resolved(self) -> Path:
        return Path(self.cover_letter_template_path)


yaml_overrides = _load_yaml_config()
settings = Settings(**yaml_overrides)
