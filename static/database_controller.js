/* Explicit SQLite maintenance UI; one owned poll and no mutation retries. */
(() => {
  'use strict';
  function create({ browser, document, $, t, api, uiMessage, getSnapshot, fileSize, toast }) {
    const scope = window.SSDLControllerLifecycle.create(browser);
    const dialog = $('#database-confirm-dialog');
    let report = null, pending = false, timer = null, rowsKey = '';
    const retired = new Set();
    function paint() {
      if (!scope.active) return;
      const busy = pending || report?.busy;
      const data = getSnapshot();
      const idlePaused = data?.paused && !(data?.counts.active > 0) && !data?.active_job;
      $('#database-refresh').disabled = Boolean(busy);
      for (const id of ['#database-backup', '#database-compact']) {
        $(id).disabled = Boolean(busy || !idlePaused);
        $(id).title = !idlePaused ? t('ui.database_pause_required') : '';
      }
      $('#database-summary').textContent = !report?.ready && !report?.busy ? t('ui.database_not_checked') : report?.busy
        ? t('ui.database_running') : report?.error_code ? t('ui.' + report.error_code) : t('ui.database_complete');
      $('#database-summary').classList.toggle('error', Boolean(report?.error_code));
      $('#database-summary').setAttribute('aria-busy', String(Boolean(busy)));
      $('#database-capacity').textContent = report?.ready
        ? t('ui.database_capacity', {size:fileSize(report.total_bytes), free:fileSize(report.reclaimable_bytes)}) : '';
      $('#database-backup-result').textContent = report?.backup_name
        ? t('ui.database_backup_location', {name:report.backup_name, size:fileSize(report.backup_bytes)}) : '';
      if (report?.result_code) $('#database-summary').textContent = t('ui.' + report.result_code);
      const key = JSON.stringify(report?.entries) + t('ui.databases');
      if (rowsKey === key) return;
      rowsKey = key;
      $('#database-entries').replaceChildren(...(report?.entries || []).map(entry => {
        const row = document.createElement('li');
        row.dataset.status = entry.status === 'error' ? 'error' : entry.checkpoint_busy || entry.schema_ok === false && entry.status === 'ok' ? 'warning' : 'ok';
        const heading = document.createElement('b'); heading.textContent = entry.filename;
        const detail = document.createElement('p');
        detail.textContent = entry.error_code ? t('ui.' + entry.error_code) : entry.status === 'missing' ? t('ui.database_missing') :
          t('ui.database_entry', {count:entry.records ?? '—', size:fileSize(entry.size_bytes), wal:fileSize(entry.wal_bytes), free:fileSize(entry.reclaimable_bytes)});
        if (entry.checkpoint_busy) detail.textContent += ' ' + t('ui.database_wal_busy');
        if (entry.schema_ok === false && entry.status === 'ok') detail.textContent += ' ' + t('ui.database_schema');
        row.append(heading, detail); return row;
      }));
    }
    function accept(next) {
      if (!scope.active || !next || retired.has(next.instance)) return;
      if (report?.instance === next.instance && next.revision < report.revision) return;
      if (report && report.instance !== next.instance) retired.add(report.instance);
      report = next;
      paint();
      if (timer !== null) scope.cancel(timer);
      timer = null;
      if (report.busy) timer = scope.defer(poll, 1000);
    }
    async function poll() {
      timer = null;
      try { accept(await api('/api/databases')); }
      catch (error) {
        if (!scope.active) return;
        $('#database-summary').textContent = uiMessage(error.message);
        if (report?.busy) timer = scope.defer(poll, 3000);
      }
    }
    async function request(action) {
      if (!scope.active || pending || report?.busy) return;
      pending = true; paint();
      try { accept(await api('/api/databases', {method:'POST', body:JSON.stringify({action, ...(action === 'compact' ? {confirmed:true} : {})})})); }
      catch (error) { if (scope.active) { toast(error.message, true); scope.defer(poll, 0); } }
      finally { pending = false; paint(); }
    }
    const close = () => { if (dialog.open) dialog.close(); };
    scope.listen($('#database-refresh'), 'click', () => request('refresh'));
    scope.listen($('#database-backup'), 'click', () => request('backup'));
    scope.listen($('#database-compact'), 'click', () => { if (!pending && !report?.busy && !dialog.open) dialog.showModal(); });
    for (const id of ['#database-confirm-close', '#database-confirm-cancel']) scope.listen($(id), 'click', close);
    scope.listen(dialog, 'cancel', event => { event.preventDefault(); close(); });
    scope.listen($('#database-confirm-submit'), 'click', () => { close(); return request('compact'); });
    scope.onDispose(close);
    return Object.freeze({init:scope.init, dispose:scope.dispose, render(data) {accept(data?.databases); paint();}});
  }
  window.SSDLDatabaseController = Object.freeze({create});
})();
