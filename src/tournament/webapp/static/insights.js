"use strict";

/* ==========================================================================
   Deterministic "so-what" takeaway generation.

   Everything here is fixed threshold logic over numbers the views already
   compute - no LLM call, no server round-trip. See CLAUDE.md's "so-what
   layer" build-order entry for why: the numbers are simple enough that a
   rule table covers them today, and a per-view LLM call would add latency/
   cost for zero benefit at this data volume. Revisit only once the rules
   below stop being able to say anything useful (see CLAUDE.md backlog).
   ========================================================================== */

const MIN_N = 5; // matches run_last_round_experiment.py's default REPEATS

function nBadge(n) {
  const low = n < MIN_N;
  return `<span class="badge${low ? " n-low" : ""}">n=${n}</span>`;
}

function pct(x) {
  return `${(x * 100).toFixed(0)}%`;
}

function takeawayPanel(title, html) {
  return `<div class="panel"><p class="panel-title">${title}</p><p class="takeaway-text">${html}</p></div>`;
}

/* ==========================================================================
   Standings
   ========================================================================== */

function standingsTakeaway(standings, matches) {
  const n = (matches || []).length;
  if (n < MIN_N) {
    return takeawayPanel("Takeaway", `Only ${nBadge(n)} matches recorded — too few to call a leader yet.`);
  }
  if (!standings || standings.length < 2) {
    return takeawayPanel("Takeaway", `Not enough strategies with results yet (${nBadge(n)}).`);
  }
  const [top, second] = standings;
  const margin = top.total_score > 0 ? (top.total_score - second.total_score) / top.total_score : 0;
  if (margin > 0.2) {
    return takeawayPanel(
      "Takeaway",
      `<code class="strategy-name">${top.strategy}</code> leads by ${pct(margin)} over <code class="strategy-name">${second.strategy}</code> across ${nBadge(n)} matches.`
    );
  }
  return takeawayPanel(
    "Takeaway",
    `Scores are close across the top strategies — <code class="strategy-name">${top.strategy}</code> and <code class="strategy-name">${second.strategy}</code> are within ${pct(margin)} of each other (${nBadge(n)}). No single strategy clearly dominates this run.`
  );
}

/* ==========================================================================
   Model comparison
   ========================================================================== */

function comparisonTakeaways(byModel, catalog) {
  const models = Object.keys(byModel).sort();
  const lines = [];

  // per-model cooperation + endgame-collapse detection
  models.forEach((m) => {
    const s = byModel[m];
    if (s.totalMoves < MIN_N) {
      lines.push(`<code class="strategy-name">${m}</code>: not enough moves yet (${nBadge(s.totalMoves)}).`);
      return;
    }
    const overallCoop = s.coopMoves / s.totalMoves;
    const rounds = Object.keys(s.perRound).map(Number);
    const maxRound = rounds.length ? Math.max(...rounds) : null;
    let sentence = `<code class="strategy-name">${m}</code> cooperated in ${pct(overallCoop)} of moves (${nBadge(s.totalMoves)})`;
    if (maxRound !== null) {
      const [coopAtLast, totalAtLast] = s.perRound[maxRound];
      if (totalAtLast < 2) {
        sentence += ` — final-round rate not shown, only ${totalAtLast} observation(s) at round ${maxRound}.`;
      } else {
        const lastRate = coopAtLast / totalAtLast;
        if (overallCoop - lastRate >= 0.3) {
          sentence += `, but dropped to ${pct(lastRate)} in the final round (round ${maxRound}, n=${totalAtLast}).`;
        } else {
          sentence += ", with no notable final-round collapse.";
        }
      }
    }
    lines.push(sentence);
  });

  // size vs score/cooperation
  const sized = models.filter((m) => catalog && catalog[m] != null && byModel[m].matchCount >= MIN_N);
  if (sized.length >= 2) {
    const bySize = [...sized].sort((a, b) => catalog[a] - catalog[b]);
    const small = bySize[0];
    const big = bySize[bySize.length - 1];
    const smallCoop = byModel[small].coopMoves / byModel[small].totalMoves;
    const bigCoop = byModel[big].coopMoves / byModel[big].totalMoves;
    const direction = bigCoop > smallCoop ? "more" : bigCoop < smallCoop ? "less" : "about as";
    lines.push(
      `The larger model tested (<code class="strategy-name">${big}</code>, ${catalog[big]}B) cooperated ${direction} often than the smaller one (<code class="strategy-name">${small}</code>, ${catalog[small]}B).`
    );
  } else {
    lines.push("Not enough models with known parameter counts and sufficient matches to compare size effects yet.");
  }

  return takeawayPanel("Takeaway", lines.join("<br>"));
}

