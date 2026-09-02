from pathlib import Path

from app.services.cv_diff import (
    _cleanup_aux_files,
    _generate_diff_body,
    _inject_style_before_document,
    _is_wrappable,
    _mark_added_line,
    _mark_removed_line,
    _tokenize,
    _word_marks,
    generate_cv_diff,
)

MASTER_CV = """\\documentclass[11pt]{article}
\\usepackage{enumitem}

\\begin{document}

\\section{Summary}
Business analyst skilled in dashboards, reporting, and stakeholder communication.

\\section{Experience}
\\resumeItem{Built dashboards in Power BI}
\\resumeItem{Automated reports with SQL}

\\end{document}
"""

TAILORED_CV = MASTER_CV.replace("Built dashboards in Power BI", "Owned dashboards in Power BI")


def test_tokenize_splits_commands_braces_and_words():
    assert _tokenize(r"\resumeItem{Built dashboards}") == [
        "\\resumeItem",
        "{",
        "Built",
        " ",
        "dashboards",
        "}",
    ]


def test_word_marks_marks_only_changed_words():
    marks = _word_marks("Built dashboards in Power BI", "Owned dashboards in Power BI")
    assert marks is not None
    joined = "".join(marks)
    assert r"\DIFdel{Built}" in joined
    assert r"\DIFadd{Owned}" in joined
    assert r"\DIFdel{Built} \DIFadd{Owned}" in joined
    assert "dashboards in Power BI" in joined


def test_word_marks_returns_none_for_unbalanced_brace_span():
    assert _word_marks(r"\textbf{alpha}", "alpha") is None


def test_word_marks_returns_none_for_command_span():
    assert _word_marks(r"\textbf bold", "bold") is None


def test_word_marks_allows_balanced_word_spans():
    marks = _word_marks(r"\resumeItem{Built dashboards}", r"\resumeItem{Owned dashboards}")
    assert marks is not None
    assert r"\resumeItem{" in "".join(marks)


def test_is_wrappable_rules():
    assert _is_wrappable("Built dashboards with SQL")
    assert not _is_wrappable(r"\resumeItem{Built dashboards}")
    assert not _is_wrappable("{Montreal, Canada}")
    assert not _is_wrappable("[leftmargin=0.05in]")
    assert not _is_wrappable("100% sure")
    assert not _is_wrappable("unbalanced {brace")


def test_mark_removed_line_strikes_plain_text():
    assert _mark_removed_line("Built dashboards with SQL") == "\\DIFdel{Built dashboards with SQL}"


def test_mark_removed_line_leaves_structural_lines_raw():
    line = r"\resumeSubheading{Engineer}{Jan 2024}{Acme}{Berlin}"
    assert _mark_removed_line(line) == line


def test_mark_added_line_wraps_plain_text():
    assert _mark_added_line("Owned dashboards") == "\\DIFadd{Owned dashboards}"


def test_generate_diff_body_word_level_for_equal_line_counts():
    body = _generate_diff_body(
        "\\resumeItem{Built dashboards in Power BI}\n",
        "\\resumeItem{Owned dashboards in Power BI}\n",
    )
    assert r"\DIFdel{Built" in body
    assert r"\DIFadd{Owned" in body
    assert "dashboards in Power BI" in body


def test_generate_diff_body_block_delete_keeps_structural_lines_raw():
    body = _generate_diff_body(
        "\\resumeSubheading{Engineer}{Jan 2024}{Acme}{Berlin}\n\\resumeItem{Keep me}\n",
        "\\resumeItem{Keep me}\n",
    )
    assert r"\DIFdelbegin" in body
    assert r"\resumeSubheading{Engineer}{Jan 2024}{Acme}{Berlin}" in body
    assert r"\DIFdelend" in body


def test_generate_diff_body_plain_delete_is_struck_through():
    body = _generate_diff_body(
        "Old summary line\n\\resumeItem{Keep me}\n", "\\resumeItem{Keep me}\n"
    )
    assert r"\DIFdel{Old summary line}" in body


def test_generate_diff_body_plain_lines_group_old_then_new():
    body = _generate_diff_body(
        "Old summary line one\nOld summary line two\n",
        "New summary line one\nNew summary line two\n",
    )
    assert r"\DIFdel{Old summary line one}" in body
    assert r"\DIFdel{Old summary line two}" in body
    assert r"\DIFadd{New summary line one}" in body
    assert r"\DIFadd{New summary line two}" in body
    assert body.index("Old summary line two") < body.index("New summary line one")


