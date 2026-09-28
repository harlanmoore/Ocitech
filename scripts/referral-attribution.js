(function () {
  'use strict';
  if (window.ociAttribution) return;

  var key = 'oci_attribution_v1';
  var first;
  try {
    first = JSON.parse(sessionStorage.getItem(key));
    if (!first || typeof first.landing !== 'string' || typeof first.referrer !== 'string' ||
        !first.utm || typeof first.utm !== 'object' || Array.isArray(first.utm)) first = null;
  } catch (e) { first = null; }

  if (!first) {
    var campaign = {};
    var query = new URLSearchParams(location.search);
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'rdt_cid'].forEach(function (name) {
      if (query.get(name)) campaign[name] = query.get(name);
    });
    var referrer = '';
    try {
      var incoming = new URL(document.referrer);
      var host = function (value) { return value.replace(/^www\./, '').toLowerCase(); };
      if (/^https?:$/.test(incoming.protocol) && host(incoming.hostname) !== host(location.hostname)) {
        referrer = incoming.href;
      }
    } catch (e) { /* A direct visit has no referrer. */ }
    first = { landing: location.pathname + location.search, referrer: referrer, utm: campaign };
    // Store even an empty campaign so later internal links cannot replace first touch.
    try { sessionStorage.setItem(key, JSON.stringify(first)); } catch (e) { /* Keep this page usable without storage. */ }
  }

  function fields() {
    return {
      source_utm: JSON.stringify(first.utm),
      source_landing: first.landing,
      source_page: location.pathname,
      source_device: window.innerWidth < 760 ? 'mobile' : 'desktop',
      source_referrer: first.referrer
    };
  }
  function stamp(form) {
    var values = fields();
    Object.keys(values).forEach(function (name) {
      var input = form.querySelector('input[name="' + name + '"]');
      if (input) input.value = values[name];
    });
  }
  window.ociAttribution = { fields: fields, stamp: stamp };
  function stampForms() { document.querySelectorAll('form').forEach(stamp); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', stampForms);
  else stampForms();
})();
