/* Shared local API client. Deadlines cover both headers and JSON body reads. */
(() => {
  'use strict';
  const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  const number = (value) => Number.isFinite(value) && value >= 0;
  const count = (value) => Number.isInteger(value) && value >= 0;
  const strings = (value) => Array.isArray(value) && value.every((item) => typeof item === 'string');
  const optional = (value, key, check) => value[key] === undefined || check(value[key]);
  function databases(value) {
    return object(value) && typeof value.instance === 'string' && /^[a-f0-9]{32}$/.test(value.instance) && count(value.revision) &&
      typeof value.ready === 'boolean' && typeof value.busy === 'boolean' && number(value.checked_at) &&
      ['idle', 'running', 'complete', 'partial', 'failed', 'cancelled'].includes(value.phase) &&
      ['', 'refresh', 'backup', 'compact'].includes(value.operation) &&
      ['total_bytes', 'reclaimable_bytes', 'backup_bytes'].every(key => count(value[key])) &&
      typeof value.backup_name === 'string' && /^(?:|backup-\d{8}-\d{6}-[a-f0-9]{12})$/.test(value.backup_name) &&
      typeof value.error_code === 'string' && typeof value.result_code === 'string' &&
      Array.isArray(value.entries) && value.entries.length <= 3 && new Set(value.entries.map(item => item?.id)).size === value.entries.length &&
      value.entries.every(item => object(item) && ['images', 'media', 'profiles'].includes(item.id) &&
        typeof item.filename === 'string' && ['ok', 'error', 'missing'].includes(item.status) && typeof item.error_code === 'string' &&
        ['size_bytes', 'wal_bytes', 'shm_bytes', 'journal_bytes', 'page_count', 'page_size', 'free_pages', 'reclaimable_bytes'].every(key => optional(item, key, count)) &&
        optional(item, 'records', value => value === null || count(value)) &&
        ['schema_ok', 'compacted', 'checkpoint_busy'].every(key => optional(item, key, flag => typeof flag === 'boolean')));
  }
  function environment(value) {
    return object(value) && ['idle', 'checking', 'complete'].includes(value.phase) &&
      typeof value.busy === 'boolean' && typeof value.ready === 'boolean' && number(value.checked_at) &&
      ['ok', 'warning', 'error'].includes(value.status) && count(value.errors) && count(value.warnings) &&
      (value.port === null || Number.isInteger(value.port) && value.port >= 1 && value.port <= 65535) &&
      Array.isArray(value.checks) && value.checks.every((item) => object(item) &&
        ['id', 'name', 'detail', 'version', 'hint'].every((key) => typeof item[key] === 'string') &&
        ['ok', 'warning', 'error'].includes(item.status) && typeof item.required === 'boolean');
  }
  function job(job) {
    return object(job) &&
      typeof job.id === 'string' && typeof job.url === 'string' && typeof job.platform === 'string' &&
      ['queued', 'active', 'completed', 'failed', 'selecting'].includes(job.status) && number(job.created_at) &&
      optional(job, 'files', strings) && optional(job, 'warnings', strings) &&
      optional(job, 'title', (item) => typeof item === 'string') &&
      optional(job, 'file_count', count) && optional(job, 'warning_count', count) &&
      optional(job, 'video_quality', (item) => ['best', '2160', '1440', '1080', '720', '480', '360', '240', '144'].includes(item)) &&
      optional(job, 'selected_media', (item) => item === '' || typeof item === 'string' && /^[a-f0-9]{24}$/.test(item)) &&
      optional(job, 'selection_options', (items) => Array.isArray(items) && items.length >= 1 && items.length <= 12 &&
        items.every((item) => object(item) && typeof item.id === 'string' && /^[a-f0-9]{24}$/.test(item.id) &&
          typeof item.title === 'string' && typeof item.host === 'string' && count(item.variants) && item.variants > 0 &&
          ['video', 'audio', 'embed', 'media'].includes(item.kind))) &&
      optional(job, 'files_complete', (item) => typeof item === 'boolean');
  }
  function state(value) {
    return object(value) && Array.isArray(value.jobs) && value.jobs.every(job) &&
      (value.state_instance === undefined && value.state_sequence === undefined ||
        typeof value.state_instance === 'string' && /^[a-f0-9]{32}$/.test(value.state_instance) &&
        Number.isSafeInteger(value.state_sequence) && value.state_sequence >= 0) &&
      optional(value, 'total_jobs', count) && optional(value, 'platforms', strings) &&
      optional(value, 'active_job', (item) => item === null || job(item)) &&
      optional(value, 'jobs_page', (item) => object(item) && count(item.page) && item.page >= 1 &&
        [10, 20, 50].includes(item.page_size) && count(item.page_count) && item.page_count >= item.page && count(item.total) &&
        ['all', 'queued', 'active', 'completed', 'failed', 'selecting'].includes(item.status) &&
        typeof item.platform === 'string' && typeof item.search === 'string' && value.jobs.length <= item.page_size) &&
      object(value.counts) && ['queued', 'active', 'completed', 'failed'].every((key) => count(value.counts[key])) &&
      optional(value.counts, 'selecting', count) &&
      typeof value.paused === 'boolean' && typeof value.ready === 'boolean' &&
      optional(value, 'file_actions', (item) => ['desktop', 'browser'].includes(item)) &&
      optional(value, 'pairing_url', (item) => typeof item === 'string' && item.length <= 512) &&
      optional(value, 'app_version', (item) => typeof item === 'string' && item.length <= 64) &&
      optional(value, 'dynamic_capture', (item) => typeof item === 'boolean') &&
      optional(value, 'browser_capture_available', (item) => typeof item === 'boolean') &&
      optional(value, 'pixiv_auth', (item) => object(item) && typeof item.connected === 'boolean' &&
        typeof item.busy === 'boolean' && typeof item.phase === 'string' &&
        ['dpapi', 'memory', 'aes-gcm'].includes(item.storage_mode) &&
        !('refresh_token' in item) && !('access_token' in item)) &&
      typeof value.download_dir === 'string' && typeof value.x_cookie_file === 'string' &&
      object(value.x_auth) && typeof value.x_auth.connected === 'boolean' && typeof value.x_auth.busy === 'boolean' &&
      optional(value.x_auth, 'host_browser', (item) => typeof item === 'boolean') &&
      optional(value.x_auth, 'storage_mode', (item) => ['dpapi', 'memory', 'aes-gcm'].includes(item)) &&
      optional(value.x_auth, 'persistent', (item) => typeof item === 'boolean') &&
      typeof value.x_auth.phase === 'string' && object(value.safe_queue) && typeof value.safe_queue.enabled === 'boolean' &&
      object(value.rate_limit) && count(value.rate_limit.used) && count(value.rate_limit.limit) &&
      object(value.storage) && typeof value.storage.ready === 'boolean' &&
      optional(value, 'persistence', (item) => object(item) && typeof item.healthy === 'boolean' && typeof item.error === 'string' && typeof item.blocked === 'boolean' &&
        optional(item, 'max_bytes', (size) => count(size) && size > 0) &&
        ['saved_bytes', 'attempted_bytes'].every((key) => optional(item, key, (size) => size === null || count(size))) &&
        ['capacity_warning', 'attempted_bytes_exact'].every((key) => optional(item, key, (flag) => typeof flag === 'boolean'))) &&
      optional(value, 'worker', (item) => object(item) && typeof item.alive === 'boolean' && typeof item.phase === 'string') &&
      optional(value, 'databases', databases) && optional(value, 'environment', environment);
  }
  function contract(path, method = 'GET') {
    path = path.split('?')[0];
    if (path === '/api/ui-preferences') return value => object(value) && (value.preferences === null ||
      object(value.preferences) && value.preferences.schema === 1 && ['en', 'zh-Hant'].includes(value.preferences.language) &&
      [10, 20, 50].includes(value.preferences.page_size));
    if (path === '/api/databases') return databases;
    if (/^\/api\/jobs\/[^/]+\/select-media$/.test(path)) return state;
    if (/^\/api\/jobs\/[^/]+\/details$/.test(path)) return (value) => job(value) &&
      strings(value.warnings) && typeof value.error_detail === 'string';
    if (/^\/api\/jobs\/[^/]+\/files$/.test(path)) return (value) => object(value) &&
      typeof value.job_id === 'string' && count(value.total) && count(value.offset) && value.offset <= value.total &&
      count(value.limit) && value.limit >= 1 && value.limit <= 100 &&
      (value.next_offset === null || count(value.next_offset) && value.next_offset > value.offset && value.next_offset <= value.total) &&
      Array.isArray(value.files) && value.files.length <= value.limit &&
      value.files.every((item, index) => object(item) && item.index === value.offset + index &&
        item.index < value.total && typeof item.filename === 'string');
    if (path === '/api/environment' || path === '/api/environment/refresh') return environment;
    if (path === '/api/diagnostics') return (value) => object(value) && value.format_version === 1 &&
      optional(value, 'app_version', (item) => typeof item === 'string' && item.length <= 64) &&
      number(value.created_at) && environment(value.environment) && Array.isArray(value.jobs) && object(value.counts);
    if (path === '/api/auth/pixiv/begin') return (value) => object(value) &&
      (typeof value.authorization_url === 'string' && value.authorization_url.length <= 1024 &&
        value.authorization_url.startsWith('https://app-api.pixiv.net/web/v1/login?') ||
       typeof value.pairing_url === 'string' && value.pairing_url.length <= 256 &&
        /^http:\/\/127\.0\.0\.1:[0-9]{1,5}\/pixiv-connect#ticket=[A-Za-z0-9_-]{43}$/.test(value.pairing_url)) &&
      typeof value.opened === 'boolean' && count(value.expires_in);
    if (['/api/auth/pixiv/connect', '/api/auth/pixiv/disconnect', '/api/auth/pixiv/status'].includes(path)) return (value) =>
      object(value) && object(value.pixiv_auth) && typeof value.pixiv_auth.connected === 'boolean' &&
      typeof value.pixiv_auth.busy === 'boolean' && typeof value.pixiv_auth.phase === 'string' &&
      ['dpapi', 'memory', 'aes-gcm'].includes(value.pixiv_auth.storage_mode) &&
      !('refresh_token' in value.pixiv_auth) && !('access_token' in value.pixiv_auth);
    if (path === '/api/auth/x/setup') return (value) => object(value) &&
      typeof value.extension_dir === 'string' && typeof value.extension_id === 'string' &&
      optional(value, 'port', (item) => Number.isInteger(item) && item >= 1 && item <= 65535);
    if (path === '/api/downloads/open' || /\/(?:open-file|open-folder)$/.test(path)) {
      return (value) => object(value) && value.opened === true;
    }
    if (path === '/api/jobs' && method.toUpperCase() !== 'GET') return (value) => object(value) && state(value.state) &&
      strings(value.added) && strings(value.reused) && strings(value.already_pending) &&
      Array.isArray(value.rejected) && value.rejected.every((item) => object(item) && typeof item.error === 'string');
    if (['/api/rate/reset', '/api/jobs/clear-done', '/api/jobs/clear-all', '/api/jobs/retry-failed'].includes(path)) {
      return (value) => object(value) && state(value.state) &&
        (path === '/api/rate/reset' || path === '/api/jobs/retry-failed' ? true : count(value.removed)) &&
        (path !== '/api/jobs/retry-failed' || count(value.retried)) &&
        (path !== '/api/jobs/clear-all' || typeof value.pending_active === 'boolean');
    }
    return state;
  }
  async function request(path, options = {}) {
    const { timeoutMs = 15000, validate = contract(path, options.method || 'GET'), signal, ...fetchOptions } = options;
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    const cancel = () => controller.abort();
    if (signal?.aborted) cancel();
    else signal?.addEventListener('abort', cancel, { once: true });
    const method = (fetchOptions.method || 'GET').toUpperCase();
    const mutation = method !== 'GET' && method !== 'HEAD';
    const fail = (code, copy, uncertain = false) => {
      const error = new Error(copy);
      error.code = code;
      error.uncertain = uncertain && mutation;
      if (error.uncertain) error.message += ' 操作結果尚未確認，請先更新狀態，避免重複操作。';
      return error;
    };
    try {
      const response = await fetch(path, { ...fetchOptions, signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) } });
      if (!/^application\/json\b/i.test(response.headers.get('Content-Type') || '')) {
        throw fail('invalid_response', '本機服務回傳了非 JSON 回應，請更新狀態或重新啟動服務。', response.ok || response.status >= 500);
      }
      let result;
      try { result = await response.json(); }
      catch (error) {
        if (timedOut || controller.signal.aborted) throw error;
        throw fail('invalid_json', '本機服務回傳的 JSON 無法解析，已保留上次成功資料。', response.ok || response.status >= 500);
      }
      if (!response.ok) throw fail('http_error', typeof result?.error === 'string' && result.error
        ? result.error : `請求失敗 (${response.status})`, response.status >= 500);
      if (!validate(result)) throw fail('invalid_schema', '本機服務回應格式不正確，已保留上次成功資料。', true);
      return result;
    } catch (error) {
      if (timedOut) throw fail('timeout', '本機服務回應逾時，請確認服務仍在執行。', true);
      if (controller.signal.aborted) throw fail('cancelled', '請求已取消。', true);
      if (error.code) throw error;
      throw fail('network', '無法連線到本機服務，請確認 start.bat 已啟動。', true);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
    }
  }
  window.SSDLApi = { request, isState: state, isEnvironment: environment };
})();
