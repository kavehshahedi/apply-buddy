document.addEventListener("DOMContentLoaded", function () {
    // Rows can be hidden by the search box (hidden attr) and by status tabs / the flow chart
    // (style.display), so every filter calls this to refresh the empty row, count and bulk selection.
    window.syncFilteredRows = function () {
        var rows = Array.from(document.querySelectorAll("tr[data-search]"));
        var shown = rows.filter(function (r) {
            return !r.hidden && r.style.display !== "none";
        }).length;
        var empty = document.getElementById("filter-empty");
        if (empty) empty.hidden = shown > 0;
        var status = document.getElementById("filter-status");
        if (status) status.textContent = shown + (shown === 1 ? " job" : " jobs") + " shown";
        if (window.bulkSync) window.bulkSync();
    };

    var filterForm = document.getElementById("filter-form");
    if (filterForm) setupFilters(filterForm);

    // Search filters rows in place; every other field reloads the page with new query params.
    function setupFilters(form) {
        var fields = Array.from(form.querySelectorAll("[data-default]"));
        var search = document.getElementById("filter-search");
        var serverFields = fields.filter(function (el) {
            return el !== search;
        });
        var storageKey = form.dataset.storageKey;
        var barReset = form.querySelector("[data-filter-reset]");
        var timer;

        function urlWith(params) {
            var qs = params.toString();
            return location.pathname + (qs ? "?" + qs : "");
        }

        function syncReset() {
            barReset.hidden = fields.every(function (el) {
                return el.value.trim() === el.dataset.default;
            });
        }

        function filterRows() {
            var terms = search.value.toLowerCase().split(/\s+/).filter(Boolean);
            document.querySelectorAll("tr[data-search]").forEach(function (row) {
                row.hidden = !terms.every(function (t) {
                    return row.dataset.search.indexOf(t) !== -1;
                });
            });
            window.syncFilteredRows();
            var params = new URLSearchParams(location.search);
            if (terms.length) params.set("q", search.value.trim());
            else params.delete("q");
            history.replaceState(null, "", urlWith(params));
        }

        function apply() {
            clearTimeout(timer);
            // Only non-default values go in the URL and the saved filters.
            var params = new URLSearchParams(location.search);
            var saved = new URLSearchParams();
            serverFields.forEach(function (el) {
                var v = el.value.trim();
                if (v === el.dataset.default) {
                    params.delete(el.name);
                } else {
                    params.set(el.name, v);
                    saved.set(el.name, v);
                }
            });
            if (saved.toString()) localStorage.setItem(storageKey, saved.toString());
            else localStorage.removeItem(storageKey);
            var url = urlWith(params);
            if (url === location.pathname + location.search) return;
            // Keep the filter bar where it was on screen, and keep keyboard focus on the field.
            sessionStorage.setItem(
                "filterAnchor",
                JSON.stringify({ top: form.getBoundingClientRect().top, focus: document.activeElement.id })
            );
            location.href = url;
        }

        function reset() {
            fields.forEach(function (el) {
                el.value = el.dataset.default;
            });
            if (search) filterRows();
            syncReset();
            apply();
            if (search) search.focus();
        }

        // Saved filters come back when the page is opened without any of its own.
        var saved = localStorage.getItem(storageKey);
        var current = new URLSearchParams(location.search);
        var hasFilters = serverFields.some(function (el) {
            return current.has(el.name);
        });
        if (saved && !hasFilters) {
            new URLSearchParams(saved).forEach(function (v, k) {
                current.set(k, v);
            });
            var restored = urlWith(current);
            if (restored !== location.pathname + location.search) return location.replace(restored);
        }

        var anchor = JSON.parse(sessionStorage.getItem("filterAnchor") || "null");
        sessionStorage.removeItem("filterAnchor");
        if (anchor) {
            // Next frame, so charts rendered on DOMContentLoaded have their final height.
            requestAnimationFrame(function () {
                window.scrollBy(0, form.getBoundingClientRect().top - anchor.top);
                var el = anchor.focus && document.getElementById(anchor.focus);
                if (el) el.focus({ preventScroll: true });
            });
        }

        serverFields.forEach(function (el) {
            if (el.tagName === "SELECT") {
                el.addEventListener("change", apply);
                return;
            }
            // Number inputs: wait for typing (or spinner clicks) to settle; Enter applies at once.
            el.addEventListener("input", function () {
                clearTimeout(timer);
                syncReset();
                if (el.value !== "" && el.checkValidity()) timer = setTimeout(apply, 700);
            });
            el.addEventListener("keydown", function (e) {
                if (e.key !== "Enter") return;
                e.preventDefault();
                if (el.reportValidity()) apply();
            });
            el.addEventListener("blur", function () {
                if (el.value !== "" && el.checkValidity()) return;
                clearTimeout(timer);
                el.value = el.defaultValue;
                syncReset();
            });
        });

        if (search) {
            search.addEventListener("input", function () {
                filterRows();
                syncReset();
            });
            if (search.value) filterRows();
        }
        form.addEventListener("submit", function (e) {
            e.preventDefault();
        });
        document.querySelectorAll("[data-filter-reset]").forEach(function (btn) {
            btn.addEventListener("click", reset);
        });
        syncReset();
    }

    function setupFetchJobs(btnId, progressId, textId) {
        var fetchBtn = document.getElementById(btnId);
        var progressDiv = document.getElementById(progressId);
        var progressText = document.getElementById(textId);
        if (!fetchBtn) return;
        fetchBtn.addEventListener("click", async function () {
            fetchBtn.disabled = true;
            fetchBtn.textContent = "Fetching...";
            if (progressDiv) {
                progressDiv.classList.remove("hidden");
                if (progressText) progressText.textContent = "Starting scrape...";
            }
            var resp = await fetch("/scrape/run", { method: "POST" });
            if (!resp.ok) {
                var err = await resp.json();
                if (progressText) progressText.textContent = err.error || "Failed to start scrape.";
                fetchBtn.disabled = false;
                fetchBtn.textContent = "Fetch Jobs";
                return;
            }
            var poll = setInterval(async function () {
                var p = await (await fetch("/scrape/progress")).json();
                if (progressText)
                    progressText.textContent =
                        p.message ||
                        "Scraped " + p.current + "/" + p.total + " (" + p.errors + " errors)";
                if (!p.running) {
                    clearInterval(poll);
                    fetchBtn.disabled = false;
                    fetchBtn.textContent = "Fetch Jobs";
                    if (p.errors > 0)
                        window.showToast("Scrape finished with " + p.errors + " errors", "error");
                    else window.showToast("Scrape complete: " + p.current + " jobs", "");
                    location.reload();
                }
            }, 1000);
        });
    }

    setupFetchJobs("fetch-jobs-btn", "scrape-progress", "scrape-progress-text");
    setupFetchJobs("fetch-jobs-btn-empty", "scrape-progress", "scrape-progress-text");
    setupFetchJobs("fetch-jobs-subnav", "scrape-progress", "scrape-progress-text");

    var manualFetchBtn = document.getElementById("manual-fetch-btn");
    var manualFetchOverlay = document.getElementById("manual-fetch-overlay");
    var manualFetchClose = document.getElementById("manual-fetch-close");
    var manualFetchCancel = document.getElementById("manual-fetch-cancel");
    var manualFetchSubmit = document.getElementById("manual-fetch-submit");
    var manualFetchUrl = document.getElementById("manual-fetch-url");
    var manualFetchProgress = document.getElementById("manual-fetch-progress");
    var manualFetchProgressText = document.getElementById("manual-fetch-progress-text");

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
    var manualFetchBtnEmpty = document.getElementById("manual-fetch-btn-empty");
    if (manualFetchBtnEmpty) {
        manualFetchBtnEmpty.addEventListener("click", openManualFetchModal);
    }
    var manualFetchSubnav = document.getElementById("manual-fetch-subnav");
    if (manualFetchSubnav) {
        manualFetchSubnav.addEventListener("click", openManualFetchModal);
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
            var url = manualFetchUrl.value.trim();
            if (!url) {
                window.showToast("Please enter a LinkedIn job URL", "error");
                manualFetchUrl.focus();
                return;
            }
            if (!url.startsWith("https://www.linkedin.com/jobs/view/")) {
                window.showToast(
                    "URL must start with https://www.linkedin.com/jobs/view/",
                    "error"
                );
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

            var resp = await fetch("/manual-fetch/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: url }),
            });

            if (!resp.ok) {
                var err = await resp.json();
                if (manualFetchProgressText)
                    manualFetchProgressText.textContent = err.error || "Failed to start fetch.";
                manualFetchSubmit.disabled = false;
                manualFetchSubmit.textContent = "Fetch Job";
                window.showToast(err.error || "Failed to start fetch", "error");
                return;
            }

            var poll = setInterval(async function () {
                var p = await (await fetch("/manual-fetch/progress")).json();
                if (manualFetchProgressText)
                    manualFetchProgressText.textContent = p.message || "Fetching...";
                if (!p.running) {
                    clearInterval(poll);
                    closeManualFetchModal();
                    if (p.errors > 0) window.showToast(p.message || "Fetch failed", "error");
                    else window.showToast("Job added successfully!", "");
                    location.reload();
                }
            }, 1000);
        });
    }

    var manualJobBtn = document.getElementById("manual-job-btn");
    var manualJobOverlay = document.getElementById("manual-job-overlay");
    var manualJobClose = document.getElementById("manual-job-close");
    var manualJobCancel = document.getElementById("manual-job-cancel");
    var manualJobForm = document.getElementById("manual-job-form");

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
    var manualJobBtnEmpty = document.getElementById("manual-job-btn-empty");
    if (manualJobBtnEmpty) {
        manualJobBtnEmpty.addEventListener("click", openManualJobModal);
    }
    var manualJobSubnav = document.getElementById("manual-job-subnav");
    if (manualJobSubnav) {
        manualJobSubnav.addEventListener("click", openManualJobModal);
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

    window.quickStatus = async function (jobId, status) {
        var form = document.createElement("form");
        form.method = "POST";
        form.action = "/jobs/" + jobId + "/status";
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "status";
        input.value = status;
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    };

    var scoreBtn = document.getElementById("score-fit-btn");
    var scoreProgress = document.getElementById("score-progress");
    var scoreProgressText = document.getElementById("score-progress-text");
    var forceRescoreCheckbox = document.getElementById("force-rescore-checkbox");
    if (scoreBtn) {
        scoreBtn.addEventListener("click", async function () {
            scoreBtn.disabled = true;
            scoreBtn.textContent = "Starting...";
            if (scoreProgress) {
                scoreProgress.classList.remove("hidden");
                if (scoreProgressText) scoreProgressText.textContent = "Starting scoring...";
            }
            var force = forceRescoreCheckbox ? forceRescoreCheckbox.checked : false;
            var params = force ? "?force=true" : "";
            var resp = await fetch("/actions/score-fit" + params, { method: "POST" });
            if (!resp.ok) {
                var err = await resp.json();
                if (scoreProgressText)
                    scoreProgressText.textContent = err.error || "Failed to start scoring.";
                scoreBtn.disabled = false;
                scoreBtn.textContent = "Score Fit";
                return;
            }
            var poll = setInterval(async function () {
                var p = await (await fetch("/actions/score-progress")).json();
                if (scoreProgressText)
                    scoreProgressText.textContent =
                        p.message || "Scored " + p.current + "/" + p.total;
                if (!p.running) {
                    clearInterval(poll);
                    scoreBtn.disabled = false;
                    scoreBtn.textContent = "Score Fit";
                    if (p.errors > 0)
                        window.showToast("Scoring finished with " + p.errors + " errors", "error");
                    else window.showToast("Scoring complete: " + p.current + " jobs", "");
                    location.reload();
                }
            }, 1000);
        });
    }

    document.querySelectorAll("[data-action]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
            var action = this.dataset.action;
            var jobId = this.dataset.jobId;
            var url = "/actions/" + action + "/" + jobId;
            if (action === "score-fit") {
                var cvSelect = this.closest(".fit-card")?.querySelector(".fit-card-cv-select");
                if (cvSelect) url += "?cv_source=" + cvSelect.value;
            } else if (action === "cover-letter") {
                var clToggle = document.getElementById("cl-use-template");
                if (clToggle) url += "?use_template=" + clToggle.checked;
            }
            this.disabled = true;
            this.textContent = "Starting...";
            try {
                var resp = await fetch(url, { method: "POST" });
                if (!resp.ok) {
                    var err = await resp.json();
                    window.showToast(err.error || "Action failed", "error");
                    this.disabled = false;
                    this.textContent = "Retry";
                    return;
                }
                var poll = setInterval(
                    async function () {
                        var p = await (await fetch("/actions/action-progress/" + jobId)).json();
                        var label =
                            action === "tailor-cv"
                                ? "Tailoring CV"
                                : action === "cover-letter"
                                  ? "Writing letter"
                                  : "Scoring";
                        this.textContent = label + "...";
                        if (p.message && p.message !== "Starting...") {
                            this.textContent =
                                p.message.length > 30
                                    ? p.message.substring(0, 30) + "..."
                                    : p.message;
                        }
                        if (!p.running) {
                            clearInterval(poll);
                            window.showToast(p.message || "Done", "");
                            location.reload();
                        }
                    }.bind(this),
                    1000
                );
            } catch (e) {
                window.showToast("Network error", "error");
                this.disabled = false;
                this.textContent = "Retry";
            }
        });
    });

    window.toggleStatusMenu = function (btn) {
        var menu = btn.nextElementSibling;
        var isOpen = menu.classList.contains("open");
        document.querySelectorAll(".status-dropdown-menu.open").forEach(function (m) {
            m.classList.remove("open");
        });
        if (!isOpen) menu.classList.add("open");
    };

    window.changeStatus = async function (jobId, status) {
        var form = document.createElement("form");
        form.method = "POST";
        form.action = "/jobs/" + jobId + "/status";
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "status";
        input.value = status;
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    };

    window.deleteJob = async function (jobId) {
        if (!confirm("Delete this job permanently? This cannot be undone.")) return;
        var form = document.createElement("form");
        form.method = "POST";
        form.action = "/jobs/" + jobId + "/delete";
        document.body.appendChild(form);
        form.submit();
    };

    document.querySelectorAll(".job-row-title").forEach(function (el) {
        el.addEventListener("keydown", function (e) {
            if (e.key === "Enter") window.location.href = this.href;
        });
    });

    window.filterByStatus = function (status, btn) {
        document.querySelectorAll(".status-tab").forEach(function (t) {
            t.classList.remove("active");
        });
        if (btn) btn.classList.add("active");
        document.querySelectorAll("#applied-table tbody tr[data-status]").forEach(function (row) {
            if (status === "all" || row.dataset.status === status) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
        window.syncFilteredRows();
    };
});
