const API = ""; // same origin when served by FastAPI

let state = {
  workload: "heavy",
  acclimatized: false,
  planner: null,
  selectedSiteId: "brickell",
  selectedHourLocal: null,
};

function plannerQuery() {
  const params = new URLSearchParams({
    workload: state.workload,
    acclimatized: String(state.acclimatized),
  });
  if (state.selectedHourLocal) params.set("hour_local", state.selectedHourLocal);
  return params.toString();
}

const fmt = (v, suffix = "") =>
  v === null || v === undefined ? "—" : `${Number(v).toFixed(1)}${suffix}`;

const hourLabel = (iso) => {
  if (!iso) return "?";
  const m = iso.match(/T(\d{2}):/);
  if (!m) return "?";
  const h = parseInt(m[1], 10);
  return h === 0 ? "12" : h > 12 ? String(h - 12) : String(h);
};

const riskClass = (level) => {
  if (level === "green") return "risk-green";
  if (level === "amber") return "risk-amber";
  if (level === "red") return "risk-red";
  return "risk-unknown";
};

const riskLabel = (level) => {
  const map = { green: "Green — lower screening risk", amber: "Amber — elevated risk", red: "Red — restrict outdoor work", unknown: "Unknown — missing data" };
  return map[level] || level;
};

async function fetchJson(path, options) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
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

function selectedHourRow(site) {
  if (!site?.hours?.length) return null;
  if (state.selectedHourLocal) {
    return site.hours.find((h) => h.hour_local === state.selectedHourLocal) || site.hours[0];
  }
  const ten = site.hours.find((h) => h.hour_local?.includes("T10:"));
  return ten || site.hours[Math.min(4, site.hours.length - 1)];
}

function renderSiteGrid() {
  const grid = document.getElementById("site-grid");
  grid.innerHTML = "";
  for (const site of state.planner?.sites || []) {
    const hour = selectedHourRow(site) || site.hours?.[0];
    const card = document.createElement("button");
    card.type = "button";
    card.className = `site-card${site.id === state.selectedSiteId ? " selected" : ""}`;
    card.innerHTML = `
      <div class="name"><span class="risk-dot ${riskClass(site.now_risk || site.current_risk)}"></span>${site.name}</div>
      <div class="meta">${site.city}</div>
      <div class="temp">${fmt(hour?.screening_air_temp_c ?? hour?.temp_c_mean, "°C")}</div>
      <div class="meta">Now ${site.now_risk || site.current_risk || "—"} · Peak ${site.peak_risk || "—"}</div>
    `;
    card.onclick = () => {
      state.selectedSiteId = site.id;
      state.selectedHourLocal = null;
      renderAll();
    };
    grid.appendChild(card);
  }
}

function renderDetail() {
  const site = selectedSite();
  if (!site) return;
  const hour = selectedHourRow(site);
  if (hour) state.selectedHourLocal = hour.hour_local;

  document.getElementById("site-title").textContent = site.name.toUpperCase();
  document.getElementById("site-surface").textContent = site.surface || "";
  document.getElementById("temp-hero").innerHTML = `${fmt(hour?.screening_air_temp_c ?? hour?.temp_c_mean)} <span>°C hotspot</span>`;
  document.getElementById("stat-min").textContent = fmt(hour?.temp_c_min, "°");
  document.getElementById("stat-mean").textContent = fmt(hour?.temp_c_mean, "°");
  document.getElementById("stat-max").textContent = fmt(hour?.temp_c_max, "°");

  const riskEl = document.getElementById("risk-detail");
  const wr = hour?.work_rest || hour?.recommendation?.work_rest || {};
  const wrLabel = wr.code ? `Work/rest ${wr.code}` : "Work/rest —";
  riskEl.innerHTML = `
    <div class="level"><span class="risk-dot ${riskClass(hour?.level)}"></span>${riskLabel(hour?.level)}</div>
    <p style="margin:0.5rem 0 0;font-size:0.85rem;color:var(--muted)">${hour?.reason || "No risk reason available."}</p>
    <p style="margin:0.35rem 0 0;font-size:0.8rem;color:var(--muted)">${wrLabel}${wr.allocation ? ` · ${wr.allocation}` : ""}</p>
    <p style="margin:0.35rem 0 0;font-size:0.8rem;color:var(--muted)">Effective WBGT: ${fmt(hour?.effective_wbgt_c ?? hour?.screening_wbgt_c, "°C")} · Hotspot Ta: ${fmt(hour?.screening_air_temp_c, "°C")} (${hour?.screening_air_temp_source || "—"}) · Mean: ${fmt(hour?.temp_c_mean, "°C")} · Wet bulb: ${fmt(hour?.wet_bulb_temperature_celsius, "°C")}</p>
  `;

  const action = hour?.recommendation?.primary_action || "No recommendation for this hour.";
  document.getElementById("action-detail").textContent = action;

  const timeline = document.getElementById("timeline");
  timeline.innerHTML = "";
  for (const h of site.hours || []) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = `hour-cell${h.hour_local === hour?.hour_local ? " selected" : ""}`;
    cell.innerHTML = `
      <div class="label">${hourLabel(h.hour_local)}</div>
      <div class="badge ${riskClass(h.level)}" title="${h.level}"></div>
    `;
    cell.onclick = () => {
      state.selectedHourLocal = h.hour_local;
      renderDetail();
      renderTimelineSelection();
    };
    timeline.appendChild(cell);
  }
}

