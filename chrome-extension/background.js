const DEFAULT_PORT = 8765;
const NAMES = new Set(['auth_token', 'ct0', 'twid']);

function validPort(value) {
  const text = String(value);
  return /^[0-9]{1,5}$/.test(text) && Number(text) >= 1 && Number(text) <= 65535 ? Number(text) : null;
}

function serviceOrigin(port) {
  return new URL(`http://127.0.0.1:${port}`).origin;
}

async function configuredPort() {
  const saved = await chrome.storage.local.get('toolPort');
  return validPort(saved.toolPort) || DEFAULT_PORT;
}

async function toolRequest(origin, path, body, token = '', timeout = 12000) {
  const response = await fetch(origin + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-SSDL-Extension': chrome.runtime.id, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeout),
  });
  let result;
  try { result = await response.json(); }
  catch { throw new Error('本機工具回應格式不正確，請確認連接埠及服務版本。'); }
  if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('本機工具回應格式不正確，請確認連接埠及服務版本。');
  if (!response.ok) throw new Error(typeof result.error === 'string' ? result.error : '本機工具拒絕連接，請重新按連接按鈕。');
  return result;
}

async function connectX(origin, token) {
  if (!token) token = (await toolRequest(origin, '/api/auth/x/prepare', {})).token;
  if (typeof token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
    throw new Error('本機工具回應格式不正確，請確認連接埠及服務版本。');
  }
  const groups = await Promise.all(['x.com', 'twitter.com'].map((domain) => chrome.cookies.getAll({ domain })));
  const now = Date.now() / 1000;
  const cookies = groups.flat().filter((item) =>
    ['x.com', 'twitter.com'].includes(item.domain.replace(/^\./, '')) && NAMES.has(item.name) && item.value &&
    (!item.expirationDate || item.expirationDate > now)
  ).map((item) => ({ domain: item.domain, name: item.name, value: item.value, expires: item.expirationDate || 0 }));
  if (!cookies.some((item) => item.name === 'auth_token')) {
    return { ok: false, message: '這個 Chrome 個人檔案尚未登入 X。請先在一般 Chrome 登入；若 X 顯示暫時限制，先停止登入嘗試並等待解除。' };
  }
  const result = await toolRequest(origin, '/api/auth/x/extension', { cookies }, token);
  if (result.connected !== true || typeof result.message !== 'string') {
    throw new Error('本機工具未確認連接成功，請更新下載工具的登入狀態。');
  }
  return { ok: true, message: result.message };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || message?.type !== 'SSDL_CONNECT_X') return;
  const fromPopup = sender.url === chrome.runtime.getURL('popup.html') && !sender.tab;
  let pageUrl;
  try { pageUrl = new URL(sender.url); } catch { return; }
  const fromTool = sender.tab && pageUrl.protocol === 'http:' && pageUrl.hostname === '127.0.0.1' &&
    !pageUrl.username && !pageUrl.password && pageUrl.pathname === '/chrome-connect';
  if (!fromPopup && !fromTool) return;
  const token = fromPopup ? '' : message.token;
  if (!fromPopup && (typeof token !== 'string' || (token && !/^[A-Za-z0-9_-]{43}$/.test(token)))) {
    sendResponse({ ok: false, message: '此連接已到期，請從下載工具重新按連接 Chrome。' });
    return;
  }
  (async () => {
    let port = await configuredPort();
    if (fromPopup && message.port !== undefined) {
      port = validPort(message.port);
      if (!port) throw new Error('本機連接埠必須是 1～65535 的整數。');
      // Only an explicit action in our popup can select a new destination.
      // A loopback page cannot silently redirect X cookies to another service.
      await chrome.storage.local.set({ toolPort: port });
    }
    const origin = serviceOrigin(port);
    if (fromTool && pageUrl.origin !== origin) {
      return { ok: false, message: `此頁使用連接埠 ${pageUrl.port || 80}，連接器目前使用 ${port}。請在 Chrome 連接器的「本機連接設定」輸入相同連接埠，再連接。` };
    }
    return connectX(origin, token);
  })().then(sendResponse).catch((error) => {
    sendResponse({ ok: false, message: error instanceof TypeError || error.name === 'TimeoutError'
      ? '無法連線到本機工具，請先啟動 Smart Social Downloader。'
      : error.message || '無法連接 X 登入狀態，請重新連接。' });
  });
  return true;
});

