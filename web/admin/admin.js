// Read-only consumer of /v2/admin/*. Same-origin: the host (Vercel rewrite or
// dev-server.mjs) forwards /admin/*, /v2/* and /health to the Flask backend,
// so the backend's session cookie is first-party here.
(function () {
  var state = { farmers: [], fields: [], feedback: null, scans: [], advisories: [] };
  var $ = function (id) { return document.getElementById(id); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var LANGS = { en: "English", kn: "Kannada", te: "Telugu", hi: "Hindi" };
  function langName(c) { return LANGS[c] || c || "unknown"; }

  function api(path) {
    return fetch(path, { credentials: "same-origin" }).then(function (r) {
      if (r.status === 401) { var e = new Error("unauthorized"); e.code = 401; throw e; }
      if (!r.ok) throw new Error(path + " returned " + r.status);
      return r.json();
    });
  }

  function loadAll() {
    return Promise.all([
      api("/v2/admin/farmers"), api("/v2/admin/fields"), api("/v2/admin/feedback"),
      api("/v2/admin/scans"), api("/v2/admin/advisories")
    ]).then(function (r) {
      state.farmers = r[0].items;
      state.fields = r[1].items;
      state.feedback = r[2];
      state.scans = r[3].items;
      state.advisories = r[4].items;
    });
  }

  function showLogin(msg) {
    $("app-view").hidden = true;
    $("login-view").hidden = false;
    var el = $("login-error");
    el.hidden = !msg;
    el.textContent = msg || "";
  }

  function showApp() {
    $("login-view").hidden = true;
    $("app-view").hidden = false;
    route();
  }

  // The existing /admin/login is a form POST that answers with a redirect
  // (to /admin on success, back to /admin/login on failure). fetch follows it
  // and the final URL tells us which happened. The session cookie is set
  // by the backend itself; nothing is checked client-side.
  $("login-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var form = ev.target;
    var body = new URLSearchParams(new FormData(form));
    fetch("/admin/login", { method: "POST", body: body, credentials: "same-origin" })
      .then(function (r) {
        if (new URL(r.url).pathname.replace(/\/$/, "") !== "/admin") {
          return r.text().then(function (t) {
            var m = /class="flash flash-error"[^>]*>([^<]+)</.exec(t);
            throw new Error(m ? m[1].trim() : "Invalid email or password");
          });
        }
        return loadAll();
      })
      .then(function () { form.reset(); showApp(); })
      .catch(function (e) {
        showLogin(e.code === 401 ? "Not an admin session" : e.message || "Sign in failed");
      });
  });

  $("logout").addEventListener("click", function () {
    fetch("/admin/logout", { method: "POST", credentials: "same-origin" })
      .finally(function () {
        state = { farmers: [], fields: [], feedback: null, scans: [], advisories: [] };
        location.hash = "#/";
        showLogin();
      });
  });

  // ---- views ----
  function counts(items, keyFn) {
    var m = {};
    items.forEach(function (i) { var k = keyFn(i) || "unknown"; m[k] = (m[k] || 0) + 1; });
    return Object.keys(m).map(function (k) { return [k, m[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
  }

  function bars(rows, labelFn) {
    if (!rows.length) return '<p class="muted">No data yet.</p>';
    var max = Math.max.apply(null, rows.map(function (r) { return r[1]; }));
    return rows.map(function (r) {
      return '<div class="bar"><span class="lbl">' + esc(labelFn ? labelFn(r[0]) : r[0]) +
        '</span><span class="fill" style="width:' + Math.max(2, (r[1] / max) * 60) + '%"></span>' +
        '<span class="val">' + r[1] + "</span></div>";
    }).join("");
  }

  function stat(label, value, note) {
    return '<div class="card stat"><div class="muted">' + esc(label) + '</div><div class="n">' +
      esc(value) + "</div>" + (note ? '<div class="muted">' + esc(note) + "</div>" : "") + "</div>";
  }

  function fmt(x, d) { return x == null ? "n/a" : Number(x).toFixed(d == null ? 2 : d); }

  function overview() {
    var fb = state.feedback;
    var rd = fb.rating_distribution || {};
    var ratingRows = Object.keys(rd).sort().map(function (k) { return [k + " star", rd[k]]; });
    var sevRows = (fb.by_severity || []).map(function (b) { return [b.severity, b.count]; });
    var withFields = state.farmers.filter(function (f) { return f.field_count > 0; }).length;
    return "<h2>Overview</h2>" +
      '<div class="grid">' +
      stat("Farmers", state.farmers.length, withFields + " with at least one field") +
      stat("Fields", state.fields.length) +
      stat("Feedback entries", fb.total_entries, "mean rating " + fmt(fb.mean_rating) + ", helpful " +
        (fb.helpful_rate == null ? "n/a" : Math.round(fb.helpful_rate * 100) + "%")) +
      stat("Scans run", state.scans.length, "image uploads") +
      stat("Advisories", state.advisories.length) +
      "</div>" +
      '<div class="grid wide">' +
      '<div class="card"><h3>Language distribution</h3>' +
        bars(counts(state.farmers, function (f) { return f.preferred_language; }), langName) + "</div>" +
      '<div class="card"><h3>Current crops</h3>' +
        bars(counts(state.fields, function (f) { return f.current_crop; })) + "</div>" +
      '<div class="card"><h3>Farmers by district</h3>' +
        bars(counts(state.farmers, function (f) { return f.district; })) + "</div>" +
      '<div class="card"><h3>Feedback ratings</h3>' + bars(ratingRows) + "</div>" +
      '<div class="card"><h3>Feedback by advisory severity</h3>' + bars(sevRows) + "</div>" +
      "</div>";
  }

  function farmerList() {
    var langs = counts(state.farmers, function (f) { return f.preferred_language; })
      .map(function (r) { return r[0]; });
    return "<h2>Farmers</h2>" +
      '<div class="toolbar"><input id="q" type="search" placeholder="Search name, phone, district">' +
      '<select id="lang"><option value="">All languages</option>' +
      langs.map(function (l) { return '<option value="' + esc(l) + '">' + esc(langName(l)) + "</option>"; }).join("") +
      "</select></div>" +
      '<p class="muted" id="count"></p>' +
      '<div class="tablewrap"><table><thead><tr><th>Name</th><th>Phone</th><th>District</th>' +
      '<th>Language</th><th>Fields</th><th>Joined</th></tr></thead><tbody id="rows"></tbody></table></div>';
  }

  function fillRows() {
    var q = ($("q").value || "").trim().toLowerCase();
    var lang = $("lang").value;
    var list = state.farmers.filter(function (f) {
      if (lang && f.preferred_language !== lang) return false;
      if (!q) return true;
      return [f.name, f.phone, f.district, f.state].join(" ").toLowerCase().indexOf(q) !== -1;
    });
    $("count").textContent = list.length + " of " + state.farmers.length + " farmers";
    $("rows").innerHTML = list.map(function (f) {
      return '<tr class="row" data-id="' + esc(f.id) + '"><td>' + esc(f.name) + "</td><td>" + esc(f.phone || "") +
        "</td><td>" + esc(f.district || "") + "</td><td>" + esc(langName(f.preferred_language)) +
        "</td><td>" + f.field_count + "</td><td>" + esc((f.created_at || "").slice(0, 10)) + "</td></tr>";
    }).join("") || '<tr><td colspan="6" class="muted">No farmers match.</td></tr>';
  }

  function scanTable(id) {
    var rows = state.scans.filter(function (x) { return x.farmer_id === id; });
    return '<h3 style="margin-top:1.25rem">Scan history (' + rows.length + ")</h3>" + (rows.length
      ? '<div class="tablewrap"><table><thead><tr><th>When</th><th>Field</th><th>Result</th><th>Risk</th>' +
        "<th>Confidence</th><th>Source</th></tr></thead><tbody>" + rows.map(function (a) {
          return "<tr><td>" + esc((a.created_at || "").replace("T", " ").slice(0, 16)) + "</td><td>" + esc(a.field_name) +
            "</td><td>" + esc(a.disease) + "</td><td>" + esc(a.risk_level) + "</td><td>" + fmt(a.confidence) +
            "</td><td>" + esc(a.source) + "</td></tr>";
        }).join("") + "</tbody></table></div>"
      : '<p class="muted">No image scans yet.</p>');
  }

  function advisoryList(id) {
    var rows = state.advisories.filter(function (x) { return x.farmer_id === id; });
    return '<h3 style="margin-top:1.25rem">Advisories (' + rows.length + ")</h3>" + (rows.length
      ? '<div class="tablewrap"><table><thead><tr><th>When</th><th>Field</th><th>Title</th><th>Severity</th>' +
        "<th>Language</th></tr></thead><tbody>" + rows.map(function (a) {
          return "<tr><td>" + esc((a.created_at || "").replace("T", " ").slice(0, 16)) + "</td><td>" + esc(a.field_name) +
            "</td><td>" + esc(a.title) + "</td><td>" + esc(a.severity) + "</td><td>" + esc(langName(a.language)) + "</td></tr>";
        }).join("") + "</tbody></table></div>"
      : '<p class="muted">No advisories yet.</p>');
  }

  function farmerDetail(id) {
    var f = state.farmers.filter(function (x) { return x.id === id; })[0];
    if (!f) return '<p>Farmer not found. <a href="#/farmers">Back</a></p>';
    var fields = state.fields.filter(function (x) { return x.farmer_id === id; });
    var byField = {};
    (state.feedback.by_field || []).forEach(function (b) { byField[b.field_id] = b; });
    var rows = fields.map(function (fl) {
      var b = byField[fl.id];
      return "<tr><td>" + esc(fl.name) + "</td><td>" + esc(fl.current_crop || "") + "</td><td>" +
        esc(fl.soil_type || "") + "</td><td>" + fmt(fl.area_ha) + "</td><td>" +
        fmt(fl.latitude, 4) + ", " + fmt(fl.longitude, 4) + "</td><td>" + esc(fl.sown_on || "") + "</td><td>" +
        (b ? b.count + " (avg " + fmt(b.mean_rating, 1) + ")" : "none") + "</td></tr>";
    }).join("");
    return '<a class="back" href="#/farmers">&larr; All farmers</a>' +
      "<h2>" + esc(f.name) + ' <span class="pill">' + esc(langName(f.preferred_language)) + "</span></h2>" +
      '<div class="card"><dl class="kv"><dt>Phone</dt><dd>' + esc(f.phone || "n/a") +
      "</dd><dt>District</dt><dd>" + esc([f.district, f.state].filter(Boolean).join(", ") || "n/a") +
      "</dd><dt>Role</dt><dd>" + esc(f.role) + "</dd><dt>Joined</dt><dd>" + esc((f.created_at || "").slice(0, 10)) +
      '</dd></dl></div><h3 style="margin-top:1.25rem">Fields (' + fields.length + ")</h3>" +
      (fields.length
        ? '<div class="tablewrap"><table><thead><tr><th>Name</th><th>Crop</th><th>Soil</th><th>Area (ha)</th>' +
          "<th>Lat, Lon</th><th>Sown</th><th>Feedback</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
        : '<p class="muted">This farmer has no fields.</p>') +
      scanTable(id) + advisoryList(id);
  }

  function route() {
    if ($("app-view").hidden) return;
    var h = location.hash || "#/";
    var main = $("main");
    var isFarmers = h.indexOf("#/farmers") === 0;
    $("nav-overview").className = isFarmers ? "" : "active";
    $("nav-farmers").className = isFarmers ? "active" : "";
    var m = /^#\/farmers\/(.+)$/.exec(h);
    if (m) { main.innerHTML = farmerDetail(decodeURIComponent(m[1])); return; }
    if (isFarmers) {
      main.innerHTML = farmerList();
      $("q").addEventListener("input", fillRows);
      $("lang").addEventListener("change", fillRows);
      $("rows").addEventListener("click", function (e) {
        var tr = e.target.closest("tr.row");
        if (tr) location.hash = "#/farmers/" + encodeURIComponent(tr.dataset.id);
      });
      fillRows();
      return;
    }
    main.innerHTML = overview();
  }

  window.addEventListener("hashchange", route);

  // An existing session cookie skips the login screen.
  loadAll().then(showApp).catch(function (e) {
    showLogin(e.code === 401 ? "" : "Cannot reach the backend. Is it running?");
  });
})();
