const portInput = document.querySelector('#tool-port');
const validPort = () => /^[0-9]{1,5}$/.test(portInput.value) && Number(portInput.value) >= 1 && Number(portInput.value) <= 65535;
function showOrigin() {
  const link = document.querySelector('#open-tool');
  const origin = validPort() ? new URL(`http://127.0.0.1:${Number(portInput.value)}`).origin : '';
  document.querySelector('#target-origin').textContent = origin || '請輸入有效的本機連接埠';
  if (origin) link.href = origin + '/';
  else link.removeAttribute('href');
}
portInput.addEventListener('input', showOrigin);
document.querySelector('#connect').disabled = true;
Promise.resolve().then(() => chrome.storage.local.get('toolPort')).then((saved) => {
  if (saved.toolPort !== undefined) portInput.value = String(saved.toolPort);
  if (!validPort()) portInput.value = '8765';
  showOrigin();
  document.querySelector('#connect').disabled = false;
}).catch(() => {
  document.querySelector('#message').textContent = '請在 Chrome 擴充功能頁重新載入連接器。';
  document.querySelector('#connect').disabled = true;
});
showOrigin();
document.querySelector('#connect').addEventListener('click', async () => {
  if (!validPort()) { portInput.closest('details').open = true; portInput.reportValidity(); return; }
  const button = document.querySelector('#connect');
  const message = document.querySelector('#message');
  button.disabled = true;
  portInput.disabled = true;
  message.textContent = '正在連接…';
  try {
    const result = await chrome.runtime.sendMessage({ type: 'SSDL_CONNECT_X', port: Number(portInput.value) });
    message.textContent = result?.message || '無法連接，請重試。';
    message.style.color = result?.ok ? '#8ee1bf' : '#f3a2ae';
  } catch { message.textContent = '請重新整理擴充功能後重試。'; }
  finally { button.disabled = false; portInput.disabled = false; }
});
