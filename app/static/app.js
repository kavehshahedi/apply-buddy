document.addEventListener("DOMContentLoaded", function () {
    const toast = document.getElementById("toast");

    function showToast(msg, type) {
        if (!toast) return;
        toast.textContent = msg;
        toast.className = type === "error" ? "toast-error" : "toast-success";
        toast.classList.remove("hidden");
        setTimeout(() => toast.classList.add("hidden"), 4000);
    }

    // Sort / Filter controls — persist to localStorage
    const filterForm = document.getElementById("filter-form");

    function getFilterKeys() {
        return Array.from(filterForm.elements)
            .filter((el) => el.name)
            .map((el) => el.name);
    }

    function saveFilters() {
        const params = new URLSearchParams();
        getFilterKeys().forEach((key) => {
            const el = filterForm.elements[key];
            if (el) params.set(key, el.value);
        });
        localStorage.setItem("jobFilters", params.toString());
    }

    function restoreFilters() {
        const saved = localStorage.getItem("jobFilters");
        if (!saved) return;
        const urlParams = new URLSearchParams(window.location.search);
        const savedParams = new URLSearchParams(saved);
        let needsRedirect = false;
        getFilterKeys().forEach((key) => {
            if (!urlParams.has(key) && savedParams.has(key)) {
                urlParams.set(key, savedParams.get(key));
                needsRedirect = true;
            }
        });
        if (needsRedirect) {
            const qs = urlParams.toString();
            window.location.href = "/jobs/" + (qs ? "?" + qs : "");
        }
    }

    const applyFiltersBtn = document.getElementById("apply-filters-btn");
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener("click", function () {
            saveFilters();
            const params = new URLSearchParams();
            getFilterKeys().forEach((key) => {
                const el = filterForm.elements[key];
                if (el) params.set(key, el.value);
            });
            window.location.href = "/jobs/?" + params.toString();
        });
    }

    if (applyFiltersBtn) restoreFilters();

    // Fetch Jobs
    function setupFetchJobs(btnId, progressId, textId) {
        const fetchBtn = document.getElementById(btnId);
        const progressDiv = document.getElementById(progressId);
        const progressText = document.getElementById(textId);
        if (!fetchBtn) return;
        fetchBtn.addEventListener("click", async function () {
            fetchBtn.disabled = true;
            fetchBtn.textContent = "Fetching...";
            if (progressDiv) {
                progressDiv.classList.remove("hidden");
                if (progressText) progressText.textContent = "Starting scrape...";
            }
            const resp = await fetch("/scrape/run", { method: "POST" });
            if (!resp.ok) {
                const err = await resp.json();
                if (progressText) progressText.textContent = err.error || "Failed to start scrape.";
                fetchBtn.disabled = false;
                fetchBtn.textContent = "Fetch Jobs";
                return;
            }
            const poll = setInterval(async () => {
                const p = await (await fetch("/scrape/progress")).json();
                if (progressText)
                    progressText.textContent =
                        p.message || `Scraped ${p.current}/${p.total} (${p.errors} errors)`;
                if (!p.running) {
                    clearInterval(poll);
                    fetchBtn.disabled = false;
                    fetchBtn.textContent = "Fetch Jobs";
                    if (p.errors > 0) showToast(`Scrape finished with ${p.errors} errors`, "error");
                    else showToast(`Scrape complete: ${p.current} jobs`, "");
                    location.reload();
                }
            }, 1000);
        });
    }

    setupFetchJobs("fetch-jobs-btn", "scrape-progress", "scrape-progress-text");
    setupFetchJobs("fetch-jobs-btn-empty", "scrape-progress", "scrape-progress-text");

    // Manual fetch by URL
    const manualFetchBtn = document.getElementById("manual-fetch-btn");
    const manualFetchOverlay = document.getElementById("manual-fetch-overlay");
    const manualFetchClose = document.getElementById("manual-fetch-close");
    const manualFetchCancel = document.getElementById("manual-fetch-cancel");
    const manualFetchSubmit = document.getElementById("manual-fetch-submit");
    const manualFetchUrl = document.getElementById("manual-fetch-url");
    const manualFetchProgress = document.getElementById("manual-fetch-progress");
    const manualFetchProgressText = document.getElementById("manual-fetch-progress-text");

    function openManualFetchModal() {
        if (manualFetchOverlay) {
            manualFetchOverlay.classList.remove("hidden");
            manualFetchUrl.value = "";
            manualFetchUrl.focus();
            if (manualFetchProgress) manualFetchProgress.classList.add("hidden");
            manualFetchSubmit.disabled = false;
            manualFetchSubmit.textContent = "Fetch Job";
        }
    }

    function closeManualFetchModal() {
        if (manualFetchOverlay) manualFetchOverlay.classList.add("hidden");
    }

    if (manualFetchBtn) {
        manualFetchBtn.addEventListener("click", openManualFetchModal);
    }
    const manualFetchBtnEmpty = document.getElementById("manual-fetch-btn-empty");
    if (manualFetchBtnEmpty) {
        manualFetchBtnEmpty.addEventListener("click", openManualFetchModal);
    }
    if (manualFetchClose) {
        manualFetchClose.addEventListener("click", closeManualFetchModal);
    }
    if (manualFetchCancel) {
        manualFetchCancel.addEventListener("click", closeManualFetchModal);
    }
    if (manualFetchOverlay) {
        manualFetchOverlay.addEventListener("click", function (e) {
            if (e.target === this) closeManualFetchModal();
        });
    }
    if (manualFetchUrl) {
        manualFetchUrl.addEventListener("keydown", function (e) {
            if (e.key === "Enter") manualFetchSubmit.click();
        });
    }

    if (manualFetchSubmit) {
        manualFetchSubmit.addEventListener("click", async function () {
            const url = manualFetchUrl.value.trim();
            if (!url) {
                showToast("Please enter a LinkedIn job URL", "error");
                manualFetchUrl.focus();
                return;
            }
            if (!url.startsWith("https://www.linkedin.com/jobs/view/")) {
                showToast("URL must start with https://www.linkedin.com/jobs/view/", "error");
                manualFetchUrl.focus();
                return;
            }

            manualFetchSubmit.disabled = true;
            manualFetchSubmit.textContent = "Fetching...";
            if (manualFetchProgress) {
                manualFetchProgress.classList.remove("hidden");
                if (manualFetchProgressText)
                    manualFetchProgressText.textContent = "Starting fetch...";
            }

            const resp = await fetch("/manual-fetch/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: url }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                if (manualFetchProgressText)
                    manualFetchProgressText.textContent = err.error || "Failed to start fetch.";
                manualFetchSubmit.disabled = false;
                manualFetchSubmit.textContent = "Fetch Job";
                showToast(err.error || "Failed to start fetch", "error");
                return;
            }

            const poll = setInterval(async () => {
                const p = await (await fetch("/manual-fetch/progress")).json();
                if (manualFetchProgressText)
                    manualFetchProgressText.textContent = p.message || `Fetching...`;
                if (!p.running) {
                    clearInterval(poll);
                    closeManualFetchModal();
                    if (p.errors > 0) showToast(p.message || "Fetch failed", "error");
                    else showToast("Job added successfully!", "");
                    location.reload();
                }
            }, 1000);
        });
    }

    // Manual job by title/description
    const manualJobBtn = document.getElementById("manual-job-btn");
    const manualJobOverlay = document.getElementById("manual-job-overlay");
    const manualJobClose = document.getElementById("manual-job-close");
    const manualJobCancel = document.getElementById("manual-job-cancel");
    const manualJobForm = document.getElementById("manual-job-form");

    function openManualJobModal() {
        if (manualJobOverlay) {
            manualJobOverlay.classList.remove("hidden");
            document.getElementById("manual-job-title").focus();
        }
    }

    function closeManualJobModal() {
        if (manualJobOverlay) manualJobOverlay.classList.add("hidden");
    }

    if (manualJobBtn) {
        manualJobBtn.addEventListener("click", openManualJobModal);
    }
    const manualJobBtnEmpty = document.getElementById("manual-job-btn-empty");
    if (manualJobBtnEmpty) {
        manualJobBtnEmpty.addEventListener("click", openManualJobModal);
    }
    if (manualJobClose) {
        manualJobClose.addEventListener("click", closeManualJobModal);
    }
    if (manualJobCancel) {
        manualJobCancel.addEventListener("click", closeManualJobModal);
    }
    if (manualJobOverlay) {
        manualJobOverlay.addEventListener("click", function (e) {
            if (e.target === this) closeManualJobModal();
        });
    }
    if (manualJobForm) {
        manualJobForm.addEventListener("submit", function () {
            manualJobForm.querySelector('button[type="submit"]').disabled = true;
            manualJobForm.querySelector('button[type="submit"]').textContent = "Adding...";
        });
    }

    // Score Fit
    const scoreBtn = document.getElementById("score-fit-btn");
    const scoreProgress = document.getElementById("score-progress");
    const scoreProgressText = document.getElementById("score-progress-text");
    const forceRescoreCheckbox = document.getElementById("force-rescore-checkbox");
    if (scoreBtn) {
        scoreBtn.addEventListener("click", async function () {
            scoreBtn.disabled = true;
            scoreBtn.textContent = "Starting...";
            if (scoreProgress) {
                scoreProgress.classList.remove("hidden");
                if (scoreProgressText) scoreProgressText.textContent = "Starting scoring...";
            }
            const force = forceRescoreCheckbox ? forceRescoreCheckbox.checked : false;
            const params = force ? "?force=true" : "";
            const resp = await fetch("/actions/score-fit" + params, { method: "POST" });
            if (!resp.ok) {
                const err = await resp.json();
                if (scoreProgressText)
                    scoreProgressText.textContent = err.error || "Failed to start scoring.";
                scoreBtn.disabled = false;
                scoreBtn.textContent = "Score Fit";
                return;
            }
            const poll = setInterval(async () => {
                const p = await (await fetch("/actions/score-progress")).json();
                if (scoreProgressText)
                    scoreProgressText.textContent = p.message || `Scored ${p.current}/${p.total}`;
                if (!p.running) {
                    clearInterval(poll);
                    scoreBtn.disabled = false;
                    scoreBtn.textContent = "Score Fit";
                    if (p.errors > 0)
                        showToast(`Scoring finished with ${p.errors} errors`, "error");
                    else showToast(`Scoring complete: ${p.current} jobs`, "");
                    location.reload();
                }
            }, 1000);
        });
    }

    // Action buttons (tailor CV, cover letter)
    document.querySelectorAll("[data-action]").forEach((btn) => {
        btn.addEventListener("click", async function () {
            const action = this.dataset.action;
            const jobId = this.dataset.jobId;
            let url = `/actions/${action}/${jobId}`;
            if (action === "score-fit") {
                const cvSelect = this.closest(".fit-card")?.querySelector(".fit-card-cv-select");
                if (cvSelect) url += `?cv_source=${cvSelect.value}`;
            } else if (action === "cover-letter") {
                const clToggle = document.getElementById("cl-use-template");
                if (clToggle) url += `?use_template=${clToggle.checked}`;
            }
            this.disabled = true;
            this.textContent = "Starting...";
            try {
                const resp = await fetch(url, { method: "POST" });
                if (!resp.ok) {
                    const err = await resp.json();
                    showToast(err.error || "Action failed", "error");
                    this.disabled = false;
                    this.textContent = "Retry";
                    return;
                }
                const poll = setInterval(async () => {
                    const p = await (await fetch(`/actions/action-progress/${jobId}`)).json();
                    const label =
                        action === "tailor-cv"
                            ? "Tailoring CV"
                            : action === "cover-letter"
                              ? "Writing letter"
                              : "Scoring";
                    this.textContent = `${label}...`;
                    if (p.message && p.message !== "Starting...") {
                        this.textContent =
                            p.message.length > 30 ? p.message.substring(0, 30) + "..." : p.message;
                    }
                    if (!p.running) {
                        clearInterval(poll);
                        showToast(p.message || "Done", "");
                        location.reload();
                    }
                }, 1000);
            } catch (e) {
                showToast("Network error", "error");
                this.disabled = false;
                this.textContent = "Retry";
            }
        });
    });

    // Settings: Add query
    const addQueryBtn = document.getElementById("add-query-btn");
    const addQueryForm = document.getElementById("add-query-form");
    const addQueryFormStyle = addQueryForm?.style;
    if (addQueryBtn) {
        addQueryBtn.addEventListener("click", () => {
            if (editingQueryId) {
                exitEditMode();
                addQueryFormStyle.display = "none";
                return;
            }
            const isHidden = addQueryFormStyle.display === "none" || !addQueryFormStyle.display;
            addQueryFormStyle.display = isHidden ? "block" : "none";
            if (isHidden) clearForm();
        });
    }
    // Filter chips — click to toggle
    document.querySelectorAll(".filter-chips").forEach((container) => {
        container.addEventListener("click", function (e) {
            const chip = e.target.closest(".filter-chip");
            if (!chip) return;
            chip.classList.toggle("active");
        });
    });

    function getChipValues(id) {
        const container = document.getElementById(id);
        if (!container) return [];
        return Array.from(container.querySelectorAll(".filter-chip.active")).map(
            (chip) => chip.dataset.value
        );
    }

    let editingQueryId = null;
    const queriesData = document.getElementById("queries-data");
    const allQueries = queriesData ? JSON.parse(queriesData.textContent) : [];

    function setChipValues(id, values) {
        const container = document.getElementById(id);
        if (!container) return;
        container.querySelectorAll(".filter-chip").forEach((chip) => {
            chip.classList.toggle("active", values.includes(chip.dataset.value));
        });
    }

    function populateForm(q) {
        document.getElementById("q-keywords").value = q.keywords || "";
        document.getElementById("q-locations").value = (q.locations || []).join(", ");
        document.getElementById("q-limit").value = q.limit || 25;
        document.getElementById("q-days-back").value = q.days_back || "";
        document.getElementById("q-time-filter").value = q.time_filter || "any";
        document.getElementById("q-relevance").value = q.relevance || "recent";
        document.getElementById("q-job-type").value = q.job_type || "";
        document.getElementById("q-experience").value = q.experience || "";
        document.getElementById("q-on-site-remote").value = q.on_site_or_remote || "";
        document.getElementById("q-base-salary").value = q.base_salary || "";
        setChipValues("q-industry", q.industry || []);
        setChipValues("q-job-function", q.job_function || []);
        setChipValues("q-benefits", q.benefits || []);
        setChipValues("q-commitments", q.commitments || []);
        document.getElementById("q-easy-apply").checked = q.easy_apply || false;
        document.getElementById("q-under-10").checked = q.under_10_applicants || false;
    }

    function clearForm() {
        populateForm({
            keywords: "",
            locations: [],
            limit: 25,
            days_back: null,
            time_filter: "any",
            relevance: "recent",
            job_type: null,
            experience: null,
            on_site_or_remote: null,
            base_salary: null,
            industry: [],
            job_function: [],
            benefits: [],
            commitments: [],
            easy_apply: false,
            under_10_applicants: false,
        });
    }

    function enterEditMode(queryId) {
        editingQueryId = queryId;
        const q = allQueries.find((q) => q.id === queryId);
        if (!q) return;
        populateForm(q);
        addQueryForm.style.display = "block";
        document.getElementById("save-query-btn").textContent = "Update Query";
        document.getElementById("cancel-edit-btn").style.display = "";
        addQueryBtn.textContent = "Cancel";
    }

    function exitEditMode() {
        editingQueryId = null;
        clearForm();
        document.getElementById("save-query-btn").textContent = "Save Query";
        document.getElementById("cancel-edit-btn").style.display = "none";
        addQueryBtn.textContent = "Add Query";
    }

    // Edit query
    document.querySelectorAll(".edit-query").forEach((btn) => {
        btn.addEventListener("click", function () {
            enterEditMode(parseInt(this.dataset.queryId));
        });
    });

    // Cancel edit
    document.getElementById("cancel-edit-btn")?.addEventListener("click", function () {
        exitEditMode();
        addQueryFormStyle.display = "none";
        addQueryBtn.textContent = "Add Query";
    });

    const saveQueryBtn = document.getElementById("save-query-btn");
    if (saveQueryBtn) {
        saveQueryBtn.addEventListener("click", async function () {
            const keywords = document.getElementById("q-keywords").value;
            const locations = document
                .getElementById("q-locations")
                .value.split(",")
                .map((s) => s.trim())
                .filter(Boolean);
            const limit = parseInt(document.getElementById("q-limit").value) || 25;
            const daysBackInput = document.getElementById("q-days-back");
            const days_back = daysBackInput.value ? parseInt(daysBackInput.value) : null;
            const time_filter = document.getElementById("q-time-filter").value;
            const relevance = document.getElementById("q-relevance").value;
            const job_type = document.getElementById("q-job-type").value || null;
            const experience = document.getElementById("q-experience").value || null;
            const on_site_or_remote = document.getElementById("q-on-site-remote").value || null;
            const base_salary = document.getElementById("q-base-salary").value || null;
            const industry = getChipValues("q-industry");
            const job_function = getChipValues("q-job-function");
            const benefits = getChipValues("q-benefits");
            const commitments = getChipValues("q-commitments");
            const easy_apply = document.getElementById("q-easy-apply").checked;
            const under_10_applicants = document.getElementById("q-under-10").checked;
            const body = {
                keywords,
                locations,
                limit,
                days_back,
                time_filter,
                relevance,
                job_type,
                experience,
                on_site_or_remote,
                base_salary,
                industry,
                job_function,
                benefits,
                commitments,
                easy_apply,
                under_10_applicants,
            };
            const method = editingQueryId ? "PUT" : "POST";
            const url = editingQueryId
                ? `/settings/queries/${editingQueryId}`
                : "/settings/queries";
            const resp = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (resp.ok) {
                showToast(editingQueryId ? "Query updated" : "Query saved", "");
                location.reload();
            } else showToast("Failed to save query", "error");
        });
    }

    // Delete query
    document.querySelectorAll(".delete-query").forEach((btn) => {
        btn.addEventListener("click", async function () {
            if (!confirm("Delete this query?")) return;
            const resp = await fetch(`/settings/queries/${this.dataset.queryId}`, {
                method: "DELETE",
            });
            if (resp.ok) {
                showToast("Query deleted", "");
                location.reload();
            }
        });
    });

    // Toggle switch save
    document.querySelectorAll(".toggle-input").forEach((cb) => {
        cb.addEventListener("change", async function () {
            const key = this.dataset.toggleKey;
            const value = this.checked ? "1" : "0";
            const resp = await fetch(`/settings/setting/${key}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value }),
            });
            if (resp.ok) showToast("Setting saved", "");
            else showToast("Failed to save setting", "error");
        });
    });

    // Save setting
    document.querySelectorAll(".save-setting").forEach((btn) => {
        btn.addEventListener("click", async function () {
            const key = this.dataset.settingKey;
            const inputId = this.dataset.inputId;
            const value = document.getElementById(inputId).value;
            const resp = await fetch(`/settings/setting/${key}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value }),
            });
            if (resp.ok) showToast("Setting saved", "");
            else showToast("Failed to save setting", "error");
        });
    });

    // Reset prompt to default
    document.querySelectorAll(".reset-prompt").forEach((btn) => {
        btn.addEventListener("click", async function () {
            const key = this.dataset.settingKey;
            const inputId = this.dataset.inputId;
            const defaultValue = this.dataset.default;
            document.getElementById(inputId).value = defaultValue;
            this.textContent = "Saving...";
            const resp = await fetch(`/settings/setting/${key}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: defaultValue }),
            });
            this.textContent = "Reset to Default";
            if (resp.ok) showToast("Prompt reset to default", "");
            else showToast("Failed to reset prompt", "error");
        });
    });

    // Tool status check
    const toolStatus = document.getElementById("tool-status");
    if (toolStatus) {
        (async function () {
            try {
                const resp = await fetch("/settings/tool-check");
                const data = await resp.json();
                for (const [key, label] of Object.entries({
                    chrome: "Chrome",
                    latex: "LaTeX",
                    pandoc: "Pandoc",
                })) {
                    const span = toolStatus.querySelector(`[data-tool="${key}"]`);
                    if (span) {
                        span.textContent = data[key] ? "available" : "not found";
                        span.className =
                            "tool-status-value " + (data[key] ? "available" : "missing");
                    }
                }
            } catch (e) {}
        })();
    }

    // Applied board: filter by status
    window.filterByStatus = function (status, btn) {
        document.querySelectorAll(".status-tab").forEach((t) => t.classList.remove("active"));
        if (btn) btn.classList.add("active");
        document.querySelectorAll("#applied-table tbody tr").forEach((row) => {
            if (status === "all" || row.dataset.status === status) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    };

    // Job listings: toggle status dropdown
    window.toggleStatusMenu = function (btn) {
        const menu = btn.nextElementSibling;
        const isOpen = menu.classList.contains("open");
        document
            .querySelectorAll(".status-dropdown-menu.open")
            .forEach((m) => m.classList.remove("open"));
        if (!isOpen) menu.classList.add("open");
    };

    // Job listings: change status via dropdown
    window.changeStatus = async function (jobId, status) {
        const form = document.createElement("form");
        form.method = "POST";
        form.action = `/jobs/${jobId}/status`;
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "status";
        input.value = status;
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    };

    // Close dropdowns on click outside
    document.addEventListener("click", function (e) {
        if (!e.target.closest(".status-dropdown-wrap")) {
            document
                .querySelectorAll(".status-dropdown-menu.open")
                .forEach((m) => m.classList.remove("open"));
        }
    });

    // Enter key on job rows goes to detail
    document.querySelectorAll(".job-row-title").forEach((el) => {
        el.addEventListener("keydown", function (e) {
            if (e.key === "Enter") window.location.href = this.href;
        });
    });

    // Settings tabs
    document.querySelectorAll(".settings-tab").forEach((tab) => {
        tab.addEventListener("click", function () {
            document.querySelectorAll(".settings-tab").forEach((t) => t.classList.remove("active"));
            document
                .querySelectorAll(".settings-panel")
                .forEach((p) => p.classList.remove("active"));
            this.classList.add("active");
            document.getElementById("panel-" + this.dataset.tab).classList.add("active");
        });
    });
});
