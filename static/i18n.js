/* UI copy only. Media titles, paths and raw engine diagnostics stay unchanged. */
(() => {
  const storageKey = 'ssdl-language';
  const catalog = window.SSDLMessages;
  const english = Object.fromEntries(Object.values(catalog).map((item) => [item['zh-Hant'], item.en]));

  let language = 'zh-Hant';
  try { if (localStorage.getItem(storageKey) === 'en') language = 'en'; } catch { /* Storage can be disabled. */ }
  const format = (copy, params) => copy.replace(/\{(\w+)\}/g, (token, name) => String(params[name] ?? token));
  const t = (key, params = {}) => format(catalog[key]?.[language] ?? (language === 'en' ? (english[key] ?? key) : key), params);
  const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const numericParams = new Set(['count', 'seconds', 'minutes', 'used', 'limit', 'added', 'reused', 'pending', 'rejected', 'status', 'posts', 'files', 'skipped', 'done', 'remaining', 'start', 'end', 'total', 'page', 'height']);
  const templates = Object.entries(english).filter(([source]) => /\{\w+\}/.test(source))
    .sort(([a], [b]) => b.replace(/\{\w+\}/g, '').length - a.replace(/\{\w+\}/g, '').length)
    .map(([source, target]) => {
    const names = [];
    const pieces = source.split(/(\{\w+\})/g).map((piece) => {
      if (/^\{\w+\}$/.test(piece)) {
        const name = piece.slice(1, -1);
        names.push(name);
        return numericParams.has(name) ? '([0-9]+(?:\\.[0-9]+)?|—)' : name === 'resolution' ? '([0-9]+×[0-9]+|[0-9]+p)' : '([\\s\\S]+?)';
      }
      return escapeRegex(piece);
    });
    return { pattern: new RegExp(`^${pieces.join('')}$`), names, target };
  });
  function message(value) {
    const source = String(value ?? '');
    if (Object.hasOwn(catalog, source)) return t(source);
    if (language !== 'en') return source;
    if (Object.hasOwn(english, source)) return english[source];
    for (const { pattern, names, target } of templates) {
      const match = source.match(pattern);
      if (match) return format(target, Object.fromEntries(names.map((name, index) => {
        const value = match[index + 1];
        return [name, name === 'detail' && value !== source ? message(value) : value];
      })));
    }
    return source;
  }

  // Capture only the original static UI, before job data is rendered into the page.
  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement.closest('script, style, pre')) continue;
    const source = node.textContent.trim();
    const key = node.parentElement.dataset.i18nKey;
    if (key && Object.hasOwn(catalog, key) || Object.hasOwn(english, source)) texts.push({ node, original: node.textContent, source, key: key || source });
  }
  const attributes = [];
  for (const element of document.querySelectorAll('[title], [aria-label], [placeholder]')) {
    for (const name of ['title', 'aria-label', 'placeholder']) {
      const source = element.getAttribute(name);
      const key = element.getAttribute('data-i18n-' + name);
      if (key && Object.hasOwn(catalog, key) || source && Object.hasOwn(english, source)) attributes.push({ element, name, key: key || source });
    }
  }
  const originalTitle = document.title;
  const liveMessages = new Map();
  function text(element, source) {
    for (const node of liveMessages.keys()) { if (!node.isConnected) liveMessages.delete(node); }
    liveMessages.set(element, String(source ?? ''));
    element.textContent = message(source);
  }
  function apply() {
    document.documentElement.lang = language;
    document.title = message(originalTitle);
    for (const { node, original, source, key } of texts) {
      if (node.isConnected) node.textContent = original.replace(source, t(key));
    }
    for (const { element, name, key } of attributes) element.setAttribute(name, t(key));
    for (const [element, source] of liveMessages) {
      if (element.isConnected) element.textContent = message(source);
      else liveMessages.delete(element);
    }
    const button = document.querySelector('#language-toggle');
    if (button) {
      button.querySelector('.language-label').textContent = language === 'en' ? '繁中' : 'EN';
      button.title = language === 'en' ? 'Switch to Traditional Chinese' : '切換為英文';
      button.setAttribute('aria-label', button.title);
    }
  }
  function change(next, persist = true) {
    if (!['en', 'zh-Hant'].includes(next) || next === language) return;
    language = next;
    if (persist) { try { localStorage.setItem(storageKey, language); } catch { /* Keep the in-page selection. */ } }
    apply();
    document.dispatchEvent(new CustomEvent('ssdl-language-changed', { detail: { language } }));
  }
  window.I18n = { t, message, text, get language() { return language; }, get locale() { return language === 'en' ? 'en-US' : 'zh-TW'; } };
  document.querySelector('#language-toggle')?.addEventListener('click', () => change(language === 'en' ? 'zh-Hant' : 'en'));
  window.addEventListener('storage', (event) => { if (event.key === storageKey) change(event.newValue === 'en' ? 'en' : 'zh-Hant', false); });
  apply();
})();
