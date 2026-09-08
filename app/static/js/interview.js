document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".prep-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
            document.querySelectorAll(".prep-tab").forEach(function (t) {
                t.classList.remove("active");
            });
            document.querySelectorAll(".prep-panel").forEach(function (p) {
                p.classList.remove("active");
            });
            this.classList.add("active");
            document.getElementById("panel-" + this.dataset.panel).classList.add("active");
        });
    });

    var generatePrepBtn = document.getElementById("generate-prep-btn");
    if (generatePrepBtn) {
        generatePrepBtn.addEventListener("click", async function () {
            var jobId = this.dataset.jobId;
            this.disabled = true;
            this.textContent = "Generating...";
            var progressDiv = document.getElementById("prep-progress");
            var progressText = document.getElementById("prep-progress-text");
            if (progressDiv) progressDiv.classList.remove("hidden");
            if (progressText) progressText.textContent = "Starting generation...";

            var resp = await fetch("/interview/" + jobId + "/generate", { method: "POST" });
            if (!resp.ok) {
                var err = await resp.json();
                window.showToast(err.error || "Failed to start generation", "error");
                this.disabled = false;
                this.textContent = "Generate Interview Prep Pack";
                return;
            }

            var poll = setInterval(async function () {
                var p = await (await fetch("/interview/" + jobId + "/progress")).json();
                if (progressText) progressText.textContent = p.message || "Generating...";
                if (!p.running) {
                    clearInterval(poll);
                    window.showToast("Prep pack generated!", "");
                    location.reload();
                }
            }, 1000);
        });
    }

    var startMockBtn = document.getElementById("start-mock-btn");
    if (startMockBtn) {
        startMockBtn.addEventListener("click", async function () {
            var jobId = this.dataset.jobId;
            var countSelect = document.getElementById("mock-question-count");
            var totalQuestions = parseInt(countSelect ? countSelect.value : 5);

            var resp = await fetch("/interview/" + jobId + "/session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ total_questions: totalQuestions }),
            });

            if (!resp.ok) {
                var err = await resp.json();
                window.showToast(err.error || "Failed to start session", "error");
                return;
            }

            var data = await resp.json();
            window.mockSession = {
                sessionId: data.session_id,
                jobId: jobId,
                totalQuestions: data.total_questions,
                currentQuestion: 0,
                questions: data.questions,
                feedback: [],
                userAnswers: [],
            };

            document.getElementById("mock-setup").style.display = "none";
            document.getElementById("mock-simulator").style.display = "block";
            document.getElementById("mock-summary-area").style.display = "none";

            showQuestion(0);
        });
    }

    function showQuestion(index) {
        var session = window.mockSession;
        if (!session || index >= session.questions.length) return;

        session.currentQuestion = index;
        document.getElementById("mock-current-q").textContent = index + 1;
        document.getElementById("mock-total-q").textContent = session.totalQuestions;
        document.getElementById("mock-question-text").textContent = session.questions[index];
        document.getElementById("mock-question-badge").textContent = index + 1;

        var progress = (index / session.totalQuestions) * 100;
        document.getElementById("mock-progress-fill").style.width = progress + "%";

        document.getElementById("mock-answer-area").style.display = "block";
        document.getElementById("mock-feedback-area").style.display = "none";
        document.getElementById("mock-answer-input").value = "";
        document.getElementById("mock-answer-input").focus();
        document.getElementById("mock-submit-btn").disabled = false;
        document.getElementById("mock-submit-btn").innerHTML =
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg> Submit Answer';
        var charCount = document.getElementById("mock-char-count");
        if (charCount) charCount.textContent = "0";
    }

    var submitBtn = document.getElementById("mock-submit-btn");
    if (submitBtn) {
        submitBtn.addEventListener("click", async function () {
            var session = window.mockSession;
            if (!session) return;

            var answer = document.getElementById("mock-answer-input").value.trim();
            if (!answer) {
                window.showToast("Please enter an answer", "error");
                return;
            }

            this.disabled = true;
            this.innerHTML =
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="spinner" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4" stroke-linecap="round" /><line x1="12" y1="2" x2="12" y2="6" /></svg> Analyzing...';

            try {
                var resp = await fetch(
                    "/interview/" + session.jobId + "/session/" + session.sessionId + "/answer",
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ answer: answer }),
                    }
                );

                if (!resp.ok) {
                    var err = await resp.json();
                    window.showToast(err.error || "Failed to analyze answer", "error");
                    this.disabled = false;
                    this.innerHTML =
                        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg> Submit Answer';
                    return;
                }

                var data = await resp.json();
                if (data.error) {
                    window.showToast(data.error, "error");
                    this.disabled = false;
                    this.innerHTML =
                        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg> Submit Answer';
                    return;
                }

                session.feedback.push(data.feedback);
                session.userAnswers.push(answer);

                document.getElementById("mock-answer-area").style.display = "none";
                document.getElementById("mock-feedback-area").style.display = "block";

                var fb = data.feedback;
                document.getElementById("mock-feedback-score").textContent =
                    (fb.score || 0) + "/100";
                document.getElementById("mock-feedback-text").textContent = fb.feedback || "";

                if (fb.model_answer) {
                    document.getElementById("mock-model-answer").textContent = fb.model_answer;
                    document.getElementById("mock-model-answer-area").style.display = "block";
                } else {
                    document.getElementById("mock-model-answer-area").style.display = "none";
                }

                var strengthsList = document.getElementById("mock-strengths");
                strengthsList.innerHTML = "";
                (fb.key_strengths || []).forEach(function (s) {
                    var li = document.createElement("li");
                    li.textContent = s;
                    strengthsList.appendChild(li);
                });

                var improvementsList = document.getElementById("mock-improvements");
                improvementsList.innerHTML = "";
                (fb.areas_for_improvement || []).forEach(function (s) {
                    var li = document.createElement("li");
                    li.textContent = s;
                    improvementsList.appendChild(li);
                });

                session.currentQuestion++;

                var nextBtn = document.getElementById("mock-next-btn");
                if (session.currentQuestion >= session.totalQuestions) {
                    nextBtn.textContent = "View Summary";
                } else {
                    nextBtn.textContent = "Next Question";
                }
            } catch (e) {
                window.showToast("Network error", "error");
                this.disabled = false;
                this.innerHTML =
                    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg> Submit Answer';
            }
        });
    }

    var nextBtn = document.getElementById("mock-next-btn");
    if (nextBtn) {
        nextBtn.addEventListener("click", function () {
            var session = window.mockSession;
            if (!session) return;

            if (session.currentQuestion >= session.totalQuestions) {
                showSummary();
            } else {
                showQuestion(session.currentQuestion);
            }
        });
    }

    var newSessionBtn = document.getElementById("mock-new-session-btn");
    if (newSessionBtn) {
        newSessionBtn.addEventListener("click", function () {
            window.mockSession = null;
            document.getElementById("mock-simulator").style.display = "none";
            document.getElementById("mock-setup").style.display = "block";
        });
    }

    function showSummary() {
        document.getElementById("mock-question-display").style.display = "none";
        document.getElementById("mock-answer-area").style.display = "none";
        document.getElementById("mock-feedback-area").style.display = "none";
        document.getElementById("mock-summary-area").style.display = "block";

        var session = window.mockSession;
        if (!session) return;

        var scores = session.feedback.map(function (f) {
            return f.score || 0;
        });
        var avgScore =
            scores.length > 0
                ? Math.round(
                      scores.reduce(function (a, b) {
                          return a + b;
                      }, 0) / scores.length
                  )
                : 0;
        document.getElementById("mock-summary-score").textContent = avgScore;

        var content = document.getElementById("mock-summary-content");
        content.innerHTML = "";

        for (var i = 0; i < session.totalQuestions; i++) {
            var div = document.createElement("div");
            div.className = "simulator-summary-section";
            div.innerHTML =
                '<div class="simulator-summary-question">Q' +
                (i + 1) +
                ": " +
                session.questions[i] +
                "</div>" +
                '<div class="simulator-summary-feedback">Score: ' +
                (session.feedback[i]?.score || 0) +
                "/100 \u2014 " +
                (session.feedback[i]?.feedback || "") +
                "</div>";
            content.appendChild(div);
        }
    }

    var voiceBtn = document.getElementById("mock-voice-btn");
    if (voiceBtn) {
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            voiceBtn.style.display = "none";
        } else {
            var recognition = null;
            var isRecording = false;

            voiceBtn.addEventListener("click", function () {
                if (isRecording) {
                    if (recognition) recognition.stop();
                    return;
                }

                isRecording = true;
                voiceBtn.classList.add("recording");

                recognition = new SpeechRecognition();
                recognition.lang = "en-US";
                recognition.interimResults = false;
                recognition.continuous = true;

                recognition.onresult = function (event) {
                    var textarea = document.getElementById("mock-answer-input");
                    for (var i = event.resultIndex; i < event.results.length; i++) {
                        if (event.results[i].isFinal) {
                            textarea.value += event.results[i][0].transcript + " ";
                        }
                    }
                };

                recognition.onerror = function () {
                    isRecording = false;
                    voiceBtn.classList.remove("recording");
                };

                recognition.onend = function () {
                    isRecording = false;
                    voiceBtn.classList.remove("recording");
                };

                recognition.start();
            });
        }
    }

    var answerInput = document.getElementById("mock-answer-input");
    var charCount = document.getElementById("mock-char-count");
    if (answerInput && charCount) {
        answerInput.addEventListener("input", function () {
            charCount.textContent = this.value.length;
        });
    }

    var clearBtn = document.getElementById("mock-clear-btn");
    if (clearBtn && answerInput && charCount) {
        clearBtn.addEventListener("click", function () {
            answerInput.value = "";
            charCount.textContent = "0";
            answerInput.focus();
        });
    }
});