function renderTimelineSelection() {
  document.querySelectorAll(".hour-cell").forEach((el) => el.classList.remove("selected"));
  const site = selectedSite();
  const hour = selectedHourRow(site);
  document.querySelectorAll(".hour-cell").forEach((el, i) => {
    if (site?.hours?.[i]?.hour_local === hour?.hour_local) el.classList.add("selected");
  });
}

function renderActions() {
  const list = document.getElementById("actions-list");
  list.innerHTML = "";
  const actions = state.planner?.todays_actions || [];
  if (!actions.length) {
    list.innerHTML = "<li>No actions generated yet.</li>";
    return;
  }
  for (const a of actions.slice(0, 8)) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${a.title}</strong><br><span style="color:var(--muted)">${a.detail || ""}</span>`;
    list.appendChild(li);
  }
}

function renderWorkloadButtons() {
  document.querySelectorAll(".workload-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.workload === state.workload);
  });
}

function renderAssumption() {
  const el = document.getElementById("assumption-banner");
  const label = state.planner?.assumption?.label;
  if (el) el.textContent = label || "Planning assumption: unacclimatized / new hires present.";
  const toggle = document.getElementById("acclimatized-toggle");
  if (toggle) toggle.checked = state.acclimatized;
}

async function loadBrief() {
  try {
    const data = await fetchJson(`/planner/brief?${plannerQuery()}`);
    document.getElementById("brief-text").textContent = data.brief || "";
  } catch {
    document.getElementById("brief-text").textContent = "Brief unavailable.";
  }
}

async function loadPlanner() {
  document.body.classList.add("loading");
  setStatus("Loading planner data…");
  try {
    state.planner = await fetchJson(`/planner?${plannerQuery()}`);
    if (!state.planner.sites?.some((s) => s.id === state.selectedSiteId)) {
      state.selectedSiteId = state.planner.sites?.[0]?.id || "brickell";
    }
    renderAll();
    await loadBrief();
    const dataMode = (state.planner.data?.mode || "unknown").toUpperCase();
    const crew = state.acclimatized ? "acclimatized" : "unacclimatized";
    setStatus(
      `Loaded ${state.planner.sites?.length || 0} sites · ${dataMode} data · ${crew} · ${state.workload} · ` +
        (state.planner.comparison_at_10am?.answer || state.planner.comparison?.answer || "ready")
    );
  } catch (err) {
    setStatus(`Failed to load data: ${err.message}. Is the API running?`, true);
  } finally {
    document.body.classList.remove("loading");
  }
}

function renderAll() {
  renderAssumption();
  renderSiteGrid();
  renderDetail();
  renderActions();
  renderWorkloadButtons();
}

async function askQuestion() {
  const input = document.getElementById("ask-input");
  const q = input.value.trim();
  if (!q) return;
  const answerEl = document.getElementById("ask-answer");
  answerEl.textContent = "Thinking…";
  try {
    const data = await fetchJson("/planner/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        workload: state.workload,
        acclimatized: state.acclimatized,
        hour_local: state.selectedHourLocal,
      }),
    });
    answerEl.hidden = false;
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

document.getElementById("reload-btn").addEventListener("click", loadPlanner);
document.getElementById("ask-btn").addEventListener("click", askQuestion);
document.getElementById("ask-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") askQuestion();
});
document.getElementById("acclimatized-toggle")?.addEventListener("change", (e) => {
  state.acclimatized = Boolean(e.target.checked);
  loadPlanner();
});

loadPlanner();
