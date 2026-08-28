from unittest.mock import MagicMock, patch

from app.services.compile import (
    _cleanup_aux_files,
    _convert_inline_markdown,
    _convert_markdown_to_pdf_direct,
    _escape_latex,
    _find_exe,
    _find_pandoc,
    _latex_document_template,
    compile_latex_to_pdf,
    convert_markdown_to_docx,
    convert_markdown_to_pdf,
    latex_available,
    pandoc_available,
)


def test_find_exe_found(mock_shutil_which):
    result = _find_exe("pdflatex")
    assert result == "/usr/bin/pdflatex"


def test_find_exe_not_found(mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    result = _find_exe("nonexistent_tool")
    assert result is None


def test_latex_available_true(mock_shutil_which):
    assert latex_available() is True


def test_latex_available_false(mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    assert latex_available() is False


def test_find_pandoc_found(mock_shutil_which):
    result = _find_pandoc()
    assert result == "/usr/bin/pandoc"


def test_find_pandoc_not_found(mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    result = _find_pandoc()
    assert result is None


def test_pandoc_available_true(mock_shutil_which):
    assert pandoc_available() is True


def test_pandoc_available_false(mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    assert pandoc_available() is False


def test_escape_latex_special_characters():
    text = "\\ { } $ & # ^ _ % ~"
    result = _escape_latex(text)
    assert "\\textbackslash " in result
    assert "\\{" in result
    assert "\\}" in result
    assert "\\$" in result
    assert "\\&" in result
    assert "\\#" in result
    assert "\\textasciicircum " in result
    assert "\\_" in result
    assert "\\%" in result
    assert "\\textasciitilde " in result


def test_escape_latex_plain_text_unchanged():
    result = _escape_latex("Hello World 123")
    assert result == "Hello World 123"


def test_convert_inline_markdown_bold():
    result = _convert_inline_markdown("This is **bold** text")
    assert result == "This is \\textbf{bold} text"


def test_convert_inline_markdown_italic():
    result = _convert_inline_markdown("This is *italic* text")
    assert result == "This is \\textit{italic} text"


def test_convert_inline_markdown_code():
    result = _convert_inline_markdown("Use `code` here")
    assert result == "Use \\texttt{code} here"


def test_convert_inline_markdown_link():
    result = _convert_inline_markdown("[click here](https://example.com)")
    assert result == "\\href{https://example.com}{click here}"


def test_convert_inline_markdown_mixed():
    result = _convert_inline_markdown("**Bold** and *italic* with `code`")
    assert "\\textbf{Bold}" in result
    assert "\\textit{italic}" in result
    assert "\\texttt{code}" in result


def test_latex_document_template():
    result = _latex_document_template("Hello World")
    assert "\\documentclass[11pt]{article}" in result
    assert "\\usepackage[margin=1in]{geometry}" in result
    assert "\\usepackage{parskip}" in result
    assert "\\begin{document}" in result
    assert "Hello World" in result
    assert "\\end{document}" in result
    assert "hyperref" not in result


def test_latex_document_template_with_hyperref():
    result = _latex_document_template("Hello World", needs_href=True)
    assert "\\usepackage{hyperref}" in result


def test_cleanup_aux_files(tmp_path):
    stem = "test_file"
    for ext in [".aux", ".log", ".out"]:
        (tmp_path / f"{stem}{ext}").write_text("dummy")
    _cleanup_aux_files(tmp_path, stem)
    for ext in [".aux", ".log", ".out"]:
        assert not (tmp_path / f"{stem}{ext}").exists()


def test_cleanup_aux_files_missing_ok(tmp_path):
    _cleanup_aux_files(tmp_path, "nonexistent")
    assert True


def test_compile_latex_to_pdf_no_latex(tmp_path, mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    success, msg = compile_latex_to_pdf(tmp_path / "test.tex", tmp_path)
    assert success is False
    assert "LaTeX toolchain not found" in msg


def test_convert_markdown_to_docx_no_pandoc(tmp_path, mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    success, msg = convert_markdown_to_docx(tmp_path / "test.md", tmp_path)
    assert success is False
    assert "Pandoc not found" in msg


def test_convert_markdown_to_pdf_no_engine(tmp_path, mock_shutil_which_none, monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")
    success, msg = convert_markdown_to_pdf(md_path, tmp_path)
    assert success is False
    assert "No PDF engine available" in msg


def test_convert_markdown_to_pdf_direct_headings(tmp_path):
    md_path = tmp_path / "test.md"
    md_path.write_text("# Title\n\n## Section\n\n### Subsection\n\nBody text", encoding="utf-8")
    with (
        patch("app.services.compile._find_exe", return_value="/usr/bin/pdflatex"),
        patch("app.services.compile.subprocess.run") as mock_run,
    ):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test_cl.pdf").touch()
        success, msg = _convert_markdown_to_pdf_direct(md_path, tmp_path)
        assert success is True
        assert "pdflatex" in msg


def test_convert_markdown_to_pdf_direct_lists(tmp_path):
    md_path = tmp_path / "test.md"
    md_path.write_text("- Item 1\n- Item 2\n\n1. First\n2. Second", encoding="utf-8")
    with (
        patch("app.services.compile._find_exe", return_value="/usr/bin/pdflatex"),
        patch("app.services.compile.subprocess.run") as mock_run,
    ):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test_cl.pdf").touch()
        success, msg = _convert_markdown_to_pdf_direct(md_path, tmp_path)
        assert success is True


def test_convert_markdown_to_pdf_direct_code_block(tmp_path):
    md_path = tmp_path / "test.md"
    md_path.write_text("Text\n\n```\ncode block\n```\n\nMore text", encoding="utf-8")
    with (
        patch("app.services.compile._find_exe", return_value="/usr/bin/pdflatex"),
        patch("app.services.compile.subprocess.run") as mock_run,
    ):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test_cl.pdf").touch()
        success, msg = _convert_markdown_to_pdf_direct(md_path, tmp_path)
        assert success is True


def test_convert_markdown_to_pdf_direct_horizontal_rule(tmp_path):
    md_path = tmp_path / "test.md"
    md_path.write_text("Before\n\n---\n\nAfter", encoding="utf-8")
    with (
        patch("app.services.compile._find_exe", return_value="/usr/bin/pdflatex"),
        patch("app.services.compile.subprocess.run") as mock_run,
    ):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test_cl.pdf").touch()
        success, msg = _convert_markdown_to_pdf_direct(md_path, tmp_path)
        assert success is True


def test_convert_markdown_to_pdf_direct_no_pdflatex(tmp_path):
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")
    with patch("app.services.compile._find_exe", return_value=None):
        success, msg = _convert_markdown_to_pdf_direct(md_path, tmp_path)
        assert success is False
        assert "No PDF engine available" in msg


def test_compile_latex_to_pdf_with_pdflatex(tmp_path, mock_shutil_which):
    tex_path = tmp_path / "test.tex"
    tex_path.write_text(
        "\\documentclass{article}\\begin{document}Test\\end{document}", encoding="utf-8"
    )
    with patch("app.services.compile.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test.pdf").touch()
        success, msg = compile_latex_to_pdf(tex_path, tmp_path)
        assert success is True
        assert "Compiled successfully" in msg


def test_compile_latex_to_pdf_timeout(tmp_path, mock_shutil_which):
    tex_path = tmp_path / "test.tex"
    tex_path.write_text(
        "\\documentclass{article}\\begin{document}Test\\end{document}", encoding="utf-8"
    )
    with patch("app.services.compile.subprocess.run") as mock_run:
        mock_run.side_effect = __import__("subprocess").TimeoutExpired(cmd="pdflatex", timeout=120)
        success, msg = compile_latex_to_pdf(tex_path, tmp_path)
        assert success is False
        assert "timed out" in msg


def test_convert_markdown_to_docx_pandoc_success(tmp_path, mock_shutil_which):
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")
    with patch("app.services.compile.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test.docx").touch()
        success, msg = convert_markdown_to_docx(md_path, tmp_path)
        assert success is True
        assert "docx" in msg


def test_convert_markdown_to_pdf_via_pandoc(tmp_path):
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test", encoding="utf-8")
    with (
        patch("app.services.compile._find_pandoc", return_value="/usr/bin/pandoc"),
        patch("app.services.compile._find_exe", return_value="/usr/bin/pdflatex"),
        patch("app.services.compile.subprocess.run") as mock_run,
    ):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        (tmp_path / "test.pdf").touch()
        success, msg = convert_markdown_to_pdf(md_path, tmp_path)
        assert success is True
        assert "pandoc" in msg
