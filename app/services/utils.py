import logging
import re
from typing import Any

from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.models import Setting

logger = logging.getLogger("apply-buddy.utils")


def load_setting(key: str, default: str) -> str:
    try:
        with Session(engine) as session:
            setting = session.get(Setting, key)
            if setting and setting.value:
                return setting.value
    except Exception:
        logger.exception(f"Failed to load setting '{key}', falling back to default")
    return default


def load_prompt(key: str, default: str) -> str:
    return load_setting(key, default)


def load_prompt_model(key: str) -> str | None:
    try:
        with Session(engine) as session:
            setting = session.get(Setting, key)
            if setting and setting.value:
                return setting.value
    except Exception:
        logger.exception(f"Failed to load prompt model '{key}'")
    return None


def run_background_task(
    state: dict[str, Any] | None,
    fn: Any,
    *args: Any,
    success_message: str = "Done",
    **kwargs: Any,
) -> None:
    try:
        fn(*args, **kwargs)
        if state:
            state["message"] = success_message
    except Exception as e:
        logger.exception(f"Background task failed: {e}")
        if state:
            state["message"] = f"Error: {e}"
    finally:
        if state:
            state["running"] = False


def read_cv_text() -> str | None:
    cv_path = settings.cv_tex_path_resolved
    if not cv_path.exists():
        logger.warning(f"CV not found at {cv_path}")
        return None
    try:
        return cv_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read CV: {e}")
        return None


def strip_tex_to_plain(tex: str) -> str:
    body = tex
    doc_start = body.find(r"\begin{document}")
    doc_end = body.find(r"\end{document}")
    if doc_start != -1 and doc_end != -1:
        body = body[doc_start + len(r"\begin{document}") : doc_end]

    body = re.sub(r"(?<!\\)%.*", "", body)
    body = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", body)
    body = re.sub(r"\[[^\[\]]*\]", "", body)

    body = body.replace(r"\\", " ")
    body = body.replace(r"\~", " ")
    body = body.replace(r"\%", "%")
    body = body.replace(r"\&", "&")
    body = body.replace(r"\_", "_")
    body = body.replace(r"\#", "#")
    body = body.replace(r"\$", "$")
    body = body.replace(r"\{", "{")
    body = body.replace(r"\}", "}")

    body = re.sub(r"\\[a-zA-Z]+", "", body)
    body = body.replace("{", " ").replace("}", " ")
    body = re.sub(r"\s+", " ", body).strip()
    return body
