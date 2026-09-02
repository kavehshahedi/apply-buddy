import difflib
import logging
import re
from pathlib import Path

from app.services.compile import compile_latex_to_pdf

logger = logging.getLogger("apply-buddy.cv_diff")

_DIF_STYLE = r"""
% latexdiff-style markup injected before \begin{document}
\usepackage[normalem]{ulem}

\definecolor{DIFadd}{rgb}{0,0,1}
\definecolor{DIFdel}{rgb}{0.7,0,0}

\newcommand{\DIFadd}[1]{\textcolor{DIFadd}{#1}}
\newcommand{\DIFdel}[1]{\textcolor{DIFdel}{\sout{#1}}}
\newcommand{\DIFaddbegin}{\color{DIFadd}}
\newcommand{\DIFaddend}{\normalcolor}
\newcommand{\DIFdelbegin}{\color{DIFdel}}
\newcommand{\DIFdelend}{\normalcolor}
\newcommand{\DIFaddword}{\color{DIFadd}}
\newcommand{\DIFaddwordend}{\normalcolor}
\newcommand{\DIFdelword}{\color{DIFdel}}
\newcommand{\DIFdelwordend}{\normalcolor}

"""

_DIF_STYLE_ANCHOR = r"\begin{document}"

_TOKEN_RE = re.compile(r"(\\[a-zA-Z]+|[\{\}]|\w+|[^\s\w{}]+|\s+)")


def _inject_style_before_document(preamble: str) -> str:
    idx = preamble.rfind(_DIF_STYLE_ANCHOR)
    if idx == -1:
        return preamble + _DIF_STYLE
    return preamble[:idx] + _DIF_STYLE + "\n" + preamble[idx:]


def _tokenize(line: str) -> list[str]:
    return [m.group() for m in _TOKEN_RE.finditer(line)]


def _span_brace_safe(tokens: list[str]) -> bool:
    depth = 0
    for token in tokens:
        depth += token.count("{") - token.count("}")
        if depth < 0:
            return False
    return depth == 0


def _line_braces_balanced(line: str) -> bool:
    return line.count("{") == line.count("}")


def _is_wrappable(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("\\", "{", "[")):
        return False
    if "%" in line:
        return False
    return _line_braces_balanced(line)


_STRIKE_UNSAFE_CHARS = frozenset(
    chr(92)
    + chr(123)
    + chr(125)
    + chr(37)
    + chr(38)
    + chr(36)
    + chr(35)
    + chr(95)
    + chr(94)
    + chr(126)
)


_PLAIN_SPAN_RE = re.compile(r"^[^\\{}%&$#_^~]+$")


def _span_is_plain(tokens: list[str]) -> bool:
    return all(not (set(tok) & _STRIKE_UNSAFE_CHARS) for tok in tokens)


def _span_markable(tokens: list[str]) -> bool:
    return bool(tokens) and _span_brace_safe(tokens) and _span_is_plain(tokens)


_NO_SPACE_BEFORE = (".", ",", ";", ":", "!", "?", ")", "]", "}")


_STRUCTURAL_TOKEN_RE = re.compile(r"[{}\\]+")


def _is_structural_token(token: str) -> bool:
    return bool(_STRUCTURAL_TOKEN_RE.fullmatch(token))


def _word_marks(old_line: str, new_line: str) -> list[str] | None:
    """Word-level markup for a reworded line pair, or None when unsafe.

    Returns None when a changed span contains unbalanced braces, commands, or
    special characters -- the caller then falls back to switch-colored whole
    lines, which keeps the raw source executing in its original context.  A
    removed span made purely of closing braces is structural: the tailored
    text supersedes it, so only the added side is marked.
    """
    old_tokens = _tokenize(old_line)
    new_tokens = _tokenize(new_line)
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append("".join(old_tokens[i1:i2]))
            continue
        removed = old_tokens[i1:i2] if tag in ("delete", "replace") else []
        added = new_tokens[j1:j2] if tag in ("insert", "replace") else []
        structural_removal = (
            bool(removed) and bool(added) and all(token == "}" for token in removed)
        )
        if removed and not structural_removal and not _span_markable(removed):
            return None
        if added and not _span_markable(added):
            if removed or not all(_is_structural_token(token) for token in added):
                return None
            parts.append("".join(added))
            continue
        old_lead, old_content, old_trail = _split_ws("".join(removed))
        new_lead, new_content, new_trail = _split_ws("".join(added))
        if not structural_removal:
            if old_lead:
                parts.append(old_lead)
            if old_content:
                parts.append(r"\DIFdel{" + old_content + "}")
            if old_trail:
                parts.append(old_trail)
        if new_lead:
            parts.append(new_lead)
        if new_content:
            needs_space = not (
                (parts and parts[-1].endswith((" ", "\t", "~", "\n")))
                or new_content.startswith(_NO_SPACE_BEFORE)
            )
            if needs_space:
                parts.append(" ")
            parts.append(r"\DIFadd{" + new_content + "}")
        if new_trail:
            parts.append(new_trail)
    return parts


