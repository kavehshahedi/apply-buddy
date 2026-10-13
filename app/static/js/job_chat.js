document.addEventListener("DOMContentLoaded", function () {
    var card = document.getElementById("job-chat");
    if (!card) return;

    var jobId = card.dataset.jobId;
    var storeKey = "jobChat:" + jobId;
    var log = document.getElementById("chat-log");
    var empty = document.getElementById("chat-empty");
    var form = document.getElementById("chat-form");
    var input = document.getElementById("chat-input");
    var sendBtn = document.getElementById("chat-send");
    var fileInput = document.getElementById("chat-file");
    var attachRow = document.getElementById("chat-attachments");
    var coverLetter = document.getElementById("chat-cl");

    var messages = load();
    var pending = [];
    var busy = false;

    function load() {
        try {
            return JSON.parse(sessionStorage.getItem(storeKey)) || [];
        } catch (e) {
            return [];
        }
    }

    function save() {
        try {
            sessionStorage.setItem(storeKey, JSON.stringify(messages));
        } catch (e) {
            // Quota exceeded (large screenshots): chat still works, just won't survive a reload.
        }
    }

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    // ponytail: minimal Markdown (code, headings, lists, bold/italic, links); no tables.
    function renderMarkdown(src) {
        var blocks = [];
        src = src.replace(/```[^\n]*\n?([\s\S]*?)```/g, function (_, code) {
            blocks.push("<pre><code>" + escapeHtml(code.replace(/\n$/, "")) + "</code></pre>");
            return "\u0000" + (blocks.length - 1) + "\u0000";
        });

        function inline(s) {
            return escapeHtml(s)
                .replace(/`([^`]+)`/g, "<code>$1</code>")
                .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
                .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
                .replace(
                    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
                    '<a href="$2" target="_blank" rel="noopener">$1</a>'
                );
        }

        var html = [];
        var para = [];
        var list = null;

        function flushPara() {
            if (para.length) html.push("<p>" + para.map(inline).join("<br>") + "</p>");
            para = [];
        }
        function closeList() {
            if (list) html.push("</" + list + ">");
            list = null;
        }

        src.split("\n").forEach(function (line) {
            var m;
            if (/^\u0000\d+\u0000$/.test(line.trim())) {
                flushPara();
                closeList();
                html.push(line.trim());
            } else if ((m = line.match(/^#{1,6}\s+(.*)/))) {
                flushPara();
                closeList();
                html.push("<h4>" + inline(m[1]) + "</h4>");
            } else if ((m = line.match(/^\s*([-*+]|\d+[.)])\s+(.*)/))) {
                flushPara();
                var tag = /\d/.test(m[1]) ? "ol" : "ul";
                if (list !== tag) {
                    closeList();
                    html.push("<" + tag + ">");
                    list = tag;
                }
                html.push("<li>" + inline(m[2]) + "</li>");
            } else if (!line.trim()) {
                flushPara();
                closeList();
            } else {
                closeList();
                para.push(line);
            }
        });
        flushPara();
        closeList();

        return html.join("").replace(/\u0000(\d+)\u0000/g, function (_, i) {
            return blocks[+i];
        });
    }

    function scrollToBottom() {
        log.scrollTop = log.scrollHeight;
    }

    function addBubble(msg) {
        var el = document.createElement("div");
        el.className = "chat-msg chat-msg-" + msg.role;

        if (msg.images && msg.images.length) {
            var imgs = document.createElement("div");
            imgs.className = "chat-msg-images";
            msg.images.forEach(function (src) {
                var img = document.createElement("img");
                img.src = src;
                img.alt = "Attached image";
                imgs.appendChild(img);
            });
            el.appendChild(imgs);
        }

        if (msg.content) {
            var body = document.createElement("div");
            body.className = "chat-msg-body";
            if (msg.role === "assistant") body.innerHTML = renderMarkdown(msg.content);
            else body.textContent = msg.content;
            el.appendChild(body);
        }

        if (msg.role === "assistant") {
            var copy = document.createElement("button");
            copy.type = "button";
            copy.className = "chat-text-btn chat-copy";
            copy.textContent = "Copy";
            copy.addEventListener("click", function () {
                navigator.clipboard.writeText(msg.content).then(function () {
                    copy.textContent = "Copied";
                    setTimeout(function () {
                        copy.textContent = "Copy";
                    }, 1500);
                });
            });
            el.appendChild(copy);
        }

        log.appendChild(el);
        scrollToBottom();
        return el;
    }

    function renderAll() {
        log.querySelectorAll(".chat-msg").forEach(function (el) {
            el.remove();
        });
        empty.classList.toggle("hidden", messages.length > 0);
        messages.forEach(addBubble);
    }

    function renderAttachments() {
        attachRow.innerHTML = "";
        pending.forEach(function (src, i) {
            var thumb = document.createElement("div");
            thumb.className = "chat-thumb";
            var img = document.createElement("img");
            img.src = src;
            img.alt = "Pending attachment " + (i + 1);
            var remove = document.createElement("button");
            remove.type = "button";
            remove.setAttribute("aria-label", "Remove image");
            remove.textContent = "×";
            remove.addEventListener("click", function () {
                pending.splice(i, 1);
                renderAttachments();
            });
            thumb.append(img, remove);
            attachRow.appendChild(thumb);
        });
        updateSendState();
    }

    function addImages(files) {
        Array.from(files)
            .filter(function (f) {
                return f && f.type.indexOf("image/") === 0;
            })
            .forEach(function (f) {
                var reader = new FileReader();
                reader.onload = function () {
                    pending.push(reader.result);
                    renderAttachments();
                };
                reader.readAsDataURL(f);
            });
    }

    function autosize() {
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 200) + "px";
    }

    function updateSendState() {
        sendBtn.disabled = busy || (!input.value.trim() && !pending.length);
    }

    function selectedCv() {
        var checked = card.querySelector('input[name="chat-cv"]:checked');
        return checked ? checked.value : "none";
    }

    async function send() {
        var text = input.value.trim();
        if (busy || (!text && !pending.length)) return;

        var msg = { role: "user", content: text, images: pending };
        messages.push(msg);
        empty.classList.add("hidden");
        var bubble = addBubble(msg);
        input.value = "";
        pending = [];
        renderAttachments();
        autosize();

        busy = true;
        updateSendState();
        var typing = document.createElement("div");
        typing.className = "chat-msg chat-msg-assistant chat-typing";
        typing.innerHTML = "<span></span><span></span><span></span>";
        log.appendChild(typing);
        scrollToBottom();

        try {
            var resp = await fetch("/chat/" + jobId, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    messages: messages,
                    cv: selectedCv(),
                    cover_letter: !!(coverLetter && coverLetter.checked),
                }),
            });
            var data = await resp.json().catch(function () {
                return {};
            });
            if (!resp.ok) throw new Error(data.error || "Request failed (" + resp.status + ")");
            var reply = { role: "assistant", content: data.reply };
            messages.push(reply);
            addBubble(reply);
            save();
        } catch (e) {
            // Roll back so the message can be edited and re-sent.
            messages.pop();
            bubble.remove();
            empty.classList.toggle("hidden", messages.length > 0);
            input.value = msg.content;
            pending = msg.images;
            renderAttachments();
            autosize();
            window.showToast(e.message, "error");
        } finally {
            typing.remove();
            busy = false;
            updateSendState();
            input.focus();
        }
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        send();
    });

    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            send();
        }
    });

    input.addEventListener("input", function () {
        autosize();
        updateSendState();
    });

    input.addEventListener("paste", function (e) {
        var files = Array.from(e.clipboardData.items)
            .filter(function (item) {
                return item.kind === "file";
            })
            .map(function (item) {
                return item.getAsFile();
            });
        if (files.length) {
            e.preventDefault();
            addImages(files);
        }
    });

    document.getElementById("chat-attach").addEventListener("click", function () {
        fileInput.click();
    });

    fileInput.addEventListener("change", function () {
        addImages(fileInput.files);
        fileInput.value = "";
    });

    card.addEventListener("dragover", function (e) {
        e.preventDefault();
        card.classList.add("is-dragging");
    });
    card.addEventListener("dragleave", function (e) {
        if (!card.contains(e.relatedTarget)) card.classList.remove("is-dragging");
    });
    card.addEventListener("drop", function (e) {
        e.preventDefault();
        card.classList.remove("is-dragging");
        addImages(e.dataTransfer.files);
    });

    document.getElementById("chat-clear").addEventListener("click", function () {
        messages = [];
        save();
        renderAll();
        input.focus();
    });

    card.querySelectorAll(".chat-suggestions .chat-chip").forEach(function (btn) {
        btn.addEventListener("click", function () {
            input.value = btn.textContent.trim();
            send();
        });
    });

    if (location.hash === "#job-chat") input.focus();
    window.addEventListener("hashchange", function () {
        if (location.hash === "#job-chat") input.focus({ preventScroll: true });
    });

    renderAll();
    updateSendState();
});