def test_generate_diff_body_unbalanced_replace_marks_extra_new_line():
    body = _generate_diff_body(
        "\\resumeItem{Alpha tracker}\n\\resumeItem{Beta report}\n",
        (
            "\\resumeItem{Alpha tracker with alerts}\n"
            "\\resumeItem{Beta report with exports}\n"
            "\\resumeItem{Gamma dashboard}\n"
        ),
    )
    assert r"\DIFadd{with alerts}" in body
    assert r"\DIFadd{with exports}" in body
    assert r"\DIFaddbegin" in body
    assert "Gamma" in body
    assert r"\DIFdel" not in body


def test_inject_style_before_document_keeps_preamble_intact():
    preamble = "\\documentclass{article}\n\\usepackage{enumitem}\n\\begin{document}\n"
    result = _inject_style_before_document(preamble)
    assert result.index("\\documentclass") < result.index(r"\usepackage[normalem]{ulem}")
    assert result.index(r"\usepackage[normalem]{ulem}") < result.rfind(r"\begin{document}")
    assert r"\definecolor{DIFdel}" in result
    assert r"\sout{#1}" in result


def test_generate_cv_diff_writes_tex_and_returns_pdf(tmp_path, monkeypatch):
    captured: dict[str, str] = {}

    def fake_compile(tex_path, output_dir):
        captured["tex"] = Path(tex_path).read_text(encoding="utf-8")
        pdf = Path(output_dir) / "cv_diff.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        return True, "ok"

    monkeypatch.setattr("app.services.cv_diff.compile_latex_to_pdf", fake_compile)

    original = tmp_path / "master.tex"
    tailored = tmp_path / "tailored.tex"
    original.write_text(MASTER_CV, encoding="utf-8")
    tailored.write_text(TAILORED_CV, encoding="utf-8")

    result = generate_cv_diff(original, tailored, tmp_path / "out")

    assert result == tmp_path / "out" / "cv_diff.pdf"
    tex = captured["tex"]
    assert "\\documentclass[11pt]{article}" in tex
    assert "\\usepackage{enumitem}" in tex
    assert r"\resumeItem{" in tex
    assert r"\DIFdel{Built" in tex
    assert r"\DIFadd{Owned" in tex
    assert r"\sout{#1}" in tex
    assert "\\end{document}" in tex


def test_generate_cv_diff_identical_bodies_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.cv_diff.compile_latex_to_pdf",
        lambda *_: (_ for _ in ()).throw(AssertionError("should not compile")),
    )
    cv = tmp_path / "cv.tex"
    cv.write_text(MASTER_CV, encoding="utf-8")
    assert generate_cv_diff(cv, cv, tmp_path / "out") is None


def test_generate_cv_diff_missing_files_return_none(tmp_path):
    missing = tmp_path / "missing.tex"
    cv = tmp_path / "cv.tex"
    cv.write_text(MASTER_CV, encoding="utf-8")
    assert generate_cv_diff(missing, cv, tmp_path / "out") is None
    assert generate_cv_diff(cv, missing, tmp_path / "out") is None


def test_generate_cv_diff_compilation_failure_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.cv_diff.compile_latex_to_pdf", lambda *_: (False, "boom"))
    original = tmp_path / "master.tex"
    tailored = tmp_path / "tailored.tex"
    original.write_text(MASTER_CV, encoding="utf-8")
    tailored.write_text(TAILORED_CV, encoding="utf-8")
    assert generate_cv_diff(original, tailored, tmp_path / "out") is None


def test_cleanup_aux_files_removes_only_expected_suffixes(tmp_path):
    stem = "cv_diff"
    for ext in [".aux", ".log", ".out", ".tex"]:
        (tmp_path / f"{stem}{ext}").write_text("x", encoding="utf-8")
    (tmp_path / "cv_diff.pdf").write_bytes(b"%PDF-1.4 fake")
    _cleanup_aux_files(tmp_path, stem)
    assert not (tmp_path / f"{stem}.aux").exists()
    assert not (tmp_path / f"{stem}.log").exists()
    assert not (tmp_path / f"{stem}.out").exists()
    assert not (tmp_path / f"{stem}.tex").exists()
    assert (tmp_path / "cv_diff.pdf").exists()
