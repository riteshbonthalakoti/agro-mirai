// AGRO MIRAI Admin Dashboard — Module 54
// Tailwind CSS + Alpine.js SPA. All /v2/admin/* endpoints unchanged.

// ── Shared helpers ──────────────────────────────────────────────────────────

const LANGS = { en: 'English', kn: 'Kannada', te: 'Telugu', hi: 'Hindi' };
function langName(c) { return LANGS[c] || c || 'unknown'; }
function fmtDt(iso) { return iso ? iso.replace('T', ' ').slice(0, 16) : '—'; }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function api(path, opts) {
  return fetch(path, Object.assign({ credentials: 'same-origin' }, opts || {})).then(function (r) {
    if (r.status === 401) { var e = new Error('unauthorized'); e.code = 401; throw e; }
    if (!r.ok) return r.json().catch(function () { return {}; }).then(function (b) {
      throw new Error((b.error && b.error.message) || (path + ' → ' + r.status));
    });
    if (r.status === 204) return null;
    return r.json();
  });
}

function apiJSON(path, method, body) {
  return api(path, {
    method: method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// Every page component's x-init="load()" fires at mount regardless of
// auth state (x-show only hides the DOM, it doesn't delay mounting), so
// on a fresh page load these race the session check and lose -- the
// resulting empty state never retried before this fix. A page's own
// catch calls this instead of showing an error toast when the failure
// was specifically "not logged in yet": once adminApp confirms the
// session (existing cookie or a fresh login), it dispatches
// 'admin-authed' and every page still waiting on one fires its retry.
function retryAfterAuth(e, loadFn) {
  if (e.code !== 401) return false;
  window.addEventListener('admin-authed', loadFn, { once: true });
  return true;
}

// Chart.js helpers — destroy before recreate to avoid "Canvas already in use"
var _charts = {};
function destroyChart(id) {
  if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}
function makeBarChart(id, labels, values, color) {
  color = color || '#22c55e';
  destroyChart(id);
  var ctx = document.getElementById(id);
  if (!ctx) return;
  _charts[id] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{ data: values, backgroundColor: color + 'cc', borderRadius: 4 }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { stepSize: 1 } },
        y: { ticks: { font: { size: 11 } } },
      },
    },
  });
}

const SOIL_TYPES = ['alluvial','black','desert','laterite','mountain','peaty','red','saline','unknown'];

// ── adminApp — top-level shell ───────────────────────────────────────────────

