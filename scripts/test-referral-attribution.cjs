const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const code = fs.readFileSync(__dirname + '/referral-attribution.js', 'utf8');
function visit(url, referrer, data = {}, blocked = false) {
  const inputs = {};
  const form = { querySelector: selector => inputs[selector] ||= {} };
  const window = { innerWidth: 1200 };
  const document = { referrer, readyState: 'complete', querySelectorAll: () => [form] };
  const sessionStorage = {
    getItem: key => { if (blocked) throw Error('blocked'); return data[key] || null; },
    setItem: (key, value) => { if (blocked) throw Error('blocked'); data[key] = value; }
  };
  vm.runInNewContext(code, { window, document, location: new URL(url), URL, URLSearchParams, sessionStorage });
  return { fields: window.ociAttribution.fields(), inputs };
}
test('ChatGPT entry through an article survives internal navigation and later campaign tags', () => {
  const data = {};
  visit('https://ocitech.com/memory-news?utm_source=chatgpt.com', 'https://chatgpt.com/', data);
  const result = visit('https://ocitech.com/sell-server-ram?utm_source=internal', 'https://ocitech.com/memory-news', data);
  assert.equal(result.fields.source_referrer, 'https://chatgpt.com/');
  assert.equal(result.fields.source_landing, '/memory-news?utm_source=chatgpt.com');
  assert.equal(result.fields.source_page, '/sell-server-ram');
  assert.equal(JSON.parse(result.fields.source_utm).utm_source, 'chatgpt.com');
  assert.equal(result.inputs['input[name="source_referrer"]'].value, 'https://chatgpt.com/');
});
test('an untagged first visit stays untagged after later tagged links', () => {
  const data = {};
  visit('https://ocitech.com/', 'https://chatgpt.com/', data);
  const result = visit('https://ocitech.com/sell-ddr4-ram?utm_source=promotion', 'https://ocitech.com/', data);
  assert.equal(result.fields.source_utm, '{}');
  assert.equal(result.fields.source_referrer, 'https://chatgpt.com/');
});
test('direct visits and internal referrers are not reported as external referrals', () => {
  for (const ref of ['', 'https://ocitech.com/about', 'https://www.ocitech.com/about']) {
    assert.equal(visit('https://ocitech.com/', ref).fields.source_referrer, '');
  }
});
test('blocked storage still stamps forms using this page attribution', () => {
  const result = visit('https://ocitech.com/?utm_source=chatgpt.com', 'https://chatgpt.com/', {}, true);
  assert.equal(result.fields.source_referrer, 'https://chatgpt.com/');
  assert.equal(result.inputs['input[name="source_landing"]'].value, '/?utm_source=chatgpt.com');
});
test('malformed saved data is safely replaced', () => {
  for (const value of ['broken', 'null', '{"landing":1}', '{"landing":"/","referrer":"","utm":[]}']) {
    const result = visit('https://ocitech.com/sell-server-ram', 'https://chatgpt.com/', { oci_attribution_v1: value });
    assert.equal(result.fields.source_landing, '/sell-server-ram');
    assert.equal(result.fields.source_referrer, 'https://chatgpt.com/');
  }
});
test('a new session captures a new source', () => {
  assert.equal(visit('https://ocitech.com/', 'https://www.google.com/').fields.source_referrer, 'https://www.google.com/');
});
