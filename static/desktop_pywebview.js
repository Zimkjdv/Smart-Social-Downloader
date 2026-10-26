/* Only this Adapter knows pywebview. Business controllers keep using HTTP. */
(() => {
  'use strict';
  function create({ browser = window, document = browser.document, timeoutMs = 120000, readyTimeoutMs = 10000 } = {}) {
    let disposed = false, metadata = null, started = false, readySettled = false;
    const pending = new Set();
    const result = status => ({ status });
    const unavailable = Object.freeze({ openExternal:false, saveText:false, copyText:false, pickDirectory:false, stopBackend:false });
    let resolveReady;
    const ready = new Promise(resolve => { resolveReady = resolve; });
    function finishReady(value) {
      if (readySettled) return;
      readySettled = true; browser.clearTimeout(readyTimer); resolveReady(value);
    }
    const readyTimer = browser.setTimeout(() => finishReady(false), readyTimeoutMs);
    async function initialize() {
      if (started || disposed || !browser.pywebview?.api) return;
      started = true;
      try {
        const value = await browser.pywebview.api.describe();
        if (disposed || readySettled) return;
        if (value?.version !== 1 || value?.kind !== 'pywebview' || !['started', 'attached'].includes(value.ownership) ||
            !value.capabilities || Object.keys(unavailable).some(key => typeof value.capabilities[key] !== 'boolean')) return finishReady(false);
        metadata = Object.freeze({ ownership:value.ownership, capabilities:Object.freeze(
          Object.fromEntries(Object.keys(unavailable).map(key => [key, value.capabilities[key]]))) });
        finishReady(true);
      } catch { finishReady(false); }
    }
    browser.addEventListener('pywebviewready', initialize);
    initialize();
    async function invoke(method, capability, args = [], { signal } = {}) {
      if (disposed || signal?.aborted) return result('cancelled');
      if (!await ready || !metadata?.capabilities[capability]) return result('unsupported');
      if (disposed || signal?.aborted) return result('cancelled');
      const api = browser.pywebview?.api;
      if (typeof api?.[method] !== 'function') return result('unsupported');
      return new Promise(resolve => {
        let timer;
        function finish(value) {
          browser.clearTimeout(timer); pending.delete(cancel);
          signal?.removeEventListener('abort', cancel);
          resolve(value);
        }
        function cancel() { finish(result('cancelled')); }
        pending.add(cancel);
        signal?.addEventListener('abort', cancel, { once:true });
        timer = browser.setTimeout(() => finish({ status:'error', code:'timeout' }), timeoutMs);
        Promise.resolve().then(() => disposed || signal?.aborted ? result('cancelled') : api[method](...args))
          .then(value => {
            if (!value || !['completed','cancelled','unsupported','blocked','error'].includes(value.status) ||
                capability === 'pickDirectory' && value.status === 'completed' && typeof value.path !== 'string') return finish(result('error'));
            finish(value);
          }, () => finish(result('error')));
      });
    }
    function reserveExternal() {
      let cancelled = false, used = false;
      return Object.freeze({
        async open(url) {
          if (cancelled || used || disposed) return result('cancelled');
          used = true;
          return invoke('open_external', 'openExternal', [url]);
        },
        cancel() { cancelled = true; },
      });
    }
    const adapter = Object.freeze({
      version:1, kind:'pywebview', ready,
      get capabilities() { return metadata?.capabilities || unavailable; },
      get ownership() { return metadata?.ownership || ''; },
      openExternal:url => invoke('open_external', 'openExternal', [url]),
      reserveExternal,
      pickDirectory:(initial = '', options) => invoke('pick_directory', 'pickDirectory', [initial], options),
      saveText:(value, options) => invoke('save_text', 'saveText', [value], options),
      copyText:text => invoke('copy_text', 'copyText', [text]),
      stopBackend:() => invoke('stop_backend', 'stopBackend'),
      dispose() {
        if (disposed) return;
        disposed = true; finishReady(false);
        browser.removeEventListener('pywebviewready', initialize);
        document.removeEventListener('click', openLink, true);
        for (const cancel of [...pending]) cancel();
      },
    });
    function openLink(event) {
      const link = event.target.closest?.('a[href]');
      if (!link || event.defaultPrevented || link.getAttribute('href')?.startsWith('#')) return;
      // Keep home navigation in this shell, including its explicit host marker.
      event.preventDefault();
      const url = new URL(link.href, browser.location.href);
      if (url.origin === browser.location.origin && url.pathname === '/' && !url.search && !url.hash) {
        browser.location.reload(); return;
      }
      adapter.openExternal(url.href);
    }
    document.addEventListener('click', openLink, true);
    return adapter;
  }
  window.SSDLDesktopPywebview = Object.freeze({ create });
})();