def _split_ws(text: str) -> tuple[str, str, str]:
    """Split leading whitespace, content, and trailing whitespace apart."""
    stripped = text.strip()
    if not stripped:
        return text, "", ""
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    return lead, stripped, trail


def _mark_removed_line(line: str) -> str:
    if _is_wrappable(line):
        return r"\DIFdel{" + line.rstrip() + "}"
    return line


def _mark_added_line(line: str) -> str:
    if _is_wrappable(line):
        return r"\DIFadd{" + line + "}"
    return line


def _mark_removed_block(lines: list[str]) -> list[str]:
    return (
        [r"\DIFdelbegin" + "\n"]
        + [_mark_removed_line(line) + "\n" for line in lines]
        + [r"\DIFdelend" + "\n"]
    )


def _mark_added_block(lines: list[str]) -> list[str]:
    return (
        [r"\DIFaddbegin" + "\n"]
        + [_mark_added_line(line) + "\n" for line in lines]
        + [r"\DIFaddend" + "\n"]
    )


_MERGE_RATIO = 0.6


_WORD_TOKEN_RE = re.compile(r"\w+")


def _pair_is_similar(old_line: str, new_line: str) -> bool:
    """Compare word content only: lines that merely share spacing or
    punctuation must not be merged into interleaved word-level markup."""
    old_words = _WORD_TOKEN_RE.findall(old_line)
    new_words = _WORD_TOKEN_RE.findall(new_line)
    matcher = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
    return matcher.ratio() >= _MERGE_RATIO


def _separated_lines_markup(old_line: str, new_line: str) -> str:
    parts = [
        r"\DIFdelbegin",
        old_line.rstrip(),
        r"\DIFdelend",
        r"\DIFaddbegin",
        new_line.rstrip(),
        r"\DIFaddend",
    ]
    return "\n".join(parts) + "\n"


def _is_resume_item_pair(old_line: str, new_line: str) -> bool:
    return old_line.lstrip().startswith(r"\resumeItem") and new_line.lstrip().startswith(
        r"\resumeItem"
    )


def _marks_have_removals(marks: list[str]) -> bool:
    return any(r"\DIFdel{" in part for part in marks)


def _mergeable_pair(old_line: str, new_line: str, marks: list[str] | None) -> bool:
    """Work-experience bullets merge inline when similar; pairs with
    nothing visibly removed (invisible structure only) render the tailored
    line once, plain.  Every other pair is shown as two separated blocks."""
    if marks is None:
        return False
    if not _marks_have_removals(marks):
        return True
    return _is_resume_item_pair(old_line, new_line) and _pair_is_similar(old_line, new_line)


def _replaced_line(old_line: str, new_line: str) -> str:
    """Merged inline markup for work-experience pairs, struck/blue otherwise."""
    marks = _word_marks(old_line, new_line)
    if _mergeable_pair(old_line, new_line, marks):
        assert marks is not None
        return "".join(marks) + "\n"
    return _separated_lines_markup(old_line, new_line)