function heatmapTakeaway(matches) {
  const llmMatches = (matches || []).filter((m) => m.model_a && m.model_b);
  const n = llmMatches.length;
  if (n < MIN_N) {
    return `<p class="caveat">Only ${nBadge(n)} model-vs-model matchup(s) so far — the matrix will fill in as more LLM-vs-LLM matches run.</p>`;
  }
  return `<p class="caveat">${nBadge(n)} model-vs-model matchups recorded.</p>`;
}

async function lastRoundExperimentTakeaway() {
  const data = await getJSON("/api/last-round-experiment");
  if (!data) return "";

  const rows = Object.entries(data)
    .filter(([, r]) => r.p_value !== null && r.told.last_round_total >= MIN_N)
    .sort((a, b) => a[1].p_value - b[1].p_value);

  if (rows.length === 0) {
    return takeawayPanel(
      "Last-round framing effect",
      "An experiment has run, but no model yet has enough repeats to draw a conclusion — see the Research Questions view."
    );
  }

  const [model, r] = rows[0];
  const n = r.told.last_round_total;
  return takeawayPanel(
    "Last-round framing effect",
    `Strongest signal: <code class="strategy-name">${model}</code> defected on the final round ${pct(r.told.last_round_defect_rate)} of the time when told it was the last round, vs. ${pct(r.untold.last_round_defect_rate)} when not told (p=${r.p_value.toFixed(3)}, ${nBadge(n)}).`
  );
}

/* ==========================================================================
   Spatial / noise & ecological
   ========================================================================== */

function spatialTakeaway(data) {
  if (!data || !data.summary || data.summary.length === 0) return "";
  const final = data.summary[data.summary.length - 1];
  const counts = final.counts;
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const [winner, count] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  const share = total ? count / total : 0;
  return takeawayPanel(
    "Takeaway",
    `Single deterministic run (seed=${data.seed}) — <code class="strategy-name">${winner}</code> occupies ${pct(share)} of the grid at generation ${final.generation}. This is one outcome, not a distribution; a different seed could differ.`
  );
}

function sweepsTakeaway(noise) {
  if (!noise) return "";
  const keyForLevel = (lvl) => Object.keys(noise.spatial).find((k) => Number(k) === lvl);
  const levels = noise.noise_levels;
  const lowCounts = noise.spatial[keyForLevel(levels[0])];
  const highCounts = noise.spatial[keyForLevel(levels[levels.length - 1])];
  const lowWinner = Object.entries(lowCounts).sort((a, b) => b[1] - a[1])[0][0];
  const highWinner = Object.entries(highCounts).sort((a, b) => b[1] - a[1])[0][0];

  let sentence;
  if (lowWinner !== highWinner) {
    sentence = `<code class="strategy-name">${lowWinner}</code> dominates the spatial grid at low noise (${levels[0]}), but <code class="strategy-name">${highWinner}</code> takes over by ${levels[levels.length - 1]} noise — a noise-driven crossover.`;
  } else {
    sentence = `<code class="strategy-name">${lowWinner}</code> remains dominant across the full noise range tested (${levels[0]}–${levels[levels.length - 1]}).`;
  }
  return takeawayPanel("Takeaway", `One run per noise level (not a distribution) — read trends, not exact values. ${sentence}`);
}

/* ==========================================================================
   Research questions
   ========================================================================== */

