document.addEventListener("DOMContentLoaded", function () {
    function setupAutopilot(btnId, progressId, textId) {
        var btn = document.getElementById(btnId);
        var progressDiv = document.getElementById(progressId);
        var progressText = document.getElementById(textId);
        if (!btn) return;
        btn.addEventListener("click", async function () {
            btn.disabled = true;
            btn.textContent = "Starting...";
            if (progressDiv) {
                progressDiv.classList.remove("hidden");
                if (progressText) progressText.textContent = "Starting Auto-Pilot...";
            }
            var skipFetch = document.getElementById("autopilot-skip-fetch")?.checked || false;
            var resp = await fetch("/autopilot/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ skip_fetch: skipFetch }),
            });
            if (!resp.ok) {
                var err = await resp.json();
                if (progressText)
                    progressText.textContent = err.error || "Failed to start Auto-Pilot.";
                btn.disabled = false;
                btn.textContent = "Run";
                return;
            }
            var poll = setInterval(async function () {
                var p = await (await fetch("/autopilot/progress")).json();
                if (progressText) {
                    progressText.textContent = p.message || "Working...";
                }
                if (!p.running) {
                    clearInterval(poll);
                    btn.disabled = false;
                    btn.textContent = "Run";
                    var msg, type;
                    if (p.phase === "error") {
                        msg = p.message || "Auto-Pilot encountered an error";
                        type = "error";
                    } else if (p.errors > 0) {
                        msg =
                            "Auto-Pilot finished with " +
                            p.errors +
                            " error" +
                            (p.errors > 1 ? "s" : "");
                        type = "error";
                    } else {
                        var parts = [];
                        if (p.scraped_count > 0) parts.push("scraped " + p.scraped_count);
                        if (p.scored_count > 0) parts.push("scored " + p.scored_count);
                        if (p.tailored_count > 0)
                            parts.push("tailored " + p.tailored_count + " CVs");
                        if (p.cl_count > 0)
                            parts.push(
                                "generated " +
                                    p.cl_count +
                                    " cover letter" +
                                    (p.cl_count > 1 ? "s" : "")
                            );
                        msg =
                            parts.length > 0
                                ? "Auto-Pilot complete: " + parts.join(", ")
                                : "Auto-Pilot complete";
                        type = "success";
                    }
                    sessionStorage.setItem("autopilot_toast", msg + "||" + type);
                    location.reload();
                }
            }, 1000);
        });
    }

    setupAutopilot("autopilot-btn", "autopilot-progress", "autopilot-progress-text");

    var resetBtn = document.getElementById("autopilot-reset-btn");
    if (resetBtn) {
        resetBtn.addEventListener("click", async function () {
            if (!confirm("Reset all ready jobs to 'new' so Auto-Pilot can re-process them?"))
                return;
            resetBtn.disabled = true;
            resetBtn.textContent = "Resetting...";
            var resp = await fetch("/autopilot/reset", { method: "POST" });
            if (resp.ok) {
                var data = await resp.json();
                window.showToast(
                    "Reset " + data.reset_count + " jobs. Redirecting to Job Listings...",
                    ""
                );
                setTimeout(function () {
                    window.location.href = "/jobs/";
                }, 800);
            } else {
                window.showToast("Failed to reset jobs", "error");
                resetBtn.disabled = false;
                resetBtn.textContent = "Reset All & Re-run";
            }
        });
    }
});
