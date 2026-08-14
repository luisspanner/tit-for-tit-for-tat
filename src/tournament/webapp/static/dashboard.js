"use strict";

const PALETTE = {
  text: "#e8e6e1",
  textSecondary: "#9ba0a8",
  textTertiary: "#767b83",
  grid: "#262b33",
  accent: "#d99a3f",
  cooperate: "#4fd1ae",
  defect: "#e2685a",
  provider: {
    classic: "#6b7280",
    groq: "#d99a3f",
    ollama_cloud: "#4d8fd1",
    ollama_local: "#6b7fa0",
    anthropic: "#9c7fd1",
  },
};

Chart.defaults.color = PALETTE.textSecondary;
Chart.defaults.borderColor = PALETTE.grid;
Chart.defaults.font.family = "IBM Plex Mono, ui-monospace, monospace";
Chart.defaults.font.size = 11;

function providerFromStrategyName(name) {
  if (name.startsWith("llm_claude")) return "anthropic";
  if (name.startsWith("llm_groq")) return "groq";
  if (name.startsWith("llm_ollama_cloud")) return "ollama_cloud";
  if (name.startsWith("llm_ollama_local")) return "ollama_local";
  return "classic";
}

function providerLabel(key) {
  return {
    classic: "classic",
    groq: "groq",
    ollama_cloud: "ollama cloud",
    ollama_local: "ollama local",
    anthropic: "anthropic",
  }[key];
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`${url} -> ${res.status}`);
  }
  return res.json();
}

/* ==========================================================================
   Router
   ========================================================================== */

const charts = {};
function destroyChart(id) {
  if (charts[id]) {
    charts[id].destroy();
    delete charts[id];
  }
}

const loaders = {
  standings: loadStandings,
  comparison: loadComparison,
  explorer: loadExplorer,
  spatial: loadSpatial,
  sweeps: loadSweeps,
  research: loadResearchQuestions,
  live: loadLive,
};

function showView(name) {
  document.querySelectorAll(".view").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  document.getElementById(`view-${name}`).classList.add("active");
  document.querySelector(`.nav-item[data-view="${name}"]`).classList.add("active");
  window.location.hash = name;
  const loader = loaders[name];
  if (loader) loader();
}

document.getElementById("nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".nav-item");
  if (btn) showView(btn.dataset.view);
});

window.addEventListener("DOMContentLoaded", () => {
  const initial = window.location.hash.replace("#", "") || "standings";
  showView(loaders[initial] ? initial : "standings");
});

/* ==========================================================================
   Standings
   ========================================================================== */

