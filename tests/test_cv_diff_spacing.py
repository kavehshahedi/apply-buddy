"""Tests for diff block separation and append-only rewording markup."""

from app.services.cv_diff import (
    _generate_diff_body,
    _replaced_block,
    _replaced_line,
    _word_marks,
)

OLD_APPEND = "\\resumeItem{Managed high-volume client inquiries and follow-ups}\n"
NEW_APPEND = (
    "\\resumeItem{Managed high-volume client inquiries and follow-ups, ensuring issue\n"
    "resolution and client satisfaction}\n"
)

OLD_SKILLS = (
    "\\resumeItemListStart\n"
    "\\resumeItem{Built dashboards in Power BI}\n"
    "\\resumeItem{Automated reporting with SQL}\n"
    "\\resumeItemListEnd\n"
)
NEW_SKILLS = (
    "\\resumeItemListStart\n"
    "\\resumeItem{Owned dashboards in Power BI}\n"
    "\\resumeItem{Automated reporting pipelines with SQL and Python}\n"
    "\\resumeItem{Tracked KPIs and follow-ups}\n"
    "\\resumeItemListEnd\n"
)

OLD_OFF_TOPIC = "\\resumeItem{Built dashboards in Power BI}"
NEW_OFF_TOPIC = "\\resumeItem{Greeted customers and assessed needs}"


def test_replaced_block_separates_dissimilar_lines_tightly():
    rows = _replaced_block(
        [OLD_OFF_TOPIC, "\\resumeItem{Automated reporting with SQL}"],
        [NEW_OFF_TOPIC, "\\resumeItem{Maintained merchandise displays}"],
    )
    text = "".join(rows)
    lines = text.split("\n")
    assert lines.count(r"\DIFdelbegin") == 1
    assert lines.count(r"\DIFaddbegin") == 1
    del_end = lines.index(r"\DIFdelend")
    add_begin = lines.index(r"\DIFaddbegin")
    assert lines[del_end + 1] == ""
    assert lines[add_begin + 1].startswith(r"\noindent")
    assert "" not in lines[add_begin + 1 : add_begin + 3]


def test_replaced_block_merges_append_only_pair_inline():
    rows = _replaced_block([OLD_APPEND], [NEW_APPEND])
    text = "".join(rows)
    assert r"\DIFadd{, ensuring issue" in text
    assert r"\DIFdel" not in text
    assert "Managed high-volume client inquiries and follow-ups" in text


def test_replaced_block_groups_dissimilar_lines_before_append_lines():
    rows = _replaced_block(
        [OLD_OFF_TOPIC, OLD_APPEND],
        [NEW_OFF_TOPIC, NEW_APPEND],
    )
    text = "".join(rows)
    assert text.index(r"\DIFdelbegin") < text.index(r"\DIFaddbegin")
    assert r"\DIFdel{" not in text[text.index(r"\DIFdelend") :]


def test_word_marks_no_space_before_appended_punctuation():
    marks = _word_marks(
        "Managed high-volume client inquiries and follow-ups in a fast-paced environment",
        (
            "Managed high-volume client inquiries and follow-ups in a fast-paced environment, "
            "ensuring issue resolution and client satisfaction"
        ),
    )
    assert marks is not None
    joined = "".join(marks)
    assert r"\DIFadd{, ensuring issue resolution and client satisfaction}" in joined
    assert "environment , ensuring" not in joined
    assert "fast-paced environment" in joined


def test_word_marks_structural_close_is_superseded_by_added_text():
    marks = _word_marks(
        "\\resumeItem{Managed high-volume client inquiries and follow-ups}",
        "\\resumeItem{Managed high-volume client inquiries and follow-ups, ensuring focus}",
    )
    assert marks is not None
    joined = "".join(marks)
    assert r"\DIFdel" not in joined
    assert r"\DIFadd{, ensuring focus}" in joined
    assert joined.startswith("\\resumeItem{Managed high-volume")
    assert joined.endswith("}")


def test_replaced_line_separates_dissimilar_pair_without_extra_spacing():
    rendered = _replaced_line(OLD_OFF_TOPIC, NEW_OFF_TOPIC)
    lines = rendered.split("\n")
    assert lines == [
        r"\DIFdelbegin",
        OLD_OFF_TOPIC,
        r"\DIFdelend",
        r"\DIFaddbegin",
        NEW_OFF_TOPIC,
        r"\DIFaddend",
        "",
    ]


def test_generate_diff_body_append_keeps_shared_text_plain():
    body = _generate_diff_body(OLD_APPEND, NEW_APPEND)
    assert r"\DIFadd{, ensuring issue" in body
    assert r"\DIFdel" not in body
    assert "Managed high-volume client inquiries and follow-ups" in body


def test_replaced_block_plain_lines_group_old_then_new():
    old = "\\textbf{Communication:} Partner outreach, stakeholder communication, client service, cross-team collaboration"
    new = "\\textbf{Merchandising:} Stock maintenance, product display, signage, inventory organization"
    rows = _replaced_block([old], [new])
    text = "".join(rows)
    assert r"\DIFdelbegin" in text
    assert r"\DIFaddbegin" in text
    assert r"\DIFadd{" not in text
    assert text.index("Communication") < text.index("Merchandising")


def test_generate_diff_body_block_rework_merges_similar_pairs():
    body = _generate_diff_body(OLD_SKILLS, NEW_SKILLS)
    assert r"\DIFdel{Built}" in body
    assert r"\DIFadd{Owned}" in body
    assert r"\DIFaddbegin" in body
    assert "Tracked KPIs and follow-ups" in body