function adminApp() {
  return {
    authed: false,
    view: 'overview',
    unreadBugs: 0,
    otpDevMode: false,
    loginEmail: '',
    loginPassword: '',
    loginBusy: false,
    loginError: '',
    toast: { show: false, msg: '', type: 'info', _timer: null },
    confirm: { show: false, expected: '', typed: '', onConfirm: null },
    drawer: { show: false, title: '', bodyHtml: '', save: null, saving: false, error: '' },

    navItems: [
      { view: 'overview', hash: '',        icon: '📊', label: 'Overview' },
      { view: 'farmers',  hash: 'farmers', icon: '👩‍🌾', label: 'Farmers' },
      { view: 'fields',   hash: 'fields',  icon: '🌾', label: 'Fields' },
      { view: 'bugs',     hash: 'bugs',    icon: '🐛', label: 'Bug Reports' },
      { view: 'audit',    hash: 'audit',   icon: '📋', label: 'Audit Log' },
      { view: 'otps',     hash: 'otps',    icon: '🔑', label: 'OTPs (dev)' },
    ],

    init() {
      var self = this;
      // Try existing session cookie
      api('/v2/admin/overview').then(function (d) {
        self.otpDevMode = d.otp_dev_mode === true;
        self.authed = true;
        self._routeFromHash();
        window.dispatchEvent(new CustomEvent('admin-authed'));
      }).catch(function (e) {
        if (e.code !== 401) self.loginError = 'Backend unreachable.';
      });

      window.addEventListener('hashchange', function () { self._routeFromHash(); });

      // Cross-component event bus
      window.addEventListener('admin-toast', function (e) {
        self.showToast(e.detail.msg, e.detail.type || 'info');
      });
      window.addEventListener('admin-confirm', function (e) {
        self.showConfirm(e.detail.expected, e.detail.onConfirm);
      });
      window.addEventListener('admin-open-drawer', function (e) {
        self.openDrawer(e.detail.title, e.detail.html, function () {
          self.drawer.saving = true;
          self.drawer.error = '';
          return e.detail.saveFn()
            .then(function () { self.drawer.show = false; })
            .catch(function (err) { self.drawer.error = err.message || 'Save failed'; })
            .finally(function () { self.drawer.saving = false; });
        });
      });
      window.addEventListener('admin-new-bug', function () {
        if (self.view !== 'bugs') self.unreadBugs++;
      });

      this.$watch('view', function (v) {
        window.dispatchEvent(new CustomEvent('view-changed', { detail: v }));
      });
    },

    _routeFromHash() {
      var h = (location.hash || '').replace(/^#\/?/, '');
      var seg = h.split('/')[0];
      var map = { '': 'overview', farmers: 'farmers', fields: 'fields',
                  bugs: 'bugs', audit: 'audit', otps: 'otps' };
      this.view = map[seg] || 'overview';
      if (this.view === 'bugs') this.unreadBugs = 0;
    },

    navigate(v) {
      this.view = v;
      if (v === 'bugs') this.unreadBugs = 0;
    },

    login() {
      var self = this;
      self.loginBusy = true;
      self.loginError = '';
      var body = new URLSearchParams({ email: self.loginEmail, password: self.loginPassword });
      fetch('/admin/login', { method: 'POST', body: body, credentials: 'same-origin' })
        .then(function (r) {
          // Detect success: backend redirects to /admin on success, back to /admin/login on failure
          var p = new URL(r.url).pathname.replace(/\/$/, '');
          if (p !== '/admin') {
            return r.text().then(function (t) {
              var m = /class="flash flash-error"[^>]*>([^<]+)</.exec(t);
              throw new Error(m ? m[1].trim() : 'Invalid email or password');
            });
          }
          return api('/v2/admin/overview').then(function (d) {
            self.otpDevMode = d.otp_dev_mode === true;
          });
        })
        .then(function () {
          self.authed = true;
          self.loginEmail = '';
          self.loginPassword = '';
          self.view = 'overview';
          window.dispatchEvent(new CustomEvent('admin-authed'));
        })
        .catch(function (e) { self.loginError = e.message || 'Sign in failed'; })
        .finally(function () { self.loginBusy = false; });
    },

    logout() {
      var self = this;
      fetch('/admin/logout', { method: 'POST', credentials: 'same-origin' })
        .finally(function () {
          self.authed = false;
          self.view = 'overview';
          self.unreadBugs = 0;
        });
    },

    showToast(msg, type) {
      var self = this;
      clearTimeout(self.toast._timer);
      self.toast = {
        show: true, msg: msg, type: type || 'info',
        _timer: setTimeout(function () { self.toast.show = false; }, 4000),
      };
    },

    showConfirm(expected, onConfirm) {
      var self = this;
      self.confirm = {
        show: true, expected: expected, typed: '',
        onConfirm: function () {
          onConfirm()
            .then(function () { self.confirm.show = false; })
            .catch(function (e) { self.showToast(e.message || 'Delete failed', 'error'); });
        },
      };
      self.$nextTick(function () {
        var el = self.$refs.confirmInput;
        if (el) el.focus();
      });
    },

    openDrawer(title, bodyHtml, saveFn) {
      this.drawer = { show: true, title: title, bodyHtml: bodyHtml, save: saveFn, saving: false, error: '' };
    },
  };
}

// ── overviewPage ─────────────────────────────────────────────────────────────

function overviewPage() {
  return {
    ovLoading: true,
    statCards: [],
    recentActivity: [],
    _farmers: [],
    _fields: [],

    load() {
      var self = this;
      Promise.all([
        api('/v2/admin/overview'),
        api('/v2/admin/farmers'),
        api('/v2/admin/fields'),
        api('/v2/admin/scans'),
        api('/v2/admin/advisories'),
      ]).then(function (results) {
        var ov = results[0], fa = results[1], fi = results[2], sc = results[3], ad = results[4];
        self._farmers = fa.items;
        self._fields = fi.items;
        var fb = ov.feedback || {};
        var withFields = fa.items.filter(function (f) { return f.field_count > 0; }).length;
        self.statCards = [
          { label: 'Total Farmers', value: fa.items.length, note: withFields + ' with fields' },
          { label: 'Total Fields',  value: fi.items.length, note: '' },
          { label: 'Disease Scans', value: sc.items.length, note: 'image uploads' },
          { label: 'Advisories',    value: ad.items.length, note: '' },
          { label: 'Open Bugs',     value: ov.open_bug_count != null ? ov.open_bug_count : '—', note: '' },
          { label: 'Avg Feedback',
            value: fb.mean_rating != null ? (+fb.mean_rating).toFixed(1) + ' ★' : '—',
            note:  fb.helpful_rate != null ? Math.round(fb.helpful_rate * 100) + '% helpful' : '' },
        ];
        var rows = sc.items.map(function (s) {
          return { type: 'Scan', created_at: s.created_at, field_name: s.field_name, detail: s.disease };
        }).concat(ad.items.map(function (a) {
          return { type: 'Advisory', created_at: a.created_at, field_name: a.field_name, detail: a.severity };
        }));
        rows.sort(function (a, b) { return (b.created_at || '').localeCompare(a.created_at || ''); });
        self.recentActivity = rows.slice(0, 20).map(function (r) {
          return Object.assign({}, r, { when: fmtDt(r.created_at) });
        });
        self.ovLoading = false;
        self.$nextTick(function () { self._drawCharts(); });
      }).catch(function (e) {
        if (retryAfterAuth(e, function () { self.load(); })) return;
        self.ovLoading = false;
        window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
      });
    },

    _drawCharts() {
      var cropCounts = {};
      this._fields.forEach(function (f) {
        var k = f.current_crop || 'unknown';
        cropCounts[k] = (cropCounts[k] || 0) + 1;
      });
      var cropSorted = Object.entries(cropCounts).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 8);
      makeBarChart('cropChart', cropSorted.map(function (r) { return r[0]; }), cropSorted.map(function (r) { return r[1]; }));

      var langCounts = {};
      this._farmers.forEach(function (f) {
        var k = f.preferred_language || 'unknown';
        langCounts[k] = (langCounts[k] || 0) + 1;
      });
      var langSorted = Object.entries(langCounts).sort(function (a, b) { return b[1] - a[1]; });
      makeBarChart('langChart',
        langSorted.map(function (r) { return langName(r[0]); }),
        langSorted.map(function (r) { return r[1]; }),
        '#3b82f6');
    },
  };
}

