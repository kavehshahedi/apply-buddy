from unittest.mock import patch

from app.services.job_chat import build_context
from app.services.llm import LLMError


def test_chat_404(client, db_session):
    resp = client.post("/chat/99999", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 404


def test_chat_sends_job_context_and_images(client, sample_job):
    image = "data:image/png;base64,AAAA"
    with patch("app.services.job_chat.chat_completion", return_value="**ok**") as mock:
        resp = client.post(
            f"/chat/{sample_job.id}",
            json={"messages": [{"role": "user", "content": "Fit?", "images": [image]}]},
        )
    assert resp.status_code == 200
    assert resp.json() == {"reply": "**ok**"}
    system, user = mock.call_args.args[0]
    assert sample_job.title in system["content"]
    assert user["content"][0] == {"type": "text", "text": "Fit?"}
    assert user["content"][1]["image_url"]["url"] == image


def test_chat_rejects_non_image_urls(client, sample_job):
    resp = client.post(
        f"/chat/{sample_job.id}",
        json={"messages": [{"role": "user", "content": "x", "images": ["http://evil"]}]},
    )
    assert resp.status_code == 422


def test_chat_llm_error_returns_502(client, sample_job):
    with patch("app.services.job_chat.chat_completion", side_effect=LLMError("down")):
        resp = client.post(
            f"/chat/{sample_job.id}", json={"messages": [{"role": "user", "content": "hi"}]}
        )
    assert resp.status_code == 502


def test_build_context_attachments(sample_job, tmp_path):
    cv = tmp_path / "cv.tex"
    cv.write_text("TAILORED_CV")
    cl = tmp_path / "cl.md"
    cl.write_text("MY_LETTER")
    sample_job.tailored_cv_path = str(cv)
    sample_job.cover_letter_path = str(cl)

    ctx = build_context(sample_job, "tailored", include_cover_letter=True)
    assert "TAILORED_CV" in ctx and "MY_LETTER" in ctx
    ctx = build_context(sample_job, "none", include_cover_letter=False)
    assert "TAILORED_CV" not in ctx and "MY_LETTER" not in ctx
    assert sample_job.description in ctx


def test_chat_uses_configured_model_and_prompt(client, db_session, sample_job):
    from app.models import Setting

    db_session.add(Setting(key="prompt_job_chat_model", value="gpt-vision"))
    db_session.add(Setting(key="prompt_job_chat", value="CUSTOM_PROMPT"))
    db_session.commit()
    with patch("app.services.job_chat.chat_completion", return_value="ok") as mock:
        client.post(
            f"/chat/{sample_job.id}", json={"messages": [{"role": "user", "content": "hi"}]}
        )
    assert mock.call_args.kwargs["model"] == "gpt-vision"
    assert mock.call_args.args[0][0]["content"].startswith("CUSTOM_PROMPT")
