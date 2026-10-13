/* SSDLJobsController: explicit dependencies and controller-owned state. */
(() => {
  'use strict';
  function create(dependencies) {
    const { document, browser, $, state, I18n, t, uiMessage, api, getSnapshot } = dependencies;
    const scope = window.SSDLControllerLifecycle.create(browser);
    const render = scope.effect(dependencies.render);
    const toast = scope.effect(dependencies.toast);
    const refresh = scope.effect(dependencies.refresh);
    const { rows, pendingJobActions, jobPageSizes, jobPageSizeKey, renderWarnings,
      actionIcon, isImageFile, safe, requestJobView, connectX, openMediaSelection } = dependencies;
    const renderJobs = scope.effect(dependencies.renderJobs);
    const busyControls = new Set();
    let searchTimer = null;
    let shownWarnings = null;

    let shownError = null;
    let detailsEpoch = 0;

    scope.listen(rows, 'click', async (event) => {
      const button = event.target.closest('button');
      if (!button || button.disabled) return;
      const job = state.jobs.find((item) => item.id === button.closest('tr')?.dataset.jobId);
      if (!job || pendingJobActions.has(job.id)) return;
      if (button.hasAttribute('data-login')) { connectX(); return; }
      if (button.hasAttribute('data-select-media')) { openMediaSelection(job); return; }
      if (button.hasAttribute('data-open-media')) { openFileAction(job, 'open-file'); return; }
      if (button.hasAttribute('data-open-folder')) { openFileAction(job, 'open-folder'); return; }
      const kind = ['remove', 'retry', 'stop', 'detail', 'warnings'].find((key) => button.hasAttribute('data-' + key));
      if (!kind) return;
      pendingJobActions.set(job.id, kind);
      button.disabled = true;
      renderJobs();
      try {
        const base = '/api/jobs/' + encodeURIComponent(job.id);
        if (kind === 'detail' || kind === 'warnings') {
          const epoch = ++detailsEpoch;
          const detail = await api(base + '/details');
          if (!scope.active || epoch !== detailsEpoch) return;
          if (kind === 'warnings') {
            shownWarnings = detail;
            renderWarnings(detail);
            warningsModal.dataset.jobId = job.id;
            warningsModal.classList.remove('hidden');
            $('#warnings-close').focus();
          } else {
            shownError = detail;
            $('#error-summary').textContent = uiMessage(detail.error);
            $('#error-source').textContent = detail.url;
            $('#error-diagnostic').textContent = detail.error_detail || detail.error;
            errorModal.dataset.jobId = job.id;
            errorModal.classList.remove('hidden');
            $('#error-close').focus();
          }
        } else {
          render(await api(base + (kind === 'remove' ? '' : '/' + kind), { method: 'POST', body: '{}' }));
          if (kind === 'retry') toast(state.paused ? 'ui.queued_again_resume_the_queue_to_start' : 'ui.queued_for_another_download');
        }
      } catch (error) { toast(error.message, true); }
      finally {
        pendingJobActions.delete(job.id);
        if (scope.active && button.isConnected) button.disabled = false;
        renderJobs();
      }
    });

    function renderJobControlButtons() {
      if (!scope.active) return;
      $('#retry-failed').disabled = busyControls.has('retry-failed') || !(getSnapshot()?.counts?.failed);
      $('#clear-done').disabled = busyControls.has('clear-done') || !(getSnapshot()?.counts?.completed);
      $('#clear-all').disabled = busyControls.has('clear-all') || !(getSnapshot()?.total_jobs ?? state.jobs.length) || !getSnapshot()?.safe_queue?.enabled;
    }

    document.querySelectorAll('.filter-tab').forEach((tab) => scope.listen(tab, 'click', () => {
      document.querySelectorAll('.filter-tab').forEach((item) => {
        const selected = item === tab;
        item.classList.toggle('selected', selected);
        item.setAttribute('aria-pressed', String(selected));
      });
      state.filter = tab.dataset.filter;
      state.page = 1;
      requestJobView();
    }));

    scope.listen($('#platform-filter'), 'change', (event) => { state.platform = event.target.value; state.page = 1; requestJobView(); });

    scope.listen($('#search-input'), 'input', (event) => {
      state.search = event.target.value.slice(0, 300); state.page = 1;
      scope.cancel(searchTimer);
      searchTimer = scope.defer(requestJobView, 250);
    });

    scope.listen($('#jobs-page-size'), 'change', (event) => {
      const pageSize = Number(event.target.value);
      if (!jobPageSizes.includes(pageSize)) return;
      state.pageSize = pageSize;
      state.page = 1;
      try { browser.localStorage.setItem(jobPageSizeKey, String(pageSize)); } catch { /* Retain the selection for this page. */ }
      requestJobView();
    });

    function changeJobPage(page) {
      state.page = page;
      requestJobView();
    }

    scope.listen($('#jobs-page-prev'), 'click', () => changeJobPage(state.page - 1));

    scope.listen($('#jobs-page-next'), 'click', () => changeJobPage(state.page + 1));

    scope.listen($('#jobs-page-numbers'), 'click', (event) => {
      const button = event.target.closest('button[data-page]');
      if (button && !button.disabled) changeJobPage(Number(button.dataset.page));
    });

    let pauseBusy = false;

    async function togglePause() {
      if (!scope.active || pauseBusy) return;
      pauseBusy = true;
      const buttons = [$('#pause-queue'), $('#top-pause')];
      buttons.forEach((button) => { button.disabled = true; });
      try { render(await api('/api/pause', { method: 'POST', body: JSON.stringify({ paused: !state.paused }) })); }
      catch (error) { toast(error.message, true); }
      finally { pauseBusy = false; if (scope.active) buttons.forEach((button) => { button.disabled = false; }); }
    }

    scope.listen($('#pause-queue'), 'click', togglePause);

    scope.listen($('#top-pause'), 'click', togglePause);

    scope.listen($('#top-storage'), 'click', async () => {
      const button = $('#top-storage');
      button.disabled = true;
      try { await api('/api/downloads/open', { method: 'POST', body: '{}' }); }
      catch (error) { toast(error.message, true); }
      finally { if (scope.active) button.disabled = false; }
    });

    scope.listen($('#clear-done'), 'click', async () => {
      if (busyControls.has('clear-done')) return;
      busyControls.add('clear-done');
      renderJobControlButtons();
      try { const result = await api('/api/jobs/clear-done', { method: 'POST', body: '{}' }); render(result.state); toast(result.removed ? `已清除 ${result.removed} 個項目` : 'ui.no_completed_jobs_to_clear'); }
      catch (error) { toast(error.message, true); }
      finally { busyControls.delete('clear-done'); renderJobControlButtons(); }
    });

    scope.listen($('#clear-all'), 'click', async () => {
      if (busyControls.has('clear-all')) return;
      busyControls.add('clear-all');
      const button = $('#clear-all');
      button.disabled = true;
      try {
        const result = await api('/api/jobs/clear-all', { method: 'POST', body: '{}' });
        render(result.state);
        toast(result.pending_active ? `已清除 ${result.removed} 個項目；目前工作完成後會自動移除，檔案保留` : `已清除 ${result.removed} 個項目，下載檔案保留`);
      } catch (error) { toast(error.message, true); await refresh(); }
      finally { busyControls.delete('clear-all'); renderJobControlButtons(); }
    });

    scope.listen($('#retry-failed'), 'click', async () => {
      if (busyControls.has('retry-failed')) return;
      busyControls.add('retry-failed');
      const button = $('#retry-failed');
      button.disabled = true;
      try {
        const result = await api('/api/jobs/retry-failed', { method: 'POST', body: '{}' });
        render(result.state);
        toast(result.retried ? `已重新排入 ${result.retried} 個失敗項目${state.paused ? '；請按繼續佇列' : ''}` : 'ui.no_failed_jobs_to_retry');
      } catch (error) { toast(error.message, true); await refresh(); }
      finally { busyControls.delete('retry-failed'); renderJobControlButtons(); }
    });

    const errorModal = $('#error-modal');

    const closeError = scope.effect(() => { detailsEpoch++; errorModal.classList.add('hidden'); });

    scope.listen($('#error-close'), 'click', closeError);

    scope.listen($('#error-ok'), 'click', closeError);

    scope.listen(errorModal, 'click', (event) => { if (event.target === errorModal) closeError(); });

    const warningsModal = $('#warnings-modal');

    function closeWarnings() {
      if (!scope.active) return;
      detailsEpoch++;
      if (warningsModal.classList.contains('hidden')) return;
      warningsModal.classList.add('hidden');
      const trigger = [...rows.querySelectorAll('[data-warnings]')].find((button) => button.dataset.warnings === warningsModal.dataset.jobId);
      trigger?.focus();
    }

    scope.listen($('#warnings-close'), 'click', closeWarnings);

    scope.listen($('#warnings-ok'), 'click', closeWarnings);

    scope.listen(warningsModal, 'click', (event) => { if (event.target === warningsModal) closeWarnings(); });

    scope.listen(warningsModal, 'keydown', (event) => {
      if (event.key !== 'Tab') return;
      const first = $('#warnings-close');
      const last = $('#warnings-ok');
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });

    const filePicker = $('#file-picker-modal');

    let openingFile = false;

    function closeFilePicker() {
      filePickerEpoch++;
      if (!scope.active) return;
      if (filePicker.classList.contains('hidden')) return;
      filePicker.classList.add('hidden');
      const key = filePicker.dataset.mode === 'open-folder' ? 'openFolder' : 'openMedia';
      const trigger = [...rows.querySelectorAll('[data-open-media], [data-open-folder]')].find((button) => button.dataset[key] === filePicker.dataset.jobId);
      trigger?.focus();
    }

    async function runFileAction(job, mode, index) {
      if (!scope.active || openingFile) return;
      openingFile = true;
      closeFilePicker();
      try {
        await api(`/api/jobs/${encodeURIComponent(job.id)}/${mode}`, { method: 'POST', body: JSON.stringify({ file_index: index, filename: job.files[index] }) });
      } catch (error) { toast(error.message, true); await refresh(); }
      finally { openingFile = false; }
    }

    let filePickerEpoch = 0;

    async function openFileAction(job, mode) {
      const count = job.file_count ?? job.files?.length ?? 0;
      if (!scope.active || openingFile || !count) return;
      if (count === 1 && job.files?.length === 1) { runFileAction(job, mode, 0); return; }
      const epoch = ++filePickerEpoch;
      filePicker.dataset.jobId = job.id;
      filePicker.dataset.mode = mode;
      renderFilePickerCopy(mode);
      const list = $('#file-picker-list');
      list.replaceChildren();
      filePicker.classList.remove('hidden');
      $('#file-picker-close').focus();
      let nextOffset = 0;
      let loading = false;
      async function appendChoices() {
        if (loading || nextOffset === null || epoch !== filePickerEpoch) return;
        loading = true;
        let more = $('#file-picker-more');
        if (!more) {
          more = document.createElement('button');
          more.type = 'button'; more.id = 'file-picker-more'; more.className = 'file-choice';
          more.dataset.remaining = String(Math.max(0, count - nextOffset));
          more.addEventListener('click', appendChoices);
          list.append(more);
        }
        more.disabled = true;
        more.textContent = t('ui.loading_files');
        const focusNext = document.activeElement === more;
        try {
          const page = await api('/api/jobs/' + encodeURIComponent(job.id) + '/files?offset=' + nextOffset + '&limit=100');
          if (epoch !== filePickerEpoch || filePicker.classList.contains('hidden')) return;
          more.remove();
          let firstChoice = null;
          for (const item of page.files) {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'file-choice';
            const icon = document.createElement('span');
            icon.className = 'file-choice-icon';
            icon.innerHTML = actionIcon(mode === 'open-folder' ? 'folder' : isImageFile(item.filename) ? 'image' : 'play');
            const label = document.createElement('span'); label.textContent = item.filename;
            button.append(icon, label);
            button.addEventListener('click', () => runFileAction({ id: job.id, files: { [item.index]: item.filename } }, mode, item.index));
            list.append(button);
            firstChoice ||= button;
          }
          nextOffset = page.next_offset;
          if (focusNext) firstChoice?.focus();
          if (nextOffset !== null) {
            more.dataset.remaining = String(page.total - nextOffset);
            more.textContent = t('ui.show_more_files_count_remaining', { count: more.dataset.remaining });
            more.disabled = false;
            list.append(more);
          }
          if (!page.files.length) {
            const empty = document.createElement('p'); empty.textContent = t('ui.no_saved_file_is_available_or_the');
            list.append(empty);
          }
        } catch (error) {
          if (epoch !== filePickerEpoch || filePicker.classList.contains('hidden')) return;
          more.disabled = false;
          more.textContent = t('ui.loading_failed_click_to_retry');
          toast(error.message, true);
        } finally { loading = false; }
      }
      await appendChoices();
    }

    function renderFilePickerCopy(mode) {
      $('#file-picker-title').textContent = t(mode === 'open-folder' ? 'ui.choose_a_file_to_open_its_folder' : 'ui.choose_a_file_to_play_or_view_2');
      $('#file-picker-copy').textContent = t(mode === 'open-folder' ? 'ui.open_the_selected_file_s_folder' : 'ui.videos_images_and_audio_open_in_this');
      const more = $('#file-picker-more');
      if (more) more.textContent = more.disabled ? t('ui.loading_files') : t('ui.show_more_files_count_remaining', { count: more.dataset.remaining || 0 });
    }

    scope.listen($('#file-picker-close'), 'click', closeFilePicker);

    scope.listen($('#file-picker-cancel'), 'click', closeFilePicker);

    scope.listen(filePicker, 'click', (event) => { if (event.target === filePicker) closeFilePicker(); });

    scope.listen(filePicker, 'keydown', (event) => {
      if (event.key !== 'Tab') return;
      const buttons = [...filePicker.querySelectorAll('button:not(:disabled)')];
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });
    function jobViewKey() {
      return JSON.stringify([state.page, state.pageSize, state.filter, state.platform, state.search.slice(0, 300)]);
    }
    function renderSnapshot(data, options = {}) {
      if (!scope.active) return;
      const counts = data.counts || {};
      for (const name of ['queued', 'active', 'completed', 'failed']) $('#tab-' + name).textContent = counts[name] || 0;
      $('#tab-all').textContent = data.total_jobs ?? state.jobs.length;
      $('#tab-selecting').textContent = counts.selecting || 0;
      renderJobControlButtons();
      const platformSelect = $('#platform-filter');
      const current = state.platform;
      const platforms = [...(data.platforms || new Set(state.jobs.map(job => job.platform)))].sort((a,b) => a.localeCompare(b,I18n.locale));
      const markup = '<option value="all">' + t('ui.all_platforms') + '</option>' + platforms.map(name => '<option value="' + safe(name) + '">' + safe(name) + '</option>').join('');
      if (platformSelect.innerHTML !== markup) platformSelect.innerHTML = markup;
      platformSelect.value = platforms.includes(current) ? current : 'all';
      state.platform = platformSelect.value;
      if (state.platform !== current) dependencies.invalidateView();
      data._requestView = jobViewKey();
      renderJobs(options);
    }
    function onLanguageChanged() {
      if (!scope.active) return;
      if (!errorModal.classList.contains('hidden') && shownError) $('#error-summary').textContent = uiMessage(shownError.error);
      if (!warningsModal.classList.contains('hidden') && shownWarnings?.warnings?.length) renderWarnings(shownWarnings);
      if (!filePicker.classList.contains('hidden')) renderFilePickerCopy(filePicker.dataset.mode);
    }
    scope.onDispose(() => { filePickerEpoch++; detailsEpoch++; });
    return Object.freeze({ init: scope.init, dispose: scope.dispose, render: renderSnapshot, viewKey: jobViewKey, renderJobControlButtons, closeError, closeWarnings, closeFilePicker, onLanguageChanged });
  }
  window.SSDLJobsController = Object.freeze({ create });
})();
