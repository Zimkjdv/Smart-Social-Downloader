/* Stable job rows; patch only cells whose rendered content has changed. */
(() => {
  const tables = new WeakMap();
  function reconcile(rows, entries) {
    let saved = tables.get(rows);
    if (!saved) { saved = new Map(); tables.set(rows, saved); }
    const retained = new Set(entries.map((item) => item.id));
    for (const [id, entry] of saved) {
      if (!retained.has(id)) { entry.node.remove(); saved.delete(id); }
    }
    entries.forEach(({ id, markup }, position) => {
      let entry = saved.get(id);
      if (!entry || entry.markup !== markup) {
        const template = document.createElement('template');
        template.innerHTML = markup.trim();
        const next = template.content.firstElementChild;
        const cells = [...next.children].map((cell) => cell.innerHTML);
        if (!entry) {
          entry = { node: next, cells, markup };
          saved.set(id, entry);
        } else {
          cells.forEach((html, index) => {
            if (entry.cells[index] !== html) entry.node.children[index].replaceWith(next.children[index].cloneNode(true));
          });
          entry.cells = cells;
          entry.markup = markup;
        }
      }
      const current = rows.children[position];
      if (current !== entry.node) rows.insertBefore(entry.node, current || null);
    });
  }
  window.SSDLJobRows = { reconcile };
})();
