/* Dashboard composition, ordered snapshot publishing and refresh scheduling. */
const controllerDependencies = { document, browser: window, $, state, I18n, t, uiMessage, uiText,
  api, render, toast, refresh, getSnapshot: () => lastResponse, isOffline: () => connectionOffline };
const diagnosticsController = SSDLDiagnosticsController.create({ ...controllerDependencies, scheduleStatusRefresh, timeLabel, fileSize });
const jobsController = SSDLJobsController.create({ ...controllerDependencies, rows, pendingJobActions, jobPageSizes, jobPageSizeKey,
  renderJobs, renderWarnings, actionIcon, isImageFile, safe, requestJobView, connectX, openMediaSelection,
  invalidateView: () => { viewRefreshPending = true; } });
const settingsController = SSDLSettingsController.create({ ...controllerDependencies, renderOffline,
  loadEnvironment: (...args) => diagnosticsController.load(...args) });
const pixivLogin = SSDLPixivLogin.create({ api, refresh, state, $, t, uiText });
diagnosticsController.init(); jobsController.init(); settingsController.init(); pixivLogin.init();
let dashboardDisposed = false;
function disposeDashboard() {
  if (dashboardDisposed) return;
  dashboardDisposed = true;
  clearTimeout(refreshTimer);
  pixivLogin.dispose(); settingsController.dispose(); jobsController.dispose(); diagnosticsController.dispose();
}
window.addEventListener('pagehide', (event) => { if (!event.persisted) disposeDashboard(); });
function openSettings(...args) { return settingsController.open(...args); }

function toast(message, isError = false) {
  if (dashboardDisposed) return;
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
    if (error.uncertain && !dashboardDisposed) setTimeout(() => refresh(), 0);
    throw error;
  }
}

function jobViewKey() { return jobsController.viewKey(); }
function requestJobView() {
  resetJobsScroll = true;
  viewRefreshPending = true;
  refresh();
}