// OAuth codes are observed only for the top-level callback in the tab explicitly
// paired by the user. The verifier/refresh token never enters the extension.
const pixivKey = (tabId) => 'pixivAttempt:' + tabId;
const pixivCallbacks = new Set();
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || message?.type !== 'SSDL_CONNECT_PIXIV' || !sender.tab || sender.frameId !== 0) return;
  let page;
  try { page = new URL(sender.url); } catch { return; }
  if (page.protocol !== 'http:' || page.hostname !== '127.0.0.1' || page.username || page.password ||
      page.pathname !== '/pixiv-connect' || typeof message.ticket !== 'string' ||
      !/^[A-Za-z0-9_-]{43}$/.test(message.ticket)) return;
  (async () => {
    const origin = serviceOrigin(await configuredPort());
    if (page.origin !== origin) throw new Error('連接埠不一致，請在 Chrome 連接器的本機連接設定選擇相同連接埠。');
    const result = await toolRequest(origin, '/api/auth/pixiv/claim', { ticket: message.ticket });
    const destination = new URL(result.authorization_url);
    if (destination.origin !== 'https://app-api.pixiv.net' || destination.pathname !== '/web/v1/login' ||
        destination.username || destination.password) throw new Error('Pixiv 授權網址不正確。');
    const previous = await chrome.storage.session.get(null);
    const obsolete = Object.entries(previous).filter(([key, value]) => key.startsWith('pixivAttempt:') &&
      (value.origin === origin || value.expires <= Date.now())).map(([key]) => key);
    if (obsolete.length) await chrome.storage.session.remove(obsolete);
    await chrome.storage.session.set({ [pixivKey(sender.tab.id)]:
      { origin, ticket: message.ticket, expires: Date.now() + 600000 } });
    // Store before navigation so even an already signed-in callback is captured.
    await chrome.tabs.update(sender.tab.id, { url: destination.href });
    return { ok: true, message: '請在 Pixiv 頁面完成登入，工具會自動連接。' };
  })().then(sendResponse).catch(() => sendResponse({ ok: false,
    message: '無法啟動 Pixiv 連接。請確認工具已啟動、連接埠一致，再從工具重新連接。' }));
  return true;
});

chrome.webRequest.onBeforeRequest.addListener((details) => {
  if (details.tabId < 0 || details.type !== 'main_frame' || pixivCallbacks.has(details.tabId)) return;
  let url;
  try { url = new URL(details.url); } catch { return; }
  if (url.origin !== 'https://app-api.pixiv.net' || url.pathname !== '/web/v1/users/auth/pixiv/callback' ||
      url.username || url.password || url.searchParams.getAll('code').length !== 1 ||
      !/^[A-Za-z0-9._~-]{5,512}$/.test(url.searchParams.get('code') || '')) return;
  pixivCallbacks.add(details.tabId);
  (async () => {
    const key = pixivKey(details.tabId);
    const saved = (await chrome.storage.session.get(key))[key];
    if (!saved) return;
    await chrome.storage.session.remove(key); // A callback ticket is submitted once.
    if (saved.expires <= Date.now() || saved.origin !== serviceOrigin(await configuredPort())) return;
    // Replace the sensitive callback address; do not put codes in local URLs.
    await chrome.tabs.update(details.tabId, { url: saved.origin + '/pixiv-connect#result=working' });
    let connected = false;
    try {
      const result = await toolRequest(saved.origin, '/api/auth/pixiv/callback',
        { ticket: saved.ticket, code: url.searchParams.get('code') }, '', 35000);
      connected = result.pixiv_auth?.connected === true && result.pixiv_auth?.attempt_phase === 'connected';
    } finally {
      await chrome.tabs.update(details.tabId, { url: saved.origin + '/pixiv-connect#result=' +
        (connected ? 'connected' : 'failed') });
    }
  })().catch(() => { /* The tool's status page reports failure; never log codes/tickets. */ })
    .finally(() => pixivCallbacks.delete(details.tabId));
}, { urls: ['https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback*'], types: ['main_frame'] });
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.session.remove(pixivKey(tabId)).catch(() => {});
});
