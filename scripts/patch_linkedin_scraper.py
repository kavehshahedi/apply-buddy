"""
Patch linkedin_jobs_scraper to fix selectors broken by LinkedIn's DOM overhaul
(~Sep 2026: all CSS class names fully hashed, data-occludable-job-id removed,
job cards changed from li[data-occludable-job-id] to div[role=button][componentkey]).

Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

TARGET = "linkedin_jobs_scraper/strategies/authenticated_strategy.py"

PATCHES = [
    # ------------------------------------------------------------------
    # 1. Container gate: .scaffold-layout__list → componentkey selector.
    #    LinkedIn removed data-occludable-job-id; job cards now carry
    #    componentkey="job-card-component-ref-<id>" on div[role="button"].
    # ------------------------------------------------------------------
    (
        "container = 'li[data-occludable-job-id]'",
        "container = '[componentkey^=\"job-card-component-ref-\"]'",
    ),
    # ------------------------------------------------------------------
    # 2. Job-items selector: same componentkey pattern.
    # ------------------------------------------------------------------
    (
        "job_items = f'li[{JOB_ID_ATTRIBUTE}]'",
        "job_items = '[componentkey^=\"job-card-component-ref-\"]'",
    ),
    # ------------------------------------------------------------------
    # 3. Per-job selector builder: target componentkey="job-card-component-ref-<id>".
    # ------------------------------------------------------------------
    (
        "return f'li[{JOB_ID_ATTRIBUTE}=\"{job_id}\"]'",
        "return f'[componentkey=\"job-card-component-ref-{job_id}\"]'",
    ),
    # ------------------------------------------------------------------
    # 4. Description selector: .jobs-description is gone.
    #    The new UI uses id="JobDetails_AboutTheJob_{job_id}" on the
    #    description section — the id prefix is stable across all jobs.
    # ------------------------------------------------------------------
    (
        "description = '.jobs-description'",
        "description = '[id^=\"JobDetails_AboutTheJob_\"]'",
    ),
    # ------------------------------------------------------------------
    # 4b. Same fix for installs that already had the intermediate selector
    #     (#job-details etc.) from a prior patch run.
    # ------------------------------------------------------------------
    (
        "description = '#job-details, .jobs-description__content, .jobs-box__html-content'",
        "description = '[id^=\"JobDetails_AboutTheJob_\"]'",
    ),
    # ------------------------------------------------------------------
    # 4c. Panel title: .job-details-jobs-unified-top-card__job-title gone.
    #     The panel now renders a canonical job link whose text is the title.
    # ------------------------------------------------------------------
    (
        "panel_title = '.job-details-jobs-unified-top-card__job-title'",
        "panel_title = 'a[href*=\"/jobs/view/\"]'",
    ),
    # ------------------------------------------------------------------
    # 4d. Panel company: .job-details-jobs-unified-top-card__company-name gone.
    #     Company name is now a link to /company/{slug}/.
    # ------------------------------------------------------------------
    (
        "panel_company = '.job-details-jobs-unified-top-card__company-name'",
        "panel_company = 'a[href*=\"/company/\"]'",
    ),
    # ------------------------------------------------------------------
    # 5. __load_job_details: drop the detailsPanel dependency entirely.
    # ------------------------------------------------------------------
    (
        """\
                        const detailsPanel = document.querySelector(arguments[1]);
                        const description = document.querySelector(arguments[2]);
                        return detailsPanel && detailsPanel.innerHTML.includes(arguments[0]) &&
                            description && description.innerText.length > 0;\
""",
        """\
                        const description = document.querySelector(arguments[1]);
                        return document.body.innerHTML.includes(arguments[0]) &&
                            description && description.innerText.length > 0;\
""",
    ),
    # Remove the now-unused Selectors.detailsPanel argument from the call.
    (
        """\
                    job_id,
                    Selectors.detailsPanel,
                    Selectors.description)

                if loaded:\
""",
        """\
                    job_id,
                    Selectors.description)

                if loaded:\
""",
    ),
    # ------------------------------------------------------------------
    # 6. __wait_for_job_panel: replace panel.innerHTML check with URL check.
    # ------------------------------------------------------------------
    (
        """\
                        const panel = document.querySelector(arguments[1]);
                        const titleEl = document.querySelector(arguments[2]);
                        const descEl = document.querySelector(arguments[3]);

                        const hasId = panel ? panel.innerHTML.includes(arguments[0]) : false;\
