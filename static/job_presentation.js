/* Job formatting and keyed table rendering; actions live in jobs_controller.js. */
const safe = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const statusNames = { queued: '等待中', active: '下載中', completed: '已完成', failed: '失敗', selecting: '待選擇媒體' };
function pixivAuthorLabel(job) {
  const account = String(job.account || '');
  if (!/^[1-9][0-9]{0,19}$/.test(account)) return account;
  const suffix = `(${account})`;
  const prefix = 'Pixiv · ';
  if (typeof job.title === 'string' && job.title.startsWith(prefix) && job.title.endsWith(suffix)) {
    return job.title.slice(prefix.length);
  }
  // Older history already contains the named folder, even before its next sync.
  for (const filename of job.files || []) {
    const parts = String(filename).split(/[\\/]/);
    if (parts.length === 3 && parts[0] === 'pixiv' && parts[1].endsWith(suffix) && parts[1].length > suffix.length) {
      return parts[1];
    }
  }
  return account;
}
const jobTitle = (job) => job.mode === 'pixiv_profile' ? t('ui.pixiv_author_title', { account: pixivAuthorLabel(job) }) : job.mode === 'x_profile' ? t('ui.x_account_media_account', { account: job.account || '' }) : !job.title || job.title === '等待下載' || job.title === '正在下載圖片來源檔' ? t(job.title || 'ui.waiting_to_download') : job.title;

function wasSkipped(job) {
  return job.status === 'completed' && !['x_profile', 'pixiv_profile'].includes(job.mode) &&
    (job.skipped_download || job.status_text === '已略過，檔案已存在');
}

function jobRun(job) {
  return `${job.attempts || 0}:${job.started_at || 0}:${job.finished_at || 0}`;
}

function updateRecentSkippedJobs(jobs) {
  const previous = new Map(state.jobs.map((job) => [job.id, job]));
  const currentIds = new Set(jobs.map((job) => job.id));
  for (const id of recentSkippedJobs.keys()) {
    if (!currentIds.has(id) && recentSkippedJobs.size > 200) recentSkippedJobs.delete(id);
  }
  for (const job of jobs) {
    if (!wasSkipped(job)) {
      recentSkippedJobs.delete(job.id);
      continue;
    }
    const before = previous.get(job.id);
    if (lastResponse && before && (before.status !== 'completed' || jobRun(before) !== jobRun(job))) {
      recentSkippedJobs.set(job.id, jobRun(job));
    }
  }
}

function profileSummary(job) {
  if (job.profile_scan_complete && Number.isFinite(job.profile_total_files)) {
    const total = job.profile_total_files;
    const done = Math.min(total, job.profile_completed_files || 0);
    return t('ui.files_total_files_done_files_completed_remaining', {
      files: total, done, remaining: Math.max(0, total - done),
    });
  }
  if (Number.isFinite(job.profile_scanned_files)) {
    if (job.status === 'queued') return t('ui.waiting_to_scan_the_media_list');
    return t('ui.files_files_found_so_far_total_available', { files: job.profile_scanned_files });
  }
  return t('ui.posts_posts_processed_files_files_skipped_downloaded', {
    posts: job.profile_posts || 0, files: job.file_count ?? job.files?.length ?? 0, skipped: job.profile_skipped || 0,
  });
}

function storageSize(bytes) {
  const size = Math.max(0, Number(bytes) || 0);
  return size >= 1024 ** 3 ? `${(size / 1024 ** 3).toFixed(1)} GB` : `${(size / 1024 ** 2).toFixed(1)} MB`;
}

function fileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${unit ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

function elapsedLabel(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 1) return t('ui.seconds_s', { seconds: seconds.toFixed(1) });
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const remainder = String(whole % 60).padStart(2, '0');
  return minutes >= 60 ? `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}:${remainder}` : `${minutes}:${remainder}`;
}

const statusIcons = {
  queued: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  active: '<circle cx="12" cy="12" r="9" opacity=".25"/><path d="M12 3a9 9 0 0 1 9 9"/>',
  completed: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  failed: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/>',
};
function statusIcon(status) {
  const name = statusIcons[status] ? status : 'queued';
  return `<svg class="status-icon status-icon-${name}" viewBox="0 0 24 24" aria-hidden="true">${statusIcons[name]}</svg>`;
}