async function loadStandings() {
  const [standings, matches] = await Promise.all([getJSON("/api/standings"), getJSON("/api/matches")]);
  const tbody = document.querySelector("#standings-table tbody");
  tbody.innerHTML = "";
  document.getElementById("standings-takeaway").innerHTML = "";

  if (!standings) {
    tbody.innerHTML = `<tr><td colspan="4"><p class="empty-state">No round-robin has run yet. Start one from Live Run.</p></td></tr>`;
    destroyChart("standings");
    return;
  }

  const modelByStrategy = {};
  (matches || []).forEach((m) => {
    if (m.model_a) modelByStrategy[m.strategy_a] = m.model_a;
    if (m.model_b) modelByStrategy[m.strategy_b] = m.model_b;
  });

  standings.forEach((row, i) => {
    const provider = providerFromStrategyName(row.strategy);
    const model = modelByStrategy[row.strategy] || "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="rank">${i + 1}</td>
      <td class="strategy-name">${row.strategy}</td>
      <td>${model ? `<span class="badge provider-${provider.replace("_", "-")}">${model}</span>` : ""}</td>
      <td class="num">${row.total_score}</td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById("standings-takeaway").innerHTML = standingsTakeaway(standings, matches);

  destroyChart("standings");
  const ctx = document.getElementById("standings-chart");
  charts.standings = new Chart(ctx, {
    type: "bar",
    data: {
      labels: standings.map((r) => r.strategy),
      datasets: [
        {
          data: standings.map((r) => r.total_score),
          backgroundColor: standings.map((r) => PALETTE.provider[providerFromStrategyName(r.strategy)]),
          borderRadius: 3,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: PALETTE.grid } },
        y: { grid: { display: false }, ticks: { font: { size: 10 } } },
      },
    },
  });
}

/* ==========================================================================
   Model comparison
   ========================================================================== */

async function loadComparison() {
  const [matches, transcripts, catalog] = await Promise.all([
    getJSON("/api/matches"),
    getJSON("/api/transcripts?full=true"),
    getJSON("/api/model-catalog"),
  ]);

  destroyChart("sizeScore");
  destroyChart("sizeCoop");
  destroyChart("convergence");
  document.getElementById("comparison-takeaway").innerHTML = "";
  document.getElementById("last-round-takeaway").innerHTML = "";
  document.getElementById("heatmap-takeaway").innerHTML = "";

  if (!matches || !transcripts || transcripts.length === 0) {
    document.getElementById("heatmap-wrap").innerHTML =
      '<p class="empty-state">No LLM matches yet. Start a "LLM round robin" from Live Run to populate this view.</p>';
    lastRoundExperimentTakeaway().then((html) => {
      document.getElementById("last-round-takeaway").innerHTML = html;
    });
    return;
  }

  // --- aggregate per model: total score, cooperation rate, per-round cooperation ---
  const byModel = {}; // model -> {scoreSum, matches, coopMoves, totalMoves, perRound: {roundIndex: [coopCount, total]}}
  function ensure(model) {
    if (!byModel[model]) byModel[model] = { scoreSum: 0, matchCount: 0, coopMoves: 0, totalMoves: 0, perRound: {} };
    return byModel[model];
  }

  (matches || []).forEach((m) => {
    if (m.model_a) {
      const s = ensure(m.model_a);
      s.scoreSum += Number(m.score_a);
      s.matchCount += 1;
    }
    if (m.model_b) {
      const s = ensure(m.model_b);
      s.scoreSum += Number(m.score_b);
      s.matchCount += 1;
    }
  });

  transcripts.forEach((t) => {
    [
      [t.model_a, "move_a"],
      [t.model_b, "move_b"],
    ].forEach(([model, key]) => {
      if (!model) return;
      const s = ensure(model);
      t.moves.forEach(([roundIndex, moveA, moveB]) => {
        const move = key === "move_a" ? moveA : moveB;
        s.totalMoves += 1;
        if (move === "C") s.coopMoves += 1;
        if (!s.perRound[roundIndex]) s.perRound[roundIndex] = [0, 0];
        s.perRound[roundIndex][1] += 1;
        if (move === "C") s.perRound[roundIndex][0] += 1;
      });
    });
  });

  const models = Object.keys(byModel).sort();
  const seriesColors = models.map((_, i) => qualitativeColor(i));

  document.getElementById("comparison-takeaway").innerHTML = comparisonTakeaways(byModel, catalog);
  document.getElementById("heatmap-takeaway").innerHTML = heatmapTakeaway(matches);
  lastRoundExperimentTakeaway().then((html) => {
    document.getElementById("last-round-takeaway").innerHTML = html;
  });

  // --- size vs score ---
  destroyChart("sizeScore");
  charts.sizeScore = new Chart(document.getElementById("size-score-chart"), {
    type: "scatter",
    data: {
      datasets: models
        .filter((m) => catalog && catalog[m] != null)
        .map((m, i) => ({
          label: m,
          data: [{ x: catalog[m], y: byModel[m].scoreSum }],
          backgroundColor: seriesColors[i],
          pointRadius: 6,
        })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "size (billion params)" }, grid: { color: PALETTE.grid } },
        y: { title: { display: true, text: "total score" }, grid: { color: PALETTE.grid } },
      },
    },
  });

  // --- size vs cooperation rate ---
  destroyChart("sizeCoop");
  charts.sizeCoop = new Chart(document.getElementById("size-coop-chart"), {
    type: "scatter",
    data: {
      datasets: models
        .filter((m) => catalog && catalog[m] != null)
        .map((m, i) => ({
          label: m,
          data: [{ x: catalog[m], y: byModel[m].totalMoves ? byModel[m].coopMoves / byModel[m].totalMoves : 0 }],
          backgroundColor: seriesColors[i],
          pointRadius: 6,
        })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "size (billion params)" }, grid: { color: PALETTE.grid } },
        y: { title: { display: true, text: "cooperation rate" }, min: 0, max: 1, grid: { color: PALETTE.grid } },
      },
    },
  });

  // --- convergence: cooperation rate per round, one line per model ---
  const maxRound = Math.max(0, ...models.flatMap((m) => Object.keys(byModel[m].perRound).map(Number)));
  const roundLabels = Array.from({ length: maxRound + 1 }, (_, i) => i);
  destroyChart("convergence");
  charts.convergence = new Chart(document.getElementById("convergence-chart"), {
    type: "line",
    data: {
      labels: roundLabels,
      datasets: models.map((m, i) => ({
        label: m,
        data: roundLabels.map((r) => {
          const cell = byModel[m].perRound[r];
          return cell ? cell[0] / cell[1] : null;
        }),
        borderColor: seriesColors[i],
        backgroundColor: seriesColors[i],
        tension: 0.25,
        spanGaps: true,
        pointRadius: 0,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "round" }, grid: { color: PALETTE.grid } },
        y: { title: { display: true, text: "cooperation rate" }, min: 0, max: 1, grid: { color: PALETTE.grid } },
      },
    },
  });

  renderHeatmap(matches);
}