""",
        """\
                        const titleEl = document.querySelector(arguments[1]);
                        const descEl = document.querySelector(arguments[2]);

                        const hasId = window.location.search.includes(arguments[0]);\
""",
    ),
    # Fix the argument list to match (drop Selectors.detailsPanel).
    (
        """\
                    job_id,
                    Selectors.detailsPanel,
                    Selectors.panel_title,
                    Selectors.description)\
""",
        """\
                    job_id,
                    Selectors.panel_title,
                    Selectors.description)\
""",
    ),
    # ------------------------------------------------------------------
    # 7. Drop the hasTitle guard in __wait_for_job_panel.
    # ------------------------------------------------------------------
    (
        "if state and state['hasId'] and state['hasTitle'] and state['length'] > 0:",
        "if state and state['hasId'] and state['length'] > 0:",
    ),
    # ------------------------------------------------------------------
    # 8. __get_job_ids JS: use componentkey attribute and strip the
    #    "job-card-component-ref-" prefix to return only the numeric ID.
    # ------------------------------------------------------------------
    (
        "        .map(e => e.getAttribute(arguments[1]))",
        "        .map(e => (e.getAttribute('componentkey') || '').replace('job-card-component-ref-', ''))",
    ),
    # ------------------------------------------------------------------
    # 9. __load_job_card rendered check: the old guard looked for a child
    #    element with Selectors.jobs (div.job-card-container), which no
    #    longer exists. If the componentkey element is present, it's ready.
    # ------------------------------------------------------------------
    (
        """\
                        if (item.querySelector(arguments[1])) {
                            return 'rendered';
                        }

                        item.scrollIntoView({block: 'center'});
                        return 'pending';
                    ''',
                    get_job_item_selector(job_id),
                    Selectors.jobs)\
""",
        """\
                        item.scrollIntoView({block: 'center'});
                        return 'rendered';
                    ''',
                    get_job_item_selector(job_id))\
""",
    ),
    # ------------------------------------------------------------------
    # 10. Job-click + card-data JS: LinkedIn removed <a> links from cards.
    #     Click the div[role="button"] directly. Get the job title from
    #     the dismiss button's aria-label ("Dismiss {title} job") since
    #     all card CSS classes are now fully hashed.
    # ------------------------------------------------------------------
    (
        """\
                    debug(tag, 'Evaluating selectors', [
                        Selectors.job_items,
                        Selectors.link,
                        Selectors.company,
                        Selectors.place,
                        Selectors.date])

                    job_title, job_company, \\
                        job_company_img_link, job_place, job_date, job_is_promoted = \\
                        driver.execute_script(
                            '''
                                const job = document.querySelector(arguments[0]);
                                const link = job.querySelector(arguments[1]);

                                // Click job link and scroll
                                link.scrollIntoView();
                                link.click();

                                let title = "";
                                const titleElem = job.querySelector(arguments[2]);

                                if (titleElem) {
                                    // The title is duplicated in a visually hidden node for
                                    // screen readers, the strong element holds the visible one
                                    const visibleTitle = titleElem.querySelector("strong") || titleElem;

                                    title = visibleTitle.innerText
                                        .split("\\\\n")
                                        .map(e => e.trim())
                                        .filter(e => e.length)[0] || "";
                                }

                                let company = "";
                                const companyElem = job.querySelector(arguments[3]);

                                if (companyElem) {
                                    company = companyElem.innerText;
                                }

                                const companyImgLink = job.querySelector("img") ?
                                    job.querySelector("img").getAttribute("src") : "";

                                const place = job.querySelector(arguments[4]) ?
                                    job.querySelector(arguments[4]).innerText : "";

                                const date = job.querySelector(arguments[5]) ?
                                    job.querySelector(arguments[5]).getAttribute('datetime') : "";

                                const isPromoted = Array.from(job.querySelectorAll('li'))
                                    .find(e => e.innerText === 'Promoted') ? true : false;

                                return [
                                    title,
                                    company,
                                    companyImgLink,
                                    place,
                                    date,
                                    isPromoted,
                                ];
                            ''',
                            get_job_item_selector(job_id),
                            Selectors.link,
                            Selectors.title,
                            Selectors.company,
                            Selectors.place,
                            Selectors.date)\
