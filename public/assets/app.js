/** HeatGuard dashboard. Displays planner JSON only — does not calculate OSHA risk. */
const API = "";

let state = {
  workload: "heavy",
  acclimatized: false,
  extraPpe: false,
  planner: null,
  selectedSiteId: "brickell",
  selectedHourLocal: null,
};

let leafletMap = null;
let leafletLayer = null;

const SHORT_NAME = {
  brickell: "Brickell",
  miami_beach: "Beach",
  doral: "Doral",
  coconut_grove: "Grove",
  little_haiti: "Haiti",
};

const fmt = (v, suffix = "") =>
  v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : `${Number(v).toFixed(1)}${suffix}`;

function plannerQuery() {
  const params = new URLSearchParams({
    workload: state.workload,
    acclimatized: String(state.acclimatized),
    extra_ppe: String(state.extraPpe),
  });
  if (state.selectedHourLocal) params.set("hour_local", state.selectedHourLocal);
  return params.toString();
}

function hourLabel(iso) {
  if (!iso) return "?";
  const m = String(iso).match(/T(\d{2}):/);
  if (!m) return "?";
  const h = parseInt(m[1], 10);
  if (h === 0) return "12a";
  if (h === 12) return "12";
  return h > 12 ? String(h - 12) : String(h);
}

