/* Built-in Node tests: synthetic DOM, transport and Chrome APIs only. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = (name) => fs.readFileSync(path.join(root, name), 'utf8');
const environment = () => ({phase:'complete', busy:false, ready:true, checked_at:1, status:'ok', errors:0, warnings:0, port:8765, checks:[]});
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
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key] ?? null; }
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
  for (const name of ['ui_state.js', 'job_presentation.js', 'x_login.js', 'media_selection.js', 'app.js']) {
    vm.runInContext(source('static/' + name), context);
  }
  return {context, elements, calls, scheduled, get:key => document.querySelector(key), document,
    evaluate:code => vm.runInContext(code, context), response:fn => {response = fn;},
    close:() => {for (const timer of realTimers) clearTimeout(timer); scheduled.clear();}};
}
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
  let listener, cookieReads = 0; const requests = [];
  const id = 'fixture-extension', popup = 'chrome-extension://' + id + '/popup.html';
  const chrome = {
    runtime:{id, getURL:file => 'chrome-extension://' + id + '/' + file, onMessage:{addListener:fn => {listener = fn;}}},
    storage:{local:{get:async () => ({toolPort:port}), set:async data => {port = data.toolPort;}}},
    cookies:{getAll:async ({domain}) => {cookieReads++; return [{domain, name:'auth_token', value:'SYNTHETIC_COOKIE'}];}},
  };
  const context = vm.createContext({chrome, URL, AbortSignal, Date,
    fetch:async (url, options) => {
      requests.push({url, body:options.body});
      return failPreflight ? json({error:'Windows storage unavailable'}, 503) :
        json(url.endsWith('/prepare') ? {token:'A'.repeat(43)} : {connected:true, message:'Fixture connected'});
    }});
  vm.runInContext(source('chrome-extension/background.js'), context);
  return {requests, cookieReads:() => cookieReads,
    send:(message, sender) => new Promise(resolve => { if (listener(message, {id, ...sender}, resolve) !== true) resolve(undefined); }),
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