""",
        """\
                    debug(tag, 'Evaluating selectors', [
                        Selectors.job_items,
                        Selectors.company,
                        Selectors.place,
                        Selectors.date])

                    job_title, job_company, \\
                        job_company_img_link, job_place, job_date, job_is_promoted = \\
                        driver.execute_script(
                            '''
                                const job = document.querySelector(arguments[0]);

                                // Click job card directly (LinkedIn removed <a> links)
                                job.scrollIntoView({block: 'center'});
                                job.click();

                                // Get title from dismiss-button aria-label: "Dismiss {title} job"
                                let title = "";
                                const dismissBtn = job.querySelector('[aria-label$=" job"]');
                                if (dismissBtn) {
                                    const raw = dismissBtn.getAttribute('aria-label') || '';
                                    title = raw.replace(/^Dismiss\\s+/i, '').replace(/\\s+job$/i, '').trim();
                                }
                                if (!title) {
                                    const titleElem = job.querySelector(arguments[1]);
                                    if (titleElem) {
                                        const visibleTitle = titleElem.querySelector("strong") || titleElem;
                                        title = visibleTitle.innerText
                                            .split("\\\\n")
                                            .map(e => e.trim())
                                            .filter(e => e.length)[0] || "";
                                    }
                                }

                                let company = "";
                                const companyElem = job.querySelector(arguments[2]);

                                if (companyElem) {
                                    company = companyElem.innerText;
                                }

                                const companyImgLink = job.querySelector("img") ?
                                    job.querySelector("img").getAttribute("src") : "";

                                const place = job.querySelector(arguments[3]) ?
                                    job.querySelector(arguments[3]).innerText : "";

                                const date = job.querySelector(arguments[4]) ?
                                    job.querySelector(arguments[4]).getAttribute('datetime') : "";

                                const isPromoted = Array.from(job.querySelectorAll('li'))
                                    .find(e => e.innerText === 'Promoted') ? true : false;

                                return [
                                    title,
                                    company,
                                    companyImgLink,
                                    place,
                                    date,
                                    isPromoted,
                                ];
                            ''',
                            get_job_item_selector(job_id),
                            Selectors.title,
                            Selectors.company,
                            Selectors.place,
                            Selectors.date)\
""",
    ),
    # ------------------------------------------------------------------
    # 11a. Deduplicate job IDs: LinkedIn's new card HTML has componentkey
    #      on BOTH the outer div[role="button"] and an inner div, so each
    #      job_id appears twice in the querySelectorAll result. Wrap in Set.
    # ------------------------------------------------------------------
    (
        "                    return Array.from(document.querySelectorAll(arguments[0]))\n"
        "                        .map(e => (e.getAttribute('componentkey') || '').replace('job-card-component-ref-', ''))\n"
        "                        .filter(e => e);",
        "                    return [...new Set(Array.from(document.querySelectorAll(arguments[0]))\n"
        "                        .map(e => (e.getAttribute('componentkey') || '').replace('job-card-component-ref-', ''))\n"
        "                        .filter(e => e))];",
    ),
    # ------------------------------------------------------------------
    # 11b. __load_job_details: replace body.innerHTML.includes(job_id) with
    #      window.location.search.includes(job_id) — same check that
    #      __wait_for_job_panel uses, which we know succeeds.  Also make
    #      the description gate soft: if the selector is missing we still
    #      proceed (description is read separately after this gate).
    # ------------------------------------------------------------------
    (
        "                        const description = document.querySelector(arguments[1]);\n"
        "                        return document.body.innerHTML.includes(arguments[0]) &&\n"
        "                            description && description.innerText.length > 0;",
        "                        const description = document.querySelector(arguments[1]);\n"
        "                        const hasDesc = !description || description.innerText.length > 0;\n"
        "                        return window.location.search.includes(arguments[0]) && hasDesc;",
    ),
    # ------------------------------------------------------------------
    # 12. Fix SyntaxError from \s in Python 3.12+ string literal.
    #     The regex approach put an invalid escape in the file; replace
    #     with plain JS startsWith/endsWith — no backslashes needed.
    # ------------------------------------------------------------------
    (
        # Use \\s in the old string so Python evaluates to \s (what's in file)
        "title = raw.replace(/^Dismiss\\s+/i, '').replace(/\\s+job$/i, '').trim();",
        "const afterDismiss = raw.indexOf('Dismiss ') === 0 ? raw.slice(8) : raw;\n"
        "                                    title = afterDismiss.endsWith(' job') ? afterDismiss.slice(0, -4).trim() : afterDismiss.trim();",
    ),
    # ------------------------------------------------------------------
    # 4e. Upgrade description selector to the expandable text box.
    #     [id^="JobDetails_AboutTheJob_"] is the outer section wrapper;
    #     [data-testid="expandable-text-box"] is the stable inner content
    #     element that we can expand by clicking its sibling button first.
    # ------------------------------------------------------------------
    (
        "description = '[id^=\"JobDetails_AboutTheJob_\"]'",
        "description = '[data-testid=\"expandable-text-box\"]'",
    ),
    # ------------------------------------------------------------------
    # 13a. Description extraction (scrape_job / single-URL path):
    #      The expandable-text-box span contains the full content already
    #      in the DOM; the "… more" button is a positioned child INSIDE
    #      the same span, so its text appears in innerText. Clone the
    #      element, strip the button from the clone, then read the text.
    # ------------------------------------------------------------------
    (
        """\
        job_description, job_description_html = driver.execute_script(
            '''
                const el = document.querySelector(arguments[0]);

                if (!el) {
                    return ["", ""];
                }

                return [
                    el.innerText,
                    el.outerHTML
                ];
            ''',
            Selectors.description)\
