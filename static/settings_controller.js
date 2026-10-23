/* SSDLSettingsController: explicit dependencies and controller-owned state. */
(() => {
  'use strict';
  function create(dependencies) {
    const { document, browser, $, t, uiMessage, uiText, api, getSnapshot, isOffline } = dependencies;
    const scope = window.SSDLControllerLifecycle.create(browser);
    const render = scope.effect(dependencies.render);
    const toast = scope.effect(dependencies.toast);
    const { loadEnvironment, renderOffline } = dependencies;
    let settingsOpening = false;
    let resettingRate = false;
    let settingsEpoch = 0;
    let savingSettings = false;
    const modal = $('#settings-modal');

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
      scope.listen(tab, 'click', () => selectSettingsTab(tab.dataset.settingsTab));
      scope.listen(tab, 'keydown', (event) => {
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

    scope.listen(modal, 'keydown', (event) => {
      if (event.key !== 'Tab' || modal.classList.contains('hidden') || rateConfirmation.open) return;
      const focusable = [...modal.querySelectorAll('button:not([disabled]), input:not([disabled]), a[href], summary, [tabindex="0"]')]
        .filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });

    function closeSettings() {
      settingsEpoch++;
      if (!scope.active) return;
      if (modal.classList.contains('hidden')) return;
      modal.classList.add('hidden');
      $('#pixiv-code').value = $('#pixiv-token').value = '';
      if (settingsReturnFocus?.isConnected && !settingsReturnFocus.disabled) settingsReturnFocus.focus();
      settingsReturnFocus = null;
    }

    async function openSettings(requestedTab) {
      if (!scope.active || settingsOpening) return false;
      const epoch = ++settingsEpoch;
      settingsOpening = true;
      const wasOpen = !modal.classList.contains('hidden');
      if (!wasOpen) settingsReturnFocus = document.activeElement;
      $('#settings-open').disabled = true;
      let loaded = false;
      try {
        const data = await api('/api/state');
        if (!scope.active || epoch !== settingsEpoch) return false;
        render(data);
        loaded = true;
        uiText($('#settings-message'), '');
        $('#settings-message').classList.remove('error');
      } catch (error) {
        if (!scope.active || epoch !== settingsEpoch) return false;
        uiText($('#settings-message'), error.message);
        $('#settings-message').classList.add('error');
        renderOffline(error);
      } finally {
        if (scope.active && epoch === settingsEpoch) {
          if (!wasOpen && getSnapshot()) {
            const snapshot = getSnapshot();
            $('#download-dir').value = snapshot.download_dir;
            $('#x-cookie-file').value = snapshot.x_cookie_file;
            $('#hourly-job-limit').value = snapshot.hourly_job_limit ?? snapshot.rate_limit.limit;
            $('#no-progress-timeout').value = snapshot.no_progress_timeout ?? 300;
            $('#cooldown-mode').value = snapshot.safe_queue.cooldown_mode || 'platform';
            $('#dynamic-capture').checked = Boolean(snapshot.dynamic_capture);
          }
          modal.classList.remove('hidden');
          selectSettingsTab(typeof requestedTab === 'string' ? requestedTab : wasOpen ? settingsTab : 'general');
          if (!wasOpen) $('#settings-tab-' + settingsTab).focus();
        }
        settingsOpening = false;
        if (scope.active) $('#settings-open').disabled = false;
      }
      return loaded;
    }

    scope.listen($('#settings-open'), 'click', openSettings);

    const rateConfirmation = $('#rate-confirm-dialog');

    let rateResetTrigger = null;

    function openRateResetConfirmation(event) {
      if (resettingRate || isOffline() || !getSnapshot() || rateConfirmation.open) return;
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

    scope.listen($('#rate-confirm-close'), 'click', closeRateResetConfirmation);

    scope.listen($('#rate-confirm-cancel'), 'click', closeRateResetConfirmation);

    scope.listen(rateConfirmation, 'cancel', (event) => {
      event.preventDefault();
      closeRateResetConfirmation();
    });

    function renderRateResetButtons() {
      if (!scope.active) return;
      const button = $('#rate-reset');
      const topButton = $('#top-rate');
      const quota = getSnapshot()?.rate_limit || {};
      const unavailable = resettingRate || isOffline() || !getSnapshot();
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
      topButton.title = isOffline() ? t('ui.service_offline') : resettingRate ? t('ui.resetting_rate') :
        t('ui.click_to_confirm_a_rate_reset') + '\n' + t('ui.used_jobs_started_in_the_last_60', { used: quota.used ?? '—', limit: quota.limit ?? 40 }) +
        (quota.limited ? t('ui.next_slot_in_about_minutes_minutes', { minutes: Math.ceil((quota.wait_seconds || 0) / 60) }) : '');
    }

    async function resetRate() {
      if (!rateConfirmation.open || resettingRate || isOffline() || !getSnapshot()) return;
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
        if (!scope.active) return;
        render(result.state);
        didReset = true;
        uiText(message, 'ui.rate_reset_new_job_starts_will_be');
        toast('ui.rate_reset_new_job_starts_will_be');
      } catch (error) {
        if (!scope.active) return;
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

    scope.listen($('#rate-reset'), 'click', openRateResetConfirmation);

    scope.listen($('#top-rate'), 'click', openRateResetConfirmation);

    scope.listen($('#rate-confirm-submit'), 'click', resetRate);

    scope.listen($('#settings-close'), 'click', closeSettings);

    scope.listen($('#settings-cancel'), 'click', closeSettings);

    scope.listen(modal, 'click', (event) => { if (event.target === modal) closeSettings(); });

    scope.listen($('#settings-save'), 'click', async () => {
      if (savingSettings) return;
      const button = $('#settings-save');
      const message = $('#settings-message');
      if ($('#hourly-job-limit').validity?.valid === false || $('#no-progress-timeout').validity?.valid === false) selectSettingsTab('general');
      if (!$('#hourly-job-limit').reportValidity() || !$('#no-progress-timeout').reportValidity()) return;
      savingSettings = true;
      const epoch = settingsEpoch;
      button.disabled = true;
      uiText(message, 'ui.saving');
      message.classList.remove('error');
      try {
        const result = await api('/api/settings', { method: 'POST', body: JSON.stringify({ download_dir: $('#download-dir').value, x_cookie_file: $('#x-cookie-file').value, hourly_job_limit: Number($('#hourly-job-limit').value), no_progress_timeout: Number($('#no-progress-timeout').value), cooldown_mode: $('#cooldown-mode').value, dynamic_capture: $('#dynamic-capture').checked }) });
        if (!scope.active) return;
        render(result);
        if (epoch !== settingsEpoch) return;
        uiText(message, 'ui.settings_saved_the_hourly_limit_is_now'); toast('ui.settings_saved');
        scope.defer(() => { if (epoch === settingsEpoch) closeSettings(); }, 550);
      } catch (error) { if (scope.active && epoch === settingsEpoch) { uiText(message, error.message); message.classList.add('error'); } }
      finally { savingSettings = false; if (scope.active) button.disabled = false; }
    });
    function renderSnapshot(data) {
      if (!scope.active) return;
      $('#settings-application-version').textContent = data.app_version || '—';
      $('#browser-capture-status').textContent = t(data.browser_capture_available ? 'ui.dynamic_capture_ready' : 'ui.dynamic_capture_missing');
      const quota = data.rate_limit || {};
      $('#settings-rate-summary').textContent = t('ui.current_usage_used_limit_jobs', { used: quota.used ?? '—', limit: quota.limit ?? 40 });
      renderRateResetButtons();
    }
    function closeForEscape(event) {
      if (!scope.active) return false;
      if (rateConfirmation.open) { event.preventDefault(); closeRateResetConfirmation(); return true; }
      closeSettings(); return false;
    }
    scope.onDispose(() => { settingsEpoch++; });
    return Object.freeze({ init: scope.init, dispose: scope.dispose, render: renderSnapshot, open: openSettings, close: closeSettings, renderRateResetButtons, closeForEscape });
  }
  window.SSDLSettingsController = Object.freeze({ create });
})();
