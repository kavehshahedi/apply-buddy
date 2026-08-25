document.addEventListener('DOMContentLoaded', function () {
  const toast = document.getElementById('toast');

  function showToast(msg, type) {
    if (!toast) return;
    toast.textContent = msg;
    toast.className = type === 'error' ? 'toast-error' : 'toast-success';
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 4000);
  }

  // Sort / Filter controls
  const applyFiltersBtn = document.getElementById('apply-filters-btn');
  if (applyFiltersBtn) {
    applyFiltersBtn.addEventListener('click', function () {
      const sort = document.getElementById('sort-select').value;
      const order = document.getElementById('order-select').value;
      const minScore = document.getElementById('min-score-input').value || '0';
      window.location.href = `/jobs/?sort=${sort}&order=${order}&min_score=${minScore}`;
    });
  }

  // Fetch Jobs
  function setupFetchJobs(btnId, progressId, textId) {
    const fetchBtn = document.getElementById(btnId);
    const progressDiv = document.getElementById(progressId);
    const progressText = document.getElementById(textId);
    if (!fetchBtn) return;
    fetchBtn.addEventListener('click', async function () {
      fetchBtn.disabled = true;
      fetchBtn.textContent = 'Fetching...';
      if (progressDiv) {
        progressDiv.classList.remove('hidden');
        if (progressText) progressText.textContent = 'Starting scrape...';
      }
      const resp = await fetch('/scrape/run', { method: 'POST' });
      if (!resp.ok) {
        const err = await resp.json();
        if (progressText) progressText.textContent = err.error || 'Failed to start scrape.';
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch Jobs';
        return;
      }
      const poll = setInterval(async () => {
        const p = await (await fetch('/scrape/progress')).json();
        if (progressText) progressText.textContent = p.message || `Scraped ${p.current}/${p.total} (${p.errors} errors)`;
        if (!p.running) {
          clearInterval(poll);
          fetchBtn.disabled = false;
          fetchBtn.textContent = 'Fetch Jobs';
          if (p.errors > 0) showToast(`Scrape finished with ${p.errors} errors`, 'error');
          else showToast(`Scrape complete: ${p.current} jobs`, '');
          location.reload();
        }
      }, 1000);
    });
  }

  setupFetchJobs('fetch-jobs-btn', 'scrape-progress', 'scrape-progress-text');
  setupFetchJobs('fetch-jobs-btn-empty', 'scrape-progress', 'scrape-progress-text');

  // Manual fetch by URL
  const manualFetchBtn = document.getElementById('manual-fetch-btn');
  const manualFetchOverlay = document.getElementById('manual-fetch-overlay');
  const manualFetchClose = document.getElementById('manual-fetch-close');
  const manualFetchCancel = document.getElementById('manual-fetch-cancel');
  const manualFetchSubmit = document.getElementById('manual-fetch-submit');
  const manualFetchUrl = document.getElementById('manual-fetch-url');
  const manualFetchProgress = document.getElementById('manual-fetch-progress');
  const manualFetchProgressText = document.getElementById('manual-fetch-progress-text');

  function openManualFetchModal() {
    if (manualFetchOverlay) {
      manualFetchOverlay.classList.remove('hidden');
      manualFetchUrl.value = '';
      manualFetchUrl.focus();
      if (manualFetchProgress) manualFetchProgress.classList.add('hidden');
      manualFetchSubmit.disabled = false;
      manualFetchSubmit.textContent = 'Fetch Job';
    }
  }

  function closeManualFetchModal() {
    if (manualFetchOverlay) manualFetchOverlay.classList.add('hidden');
  }

  if (manualFetchBtn) {
    manualFetchBtn.addEventListener('click', openManualFetchModal);
  }
  const manualFetchBtnEmpty = document.getElementById('manual-fetch-btn-empty');
  if (manualFetchBtnEmpty) {
    manualFetchBtnEmpty.addEventListener('click', openManualFetchModal);
  }
  if (manualFetchClose) {
    manualFetchClose.addEventListener('click', closeManualFetchModal);
  }
  if (manualFetchCancel) {
    manualFetchCancel.addEventListener('click', closeManualFetchModal);
  }
  if (manualFetchOverlay) {
    manualFetchOverlay.addEventListener('click', function (e) {
      if (e.target === this) closeManualFetchModal();
    });
  }
  if (manualFetchUrl) {
    manualFetchUrl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') manualFetchSubmit.click();
    });
  }

  if (manualFetchSubmit) {
    manualFetchSubmit.addEventListener('click', async function () {
      const url = manualFetchUrl.value.trim();
      if (!url) {
        showToast('Please enter a LinkedIn job URL', 'error');
        manualFetchUrl.focus();
        return;
      }
      if (!url.startsWith('https://www.linkedin.com/jobs/view/')) {
        showToast('URL must start with https://www.linkedin.com/jobs/view/', 'error');
        manualFetchUrl.focus();
        return;
      }

      manualFetchSubmit.disabled = true;
      manualFetchSubmit.textContent = 'Fetching...';
      if (manualFetchProgress) {
        manualFetchProgress.classList.remove('hidden');
        if (manualFetchProgressText) manualFetchProgressText.textContent = 'Starting fetch...';
      }

      const resp = await fetch('/manual-fetch/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url })
      });

      if (!resp.ok) {
        const err = await resp.json();
        if (manualFetchProgressText) manualFetchProgressText.textContent = err.error || 'Failed to start fetch.';
        manualFetchSubmit.disabled = false;
        manualFetchSubmit.textContent = 'Fetch Job';
        showToast(err.error || 'Failed to start fetch', 'error');
        return;
      }

      const poll = setInterval(async () => {
        const p = await (await fetch('/manual-fetch/progress')).json();
        if (manualFetchProgressText) manualFetchProgressText.textContent = p.message || `Fetching...`;
        if (!p.running) {
          clearInterval(poll);
          closeManualFetchModal();
          if (p.errors > 0) showToast(p.message || 'Fetch failed', 'error');
          else showToast('Job added successfully!', '');
          location.reload();
        }
      }, 1000);
    });
  }

  // Score Fit
  const scoreBtn = document.getElementById('score-fit-btn');
  const scoreProgress = document.getElementById('score-progress');
  const scoreProgressText = document.getElementById('score-progress-text');
  const forceRescoreCheckbox = document.getElementById('force-rescore-checkbox');
  if (scoreBtn) {
    scoreBtn.addEventListener('click', async function () {
      scoreBtn.disabled = true;
      scoreBtn.textContent = 'Starting...';
      if (scoreProgress) {
        scoreProgress.classList.remove('hidden');
        if (scoreProgressText) scoreProgressText.textContent = 'Starting scoring...';
      }
      const force = forceRescoreCheckbox ? forceRescoreCheckbox.checked : false;
      const params = force ? '?force=true' : '';
      const resp = await fetch('/actions/score-fit' + params, { method: 'POST' });
      if (!resp.ok) {
        const err = await resp.json();
        if (scoreProgressText) scoreProgressText.textContent = err.error || 'Failed to start scoring.';
        scoreBtn.disabled = false;
        scoreBtn.textContent = 'Score Fit';
        return;
      }
      const poll = setInterval(async () => {
        const p = await (await fetch('/actions/score-progress')).json();
        if (scoreProgressText) scoreProgressText.textContent = p.message || `Scored ${p.current}/${p.total}`;
        if (!p.running) {
          clearInterval(poll);
          scoreBtn.disabled = false;
          scoreBtn.textContent = 'Score Fit';
          if (p.errors > 0) showToast(`Scoring finished with ${p.errors} errors`, 'error');
          else showToast(`Scoring complete: ${p.current} jobs`, '');
          location.reload();
        }
      }, 1000);
    });
  }

  // Action buttons (tailor CV, cover letter)
  document.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', async function () {
      const action = this.dataset.action;
      const jobId = this.dataset.jobId;
      this.disabled = true;
      this.textContent = 'Starting...';
      try {
        const resp = await fetch(`/actions/${action}/${jobId}`, { method: 'POST' });
        if (!resp.ok) {
          const err = await resp.json();
          showToast(err.error || 'Action failed', 'error');
          this.disabled = false;
          this.textContent = 'Retry';
          return;
        }
        const poll = setInterval(async () => {
          const p = await (await fetch(`/actions/action-progress/${jobId}`)).json();
          const label = action === 'tailor-cv' ? 'Tailoring CV' : action === 'cover-letter' ? 'Writing letter' : 'Scoring';
          this.textContent = `${label}...`;
          if (p.message && p.message !== 'Starting...') {
            this.textContent = p.message.length > 30 ? p.message.substring(0, 30) + '...' : p.message;
          }
          if (!p.running) {
            clearInterval(poll);
            showToast(p.message || 'Done', '');
            location.reload();
          }
        }, 1000);
      } catch (e) {
        showToast('Network error', 'error');
        this.disabled = false;
        this.textContent = 'Retry';
      }
    });
  });

  // Settings: Add query
  const addQueryBtn = document.getElementById('add-query-btn');
  const addQueryForm = document.getElementById('add-query-form');
  if (addQueryBtn) {
    addQueryBtn.addEventListener('click', () => {
      const isHidden = addQueryForm.style.display === 'none' || !addQueryForm.style.display;
      addQueryForm.style.display = isHidden ? 'block' : 'none';
    });
  }
  const saveQueryBtn = document.getElementById('save-query-btn');
  if (saveQueryBtn) {
    saveQueryBtn.addEventListener('click', async function () {
      const keywords = document.getElementById('q-keywords').value;
      const locations = document.getElementById('q-locations').value.split(',').map(s => s.trim()).filter(Boolean);
      const limit = parseInt(document.getElementById('q-limit').value) || 25;
      const daysBackInput = document.getElementById('q-days-back');
      const days_back = daysBackInput.value ? parseInt(daysBackInput.value) : null;
      const resp = await fetch('/settings/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords, locations, limit, days_back })
      });
      if (resp.ok) { showToast('Query saved', ''); location.reload(); }
      else showToast('Failed to save query', 'error');
    });
  }

  // Delete query
  document.querySelectorAll('.delete-query').forEach(btn => {
    btn.addEventListener('click', async function () {
      if (!confirm('Delete this query?')) return;
      const resp = await fetch(`/settings/queries/${this.dataset.queryId}`, { method: 'DELETE' });
      if (resp.ok) { showToast('Query deleted', ''); location.reload(); }
    });
  });

  // Toggle switch save
  document.querySelectorAll('.toggle-input').forEach(cb => {
    cb.addEventListener('change', async function () {
      const key = this.dataset.toggleKey;
      const value = this.checked ? '1' : '0';
      const resp = await fetch(`/settings/setting/${key}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value })
      });
      if (resp.ok) showToast('Setting saved', '');
      else showToast('Failed to save setting', 'error');
    });
  });

  // Save setting
  document.querySelectorAll('.save-setting').forEach(btn => {
    btn.addEventListener('click', async function () {
      const key = this.dataset.settingKey;
      const inputId = this.dataset.inputId;
      const value = document.getElementById(inputId).value;
      const resp = await fetch(`/settings/setting/${key}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value })
      });
      if (resp.ok) showToast('Setting saved', '');
      else showToast('Failed to save setting', 'error');
    });
  });

  // Reset prompt to default
  document.querySelectorAll('.reset-prompt').forEach(btn => {
    btn.addEventListener('click', async function () {
      const key = this.dataset.settingKey;
      const inputId = this.dataset.inputId;
      const defaultValue = this.dataset.default;
      document.getElementById(inputId).value = defaultValue;
      this.textContent = 'Saving...';
      const resp = await fetch(`/settings/setting/${key}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: defaultValue })
      });
      this.textContent = 'Reset to Default';
      if (resp.ok) showToast('Prompt reset to default', '');
      else showToast('Failed to reset prompt', 'error');
    });
  });

  // Tool status check
  const toolStatus = document.getElementById('tool-status');
  if (toolStatus) {
    (async function () {
      try {
        const resp = await fetch('/settings/tool-check');
        const data = await resp.json();
        for (const [key, label] of Object.entries({ chrome: 'Chrome', latex: 'LaTeX', pandoc: 'Pandoc' })) {
          const span = toolStatus.querySelector(`[data-tool="${key}"]`);
          if (span) {
            span.textContent = data[key] ? 'available' : 'not found';
            span.className = 'tool-status-value ' + (data[key] ? 'available' : 'missing');
          }
        }
      } catch (e) { }
    })();
  }

  // Applied board: filter by status
  window.filterByStatus = function(status, btn) {
    document.querySelectorAll('.status-tab').forEach(t => t.classList.remove('active'));
    if (btn) btn.classList.add('active');
    document.querySelectorAll('#applied-table tbody tr').forEach(row => {
      if (status === 'all' || row.dataset.status === status) {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  };

  // Job listings: toggle status dropdown
  window.toggleStatusMenu = function(btn) {
    const menu = btn.nextElementSibling;
    const isOpen = menu.classList.contains('open');
    document.querySelectorAll('.status-dropdown-menu.open').forEach(m => m.classList.remove('open'));
    if (!isOpen) menu.classList.add('open');
  };

  // Job listings: change status via dropdown
  window.changeStatus = async function(jobId, status) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/jobs/${jobId}/status`;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'status';
    input.value = status;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
  };

  // Close dropdowns on click outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.status-dropdown-wrap')) {
      document.querySelectorAll('.status-dropdown-menu.open').forEach(m => m.classList.remove('open'));
    }
  });

  // Enter key on job rows goes to detail
  document.querySelectorAll('.job-row-title').forEach(el => {
    el.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') window.location.href = this.href;
    });
  });

  // Settings tabs
  document.querySelectorAll('.settings-tab').forEach(tab => {
    tab.addEventListener('click', function() {
      document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      document.getElementById('panel-' + this.dataset.tab).classList.add('active');
    });
  });
});