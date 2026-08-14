# tit-for-tit-for-tat

An Axelrod-style iterated Prisoner's Dilemma tournament. Classic strategies
(tit-for-tat, grim trigger, Pavlov, always-cooperate, always-defect, random)
play round-robin against each other **and** against LLM-driven strategies
whose behavior is defined by a system prompt instead of code.

## Research questions

- Do LLM-driven players converge on cooperative strategies under repeated play?
- Does behavior change when the player is told the current round is the last one?
- Does behavior change when the player is told (vs. not told) that the opponent is an AI?

## Status

- **v0 (done)**: two hardcoded classic strategies (tit-for-tat vs
  always-defect), 100 rounds, scores printed to stdout.
- **v1 (code complete, not yet run live)**: one LLM-backed strategy
  (`prompts/baseline.txt`) vs tit-for-tat, 10 rounds. Blocked on
  `ANTHROPIC_API_KEY` pending an Anthropic Console org review.
- **v2 (done for classic strategies)**: full round-robin across all six
  classic strategies via `Tournament`, results written to
  `results/matches.csv` and `results/standings.json`. The LLM strategy is
  wired in and included automatically once `ANTHROPIC_API_KEY` is set, but
  hasn't been run live yet either.
- **v3 (done for classic strategies)**: 8x8 toroidal grid, Nowak-May spatial
  dynamics ("imitate the best neighbor" each generation), 40 generations,
  rendered as an animated GIF (`results/spatial_evolution.gif`). Classic
  strategies only for now — a grid full of LLM cells would be a lot of API
  calls per run.
- **Round-context + noise model (done)**: every strategy can now see where it
  is in a match (`RoundContext`: `round_index`, `total_rounds`,
  `is_last_round`) — the piece needed for the "told this is the last round"
  research question. `Match`/`Tournament`/`Grid` also support a per-move
  "trembling hand" noise rate, letting us directly test *why* GrimTrigger beat
  TitForTat in the v3 run: a single accidental flip locks GrimTrigger into
  permanent mutual defection, while TitForTat instead falls into a persistent
  alternating "echo" — never both-D, never both-C again, but still scoring
  higher than Grim's full lock-in. Both are proven with executable tests, not
  just discussed.
- **New strategy variants (done)**: `GenerousTitForTat` (forgives
  probabilistically), `Joss` (defects unprovoked with small probability), and
  `EndgameDefector` (the first strategy to actually use `RoundContext` —
  defects unconditionally on the last round). Wired into both the
  round-robin and the spatial grid. Rerunning v3 with these produced a
  striking result: `EndgameDefector` sweeps the **entire** grid by
  generation 3 — its "free unpunished last-round defection" is 10x more
  valuable in the spatial grid's short 10-round sub-matches than in the full
  100-round round-robin, a real "shadow of the future" effect.

- **Noise-sweep experiment (done)**: the round-robin and the spatial grid,
  both run across `noise = [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]`
  (`results/noise_sweep_summary.json` + two charts). Confirms the
  forgiveness-vs-noise story with real numbers: `grim_trigger`'s round-robin
  lead collapses almost immediately (2598 -> 2079 total score at just 2%
  noise) while `generous_tit_for_tat` degrades far more gracefully. In the
  spatial grid, `endgame_defector` keeps its full-grid takeover through
  0-20% noise, but `grim_trigger` reclaims the whole grid at 30% noise — a
  genuine crossover, not just a noise-free curiosity.

- **Ecological (population-proportional) tournament (done)**: Axelrod's
  actual second-tournament methodology — population shares evolve each
  generation proportional to average payoff against the whole mixed
  population, not fixed spatial neighbors (`results/ecological_trajectory.png`).
  Qualitatively different from the spatial grid: `always_defect`/`random`/`joss`
  go extinct by ~generation 10, but **six** nice strategies settle into a
  slowly-shifting coexistence instead of one strategy taking the whole
  population — no winner-take-all monoculture.
- **Multi-provider/multi-model LLM roster (code complete, not yet run live)**:
  a second `LLMClient` implementation (`OpenAICompatibleLLMClient`) for any
  OpenAI-chat-completions-compatible provider, with factories for Groq and
  Ollama (local and cloud) alongside the existing Anthropic strategy. Every
  configured LLM strategy now plays every classic strategy *and* every other
  LLM strategy (including each other), and results carry a `model_name` per
  strategy so they can be filtered by model — built for two new questions:
  does a larger model converge to cooperation faster/more stably, and does a
  large model exploit a small one it's paired against.
