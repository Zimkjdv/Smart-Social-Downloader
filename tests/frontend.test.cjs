/* Built-in Node tests: synthetic DOM, transport and Chrome APIs only. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = (name) => fs.readFileSync(path.join(root, name), 'utf8');
const environment = () => ({phase:'complete', busy:false, ready:true, checked_at:1, status:'ok', errors:0, warnings:0, port:8765, checks:[]});
const databases = (values = {}) => ({instance:'a'.repeat(32), revision:1, ready:true, busy:false, phase:'complete', operation:'refresh',
  checked_at:1, entries:[], total_bytes:0, reclaimable_bytes:0, backup_name:'', backup_bytes:0, error_code:'', result_code:'', ...values});
const state = (jobs = []) => ({
  jobs, counts: Object.fromEntries(['queued','active','completed','failed'].map(status => [status, jobs.filter(job => job.status === status).length])),
  paused:false, ready:true, download_dir:'fixture-downloads', x_cookie_file:'',
  x_auth:{connected:false, busy:false, phase:'idle'}, safe_queue:{enabled:true, phase:'idle'},
  rate_limit:{used:0, limit:40}, storage:{ready:true}, environment:environment(),
  persistence:{healthy:true, error:'', blocked:false}, worker:{alive:true, phase:'idle'}, no_progress_timeout:300,
});
const job = (status = 'completed', id = 'one') => ({id, status, url:'https://example.org/media', platform:'Web', created_at:1, title:'Fixture', files:['web/media.png']});
const json = (body, status = 200) => ({ok:status < 400, status, headers:{get:() => 'application/json'}, json:async () => body});
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function apiContext(fetch) {
  const context = vm.createContext({window:{}, fetch, AbortController, setTimeout, clearTimeout});
  vm.runInContext(source('static/api.js'), context);
  return context.window.SSDLApi;
}
test('API rejects non JSON, invalid JSON and missing state fields', async () => {
  for (const [response, code] of [
    [{...json({}), headers:{get:() => 'text/html'}}, 'invalid_response'],
    [{...json({}), json:async () => { throw new SyntaxError('fixture'); }}, 'invalid_json'],
    [json({}), 'invalid_schema'],
  ]) {
    const api = apiContext(async () => response);
    await assert.rejects(api.request('/api/state'), error => error.code === code);
  }
  assert.equal(apiContext(async () => json(state())).isState(state()), true);
});
test('API deadlines cover both header and body waits', async () => {
  for (const waitForBody of [false, true]) {
    const api = apiContext(async (url, options) => {
      const pending = () => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted')), {once:true}));
      return waitForBody ? {...json({}), json:pending} : pending();
    });
    await assert.rejects(api.request('/api/state', {timeoutMs:20}), error => error.code === 'timeout' && !error.uncertain);
  }
});
test('lost mutation response is uncertain and is never resent by API client', async () => {
  let writes = 0;
  const api = apiContext(async () => { writes++; throw new TypeError('lost response'); });
  await assert.rejects(api.request('/api/pause', {method:'POST'}), error => error.uncertain && error.code === 'network');
  assert.equal(writes, 1);
});

class Element {
  constructor(name = '') {
    this.name = name; this.textContent = ''; this.innerHTML = ''; this.value = ''; this.disabled = false;
    this.dataset = {}; this.style = {}; this.attrs = {}; this.events = new Map(); this.children = new Map();
    this.scrollTop = 0; this.scrollLeft = 0; this.isConnected = true; this.parentElement = this;
    const classes = new Set(['hidden']);
    this.classList = {add:(...v) => v.forEach(x => classes.add(x)), remove:(...v) => v.forEach(x => classes.delete(x)),
      contains:v => classes.has(v), toggle:(v, force) => { const next = force ?? !classes.has(v); next ? classes.add(v) : classes.delete(v); return next; }};
  }
  addEventListener(type, callback) { this.events.set(type, [...(this.events.get(type) || []), callback]); }
  async fire(type, data = {}) { for (const callback of this.events.get(type) || []) await callback({target:this, ...data}); }
  removeEventListener(type, callback) { this.events.set(type, (this.events.get(type) || []).filter(item => item !== callback)); }
  showModal() { this.open = true; }
  close() { this.open = false; }
  click() { return this.fire('click', {currentTarget:this}); }
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key] ?? null; }
  hasAttribute(key) { return Object.hasOwn(this.attrs, key); }
  removeAttribute(key) { delete this.attrs[key]; }
  querySelector(key) { if (!this.children.has(key)) this.children.set(key, new Element(key)); return this.children.get(key); }
  querySelectorAll() { return []; }
  contains() { return false; }
  matches() { return false; }
  closest() { return null; }
  append() {}
  replaceChildren() {}
  remove() {}
  focus() {}
  reportValidity() { return true; }
}
function appHarness() {
  const elements = new Map(), scheduled = new Map(), realTimers = new Set(), calls = [];
  const document = new Element();
  document.querySelector = key => { if (!elements.has(key)) elements.set(key, new Element(key)); return elements.get(key); };
  document.documentElement = {}; document.body = new Element(); document.title = 'Smart Social Downloader';
  document.createElement = () => new Element(); document.createTreeWalker = () => ({nextNode:() => false});
  document.dispatchEvent = event => document.fire(event.type);
  const store = new Map();
  let response = () => json(state()), nextTimer = 1;
  const context = vm.createContext({
    document, NodeFilter:{SHOW_TEXT:4}, CustomEvent:class {constructor(type) {this.type = type;}},
    localStorage:{getItem:key => store.get(key) ?? null, setItem:(key, value) => store.set(key, value)},
    AbortController, URL, Blob, Intl, console,
    fetch:async (url, options) => { calls.push({url, method:options.method || 'GET'}); return response(url, options); },
    setTimeout:(fn, delay) => { const id = nextTimer++; if (delay <= 50) { const timer = setTimeout(() => {realTimers.delete(timer); fn();}, delay); realTimers.add(timer); } else scheduled.set(id, {fn, delay}); return id; },
    clearTimeout:id => scheduled.delete(id),
    addEventListener:() => {}, scrollTo:() => {},
  });
  context.window = context;
  vm.runInContext(source('static/locales.js'), context);
  vm.runInContext(source('static/i18n.js'), context);
  vm.runInContext(source('static/api.js'), context);
  const request = context.SSDLApi.request;
  context.SSDLApi.request = (url, options) => request(url, {...options, timeoutMs:20});
  for (const name of ['ui_state.js', 'job_presentation.js', 'x_login.js', 'media_selection.js', 'controller_lifecycle.js', 'database_controller.js', 'diagnostics_controller.js', 'jobs_controller.js', 'settings_controller.js', 'pixiv_login.js', 'app.js']) {
    vm.runInContext(source('static/' + name), context);
  }
  return {context, elements, calls, scheduled, get:key => document.querySelector(key), document,
    evaluate:code => vm.runInContext(code, context), response:fn => {response = fn;},
    close:() => {vm.runInContext('disposeDashboard()', context); for (const timer of realTimers) clearTimeout(timer); scheduled.clear();}};
}

test('controller modules load without DOM access or application globals', () => {
  const context = vm.createContext({window:{}, document:new Proxy({}, {get() {throw new Error('unexpected DOM access');}})});
  for (const name of ['controller_lifecycle.js','settings_controller.js','jobs_controller.js','database_controller.js','diagnostics_controller.js']) {
    vm.runInContext(source('static/' + name), context);
  }
  assert.equal(typeof context.window.SSDLSettingsController.create, 'function');
  assert.equal(typeof context.window.SSDLJobsController.create, 'function');
  assert.equal(typeof context.window.SSDLDiagnosticsController.create, 'function');
});

test('Pixiv author titles include display names from metadata and matching historical folders', async () => {
  const app = appHarness();
  try {
    const profile = {mode:'pixiv_profile', account:'82728784', title:'Pixiv · 82728784', files:[]};
    const title = values => app.evaluate('jobTitle(' + JSON.stringify({...profile, ...values}) + ')');
    assert.equal(title({}), 'Pixiv 作者 · 82728784');
    assert.equal(title({title:'Pixiv · Hoshirapu(82728784)'}), 'Pixiv 作者 · Hoshirapu(82728784)');
    for (const filename of ['pixiv/Hoshirapu(82728784)/1_p0.png', 'pixiv\\Hoshirapu(82728784)\\1_p0.png']) {
      assert.equal(title({files:[filename]}), 'Pixiv 作者 · Hoshirapu(82728784)');
    }
    assert.equal(title({files:['pixiv/Another author(123)/1_p0.png']}), 'Pixiv 作者 · 82728784');
    assert.equal(title({files:['pixiv/82728784/1_p0.png']}), 'Pixiv 作者 · 82728784');
    await app.get('#language-toggle').fire('click');
    assert.equal(title({title:'Pixiv · Hoshirapu(82728784)'}), 'Pixiv author · Hoshirapu(82728784)');
  } finally {app.close();}
});

test('capacity health renders size, warning, blocked save and English messages', async () => {
  const app = appHarness();
  try {
    await pause(10);
    app.context.snapshot = state();
    app.context.snapshot.persistence = {healthy:true, blocked:false, error:'', max_bytes:67108864,
      saved_bytes:60000000, capacity_warning:true};
    app.evaluate('render(snapshot)');
    assert.match(app.get('#persistence-capacity').textContent, /已保存紀錄/);
    assert.match(app.get('#persistence-capacity').textContent, /64 MiB/);
    assert.match(app.get('#persistence-capacity').textContent, /接近或超過/);
    assert.equal(app.get('#engine-status').classList.contains('hidden'), false);
    assert.equal(app.get('#state-save').disabled, false);
    await app.get('#language-toggle').fire('click');
    assert.match(app.get('#persistence-capacity').textContent, /Saved history:/);
    assert.match(app.get('#persistence-capacity').textContent, /near or above/);
    assert.match(app.get('#engine-subtitle').textContent, /Back it up/);
    assert.match(app.context.I18n.message(app.context.SSDLMessages['ui.state_too_large']['zh-Hant']), /64 MiB save limit/);
    assert.match(app.context.I18n.message(app.context.SSDLMessages['ui.worker_message_too_large']['zh-Hant']), /queue will continue/);
    app.context.snapshot.persistence = {healthy:false, blocked:true, error:app.context.SSDLMessages['ui.state_read_too_large']['zh-Hant'],
      max_bytes:67108864, saved_bytes:null, capacity_warning:true};
    app.evaluate('render(snapshot)');
    assert.equal(app.get('#state-save').disabled, true);
    assert.match(app.get('#persistence-summary').textContent, /64 MiB read limit/);
    assert.match(app.get('#persistence-capacity').textContent, /size not yet available/);
    app.context.snapshot.persistence = {healthy:true, blocked:false, error:''};
    app.evaluate('render(snapshot)');
    assert.equal(app.get('#persistence-capacity').classList.contains('hidden'), true);
    assert.equal(app.get('#state-save').disabled, false);
  } finally {app.close();}
});

test('API validates optional capacity byte counts and warning flags', () => {
  const api = apiContext(async () => json(state()));
  for (const capacity of [{max_bytes:-1}, {saved_bytes:'large'}, {attempted_bytes:-1},
    {capacity_warning:1}, {attempted_bytes_exact:'false'}]) {
    const value = state(); value.persistence = {...value.persistence, ...capacity};
    assert.equal(api.isState(value), false);
  }
  const value = state(); value.persistence = {...value.persistence, max_bytes:67108864,
    saved_bytes:null, attempted_bytes:67108865, attempted_bytes_exact:false, capacity_warning:true};
  assert.equal(api.isState(value), true);
});

test('database maintenance validates contracts and requires confirmation before a single compact request', async () => {
  const app = appHarness();
  try {
    await pause(10);
    const next = state(); next.paused = true; next.databases = databases();
    app.context.snapshot = next; app.evaluate('render(snapshot)');
    await app.get('#database-compact').fire('click');
    assert.equal(app.get('#database-confirm-dialog').open, true);
    await app.get('#database-confirm-cancel').fire('click');
    assert.equal(app.get('#database-confirm-dialog').open, false);
    assert.equal(app.calls.filter(call => call.url === '/api/databases').length, 0);
    await app.get('#database-compact').fire('click');
    let finish;
    app.response(() => new Promise(resolve => {finish = resolve;}));
    const first = app.get('#database-confirm-submit').fire('click');
    await app.get('#database-confirm-submit').fire('click');
    assert.equal(app.calls.filter(call => call.url === '/api/databases' && call.method === 'POST').length, 1);
    finish(json(databases({revision:2, operation:'compact', backup_name:'backup-20261015-000000-aaaaaaaaaaaa', backup_bytes:4096})));
    await first;
    assert.match(app.get('#database-backup-result').textContent, /backup-20261015/);
    await app.get('#language-toggle').fire('click');
    assert.match(app.get('#database-backup-result').textContent, /Latest backup/);
    const api = apiContext(async () => json({}));
    assert.equal(api.isState(next), true);
    for (const invalid of [databases({total_bytes:-1}), databases({entries:[{id:'foreign'}]}), databases({backup_name:'../outside'})]) {
      assert.equal(api.isState({...next, databases:invalid}), false);
    }
  } finally {app.close();}
});

test('database UI retains newer maintenance status and blocks writes during active downloads', async () => {
  const app = appHarness();
  try {
    await pause(10);
    const next = state(); next.databases = databases({revision:2, busy:true, phase:'running', operation:'backup'});
    app.context.snapshot = next; app.evaluate('render(snapshot)');
    assert.equal(app.get('#database-backup').disabled, true);
    assert.match(app.get('#database-summary').textContent, /正在處理/);
    next.databases = databases({revision:1}); app.evaluate('render(snapshot)');
    assert.match(app.get('#database-summary').textContent, /正在處理/);
    next.databases = databases({revision:3}); next.paused = true; next.counts.active = 1;
    app.evaluate('render(snapshot)');
    assert.equal(app.get('#database-compact').disabled, true);
    next.counts.active = 0; app.evaluate('render(snapshot)');
    assert.equal(app.get('#database-compact').disabled, false);
    next.databases = databases({revision:4, phase:'partial', error_code:'database_invalid'});
    app.evaluate('render(snapshot)');
    assert.match(app.get('#engine-title').textContent, /資料庫需要注意/);
    assert.equal(app.get('#engine-status').classList.contains('hidden'), false);
  } finally {app.close();}
});

test('disposed database controller discards late maintenance responses', async () => {
  const app = appHarness();
  try {
    await pause(10);
    let finish;
    app.response(() => new Promise(resolve => {finish = resolve;}));
    const reading = app.get('#database-refresh').fire('click');
    app.evaluate('diagnosticsController.dispose()');
    const before = app.get('#database-summary').textContent;
    finish(json(databases({error_code:'database_invalid', phase:'partial'})));
    await reading;
    assert.equal(app.get('#database-summary').textContent, before);
  } finally {app.close();}
});

test('controller lifecycle initializes once and releases listeners timers and queued callbacks', async () => {
  const context = vm.createContext({window:{}});
  vm.runInContext(source('static/controller_lifecycle.js'), context);
  const timers = new Map(), target = new Element();
  let calls = 0, next = 0, cleanup = 0;
  const scope = context.window.SSDLControllerLifecycle.create({setTimeout:(fn) => {timers.set(++next, fn); return next;}, clearTimeout:id => timers.delete(id)});
  scope.listen(target, 'click', () => calls++);
  await target.fire('click'); assert.equal(calls, 0);
  scope.init(); scope.init();
  await target.fire('click'); assert.equal(calls, 1);
  scope.defer(() => calls++, 250);
  const delayed = [...timers.values()][0];
  scope.onDispose(() => cleanup++);
  scope.dispose(); scope.dispose();
  delayed(); await target.fire('click');
  assert.equal(calls, 1); assert.equal(cleanup, 1); assert.equal(timers.size, 0);
  assert.equal(target.events.get('click').length, 0);
  assert.throws(() => scope.init(), /disposed/);
});

test('controller initialization never duplicates writes and settings save rejects concurrent submissions', async () => {
  const app = appHarness();
  try {
    await pause(10);
    app.evaluate('jobsController.init(); settingsController.init(); diagnosticsController.init();');
    assert.equal(app.get('#top-pause').events.get('click').length, 1);
    assert.equal(app.get('#settings-save').events.get('click').length, 1);
    assert.equal(app.get('#environment-refresh').events.get('click').length, 1);
    let finish;
    app.response(() => new Promise(resolve => {finish = resolve;}));
    const first = app.get('#settings-save').fire('click');
    await app.get('#settings-save').fire('click');
    assert.equal(app.calls.filter(call => call.url.startsWith('/api/settings')).length, 1);
    finish(json(state())); await first;
    assert.equal(app.get('#settings-save').disabled, false);
  } finally {app.close();}
});

test('closing settings during its load cannot reopen the dialog when the response arrives', async () => {
  const app = appHarness();
  try {
    await pause(10);
    let finish;
    app.response(() => new Promise(resolve => {finish = resolve;}));
    const opening = app.evaluate('openSettings()');
    app.evaluate('settingsController.close()');
    finish(json(state()));
    assert.equal(await opening, false);
    assert.equal(app.get('#settings-modal').classList.contains('hidden'), true);
    assert.equal(app.get('#settings-open').disabled, false);
  } finally {app.close();}
});

test('old save auto-close cannot close a freshly reopened settings draft', async () => {
  const app = appHarness();
  try {
    await pause(10); await app.evaluate('openSettings()');
    await app.get('#settings-save').fire('click');
    const delayed = [...app.scheduled.values()].find(timer => timer.delay === 550).fn;
    app.evaluate('settingsController.close()'); await app.evaluate('openSettings()');
    app.get('#download-dir').value = 'new unsaved draft'; delayed();
    assert.equal(app.get('#settings-modal').classList.contains('hidden'), false);
    assert.equal(app.get('#download-dir').value, 'new unsaved draft');
  } finally {app.close();}
});

test('disposed diagnostics ignores a late response and job disposal cancels search debounce', async () => {
  const app = appHarness();
  try {
    await pause(10);
    const oldSummary = app.get('#environment-summary').textContent;
    let finish;
    app.response(() => new Promise(resolve => {finish = resolve;}));
    const loading = app.evaluate('diagnosticsController.load()');
    app.evaluate('diagnosticsController.dispose()');
    finish(json({...environment(), checked_at:99, status:'warning', warnings:1})); await loading;
    assert.equal(app.get('#environment-summary').textContent, oldSummary);
    app.get('#search-input').value = 'fixture'; await app.get('#search-input').fire('input');
    const delayed = [...app.scheduled.values()].find(timer => timer.delay === 250).fn;
    const before = app.calls.length;
    app.evaluate('jobsController.dispose()'); delayed();
    await app.get('#top-pause').fire('click');
    assert.equal(app.calls.length, before);
    assert.equal([...app.scheduled.values()].some(timer => timer.delay === 250), false);
  } finally {app.close();}
});

test('diagnostic export releases object URLs when its controller is disposed', async () => {
  const app = appHarness();
  try {
    await pause(10);
    const revoked = [];
    app.context.URL = class extends URL {static createObjectURL() {return 'blob:synthetic-report';} static revokeObjectURL(url) {revoked.push(url);}};
    app.response(() => json({format_version:1, created_at:1, counts:{}, jobs:[], environment:environment()}));
    await app.get('#diagnostics-export').fire('click');
    app.evaluate('diagnosticsController.dispose()');
    assert.deepEqual(revoked, ['blob:synthetic-report']);
    assert.equal([...app.scheduled.values()].some(timer => timer.delay === 1000), false);
  } finally {app.close();}
});

test('closing job details during its read discards the late dialog response', async () => {
  const app = appHarness();
  try {
    await pause(10);
    app.context.snapshot = state([job('failed')]); app.evaluate('render(snapshot)');
    let finish;
    app.response(() => new Promise(resolve => {finish = resolve;}));
    const button = new Element(); button.attrs['data-detail'] = 'one';
    button.closest = selector => selector === 'button' ? button : {dataset:{jobId:'one'}};
    const reading = app.get('#job-rows').fire('click', {target:button});
    app.evaluate('jobsController.closeError()');
    finish(json({...job('failed'), warnings:[], error:'synthetic failure', error_detail:'synthetic detail'}));
    await reading;
    assert.equal(app.get('#error-modal').classList.contains('hidden'), true);
    assert.equal(button.disabled, false);
    assert.equal(app.evaluate('pendingJobActions.size'), 0);
  } finally {app.close();}
});
test('DOM retains last valid jobs offline, restores refresh control and polling, then reconnects', async () => {
  const app = appHarness();
  try {
    await pause(10);
    app.response(() => json(state([job()])));
    await app.evaluate('refresh()');
    const markup = app.get('#job-rows').innerHTML;
    app.response(() => {throw new TypeError('fixture offline');});
    await app.evaluate('refresh()');
    assert.equal(app.get('#job-rows').innerHTML, markup);
    assert.match(app.get('#queue-status-copy').textContent, /已保留上次成功資料/);
    assert.equal(app.get('#status-refresh').disabled, false);
    assert.ok([...app.scheduled.values()].some(timer => timer.delay === 30000));
    app.response(() => json(state([job('active')])));
    await app.evaluate('refresh()');
    assert.equal(app.evaluate('connectionOffline'), false);
    assert.match(app.get('#job-rows').innerHTML, /data-stop="one"/);
    assert.ok([...app.scheduled.values()].some(timer => timer.delay === 2000));
  } finally {app.close();}
});
test('older polling and previous-service snapshots cannot overwrite a newer mutation', async () => {
  const app = appHarness();
  try {
    await pause(10);
    const first = 'a'.repeat(32), second = 'b'.repeat(32);
    let releaseRead;
    app.response((url, options) => options.method === 'POST'
      ? json({...state(), paused:true, state_instance:first, state_sequence:2})
      : new Promise(resolve => { releaseRead = resolve; }));
    const pending = app.evaluate('refresh()');
    await app.get('#top-pause').fire('click');
    assert.equal(app.evaluate('state.paused'), true);
    releaseRead(json({...state(), state_instance:first, state_sequence:1}));
    await pending;
    assert.equal(app.evaluate('state.paused'), true);
    app.context.newService = {...state(), state_instance:second, state_sequence:1};
    app.evaluate('render(newService)');
    assert.equal(app.evaluate('state.paused'), false);
    app.context.retiredService = {...state(), paused:true, state_instance:first, state_sequence:3};
    app.evaluate('render(retiredService)');
    assert.equal(app.evaluate('state.paused'), false);
  } finally {app.close();}
});

test('snapshot ordering fields are a validated optional pair', () => {
  const api = apiContext(async () => json(state()));
  assert.equal(api.isState({...state(), state_instance:'a'.repeat(32), state_sequence:1}), true);
  for (const fields of [{state_instance:'a'.repeat(32)}, {state_sequence:1},
    {state_instance:'invalid', state_sequence:1}, {state_instance:'a'.repeat(32), state_sequence:-1},
    {state_instance:'a'.repeat(32), state_sequence:1.5}]) {
    assert.equal(api.isState({...state(), ...fields}), false);
  }
});
test('DOM controls recover after uncertain write; reconciliation reads do not repeat mutation', async () => {
  const app = appHarness();
  try {
    await pause(10);
    app.response(url => { if (url === '/api/pause') throw new TypeError('response lost'); return json(state()); });
    await app.get('#top-pause').fire('click');
    await pause(15);
    assert.equal(app.calls.filter(call => call.method === 'POST' && call.url === '/api/pause').length, 1);
    assert.ok(app.calls.filter(call => call.url === '/api/state').length >= 2);
    assert.equal(app.get('#top-pause').disabled, false);
  } finally {app.close();}
});
test('DOM settings draft, page and scroll survive polling and English language switch', async () => {
  const app = appHarness();
  try {
    await pause(10);
    const jobs = Array.from({length:25}, (_, i) => job('completed', String(i)));
    app.response(() => json(state(jobs)));
    await app.evaluate('refresh();');
    app.evaluate('state.page = 2; renderJobs();');
    app.get('#jobs-table-scroll').scrollTop = 45;
    await app.evaluate('openSettings()');
    app.get('#download-dir').value = 'unsaved draft';
    await app.evaluate('refresh()');
    await app.evaluate('openSettings()');
    assert.equal(app.get('#download-dir').value, 'unsaved draft');
    assert.equal(app.evaluate('state.page'), 2);
    assert.equal(app.get('#jobs-table-scroll').scrollTop, 45);
    await app.get('#language-toggle').fire('click');
    assert.equal(app.context.I18n.language, 'en');
    assert.equal(app.get('#queue-status-title').textContent, 'Queue idle');
    assert.equal(app.get('#download-dir').value, 'unsaved draft');
  } finally {app.close();}
});

function extensionHarness(port = 8765, failPreflight = false) {
  let cookieReads = 0; const requests = [], listeners = [], session = {};
  const id = 'fixture-extension', popup = 'chrome-extension://' + id + '/popup.html';
  const chrome = {
    runtime:{id, getURL:file => 'chrome-extension://' + id + '/' + file, onMessage:{addListener:fn => {listeners.push(fn);}}},
    storage:{local:{get:async () => ({toolPort:port}), set:async data => {port = data.toolPort;}},
      session:{get:async key => key === null ? {...session} : {[key]:session[key]},
        set:async values => {Object.assign(session, values);},
        remove:async keys => {for (const key of Array.isArray(keys) ? keys : [keys]) delete session[key];}}},
    cookies:{getAll:async ({domain}) => {cookieReads++; return [{domain, name:'auth_token', value:'SYNTHETIC_COOKIE'}];}},
    webRequest:{onBeforeRequest:{addListener:() => {}}},
    tabs:{update:async () => ({}), onRemoved:{addListener:() => {}}},
  };
  const context = vm.createContext({chrome, URL, AbortSignal, Date,
    fetch:async (url, options) => {
      requests.push({url, body:options.body});
      return failPreflight ? json({error:'Windows storage unavailable'}, 503) :
        json(url.endsWith('/prepare') ? {token:'A'.repeat(43)} : {connected:true, message:'Fixture connected'});
    }});
  vm.runInContext(source('chrome-extension/background.js'), context);
  return {requests, cookieReads:() => cookieReads,
    send:(message, sender) => new Promise(resolve => {
      const pending = listeners.map(listener => listener(message, {id, ...sender}, resolve));
      if (!pending.includes(true)) resolve(undefined);
    }),
    popup, id};
}
test('Chrome connector rejects mismatched or foreign sources before reading any Cookie', async () => {
  const extension = extensionHarness();
  const mismatch = await extension.send({type:'SSDL_CONNECT_X', token:'A'.repeat(43)}, {tab:{}, url:'http://127.0.0.1:8877/chrome-connect'});
  assert.equal(mismatch.ok, false);
  assert.equal(extension.cookieReads(), 0);
  assert.equal(extension.requests.length, 0);
  await extension.send({type:'SSDL_CONNECT_X'}, {tab:{}, url:'https://evil.example/chrome-connect'});
  assert.equal(extension.cookieReads(), 0);
});
test('Chrome connector popup selects custom loopback port and preflight runs before Cookie access', async () => {
  const extension = extensionHarness();
  const result = await extension.send({type:'SSDL_CONNECT_X', port:8877}, {url:extension.popup});
  assert.equal(result.ok, true);
  assert.equal(extension.cookieReads(), 2);
  assert.deepEqual(extension.requests.map(request => request.url), ['http://127.0.0.1:8877/api/auth/x/prepare', 'http://127.0.0.1:8877/api/auth/x/extension']);
  assert.equal(extension.requests[0].body, '{}');
  const failure = extensionHarness(8765, true);
  const rejected = await failure.send({type:'SSDL_CONNECT_X'}, {url:failure.popup});
  assert.equal(rejected.ok, false);
  assert.equal(failure.cookieReads(), 0);
});