def _replaced_block(old_lines: list[str], new_lines: list[str]) -> list[str]:
    """Pair block lines by position: work-experience bullets merge inline
    when similar; pairs with no visible removals render once, plain.
    Everything else collects into one removed group and one added group."""
    rows: list[str] = []
    separated_old: list[str] = []
    separated_new: list[str] = []
    paired = min(len(old_lines), len(new_lines))

    def flush_separated() -> None:
        removed_present = bool(separated_old)
        if separated_old:
            rows.extend(_mark_removed_block(separated_old))
            separated_old.clear()
        if separated_new:
            if removed_present:
                rows.append("\n")
            add_rows = _mark_added_block(separated_new)
            if removed_present:
                add_rows[1] = r"\noindent" + add_rows[1]
            rows.extend(add_rows)
            separated_new.clear()

    for index in range(paired):
        old_line = old_lines[index]
        new_line = new_lines[index]
        marks = _word_marks(old_line, new_line)
        if _mergeable_pair(old_line, new_line, marks) and marks is not None:
            flush_separated()
            rows.append("".join(marks) + "\n")
        else:
            separated_old.append(old_line)
            separated_new.append(new_line)
    if paired < len(old_lines):
        separated_old.extend(old_lines[paired:])
    if paired < len(new_lines):
        separated_new.extend(new_lines[paired:])
    flush_separated()
    return rows


def _generate_diff_body(original: str, tailored: str) -> str:
    orig_lines = original.splitlines(keepends=True)
    tail_lines = tailored.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, orig_lines, tail_lines, autojunk=False)
    out: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.extend(orig_lines[i1:i2])
        elif tag == "delete":
            out.extend(_mark_removed_block([line.rstrip("\n\r") for line in orig_lines[i1:i2]]))
        elif tag == "insert":
            out.extend(_mark_added_block([line.rstrip("\n\r") for line in tail_lines[j1:j2]]))
        else:
            old_block = [line.rstrip("\n\r") for line in orig_lines[i1:i2]]
            new_block = [line.rstrip("\n\r") for line in tail_lines[j1:j2]]
            out.extend(_replaced_block(old_block, new_block))

    return "".join(out)


def generate_cv_diff(
    original_path: Path,
    tailored_path: Path,
    output_dir: Path,
) -> Path | None:
    if not original_path.exists():
        logger.warning("Original CV not found at %s", original_path)
        return None
    if not tailored_path.exists():
        logger.warning("Tailored CV not found at %s", tailored_path)
        return None

    original_tex = original_path.read_text(encoding="utf-8")
    tailored_tex = tailored_path.read_text(encoding="utf-8")

    doc_start = original_tex.find(r"\begin{document}")
    doc_end = original_tex.rfind(r"\end{document}")
    if doc_start == -1 or doc_end == -1:
        logger.warning("Could not find document boundaries in original CV")
        return None

    original_body = original_tex[doc_start + len(r"\begin{document}") : doc_end]

    td_start = tailored_tex.find(r"\begin{document}")
    td_end = tailored_tex.rfind(r"\end{document}")
    if td_start == -1 or td_end == -1:
        logger.warning("Could not find document boundaries in tailored CV")
        return None

    tailored_body = tailored_tex[td_start + len(r"\begin{document}") : td_end]

    if original_body == tailored_body:
        logger.info("No differences between original and tailored CV")
        return None

    original_preamble = original_tex[:doc_start]
    diff_preamble = _inject_style_before_document(original_preamble)
    diff_body = _generate_diff_body(original_body, tailored_body)
    diff_tex = (
        diff_preamble + "\n" + r"\begin{document}" + "\n" + diff_body + "\n" + r"\end{document}"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    diff_tex_path = output_dir / "cv_diff.tex"
    diff_tex_path.write_text(diff_tex, encoding="utf-8")

    success, msg = compile_latex_to_pdf(diff_tex_path, output_dir)
    if success:
        diff_pdf_path = output_dir / "cv_diff.pdf"
        if diff_pdf_path.exists():
            _cleanup_aux_files(output_dir, "cv_diff")
            logger.info("CV diff PDF generated at %s", diff_pdf_path)
            return diff_pdf_path
        logger.warning("cv_diff.pdf not found after compilation")
        return None

    logger.warning("CV diff compilation failed: %s", msg[:200])
    return None


def _cleanup_aux_files(output_dir: Path, stem: str) -> None:
    for ext in [".aux", ".log", ".out", ".tex"]:
        (output_dir / f"{stem}{ext}").unlink(missing_ok=True)
