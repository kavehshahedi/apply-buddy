document.addEventListener("DOMContentLoaded", function () {
    var bar = document.getElementById("bulk-bar");
    var table = document.querySelector("[data-bulk-table]");
    if (!bar || !table) return;

    var allBox = table.querySelector("[data-bulk-all]");
    var countEl = document.getElementById("bulk-count");
    var selectAllBtn = bar.querySelector("[data-bulk-select-all]");
    var lastClicked = null;

    function rowBoxes() {
        return Array.from(table.querySelectorAll("[data-bulk-row]"));
    }

    // Rows hidden by a client-side filter (Applied Board tabs) are never part of the selection.
    function visibleBoxes() {
        return rowBoxes().filter(function (b) {
            return b.closest("tr").style.display !== "none";
        });
    }

    function selectedIds() {
        return visibleBoxes()
            .filter(function (b) {
                return b.checked;
            })
            .map(function (b) {
                return Number(b.value);
            });
    }

    function sync() {
        var visible = visibleBoxes();
        rowBoxes().forEach(function (b) {
            if (visible.indexOf(b) === -1) b.checked = false;
            b.closest("tr").classList.toggle("selected", b.checked);
        });
        var n = selectedIds().length;
        allBox.checked = n > 0 && n === visible.length;
        allBox.indeterminate = n > 0 && n < visible.length;
        countEl.textContent = n;
        selectAllBtn.textContent = "Select all " + visible.length;
        selectAllBtn.hidden = n === visible.length;
        bar.classList.toggle("open", n > 0);
        bar.inert = n === 0;
        document.body.classList.toggle("bulk-active", n > 0);
    }
    window.bulkSync = sync;

    function setAll(checked) {
        visibleBoxes().forEach(function (b) {
            b.checked = checked;
        });
        lastClicked = null;
        sync();
    }

    allBox.addEventListener("change", function () {
        setAll(allBox.checked);
    });
    selectAllBtn.addEventListener("click", function () {
        setAll(true);
    });
    bar.querySelector("[data-bulk-clear]").addEventListener("click", function () {
        setAll(false);
    });

    // Shift-click selects (or clears) the whole range since the last clicked row.
    table.addEventListener("click", function (e) {
        var box = e.target.closest("[data-bulk-row]");
        if (!box) return;
        var visible = visibleBoxes();
        if (e.shiftKey && lastClicked && visible.indexOf(lastClicked) !== -1) {
            var a = visible.indexOf(lastClicked);
            var b = visible.indexOf(box);
            visible.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(function (x) {
                x.checked = box.checked;
            });
        }
        lastClicked = box;
        sync();
    });

    document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;
        var openMenu = bar.querySelector(".status-dropdown-menu.open");
        if (openMenu) openMenu.classList.remove("open");
        else if (selectedIds().length) setAll(false);
    });

    async function run(body, doneMsg) {
        var ids = selectedIds();
        var buttons = bar.querySelectorAll("button");
        buttons.forEach(function (b) {
            b.disabled = true;
        });
        try {
            var resp = await fetch("/jobs/bulk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(Object.assign({ ids: ids }, body)),
            });
            if (!resp.ok) throw new Error();
            var data = await resp.json();
            sessionStorage.setItem("autopilot_toast", doneMsg(data.count) + "||success");
            location.reload();
        } catch (err) {
            window.showToast("Bulk update failed", "error");
            buttons.forEach(function (b) {
                b.disabled = false;
            });
        }
    }

    function jobs(n) {
        return n + (n === 1 ? " job" : " jobs");
    }

    bar.querySelectorAll("[data-bulk-status]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var status = btn.dataset.bulkStatus;
            run({ action: "status", status: status }, function (n) {
                return status === "archived" ? "Archived " + jobs(n) : "Moved " + jobs(n) + " to " + status[0].toUpperCase() + status.slice(1);
            });
        });
    });

    bar.querySelector("[data-bulk-delete]").addEventListener("click", function () {
        var n = selectedIds().length;
        if (!confirm("Delete " + jobs(n) + " permanently? This cannot be undone.")) return;
        run({ action: "delete" }, function (n) {
            return "Deleted " + jobs(n);
        });
    });

    sync();
});