// ── farmersPage ──────────────────────────────────────────────────────────────

function farmersPage() {
  return {
    farmers: [],
    fq: '',
    fLang: '',
    detailId: null,

    get filteredFarmers() {
      var q = this.fq.trim().toLowerCase();
      var lang = this.fLang;
      return this.farmers.filter(function (f) {
        if (lang && f.preferred_language !== lang) return false;
        if (!q) return true;
        return [f.name, f.phone, f.district, f.state].join(' ').toLowerCase().indexOf(q) !== -1;
      });
    },

    langName: langName,

    load() {
      var self = this;
      api('/v2/admin/farmers').then(function (r) { self.farmers = r.items; })
        .catch(function (e) {
          if (retryAfterAuth(e, function () { self.load(); })) return;
          window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
        });
    },

    openFarmerEdit(f) {
      var self = this;
      var langOpts = ['en','kn','te','hi'].map(function (l) {
        return '<option value="' + l + '"' + (f.preferred_language === l ? ' selected' : '') + '>' + langName(l) + '</option>';
      }).join('');
      var html = '<div class="space-y-4">' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Name</span>' +
        '<input id="de-name" class="input-field mt-1" value="' + esc(f.name) + '"></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Phone</span>' +
        '<input id="de-phone" class="input-field mt-1" value="' + esc(f.phone || '') + '"></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Language</span>' +
        '<select id="de-lang" class="input-field mt-1">' + langOpts + '</select></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">District</span>' +
        '<input id="de-district" class="input-field mt-1" value="' + esc(f.district || '') + '"></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">State</span>' +
        '<input id="de-state" class="input-field mt-1" value="' + esc(f.state || '') + '"></label>' +
        '</div>';
      var saveFn = function () {
        var patch = {
          name:               document.getElementById('de-name').value,
          phone:              document.getElementById('de-phone').value,
          preferred_language: document.getElementById('de-lang').value,
          district:           document.getElementById('de-district').value,
          state:              document.getElementById('de-state').value,
        };
        return apiJSON('/v2/admin/farmers/' + encodeURIComponent(f.id), 'PATCH', patch)
          .then(function (updated) {
            self.farmers = self.farmers.map(function (x) {
              return x.id === f.id ? Object.assign({}, x, updated) : x;
            });
            window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: 'Saved.' } }));
          });
      };
      window.dispatchEvent(new CustomEvent('admin-open-drawer', {
        detail: { title: 'Edit: ' + f.name, html: html, saveFn: saveFn },
      }));
    },

    deleteFarmer(id, name) {
      var self = this;
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: name,
        onConfirm: function () {
          return api('/v2/admin/farmers/' + encodeURIComponent(id), { method: 'DELETE' })
            .then(function () { self.farmers = self.farmers.filter(function (x) { return x.id !== id; }); });
        },
      }}));
    },
  };
}

