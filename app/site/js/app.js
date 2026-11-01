/* NYC Open Play — static client. Reads data/index.json and data/parks/<id>.json.
   All times are New York wall-clock strings ("2026-11-02T18:00"); we do date math on
   them as if they were UTC so the viewer's own time zone never shifts anything. */
(function () {
  "use strict";

  var OPEN_HOUR = 8;            // NYC Parks map grid starts at 8:00am
  var DEFAULT_CLOSE = "22:00";  // used when the API gives no close time
  var SLOT = 30;
  var PARKS_MAP_URL = "https://www.nycgovparks.org/permits/field-and-court/map";
  var REPO_URL = "https://github.com/SoundsPrettyCool/nyc-open-play";
  var BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"];

  var app = document.getElementById("app");
  var state = { index: null, parks: {}, day: null, time: null, q: "", borough: "" };

  // ---------- time helpers ----------
  function toMin(s) {
    var y = +s.slice(0, 4), mo = +s.slice(5, 7), d = +s.slice(8, 10);
    var h = +s.slice(11, 13) || 0, mi = +s.slice(14, 16) || 0;
    return Date.UTC(y, mo - 1, d, h, mi) / 60000;
  }
  function hm(str) { var p = str.split(":"); return (+p[0]) * 60 + (+p[1]); }
  function dayStart(day) { return toMin(day + "T00:00"); }
  function nowNY() {
    var parts = {};
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23"
    }).formatToParts(new Date()).forEach(function (p) { parts[p.type] = p.value; });
    return { day: parts.year + "-" + parts.month + "-" + parts.day, min: (+parts.hour) * 60 + (+parts.minute) };
  }
  function fmtTime(minOfDay) {
    var h = Math.floor(minOfDay / 60) % 24, m = minOfDay % 60;
    var ap = h >= 12 ? "pm" : "am", h12 = h % 12 || 12;
    return h12 + (m ? ":" + String(m).padStart(2, "0") : "") + ap;
  }
  function fmtRange(a, b) { return fmtTime(a) + "–" + fmtTime(b); }
  function fmtDay(day, opts) {
    var d = new Date(day + "T12:00:00Z");
    return d.toLocaleDateString("en-US", Object.assign({ timeZone: "UTC" }, opts));
  }
  function addDays(day, n) {
    var d = new Date(day + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function windowDays() {
    var w = state.index.meta.window, out = [], d = w[0];
    while (d <= w[1]) { out.push(d); d = addDays(d, 1); }
    return out;
  }

  // ---------- availability ----------
  var STATE_LABEL = { open: "Open", booked: "Permitted", awaiting: "Permit awaiting approval",
    closed: "Closed", unknown: "No data" };
  var CODE = { b: "booked", a: "awaiting", p: "pending" };

  function closeMin(field, day) {
    var c = (field.close && field.close[day]) || DEFAULT_CLOSE;
    return hm(c);
  }
  // intervals: [{start,end,state}] ; returns {state, pending, interval}
  function stateAt(field, day, minOfDay) {
    var w = state.index.meta.window;
    if (field.status && field.status !== "Active") return { state: "closed" };
    if (field.data && field.data !== "ok") return { state: "unknown" };
    if (day < w[0] || day > w[1]) return { state: "unknown" };
    if (minOfDay < OPEN_HOUR * 60 || minOfDay >= closeMin(field, day)) return { state: "closed" };
    var t = dayStart(day) + minOfDay, pending = false;
    var ivs = field.intervals || [];
    for (var i = 0; i < ivs.length; i++) {
      var iv = ivs[i], s = toMin(iv.start), e = toMin(iv.end);
      if (t >= s && t < e) {
        if (iv.state === "pending") { pending = true; continue; }
        return { state: iv.state, interval: iv };
      }
    }
    return { state: "open", pending: pending };
  }
  // Compact index form: [id, data, [[start,end,code]]]
  function compactField(f) {
    return { id: f[0], data: f[1], status: "Active",
      intervals: f[2].map(function (x) { return { start: x[0], end: x[1], state: CODE[x[2]] }; }) };
  }
  function parkCounts(park, day, minOfDay) {
    var open = 0, known = 0;
    (park.f || []).forEach(function (f) {
      var s = stateAt(compactField(f), day, minOfDay).state;
      if (s !== "unknown") known++;
      if (s === "open") open++;
    });
    return { open: open, known: known, total: (park.f || []).length };
  }
  function freeWindows(field, day) {
    var out = [], start = null, end = closeMin(field, day);
    for (var m = OPEN_HOUR * 60; m < end; m += SLOT) {
      var s = stateAt(field, day, m).state;
      if (s === "open") { if (start === null) start = m; }
      else if (start !== null) { out.push([start, m]); start = null; }
    }
    if (start !== null) out.push([start, end]);
    return out;
  }

  // ---------- rendering helpers ----------
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function pill(cls, text) { return '<span class="pill s-' + cls + '">' + esc(text) + "</span>"; }
  function norm(s) { return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim(); }

  function masthead() {
    var meta = state.index.meta;
    var gen = new Date(meta.generated_at).toLocaleString("en-US", {
      timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
    });
    return '<header class="masthead">' +
      '<div class="kicker">Pickup soccer · NYC Parks fields</div>' +
      '<div class="brand"><h1><a href="#">NYC Open Play</a></h1></div>' +
      '<p class="muted small">Soccer fields with no permit at the time you pick. Permit data refreshed ' +
      esc(gen) + " ET, covering " + esc(fmtDay(meta.window[0], { month: "short", day: "numeric" })) + "–" +
      esc(fmtDay(meta.window[1], { month: "short", day: "numeric" })) + ".</p></header>";
  }
  function dayPicker() {
    return '<div class="days" role="group" aria-label="Day">' + windowDays().map(function (d) {
      return '<button type="button" class="day" data-day="' + d + '" aria-pressed="' + (d === state.day) + '">' +
        '<span>' + esc(fmtDay(d, { weekday: "short" })) + '</span><span class="num">' +
        esc(fmtDay(d, { day: "numeric" })) + "</span></button>";
    }).join("") + "</div>";
  }
  function timeSelect() {
    var opts = "";
    for (var m = OPEN_HOUR * 60; m < hm(DEFAULT_CLOSE); m += SLOT) {
      opts += '<option value="' + m + '"' + (m === state.time ? " selected" : "") + ">" + fmtTime(m) + "</option>";
    }
    return '<label class="field-label" for="time">Time<select id="time">' + opts + "</select></label>";
  }
  function footer() {
    return '<footer class="footer">' +
      "<p>Unofficial. Built from NYC Parks permit data and NYC Open Data. Fields can still be closed, under maintenance or in informal use, and permits can change after the last refresh. " +
      'Confirm on the <a href="' + PARKS_MAP_URL + '" target="_blank" rel="noopener">NYC Parks Field &amp; Court Permit Availability Map</a> before you go.</p>' +
      '<p><a href="' + REPO_URL + '" target="_blank" rel="noopener">Source on GitHub</a></p></footer>';
  }

  // ---------- home ----------
  function renderHome() {
    var q = norm(state.q), terms = q ? q.split(" ") : [];
    var parks = state.index.parks.filter(function (p) {
      if (state.borough && p.borough !== state.borough) return false;
      if (!terms.length) return true;
      var hay = norm([p.name].concat(p.aliases || []).join(" "));
      return terms.every(function (t) { return hay.indexOf(t) !== -1; });
    }).map(function (p) { return { p: p, c: parkCounts(p, state.day, state.time) }; });
    parks.sort(function (a, b) {
      return (b.c.open > 0) - (a.c.open > 0) || b.c.open - a.c.open || a.p.name.localeCompare(b.p.name);
    });
    var anyOpen = parks.filter(function (x) { return x.c.open > 0; }).length;

    var rows = parks.map(function (x) {
      var p = x.p, c = x.c, tag;
      if (!c.total) tag = pill("closed", "No active fields");
      else if (!c.known) tag = pill("unknown", "No data");
      else if (c.open) tag = pill("open", c.open + " of " + c.total + " open");
      else tag = pill("booked", c.total === 1 ? "Taken" : "All " + c.total + " taken");
      return '<a class="park-row" href="#park-' + esc(p.id) + '"><span class="park-name">' + esc(p.name) +
        "</span>" + tag + '<span class="park-meta">' + esc(p.borough) + " · " + c.total +
        (c.total === 1 ? " soccer field" : " soccer fields") + "</span></a>";
    }).join("");

    app.innerHTML = '<div class="wrap">' + masthead() +
      '<section class="controls" aria-label="Search">' +
      '<label class="field-label" for="q">Park<input id="q" type="search" placeholder="Try “Chelsea”, “Red Hook”, “Flushing Meadows”" value="' + esc(state.q) + '" autocomplete="off"></label>' +
      '<div class="row" role="group" aria-label="Borough">' +
      ['All'].concat(BOROUGHS).map(function (b) {
        var v = b === "All" ? "" : b;
        return '<button type="button" class="chip" data-borough="' + esc(v) + '" aria-pressed="' + (state.borough === v) + '">' + esc(b) + "</button>";
      }).join("") + "</div>" +
      dayPicker() + '<div class="row">' + timeSelect() + "</div></section>" +
      '<p class="count" aria-live="polite">' + anyOpen + " of " + parks.length + " parks have an open field on " +
      esc(fmtDay(state.day, { weekday: "long", month: "short", day: "numeric" })) + " at " + fmtTime(state.time) + ".</p>" +
      '<nav class="results" aria-label="Parks">' + (rows || '<p class="empty">No parks match. Check the spelling or clear the borough filter.</p>') + "</nav>" +
      footer() + "</div>";

    var qi = document.getElementById("q");
    qi.addEventListener("input", function () {
      state.q = qi.value; var pos = qi.selectionStart; renderHome();
      var n = document.getElementById("q"); n.focus(); try { n.setSelectionRange(pos, pos); } catch (e) {}
    });
    bindCommon(renderHome);
    app.querySelectorAll("[data-borough]").forEach(function (b) {
      b.addEventListener("click", function () { state.borough = b.getAttribute("data-borough"); renderHome(); });
    });
  }

  // ---------- park ----------
  function project(coordsList) {
    var xs = [], ys = [];
    coordsList.forEach(function (c) { xs.push(c[0]); ys.push(c[1]); });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    var k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
    var w = Math.max((maxX - minX) * k, 1e-5), h = Math.max(maxY - minY, 1e-5);
    var pad = 0.18, W = 600, scale = W / (w * (1 + 2 * pad)), H = h * (1 + 2 * pad) * scale;
    H = Math.max(Math.min(H, 600), 160);
    var ox = minX - w / k * pad, oy = maxY + h * pad;
    return { W: W, H: H, f: function (c) { return [((c[0] - ox) * k * scale).toFixed(1), ((oy - c[1]) * scale).toFixed(1)]; } };
  }
  function rings(geom) {
    if (!geom) return [];
    if (geom.type === "Polygon") return geom.coordinates;
    if (geom.type === "MultiPolygon") return [].concat.apply([], geom.coordinates);
    return [];
  }
  function pathOf(geom, P) {
    return rings(geom).map(function (r) { return "M" + r.map(function (c) { return P.f(c).join(","); }).join("L") + "Z"; }).join("");
  }
  function centroid(geom, P) {
    var pts = rings(geom)[0] || [], sx = 0, sy = 0;
    pts.forEach(function (c) { var p = P.f(c); sx += +p[0]; sy += +p[1]; });
    return pts.length ? [sx / pts.length, sy / pts.length] : null;
  }
  function mapSVG(park, states, selId) {
    var fieldPts = [];
    park.fields.forEach(function (f) { rings(f.geometry).forEach(function (r) { fieldPts = fieldPts.concat(r); }); });
    var pts = fieldPts.length ? fieldPts : [].concat.apply([], rings(park.boundary));
    if (!pts.length) return "";
    var P = project(pts);
    var parts = ['<svg viewBox="0 0 ' + P.W + " " + P.H.toFixed(0) + '" role="img" aria-label="Map of ' + esc(park.name) + ' soccer fields">'];
    if (park.boundary) parts.push('<path class="map-park" d="' + pathOf(park.boundary, P) + '"></path>');
    park.fields.forEach(function (f) {
      if (!f.geometry) return;
      var st = states[f.id];
      parts.push('<path class="map-field f-' + st + (f.id === selId ? " sel" : "") + '" data-field="' + esc(f.id) +
        '" d="' + pathOf(f.geometry, P) + '"><title>' + esc(f.name + ": " + STATE_LABEL[st]) + "</title></path>");
    });
    park.fields.forEach(function (f) {
      var c = f.geometry && centroid(f.geometry, P);
      if (c) parts.push('<text class="map-label" x="' + c[0].toFixed(1) + '" y="' + c[1].toFixed(1) + '" text-anchor="middle" dominant-baseline="middle">' + esc(f.name) + "</text>");
    });
    parts.push("</svg>");
    return parts.join("");
  }
  function timeline(field, day) {
    var open = OPEN_HOUR * 60, close = closeMin(field, day), span = close - open, segs = "";
    function seg(a, b, cls) {
      a = Math.max(a, open); b = Math.min(b, close); if (b <= a) return "";
      return '<div class="seg ' + cls + '" style="left:' + ((a - open) / span * 100).toFixed(2) + "%;width:" + ((b - a) / span * 100).toFixed(2) + '%"></div>';
    }
    if (field.status !== "Active") segs = seg(open, close, "closed");
    else (field.intervals || []).forEach(function (iv) {
      if (iv.start.slice(0, 10) !== day) return;
      segs += seg(hm(iv.start.slice(11)), hm(iv.end.slice(11)) || 24 * 60, iv.state);
    });
    var now = state.time >= open && state.time < close
      ? '<div class="now-line" style="left:' + ((state.time - open) / span * 100).toFixed(2) + '%"></div>' : "";
    var ticks = "";
    for (var m = open; m <= close; m += 120) ticks += "<span>" + fmtTime(m).replace(":00", "") + "</span>";
    return '<div class="timeline" aria-hidden="true">' + segs + now + '</div><div class="ticks">' + ticks + "</div>";
  }
  function fieldCard(field, day, st, selId) {
    var meta = [field.surface, field.lit ? "Lights" : null, field.dimensions].filter(Boolean).join(" · ");
    var head = '<div class="field-head"><div><h3>' + esc(field.name) + '</h3><div class="muted small">' + esc(meta) +
      '</div></div>' + pill(st.state, (st.state === "open" && st.pending ? "Open · application pending" : STATE_LABEL[st.state]) +
      " at " + fmtTime(state.time)) + "</div>";
    if (field.status !== "Active") {
      return '<article class="field-card" id="f-' + esc(field.id) + '">' + head +
        '<p class="small muted">NYC Parks lists this field as ' + esc(field.status || "not active") + ".</p></article>";
    }
    if (field.data !== "ok") {
      return '<article class="field-card" id="f-' + esc(field.id) + '">' + head +
        '<p class="small muted">Permit data for this field couldn’t be loaded in the last refresh. Check the NYC Parks map.</p></article>';
    }
    var wins = freeWindows(field, day);
    var winText = wins.length ? "Open " + wins.map(function (w) { return fmtRange(w[0], w[1]); }).join(", ")
      : "No open time this day";
    var permits = (field.intervals || []).filter(function (iv) { return iv.start.slice(0, 10) === day; }).map(function (iv) {
      var label = iv.state === "booked" ? "" : iv.state === "awaiting" ? " (awaiting approval)" : " (application pending; still open)";
      var who = iv.holder ? esc(iv.holder) : "Applicant not shown";
      var extra = [iv.type, iv.permit ? "#" + iv.permit : null].filter(Boolean).join(" · ");
      return '<li><span class="data">' + fmtRange(hm(iv.start.slice(11)), hm(iv.end.slice(11)) || 1440) + '</span><span class="who">' +
        who + esc(label) + (extra ? ' <span class="muted">' + esc(extra) + "</span>" : "") +
        (iv.overlapping ? ' <span class="muted">· permit is for an overlapping field</span>' : "") + "</span></li>";
    }).join("");
    return '<article class="field-card' + (field.id === selId ? " sel" : "") + '" id="f-' + esc(field.id) + '">' + head +
      timeline(field, day) + '<p class="windows"><strong>' + esc(winText) + "</strong></p>" +
      (permits ? '<ul class="permits">' + permits + "</ul>" : '<p class="small muted">No permits this day.</p>') + "</article>";
  }

  function renderPark(id, selId) {
    var park = state.parks[id];
    if (!park) {
      app.innerHTML = '<div class="wrap">' + masthead() + '<p class="empty">Loading park…</p></div>';
      fetch("data/parks/" + encodeURIComponent(id) + ".json").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (p) { state.parks[id] = p; renderPark(id, selId); }).catch(function () {
        app.innerHTML = '<div class="wrap">' + masthead() + '<p class="empty">This park isn’t in the current data. <a href="#">Back to all parks</a>.</p></div>';
      });
      return;
    }
    var states = {}, open = 0, active = 0;
    park.fields.forEach(function (f) {
      var s = stateAt(f, state.day, state.time); states[f.id] = s.state;
      if (f.status === "Active") { active++; if (s.state === "open") open++; }
    });
    var summary = !active ? pill("closed", "No active soccer fields")
      : open ? pill("open", open + " of " + active + " open") : pill("booked", active === 1 ? "Taken" : "All " + active + " taken");
    var c = park.center;
    var dir = c ? "https://www.google.com/maps/dir/?api=1&destination=" + c[1] + "," + c[0] : null;
    var legend = '<div class="legend">' + pill("open", "Open") + pill("booked", "Permitted") +
      pill("awaiting", "Awaiting approval") + pill("closed", "Closed") + "</div>";

    app.innerHTML = '<div class="wrap">' + masthead() +
      '<a class="back" href="#">← All parks</a>' +
      '<section aria-labelledby="park-title" style="display:grid;gap:10px">' +
      '<h2 id="park-title">' + esc(park.name) + '</h2><div class="muted small">' + esc(park.borough) + "</div>" +
      '<div class="links">' + (dir ? '<a href="' + dir + '" target="_blank" rel="noopener">Directions</a>' : "") +
      '<a href="' + PARKS_MAP_URL + '" target="_blank" rel="noopener">Confirm on the NYC Parks map</a></div></section>' +
      '<section class="controls" aria-label="When">' + dayPicker() + '<div class="row">' + timeSelect() + "</div></section>" +
      '<div class="summary">' + summary + "<span>on " + esc(fmtDay(state.day, { weekday: "long", month: "short", day: "numeric" })) +
      " at " + fmtTime(state.time) + "</span></div>" +
      '<div class="map-card">' + mapSVG(park, states, selId) + legend + "</div>" +
      '<section class="fields" aria-label="Soccer fields">' +
      park.fields.map(function (f) { return fieldCard(f, state.day, stateAt(f, state.day, state.time), selId); }).join("") +
      "</section>" + footer() + "</div>";

    bindCommon(function () { renderPark(id, selId); });
    app.querySelectorAll("[data-field]").forEach(function (el) {
      el.addEventListener("click", function () {
        var fid = el.getAttribute("data-field");
        renderPark(id, fid);
        var card = document.getElementById("f-" + fid);
        if (card) card.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      });
    });
  }

  function bindCommon(rerender) {
    app.querySelectorAll("[data-day]").forEach(function (b) {
      b.addEventListener("click", function () { state.day = b.getAttribute("data-day"); rerender(); });
    });
    var t = document.getElementById("time");
    if (t) t.addEventListener("change", function () { state.time = +t.value; rerender(); });
  }

  // ---------- routing ----------
  function route() {
    var h = location.hash.replace(/^#/, "");
    var m = /^park-([A-Za-z0-9]+)$/.exec(h);
    if (m) renderPark(m[1]); else renderHome();
    window.scrollTo(0, 0);
  }
  function initTime() {
    var n = nowNY(), days = windowDays();
    state.day = days.indexOf(n.day) !== -1 ? n.day : days[0];
    var next = Math.ceil(n.min / SLOT) * SLOT;
    var inHours = state.day === n.day && next >= OPEN_HOUR * 60 && next < hm(DEFAULT_CLOSE);
    state.time = inHours ? next : 18 * 60;
  }

  fetch("data/index.json").then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (idx) {
    state.index = idx; initTime(); route();
    window.addEventListener("hashchange", route);
  }).catch(function () {
    app.innerHTML = '<div class="wrap"><h1>NYC Open Play</h1><p class="empty">The field data didn’t load. Refresh the page; if it keeps happening, the data refresh may have failed.</p></div>';
  });
})();
