import shutil
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session, select
from app.db import get_session
from app.models import SearchQuery, Setting
from app.schemas import SearchQueryCreate, SearchQueryUpdate, SettingUpdate
from app.config import settings
from app.services.matcher import DEFAULT_SCORE_FIT_PROMPT
from app.services.cv_tailor import DEFAULT_TAILOR_CV_PROMPT
from app.services.cover_letter import DEFAULT_COVER_LETTER_PROMPT
from app.services.llm import _load_available_models

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request, session: Session = Depends(get_session)):
    queries = session.exec(select(SearchQuery)).all()
    db_settings = {s.key: s.value for s in session.exec(select(Setting)).all()}
    available_models = _load_available_models()
    return request.app.state.templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "queries": queries,
            "cv_path": db_settings.get("cv_tex_path", settings.cv_tex_path),
            "match_keywords": db_settings.get(
                "match_keywords", settings.match_keywords
            ),
            "min_fit_score": db_settings.get(
                "min_fit_score", str(settings.min_fit_score)
            ),
            "min_keyword_score": db_settings.get(
                "min_keyword_score", str(settings.min_keyword_score)
            ),
            "llm_max_concurrency": db_settings.get(
                "llm_max_concurrency", str(settings.llm_max_concurrency)
            ),
            "prompt_score_fit": db_settings.get(
                "prompt_score_fit", DEFAULT_SCORE_FIT_PROMPT
            ),
            "prompt_tailor_cv": db_settings.get(
                "prompt_tailor_cv", DEFAULT_TAILOR_CV_PROMPT
            ),
            "prompt_cover_letter": db_settings.get(
                "prompt_cover_letter", DEFAULT_COVER_LETTER_PROMPT
            ),
            "DEFAULT_SCORE_FIT_PROMPT": DEFAULT_SCORE_FIT_PROMPT,
            "DEFAULT_TAILOR_CV_PROMPT": DEFAULT_TAILOR_CV_PROMPT,
            "DEFAULT_COVER_LETTER_PROMPT": DEFAULT_COVER_LETTER_PROMPT,
            "available_models": available_models,
            "prompt_score_fit_model": db_settings.get(
                "prompt_score_fit_model", ""
            ),
            "prompt_tailor_cv_model": db_settings.get(
                "prompt_tailor_cv_model", ""
            ),
            "prompt_cover_letter_model": db_settings.get(
                "prompt_cover_letter_model", ""
            ),
            "default_model": settings.llm_model,
        },
    )


@router.get("/tool-check")
async def tool_check():
    import os

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome = (
        shutil.which("chrome")
        or shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or (os.name == "nt" and any(os.path.exists(p) for p in chrome_paths))
    )
    latex = (
        shutil.which("latexmk")
        or shutil.which("pdflatex")
        or (
            os.name == "nt"
            and (
                os.path.exists(r"C:\Program Files\MiKTeX\miktex\bin\x64\latexmk.exe")
                or os.path.exists(
                    r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe"
                )
                or os.path.exists(
                    os.path.expandvars(
                        r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\latexmk.exe"
                    )
                )
                or os.path.exists(
                    os.path.expandvars(
                        r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
                    )
                )
            )
        )
    )
    pandoc = shutil.which("pandoc") or (
        os.name == "nt"
        and (
            os.path.exists(r"C:\Program Files\Pandoc\pandoc.exe")
            or os.path.exists(os.path.expandvars(r"%LOCALAPPDATA%\Pandoc\pandoc.exe"))
        )
    )
    return {
        "chrome": bool(chrome),
        "latex": bool(latex),
        "pandoc": bool(pandoc),
    }


@router.post("/queries")
async def create_query(
    data: SearchQueryCreate, session: Session = Depends(get_session)
):
    query = SearchQuery(**data.model_dump())
    session.add(query)
    session.commit()
    session.refresh(query)
    return JSONResponse({"id": query.id})


@router.put("/queries/{query_id}")
async def update_query(
    query_id: int, data: SearchQueryUpdate, session: Session = Depends(get_session)
):
    query = session.get(SearchQuery, query_id)
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(query, key, val)
    session.add(query)
    session.commit()
    return JSONResponse({"ok": True})


@router.delete("/queries/{query_id}")
async def delete_query(query_id: int, session: Session = Depends(get_session)):
    query = session.get(SearchQuery, query_id)
    session.delete(query)
    session.commit()
    return JSONResponse({"ok": True})


@router.post("/setting/{key}")
async def update_setting(
    key: str, data: SettingUpdate, session: Session = Depends(get_session)
):
    setting = session.get(Setting, key)
    if setting:
        setting.value = data.value
    else:
        setting = Setting(key=key, value=data.value)
    session.add(setting)
    session.commit()
    return JSONResponse({"ok": True})