const RESEARCH_QUESTIONS = [
  {
    id: "rq1",
    text: "Do LLM-driven players converge on cooperative strategies under repeated play?",
    view: "comparison",
  },
  {
    id: "rq2",
    text: "Does behavior change when the player is told the current round is the last one?",
    view: "comparison",
  },
  {
    id: "rq3",
    text: "Does behavior change when the player is told (vs. not told) that the opponent is an AI?",
    view: null,
  },
  {
    id: "rq4",
    text: "Does a larger/more capable model converge to cooperation faster or more stably than a smaller one?",
    view: "comparison",
  },
  {
    id: "rq5",
    text: "When a large model plays a small one, does it exploit the mismatch, or behave the same as against an equally-sized model?",
    view: "comparison",
  },
];

function evaluateRQ1(matches, transcripts) {
  if (!transcripts || transcripts.length === 0) return { status: "open", text: "No LLM transcripts yet." };
  const byModel = {};
  transcripts.forEach((t) => {
    [t.model_a, t.model_b].forEach((m) => {
      if (!m) return;
      if (!byModel[m]) byModel[m] = [];
    });
    t.moves.forEach(([roundIndex, moveA, moveB]) => {
      if (t.model_a) byModel[t.model_a].push([roundIndex, moveA === "C"]);
      if (t.model_b) byModel[t.model_b].push([roundIndex, moveB === "C"]);
    });
  });
  let anySignal = false;
  let n = 0;
  Object.values(byModel).forEach((moves) => {
    n += moves.length;
    if (moves.length < MIN_N) return;
    const mid = Math.floor(moves.length / 2);
    const firstHalf = moves.slice(0, mid);
    const secondHalf = moves.slice(mid);
    const rate = (arr) => arr.filter(([, c]) => c).length / arr.length;
    if (rate(secondHalf) - rate(firstHalf) >= 0.15) anySignal = true;
  });
  if (n < MIN_N) return { status: "open", text: `Not enough moves yet (${nBadge(n)}).` };
  return anySignal
    ? { status: "answered", text: `At least one model shows a rising cooperation trend (${nBadge(n)} moves).` }
    : { status: "partial", text: `Data exists (${nBadge(n)} moves) but no clear rising trend yet.` };
}

async function evaluateRQ2() {
  const data = await getJSON("/api/last-round-experiment");
  if (!data) return { status: "open", text: "No last-round experiment run yet." };
  const answerable = Object.entries(data).filter(
    ([, r]) => r.p_value !== null && r.told.last_round_total >= MIN_N
  );
  if (answerable.length === 0) return { status: "partial", text: "Experiment ran, but repeats are still too few." };
  const [model, r] = answerable.sort((a, b) => a[1].p_value - b[1].p_value)[0];
  return {
    status: "answered",
    text: `${model}: ${pct(r.told.last_round_defect_rate)} told vs. ${pct(r.untold.last_round_defect_rate)} untold (p=${r.p_value.toFixed(3)}).`,
  };
}

function evaluateRQ4(matches, transcripts, catalog) {
  const byModel = {};
  (matches || []).forEach((m) => {
    [
      [m.model_a, Number(m.score_a)],
      [m.model_b, Number(m.score_b)],
    ].forEach(([model, score]) => {
      if (!model) return;
      if (!byModel[model]) byModel[model] = { matchCount: 0 };
      byModel[model].matchCount += 1;
    });
  });
  const sized = Object.keys(byModel).filter((m) => catalog && catalog[m] != null && byModel[m].matchCount >= MIN_N);
  if (sized.length < 2) return { status: "open", text: "Fewer than 2 sized models with enough matches yet." };
  return { status: "answered", text: `${sized.length} sized models with ${nBadge(MIN_N)}+ matches each — see model comparison.` };
}

function evaluateRQ5(matches, catalog) {
  const llmMatches = (matches || []).filter((m) => m.model_a && m.model_b && catalog[m.model_a] != null && catalog[m.model_b] != null);
  const mismatched = llmMatches.filter((m) => {
    const ratio = catalog[m.model_a] / catalog[m.model_b];
    return ratio >= 3 || ratio <= 1 / 3;
  });
  if (mismatched.length < MIN_N) {
    return { status: mismatched.length === 0 ? "open" : "partial", text: `${nBadge(mismatched.length)} size-mismatched LLM-vs-LLM matchups so far.` };
  }
  return { status: "answered", text: `${nBadge(mismatched.length)} size-mismatched matchups — see the matchup matrix.` };
}