function qualitativeColor(i) {
  const hues = [38, 205, 265, 165, 12, 320, 95, 230];
  const hue = hues[i % hues.length];
  return `hsl(${hue}, 55%, 60%)`;
}

function renderHeatmap(matches) {
  const wrap = document.getElementById("heatmap-wrap");
  const llmMatches = matches.filter((m) => m.model_a && m.model_b);
  if (llmMatches.length === 0) {
    wrap.innerHTML = '<p class="empty-state">No model-vs-model matches yet.</p>';
    return;
  }
  const strategies = Array.from(new Set(llmMatches.flatMap((m) => [m.strategy_a, m.strategy_b]))).sort();
  const scoreFor = {};
  llmMatches.forEach((m) => {
    scoreFor[`${m.strategy_a}|${m.strategy_b}`] = Number(m.score_a);
    scoreFor[`${m.strategy_b}|${m.strategy_a}`] = Number(m.score_b);
  });
  const allScores = Object.values(scoreFor);
  const max = Math.max(...allScores, 1);

  let html = `<div class="heatmap" style="grid-template-columns: 210px repeat(${strategies.length}, 44px);">`;
  html += `<div></div>`;
  strategies.forEach((s) => (html += `<div class="heatmap-label" style="writing-mode: vertical-rl;" title="${s}">${s}</div>`));
  strategies.forEach((rowS) => {
    html += `<div class="heatmap-label" title="${rowS}">${rowS}</div>`;
    strategies.forEach((colS) => {
      const val = scoreFor[`${rowS}|${colS}`];
      if (val === undefined) {
        html += `<div class="heatmap-cell" style="background: var(--bg-inset); color: var(--text-tertiary);">-</div>`;
      } else {
        const t = val / max;
        const bg = `hsl(38, ${30 + t * 40}%, ${18 + t * 30}%)`;
        html += `<div class="heatmap-cell" style="background: ${bg};">${val}</div>`;
      }
    });
  });
  html += `</div>`;
  wrap.innerHTML = html;
}

/* ==========================================================================
   Matchup explorer
   ========================================================================== */

