export const APP_MODE_SOURCE = 'ic-app-mode'

const APP_MODE_SCRIPT = `<script id="ic-app-mode-runtime">
(function () {
  var SOURCE = '${APP_MODE_SOURCE}';
  var NAV_EVENT = 'ic_nav';
  var STATE_EVENT = 'ic_state';
  var READY_EVENT = 'ic_ready';
  var STATE_INIT = 'ic_state_init';
  var DATA_EVENT = 'instant-coffee:update';
  var MAX_EVENTS = 100;
  var MAX_RECORDS = 200;
  var appState = {};
  var eventLog = [];
  var recordLog = [];
  var applying = false;

  function isExternalHref(href) {
    if (!href) return true;
    if (href.indexOf('#') === 0) return true;
    if (href.indexOf('//') === 0) return true;
    return /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(href);
  }

  function normalizeSlug(href) {
    if (!href) return null;
    if (isExternalHref(href)) return null;
    var raw = href.split('#')[0].split('?')[0];
    if (!raw) return null;
    if (raw.indexOf('./') === 0) raw = raw.slice(2);
    if (raw.indexOf('/') === 0) raw = raw.slice(1);
    if (raw === 'index' || raw === 'index.html') return 'index';
    if (raw.indexOf('pages/') === 0) raw = raw.slice(6);
    if (raw.slice(-5) === '.html') raw = raw.slice(0, -5);
    if (!raw) return null;
    if (raw.indexOf('/') !== -1) return null;
    return raw;
  }

  function getKey(el) {
    if (!el) return null;
    return el.getAttribute('data-ic-key') || el.name || el.id || null;
  }

  function readValue(el) {
    if (!el) return undefined;
    var tag = el.tagName;
    if (tag === 'INPUT') {
      var type = el.type || 'text';
      if (type === 'checkbox') return !!el.checked;
      if (type === 'radio') return el.checked ? el.value : undefined;
      if (type === 'file') return undefined;
      return el.value;
    }
    if (tag === 'SELECT') {
      if (el.multiple) {
        var values = [];
        for (var i = 0; i < el.options.length; i += 1) {
          var opt = el.options[i];
          if (opt.selected) values.push(opt.value);
        }
        return values;
      }
      return el.value;
    }
    if (tag === 'TEXTAREA') {
      return el.value;
    }
    return undefined;
  }

  function writeValue(el, value) {
    if (value === undefined || value === null) return;
    var tag = el.tagName;
    if (tag === 'INPUT') {
      var type = el.type || 'text';
      if (type === 'checkbox') {
        el.checked = !!value;
        return;
      }
      if (type === 'radio') {
        el.checked = String(value) === el.value;
        return;
      }
      if (type === 'file') return;
      el.value = String(value);
      return;
    }
    if (tag === 'SELECT') {
      if (el.multiple && Array.isArray(value)) {
        for (var i = 0; i < el.options.length; i += 1) {
          el.options[i].selected = value.indexOf(el.options[i].value) !== -1;
        }
        return;
      }
      el.value = String(value);
      return;
    }
    if (tag === 'TEXTAREA') {
      el.value = String(value);
    }
  }

  function applyState() {
    applying = true;
    try {
      var fields = document.querySelectorAll('input, select, textarea');
      for (var i = 0; i < fields.length; i += 1) {
        var el = fields[i];
        var key = getKey(el);
        if (!key || !(key in appState)) continue;
        writeValue(el, appState[key]);
      }
    } finally {
      applying = false;
    }
  }

  function emitUpdate() {
    if (!window.parent) return;
    window.parent.postMessage(
      {
        type: DATA_EVENT,
        state: appState,
        events: eventLog,
        records: recordLog,
        timestamp: Date.now(),
      },
      '*'
    );
  }

  function pushEvent(name, data) {
    if (!name) return;
    eventLog.unshift({
      name: String(name),
      data: data === undefined ? null : data,
      timestamp: Date.now(),
    });
    if (eventLog.length > MAX_EVENTS) {
      eventLog.length = MAX_EVENTS;
    }
    emitUpdate();
  }

  function pushRecord(type, payload) {
    var recordType =
      type === 'order_submitted' || type === 'booking_submitted' || type === 'form_submission'
        ? type
        : 'form_submission';
    recordLog.unshift({
      type: recordType,
      payload: payload,
      created_at: new Date().toISOString(),
    });
    if (recordLog.length > MAX_RECORDS) {
      recordLog.length = MAX_RECORDS;
    }
    emitUpdate();
  }

  function toSerializable(value) {
    if (!value) return value;
    if (typeof File !== 'undefined' && value instanceof File) {
      return { name: value.name, size: value.size, type: value.type };
    }
    return value;
  }

  function collectFormData(form) {
    var data = {};
    if (!form || typeof FormData === 'undefined') return data;
    var formData = new FormData(form);
    formData.forEach(function (value, key) {
      var cleaned = toSerializable(value);
      if (data[key] === undefined) {
        data[key] = cleaned;
      } else if (Array.isArray(data[key])) {
        data[key].push(cleaned);
      } else {
        data[key] = [data[key], cleaned];
      }
    });
    return data;
  }

  function inferRecordType(form) {
    if (!form || !form.getAttribute) return 'form_submission';
    var candidate =
      form.getAttribute('data-ic-record-type') ||
      form.getAttribute('data-record-type') ||
      form.getAttribute('data-record');
    if (candidate === 'order_submitted' || candidate === 'booking_submitted' || candidate === 'form_submission') {
      return candidate;
    }
    return 'form_submission';
  }

  function emitState() {
    if (!window.parent) return;
    window.parent.postMessage(
      { source: SOURCE, type: STATE_EVENT, state: appState },
      '*'
    );
  }

  function updateState(key, value) {
    if (!key) return;
    appState[key] = value;
    emitState();
    pushEvent('state_update', { key: key, value: value });
  }

  document.addEventListener('input', function (event) {
    if (applying) return;
    var target = event.target;
    var key = getKey(target);
    if (!key) return;
    var value = readValue(target);
    if (value === undefined) return;
    updateState(key, value);
  }, true);

  document.addEventListener('change', function (event) {
    if (applying) return;
    var target = event.target;
    var key = getKey(target);
    if (!key) return;
    var value = readValue(target);
    if (value === undefined) return;
    updateState(key, value);
  }, true);

  document.addEventListener('submit', function (event) {
    var target = event.target;
    if (!target || target.tagName !== 'FORM') return;
    var recordPayload = collectFormData(target);
    var recordType = inferRecordType(target);
    pushRecord(recordType, recordPayload);
    pushEvent('form_submit', { type: recordType });
  }, true);

  document.addEventListener('click', function (event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var anchor = target.closest('a');
    if (!anchor) return;
    var href = anchor.getAttribute('href');
    var slug = normalizeSlug(href);
    if (!slug) return;
    event.preventDefault();
    pushEvent('navigate', { slug: slug, href: href });
    if (window.parent) {
      window.parent.postMessage(
        { source: SOURCE, type: NAV_EVENT, slug: slug },
        '*'
      );
    }
  }, true);

  window.addEventListener('message', function (event) {
    var data = event.data || {};
    if (!data || data.source !== SOURCE) return;
    if (data.type === STATE_INIT) {
      appState = data.state && typeof data.state === 'object' ? data.state : {};
      applyState();
      emitUpdate();
    }
  });

  window.IC_APP = {
    getState: function () {
      return appState;
    },
    setState: function (keyOrState, value) {
      if (typeof keyOrState === 'string') {
        updateState(keyOrState, value);
        return;
      }
      if (keyOrState && typeof keyOrState === 'object') {
        for (var key in keyOrState) {
          if (Object.prototype.hasOwnProperty.call(keyOrState, key)) {
            appState[key] = keyOrState[key];
          }
        }
        emitState();
        pushEvent('state_sync', { keys: Object.keys(keyOrState) });
      }
    },
    navigate: function (slug) {
      if (!slug || !window.parent) return;
      window.parent.postMessage(
        { source: SOURCE, type: NAV_EVENT, slug: slug },
        '*'
      );
    }
  };

  if (window.parent) {
    window.parent.postMessage({ source: SOURCE, type: READY_EVENT }, '*');
    emitUpdate();
  }
})();
</script>`;

export const injectAppModeRuntime = (html: string) => {
  if (!html) return html
  if (html.includes('id="ic-app-mode-runtime"')) return html
  if (html.includes('</body>')) {
    return html.replace('</body>', `${APP_MODE_SCRIPT}</body>`)
  }
  if (html.includes('</head>')) {
    return html.replace('</head>', `${APP_MODE_SCRIPT}</head>`)
  }
  return `${html}${APP_MODE_SCRIPT}`
}
