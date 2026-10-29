document.addEventListener("DOMContentLoaded", function () {
    var root = document.getElementById("sankey");
    var dataEl = document.getElementById("sankey-data");
    if (!root || !dataEl) return;

    var NS = "http://www.w3.org/2000/svg";
    var NODE_W = 10;
    var PAD = 18; // min vertical gap between nodes in a column
    var LABEL_GAP = 40; // min distance between node centers so two-line labels never collide
    var TOP = 18; // room for the first label above a short node
    var ROOT_LABEL_W = 76; // the first column labels sit left of their bar, clear of the ribbons
    var MIN_WIDTH = 560; // below this the chart scrolls inside its card instead of squashing

    var data = JSON.parse(dataEl.textContent);
    var byId = {};
    data.nodes.forEach(function (n) {
        byId[n.id] = n;
        n.in = [];
        n.out = [];
    });
    data.links.forEach(function (l) {
        l.s = byId[l.source];
        l.t = byId[l.target];
        l.s.out.push(l);
        l.t.in.push(l);
    });

    var card = root.closest(".flow-card");
    var tip = document.createElement("div");
    tip.className = "sankey-tooltip";
    tip.setAttribute("role", "status");
    card.appendChild(tip);

    var selected = null;
    var lastWidth = 0;
    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function svg(tag, attrs, parent) {
        var el = document.createElementNS(NS, tag);
        for (var k in attrs) el.setAttribute(k, attrs[k]);
        if (parent) parent.appendChild(el);
        return el;
    }

    function pct(v, of) {
        var p = (v / of) * 100;
        return p > 0 && p < 1 ? "<1%" : Math.round(p) + "%";
    }

    function plural(v) {
        return v + (v === 1 ? " application" : " applications");
    }

    function layout(width) {
        var labelW = width < 720 ? 104 : 136;
        var height = width < 720 ? 280 : 340;
        var cols = [];
        data.nodes.forEach(function (n) {
            (cols[n.col] = cols[n.col] || []).push(n);
        });
        cols = cols.filter(Boolean);
        var span = cols.length > 1 ? (width - ROOT_LABEL_W - labelW - NODE_W) / (cols.length - 1) : 0;

        var k = Infinity;
        cols.forEach(function (col) {
            var sum = col.reduce(function (a, n) {
                return a + n.value;
            }, 0);
            k = Math.min(k, (height - (col.length - 1) * PAD) / sum);
        });

        data.links.forEach(function (l) {
            l.w = Math.max(1.5, l.value * k);
        });

        var bottom = 0;
        cols.forEach(function (col, ci) {
            var prev = null;
            col.forEach(function (n) {
                var sum = function (ls) {
                    return ls.reduce(function (a, l) {
                        return a + l.w;
                    }, 0);
                };
                n.x = ROOT_LABEL_W + ci * span;
                n.h = Math.max(2, sum(n.in), sum(n.out));
                n.y = prev
                    ? Math.max(prev.y + prev.h + PAD, prev.y + prev.h / 2 + LABEL_GAP - n.h / 2)
                    : TOP + Math.max(0, 12 - n.h / 2);
                bottom = Math.max(bottom, n.y + n.h);
                prev = n;
            });
        });

        // Stack link ends on each node, ordered by the node at the other end so ribbons don't cross.
        data.nodes.forEach(function (n) {
            var y = n.y;
            n.out
                .sort(function (a, b) {
                    return a.t.y - b.t.y;
                })
                .forEach(function (l) {
                    l.y0 = y + l.w / 2;
                    y += l.w;
                });
            y = n.y;
            n.in
                .sort(function (a, b) {
                    return a.s.y - b.s.y;
                })
                .forEach(function (l) {
                    l.y1 = y + l.w / 2;
                    y += l.w;
                });
        });

        return bottom + 24;
    }

    // Flows form a tree, so a node's lineage is its ancestor chain plus every descendant.
    function lineage(node) {
        var lit = new Set([node]);
        for (var n = node; n.in.length; n = n.in[0].s) {
            lit.add(n.in[0]);
            lit.add(n.in[0].s);
        }
        var queue = [node];
        while (queue.length) {
            queue.shift().out.forEach(function (l) {
                lit.add(l);
                lit.add(l.t);
                queue.push(l.t);
            });
        }
        return lit;
    }

    function highlight(lit) {
        root.classList.toggle("is-focusing", !!lit);
        data.nodes.concat(data.links).forEach(function (item) {
            item.el.classList.toggle("is-lit", !!lit && lit.has(item));
        });
    }

    function restore() {
        highlight(selected ? lineage(selected) : null);
        tip.classList.remove("is-visible");
    }

    function showTip(html, clientX, clientY) {
        tip.innerHTML = html;
        var box = card.getBoundingClientRect();
        var x = clientX - box.left + 14;
        var y = clientY - box.top + 14;
        tip.classList.add("is-visible");
        var maxX = box.width - tip.offsetWidth - 8;
        if (x > maxX) x = clientX - box.left - tip.offsetWidth - 14;
        tip.style.transform = "translate(" + Math.max(8, x) + "px," + y + "px)";
    }

    function dot(n) {
        return '<span class="sankey-tooltip-dot" style="background:var(' + n.color + ')"></span>';
    }

    function nodeTip(n) {
        return (
            '<div class="sankey-tooltip-title">' +
            dot(n) +
            n.label +
            '</div><div class="sankey-tooltip-value">' +
            plural(n.value) +
            '</div><div class="sankey-tooltip-meta">' +
            n.hint +
            " · " +
            pct(n.value, data.total) +
            " of all</div>"
        );
    }

    function linkTip(l) {
        return (
            '<div class="sankey-tooltip-title">' +
            dot(l.s) +
            l.s.label +
            '<span class="sankey-tooltip-arrow">→</span>' +
            dot(l.t) +
            l.t.label +
            '</div><div class="sankey-tooltip-value">' +
            plural(l.value) +
            '</div><div class="sankey-tooltip-meta">' +
            pct(l.value, l.s.value) +
            " of " +
            l.s.label +
            "</div>"
        );
    }

    function filterRows(node) {
        document.querySelectorAll("#applied-table tbody tr[data-flow]").forEach(function (row) {
            var hit = !node || row.dataset.flow.split(" ").indexOf(node.id) !== -1;
            row.style.display = hit ? "" : "none";
        });
        document.querySelectorAll(".status-tab").forEach(function (t, i) {
            t.classList.toggle("active", !node && i === 0);
        });
        window.syncFilteredRows();
    }

    function select(node) {
        selected = node === selected ? null : node;
        data.nodes.forEach(function (n) {
            n.el.classList.toggle("is-selected", n === selected);
            n.el.setAttribute("aria-pressed", n === selected);
        });
        filterRows(selected);
        restore();
    }

    function render() {
        var width = Math.max(root.clientWidth, MIN_WIDTH);
        if (width === lastWidth) return;
        var animate = !lastWidth && !reduceMotion;
        lastWidth = width;
        var height = layout(width);

        root.textContent = "";
        var chart = svg("svg", {
            width: width,
            height: height,
            viewBox: "0 0 " + width + " " + height,
            role: "group",
            "aria-label":
                "Application flow: " +
                data.nodes
                    .map(function (n) {
                        return n.label + " " + n.value;
                    })
                    .join(", "),
        });
        var defs = svg("defs", {}, chart);
        var linkLayer = svg("g", {}, chart);
        var nodeLayer = svg("g", {}, chart);

        data.links.forEach(function (l, i) {
            var x0 = l.s.x + NODE_W;
            var x1 = l.t.x;
            var xm = (x0 + x1) / 2;
            var grad = svg(
                "linearGradient",
                { id: "sankey-g" + i, gradientUnits: "userSpaceOnUse", x1: x0, x2: x1, y1: 0, y2: 0 },
                defs
            );
            svg("stop", { offset: "0%", style: "stop-color:var(" + l.s.color + ")" }, grad);
            svg("stop", { offset: "100%", style: "stop-color:var(" + l.t.color + ")" }, grad);
            l.el = svg(
                "path",
                {
                    class: "sankey-link",
                    d: "M" + x0 + "," + l.y0 + "C" + xm + "," + l.y0 + " " + xm + "," + l.y1 + " " + x1 + "," + l.y1,
                    stroke: "url(#sankey-g" + i + ")",
                    "stroke-width": l.w,
                    pathLength: 1,
                    style: "animation-delay:" + l.s.col * 260 + "ms",
                },
                linkLayer
            );
            l.el.addEventListener("mousemove", function (e) {
                highlight(new Set([l, l.s, l.t]));
                showTip(linkTip(l), e.clientX, e.clientY);
            });
            l.el.addEventListener("mouseleave", restore);
        });

        data.nodes.forEach(function (n) {
            var g = svg(
                "g",
                {
                    class: "sankey-node" + (n === selected ? " is-selected" : ""),
                    tabindex: 0,
                    role: "button",
                    "aria-pressed": n === selected,
                    "aria-label": n.label + ": " + plural(n.value) + ", " + pct(n.value, data.total) + ". " + n.hint,
                    style: "animation-delay:" + n.col * 260 + "ms",
                },
                nodeLayer
            );
            n.el = g;
            var left = n.col === data.nodes[0].col;
            var lx = left ? n.x - 10 : n.x + NODE_W + 10;
            var cy = n.y + n.h / 2;
            // Invisible hit area covering bar + label: thin bars are hard to hover on their own.
            svg("rect", {
                class: "sankey-node-hit",
                x: left ? n.x - ROOT_LABEL_W : n.x - 6,
                y: cy - 22,
                width: NODE_W + (left ? ROOT_LABEL_W + 6 : 112),
                height: 44,
            }, g);
            svg("rect", {
                class: "sankey-node-bar",
                x: n.x,
                y: n.y,
                width: NODE_W,
                height: n.h,
                rx: Math.min(3, n.h / 2),
                style: "fill:var(" + n.color + ")",
            }, g);
            var text = svg("text", { class: "sankey-label", x: lx, y: cy - 3, "text-anchor": left ? "end" : "start" }, g);
            svg("tspan", { class: "sankey-label-name" }, text).textContent = n.label;
            svg("tspan", { class: "sankey-label-value", x: lx, y: cy + 13 }, text).textContent =
                n.value + " · " + pct(n.value, data.total);

            g.addEventListener("mousemove", function (e) {
                highlight(lineage(n));
                showTip(nodeTip(n), e.clientX, e.clientY);
            });
            g.addEventListener("mouseleave", restore);
            g.addEventListener("focus", function () {
                highlight(lineage(n));
                var r = g.querySelector(".sankey-node-bar").getBoundingClientRect();
                showTip(nodeTip(n), r.right, r.top);
            });
            g.addEventListener("blur", restore);
            g.addEventListener("click", function () {
                select(n);
            });
            g.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    select(n);
                } else if (e.key === "Escape" && selected) {
                    select(selected);
                }
            });
        });

        root.appendChild(chart);
        if (animate) {
            root.classList.add("is-entering");
            setTimeout(function () {
                root.classList.remove("is-entering");
            }, 2400);
        }
        if (selected) restore();
    }

    // Status tabs filter by status; drop the flow selection so the two filters never disagree.
    document.querySelectorAll(".status-tab").forEach(function (t) {
        t.addEventListener("click", function () {
            if (!selected) return;
            selected.el.classList.remove("is-selected");
            selected.el.setAttribute("aria-pressed", false);
            selected = null;
            restore();
        });
    });

    render();
    new ResizeObserver(render).observe(root);
});
