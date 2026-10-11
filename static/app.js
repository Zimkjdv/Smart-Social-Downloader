function toast(message, isError = false) {
  const item = document.createElement('div');
  item.className = `toast${isError ? ' error' : ''}`;
  uiText(item, message);
  $('#toast-region').append(item);
  setTimeout(() => item.remove(), 3400);
}

async function api(path, options = {}) {
  const view = jobViewKey();
  const query = Object.entries({ page: state.page, page_size: state.pageSize,
    status: state.filter, platform: state.platform, search: state.search.slice(0, 300) })
    .map(([key, value]) => encodeURIComponent(key) + '=' + encodeURIComponent(value)).join('&');
  try {
    const defaultView = state.page === 1 && state.pageSize === 20 && state.filter === 'all' && state.platform === 'all' && !state.search;
    const result = await SSDLApi.request(defaultView ? path : path + (path.includes('?') ? '&' : '?') + query, options);
    const payload = result.state || result;
    if (SSDLApi.isState(payload)) payload._requestView = view;
    return result;
  }
  catch (error) {
    // Resolve uncertain mutations with a read, never by repeating the write.
    if (error.uncertain) setTimeout(() => refresh(), 0);
    throw error;
  }
}

function jobViewKey() {
  return JSON.stringify([state.page, state.pageSize, state.filter, state.platform, state.search.slice(0, 300)]);
}
function requestJobView() {
  resetJobsScroll = true;
  viewRefreshPending = true;
  refresh();
}

let shownWarnings = null;
let shownError = null;
rows.addEventListener('click', async (event) => {
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
      const detail = await api(base + '/details');
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
    if (button.isConnected) button.disabled = false;
    renderJobs();
  }
});

