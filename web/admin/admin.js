// Consumer of /v2/admin/*. Same-origin: the host (Vercel rewrite or
// dev-server.mjs) forwards /admin/*, /v2/* and /health to the Flask
// backend, so the backend's session cookie is first-party here.
// Module 50: gained write actions (farmer/field edit+delete, bug-report
// status+delete) on top of the original read-only Overview/Farmers views.
(function () {
  var state = { farmers: [], fields: [], feedback: null, scans: [], advisories: [],
                bugReports: [], auditLog: [] };
  var $ = function (id) { return document.getElementById(id); };
  var bugStream = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var LANGS = { en: "English", kn: "Kannada", te: "Telugu", hi: "Hindi" };
  function langName(c) { return LANGS[c] || c || "unknown"; }

  var BUG_STATUSES = ["open", "triaged", "in_progress", "resolved"];

  function api(path, opts) {
    return fetch(path, Object.assign({ credentials: "same-origin" }, opts || {})).then(function (r) {
      if (r.status === 401) { var e = new Error("unauthorized"); e.code = 401; throw e; }
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (body) {
          throw new Error((body.error && body.error.message) || (path + " returned " + r.status));
        });
      }
      if (r.status === 204) return null;
      return r.json();
    });
  }

  function apiJSON(path, method, body) {
    return api(path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
    if (bugStream) { bugStream.close(); bugStream = null; }
    fetch("/admin/logout", { method: "POST", credentials: "same-origin" })
      .finally(function () {
        state = { farmers: [], fields: [], feedback: null, scans: [], advisories: [],
                  bugReports: [], auditLog: [] };
        location.hash = "#/";
        showLogin();
      });
  });

  // ---- confirm-delete overlay (type-to-confirm) ----
  function confirmDelete(label, onConfirm) {
    var wrap = document.createElement("div");
    wrap.className = "overlay";
    wrap.innerHTML = '<div class="card">' +
      '<p>Type <strong>' + esc(label) + '</strong> to confirm deletion. This cannot be undone.</p>' +
      '<input id="confirm-input" autocomplete="off">' +
      '<div class="actions" style="margin-top:.75rem">' +
      '<button id="confirm-delete-btn" class="danger" disabled>Delete</button>' +
      '<button id="confirm-cancel-btn" class="ghost">Cancel</button></div></div>';
    document.body.appendChild(wrap);
    var input = wrap.querySelector("#confirm-input");
    var delBtn = wrap.querySelector("#confirm-delete-btn");
    input.addEventListener("input", function () { delBtn.disabled = input.value !== label; });
    wrap.querySelector("#confirm-cancel-btn").addEventListener("click", function () { wrap.remove(); });
    delBtn.addEventListener("click", function () {
      delBtn.disabled = true;
      onConfirm().then(function () { wrap.remove(); }).catch(function (e) {
        delBtn.disabled = false;
        alert(e.message || "Delete failed");
      });
    });
    input.focus();
  }

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

  function recentActivity() {
    var rows = state.scans.map(function (s) {
      return { type: "Scan", created_at: s.created_at, field_name: s.field_name, detail: s.disease };
    }).concat(state.advisories.map(function (a) {
      return { type: "Advisory", created_at: a.created_at, field_name: a.field_name, detail: a.severity };
    }));
    rows.sort(function (a, b) { return (b.created_at || "").localeCompare(a.created_at || ""); });
    rows = rows.slice(0, 20);
    if (!rows.length) return '<p class="muted">No activity yet.</p>';
    return '<div class="tablewrap"><table><thead><tr><th>When</th><th>Type</th><th>Field</th><th>Detail</th></tr></thead><tbody>' +
      rows.map(function (r) {
        return "<tr><td>" + esc((r.created_at || "").replace("T", " ").slice(0, 16)) + "</td><td>" +
          esc(r.type) + "</td><td>" + esc(r.field_name) + "</td><td>" + esc(r.detail) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

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
      "</div>" +
      '<div class="card" style="margin-top:1.25rem"><h3>Recent activity</h3>' + recentActivity() + "</div>";
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
      '<th>Language</th><th>Fields</th><th>Joined</th><th></th></tr></thead><tbody id="rows"></tbody></table></div>';
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
        "</td><td>" + f.field_count + "</td><td>" + esc((f.created_at || "").slice(0, 10)) + "</td>" +
        '<td><button class="danger small farmer-delete" data-id="' + esc(f.id) + '" data-name="' +
        esc(f.name) + '">Delete</button></td></tr>';
    }).join("") || '<tr><td colspan="7" class="muted">No farmers match.</td></tr>';
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
      return '<tr data-field-id="' + esc(fl.id) + '"><td>' + esc(fl.name) + "</td><td>" +
        '<input class="field-crop-input" value="' + esc(fl.current_crop || "") + '" style="width:9rem"></td><td>' +
        esc(fl.soil_type || "") + "</td><td>" + fmt(fl.area_ha) + "</td><td>" +
        fmt(fl.latitude, 4) + ", " + fmt(fl.longitude, 4) + "</td><td>" + esc(fl.sown_on || "") + "</td><td>" +
        (b ? b.count + " (avg " + fmt(b.mean_rating, 1) + ")" : "none") + "</td>" +
        '<td class="actions"><button class="small field-save">Save</button>' +
        '<button class="danger small field-delete" data-name="' + esc(fl.name) + '">Delete</button></td></tr>';
    }).join("");
    return '<a class="back" href="#/farmers">&larr; All farmers</a>' +
      "<h2>" + esc(f.name) + ' <span class="pill">' + esc(langName(f.preferred_language)) + "</span></h2>" +
      '<div class="card">' +
      '<form id="farmer-edit-form">' +
      '<div class="grid wide">' +
      '<label>Name <input name="name" value="' + esc(f.name) + '"></label>' +
      '<label>Phone <input name="phone" value="' + esc(f.phone || "") + '"></label>' +
      '<label>District <input name="district" value="' + esc(f.district || "") + '"></label>' +
      '<label>State <input name="state" value="' + esc(f.state || "") + '"></label>' +
      "</div>" +
      '<div class="actions"><button type="submit">Save changes</button>' +
      '<button type="button" id="farmer-delete-btn" class="danger">Delete farmer</button></div>' +
      '<p id="farmer-edit-msg" class="muted" hidden></p>' +
      "</form>" +
      '<dl class="kv" style="margin-top:1rem"><dt>Role</dt><dd>' + esc(f.role) +
      "</dd><dt>Joined</dt><dd>" + esc((f.created_at || "").slice(0, 10)) +
      '</dd></dl></div><h3 style="margin-top:1.25rem">Fields (' + fields.length + ")</h3>" +
      (fields.length
        ? '<div class="tablewrap"><table><thead><tr><th>Name</th><th>Crop</th><th>Soil</th><th>Area (ha)</th>' +
          "<th>Lat, Lon</th><th>Sown</th><th>Feedback</th><th></th></tr></thead><tbody>" + rows + "</tbody></table></div>"
        : '<p class="muted">This farmer has no fields.</p>') +
      scanTable(id) + advisoryList(id);
  }

  function wireFarmerDetail(id) {
    var form = $("farmer-edit-form");
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(form);
      var patch = { name: fd.get("name"), phone: fd.get("phone"), district: fd.get("district"), state: fd.get("state") };
      var msg = $("farmer-edit-msg");
      apiJSON("/v2/admin/farmers/" + encodeURIComponent(id), "PATCH", patch)
        .then(function (updated) {
          state.farmers = state.farmers.map(function (x) {
            return x.id === id ? Object.assign({}, x, updated) : x;
          });
          msg.hidden = false; msg.textContent = "Saved.";
          setTimeout(function () { msg.hidden = true; }, 2000);
        })
        .catch(function (e) { msg.hidden = false; msg.className = "error"; msg.textContent = e.message; });
    });

    $("farmer-delete-btn").addEventListener("click", function () {
      var f = state.farmers.filter(function (x) { return x.id === id; })[0];
      confirmDelete(f.name, function () {
        return api("/v2/admin/farmers/" + encodeURIComponent(id), { method: "DELETE" }).then(function () {
          location.hash = "#/farmers";
          return loadAll().then(route);
        });
      });
    });

    $("main").querySelectorAll("tr[data-field-id]").forEach(function (tr) {
      var fieldId = tr.dataset.fieldId;
      tr.querySelector(".field-save").addEventListener("click", function () {
        var crop = tr.querySelector(".field-crop-input").value;
        apiJSON("/v2/admin/fields/" + encodeURIComponent(fieldId), "PATCH", { current_crop: crop })
          .then(function (updated) {
            state.fields = state.fields.map(function (x) {
              return x.id === fieldId ? Object.assign({}, x, updated) : x;
            });
          })
          .catch(function (e) { alert(e.message); });
      });
      tr.querySelector(".field-delete").addEventListener("click", function () {
        var name = tr.dataset.name || tr.querySelector(".field-delete").dataset.name;
        confirmDelete(name, function () {
          return api("/v2/admin/fields/" + encodeURIComponent(fieldId), { method: "DELETE" }).then(function () {
            return loadAll().then(function () { $("main").innerHTML = farmerDetail(id); wireFarmerDetail(id); });
          });
        });
      });
    });
  }

  // ---- Bug reports (Module 50) ----
  function bugReportsView() {
    return "<h2>Bug Reports <span id=\"bug-live-pill\" class=\"pill\">connecting…</span></h2>" +
      '<div class="tablewrap"><table><thead><tr><th>When</th><th>Category</th><th>Message</th>' +
      "<th>Status</th><th></th></tr></thead><tbody id=\"bug-rows\"></tbody></table></div>";
  }

  function fillBugRows() {
    var rows = state.bugReports.slice().sort(function (a, b) {
      return (b.created_at || "").localeCompare(a.created_at || "");
    });
    $("bug-rows").innerHTML = rows.map(function (r) {
      return '<tr data-id="' + esc(r.id) + '"><td>' + esc((r.created_at || "").replace("T", " ").slice(0, 16)) +
        "</td><td>" + esc(r.category || "—") + "</td><td>" + esc(r.message || "—") + "</td><td>" +
        '<select class="bug-status">' + BUG_STATUSES.map(function (s) {
          return '<option value="' + s + '"' + (s === r.status ? " selected" : "") + ">" + s + "</option>";
        }).join("") + "</select></td>" +
        '<td><button class="danger small bug-delete" data-id="' + esc(r.id) + '">Delete</button></td></tr>';
    }).join("") || '<tr><td colspan="5" class="muted">No bug reports yet.</td></tr>';

    $("bug-rows").querySelectorAll(".bug-status").forEach(function (sel) {
      sel.addEventListener("change", function () {
        var id = sel.closest("tr").dataset.id;
        apiJSON("/v2/admin/bug-reports/" + encodeURIComponent(id), "PATCH", { status: sel.value })
          .then(function (updated) {
            state.bugReports = state.bugReports.map(function (x) { return x.id === id ? updated : x; });
          })
          .catch(function (e) { alert(e.message); });
      });
    });
    $("bug-rows").querySelectorAll(".bug-delete").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.dataset.id;
        confirmDelete(id, function () {
          return api("/v2/admin/bug-reports/" + encodeURIComponent(id), { method: "DELETE" }).then(function () {
            state.bugReports = state.bugReports.filter(function (x) { return x.id !== id; });
            fillBugRows();
          });
        });
      });
    });
  }

  function startBugStream() {
    if (bugStream) return;
    bugStream = new EventSource("/v2/admin/stream/bug-reports");
    bugStream.onopen = function () {
      var pill = $("bug-live-pill");
      if (pill) { pill.textContent = "live"; pill.classList.add("live"); }
    };
    bugStream.onmessage = function (ev) {
      var report = JSON.parse(ev.data);
      state.bugReports = [report].concat(state.bugReports.filter(function (r) { return r.id !== report.id; }));
      if (location.hash === "#/bugs") fillBugRows();
    };
    bugStream.onerror = function () {
      var pill = $("bug-live-pill");
      if (pill) { pill.textContent = "reconnecting…"; pill.classList.remove("live"); }
    };
  }

  // ---- Audit log (Module 50) ----
  function auditLogView() {
    return "<h2>Audit Log</h2>" +
      '<div class="tablewrap"><table><thead><tr><th>When</th><th>Action</th><th>Target</th></tr></thead><tbody>' +
      (state.auditLog.length
        ? state.auditLog.map(function (e) {
            return "<tr><td>" + esc((e.created_at || "").replace("T", " ").slice(0, 19)) + "</td><td>" +
              esc(e.action) + "</td><td>" + esc(e.target_type) + ":" + esc(e.target_id) + "</td></tr>";
          }).join("")
        : '<tr><td colspan="3" class="muted">No actions logged yet.</td></tr>') +
      "</tbody></table></div>";
  }

  function route() {
    if ($("app-view").hidden) return;
    if (bugStream && location.hash !== "#/bugs") { /* keep streaming in background */ }
    var h = location.hash || "#/";
    var main = $("main");
    ["nav-overview", "nav-farmers", "nav-bugs", "nav-audit"].forEach(function (id) { $(id).className = ""; });

    var m = /^#\/farmers\/(.+)$/.exec(h);
    if (m) {
      $("nav-farmers").className = "active";
      var id = decodeURIComponent(m[1]);
      main.innerHTML = farmerDetail(id);
      wireFarmerDetail(id);
      return;
    }
    if (h.indexOf("#/farmers") === 0) {
      $("nav-farmers").className = "active";
      main.innerHTML = farmerList();
      $("q").addEventListener("input", fillRows);
      $("lang").addEventListener("change", fillRows);
      $("rows").addEventListener("click", function (e) {
        if (e.target.closest(".farmer-delete")) return;
        var tr = e.target.closest("tr.row");
        if (tr) location.hash = "#/farmers/" + encodeURIComponent(tr.dataset.id);
      });
      $("rows").addEventListener("click", function (e) {
        var btn = e.target.closest(".farmer-delete");
        if (!btn) return;
        e.stopPropagation();
        confirmDelete(btn.dataset.name, function () {
          return api("/v2/admin/farmers/" + encodeURIComponent(btn.dataset.id), { method: "DELETE" })
            .then(function () { return loadAll().then(fillRows); });
        });
      });
      fillRows();
      return;
    }
    if (h === "#/bugs") {
      $("nav-bugs").className = "active";
      main.innerHTML = bugReportsView();
      api("/v2/admin/bug-reports").then(function (r) {
        state.bugReports = r.items;
        fillBugRows();
        startBugStream();
      }).catch(function (e) { main.innerHTML = '<p class="error">' + esc(e.message) + "</p>"; });
      return;
    }
    if (h === "#/audit") {
      $("nav-audit").className = "active";
      main.innerHTML = '<p class="muted">Loading…</p>';
      api("/v2/admin/audit-log").then(function (r) {
        state.auditLog = r.items;
        main.innerHTML = auditLogView();
      }).catch(function (e) { main.innerHTML = '<p class="error">' + esc(e.message) + "</p>"; });
      return;
    }
    $("nav-overview").className = "active";
    main.innerHTML = overview();
  }

  window.addEventListener("hashchange", route);

  // An existing session cookie skips the login screen.
  loadAll().then(showApp).catch(function (e) {
    showLogin(e.code === 401 ? "" : "Cannot reach the backend. Is it running?");
  });
})();
