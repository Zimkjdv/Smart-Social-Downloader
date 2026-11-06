/* Pixiv credentials stay in transient inputs/requests, never browser storage. */
(() => {
  'use strict';
  window.SSDLPixivLogin = {
    create({ api, refresh, state, $, t, uiText, desktop }) {
      const scope = window.SSDLControllerLifecycle.create(window);
      let busy = false;
      let pendingPairing = null;
      let attemptPhase = 'idle';
      function message(key, error = false) {
        if (['ui.pixiv_connected', 'ui.pixiv_disconnected'].includes(key)) key = '';
        uiText($('#pixiv-auth-message'), key);
        $('#pixiv-auth-message').classList.toggle('error', error);
      }
      function render() {
        if (!scope.active) return;
        const auth = state.pixivAuth || {};
        const phase = auth.attempt_phase || 'idle';
        const pending = Boolean(auth.pending || auth.busy);
        const cardState = pending ? 'pending' : auth.connected ? 'connected' : auth.phase === 'expired' ? 'expired' : 'disconnected';
        $('#pixiv-session-card').dataset.state = cardState;
        $('#pixiv-auth-status').textContent = t(auth.pending || auth.busy ? 'ui.pixiv_automatic_waiting' : auth.connected ? 'ui.pixiv_connected' :
          auth.phase === 'expired' ? 'ui.pixiv_expired' : 'ui.pixiv_connect_required');
        $('#pixiv-session-summary').textContent = t(pending ? 'ui.pixiv_session_pending' : auth.connected ?
          'ui.pixiv_session_ready' : 'ui.pixiv_session_connect_help');
        $('#pixiv-automatic-help').classList.toggle('hidden', Boolean(auth.connected) && !pending);
        $('#pixiv-begin').textContent = t(auth.connected ? 'ui.pixiv_reconnect' : 'ui.pixiv_automatic_begin');
        $('#pixiv-disconnect').textContent = t(pending ? 'ui.pixiv_cancel_connection' : 'ui.pixiv_clear_session');
        $('#pixiv-disconnect').disabled = busy || Boolean(auth.busy) || (!auth.connected && !pending && auth.phase !== 'expired');
        $('#pixiv-storage-description').textContent = t(auth.storage_mode === 'dpapi' ? 'ui.pixiv_dpapi' :
          auth.storage_mode === 'aes-gcm' ? 'ui.pixiv_aes' : 'ui.pixiv_memory');
        for (const id of ['pixiv-begin', 'pixiv-manual-begin', 'pixiv-connect', 'pixiv-token-connect']) {
          $('#' + id).disabled = busy || Boolean(auth.busy);
        }
        if (phase !== attemptPhase) {
          attemptPhase = phase;
          const key = { connected: 'ui.pixiv_connected', failed: 'ui.pixiv_automatic_failed',
            expired: 'ui.pixiv_automatic_expired', cancelled: 'ui.pixiv_disconnected' }[phase];
          if (key) message(key, ['failed', 'expired'].includes(phase));
        }
        if (['connected', 'failed', 'expired', 'cancelled'].includes(phase)) {
          $('#pixiv-auth-link').classList.add('hidden');
          $('#pixiv-auth-link').removeAttribute('href');
        }
      }
      async function perform(action, values = {}) {
        if (busy || !scope.active) return;
        busy = true;
        const pairingTab = pendingPairing = action === 'begin' && state.xAuth.host_browser ? desktop.reserveExternal() : null;
        render();
        message('ui.pixiv_working');
        try {
          const result = await api('/api/auth/pixiv/' + action,
            { method: 'POST', body: JSON.stringify(values), timeoutMs: 35000 });
          if (!scope.active) return;
          if (action === 'begin') {
            const url = new URL(result.pairing_url || result.authorization_url);
            const automatic = Boolean(result.pairing_url);
            if (url.username || url.password || (automatic ?
                url.protocol !== 'http:' || url.hostname !== '127.0.0.1' ||
                (url.port || '80') !== (location.port || '80') || url.pathname !== '/pixiv-connect' || url.search ||
                !/^#ticket=[A-Za-z0-9_-]{43}$/.test(url.hash) :
                url.origin !== 'https://app-api.pixiv.net' || url.pathname !== '/web/v1/login')) {
              throw new Error(t('ui.pixiv_invalid_authorization'));
            }
            const link = $('#pixiv-auth-link');
            link.href = url.href;
            link.classList.remove('hidden');
            if (!result.opened) {
              const opened = pairingTab ? await pairingTab.open(url.href) : await desktop.openExternal(url.href);
              if (opened.status !== 'completed') { message('ui.pixiv_use_link'); await refresh(); return; }
            }
            message(automatic ? 'ui.pixiv_automatic_opened' : 'ui.pixiv_opened');
            await refresh();
          } else {
            state.pixivAuth = result.pixiv_auth;
            $('#pixiv-auth-link').classList.add('hidden');
            $('#pixiv-auth-link').removeAttribute('href');
            message(action === 'disconnect' ? 'ui.pixiv_disconnected' : 'ui.pixiv_connected');
            await refresh();
          }
        } catch (error) {
          if (scope.active) message(error.message, true);
        } finally {
          pairingTab?.cancel();
          pendingPairing = null;
          busy = false;
          render();
        }
      }
      scope.listen($('#pixiv-begin'), 'click', () => perform('begin'));
      scope.listen($('#pixiv-manual-begin'), 'click', () => perform('begin', { manual: true }));
      scope.listen($('#pixiv-connect'), 'click', () => {
        const code = $('#pixiv-code').value.trim();
        if (!code) { message('ui.pixiv_paste_code', true); $('#pixiv-code').focus(); return; }
        $('#pixiv-code').value = '';
        perform('connect', { code });
      });
      scope.listen($('#pixiv-token-connect'), 'click', () => {
        const token = $('#pixiv-token').value.trim();
        if (!token) { message('ui.pixiv_paste_token', true); $('#pixiv-token').focus(); return; }
        $('#pixiv-token').value = '';
        perform('connect', { refresh_token: token });
      });
      scope.listen($('#pixiv-disconnect'), 'click', () => {
        $('#pixiv-code').value = $('#pixiv-token').value = '';
        perform('disconnect');
      });
      for (const [input, button] of [['pixiv-code', 'pixiv-connect'], ['pixiv-token', 'pixiv-token-connect']]) {
        scope.listen($('#' + input), 'keydown', (event) => {
          if (event.key === 'Enter') { event.preventDefault(); $('#' + button).click(); }
        });
      }
      return { init: scope.init, render, dispose() {
        pendingPairing?.cancel();
        $('#pixiv-code').value = $('#pixiv-token').value = '';
        scope.dispose();
      } };
    },
  };
})();
