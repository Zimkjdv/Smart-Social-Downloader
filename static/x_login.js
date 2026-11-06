/* X login actions use the shared local API client and application state. */
let xConnectEpoch = 0;
async function connectX(loginOnly = false) {
  if (state.xAuth.busy || connectingXRequest) return;
  if (state.xAuth.host_browser && loginOnly) {
    const result = await desktop.openExternal('https://x.com/home');
    if (result.status !== 'completed') toast('ui.desktop_open_failed', true);
    return;
  }
  const pairingTab = state.xAuth.host_browser ? desktop.reserveExternal() : null;
  const epoch = ++xConnectEpoch;
  $('#x-pairing-link').hidden = true;
  $('#x-pairing-link').removeAttribute('href');
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
      const opened = pairingTab ? await pairingTab.open(destination.href) : await desktop.openExternal(destination.href);
      if (opened.status !== 'completed') toast('ui.x_use_pairing_link');
    }
  } catch (error) { toast(error.message, true); await refresh(); }
  finally {
    pairingTab?.cancel();
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
