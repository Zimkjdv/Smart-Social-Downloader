/* Controller-owned listeners and timers; loading this file does not touch the DOM. */
(() => {
  'use strict';
  function create(browser) {
    let started = false;
    let disposed = false;
    const listeners = [];
    const timers = new Set();
    const cleanups = [];
    const scope = {
      get active() { return started && !disposed; },
      effect(callback) { return (...args) => { if (scope.active) return callback(...args); }; },
      listen(target, type, callback, options) {
        const listener = function (...args) {
          if (scope.active) return callback.apply(this, args);
        };
        listeners.push({ target, type, listener, options });
        if (scope.active) target.addEventListener(type, listener, options);
      },
      init() {
        if (disposed) throw new Error('Cannot initialize a disposed controller.');
        if (started) return;
        started = true;
        for (const item of listeners) item.target.addEventListener(item.type, item.listener, item.options);
      },
      defer(callback, delay) {
        if (!scope.active) return null;
        const id = browser.setTimeout(() => {
          timers.delete(id);
          if (scope.active) callback();
        }, delay);
        timers.add(id);
        return id;
      },
      cancel(id) { browser.clearTimeout(id); timers.delete(id); },
      onDispose(callback) { cleanups.push(callback); },
      dispose() {
        if (disposed) return;
        disposed = true;
        for (const item of listeners) item.target.removeEventListener(item.type, item.listener, item.options);
        for (const id of timers) browser.clearTimeout(id);
        for (const cleanup of cleanups) cleanup();
        listeners.length = 0; timers.clear(); cleanups.length = 0;
      },
    };
    return scope;
  }
  window.SSDLControllerLifecycle = Object.freeze({ create });
})();
