document.addEventListener("DOMContentLoaded", function () {
    var addQueryBtn = document.getElementById("add-query-btn");
    var addQueryForm = document.getElementById("add-query-form");
    var addQueryFormStyle = addQueryForm?.style;
    var editingQueryId = null;
    var queriesData = document.getElementById("queries-data");
    var allQueries = queriesData ? JSON.parse(queriesData.textContent) : [];

    function getChipValues(id) {
        var container = document.getElementById(id);
        if (!container) return [];
        return Array.from(container.querySelectorAll(".filter-chip.active")).map(function (chip) {
            return chip.dataset.value;
        });
    }

    function setChipValues(id, values) {
        var container = document.getElementById(id);
        if (!container) return;
        container.querySelectorAll(".filter-chip").forEach(function (chip) {
            chip.classList.toggle("active", values.indexOf(chip.dataset.value) !== -1);
        });
    }

    function populateForm(q) {
        document.getElementById("q-keywords").value = q.keywords || "";
        document.getElementById("q-locations").value = (q.locations || []).join(", ");
        document.getElementById("q-limit").value = q.limit != null ? q.limit : 25;
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
        var q = allQueries.find(function (q) {
            return q.id === queryId;
        });
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

    document.querySelectorAll(".filter-chips").forEach(function (container) {
        container.addEventListener("click", function (e) {
            var chip = e.target.closest(".filter-chip");
            if (!chip) return;
            chip.classList.toggle("active");
        });
    });

    if (addQueryBtn) {
        addQueryBtn.addEventListener("click", function () {
            if (editingQueryId) {
                exitEditMode();
                addQueryFormStyle.display = "none";
                return;
            }
            var isHidden = addQueryFormStyle.display === "none" || !addQueryFormStyle.display;
            addQueryFormStyle.display = isHidden ? "block" : "none";
            if (isHidden) clearForm();
        });
    }

    document.querySelectorAll(".edit-query").forEach(function (btn) {
        btn.addEventListener("click", function () {
            enterEditMode(parseInt(this.dataset.queryId));
        });
    });

    document.getElementById("cancel-edit-btn")?.addEventListener("click", function () {
        exitEditMode();
        addQueryFormStyle.display = "none";
        addQueryBtn.textContent = "Add Query";
    });

    var saveQueryBtn = document.getElementById("save-query-btn");
    if (saveQueryBtn) {
        saveQueryBtn.addEventListener("click", async function () {
            var keywords = document.getElementById("q-keywords").value;
            var locations = document
                .getElementById("q-locations")
                .value.split(",")
                .map(function (s) {
                    return s.trim();
                })
                .filter(Boolean);
            var limit = parseInt(document.getElementById("q-limit").value);
            if (isNaN(limit)) limit = 25;
            var daysBackInput = document.getElementById("q-days-back");
            var days_back = daysBackInput.value ? parseInt(daysBackInput.value) : null;
            var time_filter = document.getElementById("q-time-filter").value;
            var relevance = document.getElementById("q-relevance").value;
            var job_type = document.getElementById("q-job-type").value || null;
            var experience = document.getElementById("q-experience").value || null;
            var on_site_or_remote = document.getElementById("q-on-site-remote").value || null;
            var base_salary = document.getElementById("q-base-salary").value || null;
            var industry = getChipValues("q-industry");
            var job_function = getChipValues("q-job-function");
            var benefits = getChipValues("q-benefits");
            var commitments = getChipValues("q-commitments");
            var easy_apply = document.getElementById("q-easy-apply").checked;
            var under_10_applicants = document.getElementById("q-under-10").checked;
            var body = {
                keywords: keywords,
                locations: locations,
                limit: limit,
                days_back: days_back,
                time_filter: time_filter,
                relevance: relevance,
                job_type: job_type,
                experience: experience,
                on_site_or_remote: on_site_or_remote,
                base_salary: base_salary,
                industry: industry,
                job_function: job_function,
                benefits: benefits,
                commitments: commitments,
                easy_apply: easy_apply,
                under_10_applicants: under_10_applicants,
            };
            var method = editingQueryId ? "PUT" : "POST";
            var url = editingQueryId ? "/settings/queries/" + editingQueryId : "/settings/queries";
            var resp = await fetch(url, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (resp.ok) {
                window.showToast(editingQueryId ? "Query updated" : "Query saved", "");
                location.reload();
            } else window.showToast("Failed to save query", "error");
        });
    }

    document.querySelectorAll(".delete-query").forEach(function (btn) {
        btn.addEventListener("click", async function () {
            if (!confirm("Delete this query?")) return;
            var resp = await fetch("/settings/queries/" + this.dataset.queryId, {
                method: "DELETE",
            });
            if (resp.ok) {
                window.showToast("Query deleted", "");
                location.reload();
            }
        });
    });

    document.querySelectorAll(".toggle-input").forEach(function (cb) {
        cb.addEventListener("change", async function () {
            var key = this.dataset.toggleKey;
            var value = this.checked ? "1" : "0";
            var resp = await fetch("/settings/setting/" + key, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: value }),
            });
            if (resp.ok) window.showToast("Setting saved", "");
            else window.showToast("Failed to save setting", "error");
        });
    });

    document.querySelectorAll(".save-setting").forEach(function (btn) {
        btn.addEventListener("click", async function () {
            var key = this.dataset.settingKey;
            var inputId = this.dataset.inputId;
            var value = document.getElementById(inputId).value;
            var resp = await fetch("/settings/setting/" + key, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: value }),
            });
            if (resp.ok) window.showToast("Setting saved", "");
            else window.showToast("Failed to save setting", "error");
        });
    });

    document.querySelectorAll(".reset-prompt").forEach(function (btn) {
        btn.addEventListener("click", async function () {
            var key = this.dataset.settingKey;
            var inputId = this.dataset.inputId;
            var defaultValue = this.dataset.default;
            document.getElementById(inputId).value = defaultValue;
            this.textContent = "Saving...";
            var resp = await fetch("/settings/setting/" + key, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: defaultValue }),
            });
            this.textContent = "Reset to Default";
            if (resp.ok) window.showToast("Prompt reset to default", "");
            else window.showToast("Failed to reset prompt", "error");
        });
    });

    var toolStatus = document.getElementById("tool-status");
    if (toolStatus) {
        (async function () {
            try {
                var resp = await fetch("/settings/tool-check");
                var data = await resp.json();
                var tools = {
                    chrome: "Chrome",
                    latex: "LaTeX",
                    pandoc: "Pandoc",
                };
                for (var key in tools) {
                    if (tools.hasOwnProperty(key)) {
                        var span = toolStatus.querySelector('[data-tool="' + key + '"]');
                        if (span) {
                            span.textContent = data[key] ? "available" : "not found";
                            span.className =
                                "tool-status-value " + (data[key] ? "available" : "missing");
                        }
                    }
                }
            } catch (e) {}
        })();
    }

    document.querySelectorAll(".settings-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
            document.querySelectorAll(".settings-tab").forEach(function (t) {
                t.classList.remove("active");
            });
            document.querySelectorAll(".settings-panel").forEach(function (p) {
                p.classList.remove("active");
            });
            this.classList.add("active");
            document.getElementById("panel-" + this.dataset.tab).classList.add("active");
        });
    });
});