const actionIcons = {
  play: '<path d="m8 5 11 7-11 7V5Z"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m21 15-5-5L6 21"/>',
  folder: '<path d="M3 7V5h7l2 3h9v11H3V7Z"/><path d="M3 11h18"/>',
  retry: '<path d="M3 11a9 9 0 1 1 2.6 7M3 4v7h7"/>',
  remove: '<path d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  warning: '<path d="M10.3 4.8 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.8a2 2 0 0 0-3.4 0Z"/><path d="M12 9v5m0 3h.01"/>',
};
function actionIcon(name) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${actionIcons[name]}</svg>`;
}
function isImageFile(filename) {
  return /\.(?:jpe?g|png|webp|gif|avif|bmp|tiff?|heic|heif|jxl|svg|ico)$/i.test(filename || '');
}

function shortFileName(filename) {
  const value = String(filename || '');
  const leaf = value.split(/[\\/]/).pop();
  return /[\\/]/.test(value) ? `…${value.includes('\\') ? '\\' : '/'}${leaf}` : value;
}

function fullFilePath(job, filename) {
  const value = String(filename || '');
  if (!value || /^(?:[a-z]:[\\/]|[\\/])/i.test(value)) return value;
  const directory = job.output_dir || state.downloadDir || '';
  return directory ? `${directory.replace(/[\\/]+$/, '')}${directory.includes('\\') ? '\\' : '/'}${value}` : value;
}

function mediaPreview(job, files, viewTitle) {
  const count = job.file_count ?? files.length;
  // URLs are issued only for generated local JPEGs, never for remote source images.
  const thumbnail = typeof job.thumbnail_url === 'string' && /^\/api\/jobs\/[a-z0-9]+\/thumbnail\?key=[a-f0-9]{64}$/.test(job.thumbnail_url) ? job.thumbnail_url : '';
  const art = `<span class="media-art-placeholder" aria-hidden="true">${job.status === 'completed' ? '▣' : '▶'}</span>` +
    (thumbnail ? `<img class="media-thumbnail" src="${safe(thumbnail)}" alt="${t('ui.media_thumbnail')}" width="52" height="52" loading="lazy" decoding="async"><span class="media-thumbnail-play" aria-hidden="true">${actionIcon('play')}</span>` : '') +
    (count > 1 ? `<span class="media-file-count" aria-hidden="true">${count}</span>` : '');
  const className = `media-art${job.thumbnail_kind === 'video' ? ' media-art-video' : ''}`;
  return count ? `<button type="button" class="${className}" data-open-media="${safe(job.id)}" title="${safe(viewTitle)}" aria-label="${safe(viewTitle)}">${art}</button>` : `<div class="${className}">${art}</div>`;
}


function timeLabel(timestamp) {
  if (!timestamp) return '—';
  return new Intl.DateTimeFormat(I18n.locale, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(timestamp * 1000));
}

function getVisibleJobs() {
  if (lastResponse?.jobs_page) return state.jobs;
  return state.jobs.filter((job) => {
    const matchesStatus = state.filter === 'all' || job.status === state.filter;
    const matchesPlatform = state.platform === 'all' || job.platform === state.platform;
    const needle = state.search.trim().toLocaleLowerCase();
    const matchesSearch = !needle || `${job.title} ${job.url} ${job.platform} ${job.filename}`.toLocaleLowerCase().includes(needle);
    return matchesStatus && matchesPlatform && matchesSearch;
  });
}

function renderPagination(total, pageCount) {
  const start = total ? (state.page - 1) * state.pageSize + 1 : 0;
  const end = Math.min(state.page * state.pageSize, total);
  const summary = total ? t('ui.showing_start_end_of_total_items', { start, end, total }) : t('ui.showing_0_items');
  if ($('#footer-summary').textContent !== summary) $('#footer-summary').textContent = summary;
  $('#jobs-page-size').value = String(state.pageSize);
  $('#jobs-page-prev').disabled = state.page <= 1;
  $('#jobs-page-next').disabled = state.page >= pageCount;

  const numbers = $('#jobs-page-numbers');
  const focusedPage = numbers.contains(document.activeElement) ? document.activeElement.dataset.page : null;
  const windowStart = Math.max(1, Math.min(state.page - 1, pageCount - 2));
  const pages = new Set([1, pageCount]);
  for (let page = windowStart; page <= Math.min(pageCount, windowStart + 2); page++) pages.add(page);
  let previous = 0;
  const markup = [...pages].sort((a, b) => a - b).map((page) => {
    const gap = previous && page > previous + 1 ? '<span class="page-gap" aria-hidden="true">…</span>' : '';
    previous = page;
    const current = page === state.page;
    const label = safe(t('ui.page_page', { page }));
    return `${gap}<button type="button" class="page-button${current ? ' selected' : ''}" data-page="${page}" title="${label}" aria-label="${label}"${current ? ' aria-current="page"' : ''}${total ? '' : ' disabled=""'}>${page}</button>`;
  }).join('');
  // Unchanged polling results keep the existing page controls and keyboard focus.
  if (numbers.innerHTML !== markup) {
    numbers.innerHTML = markup;
    if (focusedPage) {
      const target = numbers.querySelector(`[data-page="${focusedPage}"]`) || numbers.querySelector('[aria-current="page"]');
      if (target && !target.disabled) target.focus({ preventScroll: true });
    }
  }
}

function renderJobs({ resetScroll = false } = {}) {
  if (lastResponse?.jobs_page && lastResponse._requestView !== jobViewKey()) return;
  const visible = getVisibleJobs();
  const total = lastResponse?.jobs_page?.total ?? visible.length;
  const pageCount = lastResponse?.jobs_page?.page_count ?? Math.max(1, Math.ceil(total / state.pageSize));
  const previousPage = state.page;
  state.page = Math.max(1, Math.min(state.page, pageCount));
  const pageJobs = lastResponse?.jobs_page ? visible : visible.slice((state.page - 1) * state.pageSize, state.page * state.pageSize);
  const scroller = $('#jobs-table-scroll');
  const scrollTop = resetScroll || previousPage !== state.page ? 0 : scroller.scrollTop;
  const scrollLeft = scroller.scrollLeft;
  const focusedButton = rows.contains(document.activeElement) && document.activeElement.matches('button') ? document.activeElement : null;
  const focusedAttribute = focusedButton ? [...focusedButton.attributes].find((attribute) => attribute.name.startsWith('data-')) : null;
  const focusedAction = focusedAttribute ? { jobId: focusedButton.closest('tr').dataset.jobId, preview: focusedButton.classList.contains('media-art'), name: focusedAttribute.name, value: focusedAttribute.value } : null;
  $('#table-empty').classList.toggle('hidden', visible.length > 0);
  const renderedRows = pageJobs.map((job) => {
    const busy = pendingJobActions.has(job.id);
    const progress = Number.isFinite(job.progress) ? Math.max(0, Math.min(100, job.progress)) : null;
    const isActive = job.status === 'active';
    const isProfile = ['x_profile', 'pixiv_profile'].includes(job.mode);
    const stopped = job.error_code === 'profile_stopped';
    const skipped = wasSkipped(job);
    const showSkipResult = skipped && recentSkippedJobs.get(job.id) === jobRun(job);
    const stateText = uiMessage(skipped && !showSkipResult ? '已完成' : job.status_text || statusNames[job.status] || '處理中');
    const stateTitle = skipped ? t('ui.last_check_the_file_already_existed_so') : stateText;
    const supporting = (job.url ? `<div class="media-source" title="${safe(job.url)}">${safe(job.url)}</div>` : '') +
      (job.remove_when_finished ? `<div class="media-quality">${t(isProfile ? 'ui.stop_and_remove_after_the_current_post' : 'ui.this_job_will_be_removed_from_the')}</div>` : '') +
      (job.error ? `<div class="job-error">${safe(uiMessage(job.error))} <button class="detail-link" data-detail="${safe(job.id)}">${t('ui.view_details')}</button>${job.platform === 'X' ? `<button class="detail-link" data-login>${t('ui.connect_chrome')}</button>` : ''}</div>` : '');
    const showProgress = isActive && (!isProfile || (job.profile_scan_complete && job.profile_total_files > 0));
    const progressLine = showProgress ? `<div class="progress-line"><i style="width:${progress ?? 8}%"></i></div>` : '';
    const accountProgress = isProfile ? `<div class="profile-summary">${safe(profileSummary(job))}</div>` : '';
    const detail = isActive ? job.speed : '';
    const sizeLabel = Number.isFinite(job.size_bytes) ? fileSize(job.size_bytes) : (job.size || '—');
    const elapsed = elapsedLabel(job.elapsed_seconds);
    const sizeTitle = t(isProfile && isActive ? 'ui.size_of_saved_account_files_plus_bytes' : isActive ? 'ui.estimated_size_of_the_current_media_received' : 'ui.total_size_of_saved_files_for_this');
    const timeTitle = t(elapsed === '—' ? 'ui.elapsed_time_is_not_available' : 'ui.elapsed_time_from_start_to_finish_including');
    const canRetry = job.status === 'failed' || job.status === 'completed';
    const files = job.files || [];
    const fileCount = job.file_count ?? files.length;
    const viewImage = fileCount > 0 && files.every(isImageFile);
    const viewTitle = t(!fileCount ? 'ui.no_file_is_available_yet' : state.fileActions === 'browser' ? 'ui.browser_media_view' : fileCount > 1 ? 'ui.choose_a_file_to_play_or_view' : viewImage ? 'ui.view_image_in_the_default_app' : 'ui.play_video_or_audio_in_the_default');
    const folderTitle = t(!fileCount ? 'ui.no_saved_file_folder_is_available_yet' : state.fileActions === 'browser' ? 'ui.browser_job_files' : fileCount > 1 ? 'ui.choose_a_file_and_open_its_folder' : 'ui.open_this_file_s_folder');
    const requestedQuality = job.video_quality && job.video_quality !== 'best' ? t('ui.quality_limit_height_p', { height: job.video_quality }) : '';
    const retryTitle = t(canRetry && isProfile ? 'ui.sync_account_media_fetch_new_or_unfinished' : canRetry ? 'ui.download_again_and_overwrite_files_with_the' : isActive ? 'ui.download_in_progress_retry_after_it_finishes' : 'ui.this_job_is_already_queued') + (requestedQuality ? ` · ${requestedQuality}` : '');
    const stopTitle = t(job.stop_requested ? 'ui.stopping_keeping_downloaded_files' : 'ui.stop_download_keep_saved_files');
    const action = `<div class="row-actions compact-actions">
      <button type="button" class="row-icon-button media-open-button" data-open-media="${safe(job.id)}" title="${safe(viewTitle)}" aria-label="${safe(viewTitle)}" ${fileCount ? '' : 'disabled'}>${actionIcon(viewImage ? 'image' : 'play')}</button>
      <button type="button" class="row-icon-button folder-open-button" data-open-folder="${safe(job.id)}" title="${safe(folderTitle)}" aria-label="${safe(folderTitle)}" ${fileCount ? '' : 'disabled'}>${actionIcon('folder')}</button>
      ${job.status === 'selecting' ? `<button type="button" class="row-icon-button icon-retry-button" data-select-media="${safe(job.id)}" title="${t('ui.choose_media_to_download')}" aria-label="${t('ui.choose_media_to_download')}" aria-haspopup="dialog" ${busy ? 'disabled' : ''}>${actionIcon('play')}</button>` : `<button type="button" class="row-icon-button icon-retry-button" data-retry="${safe(job.id)}" title="${safe(retryTitle)}" aria-label="${safe(retryTitle)}" ${canRetry && !busy ? '' : 'disabled'}>${actionIcon('retry')}</button>`}
      ${isActive ? `<button type="button" class="row-icon-button icon-stop-button" data-stop="${safe(job.id)}" title="${safe(stopTitle)}" aria-label="${safe(stopTitle)}" ${job.stop_requested || busy ? 'disabled' : ''}>${actionIcon('stop')}</button>` : ''}
      <button type="button" class="row-icon-button icon-remove-button" data-remove="${safe(job.id)}" title="${t(isActive ? 'ui.wait_for_this_download_to_finish_before' : 'ui.remove_from_the_list_and_keep_files')}" aria-label="${t('ui.remove_from_the_list')}" ${isActive || busy ? 'disabled' : ''}>${actionIcon('remove')}</button>
    </div>`;
    const filenameForDisplay = files[0] || job.filename;
    const fileLabel = fileCount > 1 ? t('ui.count_media_files', { count: fileCount }) : (filenameForDisplay ? shortFileName(filenameForDisplay) : (isProfile && job.status === 'completed' ? t('ui.no_downloadable_media') : job.status === 'failed' ? '—' : t('ui.waiting_for_files')));
    const filePaths = fileCount ? files.slice(0, 20).map((filename) => fullFilePath(job, filename)).join('\n') +
      (fileCount > 20 ? `\n${t('ui.count_more_files_use_play_view_to', { count: fileCount - 20 })}` : '') : fullFilePath(job, job.filename);
    const warnings = job.warnings || [];
    const warningCount = job.warning_count ?? warnings.length;
    const warningTitle = t('ui.view_count_download_warnings', { count: warningCount });
    const warningButton = warningCount ? `<button type="button" class="quality-warning" data-warnings="${safe(job.id)}" aria-haspopup="dialog" aria-controls="warnings-modal" title="${safe(warningTitle)}" aria-label="${safe(warningTitle)}">${actionIcon('warning')}<span class="warning-count" aria-hidden="true">${warningCount}</span></button>` : '';
    const quality = uiMessage(job.quality || '原尺寸圖片 / 最高可用影片') + (requestedQuality ? ` · ${requestedQuality}` : '');
    return { id: job.id, markup: `<tr data-job-id="${safe(job.id)}">
      <td><div class="media-cell">${mediaPreview(job, files, viewTitle)}<div class="media-copy"><div class="media-title" title="${safe(jobTitle(job))}">${safe(jobTitle(job))}</div>${supporting}<div class="media-quality" title="${safe(quality)}">${safe(quality)}</div></div></div></td>
      <td><span class="platform-tag ${safe(job.platform.toLowerCase())}">${safe(job.platform)}</span></td>
      <td class="date-cell">${timeLabel(job.created_at)}</td>
      <td class="status-cell"><div class="status-row"><div class="status-label ${safe(stopped ? 'stopped' : job.status)}" title="${safe(stateTitle)}">${stopped ? actionIcon('stop') : statusIcon(job.status)}<span>${safe(stateText)}${progress !== null && showProgress ? ` · ${progress}%` : ''}</span></div>${warningButton}</div>${progressLine}${accountProgress}${detail ? `<div class="media-source">${safe(detail)}</div>` : ''}</td>
      <td class="size-time-cell"><b title="${safe(sizeTitle)}">${safe(sizeLabel)}</b><span class="size-time-duration" title="${safe(timeTitle)}">${safe(t('ui.elapsed_time', { time: elapsed }))}</span>${isActive && job.eta ? `<span class="size-time-eta">${safe(t('ui.remaining_time', { time: job.eta }))}</span>` : ''}</td>
      <td class="file-cell" title="${safe(filePaths)}">${safe(fileLabel)}</td>
      <td>${action}</td>
    </tr>` };
  });
  if (window.SSDLJobRows) SSDLJobRows.reconcile(rows, renderedRows);
  else rows.innerHTML = renderedRows.map((item) => item.markup).join('');

  rows.querySelectorAll('.media-thumbnail').forEach((preview) => {
    if (preview.dataset.bound) return;
    preview.dataset.bound = 'true';
    const loaded = () => preview.closest('.media-art')?.classList.add('has-thumbnail');
    const fallback = () => { preview.closest('.media-art')?.classList.remove('has-thumbnail'); preview.remove(); };
    preview.addEventListener('load', loaded);
    preview.addEventListener('error', fallback);
    if (preview.complete) { if (preview.naturalWidth) loaded(); else fallback(); }
  });

  renderPagination(total, pageCount);
  if (focusedAction) {
    const target = [...rows.querySelectorAll('button')].find((button) => button.closest('tr').dataset.jobId === focusedAction.jobId && button.classList.contains('media-art') === focusedAction.preview && button.getAttribute(focusedAction.name) === focusedAction.value);
    if (target && !target.disabled) target.focus({ preventScroll: true });
  }
  scroller.scrollTop = scrollTop;
  scroller.scrollLeft = scrollLeft;
}


function renderWarnings(job) {
  $('#warnings-title').textContent = t('ui.download_warnings_count', { count: job.warnings.length });
  $('#warnings-source').textContent = job.url;
  $('#warnings-list').replaceChildren(...job.warnings.map((source) => {
    const item = document.createElement('li');
    item.textContent = uiMessage(source);
    return item;
  }));
}
