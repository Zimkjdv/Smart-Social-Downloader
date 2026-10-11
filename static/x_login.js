/* X login actions use the shared local API client and application state. */
async function connectX(loginOnly = false) {
  if (state.xAuth.busy || connectingXRequest) return;
  connectingXRequest = true;
  $('#x-connect').disabled = true;
  $('#x-login-open').disabled = true;
  try {
    if (!await openSettings('x')) return;
    render(await api(loginOnly ? '/api/auth/x/login' : '/api/auth/x/connect', { method: 'POST', body: '{}' }));
  } catch (error) { toast(error.message, true); await refresh(); }
  finally {
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
  try {
    render(await api('/api/auth/x/disconnect', { method: 'POST', body: '{}' }));
    $('#x-cookie-file').value = '';
    toast('ui.x_session_disconnected');
  } catch (error) { toast(error.message, true); }
});
