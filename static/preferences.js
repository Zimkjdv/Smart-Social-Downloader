/* Persist presentation choices over HTTP so changing desktop hosts keeps them. */
(() => {
  'use strict';
  function create({ api, read, apply, onError }) {
    let epoch = 0, disposed = false, hydrating = false, writes = Promise.resolve();
    const controller = new AbortController();
    function changed() {
      if (disposed || hydrating) return writes;
      epoch += 1;
      const value = read();
      writes = writes.catch(() => {}).then(async () => {
        if (disposed) return;
        try { await api('/api/ui-preferences', { method: 'POST', body: JSON.stringify(value), signal: controller.signal }); }
        catch (error) { if (!disposed) onError(error); }
      });
      return writes;
    }
    async function start() {
      const initial = epoch;
      try {
        const value = await api('/api/ui-preferences', { signal: controller.signal });
        if (disposed || epoch !== initial) return;
        if (value.preferences === null) { await changed(); return; }
        hydrating = true;
        try { apply(value.preferences); } finally { hydrating = false; }
      } catch (error) { if (!disposed) onError(error); }
    }
    return { start, changed, dispose() { disposed = true; controller.abort(); } };
  }
  window.SSDLPreferences = { create };
})();