""",
        """\
        job_description, job_description_html = driver.execute_script(
            '''
                const el = document.querySelector(arguments[0]);

                if (!el) {
                    return ["", ""];
                }

                const clone = el.cloneNode(true);
                const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                if (expandBtn) { expandBtn.remove(); }

                return [
                    clone.innerText,
                    el.outerHTML
                ];
            ''',
            Selectors.description)\
""",
    ),
    # ------------------------------------------------------------------
    # 13b. Description extraction (run() / query path): same clone fix,
    #      different indentation level.
    # ------------------------------------------------------------------
    (
        """\
                    job_description, job_description_html = driver.execute_script(
                        '''
                            const el = document.querySelector(arguments[0]);

                            if (!el) {
                                return ["", ""];
                            }

                            return [
                                el.innerText,
                                el.outerHTML
                            ];
                        ''',
                        Selectors.description)\
""",
        """\
                    job_description, job_description_html = driver.execute_script(
                        '''
                            const el = document.querySelector(arguments[0]);

                            if (!el) {
                                return ["", ""];
                            }

                            const clone = el.cloneNode(true);
                            const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                            if (expandBtn) { expandBtn.remove(); }

                            return [
                                clone.innerText,
                                el.outerHTML
                            ];
                        ''',
                        Selectors.description)\
""",
    ),
    # ------------------------------------------------------------------
    # 13a_v2. Incremental fix: if 13a previously inserted the btn.click()
    #         approach (from an earlier patch run), replace it with the
    #         correct clone approach.
    # ------------------------------------------------------------------
    (
        """\
        job_description, job_description_html = driver.execute_script(
            '''
                const btn = document.querySelector('[data-testid="expandable-text-button"]');
                if (btn) { btn.click(); }
                const el = document.querySelector(arguments[0]);

                if (!el) {
                    return ["", ""];
                }

                return [
                    el.innerText,
                    el.outerHTML
                ];
            ''',
            Selectors.description)\
""",
        """\
        job_description, job_description_html = driver.execute_script(
            '''
                const el = document.querySelector(arguments[0]);

                if (!el) {
                    return ["", ""];
                }

                const clone = el.cloneNode(true);
                const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                if (expandBtn) { expandBtn.remove(); }

                return [
                    clone.innerText,
                    el.outerHTML
                ];
            ''',
            Selectors.description)\
""",
    ),
    # ------------------------------------------------------------------
    # 13b_v2. Same incremental fix for the run() path.
    # ------------------------------------------------------------------
    (
        """\
                    job_description, job_description_html = driver.execute_script(
                        '''
                            const btn = document.querySelector('[data-testid="expandable-text-button"]');
                            if (btn) { btn.click(); }
                            const el = document.querySelector(arguments[0]);

                            if (!el) {
                                return ["", ""];
                            }

                            return [
                                el.innerText,
                                el.outerHTML
                            ];
                        ''',
                        Selectors.description)\