async function loadExplorer() {
  const list = await getJSON("/api/transcripts");
  const listEl = document.getElementById("transcript-list");
  listEl.innerHTML = "";

  if (!list || list.length === 0) {
    listEl.innerHTML = '<p class="empty-state">No transcripts yet.</p>';
    return;
  }

  list.forEach((t) => {
    const item = document.createElement("div");
    item.className = "transcript-list-item";
    item.dataset.key = t.match_key;
    item.innerHTML = `
      <span class="pair">${t.strategy_a} vs ${t.strategy_b}</span>
      <span class="score">${t.score_a} - ${t.score_b}</span>
    `;
    item.addEventListener("click", () => selectTranscript(t.match_key, item));
    listEl.appendChild(item);
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function selectTranscript(matchKey, itemEl) {
  document.querySelectorAll(".transcript-list-item").forEach((el) => el.classList.remove("selected"));
  itemEl.classList.add("selected");

  const t = await getJSON(`/api/transcripts/${encodeURIComponent(matchKey)}`);
  if (!t) return;

  document.getElementById("transcript-title").textContent = `${t.strategy_a} vs ${t.strategy_b}`;
  const detail = document.getElementById("transcript-detail");
  const rowsA = t.moves
    .map(([, a, , reasonA]) => `<span class="move-chip ${a.toLowerCase()}" title="${escapeHtml(reasonA || "")}">${a}</span>`)
    .join("");
  const rowsB = t.moves
    .map(([, , b, , reasonB]) => `<span class="move-chip ${b.toLowerCase()}" title="${escapeHtml(reasonB || "")}">${b}</span>`)
    .join("");
  detail.innerHTML = `
    <p class="mono" style="color: var(--text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-2);">
      ${t.model_a || t.strategy_a} — final score ${t.score_a}
    </p>
    <div class="move-sequence" style="margin-bottom: var(--space-6);">${rowsA}</div>
    <p class="mono" style="color: var(--text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-2);">
      ${t.model_b || t.strategy_b} — final score ${t.score_b}
    </p>
    <div class="move-sequence">${rowsB}</div>
  `;
}

/* ==========================================================================
   Spatial grid
   ========================================================================== */

async function loadSpatial() {
  const data = await getJSON("/api/spatial");
  destroyChart("spatial");
  const legendEl = document.getElementById("spatial-legend");
  const gifEl = document.getElementById("spatial-gif");
  gifEl.src = `/results/spatial_evolution.gif?t=${Date.now()}`;

  if (!data) {
    legendEl.innerHTML = "";
    document.getElementById("spatial-takeaway").innerHTML = "";
    return;
  }

  document.getElementById("spatial-takeaway").innerHTML = spatialTakeaway(data);
  legendEl.innerHTML = "";
  if (data.legend) {
    Object.entries(data.legend).forEach(([name, color]) => {
      const item = document.createElement("div");
      item.className = "legend-item";
      item.innerHTML = `<span class="legend-swatch" style="background:${color}"></span>${name}`;
      legendEl.appendChild(item);
    });
  }

  const final = data.summary[data.summary.length - 1].counts;
  const labels = Object.keys(final);
  charts.spatial = new Chart(document.getElementById("spatial-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          data: labels.map((l) => final[l]),
          backgroundColor: labels.map((l) => (data.legend && data.legend[l]) || PALETTE.accent),
          borderRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { font: { size: 9 }, maxRotation: 45, minRotation: 45 }, grid: { display: false } },
        y: { grid: { color: PALETTE.grid } },
      },
    },
  });
}

/* ==========================================================================
   Noise sweep & ecological
   ========================================================================== */

async function loadSweeps() {
  const [noise, eco] = await Promise.all([getJSON("/api/noise-sweep"), getJSON("/api/ecological")]);
  destroyChart("noise");
  destroyChart("ecological");
  document.getElementById("sweeps-takeaway").innerHTML = sweepsTakeaway(noise);

  if (noise) {
    // Python's str(0.0) == "0.0" but JS's String(0.0) == "0" - match keys by
    // numeric value instead of reconstructing the string.
    const keyForLevel = (lvl) => Object.keys(noise.round_robin).find((k) => Number(k) === lvl);
    const names = Object.keys(
      noise.round_robin[keyForLevel(noise.noise_levels[0])].reduce((acc, r) => {
        acc[r.strategy] = true;
        return acc;
      }, {})
    );
    charts.noise = new Chart(document.getElementById("noise-chart"), {
      type: "line",
      data: {
        labels: noise.noise_levels,
        datasets: names.map((name, i) => ({
          label: name,
          data: noise.noise_levels.map((lvl) => {
            const row = noise.round_robin[keyForLevel(lvl)].find((r) => r.strategy === name);
            return row ? row.total_score : null;
          }),
          borderColor: qualitativeColor(i),
          backgroundColor: qualitativeColor(i),
          tension: 0.2,
          pointRadius: 2,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: "noise rate" }, grid: { color: PALETTE.grid } },
          y: { title: { display: true, text: "total score" }, grid: { color: PALETTE.grid } },
        },
      },
    });
  }

  if (eco) {
    const names = Object.keys(eco[0]);
    const generations = eco.map((_, i) => i);
    charts.ecological = new Chart(document.getElementById("ecological-chart"), {
      type: "line",
      data: {
        labels: generations,
        datasets: names.map((name, i) => ({
          label: name,
          data: eco.map((gen) => gen[name]),
          borderColor: qualitativeColor(i),
          backgroundColor: qualitativeColor(i),
          tension: 0.15,
          pointRadius: 0,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: "generation" }, grid: { color: PALETTE.grid } },
          y: { title: { display: true, text: "population share" }, grid: { color: PALETTE.grid } },
        },
      },
    });
  }
}

/* ==========================================================================
   Research questions
   ========================================================================== */