let latestStateInstance = null;
let latestStateSequence = -1;
const retiredStateInstances = new Set();
function render(data) {
  if (!SSDLApi.isState(data)) throw new Error(t('ui.the_local_service_returned_an_unexpected_format'));
  if (data.jobs_page && data._requestView && data._requestView !== jobViewKey()) {
    viewRefreshPending = true;
    if (!refreshingState) setTimeout(() => refresh(), 0);
    return;
  }
  if (data.state_instance !== undefined) {
    if (retiredStateInstances.has(data.state_instance) ||
        data.state_instance === latestStateInstance && data.state_sequence < latestStateSequence) return;
    if (data.state_instance !== latestStateInstance) {
      if (latestStateInstance) retiredStateInstances.add(latestStateInstance);
      if (retiredStateInstances.size > 8) retiredStateInstances.delete(retiredStateInstances.values().next().value);
      latestStateInstance = data.state_instance;
    }
    latestStateSequence = data.state_sequence;
  }
  if (data.jobs_page) {
    if (state.page !== data.jobs_page.page) resetJobsScroll = true;
    state.page = data.jobs_page.page;
  }
  updateRecentSkippedJobs(data.jobs || []);
  data._requestView = jobViewKey();
  lastResponse = data;
  const appVersion = data.app_version || '—';
  $('#application-version').textContent = data.app_version ? `v${appVersion}` : '—';
  $('#application-version').title = `${t('ui.application_version')}: ${appVersion}`;
  $('#settings-application-version').textContent = appVersion;
  $('#browser-capture-status').textContent = t(data.browser_capture_available ? 'ui.dynamic_capture_ready' : 'ui.dynamic_capture_missing');
  lastSuccessfulUpdate = Date.now();
  lastStatusError = null;
  connectionOffline = false;
  const oldAuthPhase = state.xAuth.phase;
  state.jobs = data.jobs || [];
  reconcileMediaSelection(state.jobs);
  state.paused = Boolean(data.paused);
  state.ready = Boolean(data.ready);
  state.xAuth = data.x_auth || {};
  state.cookieFile = data.x_cookie_file || '';
  state.downloadDir = data.download_dir || '';
  renderPlatformCooldown(data.safe_queue);
  renderProfileLogin();
  const authBusy = Boolean(state.xAuth.busy || connectingXRequest);
  const authConnected = Boolean(state.xAuth.connected);
  const authPending = authBusy || state.xAuth.phase === 'waiting';
  $('#x-login-label').textContent = t(authBusy ? 'ui.waiting_for_x' : authConnected ? 'ui.x_connected' : 'ui.connect_chrome');
  $('#x-login-open').disabled = authBusy;
  $('#x-login-open').classList.toggle('connected', authConnected);
  $('#x-login-open').title = uiMessage(state.xAuth.message || '連接 Chrome 中的 X 登入狀態');
  $('#x-connect').disabled = authBusy;
  $('#x-connect').textContent = t(authConnected ? 'ui.reconnect_chrome' : 'ui.connect_chrome_2');
  $('#x-login-browser').disabled = authBusy;
  $('#x-disconnect').disabled = !authPending && !authConnected && !state.cookieFile;
  $('#x-disconnect').textContent = t(authPending ? 'ui.cancel_connection' : 'ui.disconnect');
  $('#x-auth-message').textContent = uiMessage(state.xAuth.message || '尚未連接 X 登入');
  $('#x-auth-message').classList.toggle('connected', authConnected);
  $('#x-auth-message').classList.toggle('error', state.xAuth.phase === 'failed');
  if (oldAuthPhase && oldAuthPhase !== state.xAuth.phase) {
    if (state.xAuth.phase === 'connected') toast(state.paused ? 'ui.x_connected_failed_jobs_have_been_queued' : 'ui.x_connected_failed_x_jobs_will_be');
    else if (state.xAuth.phase === 'failed') toast(state.xAuth.message || 'ui.x_connection_failed', true);
    else if (state.xAuth.phase === 'waiting') toast('ui.connection_page_opened_in_regular_chrome_load');
  }
  const counts = data.counts || {};
  const queued = counts.queued || 0;
  const active = counts.active || 0;
  const completed = counts.completed || 0;
  const failed = counts.failed || 0;
  $('#tab-selecting').textContent = counts.selecting || 0;
  const quota = data.rate_limit || {};
  $('#top-rate-used').textContent = quota.used ?? '—';
  $('#top-rate-limit').textContent = quota.limit ?? 40;
  $('#settings-rate-summary').textContent = t('ui.current_usage_used_limit_jobs', { used: quota.used ?? '—', limit: quota.limit ?? 40 });
  renderRateResetButtons();
  $('#queue-policy-rate').textContent = `Rate ≤ ${quota.limit ?? 40} / h`;
  $('#top-rate').classList.toggle('is-limited', Boolean(quota.limited));
  const storage = data.storage || {};
  $('#top-storage-size').textContent = storage.ready ? storageSize(storage.total_bytes) : '—';
  $('#top-storage-count').textContent = storage.ready ? t('ui.count_files', { count: storage.file_count || 0 }) : t('ui.calculating');
  $('#top-storage').title = t('ui.open_download_folder') + (storage.ready ? ` · ${storageSize(storage.total_bytes)} · ${t('ui.count_media_files', { count: storage.file_count || 0 })}` : '') + (storage.partial ? t('ui.some_files_could_not_be_read_statistics') : '');
  $('#top-storage').setAttribute('aria-label', $('#top-storage').title);
  $('#top-storage').disabled = !data.storage;
  renderStorageMaintenance(data);
  $('#count-queued').textContent = queued;
  $('#count-active').textContent = active;
  $('#count-completed').textContent = completed;
  $('#count-failed').textContent = failed;
  $('#tab-all').textContent = data.total_jobs ?? state.jobs.length;
  $('#tab-queued').textContent = queued;
  $('#tab-active').textContent = active;
  $('#tab-completed').textContent = completed;
  $('#tab-failed').textContent = failed;
  renderJobControlButtons();
  $('#pause-queue').classList.toggle('is-paused', state.paused);
  $('#pause-queue .pause-symbol').textContent = state.paused ? '▶' : 'Ⅱ';
  $('#pause-queue span:last-child').textContent = t(state.paused ? 'ui.resume_queue' : 'ui.pause_queue');
  $('#top-pause').classList.toggle('is-paused', state.paused);
  $('#top-pause').setAttribute('aria-pressed', String(state.paused));
  $('#top-pause .pause-symbol').textContent = state.paused ? '▶' : 'Ⅱ';
  $('#top-pause .pause-label').textContent = t(state.paused ? 'ui.resume' : 'ui.pause');
  const runningProfile = data.active_job?.mode === 'x_profile' || state.jobs.some((job) => job.status === 'active' && job.mode === 'x_profile');
  $('#top-pause').title = t(state.paused ? 'ui.resume_upcoming_jobs_using_safe_queue_rules' : runningProfile ? 'ui.pause_upcoming_posts_the_current_post_will' : 'ui.pause_upcoming_jobs_the_current_download_will');

  const policy = data.safe_queue || {};
  const phase = policy.phase || 'idle';
  const wait = policy.wait_seconds || 0;
  const cooling = policy.cooldown_seconds || 0;
  const bannerLabels = {
    selection: [t('ui.choose_media_to_download'), t('ui.this_page_contains_multiple_media_items_choose')],
    idle: [t('ui.queue_idle'), t('ui.waiting_for_new_jobs')],
    ready: [t('ui.ready_to_download'), t('ui.jobs_waiting_count', { count: queued })],
    waiting: [t('ui.waiting_between_jobs'), t('ui.next_job_starts_in_about_seconds_s', { seconds: wait, count: queued })],
    cooldown: [t('ui.rate_limit_cooldown'), t('ui.about_seconds_s_remaining_queued_jobs_will', { seconds: cooling })],
    quota: [t('ui.hourly_limit_reached_2'), t('ui.used_limit_jobs_started_next_slot_in', { used: quota.used, limit: quota.limit, seconds: quota.wait_seconds || 0 })],
    paused: [t('ui.queue_paused_2'), t('ui.queued_count', { count: queued }) + (cooling ? t('ui.cooldown_about_seconds_s_remaining', { seconds: cooling }) : t(quota.limited ? 'ui.hourly_limit_reached' : 'ui.press_resume_to_continue'))],
    active: [t('ui.processing'), cooling ? t('ui.current_job_is_waiting_for_cooldown_about', { seconds: cooling }) : t('ui.downloading_sequentially') + (state.paused ? t('ui.upcoming_jobs_paused') : '') + t('ui.queued_count_2', { count: queued })],
  };
  const banner = bannerLabels[phase] || bannerLabels.idle;
  $('#queue-banner').dataset.phase = phase;
  $('#queue-status-title').textContent = banner[0];
  $('#queue-status-copy').textContent = banner[1];

  const activeJob = data.active_job || state.jobs.find((job) => job.id === data.active_id) || state.jobs.find((job) => job.status === 'active');
  const monitorTitle = $('#monitor-title');
  const monitorCopy = $('#monitor-copy');
  const progressBlock = $('#monitor-progress');
  const profileCounts = $('#monitor-profile-counts');
  profileCounts.classList.toggle('hidden', !(activeJob?.mode === 'x_profile' && Number.isFinite(activeJob.profile_scanned_files)));
  if (activeJob) {
    monitorTitle.textContent = activeJob.title ? jobTitle(activeJob) : t('ui.downloading_2');
    monitorCopy.textContent = `${activeJob.platform} · ${uiMessage(activeJob.status_text || '下載中')}`;
    progressBlock.classList.remove('hidden');
    const pct = activeJob.progress ?? 8;
    $('#monitor-progress-fill').style.width = `${pct}%`;
    $('#monitor-progress-text').textContent = activeJob.progress === null ? t('ui.downloading') : `${pct}%`;
    if (activeJob.mode === 'x_profile') {
      monitorCopy.textContent = `${uiMessage(activeJob.status_text || '正在讀取 X 帳號媒體')} · ${profileSummary(activeJob)}`;
      const scanned = activeJob.profile_scan_complete && Number.isFinite(activeJob.profile_total_files);
      const total = scanned ? activeJob.profile_total_files : activeJob.profile_scanned_files;
      $('#profile-total-label').textContent = t(scanned ? 'ui.total_files' : 'ui.found_so_far');
      $('#profile-total-count').textContent = total ?? '—';
      $('#profile-download-count').textContent = scanned ? activeJob.profile_files_to_download ?? 0 : '—';
      $('#profile-existing-count').textContent = activeJob.profile_existing_files ?? '—';
      profileCounts.title = t(scanned ? 'ui.the_total_is_based_on_the_accessible' : 'ui.scanning_is_incomplete_showing_the_number_found');
      progressBlock.classList.toggle('hidden', !scanned || !total);
      if (scanned && total) {
        $('#monitor-progress-fill').style.width = `${activeJob.progress ?? 0}%`;
        $('#monitor-progress-text').textContent = `${Math.min(total, activeJob.profile_completed_files || 0)}/${total}`;
      }
    }
  } else if (queued) {
    monitorTitle.textContent = t(state.paused ? 'ui.queue_paused_2' : cooling ? 'ui.rate_limit_cooldown' : quota.limited ? 'ui.hourly_limit_reached_2' : wait ? 'ui.waiting_between_jobs' : 'ui.ready_to_download_2');
    monitorCopy.textContent = t('ui.jobs_waiting_count', { count: queued }) + (!state.paused && wait ? t('ui.starts_in_about_seconds_s', { seconds: wait }) : '');
    progressBlock.classList.add('hidden');
  } else if (completed || failed) {
    monitorTitle.textContent = t(cooling ? 'ui.rate_limit_cooldown' : state.paused ? 'ui.queue_paused_2' : quota.limited ? 'ui.hourly_limit_reached_2' : 'ui.queue_is_idle_waiting_for_jobs');
    monitorCopy.textContent = t('ui.completed_count', { count: completed }) + (failed ? t('ui.failed_count', { count: failed }) : '');
    progressBlock.classList.add('hidden');
  } else {
    monitorTitle.textContent = t(cooling ? 'ui.rate_limit_cooldown' : state.paused ? 'ui.queue_paused_2' : quota.limited ? 'ui.hourly_limit_reached_2' : 'ui.queue_is_ready');
    monitorCopy.textContent = cooling || state.paused || quota.limited ? banner[1] : t('ui.add_links_to_start_your_media_collection');
    progressBlock.classList.add('hidden');
  }

  renderEnvironment(data.environment);
  renderLocalHealth(data);
  const environmentIssue = lastEnvironment?.checked_at > 0 && lastEnvironment.status !== 'ok';
  const savingIssue = data.persistence && (!data.persistence.healthy || data.persistence.recovered);
  const workerIssue = data.worker && !data.worker.alive;
  renderEngineStatus(t(savingIssue ? 'ui.local_history_needs_attention' : workerIssue ? 'ui.download_worker_unavailable' : !state.ready ? 'ui.engines_need_repair' : environmentIssue ? 'ui.environment_needs_attention' : 'ui.engines_ready'),
    savingIssue ? uiMessage(data.persistence.error) : workerIssue ? t('ui.restart_the_service_or_export_diagnostics_for') : !state.ready || environmentIssue ? t('ui.open_environment_diagnostics_in_settings_for_repair') : t('ui.image_and_video_engines_ready_original_encoding'),
    savingIssue && !data.persistence.healthy || workerIssue || !state.ready, savingIssue || workerIssue || !state.ready || environmentIssue);
  const platformSelect = $('#platform-filter');
  const current = state.platform;
  const platforms = [...(data.platforms || new Set(state.jobs.map((job) => job.platform)))].sort((a, b) => a.localeCompare(b, I18n.locale));
  const platformMarkup = `<option value="all">${t('ui.all_platforms')}</option>` + platforms.map((name) => `<option value="${safe(name)}">${safe(name)}</option>`).join('');
  if (platformSelect.innerHTML !== platformMarkup) platformSelect.innerHTML = platformMarkup;
  platformSelect.value = platforms.includes(current) ? current : 'all';
  state.platform = platformSelect.value;
  if (state.platform !== current) viewRefreshPending = true;
  data._requestView = jobViewKey();
  renderJobs({ resetScroll: resetJobsScroll });
  resetJobsScroll = false;
  if (!refreshingState) scheduleStatusRefresh();
}