function clockLabel(iso) {
  if (!iso) return "—";
  const m = String(iso).match(/T(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]}` : hourLabel(iso);
}

function dateLabel(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function riskClass(level) {
  if (level === "green") return "risk-green";
  if (level === "amber") return "risk-amber";
  if (level === "red") return "risk-red";
  return "risk-unknown";
}

function riskLetter(level) {
  if (level === "green") return "G";
  if (level === "amber") return "A";
  if (level === "red") return "R";
  return "U";
}

function riskColor(level) {
  if (level === "green") return "#22c55e";
  if (level === "amber") return "#f59e0b";
  if (level === "red") return "#ef4444";
  return "#64748b";
}

function riskTitle(level) {
  const map = {
    green: "Green — below Action Limit",
    amber: "Amber — between AL and TLV",
    red: "Red — at/above TLV",
    unknown: "Unknown — missing data",
  };
  return map[level] || level || "unknown";
}

async function fetchJson(path, options) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    let extra = "";
    try {
      const body = await res.json();
      const detail = body.detail;
      extra = detail
        ? ` — ${typeof detail === "string" ? detail : JSON.stringify(detail)}`
        : "";
    } catch (_) {
      extra = res.statusText ? ` ${res.statusText}` : "";
    }
    throw new Error(`${path} → ${res.status}${extra}`);
  }
  return res.json();
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.classList.toggle("error", isError);
}

function selectedSite() {
  return (state.planner?.sites || []).find((s) => s.id === state.selectedSiteId);
}

function hourOnSite(site, hourLocal) {
  if (!site?.hours?.length) return null;
  if (hourLocal) {
    return site.hours.find((h) => h.hour_local === hourLocal)
      || site.hours.find((h) => String(h.hour_local || "").slice(0, 13) === String(hourLocal).slice(0, 13))
      || null;
  }
  return site.hours.find((h) => String(h.hour_local || "").includes("T10:")) || site.hours[0];
}

function selectedHourRow(site) {
  return hourOnSite(site, state.selectedHourLocal);
}

function matrixHours() {
  const sites = state.planner?.sites || [];
  const seen = [];
  const keys = new Set();
  for (const site of sites) {
    for (const h of site.hours || []) {
      const key = String(h.hour_local || "").slice(0, 13);
      if (!keys.has(key)) {
        keys.add(key);
        seen.push(h.hour_local);
      }
    }
  }
  return seen;
}

function pickDefaultHour() {
  const hours = matrixHours();
  const ten = hours.find((h) => String(h).includes("T10:"));
  return ten || hours[0] || null;
}

async function loadPlanner() {
  document.body.classList.add("loading");
  setStatus("Loading planner…");
  try {
    state.planner = await fetchJson(`/planner?${plannerQuery()}`);
    if (!state.planner.sites?.some((s) => s.id === state.selectedSiteId)) {
      state.selectedSiteId = state.planner.sites?.[0]?.id || "brickell";
    }
    if (!state.selectedHourLocal || !hourOnSite(selectedSite(), state.selectedHourLocal)) {
      state.selectedHourLocal = pickDefaultHour();
    }
    renderAll();
    const mode = (state.planner.data?.mode || "unknown").toUpperCase();
    setStatus(
      `${state.planner.sites?.length || 0} sites · ${mode} · ${state.workload}` +
        (state.planner.threshold_flip?.decision ? ` · ${state.planner.threshold_flip.decision}` : "")
    );
  } catch (err) {
    setStatus(`Failed to load data: ${err.message}`, true);
  } finally {
    document.body.classList.remove("loading");
  }
}

function renderCommandStrip() {
  const site = selectedSite();
  const hour = selectedHourRow(site);
  const stamp = hour?.hour_local || pickDefaultHour();
  document.getElementById("plan-date").textContent = dateLabel(stamp);

  const rawMode = state.planner?.data?.mode || "unknown";
  const modeEl = document.getElementById("data-mode");
  const label = rawMode === "fixture" ? "BACKUP" : rawMode === "live" ? "LIVE" : rawMode.toUpperCase();
  modeEl.textContent = label;
  modeEl.className = `mode-chip ${rawMode === "fixture" ? "backup" : rawMode}`;

  const plan =
    state.planner?.threshold_flip?.decision
    || state.planner?.shift_plan?.move_work?.detail
    || state.planner?.todays_actions?.[0]?.detail
    || state.planner?.comparison_at_10am?.answer
    || "No plan yet — load site hours.";
  document.getElementById("one-sentence-plan").textContent = plan;

  document.querySelectorAll(".workload-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.workload === state.workload);
  });
  const acc = document.getElementById("acclimatized-toggle");
  if (acc) acc.checked = state.acclimatized;
  const ppe = document.getElementById("extra-ppe-toggle");
  if (ppe) ppe.checked = state.extraPpe;
}

function polygonCoords(site) {
  const feat = site?.polygon_aoi?.features?.[0];
  const ring = feat?.geometry?.coordinates?.[0];
  if (!ring) return null;
  return ring.map(([lon, lat]) => [lat, lon]);
}

function renderMap() {
  const el = document.getElementById("site-map");
  if (!el || !window.L) return;
  if (!leafletMap) {
    leafletMap = L.map(el, { scrollWheelZoom: false, attributionControl: true }).setView([25.78, -80.22], 11);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(leafletMap);
    leafletLayer = L.layerGroup().addTo(leafletMap);
  }
  leafletLayer.clearLayers();
  const bounds = [];
  for (const site of state.planner?.sites || []) {
    const latlngs = polygonCoords(site);
    if (!latlngs) continue;
    const hour = selectedHourRow(site);
    const level = hour?.level || site.now_risk || "unknown";
    const poly = L.polygon(latlngs, {
      color: "#e8eef5",
      weight: site.id === state.selectedSiteId ? 3 : 1,
      fillColor: riskColor(level),
      fillOpacity: 0.72,
    });
    const wbgt = fmt(hour?.effective_wbgt_c ?? hour?.screening_wbgt_c, "°C");
    const action = hour?.recommendation?.primary_action || "—";
    poly.bindPopup(
      `<strong>${site.name}</strong><br>` +
        `${riskLetter(hour?.level)} now ${hour?.level || "—"} · peak ${site.peak_risk || "—"}<br>` +
        `Screening WBGT ${wbgt}<br>${action}`
    );
    poly.on("click", () => {
      state.selectedSiteId = site.id;
      renderAll();
    });
    poly.addTo(leafletLayer);
    latlngs.forEach((p) => bounds.push(p));
  }
  if (bounds.length) leafletMap.fitBounds(bounds, { padding: [18, 18], maxZoom: 12 });
  setTimeout(() => leafletMap.invalidateSize(), 80);
}

function renderMatrix() {
  const root = document.getElementById("matrix");
  const hours = matrixHours();
  const sites = state.planner?.sites || [];
  if (!sites.length || !hours.length) {
    root.textContent = "No hour grid yet.";
    return;
  }
  const head = hours.map((h) => `<th>${hourLabel(h)}</th>`).join("");
  const rows = sites.map((site) => {
    const cells = hours.map((hl) => {
      const hour = hourOnSite(site, hl);
      const level = hour?.level || "unknown";
      const selected = site.id === state.selectedSiteId && hour?.hour_local === selectedHourRow(site)?.hour_local;
      return `<td><button type="button" class="matrix-cell ${riskClass(level)}${selected ? " selected" : ""}" data-site="${site.id}" data-hour="${hour?.hour_local || hl}" title="${site.name} ${clockLabel(hour?.hour_local)} ${level}">${riskLetter(level)}</button></td>`;
    }).join("");
    const rowSel = site.id === state.selectedSiteId ? " selected-row" : "";
    return `<tr class="${rowSel}"><th class="site-head">${SHORT_NAME[site.id] || site.name}</th>${cells}</tr>`;
  }).join("");
  root.innerHTML = `<table><thead><tr><th class="site-head"></th>${head}</tr></thead><tbody>${rows}</tbody></table>`;
  root.querySelectorAll(".matrix-cell").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedSiteId = btn.dataset.site;
      state.selectedHourLocal = btn.dataset.hour;
      renderAll();
    });
  });
}

function renderActions() {
  const root = document.getElementById("actions-list");
  const preferred = ["do_this_morning", "pause_shade_window", "move_work"];
  const all = state.planner?.todays_actions || [];
  const picked = [];
  for (const code of preferred) {
    const hit = all.find((a) => a.code === code);
    if (hit) picked.push(hit);
  }
  for (const a of all) {
    if (picked.length >= 3) break;
    if (!picked.includes(a)) picked.push(a);
  }
  const actions = picked.slice(0, 3);
  if (!actions.length) {
    root.innerHTML = "<p>No actions generated yet.</p>";
    return;
  }
  root.innerHTML = "";
  actions.forEach((a, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "action-card";
    const siteName = SHORT_NAME[a.site_id] || a.site_id || "site";
    const wl = a.workload || state.workload;
    btn.innerHTML = `
      <div class="kicker">${i + 1}. ${a.title}</div>
      <div>${siteName} · ${clockLabel(a.hour_local)} · ${wl}</div>
      <div class="detail">${a.detail || ""}</div>
    `;
    btn.onclick = () => {
      if (a.site_id) state.selectedSiteId = a.site_id;
      if (a.hour_local) state.selectedHourLocal = a.hour_local;
      renderAll();
    };
    root.appendChild(btn);
  });
}

function renderDetail() {
  const site = selectedSite();
  if (!site) return;
  const hour = selectedHourRow(site);
  if (hour?.hour_local) state.selectedHourLocal = hour.hour_local;
  document.getElementById("site-title").textContent =
    `${site.name} · ${clockLabel(hour?.hour_local)} · ${state.workload}`;
  document.getElementById("site-surface").textContent = site.surface || "";

  const level = hour?.level || "unknown";
  document.getElementById("risk-hero").innerHTML =
    `<span class="risk-mark ${riskClass(level)}">${riskLetter(level)}</span>` +
    `<span>${riskTitle(level)}</span>`;

  document.getElementById("action-detail").textContent =
    hour?.recommendation?.primary_action || "No recommendation for this hour.";

  const wbgt = hour?.effective_wbgt_c ?? hour?.screening_wbgt_c;
  const al = hour?.action_limit_c;
  const tlv = hour?.tlv_c;
  document.getElementById("wbgt-row").innerHTML =
    `Screening WBGT <strong>${fmt(wbgt, "°C")}</strong>` +
    ` · OSHA ${state.workload} AL ${fmt(al, "°C")} / TLV ${fmt(tlv, "°C")}` +
    (hour?.work_rest?.code ? ` · work/rest ${hour.work_rest.code}` : "");

  document.getElementById("stat-min").textContent = fmt(hour?.temp_c_min, "°");
  document.getElementById("stat-mean").textContent = fmt(hour?.temp_c_mean, "°");
  document.getElementById("stat-hot").textContent = fmt(hour?.screening_air_temp_c ?? hour?.temp_c_p90 ?? hour?.temp_c_max, "°");

  const cityEl = document.getElementById("city-contrast");
  const city = hour?.city_temp_c ?? state.planner?.city_contrast?.city_temp_c;
  const delta = hour?.site_minus_city_c;
  if (city == null && delta == null) {
    cityEl.textContent = "City vs site unavailable for this hour.";
  } else {
    const deltaTxt = delta == null ? "" : ` · site ${delta >= 0 ? "+" : ""}${Number(delta).toFixed(1)}°C vs city`;
    cityEl.textContent = `Miami city ${fmt(city, "°C")} vs site mean ${fmt(hour?.temp_c_mean, "°C")}${deltaTxt} · not used in OSHA risk`;
  }

  const wr = hour?.work_rest || {};
  document.getElementById("why-color-body").innerHTML = `
    <p>${hour?.reason || "No screening reason for this hour."}</p>
    <p>Ta hotspot ${fmt(hour?.screening_air_temp_c, "°C")} (${hour?.screening_air_temp_source || "—"})
    · Tw ${fmt(hour?.wet_bulb_temperature_celsius, "°C")}
    · clothing CAF ${fmt(hour?.clothing_adjustment_c, "°C")}
    · ${hour?.method || "screening_wbgt_estimate"}.</p>
    <p>Feels like ${fmt(hour?.feels_like_c ?? hour?.apparent_temperature_celsius, "°C")} is display-only.
    ${wr.code ? `ACGIH ${wr.code} (${wr.allocation || ""}).` : ""}
    Missing: ${(hour?.missing_fields || []).join(", ") || "none"}.</p>
  `;
}

function renderAiBullets() {
  const ul = document.getElementById("ai-bullets");
  const actions = (state.planner?.todays_actions || []).slice(0, 3);
  if (!actions.length) {
    ul.innerHTML = "<li>No calculated moves yet.</li>";
    return;
  }
  ul.innerHTML = actions.map((a) => `<li><strong>${a.title}.</strong> ${a.detail || ""}</li>`).join("");
}

function renderAll() {
  renderCommandStrip();
  renderMap();
  renderMatrix();
  renderActions();
  renderDetail();
  renderAiBullets();
}

async function askQuestion() {
  const input = document.getElementById("ask-input");
  const q = input.value.trim();
  if (!q) return;
  const answerEl = document.getElementById("ask-answer");
  answerEl.hidden = false;
  answerEl.textContent = "Thinking…";
  try {
    const data = await fetchJson("/planner/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        workload: state.workload,
        acclimatized: state.acclimatized,
        extra_ppe: state.extraPpe,
        hour_local: state.selectedHourLocal,
      }),
    });
    answerEl.textContent = data.answer || "No answer returned.";
  } catch (err) {
    answerEl.textContent = `Could not get an answer: ${err.message}`;
  }
}

document.querySelectorAll(".workload-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.workload = btn.dataset.workload;
    state.selectedHourLocal = null;
    loadPlanner();
  });
});
document.getElementById("ask-btn").addEventListener("click", askQuestion);
document.getElementById("ask-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") askQuestion();
});
document.getElementById("acclimatized-toggle")?.addEventListener("change", (e) => {
  state.acclimatized = Boolean(e.target.checked);
  loadPlanner();
});
document.getElementById("extra-ppe-toggle")?.addEventListener("change", (e) => {
  state.extraPpe = Boolean(e.target.checked);
  loadPlanner();
});

loadPlanner();
setupLiveRefresh();
window.addEventListener("resize", () => {
  if (leafletMap) setTimeout(() => leafletMap.invalidateSize(), 80);
});

async function setupLiveRefresh() {
  const btn = document.getElementById("refresh-live");
  const modeEl = document.getElementById("data-mode");
  try {
    const health = await fetchJson("/health");
    if (health.hosted_demo && modeEl) {
      modeEl.title =
        "Hosted demo uses a backup 12-hour Miami day so judging is reliable. FortyGuard heatmap jobs take longer than serverless allows. Run locally with FORTYGUARD_API_KEY to load today.";
    }
    if (!btn || !health.live_refresh_available) return;
    btn.hidden = false;
    btn.addEventListener("click", refreshLive);
  } catch (_) {
    /* health is optional; planner still loads */
  }
}

async function refreshLive() {
  const btn = document.getElementById("refresh-live");
  if (btn) btn.disabled = true;
  setStatus("Pulling today's FortyGuard forecast. This can take a few minutes and uses API credits.");
  try {
    const data = await fetchJson("/demo/refresh-live", { method: "POST" });
    setStatus(`Loaded ${data.loaded || 0} live hours.`);
    await loadPlanner();
  } catch (err) {
    setStatus(`Could not load today: ${err.message}`, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}
