document.addEventListener("DOMContentLoaded", function () {
    var filterForm = document.getElementById("filter-form");

    function getFilterKeys() {
        return Array.from(filterForm.elements)
            .filter(function (el) {
                return el.name;
            })
            .map(function (el) {
                return el.name;
            });
    }

    function saveFilters() {
        var params = new URLSearchParams();
        getFilterKeys().forEach(function (key) {
            var el = filterForm.elements[key];
            if (el) params.set(key, el.value);
        });
        localStorage.setItem("jobFilters", params.toString());
    }

    function restoreFilters() {
        var saved = localStorage.getItem("jobFilters");
        if (!saved) return;
        var urlParams = new URLSearchParams(window.location.search);
        var savedParams = new URLSearchParams(saved);
        var needsRedirect = false;
        getFilterKeys().forEach(function (key) {
            if (!urlParams.has(key) && savedParams.has(key)) {
                urlParams.set(key, savedParams.get(key));
                needsRedirect = true;
            }
        });
        if (needsRedirect) {
            var qs = urlParams.toString();
            window.location.href = "/jobs/" + (qs ? "?" + qs : "");
        }
    }

    var applyFiltersBtn = document.getElementById("apply-filters-btn");
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener("click", function () {
            saveFilters();
            var params = new URLSearchParams();
            getFilterKeys().forEach(function (key) {
                var el = filterForm.elements[key];
                if (el) params.set(key, el.value);
            });
            window.location.href = "/jobs/?" + params.toString();
        });
    }

    if (applyFiltersBtn) restoreFilters();

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
        document.querySelectorAll("#applied-table tbody tr").forEach(function (row) {
            if (status === "all" || row.dataset.status === status) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    };
});
