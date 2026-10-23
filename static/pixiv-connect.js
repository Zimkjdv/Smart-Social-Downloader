/* The pairing ticket stays in the fragment; OAuth codes never enter this page. */
(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const { text: uiText } = window.I18n;
  let started = false;
  let disposed = false;
  let connectorFailed = false;
  let connectionState = 'pending';
  let timer;
  const fragment = new URLSearchParams(location.hash.slice(1));
  const hasTicket = /^[A-Za-z0-9_-]{43}$/.test(fragment.get('ticket') || '');
  function message(key, error = false) {
    const connected = key === 'ui.pixiv_connected';
    connectionState = connected ? 'connected' : error ? 'error' : 'pending';
    $('#connection-card').dataset.state = connectionState;
    uiText($('#connection-title'), connected ? 'ui.pixiv_connection_success' : error ? 'ui.pixiv_connection_attention' : 'ui.pixiv_connection_preparing');
    uiText($('#connection-message'), connected ? 'ui.pixiv_connection_ready' : key);
    uiText($('#connection-intro'), connected ? 'ui.pixiv_connection_finished' : 'ui.pixiv_bridge_intro');
    $('#connection-message').className = 'message' + (error ? ' error' : '');
    $('#connect-pixiv').classList.toggle('hidden', connected || error);
    $('#return-to-tool').classList.toggle('is-primary', connected || error);
    $('#extension-badge').classList.toggle('hidden', connected);
    if (connected) $('#install-panel').classList.add('hidden');
  }
  function start() {
    if (started || connectionState === 'connected' || !hasTicket || document.documentElement.dataset.ssdlPixivExtension !== 'ready') return;
    started = true;
    $('#connect-pixiv').disabled = true;
    message('ui.pixiv_automatic_waiting');
    document.dispatchEvent(new CustomEvent('ssdl-pixiv-connect'));
  }
  function ready() {
    uiText($('#extension-badge'), 'ui.chrome_connector_ready');
    $('#extension-badge').classList.add('ready');
    $('#install-panel').classList.add('hidden');
    start();
  }
  document.addEventListener('ssdl-pixiv-ready', ready);
  document.addEventListener('ssdl-pixiv-result', (event) => {
    let result;
    try { result = JSON.parse(event.detail); } catch { return; }
    if (result?.ok !== true) {
      connectorFailed = true;
      clearTimeout(timer);
      message('ui.pixiv_automatic_failed', true);
    }
  });
  $('#connect-pixiv').addEventListener('click', start);
  $('#reload-page').addEventListener('click', () => location.reload());
  async function poll() {
    try {
      const data = await SSDLApi.request('/api/auth/pixiv/status');
      if (disposed || connectorFailed) return;
      const auth = data.pixiv_auth;
      if (auth.connected && !auth.pending && !auth.busy && ['connected', 'idle'].includes(auth.attempt_phase || 'idle')) {
        message('ui.pixiv_connected'); return;
      }
      if (['failed', 'expired', 'cancelled'].includes(auth.attempt_phase)) {
        message(auth.attempt_phase === 'expired' ? 'ui.pixiv_automatic_expired' : 'ui.pixiv_automatic_failed', true);
        return;
      }
      if (fragment.get('result') === 'failed') { message('ui.pixiv_automatic_failed', true); return; }
      message(hasTicket || fragment.has('result') ? 'ui.pixiv_automatic_waiting' : 'ui.pixiv_bridge_start_from_tool');
    } catch { if (!disposed) message('ui.pixiv_bridge_service_unavailable', true); }
    if (!disposed && !connectorFailed) timer = setTimeout(poll, 2000);
  }
  SSDLApi.request('/api/auth/x/setup').then((data) => {
    if (!disposed && data.extension_dir) $('#extension-path').textContent = data.extension_dir;
  }).catch(() => {});
  const detectionTimer = setTimeout(() => {
    if (document.documentElement.dataset.ssdlPixivExtension === 'ready') ready();
    else uiText($('#extension-badge'), 'ui.pixiv_bridge_update_required');
  }, 800);
  poll();
  window.addEventListener('pagehide', () => { disposed = true; clearTimeout(timer); clearTimeout(detectionTimer); });
})();
