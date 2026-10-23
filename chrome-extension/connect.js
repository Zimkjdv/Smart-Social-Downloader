if (location.protocol === 'http:' && location.hostname === '127.0.0.1' && location.pathname === '/chrome-connect') {
  let busy = false;
  const report = (result) => document.dispatchEvent(new CustomEvent('ssdl-extension-result', { detail: JSON.stringify(result) }));
  async function connect() {
    if (busy) return;
    const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
    busy = true;
    report({ busy: true, message: '正在連接這個 Chrome 個人檔案的 X 登入狀態…' });
    try {
      const result = await chrome.runtime.sendMessage({ type: 'SSDL_CONNECT_X', token });
      if (!result || typeof result.message !== 'string' || typeof result.ok !== 'boolean') throw new Error('Invalid connector response');
      report(result);
    }
    catch { report({ ok: false, message: 'Chrome 連接器已更新，請重新整理這個頁面。' }); }
    finally { busy = false; }
  }
  document.addEventListener('ssdl-connect-request', connect);
  document.documentElement.dataset.ssdlExtension = 'ready';
  document.documentElement.dataset.ssdlExtensionVersion = chrome.runtime.getManifest().version;
  document.dispatchEvent(new CustomEvent('ssdl-extension-ready'));
  const pending = new URLSearchParams(location.hash.slice(1));
  if (pending.get('connect') === '1' && /^[A-Za-z0-9_-]{43}$/.test(pending.get('token') || '')) connect();
}

if (location.protocol === 'http:' && location.hostname === '127.0.0.1' && location.pathname === '/pixiv-connect') {
  let busy = false;
  async function connectPixiv() {
    if (busy) return;
    const ticket = new URLSearchParams(location.hash.slice(1)).get('ticket') || '';
    if (!/^[A-Za-z0-9_-]{43}$/.test(ticket)) return;
    busy = true;
    const report = (result) => document.dispatchEvent(new CustomEvent('ssdl-pixiv-result', { detail: JSON.stringify(result) }));
    try {
      const result = await chrome.runtime.sendMessage({ type: 'SSDL_CONNECT_PIXIV', ticket });
      report(result || { ok: false });
    } catch { report({ ok: false }); }
    finally { busy = false; }
  }
  document.addEventListener('ssdl-pixiv-connect', connectPixiv);
  document.documentElement.dataset.ssdlPixivExtension = 'ready';
  document.dispatchEvent(new CustomEvent('ssdl-pixiv-ready'));
}