let latestStateInstance = null;
let latestStateSequence = -1;
const retiredStateInstances = new Set();
function render(data) {
  if (dashboardDisposed) return;
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
  settingsController.render(data);
  lastSuccessfulUpdate = Date.now();
  lastStatusError = null;
  connectionOffline = false;
  const oldAuthPhase = state.xAuth.phase;
  state.jobs = data.jobs || [];
  reconcileMediaSelection(state.jobs);
  state.paused = Boolean(data.paused);
  state.ready = Boolean(data.ready);
  state.xAuth = data.x_auth || {};
  state.pixivAuth = data.pixiv_auth || {};
  pixivLogin.render();
  state.fileActions = data.file_actions || 'desktop';
  state.cookieFile = data.x_cookie_file || '';
  state.downloadDir = data.download_dir || '';
  renderPlatformCooldown(data.safe_queue);
  renderProfileLogin();
  const authBusy = Boolean(state.xAuth.busy || connectingXRequest);
  const authConnected = Boolean(state.xAuth.connected);
  const authPending = authBusy || state.xAuth.phase === 'waiting';
  const fileLogin = Boolean(state.cookieFile);
  const authFailed = ['failed', 'expired'].includes(state.xAuth.phase);
  $('#x-session-card').dataset.state = authPending ? 'pending' : authConnected || fileLogin ? 'connected' :
    ['expired', 'failed'].includes(state.xAuth.phase) ? 'expired' : 'disconnected';
  $('#x-session-status').textContent = t(authPending ? 'ui.waiting_for_x' : authConnected ? 'ui.x_session_connected' :
    fileLogin ? 'ui.x_cookie_session' : 'ui.x_session_not_connected');
  $('#x-auth-description').classList.toggle('hidden', (authConnected || fileLogin) && !authPending);
  $('#x-login-label').textContent = t(authBusy ? 'ui.waiting_for_x' : authConnected ? 'ui.x_connected' : 'ui.connect_chrome');
  $('#x-login-open').disabled = authBusy;
  $('#x-login-open').classList.toggle('connected', authConnected);
  $('#x-login-open').title = uiMessage(state.xAuth.message || '連接 Chrome 中的 X 登入狀態');
  $('#x-connect').disabled = authBusy;
  $('#x-connect').textContent = t(authConnected ? 'ui.reconnect_chrome' : 'ui.connect_chrome_2');
  $('#x-login-browser').disabled = authBusy;
  $('#x-disconnect').disabled = !authPending && !authConnected && !state.cookieFile;
  $('#x-disconnect').textContent = t(authPending ? 'ui.cancel_connection' : 'ui.disconnect');
  $('#x-auth-message').textContent = authFailed ? uiMessage(state.xAuth.message || 'ui.x_connection_failed') : authConnected && !authPending ? t('ui.x_session_ready') : fileLogin && !authPending ?
    t('ui.x_cookie_session_ready') : uiMessage(state.xAuth.message || '尚未連接 X 登入');
  $('#x-auth-message').classList.toggle('connected', authConnected);
  $('#x-auth-message').classList.toggle('error', authFailed);
  uiText($('#x-storage-copy'), state.xAuth.storage_mode === 'memory' ? 'ui.x_memory_storage' : state.xAuth.storage_mode === 'aes-gcm' ? 'ui.x_key_storage' : 'ui.only_x_session_cookies_are_saved_encrypted');
  uiText($('#x-auth-description'), state.xAuth.host_browser ? 'ui.x_host_pairing' : 'ui.use_your_existing_x_session_in_chrome');
  if (state.xAuth.phase !== 'waiting') { $('#x-pairing-link').hidden = true; $('#x-pairing-link').removeAttribute('href'); }
  if (oldAuthPhase && oldAuthPhase !== state.xAuth.phase) {
    if (state.xAuth.phase === 'connected') toast(state.paused ? 'ui.x_connected_failed_jobs_have_been_queued' : 'ui.x_connected_failed_x_jobs_will_be');
    else if (state.xAuth.phase === 'failed') toast(state.xAuth.message || 'ui.x_connection_failed', true);
    else if (state.xAuth.phase === 'waiting') toast(state.xAuth.host_browser ? 'ui.x_pairing_ready' : 'ui.connection_page_opened_in_regular_chrome_load');
  }
  const counts = data.counts || {};
  const queued = counts.queued || 0;
  const active = counts.active || 0;
  const completed = counts.completed || 0;
  const failed = counts.failed || 0;
  const quota = data.rate_limit || {};
  $('#top-rate-used').textContent = quota.used ?? '—';
  $('#top-rate-limit').textContent = quota.limit ?? 40;
  $('#queue-policy-rate').textContent = `Rate ≤ ${quota.limit ?? 40} / h`;
  $('#top-rate').classList.toggle('is-limited', Boolean(quota.limited));
  const storage = data.storage || {};
  $('#top-storage-size').textContent = storage.ready ? storageSize(storage.total_bytes) : '—';
  $('#top-storage-count').textContent = storage.ready ? t('ui.count_files', { count: storage.file_count || 0 }) : t('ui.calculating');
  $('#top-storage').title = t('ui.open_download_folder') + (storage.ready ? ` · ${storageSize(storage.total_bytes)} · ${t('ui.count_media_files', { count: storage.file_count || 0 })}` : '') + (storage.partial ? t('ui.some_files_could_not_be_read_statistics') : '');
  $('#top-storage').setAttribute('aria-label', $('#top-storage').title);
  $('#top-storage').disabled = !data.storage;
  $('#count-queued').textContent = queued;
  $('#count-active').textContent = active;
  $('#count-completed').textContent = completed;
  $('#count-failed').textContent = failed;
  $('#pause-queue').classList.toggle('is-paused', state.paused);
  $('#pause-queue .pause-symbol').textContent = state.paused ? '▶' : 'Ⅱ';
  $('#pause-queue span:last-child').textContent = t(state.paused ? 'ui.resume_queue' : 'ui.pause_queue');
  $('#top-pause').classList.toggle('is-paused', state.paused);
  $('#top-pause').setAttribute('aria-pressed', String(state.paused));
  $('#top-pause .pause-symbol').textContent = state.paused ? '▶' : 'Ⅱ';
  $('#top-pause .pause-label').textContent = t(state.paused ? 'ui.resume' : 'ui.pause');
  const runningProfile = ['x_profile', 'pixiv_profile'].includes(data.active_job?.mode) || state.jobs.some((job) => job.status === 'active' && ['x_profile', 'pixiv_profile'].includes(job.mode));
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
  profileCounts.classList.toggle('hidden', !(['x_profile', 'pixiv_profile'].includes(activeJob?.mode) && Number.isFinite(activeJob.profile_scanned_files)));
  if (activeJob) {
    monitorTitle.textContent = activeJob.title ? jobTitle(activeJob) : t('ui.downloading_2');
    monitorCopy.textContent = `${activeJob.platform} · ${uiMessage(activeJob.status_text || '下載中')}`;
    progressBlock.classList.remove('hidden');
    const pct = activeJob.progress ?? 8;
    $('#monitor-progress-fill').style.width = `${pct}%`;
    $('#monitor-progress-text').textContent = activeJob.progress === null ? t('ui.downloading') : `${pct}%`;
    if (['x_profile', 'pixiv_profile'].includes(activeJob.mode)) {
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

  diagnosticsController.render(data);
  jobsController.render(data, { resetScroll: resetJobsScroll });
  resetJobsScroll = false;
  if (!refreshingState) scheduleStatusRefresh();
}

function scheduleStatusRefresh() {
  if (dashboardDisposed) return;
  clearTimeout(refreshTimer);
  const processing = diagnosticsController.report?.busy || lastResponse?.storage?.refreshing || lastResponse?.thumbnail_cache?.clearing ||
    state.xAuth.busy || state.xAuth.phase === 'waiting' || state.pixivAuth.pending || state.pixivAuth.busy ||
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
  if (dashboardDisposed || refreshingState) return;
  viewRefreshPending = false;
  clearTimeout(refreshTimer);
  refreshingState = true;
  $('#jobs-table-scroll').setAttribute('aria-busy', 'true');
  renderStatusRefreshButton();
  try { render(await api('/api/state')); if (manual) toast('ui.download_status_refreshed'); }
  catch (error) { renderOffline(error); if (manual) toast(error.message, true); }
  finally {
    refreshingState = false;
    if (dashboardDisposed) return;
    $('#jobs-table-scroll').setAttribute('aria-busy', 'false');
    renderStatusRefreshButton();
    if (viewRefreshPending) setTimeout(() => refresh(), 0);
    else scheduleStatusRefresh();
  }
}
$('#status-refresh').addEventListener('click', () => refresh(true));

function renderOffline(error = lastStatusError) {
  if (dashboardDisposed) return;
  lastStatusError = error;
  connectionOffline = true;
  settingsController.renderRateResetButtons();
  diagnosticsController.renderStorageMaintenance();
  const detail = uiMessage(error?.message || '請重新啟動 start.bat 後重整頁面');
  diagnosticsController.renderEngineStatus(t('ui.status_update_failed'), detail, true, true);
  $('#queue-banner').dataset.phase = 'offline';
  $('#queue-status-title').textContent = t('ui.status_update_failed');
  $('#queue-status-copy').textContent = detail + (lastSuccessfulUpdate
    ? ' ' + t('ui.last_successful_data_time_retained_status_updates', { time: timeLabel(lastSuccessfulUpdate / 1000) })
    : ' ' + t('ui.no_valid_status_has_been_received_yet'));
  if (!refreshingState) scheduleStatusRefresh();
}

function parsedUrls() {
  if (['x_profile', 'pixiv_profile'].includes(state.inputMode)) return $('#url-input').value.split(/[\s,，]+/).map((part) => part.trim()).filter(Boolean);
  return $('#url-input').value.split(/\s+|[,，](?=\s*https?:\/\/)/i).map((part) => part.trim()).filter(Boolean);
}

function updateUrlCount() { $('#url-count').textContent = t(['x_profile', 'pixiv_profile'].includes(state.inputMode) ? 'ui.count_accounts' : 'ui.count_urls', { count: parsedUrls().length }); }

function renderProfileLogin() {
  if (state.inputMode === 'pixiv_profile') {
    const connected = Boolean(state.pixivAuth.connected);
    $('#profile-login-status').textContent = t(connected ? 'ui.pixiv_connected' : 'ui.pixiv_connect_required');
    $('#profile-login-status').parentElement.classList.toggle('is-connected', connected);
    $('#profile-connect-x').textContent = t('ui.pixiv_sign_in');
    $('#profile-connect-x').disabled = Boolean(state.pixivAuth.busy);
    return;
  }
  const connected = Boolean(state.xAuth.connected || state.cookieFile);
  $('#profile-login-status').textContent = t(connected ? 'ui.x_session_connected' : 'ui.connect_an_x_session_to_continue');
  $('#profile-login-status').parentElement.classList.toggle('is-connected', connected);
  $('#profile-connect-x').textContent = t(connected ? 'ui.sync_x_session_again' : 'ui.connect_chrome');
  $('#profile-connect-x').disabled = Boolean(state.xAuth.busy || connectingXRequest);
}

const inputDrafts = { urls: '', x_profile: '', pixiv_profile: '' };
function renderVideoQuality() {
  const profile = ['x_profile', 'pixiv_profile'].includes(state.inputMode);
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
  const profile = ['x_profile', 'pixiv_profile'].includes(state.inputMode);
  const pixiv = state.inputMode === 'pixiv_profile';
  $('#download-input-description').textContent = t(pixiv ? 'ui.pixiv_paste_author' : profile ? 'ui.paste_an_x_profile_url_or_username' : 'ui.paste_video_image_or_post_urls');
  $('#download-input-label').textContent = t(pixiv ? 'ui.pixiv_author_urls' : profile ? 'ui.x_accounts_to_download_media_from' : 'ui.urls_to_download');
  $('#url-input').placeholder = t(pixiv ? 'ui.pixiv_placeholder' : profile ? 'ui.paste_x_accounts_one_per_line_https' : 'ui.paste_media_urls_one_per_line_https');
  $('#profile-options').classList.toggle('hidden', !profile);
  $('#profile-description').textContent = t(pixiv ? 'ui.pixiv_profile_description' : 'ui.scan_the_media_list_first_to_show');
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
$('#profile-connect-x').addEventListener('click', () => state.inputMode === 'pixiv_profile' ? openSettings('pixiv') : connectX());

$('#url-input').addEventListener('input', updateUrlCount);
$('#url-input').addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') $('#add-jobs').click();
});
$('#empty-add').addEventListener('click', () => { $('#url-input').focus(); window.scrollTo({ top: 0, behavior: 'smooth' }); });

$('#add-jobs').addEventListener('click', async () => {
  const urls = parsedUrls();
  const submittedMode = state.inputMode;
  const submittedText = $('#url-input').value;
  const submittedQuality = ['x_profile', 'pixiv_profile'].includes(submittedMode) ? 'best' : state.videoQuality;
  const message = $('#form-message');
  message.classList.remove('error');
  if (!urls.length) { uiText(message, submittedMode === 'pixiv_profile' ? 'ui.pixiv_paste_author' : submittedMode === 'x_profile' ? 'ui.paste_an_x_profile_url_or_username_2' : 'ui.paste_one_or_more_media_urls_first'); message.classList.add('error'); $('#url-input').focus(); return; }
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

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (settingsController.closeForEscape(event)) return;
  jobsController.closeError(); jobsController.closeWarnings(); jobsController.closeFilePicker(); closeMediaSelection();
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
  jobsController.onLanguageChanged();
});

renderJobs();
renderInputMode();
refresh();
