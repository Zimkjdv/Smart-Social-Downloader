/* One focus boundary for layered custom modals and native dialogs. */
(() => {
  const layers = [...document.querySelectorAll('.modal-backdrop[role="dialog"], dialog')];
  const opened = [];
  const returnFocus = new WeakMap();
  const originalInert = new WeakMap();
  const outsideFocus = new WeakMap(layers.map((layer) => [layer, document.activeElement]));
  const visible = (layer) => layer.tagName === 'DIALOG' ? layer.open : !layer.classList.contains('hidden');
  const focusables = (layer) => [...layer.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]')]
    .filter((node) => !node.closest('[hidden], .hidden') && node.getClientRects().length);
  function sync() {
    let closedFocus = null;
    for (const layer of layers) {
      const index = opened.indexOf(layer);
      if (visible(layer) && index < 0) { opened.push(layer); returnFocus.set(layer, outsideFocus.get(layer)); }
      else if (!visible(layer) && index >= 0) { opened.splice(index, 1); closedFocus = returnFocus.get(layer); }
    }
    const active = opened.at(-1);
    for (const child of document.body.children) {
      if (child.tagName === 'SCRIPT' || child.classList.contains('toast-region')) continue;
      if (!originalInert.has(child)) originalInert.set(child, child.inert);
      const next = active ? !child.contains(active) : originalInert.get(child);
      if (child.inert !== next) child.inert = next;
    }
    if (active && closedFocus?.isConnected && active.contains(closedFocus) && !closedFocus.disabled) {
      closedFocus.focus({ preventScroll: true });
    } else if (active && !active.contains(document.activeElement)) {
      (focusables(active)[0] || active).focus({ preventScroll: true });
    } else if (!active && closedFocus) {
      const target = closedFocus.isConnected && !closedFocus.disabled ? closedFocus : document.querySelector('#settings-open, #status-refresh');
      target?.focus({ preventScroll: true });
    }
  }
  document.addEventListener('focusin', (event) => {
    for (const layer of layers) if (!layer.contains(event.target)) outsideFocus.set(layer, event.target);
  });
  document.addEventListener('keydown', (event) => {
    const active = opened.at(-1);
    if (!active) return;
    if (event.key === 'Escape') {
      const close = active.querySelector('.close-modal');
      event.preventDefault(); event.stopImmediatePropagation();
      if (close && !close.disabled) close.click();
    } else if (event.key === 'Tab') {
      const controls = focusables(active);
      if (!controls.length) { event.preventDefault(); return; }
      const index = controls.indexOf(document.activeElement);
      if (event.shiftKey && index <= 0 || !event.shiftKey && (index < 0 || index === controls.length - 1)) {
        event.preventDefault(); event.stopImmediatePropagation();
        controls[event.shiftKey ? controls.length - 1 : 0].focus();
      }
    }
  }, true);
  const observer = new MutationObserver(sync);
  for (const layer of layers) observer.observe(layer, { attributes: true, attributeFilter: ['class', 'open'] });
  sync();
})();
