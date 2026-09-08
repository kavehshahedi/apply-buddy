document.addEventListener("DOMContentLoaded", function () {
    const toast = document.getElementById("toast");

    window.showToast = function (msg, type) {
        if (!toast) return;
        toast.textContent = msg;
        toast.className = type === "error" ? "toast-error" : "toast-success";
        toast.classList.remove("hidden");
        setTimeout(function () {
            toast.classList.add("hidden");
        }, 4000);
    };

    const pending = sessionStorage.getItem("autopilot_toast");
    if (pending) {
        sessionStorage.removeItem("autopilot_toast");
        var parts = pending.split("||");
        window.showToast(parts[0], parts[1] || "");
    }

    var hamburgerBtn = document.getElementById("hamburger-btn");
    var mobileNav = document.getElementById("mobile-nav");
    if (hamburgerBtn && mobileNav) {
        hamburgerBtn.addEventListener("click", function () {
            var isOpen = mobileNav.classList.toggle("open");
            hamburgerBtn.setAttribute("aria-expanded", isOpen);
        });
        document.addEventListener("click", function (e) {
            if (!e.target.closest("#hamburger-btn") && !e.target.closest("#mobile-nav")) {
                mobileNav.classList.remove("open");
                hamburgerBtn.setAttribute("aria-expanded", "false");
            }
        });
    }

    document.addEventListener("click", function (e) {
        if (!e.target.closest(".status-dropdown-wrap")) {
            document.querySelectorAll(".status-dropdown-menu.open").forEach(function (m) {
                m.classList.remove("open");
            });
        }
    });
});