// ── farmerDetailPage ─────────────────────────────────────────────────────────

function farmerDetailPage() {
  return {
    fdLoading: true,
    farmer: null,
    fdFields: [],
    fdScans: [],
    fdAdvisories: [],
    fdTab: 'Fields',
    fdEdit: { name: '', phone: '', district: '', state: '' },
    fdSaving: false,
    fdMsg: '',

    langName: langName,
    fmtDt: fmtDt,

    load(id) {
      var self = this;
      self.fdLoading = true;
      Promise.all([
        api('/v2/admin/farmers'),
        api('/v2/admin/fields'),
        api('/v2/admin/scans'),
        api('/v2/admin/advisories'),
      ]).then(function (results) {
        var fa = results[0], fi = results[1], sc = results[2], ad = results[3];
        self.farmer = fa.items.find(function (f) { return f.id === id; }) || null;
        if (!self.farmer) { self.fdLoading = false; return; }
        self.fdEdit = {
          name: self.farmer.name,
          phone: self.farmer.phone || '',
          district: self.farmer.district || '',
          state: self.farmer.state || '',
        };
        self.fdFields     = fi.items.filter(function (f) { return f.farmer_id === id; });
        self.fdScans      = sc.items.filter(function (s) { return s.farmer_id === id; });
        self.fdAdvisories = ad.items.filter(function (a) { return a.farmer_id === id; });
        self.fdLoading = false;
      }).catch(function (e) {
        if (retryAfterAuth(e, function () { self.load(id); })) return;
        self.fdLoading = false;
        window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
      });
    },

    saveFarmerDetail() {
      var self = this;
      self.fdSaving = true;
      self.fdMsg = '';
      apiJSON('/v2/admin/farmers/' + encodeURIComponent(self.farmer.id), 'PATCH', self.fdEdit)
        .then(function () {
          self.fdMsg = 'Saved.';
          setTimeout(function () { self.fdMsg = ''; }, 2000);
        })
        .catch(function (e) { self.fdMsg = e.message; })
        .finally(function () { self.fdSaving = false; });
    },

    deleteFarmerDetail() {
      var self = this;
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: self.farmer.name,
        onConfirm: function () {
          return api('/v2/admin/farmers/' + encodeURIComponent(self.farmer.id), { method: 'DELETE' })
            .then(function () {
              // Navigate back to farmers list
              self.$root.detailId = null;
            });
        },
      }}));
    },

    deleteFieldDetail(id, name) {
      var self = this;
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: name,
        onConfirm: function () {
          return api('/v2/admin/fields/' + encodeURIComponent(id), { method: 'DELETE' })
            .then(function () {
              self.fdFields = self.fdFields.filter(function (f) { return f.id !== id; });
            });
        },
      }}));
    },
  };
}

// ── fieldsPage ───────────────────────────────────────────────────────────────

