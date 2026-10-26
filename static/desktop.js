/* DesktopInterface v1: browser operations and resources stay behind this seam. */
(() => {
  'use strict';
  function createBrowser({ browser = window, document = browser.document } = {}) {
    let disposed = false;
    const pending = new Set();
    const exports = new Set();
    const result = (status) => ({ status });
    function destination(value) {
      if (typeof value !== 'string' || !value || value.length > 8192) throw new TypeError('invalid_url');
      const url = new URL(value, browser.location.href);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new TypeError('invalid_url');
      return url.href;
    }
    // Reserve before an HTTP await to preserve the click gesture. Callers never receive a Window.
    function reserveExternal() {
      let tab = null, finished = disposed;
      if (!finished) {
        try { tab = browser.open('about:blank', '_blank'); if (tab) tab.opener = null; }
        catch { /* Popup permission can be denied. The caller keeps its link. */ }
      }
      function cancel() {
        if (finished) return;
        finished = true;
        pending.delete(cancel);
        try { if (tab && !tab.closed) tab.close(); } catch { /* Already closed. */ }
        tab = null;
      }
      if (!finished) pending.add(cancel);
      return Object.freeze({
        async open(value) {
          if (disposed || finished) return result('cancelled');
          try {
            const url = destination(value);
            if (!tab) { cancel(); return result('blocked'); }
            if (tab.closed) { cancel(); return result('cancelled'); }
            tab.location.replace(url);
            finished = true;
            pending.delete(cancel);
            tab = null;
            return result('completed');
          } catch { cancel(); return result('error'); }
        },
        cancel,
      });
    }
    async function openExternal(value) {
      if (disposed) return result('cancelled');
      try { destination(value); } catch { return result('error'); }
      return reserveExternal().open(value);
    }
    async function saveText({ filename, text, mimeType = 'text/plain' } = {}, { signal } = {}) {
      if (disposed || signal?.aborted) return result('cancelled');
      if (typeof filename !== 'string' || !/^[^/\\:\x00-\x1f]{1,128}$/.test(filename) || ['.', '..'].includes(filename) ||
          typeof text !== 'string' || text.length > 16 * 1024 * 1024 || !['application/json', 'text/plain'].includes(mimeType)) return result('error');
      let url = null, timer = null;
      function release() {
        if (timer !== null) browser.clearTimeout(timer);
        signal?.removeEventListener('abort', release);
        if (url !== null) browser.URL.revokeObjectURL(url);
        url = null;
        exports.delete(release);
      }
      try {
        url = browser.URL.createObjectURL(new browser.Blob([text], { type: mimeType }));
        exports.add(release);
        signal?.addEventListener('abort', release, { once: true });
        const link = document.createElement('a');
        link.href = url; link.download = filename;
        link.click();
        timer = browser.setTimeout(release, 1000);
        return result('completed');
      } catch { release(); return result('error'); }
    }
    async function copyText(text) {
      if (disposed) return result('cancelled');
      if (typeof text !== 'string' || text.length > 16 * 1024 * 1024) return result('error');
      if (!browser.navigator?.clipboard?.writeText) return result('unsupported');
      try { await browser.navigator.clipboard.writeText(text); return result(disposed ? 'cancelled' : 'completed'); }
      catch { return result('error'); }
    }
    return Object.freeze({
      version: 1, kind: 'browser',
      capabilities: Object.freeze({ openExternal: true, saveText: true, copyText: Boolean(browser.navigator?.clipboard?.writeText), pickDirectory: false }),
      reserveExternal, openExternal, saveText, copyText,
      async pickDirectory() { return result(disposed ? 'cancelled' : 'unsupported'); },
      dispose() {
        if (disposed) return;
        disposed = true;
        for (const cancel of [...pending]) cancel();
        for (const release of [...exports]) release();
      },
    });
  }
  window.SSDLDesktop = Object.freeze({ version: 1, createBrowser });
})();
