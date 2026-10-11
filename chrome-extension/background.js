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

async function toolRequest(origin, path, body, token = '') {
  const response = await fetch(origin + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-SSDL-Extension': chrome.runtime.id, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12000),
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