function fieldsPage() {
  return {
    fields: [],
    flq: '',

    get filteredFields() {
      var q = this.flq.trim().toLowerCase();
      if (!q) return this.fields;
      return this.fields.filter(function (f) {
        return [f.name, f.current_crop, f.farmer_name, f.soil_type].join(' ').toLowerCase().indexOf(q) !== -1;
      });
    },

    load() {
      var self = this;
      Promise.all([api('/v2/admin/fields'), api('/v2/admin/farmers')]).then(function (results) {
        var fi = results[0], fa = results[1];
        var farmerMap = {};
        fa.items.forEach(function (f) { farmerMap[f.id] = f.name; });
        self.fields = fi.items.map(function (f) {
          return Object.assign({}, f, { farmer_name: farmerMap[f.farmer_id] || '—' });
        });
      }).catch(function (e) {
        if (retryAfterAuth(e, function () { self.load(); })) return;
        window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
      });
    },

    openFieldEdit(fl) {
      var self = this;
      var soilOpts = SOIL_TYPES.map(function (s) {
        return '<option value="' + s + '"' + (fl.soil_type === s ? ' selected' : '') + '>' + s + '</option>';
      }).join('');
      var html = '<div class="space-y-4">' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Name</span>' +
        '<input id="de-name" class="input-field mt-1" value="' + esc(fl.name) + '"></label>' +
        '<div class="grid grid-cols-2 gap-3">' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Latitude</span>' +
        '<input id="de-lat" type="number" step="0.0001" class="input-field mt-1" value="' + (fl.latitude != null ? fl.latitude : '') + '"></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Longitude</span>' +
        '<input id="de-lng" type="number" step="0.0001" class="input-field mt-1" value="' + (fl.longitude != null ? fl.longitude : '') + '"></label>' +
        '</div>' +
        '<div class="grid grid-cols-2 gap-3">' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Area (ha)</span>' +
        '<input id="de-area" type="number" step="0.01" class="input-field mt-1" value="' + (fl.area_ha != null ? fl.area_ha : '') + '"></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Elevation (m)</span>' +
        '<input id="de-elev" type="number" class="input-field mt-1" value="' + (fl.elevation_m != null ? fl.elevation_m : '') + '"></label>' +
        '</div>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Soil type</span>' +
        '<select id="de-soil" class="input-field mt-1">' + soilOpts + '</select></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Current crop</span>' +
        '<input id="de-crop" class="input-field mt-1" value="' + esc(fl.current_crop || '') + '"></label>' +
        '<label class="block"><span class="text-xs text-slate-500 font-medium">Sown on</span>' +
        '<input id="de-sown" type="date" class="input-field mt-1" value="' + esc(fl.sown_on || '') + '"></label>' +
        '</div>';
      var saveFn = function () {
        var elevVal = document.getElementById('de-elev').value;
        var patch = {
          name:         document.getElementById('de-name').value,
          latitude:     parseFloat(document.getElementById('de-lat').value) || null,
          longitude:    parseFloat(document.getElementById('de-lng').value) || null,
          area_ha:      parseFloat(document.getElementById('de-area').value) || null,
          elevation_m:  elevVal ? +elevVal : null,
          soil_type:    document.getElementById('de-soil').value,
          current_crop: document.getElementById('de-crop').value || null,
          sown_on:      document.getElementById('de-sown').value || null,
        };
        return apiJSON('/v2/admin/fields/' + encodeURIComponent(fl.id), 'PATCH', patch)
          .then(function (updated) {
            self.fields = self.fields.map(function (f) {
              return f.id === fl.id ? Object.assign({}, f, updated) : f;
            });
            window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: 'Saved.' } }));
          });
      };
      window.dispatchEvent(new CustomEvent('admin-open-drawer', {
        detail: { title: 'Edit field: ' + fl.name, html: html, saveFn: saveFn },
      }));
    },

    deleteField(id, name) {
      var self = this;
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: name,
        onConfirm: function () {
          return api('/v2/admin/fields/' + encodeURIComponent(id), { method: 'DELETE' })
            .then(function () { self.fields = self.fields.filter(function (f) { return f.id !== id; }); });
        },
      }}));
    },
  };
}

// ── bugReportsPage ───────────────────────────────────────────────────────────