function scheduleStatusRefresh() {
  clearTimeout(refreshTimer);
  const processing = lastEnvironment?.busy || lastResponse?.storage?.refreshing || lastResponse?.thumbnail_cache?.clearing ||
    state.xAuth.busy || state.xAuth.phase === 'waiting' ||
    (lastResponse?.counts?.queued || lastResponse?.counts?.active);
  refreshTimer = setTimeout(refresh, !connectionOffline && processing ? 2000 : 30000);
}

function renderStatusRefreshButton() {
  const button = $('#status-refresh');
  button.disabled = refreshingState;
  button.setAttribute('aria-busy', String(refreshingState));
  button.setAttribute('aria-label', t(refreshingState ? 'ui.refreshing_status' : 'ui.refresh_download_status'));
  button.title = t(refreshingState ? 'ui.refreshing_status' : 'ui.refresh_download_status_automatically_every_30_seconds');
}

async function refresh(manual = false) {
  if (refreshingState) return;
  viewRefreshPending = false;
  clearTimeout(refreshTimer);
  refreshingState = true;
  $('#jobs-table-scroll').setAttribute('aria-busy', 'true');
  renderStatusRefreshButton();
  try { render(await api('/api/state')); if (manual) toast('ui.download_status_refreshed'); }
  catch (error) { renderOffline(error); if (manual) toast(error.message, true); }
  finally {
    refreshingState = false;
    $('#jobs-table-scroll').setAttribute('aria-busy', 'false');
    renderStatusRefreshButton();
    if (viewRefreshPending) setTimeout(() => refresh(), 0);
    else scheduleStatusRefresh();
  }
}
$('#status-refresh').addEventListener('click', () => refresh(true));