async function loadResearchQuestions() {
  const [matches, transcripts, catalog] = await Promise.all([
    getJSON("/api/matches"),
    getJSON("/api/transcripts?full=true"),
    getJSON("/api/model-catalog"),
  ]);
  const rq2 = await evaluateRQ2();

  const evaluations = {
    rq1: evaluateRQ1(matches, transcripts || []),
    rq2,
    rq3: { status: "open", text: "Not yet built — no code path produces this comparison (see CLAUDE.md backlog)." },
    rq4: evaluateRQ4(matches, transcripts, catalog),
    rq5: evaluateRQ5(matches || [], catalog || {}),
  };

  const list = document.getElementById("research-questions-list");
  list.innerHTML = RESEARCH_QUESTIONS.map((rq) => {
    const evaluation = evaluations[rq.id];
    const link = rq.view
      ? `<button class="btn btn-link" onclick="showView('${rq.view}')">view evidence →</button>`
      : "";
    return `
      <div class="panel">
        <p class="panel-title">${rq.text}</p>
        <p class="takeaway-text">
          <span class="badge status-${evaluation.status}">${evaluation.status}</span>
          ${evaluation.text}
        </p>
        ${link}
      </div>
    `;
  }).join("");
}

/* ==========================================================================
   Live run
   ========================================================================== */

let activeEventSource = null;
let matchesCompleted = 0;
let repeatsCompleted = 0;

function setProgress(fraction) {
  document.getElementById("progress-fill").style.transform = `scaleX(${fraction})`;
}

async function loadLive() {
  const select = document.getElementById("experiment-select");
  updateLiveFormVisibility(select.value);

  const models = await getJSON("/api/configured-models");
  const container = document.getElementById("models-checkboxes");
  container.innerHTML = "";
  (models || []).forEach((model) => {
    const id = `model-checkbox-${model.replace(/[^a-zA-Z0-9]/g, "_")}`;
    const row = document.createElement("div");
    row.className = "checkbox-row";
    row.innerHTML = `<input type="checkbox" id="${id}" value="${escapeHtml(model)}" checked><label for="${id}">${escapeHtml(model)}</label>`;
    container.appendChild(row);
  });
  if (!models || models.length === 0) {
    container.innerHTML = '<p class="empty-state">No providers configured.</p>';
  }
}

function updateLiveFormVisibility(experiment) {
  const roundsField = document.getElementById("rounds-field");
  const repeatsField = document.getElementById("repeats-field");
  const includeClassicsRow = document.getElementById("include-classics-row");
  const modelsField = document.getElementById("models-field");
  const roundsInput = document.getElementById("rounds-input");
  const isRoundRobin = experiment === "llm_round_robin" || experiment === "classic_round_robin";
  const showModels = experiment === "llm_round_robin" || experiment === "last_round_experiment";
  const showRepeats = experiment === "last_round_experiment";
  roundsField.style.display = isRoundRobin || experiment === "last_round_experiment" ? "" : "none";
  repeatsField.style.display = showRepeats ? "" : "none";
  includeClassicsRow.style.display = experiment === "llm_round_robin" ? "" : "none";
  modelsField.style.display = showModels ? "" : "none";
  if (experiment === "llm_round_robin") roundsInput.value = 20;
  if (experiment === "classic_round_robin") roundsInput.value = 100;
  if (experiment === "last_round_experiment") roundsInput.value = 20;
}

document.getElementById("experiment-select").addEventListener("change", (e) => {
  updateLiveFormVisibility(e.target.value);
});

document.getElementById("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const experiment = document.getElementById("experiment-select").value;
  const roundsField = document.getElementById("rounds-field");
  const rounds = roundsField.style.display === "none" ? null : Number(document.getElementById("rounds-input").value);
  const includeClassics = document.getElementById("include-classics-checkbox").checked;
  const btn = document.getElementById("start-run-btn");

  const modelsField = document.getElementById("models-field");
  let models = null;
  if (modelsField.style.display !== "none") {
    const checkboxes = Array.from(document.querySelectorAll("#models-checkboxes input[type=checkbox]"));
    const checked = checkboxes.filter((c) => c.checked).map((c) => c.value);
    // All checked (the default) round-trips as null - the already-tested unfiltered path.
    if (checked.length < checkboxes.length) models = checked;
  }
  const repeatsField = document.getElementById("repeats-field");
  const repeats = repeatsField.style.display === "none" ? null : Number(document.getElementById("repeats-input").value);

  btn.disabled = true;
  const log = document.getElementById("event-log");
  log.innerHTML = "";
  matchesCompleted = 0;
  repeatsCompleted = 0;
  setProgress(0.08);
  document.getElementById("progress-text").textContent = "starting...";

  try {
    const res = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ experiment, rounds, include_classics: includeClassics, models, repeats }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      appendLogLine({ type: "run_error", error: body.detail || `HTTP ${res.status}` });
      btn.disabled = false;
      return;
    }
    const { run_id } = await res.json();
    setSidebarStatus("running", experiment);
    streamRun(run_id, btn, experiment);
  } catch (err) {
    appendLogLine({ type: "run_error", error: String(err) });
    btn.disabled = false;
  }
});