""",
        """\
                    job_description, job_description_html = driver.execute_script(
                        '''
                            const el = document.querySelector(arguments[0]);

                            if (!el) {
                                return ["", ""];
                            }

                            const clone = el.cloneNode(true);
                            const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                            if (expandBtn) { expandBtn.remove(); }

                            return [
                                clone.innerText,
                                el.outerHTML
                            ];
                        ''',
                        Selectors.description)\
""",
    ),
    # ------------------------------------------------------------------
    # 15a. scrape_job() description path: `clone.innerText` on a detached
    #      node has no DOM layout, so Chrome returns a flat wall of text
    #      with no newlines between block elements (p, li, etc.).
    #      Fix: temporarily attach the clone to the document so innerText
    #      can compute layout, then remove it.
    # ------------------------------------------------------------------
    (
        """\
                const clone = el.cloneNode(true);
                const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                if (expandBtn) { expandBtn.remove(); }

                return [
                    clone.innerText,
                    el.outerHTML
                ];\
""",
        """\
                const clone = el.cloneNode(true);
                const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                if (expandBtn) { expandBtn.remove(); }
                clone.style.cssText = 'position:absolute;left:-9999px';
                document.body.appendChild(clone);
                const text = clone.innerText;
                document.body.removeChild(clone);

                return [
                    text,
                    el.outerHTML
                ];\
""",
    ),
    # ------------------------------------------------------------------
    # 15b. run() / query path: same fix, deeper indentation level.
    # ------------------------------------------------------------------
    (
        """\
                            const clone = el.cloneNode(true);
                            const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                            if (expandBtn) { expandBtn.remove(); }

                            return [
                                clone.innerText,
                                el.outerHTML
                            ];\
""",
        """\
                            const clone = el.cloneNode(true);
                            const expandBtn = clone.querySelector('[data-testid="expandable-text-button"]');
                            if (expandBtn) { expandBtn.remove(); }
                            clone.style.cssText = 'position:absolute;left:-9999px';
                            document.body.appendChild(clone);
                            const text = clone.innerText;
                            document.body.removeChild(clone);

                            return [
                                text,
                                el.outerHTML
                            ];\