function renderOffline(error = lastStatusError) {
  lastStatusError = error;
  connectionOffline = true;
  renderRateResetButtons();
  renderStorageMaintenance();
  const detail = uiMessage(error?.message || '請重新啟動 start.bat 後重整頁面');
  renderEngineStatus(t('ui.status_update_failed'), detail, true, true);
  $('#queue-banner').dataset.phase = 'offline';
  $('#queue-status-title').textContent = t('ui.status_update_failed');
  $('#queue-status-copy').textContent = detail + (lastSuccessfulUpdate
    ? ' ' + t('ui.last_successful_data_time_retained_status_updates', { time: timeLabel(lastSuccessfulUpdate / 1000) })
    : ' ' + t('ui.no_valid_status_has_been_received_yet'));
  if (!refreshingState) scheduleStatusRefresh();
}

function renderJobControlButtons() {
  $('#retry-failed').disabled = busyControls.has('retry-failed') || !(lastResponse?.counts?.failed);
  $('#clear-done').disabled = busyControls.has('clear-done') || !(lastResponse?.counts?.completed);
  $('#clear-all').disabled = busyControls.has('clear-all') || !(lastResponse?.total_jobs ?? state.jobs.length) || !lastResponse?.safe_queue?.enabled;
}

function renderStorageMaintenance(data = lastResponse) {
  const storage = data?.storage || {};
  const cache = data?.thumbnail_cache || {};
  $('#storage-scan-summary').textContent = t(storage.refreshing ? 'ui.scanning_the_download_folder_in_the_background' : 'ui.last_full_scan_time', { time: timeLabel(storage.checked_at) }) +
    (storage.partial ? t('ui.some_files_could_not_be_read_statistics') : '');
  $('#thumbnail-cache-summary').textContent = cache.ready
    ? t('ui.thumbnail_cache_size_limit_count_previews', { size: fileSize(cache.total_bytes), limit: fileSize(cache.max_bytes), count: cache.file_count })
    : t('ui.loading_thumbnail_cache_status');
  if (cache.partial) $('#thumbnail-cache-summary').textContent += t('ui.some_cached_previews_could_not_be_removed');
  $('#storage-rescan').disabled = connectionOffline || busyControls.has('storage-rescan') || Boolean(storage.refreshing);
  $('#thumbnail-cache-clear').disabled = connectionOffline || busyControls.has('thumbnail-cache-clear') || Boolean(cache.clearing);
}
for (const [id, path, copy] of [
  ['storage-rescan', '/api/storage/rescan', '已開始背景容量掃描'],
  ['thumbnail-cache-clear', '/api/thumbnails/clear', '已排入縮圖快取清理'],
]) {
  $('#' + id).addEventListener('click', async () => {
    if (busyControls.has(id)) return;
    busyControls.add(id);
    renderStorageMaintenance();
    try { render(await api(path, { method: 'POST', body: '{}' })); toast(copy); }
    catch (error) { toast(error.message, true); }
    finally { busyControls.delete(id); renderStorageMaintenance(); }
  });
}

function renderEnvironment(report = lastEnvironment) {
  if (!report) return;
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
  if (environmentRequestBusy || (recheck && lastEnvironment?.busy)) return;
  environmentRequestBusy = true;
  $('#environment-refresh').disabled = true;
  try {
    renderEnvironment(await api(recheck ? '/api/environment/refresh' : '/api/environment',
      recheck ? { method: 'POST', body: '{}' } : {}));
    scheduleStatusRefresh();
  } catch (error) { uiText($('#environment-summary'), error.message); }
  finally {
    environmentRequestBusy = false;
    $('#environment-refresh').disabled = Boolean(lastEnvironment?.busy);
    $('#environment-refresh').setAttribute('aria-busy', String(Boolean(lastEnvironment?.busy)));
  }
}
$('#environment-refresh').addEventListener('click', () => loadEnvironment(true));