function streamRun(runId, btn, experiment) {
  if (activeEventSource) activeEventSource.close();
  const log = document.getElementById("event-log");
  log.innerHTML = "";
  const source = new EventSource(`/api/runs/${runId}/events`);
  activeEventSource = source;

  source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    appendLogLine(event);

    if (event.type === "match_start" || event.type === "match_end" || event.type === "match_error") {
      if (event.type !== "match_start") matchesCompleted += 1;
      document.getElementById("progress-text").textContent = `${matchesCompleted} matches completed`;
      setProgress(0.6);
    }

    if (event.type === "lre_repeat_end") {
      repeatsCompleted += 1;
      document.getElementById("progress-text").textContent = `${repeatsCompleted} repeats completed`;
      setProgress(Math.min(0.1 + repeatsCompleted * 0.05, 0.9));
    }

    if (event.type === "run_complete" || event.type === "run_error") {
      setProgress(1);
      const doneLabel =
        experiment === "last_round_experiment" ? `done — ${repeatsCompleted} repeats` : `done — ${matchesCompleted} matches`;
      document.getElementById("progress-text").textContent = event.type === "run_complete" ? doneLabel : "run failed";
      setSidebarStatus(event.type === "run_complete" ? "done" : "error");
      btn.disabled = false;
      source.close();
      // Refresh data-bearing views so a completed run shows up immediately.
      if (experiment === "last_round_experiment") {
        loadComparison();
      } else {
        loadStandings();
      }
    }
  };

  source.onerror = () => {
    source.close();
    btn.disabled = false;
  };
}

function appendLogLine(event) {
  const log = document.getElementById("event-log");
  if (log.querySelector(".empty-state")) log.innerHTML = "";
  const line = document.createElement("div");
  line.className = `log-line type-${event.type}`;
  const ts = new Date().toLocaleTimeString();
  line.innerHTML = `<span class="ts">${ts}</span><span>${formatEvent(event)}</span>`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

function formatEvent(event) {
  switch (event.type) {
    case "run_start":
      return `run_start experiment=${event.experiment} rounds=${event.rounds}`;
    case "match_start":
      return `match_start ${event.strategy_a} vs ${event.strategy_b}`;
    case "round":
      return `  round ${event.round_index}: ${event.strategy_a}=${event.move_a} ${event.strategy_b}=${event.move_b}`;
    case "match_end":
      return `match_end ${event.strategy_a} vs ${event.strategy_b} -> ${event.result.score_a}-${event.result.score_b}`;
    case "match_error":
      return `match_error ${event.strategy_a} vs ${event.strategy_b}: ${event.error}`;
    case "lre_repeat_start":
      return `  repeat_start ${event.model} vs ${event.opponent} #${event.repeat}`;
    case "lre_repeat_end":
      return `  repeat_end ${event.model} vs ${event.opponent} #${event.repeat}: ${event.moves.join("")}`;
    case "lre_model_done": {
      const told = (event.result.told.last_round_defect_rate * 100).toFixed(0);
      const untold = (event.result.untold.last_round_defect_rate * 100).toFixed(0);
      return `model_done ${event.model} told=${told}% untold=${untold}%`;
    }
    case "run_complete":
      return "run_complete";
    case "run_error":
      return `run_error: ${event.error}`;
    default:
      return JSON.stringify(event);
  }
}

function setSidebarStatus(status, label) {
  const dot = document.getElementById("sidebar-status-dot");
  const text = document.getElementById("sidebar-status-text");
  dot.className = `status-dot ${status}`;
  text.textContent = status === "running" ? `running ${label}` : status;
}