""",
    ),
    # ------------------------------------------------------------------
    # 16. Company fallback for run() / query path: Selectors.company is a
    #     hashed CSS class (.artdeco-entity-lockup__subtitle) that no longer
    #     exists in LinkedIn's new UI, so the card-click script always returns
    #     an empty company. After the detail panel loads, read the company
    #     from Selectors.panel_company ('a[href*="/company/"]') as a fallback.
    # ------------------------------------------------------------------
    (
        """\
                    # Extract date text (eg '1 week ago')
                    debug(tag, 'Evaluating selectors', [Selectors.date_text])

                    job_date_text = driver.execute_script(\
""",
        """\
                    # Company fallback: card-level selector is a hashed class in the new UI;
                    # read from the detail panel (already loaded) when card returned nothing.
                    if not job_company:
                        job_company = normalize_spaces(driver.execute_script(
                            '''
                                const el = document.querySelector(arguments[0]);
                                return el ? el.innerText.trim() : "";
                            ''',
                            Selectors.panel_company) or '')

                    # Extract date text (eg '1 week ago')
                    debug(tag, 'Evaluating selectors', [Selectors.date_text])

                    job_date_text = driver.execute_script(\
""",
    ),
    # ------------------------------------------------------------------
    # 15c. Correct 15a: strip visibility:hidden — innerText returns "" for
    #      hidden elements, breaking description extraction. Off-screen
    #      position alone is sufficient to keep the clone out of view.
    # ------------------------------------------------------------------
    (
        """\
                clone.style.cssText = 'position:absolute;left:-9999px;visibility:hidden';
                document.body.appendChild(clone);
                const text = clone.innerText;
                document.body.removeChild(clone);\
""",
        """\
                clone.style.cssText = 'position:absolute;left:-9999px';
                document.body.appendChild(clone);
                const text = clone.innerText;
                document.body.removeChild(clone);\
""",
    ),
    # ------------------------------------------------------------------
    # 15d. Same correction for the run() path (deeper indentation).
    # ------------------------------------------------------------------
    (
        """\
                            clone.style.cssText = 'position:absolute;left:-9999px;visibility:hidden';
                            document.body.appendChild(clone);
                            const text = clone.innerText;
                            document.body.removeChild(clone);\
""",
        """\
                            clone.style.cssText = 'position:absolute;left:-9999px';
                            document.body.appendChild(clone);
                            const text = clone.innerText;
                            document.body.removeChild(clone);\
""",
    ),
    # ------------------------------------------------------------------
    # 14. Location fallback for scrape_job(): Selectors.date_text
    #     (.job-details-jobs-unified-top-card__tertiary-description-container)
    #     no longer exists in the new UI, so tertiaryEl is always null.
    #     Add an else branch that finds the location <p> by scanning for
    #     the paragraph before the description section that contains the
    #     middle-dot separator (·, U+00B7). Take the FIRST such paragraph
    #     (location · date) — not the last ("Promoted by hirer · ...").
    #
    #     The old string includes "return [title, company, place];" as a
    #     unique sentinel so the patch never matches as a substring of an
    #     already-patched if/else block on a re-run.
    # ------------------------------------------------------------------
    (
        """\
                let place = "";
                if (tertiaryEl) {
                    const segments = tertiaryEl.innerText
                        .split('\xb7')
                        .map(e => e.replace(/[\\n\\r\\t ]+/g, ' ').trim())
                        .filter(e => e.length);
                    place = segments.length ? segments[0] : "";
                }

                return [title, company, place];\
""",
        """\
                let place = "";
                if (tertiaryEl) {
                    const segments = tertiaryEl.innerText
                        .split('\xb7')
                        .map(e => e.replace(/[\\n\\r\\t ]+/g, ' ').trim())
                        .filter(e => e.length);
                    place = segments.length ? segments[0] : "";
                } else {
                    // Fallback: first <p> before the description section that
                    // contains the middle-dot separator (location · date ·
                    // applicants). The location paragraph comes before any
                    // "Promoted by hirer · ..." paragraph, so take [0].
                    const descBox = document.querySelector('[data-testid="expandable-text-box"]');
                    if (descBox) {
                        const locPs = Array.from(document.querySelectorAll('p')).filter(p =>
                            (descBox.compareDocumentPosition(p) & 2) && p.innerText.includes('\xb7'));
                        if (locPs.length) place = locPs[0].innerText.split('\xb7')[0].trim();
                    }
                }

                return [title, company, place];\
""",
    ),
]


def find_target(base: Path) -> Path | None:
    candidate = base / TARGET
    if candidate.exists():
        return candidate
    for p in base.rglob(TARGET):
        return p
    return None


def main() -> None:
    # In Docker the venv is always in-project (.venv); locally Poetry may put
    # it in its global cache, so fall back to the active interpreter prefix.
    candidates = [
        Path(__file__).parent.parent / ".venv",
        Path(sys.prefix),
    ]
    target = None
    for base in candidates:
        target = find_target(base)
        if target:
            break

    if target is None:
        print(f"[patch] ERROR: could not find {TARGET} under any of {candidates}", file=sys.stderr)
        sys.exit(1)

    original = target.read_text()
    patched = original

    applied = []
    skipped = []
    warnings = []

    for old, new in PATCHES:
        if new in patched:
            skipped.append(old.split('\n')[0].strip())
        elif old in patched:
            patched = patched.replace(old, new, 1)
            applied.append(old.split('\n')[0].strip())
        else:
            warnings.append(old.split('\n')[0].strip())

    if warnings:
        print(f"[patch] ERROR: {len(warnings)} patch(es) could not find their target string "
              f"(library may have changed):", file=sys.stderr)
        for w in warnings:
            print(f"  ? {w!r}", file=sys.stderr)
        sys.exit(1)

    if applied:
        target.write_text(patched)
        print(f"[patch] Applied {len(applied)} patch(es) to {target}")
        for s in applied:
            print(f"  + {s!r}")
    else:
        print(f"[patch] Already patched or nothing to do ({len(skipped)} skipped, "
              f"{len(warnings)} not found).")


if __name__ == "__main__":
    main()