function renderLocalHealth(data) {
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
$('#state-save').addEventListener('click', async () => {
  busyControls.add('state-save');
  $('#state-save').disabled = true;
  try { const result = await api('/api/state/save', { method: 'POST', body: '{}' }); render(result); }
  catch (error) { toast(error.message, true); }
  finally { busyControls.delete('state-save'); if (lastResponse) renderLocalHealth(lastResponse); }
});
$('#diagnostics-export').addEventListener('click', async () => {
  const button = $('#diagnostics-export');
  button.disabled = true;
  try {
    const report = await api('/api/diagnostics');
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ssdl-diagnostics.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});

function renderEngineStatus(label, detail, offline, visible = offline) {
  const engine = $('#engine-status');
  engine.classList.toggle('hidden', !visible);
  engine.classList.toggle('offline', offline);
  engine.title = detail;
  // Avoid repeated live-region announcements while polling unchanged state.
  if ($('#engine-title').textContent !== label) $('#engine-title').textContent = label;
  if ($('#engine-subtitle').textContent !== detail) $('#engine-subtitle').textContent = detail;
}

function parsedUrls() {
  if (state.inputMode === 'x_profile') return $('#url-input').value.split(/[\s,，]+/).map((part) => part.trim()).filter(Boolean);
  return $('#url-input').value.split(/\s+|[,，](?=\s*https?:\/\/)/i).map((part) => part.trim()).filter(Boolean);
}

function updateUrlCount() { $('#url-count').textContent = t(state.inputMode === 'x_profile' ? 'ui.count_accounts' : 'ui.count_urls', { count: parsedUrls().length }); }

function renderProfileLogin() {
  const connected = Boolean(state.xAuth.connected || state.cookieFile);
  $('#profile-login-status').textContent = t(connected ? 'ui.x_session_connected' : 'ui.connect_an_x_session_to_continue');
  $('#profile-login-status').parentElement.classList.toggle('is-connected', connected);
  $('#profile-connect-x').textContent = t(connected ? 'ui.sync_x_session_again' : 'ui.connect_chrome');
  $('#profile-connect-x').disabled = Boolean(state.xAuth.busy || connectingXRequest);
}

const inputDrafts = { urls: '', x_profile: '' };
function renderVideoQuality() {
  const profile = state.inputMode === 'x_profile';
  $('#video-quality-controls').classList.toggle('hidden', profile);
  $('#profile-quality-note').classList.toggle('hidden', !profile);
  $('#video-quality').disabled = profile;
  $('#video-quality').value = state.videoQuality;
  uiText($('#video-quality-hint'), state.videoQuality === 'best' ? 'ui.automatically_choose_the_best_available_quality_images' : 'ui.choose_the_best_version_at_or_below');
}
$('#video-quality').addEventListener('change', () => {
  state.videoQuality = $('#video-quality').value;
  renderVideoQuality();
});
function renderInputMode() {
  const profile = state.inputMode === 'x_profile';
  $('#download-input-description').textContent = t(profile ? 'ui.paste_an_x_profile_url_or_username' : 'ui.paste_video_image_or_post_urls');
  $('#download-input-label').textContent = t(profile ? 'ui.x_accounts_to_download_media_from' : 'ui.urls_to_download');
  $('#url-input').placeholder = t(profile ? 'ui.paste_x_accounts_one_per_line_https' : 'ui.paste_media_urls_one_per_line_https');
  $('#profile-options').classList.toggle('hidden', !profile);
  $('#supported-platforms').classList.toggle('hidden', profile);
  renderVideoQuality();
  document.querySelectorAll('[data-download-mode]').forEach((button) => {
    const selected = button.dataset.downloadMode === state.inputMode;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  updateUrlCount();
  renderProfileLogin();
}
document.querySelectorAll('[data-download-mode]').forEach((button) => button.addEventListener('click', () => {
  inputDrafts[state.inputMode] = $('#url-input').value;
  state.inputMode = button.dataset.downloadMode;
  $('#url-input').value = inputDrafts[state.inputMode];
  uiText($('#form-message'), '');
  renderInputMode();
  $('#url-input').focus();
}));
$('#profile-connect-x').addEventListener('click', () => connectX());

$('#url-input').addEventListener('input', updateUrlCount);
$('#url-input').addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') $('#add-jobs').click();
});
$('#empty-add').addEventListener('click', () => { $('#url-input').focus(); window.scrollTo({ top: 0, behavior: 'smooth' }); });

$('#add-jobs').addEventListener('click', async () => {
  const urls = parsedUrls();
  const submittedMode = state.inputMode;
  const submittedText = $('#url-input').value;
  const submittedQuality = submittedMode === 'x_profile' ? 'best' : state.videoQuality;
  const message = $('#form-message');
  message.classList.remove('error');
  if (!urls.length) { uiText(message, submittedMode === 'x_profile' ? 'ui.paste_an_x_profile_url_or_username_2' : 'ui.paste_one_or_more_media_urls_first'); message.classList.add('error'); $('#url-input').focus(); return; }
  const button = $('#add-jobs');
  button.disabled = true;
  button.querySelector('span').textContent = t('ui.adding');
  try {
    const result = await api('/api/jobs', { method: 'POST', body: JSON.stringify({ urls, mode: submittedMode, video_quality: submittedQuality }) });
    const rejected = result.rejected || [];
    const added = result.added || [];
    const reused = result.reused || [];
    const pending = result.already_pending || [];
    const acceptedCount = added.length + reused.length + pending.length;
    if (acceptedCount && !rejected.length) {
      inputDrafts[submittedMode] = '';
      if (state.inputMode === submittedMode && $('#url-input').value === submittedText) $('#url-input').value = '';
    }
    updateUrlCount();
    const summary = rejected.length ? `新增 ${added.length} 個 · 沿用 ${reused.length} 個 · 已在佇列 ${pending.length} 個；${rejected.length} 個網址未加入。` :
      !reused.length && !pending.length ? `已加入 ${added.length} 個下載項目。` :
      !added.length && !pending.length ? `已沿用 ${reused.length} 個項目，檢查原位置檔案。` :
      !added.length && !reused.length ? `${pending.length} 個項目已在佇列中，未重複加入。` :
      `新增 ${added.length} 個 · 沿用 ${reused.length} 個 · 已在佇列 ${pending.length} 個。`;
    uiText(message, summary);
    if (rejected.length && !acceptedCount) message.classList.add('error');
    render(result.state);
    if (rejected.length) toast(rejected[0].error, true);
    else toast(summary);
  } catch (error) { uiText(message, error.message); message.classList.add('error'); }
  finally { button.disabled = false; button.querySelector('span').textContent = t('ui.add_to_download_queue'); }
});

document.querySelectorAll('.filter-tab').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('.filter-tab').forEach((item) => {
    const selected = item === tab;
    item.classList.toggle('selected', selected);
    item.setAttribute('aria-pressed', String(selected));
  });
  state.filter = tab.dataset.filter;
  state.page = 1;
  requestJobView();
}));
$('#platform-filter').addEventListener('change', (event) => { state.platform = event.target.value; state.page = 1; requestJobView(); });
$('#search-input').addEventListener('input', (event) => {
  state.search = event.target.value.slice(0, 300); state.page = 1;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(requestJobView, 250);
});
$('#jobs-page-size').addEventListener('change', (event) => {
  const pageSize = Number(event.target.value);
  if (!jobPageSizes.includes(pageSize)) return;
  state.pageSize = pageSize;
  state.page = 1;
  try { localStorage.setItem(jobPageSizeKey, String(pageSize)); } catch { /* Retain the selection for this page. */ }
  requestJobView();
});
function changeJobPage(page) {
  state.page = page;
  requestJobView();
}
$('#jobs-page-prev').addEventListener('click', () => changeJobPage(state.page - 1));
$('#jobs-page-next').addEventListener('click', () => changeJobPage(state.page + 1));
$('#jobs-page-numbers').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-page]');
  if (button && !button.disabled) changeJobPage(Number(button.dataset.page));
});

