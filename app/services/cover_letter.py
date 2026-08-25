import logging
import re
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.models import Job
from app.services.llm import chat_completion, LLMError, _load_prompt, _load_prompt_model
from app.services.compile import (
    convert_markdown_to_docx,
    convert_markdown_to_pdf,
    latex_available,
    pandoc_available,
)

logger = logging.getLogger("apply-buddy.cover_letter")


def generate_cover_letter(job_id: int, state: dict = None) -> None:
    if state is None:
        state = {}
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            state["message"] = f"Job {job_id} not found"
            logger.error(f"Job {job_id} not found")
            return

        cv_path = settings.cv_tex_path_resolved
        cv_text = ""
        if cv_path.exists():
            cv_text = cv_path.read_text(encoding="utf-8")

    state["message"] = "Requesting LLM to write cover letter..."
    try:
        md = _llm_cover_letter(job.title, job.company, job.description, cv_text)
    except LLMError as e:
        state["message"] = f"LLM error: {e}"
        logger.error(f"LLM cover letter failed for job {job_id}: {e}")
        return

    state["message"] = "Saving cover letter..."
    output_dir = settings.output_path / str(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "cover_letter.md"
    md_path.write_text(md, encoding="utf-8")

    with Session(engine) as session:
        job = session.get(Job, job_id)
        job.cover_letter_path = str(md_path)
        session.add(job)
        session.commit()

    can_convert = pandoc_available() or latex_available()
    if can_convert:
        state["message"] = "Converting to DOCX/PDF..."
        docx_ok = False
        if pandoc_available():
            docx_ok, docx_err = convert_markdown_to_docx(md_path, output_dir)
            if not docx_ok:
                logger.warning("DOCX conversion failed: %s", docx_err)
        pdf_ok, pdf_err = convert_markdown_to_pdf(md_path, output_dir)
        if not pdf_ok:
            logger.warning("PDF conversion failed: %s", pdf_err)
        with Session(engine) as session:
            job = session.get(Job, job_id)
            docx_path = output_dir / "cover_letter.docx"
            pdf_path = output_dir / "cover_letter.pdf"
            if docx_ok and docx_path.exists():
                job.cover_letter_docx_path = str(docx_path)
            if pdf_ok and pdf_path.exists():
                job.cover_letter_pdf_path = str(pdf_path)
            session.add(job)
            session.commit()
        if pdf_ok:
            state["message"] = "Cover letter saved with PDF"
        else:
            state["message"] = (
                f"Cover letter .md saved (PDF conversion failed: {pdf_err[:120]})"
            )
            logger.error("PDF conversion failed for job %s: %s", job_id, pdf_err)
    else:
        state["message"] = "Cover letter .md saved (no PDF engine available)"
        logger.info(
            "No PDF engine (pandoc or pdflatex) available, cover letter .md saved without conversion"
        )


DEFAULT_COVER_LETTER_PROMPT = """Write a professional cover letter in Markdown format. Natural, human tone. No commentary.

Job Title: {title}
Company: {company}
Job Description:
{description}

Candidate CV:
{cv_text}

Write a cover letter that connects the candidate's experience to the job requirements. Include:
- Opening: what role and where
- Body: relevant experience and skills
- Closing: enthusiasm and call to action

Return ONLY the markdown cover letter."""


def _load_cover_letter_prompt() -> str:
    return _load_prompt("prompt_cover_letter", DEFAULT_COVER_LETTER_PROMPT)


def _load_cover_letter_model() -> Optional[str]:
    return _load_prompt_model("prompt_cover_letter_model")


def _llm_cover_letter(title: str, company: str, description: str, cv_text: str) -> str:
    prompt_template = _load_cover_letter_prompt()
    prompt = prompt_template.format(
        title=title,
        company=company,
        description=description[:4000],
        cv_text=cv_text[:4000],
    )

    messages = [
        {
            "role": "system",
            "content": "You write professional cover letters in Markdown. No commentary.",
        },
        {"role": "user", "content": prompt},
    ]

    result = chat_completion(messages, model=_load_cover_letter_model())
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r"^```(?:markdown)?\s*", "", result)
        result = re.sub(r"\s*```$", "", result)
    return result
