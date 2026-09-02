import logging
import re

from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.models import Job, Setting
from app.services.compile import (
    convert_markdown_to_docx,
    convert_markdown_to_pdf,
    latex_available,
    pandoc_available,
)
from app.services.llm import LLMError, _load_prompt, _load_prompt_model, chat_completion

logger = logging.getLogger("apply-buddy.cover_letter")


def generate_cover_letter(job_id: int, state: dict = None, use_template: bool = True) -> None:
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

    template_text = ""
    if use_template:
        template_path = settings.cover_letter_template_path_resolved
        if template_path.exists():
            template_text = template_path.read_text(encoding="utf-8")
            state["message"] = "Using cover letter template..."
        else:
            state["message"] = "No template found, generating from scratch..."

    state["message"] = "Requesting LLM to write cover letter..."
    try:
        md = _llm_cover_letter(job.title, job.company, job.description, cv_text, template_text)
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

    with Session(engine) as session:
        convert_cl_pdf = session.get(Setting, "convert_cl_pdf")
        convert_cl_docx = session.get(Setting, "convert_cl_docx")
        want_pdf = convert_cl_pdf.value == "1" if convert_cl_pdf else True
        want_docx = convert_cl_docx.value == "1" if convert_cl_docx else True

    docx_ok = False
    pdf_ok = False
    conversion_attempted = False

    if want_docx and pandoc_available():
        state["message"] = "Converting to DOCX..."
        docx_ok, docx_err = convert_markdown_to_docx(md_path, output_dir)
        if not docx_ok:
            logger.warning("DOCX conversion failed: %s", docx_err)
        conversion_attempted = True

    if want_pdf and (pandoc_available() or latex_available()):
        state["message"] = "Converting to PDF..."
        pdf_ok, pdf_err = convert_markdown_to_pdf(md_path, output_dir)
        if not pdf_ok:
            logger.warning("PDF conversion failed: %s", pdf_err)
        conversion_attempted = True

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

    if conversion_attempted:
        parts = []
        if docx_ok:
            parts.append("DOCX")
        if pdf_ok:
            parts.append("PDF")
        if parts:
            state["message"] = f"Cover letter saved with {' & '.join(parts)}"
        else:
            msg = "Cover letter .md saved (conversion failed)"
            if want_docx and not docx_ok:
                msg += f" DOCX: {docx_err[:120]}"
            if want_pdf and not pdf_ok:
                msg += f" PDF: {pdf_err[:120]}"
            state["message"] = msg
    else:
        if not want_pdf and not want_docx:
            state["message"] = "Cover letter .md saved (conversions disabled)"
        else:
            state["message"] = "Cover letter .md saved (no conversion engine available)"


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
- Use English only. If the job description is in another language, translate it to English first.

Return ONLY the markdown cover letter."""

DEFAULT_COVER_LETTER_TEMPLATE_PROMPT = """Write a professional cover letter in Markdown format. Follow the style, structure, tone, and format of the template below. Natural, human tone. No commentary.

Job Title: {title}
Company: {company}
Job Description:
{description}

Candidate CV:
{cv_text}

Cover Letter Template (follow this style and structure):
{template}

Write a cover letter that connects the candidate's experience to the job requirements, adapting the template's style and structure to this specific role. Include:
- Opening: what role and where
- Body: relevant experience and skills
- Closing: enthusiasm and call to action
- Use English only. If the job description is in another language, translate it to English first.

Return ONLY the markdown cover letter."""


def _load_cover_letter_prompt() -> str:
    return _load_prompt("prompt_cover_letter", DEFAULT_COVER_LETTER_PROMPT)


def _load_cover_letter_template_prompt() -> str:
    return _load_prompt("prompt_cover_letter_template", DEFAULT_COVER_LETTER_TEMPLATE_PROMPT)


def _load_cover_letter_model() -> str | None:
    return _load_prompt_model("prompt_cover_letter_model")


def _load_cover_letter_template_model() -> str | None:
    return _load_prompt_model("prompt_cover_letter_template_model")


def _llm_cover_letter(
    title: str, company: str, description: str, cv_text: str, template_text: str = ""
) -> str:
    if template_text:
        prompt_template = _load_cover_letter_template_prompt()
        prompt = prompt_template.format(
            title=title,
            company=company,
            description=description,
            cv_text=cv_text,
            template=template_text,
        )
        model = _load_cover_letter_template_model()
    else:
        prompt_template = _load_cover_letter_prompt()
        prompt = prompt_template.format(
            title=title,
            company=company,
            description=description,
            cv_text=cv_text,
        )
        model = _load_cover_letter_model()

    messages = [
        {
            "role": "system",
            "content": "You write professional cover letters in Markdown. No commentary.",
        },
        {"role": "user", "content": prompt},
    ]

    result = chat_completion(messages, model=model)
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r"^```(?:markdown)?\s*", "", result)
        result = re.sub(r"\s*```$", "", result)
    return result