- **Ollama Cloud + expanded Groq roster + live web dashboard (code complete,
  live-verified)**: Groq expanded to a 4-model size ladder (8B-120B);
  "Ollama" now primarily means Ollama Cloud (hosted, `OLLAMA_API_KEY`), with
  local Ollama kept as an independent option. Added a transcript layer
  (`results/llm_transcripts.jsonl`) so the model-comparison questions can see
  cooperation *emerge over rounds*, not just final scores. Added a full local
  web dashboard (`run_webapp.py`) — standings, model-size research charts, a
  per-match transcript explorer, the spatial GIF, noise-sweep/ecological
  charts, and a live-run panel that starts a real tournament and streams
  match/round progress in the browser via Server-Sent Events. A live 20-round
  run across all four configured models (2 Groq tiers, `gemma4:31b-cloud`,
  local `qwen2.5`) completed with zero errors, confirming the roster and Groq
  pacing work in practice.
- **Last-round announcement A/B experiment (done)**: `run_last_round_experiment.py`
  runs each configured model both "told" (standard last-round notice) and
  "untold" (notice withheld even on the true last round) against a
  never-defects-first opponent panel (`TitForTat`/`AlwaysCooperate`), repeated
  several times per pairing, and reports a told-vs-untold last-round
  defect-rate z-test per model — the "does behavior change when told this is
  the last round" research question is now directly answerable from data, not
  just theorized. Smallest models tested so far (`llama-3.1-8b-instant`, local
  `qwen2.5`) showed 0% last-round defection under *both* conditions, while
  `llama-3.3-70b-versatile` and `gemma4:31b-cloud` clearly differentiated
  (100% told vs. 0% untold) — a real floor-effect signal worth more repeat
  data to confirm.
- **Opponent-is-AI A/B experiment (done)**: `run_opponent_is_ai_experiment.py`
  + `prompts/opponent_is_ai.txt` mirror the last-round experiment's shape for
  the "does behavior change when told the opponent is an AI" question,
  comparing aggregate cooperation rate (no single critical round exists for
  this framing).
- **Per-move reasoning capture (done)**: `LLMStrategy` now asks for
  `<C or D> - <reason>` and threads the parsed reason through
  `Match`/`Tournament`'s callbacks into the transcript JSONL and the
  dashboard's transcript explorer (shown as a tooltip on each move).
- **"So-what" interpretation layer + run history (done)**: the dashboard now
  states its own deterministic, rule-based takeaways per view instead of
  requiring an LLM read of the charts, plus a **Research Questions** view
  that maps all 5 research questions above to a live open/partial/answered
  status computed from whatever data already exists. Every live run's output
  files are also archived to `results/runs/<run_id>/` (survives dashboard
  restarts), not just overwritten by the next run.
- **Model selection in the live-run panel (done)**: the dashboard's Live Run
  form can now scope a run to a subset of configured models (useful for
  cost/time control) and supports launching the last-round experiment
  directly from the browser, not just the CLI.

See `CLAUDE.md` for the full build-order history, architecture, and current
backlog (a noise x last-round combined experiment, an LLM-powered "smart
summary" upgrade to the so-what layer, and CI/engineering polish).

See `CLAUDE.md` for full architecture.

## Usage

```
uv sync
uv run python run_v0.py
uv run python run_v1.py   # needs ANTHROPIC_API_KEY / GROQ_API_KEY / OLLAMA_API_KEY / OLLAMA_ENABLED
uv run python run_v2.py   # each LLM strategy included only if its provider is configured
uv run python run_v3.py
uv run python run_noise_sweep.py
uv run python run_ecological.py
uv run python run_last_round_experiment.py      # told-vs-untold last-round A/B experiment
uv run python run_opponent_is_ai_experiment.py  # opponent-is-AI A/B experiment
uv run python run_webapp.py   # dashboard at http://127.0.0.1:8000
uv run pytest
```

`run_v1.py`/`run_v2.py`/the dashboard's live-run panel all include one LLM
strategy per configured provider — `ANTHROPIC_API_KEY`, `GROQ_API_KEY`,
`OLLAMA_API_KEY` (Ollama Cloud), and `OLLAMA_ENABLED=1` (local Ollama, plus a
server actually running on `localhost:11434`) are independent and any subset
can be set; unset providers are skipped with a printed notice, not an error.
Ollama Cloud's free tier allows only one cloud model in flight at a time —
the tournament's fully sequential match loop and the dashboard's one-run-at-a-
time guard both exist partly to guarantee that.

`run_webapp.py` does not hot-reload — restart the process after any backend
or frontend code change before trusting what the browser shows.

Always run scripts through `uv run`, not a directly-activated `python`. On
this machine that used to fail with `ModuleNotFoundError: No module named
'tournament'` because the project lived under `~/Desktop`, and macOS's
iCloud Desktop/Documents sync marks newly written files hidden
(`UF_HIDDEN`) — including `uv`'s editable-install `.pth` file — which
CPython 3.13's `site.py` then silently skips. The fix was moving the
project out of `~/Desktop` entirely (not a `uv run` workaround — `uv run`
hits the exact same bug, since it just execs the venv's own `python`).