let pauseBusy = false;
async function togglePause() {
  if (pauseBusy) return;
  pauseBusy = true;
  const buttons = [$('#pause-queue'), $('#top-pause')];
  buttons.forEach((button) => { button.disabled = true; });
  try { render(await api('/api/pause', { method: 'POST', body: JSON.stringify({ paused: !state.paused }) })); }
  catch (error) { toast(error.message, true); }
  finally { pauseBusy = false; buttons.forEach((button) => { button.disabled = false; }); }
}
$('#pause-queue').addEventListener('click', togglePause);
$('#top-pause').addEventListener('click', togglePause);
$('#top-storage').addEventListener('click', async () => {
  const button = $('#top-storage');
  button.disabled = true;
  try { await api('/api/downloads/open', { method: 'POST', body: '{}' }); }
  catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});
$('#clear-done').addEventListener('click', async () => {
  if (busyControls.has('clear-done')) return;
  busyControls.add('clear-done');
  renderJobControlButtons();
  try { const result = await api('/api/jobs/clear-done', { method: 'POST', body: '{}' }); render(result.state); toast(result.removed ? `已清除 ${result.removed} 個項目` : 'ui.no_completed_jobs_to_clear'); }
  catch (error) { toast(error.message, true); }
  finally { busyControls.delete('clear-done'); renderJobControlButtons(); }
});
$('#clear-all').addEventListener('click', async () => {
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
$('#retry-failed').addEventListener('click', async () => {
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
const closeError = () => errorModal.classList.add('hidden');
$('#error-close').addEventListener('click', closeError);
$('#error-ok').addEventListener('click', closeError);
errorModal.addEventListener('click', (event) => { if (event.target === errorModal) closeError(); });

const warningsModal = $('#warnings-modal');
function closeWarnings() {
  if (warningsModal.classList.contains('hidden')) return;
  warningsModal.classList.add('hidden');
  const trigger = [...rows.querySelectorAll('[data-warnings]')].find((button) => button.dataset.warnings === warningsModal.dataset.jobId);
  trigger?.focus();
}
$('#warnings-close').addEventListener('click', closeWarnings);
$('#warnings-ok').addEventListener('click', closeWarnings);
warningsModal.addEventListener('click', (event) => { if (event.target === warningsModal) closeWarnings(); });
warningsModal.addEventListener('keydown', (event) => {
  if (event.key !== 'Tab') return;
  const first = $('#warnings-close');
  const last = $('#warnings-ok');
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});

const modal = $('#settings-modal');
const filePicker = $('#file-picker-modal');
let openingFile = false;
function closeFilePicker() {
  filePickerEpoch++;
  if (filePicker.classList.contains('hidden')) return;
  filePicker.classList.add('hidden');
  const key = filePicker.dataset.mode === 'open-folder' ? 'openFolder' : 'openMedia';
  const trigger = [...rows.querySelectorAll('[data-open-media], [data-open-folder]')].find((button) => button.dataset[key] === filePicker.dataset.jobId);
  trigger?.focus();
}
async function runFileAction(job, mode, index) {
  if (openingFile) return;
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
  if (openingFile || !count) return;
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
$('#file-picker-close').addEventListener('click', closeFilePicker);
$('#file-picker-cancel').addEventListener('click', closeFilePicker);
filePicker.addEventListener('click', (event) => { if (event.target === filePicker) closeFilePicker(); });
filePicker.addEventListener('keydown', (event) => {
  if (event.key !== 'Tab') return;
  const buttons = [...filePicker.querySelectorAll('button:not(:disabled)')];
  const first = buttons[0];
  const last = buttons[buttons.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
});
let settingsTab = 'general';
let settingsReturnFocus = null;
function selectSettingsTab(name, focus = false) {
  const tabs = [...modal.querySelectorAll('[data-settings-tab]')];
  const target = tabs.find((tab) => tab.dataset.settingsTab === name);
  if (!target) return;
  const changed = settingsTab !== name;
  settingsTab = name;
  tabs.forEach((tab) => {
    const selected = tab === target;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
  });
  if (changed) modal.querySelector('.settings-content').scrollTop = 0;
  if (focus) target.focus();
  if (name === 'diagnostics') loadEnvironment();
}
modal.querySelectorAll('[data-settings-tab]').forEach((tab) => {
  tab.addEventListener('click', () => selectSettingsTab(tab.dataset.settingsTab));
  tab.addEventListener('keydown', (event) => {
    const tabs = [...modal.querySelectorAll('[data-settings-tab]')];
    const index = tabs.indexOf(tab);
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    selectSettingsTab(tabs[next].dataset.settingsTab, true);
  });
});
modal.addEventListener('keydown', (event) => {
  if (event.key !== 'Tab' || modal.classList.contains('hidden') || rateConfirmation.open) return;
  const focusable = [...modal.querySelectorAll('button:not([disabled]), input:not([disabled]), a[href], summary, [tabindex="0"]')]
    .filter((element) => element.getClientRects().length > 0);
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
});
function closeSettings() {
  if (modal.classList.contains('hidden')) return;
  modal.classList.add('hidden');
  if (settingsReturnFocus?.isConnected && !settingsReturnFocus.disabled) settingsReturnFocus.focus();
  settingsReturnFocus = null;
}
async function openSettings(requestedTab) {
  if (settingsOpening) return false;
  settingsOpening = true;
  const wasOpen = !modal.classList.contains('hidden');
  if (!wasOpen) settingsReturnFocus = document.activeElement;
  $('#settings-open').disabled = true;
  let loaded = false;
  try {
    const data = await api('/api/state');
    render(data);
    loaded = true;
    uiText($('#settings-message'), '');
    $('#settings-message').classList.remove('error');
  } catch (error) {
    uiText($('#settings-message'), error.message);
    $('#settings-message').classList.add('error');
    renderOffline(error);
  } finally {
    if (!wasOpen && lastResponse) {
      $('#download-dir').value = lastResponse.download_dir;
      $('#x-cookie-file').value = lastResponse.x_cookie_file;
      $('#hourly-job-limit').value = lastResponse.hourly_job_limit ?? lastResponse.rate_limit.limit;
      $('#no-progress-timeout').value = lastResponse.no_progress_timeout ?? 300;
      $('#cooldown-mode').value = lastResponse.safe_queue.cooldown_mode || 'platform';
      $('#dynamic-capture').checked = Boolean(lastResponse.dynamic_capture);
    }
    modal.classList.remove('hidden');
    selectSettingsTab(typeof requestedTab === 'string' ? requestedTab : wasOpen ? settingsTab : 'general');
    if (!wasOpen) $('#settings-tab-' + settingsTab).focus();
    settingsOpening = false;
    $('#settings-open').disabled = false;
  }
  return loaded;
}
$('#settings-open').addEventListener('click', openSettings);
const rateConfirmation = $('#rate-confirm-dialog');
let rateResetTrigger = null;
function openRateResetConfirmation(event) {
  if (resettingRate || connectionOffline || !lastResponse || rateConfirmation.open) return;
  rateResetTrigger = event.currentTarget;
  uiText($('#rate-confirm-message'), '');
  $('#rate-confirm-message').classList.remove('error');
  renderRateResetButtons();
  rateConfirmation.showModal();
}
function closeRateResetConfirmation() {
  if (resettingRate || !rateConfirmation.open) return;
  rateConfirmation.close();
  rateResetTrigger?.focus();
  rateResetTrigger = null;
}
$('#rate-confirm-close').addEventListener('click', closeRateResetConfirmation);
$('#rate-confirm-cancel').addEventListener('click', closeRateResetConfirmation);
rateConfirmation.addEventListener('cancel', (event) => {
  event.preventDefault();
  closeRateResetConfirmation();
});
function renderRateResetButtons() {
  const button = $('#rate-reset');
  const topButton = $('#top-rate');
  const quota = lastResponse?.rate_limit || {};
  const unavailable = resettingRate || connectionOffline || !lastResponse;
  button.disabled = unavailable;
  topButton.disabled = unavailable;
  button.setAttribute('aria-busy', String(resettingRate));
  topButton.setAttribute('aria-busy', String(resettingRate));
  button.querySelector('span').textContent = t(resettingRate ? 'ui.resetting' : 'ui.reset_rate');
  $('#rate-confirm-submit').disabled = unavailable;
  $('#rate-confirm-submit').textContent = t(resettingRate ? 'ui.resetting' : 'ui.confirm_reset');
  $('#rate-confirm-submit').setAttribute('aria-busy', String(resettingRate));
  $('#rate-confirm-close').disabled = resettingRate;
  $('#rate-confirm-cancel').disabled = resettingRate;
  $('#rate-confirm-summary').textContent = t('ui.current_usage_used_limit_after_confirmation_the', { used: quota.used ?? '—', limit: quota.limit ?? 40 });
  $('#top-rate-label').textContent = t(resettingRate ? 'ui.resetting' : 'Rate');
  topButton.setAttribute('aria-label', resettingRate ? t('ui.resetting_rate') : t('ui.reset_rate_current_usage_used_limit_jobs', { used: quota.used ?? '—', limit: quota.limit ?? 40 }));
  topButton.title = connectionOffline ? t('ui.service_offline') : resettingRate ? t('ui.resetting_rate') :
    t('ui.click_to_confirm_a_rate_reset') + '\n' + t('ui.used_jobs_started_in_the_last_60', { used: quota.used ?? '—', limit: quota.limit ?? 40 }) +
    (quota.limited ? t('ui.next_slot_in_about_minutes_minutes', { minutes: Math.ceil((quota.wait_seconds || 0) / 60) }) : '');
}
async function resetRate() {
  if (!rateConfirmation.open || resettingRate || connectionOffline || !lastResponse) return;
  const message = $('#settings-message');
  const confirmMessage = $('#rate-confirm-message');
  let didReset = false;
  resettingRate = true;
  renderRateResetButtons();
  uiText(message, 'ui.resetting_rate');
  message.classList.remove('error');
  uiText(confirmMessage, 'ui.resetting_rate');
  confirmMessage.classList.remove('error');
  try {
    const result = await api('/api/rate/reset', { method: 'POST', body: '{}' });
    render(result.state);
    didReset = true;
    uiText(message, 'ui.rate_reset_new_job_starts_will_be');
    toast('ui.rate_reset_new_job_starts_will_be');
  } catch (error) {
    uiText(message, error.message);
    message.classList.add('error');
    uiText(confirmMessage, error.message);
    confirmMessage.classList.add('error');
    toast(error.message, true);
  } finally {
    resettingRate = false;
    renderRateResetButtons();
    if (didReset) closeRateResetConfirmation();
  }
}
$('#rate-reset').addEventListener('click', openRateResetConfirmation);
$('#top-rate').addEventListener('click', openRateResetConfirmation);
$('#rate-confirm-submit').addEventListener('click', resetRate);
$('#settings-close').addEventListener('click', closeSettings);
$('#settings-cancel').addEventListener('click', closeSettings);
modal.addEventListener('click', (event) => { if (event.target === modal) closeSettings(); });
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (rateConfirmation.open) { event.preventDefault(); closeRateResetConfirmation(); return; }
  closeSettings(); closeError(); closeWarnings(); closeFilePicker(); closeMediaSelection();
});
$('#settings-save').addEventListener('click', async () => {
  const button = $('#settings-save');
  const message = $('#settings-message');
  if ($('#hourly-job-limit').validity?.valid === false || $('#no-progress-timeout').validity?.valid === false) selectSettingsTab('general');
  if (!$('#hourly-job-limit').reportValidity() || !$('#no-progress-timeout').reportValidity()) return;
  button.disabled = true;
  uiText(message, 'ui.saving');
  message.classList.remove('error');
  try { const result = await api('/api/settings', { method: 'POST', body: JSON.stringify({ download_dir: $('#download-dir').value, x_cookie_file: $('#x-cookie-file').value, hourly_job_limit: Number($('#hourly-job-limit').value), no_progress_timeout: Number($('#no-progress-timeout').value), cooldown_mode: $('#cooldown-mode').value, dynamic_capture: $('#dynamic-capture').checked }) }); render(result); uiText(message, 'ui.settings_saved_the_hourly_limit_is_now'); toast('ui.settings_saved'); setTimeout(closeSettings, 550); }
  catch (error) { uiText(message, error.message); message.classList.add('error'); }
  finally { button.disabled = false; }
});

document.addEventListener('ssdl-language-changed', () => {
  const wasOffline = connectionOffline;
  const savedError = lastStatusError;
  const savedUpdate = lastSuccessfulUpdate;
  if (lastResponse) render(lastResponse);
  else renderJobs();
  lastSuccessfulUpdate = savedUpdate;
  if (wasOffline) renderOffline(savedError);
  renderStatusRefreshButton();
  renderInputMode();
  $('#add-jobs span').textContent = t($('#add-jobs').disabled ? 'ui.adding' : 'ui.add_to_download_queue');
  if (!errorModal.classList.contains('hidden')) {
    const job = shownError;
    if (job) $('#error-summary').textContent = uiMessage(job.error);
  }
  if (!warningsModal.classList.contains('hidden')) {
    const job = shownWarnings;
    if (job?.warnings?.length) renderWarnings(job);
  }
  if (!filePicker.classList.contains('hidden')) renderFilePickerCopy(filePicker.dataset.mode);
});

renderJobs();
renderInputMode();
refresh();