function bugReportsPage() {
  var _stream = null;

  return {
    bugReports: [],
    fmtDt: fmtDt,

    statusClass(s) {
      return {
        open:        'bg-red-50 text-red-700',
        triaged:     'bg-amber-50 text-amber-700',
        in_progress: 'bg-blue-50 text-blue-700',
        resolved:    'bg-green-50 text-green-700',
      }[s] || '';
    },

    load() {
      var self = this;
      api('/v2/admin/bug-reports').then(function (r) {
        self.bugReports = r.items.slice().sort(function (a, b) {
          return (b.created_at || '').localeCompare(a.created_at || '');
        });
        self._startStream();
      }).catch(function (e) {
        if (retryAfterAuth(e, function () { self.load(); })) return;
        window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
      });
    },

    stopStream() {
      if (_stream) { _stream.close(); _stream = null; }
    },

    _startStream() {
      if (_stream) return;
      _stream = new EventSource('/v2/admin/stream/bug-reports');
      var badge = document.getElementById('bug-live-badge');
      _stream.onopen = function () {
        if (badge) {
          badge.textContent = 'live';
          badge.style.background = '#dcfce7';
          badge.style.color = '#166534';
        }
      };
      _stream.onmessage = function (ev) {
        var report = JSON.parse(ev.data);
        var existing = self.bugReports.some(function (r) { return r.id === report.id; });
        if (!existing) {
          self.bugReports.unshift(report);
          window.dispatchEvent(new CustomEvent('admin-new-bug'));
        }
      };
      _stream.onerror = function () {
        if (badge) {
          badge.textContent = 'reconnecting…';
          badge.style.background = '#f1f5f9';
          badge.style.color = '#64748b';
        }
      };
    },

    patchStatus(r) {
      apiJSON('/v2/admin/bug-reports/' + encodeURIComponent(r.id), 'PATCH', { status: r.status })
        .catch(function (e) {
          window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
        });
    },

    deleteReport(id) {
      var self = this;
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: id.slice(0, 8),
        onConfirm: function () {
          return api('/v2/admin/bug-reports/' + encodeURIComponent(id), { method: 'DELETE' })
            .then(function () {
              self.bugReports = self.bugReports.filter(function (r) { return r.id !== id; });
            });
        },
      }}));
    },
  };
}

// ── auditLogPage ─────────────────────────────────────────────────────────────

function auditLogPage() {
  return {
    alLoading: true,
    alEntries: [],
    fmtDt: fmtDt,

    prettyJson(jsonStr) {
      if (!jsonStr) return '';
      try { return JSON.stringify(JSON.parse(jsonStr), null, 2); } catch (e) { return jsonStr; }
    },

    load() {
      var self = this;
      api('/v2/admin/audit-log').then(function (r) {
        self.alEntries = r.items.map(function (e) { return Object.assign({ _open: false }, e); });
        self.alLoading = false;
      }).catch(function (e) {
        if (retryAfterAuth(e, function () { self.load(); })) return;
        self.alLoading = false;
        window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } }));
      });
    },
  };
}

// ── otpsPage ──────────────────────────────────────────────────────────────────

function otpsPage() {
  var _timer = null;

  return {
    otps: [],
    fmtDt: fmtDt,

    startPolling() {
      var self = this;
      self._fetch();
      _timer = setInterval(function () { self._fetch(); }, 5000);
    },

    stopPolling() {
      if (_timer) { clearInterval(_timer); _timer = null; }
    },

    _fetch() {
      var self = this;
      api('/v2/admin/otps').then(function (r) { self.otps = r.items; }).catch(function (e) {
        retryAfterAuth(e, function () { self._fetch(); });
      });
    },
  };
}

// ── Alpine registration ───────────────────────────────────────────────────────

document.addEventListener('alpine:init', function () {
  Alpine.data('adminApp',         adminApp);
  Alpine.data('overviewPage',     overviewPage);
  Alpine.data('farmersPage',      farmersPage);
  Alpine.data('farmerDetailPage', farmerDetailPage);
  Alpine.data('fieldsPage',       fieldsPage);
  Alpine.data('bugReportsPage',   bugReportsPage);
  Alpine.data('auditLogPage',     auditLogPage);
  Alpine.data('otpsPage',         otpsPage);
});
