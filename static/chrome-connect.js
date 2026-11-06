const $ = (selector) => document.querySelector(selector);
const { t, text: uiText } = window.I18n;
const desktop = SSDLDesktop.createBrowser({ browser: window, document });
window.addEventListener('pagehide', (event) => { if (!event.persisted) desktop.dispose(); });
uiText($('#service-origin'), t('ui.local_service_origin_use_the_same_port', { origin: location.origin }));
let extensionReady = false;
let connecting = false;
let sessionSynced = false;
let hostBrowser = false;
function displayMessage(text, kind = '') {
  uiText($('#connection-message'), text);
  $('#connection-message').className = `message ${kind}`;
}
function showExtension() {
  extensionReady = true;
  uiText($('#extension-badge'), 'ui.chrome_connector_ready');
  $('#extension-badge').classList.add('ready');
  $('#connect-x').disabled = connecting;
  if (document.documentElement.dataset.ssdlExtensionVersion !== '1.2.0') {
    uiText($('#setup-message'), 'ui.the_connector_has_an_update_reload_it');
  } else $('#install-panel').classList.add('hidden');
}
document.addEventListener('ssdl-extension-ready', showExtension);
document.addEventListener('ssdl-extension-result', (event) => {
  let result;
  try { result = JSON.parse(event.detail); } catch { return; }
  if (typeof result?.message !== 'string') return;
  connecting = Boolean(result.busy);
  $('#connect-x').disabled = connecting;
  displayMessage(result.message, result.ok ? 'success' : result.busy ? '' : 'error');
  if (!connecting) {
    // The server may consume a ticket before storage fails. The next click
    // must obtain a fresh ticket, including after an unsuccessful attempt.
    history.replaceState(null, '', '/chrome-connect');
  }
  if (result.ok) {
    sessionSynced = true;
    $('#connect-x').textContent = t('ui.sync_x_session_again');
  }
});
$('#connect-x').addEventListener('click', () => {
  if (!extensionReady || connecting) return;
  document.dispatchEvent(new CustomEvent('ssdl-connect-request'));
});
$('#open-extensions').addEventListener('click', async () => {
  if (hostBrowser) { uiText($('#setup-message'), 'ui.enter_chrome_extensions_in_chrome_s_address'); return; }
  const button = $('#open-extensions');
  button.disabled = true;
  try {
    await SSDLApi.request('/api/auth/x/open-extensions', { method: 'POST', body: '{}' });
  } catch (error) { uiText($('#setup-message'), error.message || 'ui.enter_chrome_extensions_in_chrome_s_address'); }
  finally { button.disabled = false; }
});
$('#copy-path').addEventListener('click', async () => {
  try {
    const result = await desktop.copyText($('#extension-path').value);
    if (result.status !== 'completed') throw new Error(result.status);
    uiText($('#setup-message'), 'ui.path_copied_paste_it_into_the_folder');
  }
  catch { $('#extension-path').select(); uiText($('#setup-message'), 'ui.press_ctrl_c_to_copy_the_selected'); }
});
$('#reload-page').addEventListener('click', () => location.reload());
SSDLApi.request('/api/auth/x/setup').then((result) => {
  hostBrowser = result.host_browser === true;
  $('#extension-path').value = result.extension_dir;
  if (hostBrowser) {
    $('#extension-path').closest('.path-row').hidden = true;
    uiText($('#setup-message'), 'ui.x_host_extension_folder');
  }
  uiText($('#session-storage-copy'), result.storage_mode === 'memory' ? 'ui.x_memory_storage' : result.storage_mode === 'aes-gcm' ? 'ui.x_key_storage' : 'ui.session_data_is_sent_only_to_the');
}).catch((error) => { uiText($('#setup-message'), error.message); });
setTimeout(() => {
  if (document.documentElement.dataset.ssdlExtension === 'ready') showExtension();
  else { uiText($('#extension-badge'), 'ui.first_time_setup_load_the_chrome_connector'); }
}, 800);
document.addEventListener('ssdl-language-changed', () => {
  $('#connect-x').textContent = t(sessionSynced ? 'ui.sync_x_session_again' : 'ui.connect_signed_in_x_session');
  uiText($('#service-origin'), t('ui.local_service_origin_use_the_same_port', { origin: location.origin }));
});
