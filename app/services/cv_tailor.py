import logging
import re
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.models import Job, Setting
from app.services.compile import compile_latex_to_pdf, latex_available
from app.services.cv_diff import generate_cv_diff
from app.services.llm import LLMError, _load_prompt, _load_prompt_model, chat_completion

logger = logging.getLogger("apply-buddy.cv_tailor")


def tailor_cv_for_job(job_id: int, state: dict = None) -> None:
    if state is None:
        state = {}
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            state["message"] = f"Job {job_id} not found"
            logger.error(f"Job {job_id} not found")
            return

        cv_path = settings.cv_tex_path_resolved
        if not cv_path.exists():
            state["message"] = "Master CV not found"
            logger.error(f"Master CV not found at {cv_path}")
            return

        master_tex = cv_path.read_text(encoding="utf-8")

    state["message"] = "Requesting LLM to tailor CV..."
    try:
        tailored = _llm_tailor_cv(master_tex, job.title, job.company, job.description)
    except LLMError as e:
        state["message"] = f"LLM error: {e}"
        logger.error(f"LLM CV tailoring failed for job {job_id}: {e}")
        return

    state["message"] = "Saving tailored CV..."
    output_dir = settings.output_path / str(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    tex_path = output_dir / "cv.tex"
    tex_path.write_text(tailored, encoding="utf-8")

    with Session(engine) as session:
        job = session.get(Job, job_id)
        job.tailored_cv_path = str(tex_path)
        job.tailored_cv_pdf_path = None
        session.add(job)
        session.commit()

    convert_pdf = True
    with Session(engine) as session:
        setting = session.get(Setting, "convert_cv_pdf")
        if setting:
            convert_pdf = setting.value == "1"

    if convert_pdf and latex_available():
        state["message"] = "Compiling CV to PDF..."
        success, msg = compile_latex_to_pdf(tex_path, output_dir)
        _cleanup_latex_aux(output_dir, "cv")
        if success:
            pdf_path = output_dir / "cv.pdf"
            with Session(engine) as session:
                job = session.get(Job, job_id)
                job.tailored_cv_pdf_path = str(pdf_path)
                session.add(job)
                session.commit()
            state["message"] = "CV compiled successfully"
            logger.info(f"CV compiled for job {job_id}")
        else:
            state["message"] = f"CV saved but compilation had issues: {msg[:200]}"
            logger.warning(f"CV compilation failed for job {job_id}: {msg}")
    else:
        if not convert_pdf:
            state["message"] = "CV .tex saved (PDF conversion disabled)"
        else:
            state["message"] = "CV .tex saved (LaTeX not available for PDF)"
        logger.info("CV .tex saved without PDF compilation")

    convert_diff = True
    with Session(engine) as session:
        setting = session.get(Setting, "convert_cv_diff")
        if setting:
            convert_diff = setting.value == "1"

    if convert_diff:
        state["message"] = "Generating CV diff..."
        diff_pdf = generate_cv_diff(cv_path, tex_path, output_dir)
        if diff_pdf:
            _cleanup_latex_aux(output_dir, "cv_diff")
        if diff_pdf:
            with Session(engine) as session:
                job = session.get(Job, job_id)
                job.tailored_cv_diff_pdf_path = str(diff_pdf)
                session.add(job)
                session.commit()
            logger.info("CV diff PDF generated for job %s", job_id)
            state["message"] = "CV tailored successfully (with diff PDF)"
        else:
            logger.info("CV diff not generated for job %s (identical or error)", job_id)
            state["message"] = "CV tailored successfully"
    else:
        state["message"] = "CV tailored successfully"


DEFAULT_TAILOR_CV_PROMPT = """You are editing a LaTeX CV. Return ONLY a complete, compilable .tex document — no commentary, no markdown fences.

Job Title: {title}
Company: {company}
Job Description:
{description}

Master CV (.tex):
{master_tex}

Tailor this CV to highlight experience relevant to the job. Keep the same documentclass, packages, and overall structure. Adjust bullet points, project descriptions, and summary to match the job requirements. Do NOT add fake experience."""


def _load_tailor_cv_prompt() -> str:
    return _load_prompt("prompt_tailor_cv", DEFAULT_TAILOR_CV_PROMPT)


def _load_tailor_cv_model() -> str | None:
    return _load_prompt_model("prompt_tailor_cv_model")


def _llm_tailor_cv(master_tex: str, title: str, company: str, description: str) -> str:
    prompt_template = _load_tailor_cv_prompt()
    prompt = prompt_template.format(
        title=title,
        company=company,
        description=description,
        master_tex=master_tex,
    )

    messages = [
        {
            "role": "system",
            "content": "You are a LaTeX expert. Return ONLY the .tex code, no explanation.",
        },
        {"role": "user", "content": prompt},
    ]

    result = chat_completion(messages, model=_load_tailor_cv_model())
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r"^```(?:latex)?\s*", "", result)
        result = re.sub(r"\s*```$", "", result)

    doc_start = result.find(r"\documentclass")
    doc_end = result.rfind(r"\end{document}")
    if doc_start != -1 and doc_end != -1:
        result = result[doc_start : doc_end + len(r"\end{document}")]

    return result


def _cleanup_latex_aux(output_dir: Path, stem: str) -> None:
    for ext in [".aux", ".log", ".out", ".fls"]:
        p = output_dir / f"{stem}{ext}"
        p.unlink(missing_ok=True)
