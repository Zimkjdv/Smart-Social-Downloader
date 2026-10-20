/* X login actions use the shared local API client and application state. */
let xConnectEpoch = 0;
async function connectX(loginOnly = false) {
  if (state.xAuth.busy || connectingXRequest) return;
  if (state.xAuth.host_browser && loginOnly) { window.open('https://x.com/home', '_blank', 'noopener'); return; }
  const pairingTab = state.xAuth.host_browser ? window.open('about:blank', '_blank') : null;
  const epoch = ++xConnectEpoch;
  $('#x-pairing-link').hidden = true;
  $('#x-pairing-link').removeAttribute('href');
  if (pairingTab) pairingTab.opener = null;
  let navigated = false;
  connectingXRequest = true;
  $('#x-connect').disabled = true;
  $('#x-login-open').disabled = true;
  try {
    if (!await openSettings('x')) return;
    const result = await api(loginOnly ? '/api/auth/x/login' : '/api/auth/x/connect', { method: 'POST', body: '{}' });
    if (epoch !== xConnectEpoch) return;
    const { pairing_url: pairingUrl, ...snapshot } = result;
    render(snapshot);
    if (pairingUrl) {
      const destination = new URL(pairingUrl);
      if (destination.protocol !== 'http:' || destination.hostname !== '127.0.0.1' || destination.username || destination.password ||
          (destination.port || '80') !== (location.port || '80') || destination.pathname !== '/chrome-connect' || destination.search ||
          !/^#token=[A-Za-z0-9_-]{43}&connect=1$/.test(destination.hash)) throw new Error(t('ui.x_invalid_pairing'));
      const link = $('#x-pairing-link'); link.href = destination.href; link.hidden = false;
      if (pairingTab && !pairingTab.closed) { pairingTab.location.replace(destination.href); navigated = true; }
      else toast('ui.x_use_pairing_link');
    }
  } catch (error) { toast(error.message, true); await refresh(); }
  finally {
    if (pairingTab && !pairingTab.closed && !navigated) pairingTab.close();
    connectingXRequest = false;
    $('#x-connect').disabled = Boolean(state.xAuth.busy);
    $('#x-login-open').disabled = Boolean(state.xAuth.busy);
    $('#x-login-browser').disabled = Boolean(state.xAuth.busy);
    renderProfileLogin();
  }
}
$('#x-login-open').addEventListener('click', () => state.xAuth.connected ? openSettings('x') : connectX());
$('#x-connect').addEventListener('click', () => connectX());
$('#x-login-browser').addEventListener('click', () => connectX(true));
$('#x-disconnect').addEventListener('click', async () => {
  xConnectEpoch++;
  try {
    render(await api('/api/auth/x/disconnect', { method: 'POST', body: '{}' }));
    $('#x-cookie-file').value = '';
    toast('ui.x_session_disconnected');
  } catch (error) { toast(error.message, true); }
});
