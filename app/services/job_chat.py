from pathlib import Path
from typing import Any

from app.config import settings
from app.models import Job
from app.services.llm import chat_completion
from app.services.utils import load_prompt, load_prompt_model

DEFAULT_JOB_CHAT_PROMPT = (
    "You are a sharp, concise career assistant helping the user with one specific job "
    "application. Use the job posting and any attached documents below as context. "
    "Answer in Markdown. When asked to write something the user will paste into an "
    "application form, give the text directly without preamble."
)


def _read(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_context(job: Job, cv: str, include_cover_letter: bool) -> str:
    parts = [
        f"## Job posting\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Location: {job.location}\n\n{job.description}"
    ]
    if cv == "reference":
        cv_text, label = _read(settings.cv_tex_path_resolved), "reference CV"
    elif cv == "tailored":
        cv_text, label = _read(job.tailored_cv_path), "CV tailored for this job"
    else:
        cv_text, label = "", ""
    if cv_text:
        parts.append(f"## My {label} (LaTeX source)\n{cv_text}")
    if include_cover_letter:
        cl_text = _read(job.cover_letter_path)
        if cl_text:
            parts.append(f"## My cover letter for this job\n{cl_text}")
    return "\n\n".join(parts)


def _to_openai(message: dict[str, Any]) -> dict[str, Any]:
    images = message.get("images") or []
    if not images:
        return {"role": message["role"], "content": message["content"]}
    content: list[dict[str, Any]] = [{"type": "text", "text": message["content"]}]
    content += [{"type": "image_url", "image_url": {"url": url}} for url in images]
    return {"role": message["role"], "content": content}


def ask(job: Job, history: list[dict[str, Any]], cv: str, include_cover_letter: bool) -> str:
    prompt = load_prompt("prompt_job_chat", DEFAULT_JOB_CHAT_PROMPT)
    system = f"{prompt}\n\n{build_context(job, cv, include_cover_letter)}"
    messages = [{"role": "system", "content": system}] + [_to_openai(m) for m in history]
    return chat_completion(messages, model=load_prompt_model("prompt_job_chat_model"))
