import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("apply-buddy.compile")


def _find_exe(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        base = os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64")
        candidate = os.path.join(base, f"{name}.exe")
        if os.path.exists(candidate):
            return candidate
    return None


def latex_available() -> bool:
    return bool(_find_exe("latexmk") or _find_exe("pdflatex"))


def _find_pandoc() -> str | None:
    found = shutil.which("pandoc")
    if found:
        return found
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\Pandoc\pandoc.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Pandoc\pandoc.exe"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
    return None


def pandoc_available() -> bool:
    return _find_pandoc() is not None


def compile_latex_to_pdf(tex_path: Path, output_dir: Path) -> tuple[bool, str]:
    if not latex_available():
        return False, "LaTeX toolchain not found"

    try:
        pdflatex = _find_exe("pdflatex")
        if pdflatex:
            result = subprocess.run(
                [
                    pdflatex,
                    "-interaction=nonstopmode",
                    "-output-directory",
                    str(output_dir),
                    str(tex_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            subprocess.run(
                [
                    pdflatex,
                    "-interaction=nonstopmode",
                    "-output-directory",
                    str(output_dir),
                    str(tex_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            pdf_path = output_dir / f"{tex_path.stem}.pdf"
            if pdf_path.exists():
                return True, "Compiled successfully (pdflatex x2)"
            return False, result.stdout + result.stderr
        latexmk = _find_exe("latexmk")
        if latexmk:
            result = subprocess.run(
                [
                    latexmk,
                    "-pdf",
                    "-interaction=nonstopmode",
                    "-output-directory",
                    str(output_dir),
                    str(tex_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                pdf_path = output_dir / f"{tex_path.stem}.pdf"
                if pdf_path.exists():
                    return True, "Compiled successfully"
            return False, result.stdout + result.stderr
        return False, "No LaTeX executable found"
    except subprocess.TimeoutExpired:
        return False, "LaTeX compilation timed out"
    except Exception as e:
        return False, f"LaTeX compilation error: {e}"


def convert_markdown_to_docx(md_path: Path, output_dir: Path) -> tuple[bool, str]:
    pandoc_exe = _find_pandoc()
    if not pandoc_exe:
        return False, "Pandoc not found"
    try:
        docx_path = output_dir / f"{md_path.stem}.docx"
        result = subprocess.run(
            [pandoc_exe, str(md_path), "-o", str(docx_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and docx_path.exists():
            return True, "Converted to docx"
        return False, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Pandoc conversion timed out"
    except Exception as e:
        return False, f"Pandoc error: {e}"


def convert_markdown_to_pdf(md_path: Path, output_dir: Path) -> tuple[bool, str]:
    pandoc_exe = _find_pandoc()
    if pandoc_exe:
        pdf_engine = _find_exe("pdflatex") or shutil.which("wkhtmltopdf")
        if pdf_engine:
            try:
                pdf_path = output_dir / f"{md_path.stem}.pdf"
                cmd = [
                    pandoc_exe,
                    str(md_path),
                    "-o",
                    str(pdf_path),
                    f"--pdf-engine={pdf_engine}",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and pdf_path.exists():
                    return True, "Converted to pdf via pandoc"
                return False, result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                return False, "Pandoc PDF conversion timed out"
            except Exception as e:
                return False, f"Pandoc PDF error: {e}"
    return _convert_markdown_to_pdf_direct(md_path, output_dir)


def _convert_markdown_to_pdf_direct(md_path: Path, output_dir: Path) -> tuple[bool, str]:
    pdflatex = _find_exe("pdflatex")
    if not pdflatex:
        return False, "No PDF engine available (install pandoc or pdflatex)"

    md_text = md_path.read_text(encoding="utf-8")

    lines = md_text.split("\n")
    latex_lines = []
    in_list = False
    list_env = "itemize"
    needs_href = "](" in md_text

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "":
            if in_list:
                latex_lines.append("\\end{" + list_env + "}")
                in_list = False
            latex_lines.append("")
            i += 1
            continue

        if stripped.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                latex_lines.append("\\texttt{" + _escape_latex(lines[i]) + "}")
                i += 1
            i += 1
            continue

        if stripped.startswith("### "):
            if in_list:
                latex_lines.append("\\end{" + list_env + "}")
                in_list = False
            content = _convert_inline_markdown(_escape_latex(stripped[4:]))
            latex_lines.append("\\subsubsection*{" + content + "}")
            i += 1
            continue

        if stripped.startswith("## "):
            if in_list:
                latex_lines.append("\\end{" + list_env + "}")
                in_list = False
            content = _convert_inline_markdown(_escape_latex(stripped[3:]))
            latex_lines.append("\\subsection*{" + content + "}")
            i += 1
            continue

        if stripped.startswith("# "):
            if in_list:
                latex_lines.append("\\end{" + list_env + "}")
                in_list = False
            content = _convert_inline_markdown(_escape_latex(stripped[2:]))
            latex_lines.append("\\section*{" + content + "}")
            i += 1
            continue

        if stripped == "---" or stripped == "***" or stripped == "___":
            if in_list:
                latex_lines.append("\\end{" + list_env + "}")
                in_list = False
            latex_lines.append("\\hrule")
            i += 1
            continue

        if stripped.startswith(("- ", "* ")):
            content = _convert_inline_markdown(_escape_latex(stripped[2:]))
            if not in_list:
                in_list = True
                list_env = "itemize"
                latex_lines.append("\\begin{itemize}")
            latex_lines.append("\\item " + content)
            i += 1
            continue

        if stripped[0].isdigit() and ". " in stripped[:4]:
            content = _convert_inline_markdown(_escape_latex(stripped.split(". ", 1)[1]))
            if not in_list:
                in_list = True
                list_env = "enumerate"
                latex_lines.append("\\begin{enumerate}")
            latex_lines.append("\\item " + content)
            i += 1
            continue

        if in_list:
            latex_lines.append("\\end{" + list_env + "}")
            in_list = False

        content = _convert_inline_markdown(_escape_latex(stripped))
        latex_lines.append(content + "\\par")
        i += 1

    if in_list:
        latex_lines.append("\\end{" + list_env + "}")

    latex_body = "\n".join(latex_lines)

    latex_doc = _latex_document_template(latex_body, needs_href)

    tex_path = output_dir / f"{md_path.stem}_cl.tex"
    tex_path.write_text(latex_doc, encoding="utf-8")

    try:
        result = subprocess.run(
            [
                pdflatex,
                "-interaction=nonstopmode",
                "-output-directory",
                str(output_dir),
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        pdf_path = output_dir / f"{md_path.stem}_cl.pdf"
        if result.returncode == 0 and pdf_path.exists():
            final_pdf = output_dir / f"{md_path.stem}.pdf"
            if final_pdf.exists():
                final_pdf.unlink()
            pdf_path.rename(final_pdf)
            tex_path.unlink(missing_ok=True)
            _cleanup_aux_files(output_dir, f"{md_path.stem}_cl")
            return True, "Converted to pdf via pdflatex (direct)"
        return False, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Direct PDF conversion timed out"
    except Exception as e:
        return False, f"Direct PDF conversion error: {e}"


def _latex_document_template(body: str, needs_href: bool = False) -> str:
    packages = "\\usepackage{hyperref}\n" if needs_href else ""
    return f"""\\documentclass[11pt]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{parskip}}
{packages}\\pagestyle{{empty}}
\\begin{{document}}

{body}
\\end{{document}}"""


def _escape_latex(text: str) -> str:
    replacements = [
        ("\\", "\\textbackslash "),
        ("{", "\\{"),
        ("}", "\\}"),
        ("$", "\\$"),
        ("&", "\\&"),
        ("#", "\\#"),
        ("^", "\\textasciicircum "),
        ("_", "\\_"),
        ("%", "\\%"),
        ("~", "\\textasciitilde "),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _convert_inline_markdown(text: str) -> str:
    import re

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\\href{\2}{\1}", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\textit{\1}", text)
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
    return text


def _cleanup_aux_files(output_dir: Path, stem: str) -> None:
    for ext in [".aux", ".log", ".out"]:
        p = output_dir / f"{stem}{ext}"
        p.unlink(missing_ok=True)
