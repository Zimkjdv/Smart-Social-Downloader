/* SSDLDiagnosticsController: explicit dependencies and controller-owned state. */
(() => {
  'use strict';
  function create(dependencies) {
    const { document, browser, $, state, I18n, t, uiMessage, uiText, api, getSnapshot, isOffline } = dependencies;
    const scope = window.SSDLControllerLifecycle.create(browser);
    const render = scope.effect(dependencies.render);
    const toast = scope.effect(dependencies.toast);
    const { scheduleStatusRefresh, timeLabel, fileSize } = dependencies;
    let lastEnvironment = null;
    let environmentRenderKey = '';
    let environmentRequestBusy = false;
    const busyControls = new Set();
    const exportUrls = new Set();
    function renderStorageMaintenance(data = getSnapshot()) {
      if (!scope.active) return;
      const storage = data?.storage || {};
      const cache = data?.thumbnail_cache || {};
      $('#storage-scan-summary').textContent = t(storage.refreshing ? 'ui.scanning_the_download_folder_in_the_background' : 'ui.last_full_scan_time', { time: timeLabel(storage.checked_at) }) +
        (storage.partial ? t('ui.some_files_could_not_be_read_statistics') : '');
      $('#thumbnail-cache-summary').textContent = cache.ready
        ? t('ui.thumbnail_cache_size_limit_count_previews', { size: fileSize(cache.total_bytes), limit: fileSize(cache.max_bytes), count: cache.file_count })
        : t('ui.loading_thumbnail_cache_status');
      if (cache.partial) $('#thumbnail-cache-summary').textContent += t('ui.some_cached_previews_could_not_be_removed');
      $('#storage-rescan').disabled = isOffline() || busyControls.has('storage-rescan') || Boolean(storage.refreshing);
      $('#thumbnail-cache-clear').disabled = isOffline() || busyControls.has('thumbnail-cache-clear') || Boolean(cache.clearing);
    }

    for (const [id, path, copy] of [
      ['storage-rescan', '/api/storage/rescan', '已開始背景容量掃描'],
      ['thumbnail-cache-clear', '/api/thumbnails/clear', '已排入縮圖快取清理'],
    ]) {
      scope.listen($('#' + id), 'click', async () => {
        if (busyControls.has(id)) return;
        busyControls.add(id);
        renderStorageMaintenance();
        try { render(await api(path, { method: 'POST', body: '{}' })); toast(copy); }
        catch (error) { toast(error.message, true); }
        finally { busyControls.delete(id); renderStorageMaintenance(); }
      });
    }

    function renderEnvironment(report = lastEnvironment) {
      if (!scope.active || !report) return;
      lastEnvironment = report;
      $('#environment-refresh').disabled = environmentRequestBusy || report.busy;
      $('#environment-refresh').setAttribute('aria-busy', String(environmentRequestBusy || report.busy));
      $('#environment-refresh').textContent = t(report.busy ? 'ui.checking' : 'ui.recheck');
      const summary = report.busy ? '正在檢查本機環境…' :
        report.phase === 'idle' ? '尚未執行環境診斷。' : report.status === 'ok' ? '環境已就緒。' :
        t('ui.environment_errors_checks_need_repair_warnings_need', { errors: report.errors, warnings: report.warnings });
      if ($('#environment-summary').textContent !== uiMessage(summary)) uiText($('#environment-summary'), summary);
      const key = JSON.stringify(report.checks) + I18n.locale;
      if (key === environmentRenderKey) return;
      environmentRenderKey = key;
      $('#environment-checks').replaceChildren(...report.checks.map((check) => {
        const item = document.createElement('li');
        item.dataset.status = check.status;
        const heading = document.createElement('div');
        heading.className = 'environment-check-heading';
        const name = document.createElement('b');
        name.textContent = t(check.name);
        const status = document.createElement('span');
        status.textContent = t({ ok: 'ui.ok', warning: 'ui.attention', error: 'ui.needs_repair' }[check.status]);
        heading.append(name, status);
        const detail = document.createElement('p');
        detail.textContent = (check.version ? `${check.version} · ` : '') + uiMessage(check.detail);
        item.append(heading, detail);
        if (check.hint) {
          const hint = document.createElement('p');
          hint.className = 'environment-check-hint';
          hint.textContent = uiMessage(check.hint);
          item.append(hint);
        }
        return item;
      }));
    }

    async function loadEnvironment(recheck = false) {
      if (!scope.active || environmentRequestBusy || (recheck && lastEnvironment?.busy)) return;
      environmentRequestBusy = true;
      $('#environment-refresh').disabled = true;
      try {
        const report = await api(recheck ? '/api/environment/refresh' : '/api/environment',
          recheck ? { method: 'POST', body: '{}' } : {});
        if (!scope.active) return;
        renderEnvironment(report);
        scheduleStatusRefresh();
      } catch (error) { if (scope.active) uiText($('#environment-summary'), error.message); }
      finally {
        environmentRequestBusy = false;
        if (scope.active) {
          $('#environment-refresh').disabled = Boolean(lastEnvironment?.busy);
          $('#environment-refresh').setAttribute('aria-busy', String(Boolean(lastEnvironment?.busy)));
        }
      }
    }

    scope.listen($('#environment-refresh'), 'click', () => loadEnvironment(true));

    function renderLocalHealth(data) {
      if (!scope.active) return;
      const persistence = data.persistence;
      const message = persistence?.error || '紀錄保存正常。';
      if ($('#persistence-summary').textContent !== uiMessage(message)) uiText($('#persistence-summary'), message);
      $('#persistence-summary').classList.toggle('error', Boolean(persistence && !persistence.healthy));
      $('#state-save').disabled = busyControls.has('state-save') || Boolean(persistence?.blocked);
      const worker = data.worker;
      const workerMessage = !worker?.alive ? '下載排程未運作' : worker.phase === 'idle' ? '下載排程正常，等待新任務。' :
        worker.phase === 'waiting' ? '下載工作等待安全佇列。' : t('ui.worker_running_seconds_seconds_since_the_last', { seconds: worker.no_progress_seconds ?? 0 });
      if ($('#worker-summary').textContent !== uiMessage(workerMessage)) uiText($('#worker-summary'), workerMessage);
    }

    scope.listen($('#state-save'), 'click', async () => {
      if (busyControls.has('state-save')) return;
      busyControls.add('state-save');
      $('#state-save').disabled = true;
      try { const result = await api('/api/state/save', { method: 'POST', body: '{}' }); render(result); }
      catch (error) { toast(error.message, true); }
      finally { busyControls.delete('state-save'); if (getSnapshot()) renderLocalHealth(getSnapshot()); }
    });

    scope.listen($('#diagnostics-export'), 'click', async () => {
      const button = $('#diagnostics-export');
      button.disabled = true;
      try {
        const report = await api('/api/diagnostics');
        if (!scope.active) return;
        const url = browser.URL.createObjectURL(new browser.Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
        exportUrls.add(url);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'ssdl-diagnostics.json';
        link.click();
        scope.defer(() => { browser.URL.revokeObjectURL(url); exportUrls.delete(url); }, 1000);
      } catch (error) { toast(error.message, true); }
      finally { if (scope.active) button.disabled = false; }
    });

    function renderEngineStatus(label, detail, offline, visible = offline) {
      if (!scope.active) return;
      const engine = $('#engine-status');
      engine.classList.toggle('hidden', !visible);
      engine.classList.toggle('offline', offline);
      engine.title = detail;
      // Avoid repeated live-region announcements while polling unchanged state.
      if ($('#engine-title').textContent !== label) $('#engine-title').textContent = label;
      if ($('#engine-subtitle').textContent !== detail) $('#engine-subtitle').textContent = detail;
    }
    function renderSnapshot(data) {
      if (!scope.active) return;
      renderStorageMaintenance(data);
      renderEnvironment(data.environment);
      renderLocalHealth(data);
      const environmentIssue = lastEnvironment?.checked_at > 0 && lastEnvironment.status !== 'ok';
      const savingIssue = data.persistence && (!data.persistence.healthy || data.persistence.recovered);
      const workerIssue = data.worker && !data.worker.alive;
      renderEngineStatus(t(savingIssue ? 'ui.local_history_needs_attention' : workerIssue ? 'ui.download_worker_unavailable' : !state.ready ? 'ui.engines_need_repair' : environmentIssue ? 'ui.environment_needs_attention' : 'ui.engines_ready'),
        savingIssue ? uiMessage(data.persistence.error) : workerIssue ? t('ui.restart_the_service_or_export_diagnostics_for') : !state.ready || environmentIssue ? t('ui.open_environment_diagnostics_in_settings_for_repair') : t('ui.image_and_video_engines_ready_original_encoding'),
        savingIssue && !data.persistence.healthy || workerIssue || !state.ready, savingIssue || workerIssue || !state.ready || environmentIssue);
    }
    scope.onDispose(() => { for (const url of exportUrls) browser.URL.revokeObjectURL(url); exportUrls.clear(); });
    return Object.freeze({ init: scope.init, dispose: scope.dispose, render: renderSnapshot, renderStorageMaintenance, renderEngineStatus, load: loadEnvironment, get report() { return lastEnvironment; } });
  }
  window.SSDLDiagnosticsController = Object.freeze({ create });
})();
