# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this is

An Axelrod-style iterated Prisoner's Dilemma tournament. Classic strategies
(tit-for-tat, grim trigger, Pavlov, always-cooperate, always-defect, random)
play round-robin against each other AND against LLM-driven strategies whose
behavior is defined by a system prompt instead of code.

The research questions this is actually for:
- Do LLM-driven players converge on cooperative strategies under repeated play?
- Does behavior change when the player is told the current round is the last one?
- Does behavior change when the player is told (vs. not told) that the opponent is an AI?
- Does a larger/more capable model converge to cooperation faster or more
  stably than a smaller one?
- When a large model plays a small one, does it exploit the mismatch, or
  behave the same as it would against an equally-sized model?

## Commands

- `uv sync` — install dependencies
- `uv run pytest` — run the full test suite
- `uv run pytest tests/test_classic_strategies.py::test_tit_for_tat_hand_computed_sequence` — run a single test
- `uv run python run_v0.py` — v0 demo: tit-for-tat vs always-defect, 100 rounds, prints scores
- `uv run python run_v1.py` — v1 demo: every configured LLM strategy vs tit-for-tat, 10 rounds each,
  one match per model (needs at least one of `ANTHROPIC_API_KEY` / `GROQ_API_KEY` / `OLLAMA_ENABLED`)
- `uv run python run_v2.py` — v2 demo: full round-robin, writes `results/matches.csv` and `results/standings.json`
  (every configured LLM strategy is included automatically — see `llm_roster.py` below — and plays
  against the classic strategies *and* every other LLM strategy, including different models against
  each other)
- `uv run python run_v3.py` — v3 demo: 8x8 spatial grid, 40 generations, writes
  `results/spatial_evolution.gif`, `results/spatial_legend.json`, `results/spatial_summary.json`
- `uv run python run_noise_sweep.py` — runs the round-robin + spatial grid across a
  range of noise levels, writes `results/noise_sweep_summary.json` and two charts
- `uv run python run_ecological.py` — 100-generation replicator-dynamics run against
  the whole mixed population, writes `results/ecological_trajectory.png` + `results/ecological_summary.json`
- `uv run python run_last_round_experiment.py` — the last-round-announcement A/B
  experiment: each configured LLM model plays 'told' (standard last-round notice)
  vs. 'untold' (notice withheld even on the true last round) against a fixed
  `TitForTat`/`AlwaysCooperate` opponent panel, repeated `REPEATS` times per pairing,
  writes `results/last_round_experiment.json` + `results/last_round_cooperation.png`
  and prints a told-vs-untold defect-rate/z-score table
- `uv run python run_webapp.py` — starts a local FastAPI dashboard at
  `http://127.0.0.1:8000`: standings, model-size research charts, a per-match
  transcript explorer, the spatial GIF, noise-sweep/ecological charts, and a
  live-run panel that starts a real tournament in the background and streams
  match/round progress over SSE. Reads whatever's already in `results/`; no
  API key needed just to view existing results.

Always invoke through `uv run` — see the README for why a directly-activated
`python` can silently fail to import `tournament` on this machine.

## Architecture

- `src/tournament/strategies/base.py` — the `Strategy` protocol every player implements:
  `move(history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move`,
  where `Move` is `Literal["C", "D"]`, `history` is `(my_move, opponent_move)` pairs
  (oldest first), and `RoundContext` (`round_index`, `total_rounds`, `.is_last_round`)
  tells a strategy where it is in the match. `context` defaults to `None` and every
  classic strategy ignores it — only `LLMStrategy` currently reads it (to mention the
  final round in its rendered prompt). Strategies are pure functions of their
  arguments — no per-instance mutable state — which is what lets the same instance be
  reused across every match in a round-robin.
- `src/tournament/strategies/classic.py` — `TitForTat`, `AlwaysDefect`,
  `AlwaysCooperate`, `GrimTrigger` (defects forever after the opponent's first
  defection), `Pavlov` (win-stay/lose-shift: repeats its last move after a good
  outcome (`R` or `T`), switches after a bad one (`P` or `S`)), `RandomStrategy`
  (seedable `random.Random` instance, `p_cooperate` controls the coin weighting),
  `GenerousTitForTat` (TFT that forgives a defection with probability
  `generosity` instead of always retaliating — `generosity=0.0`/`1.0` reduce
  exactly to `TitForTat`/`AlwaysCooperate`), `Joss` (TFT that opportunistically
  defects unprovoked with probability `defection_probability` —
  `0.0`/`1.0` reduce to `TitForTat`/`AlwaysDefect`), `EndgameDefector` (plays
  TFT but unconditionally defects when `context.is_last_round` — the **first**
  classic strategy to actually *read* `RoundContext` rather than just accept
  and ignore it). `GenerousTitForTat`/`Joss`/`RandomStrategy` all carry a
  seeded `random.Random` instance and are the only classic strategies that
  aren't pure functions of `history` alone.
- `src/tournament/strategies/llm.py` — `LLMStrategy`: renders `history` (plus
  `context`, if given) into a user-message prompt via `render_history` — which
  appends a "this is the final round" notice when `context.is_last_round` is
  true *and* `announce_last_round` (constructor param, default `True`) is
  also true — calls an injected `LLMClient`, parses the raw text response back into
  a `Move` via `parse_move` (strict: raises `ValueError` rather than silently
  defaulting on an unparseable response). Optionally takes a `DiskCache` —
  checked before every network call, keyed on `(system_prompt, history,
  is_last_round, model)` so a prompt-wording change, a last-round framing
  change, *or* a different model behind the same prompt each invalidate cache
  entries independently instead of one silently serving another's cached
  answer. Also takes an optional `model_name: str | None` — a free-text label
  (e.g. `"Codex-sonnet-5"`, `"openai/gpt-oss-120b"`) with no effect on
  behavior beyond being threaded into the cache key and (via `Tournament`,
  see below) into every match result, so results can later be grouped/filtered
  by model/sophistication tier for the two model-comparison research questions
  above. `client`/`cache`/`announce_last_round` are the things that actually
  vary behavior; `model_name` is pure metadata. `announce_last_round=False`
  computes the *effective* `is_last_round` (real game state AND the flag) and
  uses that same effective value for both the rendered prompt and the cache
  key — the point being a "told" and "untold" run of the same model never
  collide on cache key even if they ever shared a cache file, since the key
  always reflects what the model actually saw, not the raw game state. Built
  for `last_round_experiment.py` below.
- `src/tournament/llm_client.py` — `LLMClient` protocol (`complete(system_prompt,
  user_message) -> str`) plus `AnthropicLLMClient`. Tests never import this
  class — they inject a stub `LLMClient` instead, so no test can accidentally
  reach the network.
- `src/tournament/llm_clients/openai_compatible.py` — `OpenAICompatibleLLMClient`:
  a second `LLMClient` implementation for any provider speaking the OpenAI
  chat-completions HTTP format, built on `httpx` (an injectable `http_client`
  keeps it testable via `httpx.MockTransport`, same "no live network in tests"
  rule as everything else). One class, three convenience factories on top of it —
  `groq_client(model=...)`, `ollama_local_client(model="qwen2.5")` (local, no
  key — Ollama's local OpenAI-compatible server doesn't have a real auth
  concept, so the client just omits the `Authorization` header entirely rather
  than sending a fake key), and `ollama_cloud_client(model="gemma4:31b-cloud")`
  (hosted, reads `OLLAMA_API_KEY`, `base_url="https://ollama.com/v1"` —
  mirrors the local server's `/v1` path). `src/tournament/llm_clients/__init__.py`
  re-exports all four. `complete()` retries on `429`/`5xx` (exponential
  backoff, honoring a `Retry-After` header if the provider sends one) but
  raises immediately on other 4xx like `403` — those are permanent
  auth/entitlement failures, not transient load, so retrying them is
  pointless. Also paces consecutive requests through the same client instance
  (`min_request_interval`, default 0.5s; `groq_client()` overrides this to
  `GROQ_MIN_REQUEST_INTERVAL = 2.1`s, calibrated to Groq's documented 30
  requests/minute free-tier cap so a sequential run of many Groq calls stays
  under the limit proactively instead of relying on reactive 429 retries) and
  falls back to a `reasoning`/`reasoning_content` message field when
  `content` comes back empty — reasoning models like Groq's `gpt-oss` family
  put their answer there instead of `content` if `max_tokens` (default raised
  to 500, was 10) gets tight.
- `src/tournament/llm_roster.py` — `build_llm_strategies(system_prompt, cache_dir,
  announce_last_round=True)`:
  the single place that knows how to gate and construct every configured LLM
  strategy — one `if <PROVIDER>_configured` block per provider.
  `announce_last_round=False` appends `_untold` to every strategy's `name`
  and cache filename (so an "untold" roster never collides with the default
  roster's cache) and threads the flag into each `LLMStrategy`. Built so
  `last_round_experiment.py` (below) can call this twice — once per
  condition — and reuse all the provider-gating logic instead of
  duplicating it. `GROQ_MODELS`
  is a 2-entry size ladder (`llama-3.1-8b-instant` 8B, `llama-3.3-70b-versatile`
  70B), gated on `GROQ_API_KEY` — deliberately both plain instruct models, not
  reasoning models: the roster originally also included `openai/gpt-oss-20b`
  and `openai/gpt-oss-120b`, but Groq's free tier rate-limits those two far
  more tightly (1K requests/day and only 8K tokens/minute, vs. up to 14.4K
  requests/day and 500K tokens/day for the 8B instruct model) and their
  hidden reasoning tokens were the direct cause of an empty-`content`
  response bug — dropped after that tradeoff became clear from a live run.
  `OLLAMA_CLOUD_MODELS = ["gemma4:31b-cloud"]` — previously also included
  `"qwen3.5:cloud"`, dropped after it 403'd on every live call and account
  history showed it had never actually been reachable on this key, unlike
  `gemma4:31b-cloud` which had — gated on `OLLAMA_API_KEY`
  (separate from the local block's `OLLAMA_ENABLED=1`
  opt-in — local and cloud Ollama are independent, both can be on at once).
  Each strategy gets a distinct `name`, `model_name`, and its own `DiskCache`
  file. A provider whose gate isn't satisfied prints a one-line skip notice
  and is left out — never raises. **Ollama Cloud's free tier allows only one
  cloud model in flight at a time** — satisfied for free by `Tournament`'s
  fully sequential match loop (never concurrent), which is exactly why
  `webapp/runs.py` (below) refuses to start a second live run while one is
  already in progress: that's the one thing that *would* break the
  one-at-a-time guarantee. Shared by `run_v1.py`, `run_v2.py`, and
  `webapp/runs.py` — so `Tournament` naturally plays every LLM strategy
  against the classics *and* every other LLM strategy, including different
  models and different providers against each other, with no `Tournament`
  change needed for that part.
- `src/tournament/classic_roster.py` — `build_classic_strategies()` (the
  9-strategy list) and `CLASSIC_STRATEGY_FACTORIES` (the same 9, as
  `Callable[[random.Random], Strategy]` factories for `Grid`/`sweep_spatial`).
  Single source of truth shared by `run_v2.py`, `run_v3.py`,
  `run_noise_sweep.py`, `run_ecological.py`, and `webapp/runs.py` — previously
  each of those files hand-duplicated this list.
- `src/tournament/model_catalog.py` — `MODEL_SIZE_BILLIONS: dict[str, float |
  None]`, a hand-maintained `model_name -> approximate param count` lookup
  covering every roster entry (`None` where the count isn't published or
  confirmed, e.g. `Codex-sonnet-5`, `qwen3.5:cloud`). Pure metadata consumed
  by the webapp's size-vs-cooperation/score charts; doesn't touch
  `LLMStrategy` or the roster's construction logic.
- `src/tournament/cache.py` — `DiskCache` (JSON-backed get/set) and `cache_key`
  (sha256 over `{prompt, history, is_last_round, model}`). Whole file gets
  rewritten on every `set`; fine at this scale.
- `src/tournament/payoff.py` — the payoff matrix (`T=5, R=3, P=1, S=0`) and
  `score_round(move_a, move_b)`. `validate_payoffs()` runs at import time and
  enforces `T > R > P > S` and `2R > T + S` — the two conditions that make this
  a well-formed Prisoner's Dilemma. Never let a "just try something" edit to
  these constants silently violate them.
- `src/tournament/match.py` — `Match(strategy_a, strategy_b, rounds, noise=0.0,
  rng=None, on_round=None)`: runs two strategies against each other, constructs
  a `RoundContext` each round and passes it to both `.move()` calls, gives each
  side its own view of history, and returns final scores plus the move log.
  `on_round(round_index, move_a, move_b)`, if given, fires once per round right
  after scoring — default `None` is a no-op, purely additive for the webapp's
  live streaming (below). `noise` is a
  "trembling hand" execution-error rate: each strategy's *intended* move is
  independently flipped with probability `noise` before being scored or
  recorded — both sides only ever see the actual (possibly flipped) move, never
  the intent, matching the standard noisy-IPD model. Default `noise=0.0` with a
  real `random.Random()` is a no-op, so every noise-free result is unaffected.
  `rng` accepts any object with a `.random()` method, so tests can inject a
  scripted fake to force an exact sequence of flips (see
  `tests/test_match.py::test_grim_trigger_locks_into_permanent_defection_after_one_accidental_flip`
  and its `TitForTat` counterpart — direct, executable proof of the
  forgiveness-vs-noise story: GrimTrigger locks into permanent mutual defection
  after one accidental flip, while TitForTat instead falls into a persistent
  alternating "echo" of exploitation — never both-D, never both-C again, but
  it still out-scores GrimTrigger's full lock-in over the same match).
- `src/tournament/tournament.py` — `Tournament(strategies, rounds, noise=0.0,
  seed=None)`: round-robin over every unordered pair **including each strategy
  against itself** (a strategy's self-play score is a real signal — e.g. two
  `GrimTrigger`s always mutually cooperate). `noise`/`seed` are forwarded to
  every `Match` it builds, sharing one RNG across the whole tournament.
  `.play()` returns a list of per-match result dicts (`strategy_a`, `strategy_b`,
  `rounds`, `score_a`, `score_b`, plus `model_a`/`model_b` — `getattr(strategy,
  "model_name", None)`, so classic strategies record `None` and `LLMStrategy`
  instances record whatever `model_name` they were built with); `.standings()`
  aggregates total score per strategy name across every match it appeared in
  (both as `strategy_a` and `strategy_b`) and sorts descending. `.play()` also
  takes four optional callbacks — `on_match_start(a, b, model_a, model_b)`,
  `on_round(a, b, round_index, move_a, move_b)` (wraps `Match`'s `on_round`
  with the pair's names), `on_match_end(a, b, result_dict)`, and
  `on_match_error(a, b, exception)` — all default `None` (every existing
  no-arg `tournament.play()` call is unaffected). `on_match_error` is the one
  that changes behavior when supplied: only then does `Tournament` wrap each
  pair's `match.play()` in try/except, report the failure, and move on to the
  next pair instead of letting the whole round-robin crash on one bad
  call — opt-in, and the only place in the codebase that catches a strategy
  exception at all. Built for `webapp/runs.py`'s live view, where a single
  stale model tag from a fast-moving provider catalog shouldn't take down an
  otherwise-fine 90-match run.
- `src/tournament/reporting.py` — `write_results_csv` / `write_standings_json`:
  plain `csv.DictWriter` / `json.dumps` to a path, creating parent dirs as needed.
  `write_results_csv`'s `fieldnames` list is hardcoded (`csv.DictWriter`
  defaults to raising on any dict key not in it) — has to be updated in lockstep
  with any new key `Tournament.play()` starts adding to its result dicts.
- `src/tournament/spatial.py` — `Grid(size, strategy_factories, seed, noise=0.0)`: a
  toroidal (wraparound) grid running Nowak-May spatial dynamics; `noise` is
  forwarded to every internal `Match`, same semantics as above. Each cell holds a strategy
  instance built from a `Callable[[random.Random], Strategy]` factory (the RNG
  argument exists so `RandomStrategy` cells can be reseeded deterministically off
  the grid's own master RNG — every other factory just ignores it). `.step()`
  computes each cell's total payoff (a `Match` against each of its 8 neighbors,
  `MATCH_ROUNDS` each) using the *current* grid, then simultaneously updates every
  cell to imitate whichever cell in its neighborhood (self included) scored
  highest — ties favor staying put, then the fixed `_NEIGHBOR_OFFSETS` scan order.
  Grid size must be >= 3 or Moore-neighborhood offsets wrap onto themselves.
- `src/tournament/visualization.py` — `render_generations_gif`: turns a list of
  per-generation strategy-name grids into a color-coded animated GIF
  (`matplotlib` + `Pillow`, `Agg` backend so it needs no display), plus a
  `strategy name -> hex color` legend JSON alongside it. `render_line_chart`:
  a generic one-line-per-series chart (used by the noise sweep below),
  reusing the same `_PALETTE` so a strategy has the same color across every
  artifact.
- `src/tournament/experiments.py` — `sweep_round_robin(build_strategies,
  rounds, noise_levels, seed)` / `sweep_spatial(size, strategy_factories,
  generations, noise_levels, seed)`: run a fresh `Tournament`/`Grid` at each
  noise level, returning standings/final-counts keyed by noise level.
  `sweep_round_robin` takes a zero-arg *builder* callable, not a shared
  strategy list — strategies with internal RNG state (`RandomStrategy`,
  `GenerousTitForTat`, `Joss`) need to start fresh at each noise level rather
  than carrying consumed randomness over from the previous level's run.
- `src/tournament/ecological.py` — `EcologicalTournament(strategies, rounds,
  noise, seed)`: Axelrod's actual second-tournament methodology — replicator
  dynamics. Precomputes each ordered pair's average per-round payoff **once**
  via `Match` (two fixed strategies' expected payoff against each other
  doesn't change generation to generation, only the population weighting
  does), then `.run(generations, initial_shares=None)` repeatedly applies the
  standard replicator update — each strategy's fitness is its population-share-
  weighted average payoff against everyone (including itself), and its share
  for the next generation scales by `fitness / population-average fitness` —
  renormalizing each generation to guard against float drift. Returns the
  full share trajectory, one dict per generation (index 0 = the initial
  shares).
- `src/tournament/last_round_experiment.py` — `run_last_round_experiment(system_prompt,
  cache_dir, rounds=20, repeats=3, opponent_factories=None)`: the last-round
  A/B experiment. Builds two rosters via `build_llm_strategies` — one per
  `announce_last_round` value — and matches them up by `model_name`. For each
  model, under each condition, plays it against a fixed panel of *nice-opener*
  reference opponents (default `[TitForTat, AlwaysCooperate]` — deliberately
  strategies that never defect first, so a last-round defection is
  attributable to the LLM's own reasoning rather than retaliation against an
  opponent that already defected), `repeats` times per opponent. Each repeat
  uses a **fresh, uncached** `LLMStrategy` (`cache=None`, same underlying
  `LLMClient` reused from the roster build) — reusing `DiskCache` here would
  make every "repeat" return the identical cached response and defeat the
  point of repeating, since the whole point is capturing independent draws
  from the model. Returns, per model: told/untold last-round defect
  rate + count, told/untold per-round cooperation rate (averaged across
  opponents/repeats), and a two-proportion z-test + two-tailed p-value
  (`_two_proportion_z`/`_two_tailed_p_value`, computed via stdlib `math.erf`
  only — no new dependency) comparing the two conditions' last-round defect
  rates. `run_last_round_experiment.py` at the repo root is the CLI entry
  point — writes `results/last_round_experiment.json` (full summary + raw
  per-repeat move sequences) and `results/last_round_cooperation.png` (via
  the existing `render_line_chart`, two lines per model), and prints a
  told-vs-untold console table. Deliberately **not** wired into
  `Tournament`/`webapp/runs.py` — this is a narrower, dedicated experiment
  (like `run_noise_sweep.py`/`run_ecological.py`), not part of the general
  round-robin.
- `src/tournament/webapp/` — the FastAPI dashboard (`run_webapp.py` at the
  repo root is its entry point). `runs.py`: `RunState` (per-run status +
  event replay buffer + `asyncio.Queue` subscribers, one per SSE connection)
  and `RUNS: dict[str, RunState]`, an in-memory registry — correct for a
  single-process local tool, no DB. `start_run(...)` refuses a second
  concurrent run (`RunAlreadyInProgress`) and launches a `threading.Thread`
  running `_worker`, which builds the requested roster, drives `Tournament`
  (or `Grid`/`sweep_*`/`EcologicalTournament` for the other experiment types)
  with the callbacks above, and pushes each event to subscribers via
  `emit()` — `loop.call_soon_threadsafe(queue.put_nowait, event)`, since the
  worker thread never touches asyncio directly. For any LLM-involving match,
  the worker also appends the full move history to
  `results/llm_transcripts.jsonl` (one JSON line per match) — this is the
  transcript layer the model-comparison research questions actually need
  (final scores alone can't show cooperation *emerging* over rounds).
  `app.py`: routes — `POST /api/runs` / `GET /api/runs/{id}/events` (SSE,
  replays the backlog before going live) / `GET /api/standings|matches|
  spatial|noise-sweep|ecological|transcripts|model-catalog`, plus static
  mounts for `results/` (so the frontend can hit the spatial GIF directly)
  and `webapp/static/` (the frontend itself — plain HTML/CSS/JS, Chart.js via
  CDN, no build step, no npm). See `DESIGN.md` for the dashboard's visual
  system.

## Build order (do NOT skip ahead)

1. **v0 — done.** Two hardcoded classic strategies (tit-for-tat vs
   always-defect), 100 rounds, print the scores. No LLM calls.
2. **v1 — code complete, not yet run against the live API.** One LLM-backed
   strategy (`prompts/baseline.txt`) vs tit-for-tat, 10 rounds. Blocked on
   `ANTHROPIC_API_KEY` (Anthropic org under review as of 2026-07-31) — run
   `run_v1.py` for real as soon as a key is available, to actually answer
   the "does it cooperate" question, not just confirm the wiring works.
3. **v2 — done (classic strategies only; LLM strategy wired in but unverified
   live for the same reason as v1).** Full round-robin among all six classic
   strategies via `Tournament`, results in `results/matches.csv` +
   `results/standings.json`. `run_v2.py` auto-includes the LLM strategy only
   if `ANTHROPIC_API_KEY` is set.
4. **v3 (stretch) — done for classic strategies.** 8x8 toroidal grid, deterministic
   Nowak-May "imitate the best neighbor" dynamics, 40 generations, rendered as an
   animated GIF (`run_v3.py`). LLM cells are not wired into the grid yet — a full
   grid of LLM-driven cells would mean hundreds/thousands of API calls per run,
   so this stays classic-only until there's a specific reason to spend on it.
5. **Round-context + noise model — done.** `RoundContext` (round_index/total_rounds/
   is_last_round) threaded through every `Strategy.move()`, plus a per-move
   "trembling hand" noise rate in `Match`/`Tournament`/`Grid`. Built after a live
   discussion of *why* `GrimTrigger` beat `TitForTat` in the v3 spatial run
   surfaced that TFT's "nice/retaliatory/forgiving" reputation is really a
   noise-robustness story (Nowak & Sigmund), not a universal law — this phase
   makes that story directly testable in code (see the two hand-verified tests
   referenced in `match.py`'s entry above) and unblocks the "told this is the
   last round" research question, the one question that needed a Strategy
   interface change (the "opponent is AI" question doesn't — that's just a
   different prompt/flag, still backlog, see below).
6. **New strategy variants — done.** `GenerousTitForTat`, `Joss`, and
   `EndgameDefector` (see architecture entry above), wired into both
   `run_v2.py`'s round-robin roster and `run_v3.py`'s spatial grid (which
   also needed its color palette extended from 7 to 10 colors —
   `visualization.py`'s `_PALETTE`). Running v3 with the 9-strategy roster
   produced a striking result: `EndgameDefector` sweeps the **entire** 8x8
   grid by generation 3. The mechanism: each spatial generation is a short
   `MATCH_ROUNDS=10`-round sub-match, so the "free, unpunished last-round
   defection" is 1-in-10 rounds there vs. 1-in-100 in the full round-robin —
   a much bigger structural edge when interactions are short (the "shadow of
   the future" effect from game theory: looking ahead matters less, and
   knowing when the game ends matters more, the shorter the game is).
7. **Noise-sweep experiment — done.** `run_noise_sweep.py` runs the full
   9-strategy roster across `NOISE_LEVELS = [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]`
   in both the round-robin `Tournament` and the spatial `Grid`, writing
   `results/noise_sweep_summary.json` and two charts (`results/
   noise_sweep_roundrobin.png`, `results/noise_sweep_spatial.png`). Results:
   in the round-robin, `grim_trigger`'s lead collapses almost immediately
   (2598 -> 2079 total score at just 2% noise) while `generous_tit_for_tat`
   degrades much more gracefully - direct empirical confirmation of the
   forgiveness-vs-noise story, not just the two hand-picked unit tests from
   the previous phase. In the spatial grid, `endgame_defector` keeps its
   full-grid dominance through 0-20% noise, but at 30% noise `grim_trigger`
   reclaims the entire grid instead - a genuine noise-driven crossover.
8. **Ecological (population-proportional) tournament — done.**
   `run_ecological.py` runs the same 9-strategy roster for 100 generations
   via `EcologicalTournament`, starting from equal shares. Result is
   qualitatively different from the spatial grid: `always_defect`, `random`,
   and `joss` go extinct by ~generation 10, but **six** nice strategies
   (`endgame_defector`, `grim_trigger`, `generous_tit_for_tat`, `pavlov`,
   `tit_for_tat`, `always_cooperate`) settle into a slowly-shifting
   coexistence rather than one strategy taking the whole population — no
   winner-take-all monoculture like the spatial grid produced.
   `endgame_defector` is still gradually gaining share at generation 100
   (0.254, up from 0.183 at generation 30), so the population hasn't fully
   converged to a fixed point in this run.
9. **Multi-provider/multi-model LLM roster — code complete, not yet run live.**
   `llm_clients/openai_compatible.py` + `llm_roster.py` (see architecture
   above) turn the single hardcoded Anthropic strategy into a roster. Built
   for the two model-comparison research questions above — this phase is pure
   plumbing so those questions can be answered by filtering `matches.csv` by
   `model_a`/`model_b` after a real run, not by this phase itself.
   `ANTHROPIC_API_KEY` is the same one under org review since 2026-07-31, and
   as of this phase is no longer the point: the user's actual goal is
   comparing open-source models of different sizes, and Anthropic stays wired
   in (free to re-enable the moment a key exists) but isn't blocking anything.
10. **Ollama Cloud + expanded Groq roster + live web dashboard — code
    complete, not yet run live.** Superseded/extended phase 9: "Ollama" now
    means Ollama Cloud (`ollama_cloud_client`, `OLLAMA_API_KEY`), not a local
    model — local Ollama stays available too, independently gated. Groq
    expanded from 2 to 4 models spanning 8B-120B. Added the transcript layer
    (`results/llm_transcripts.jsonl`, via new opt-in callbacks on
    `Match`/`Tournament` — see architecture above) since the model-comparison
    questions need to see cooperation *emerge over rounds*, not just final
    scores — this is the "structured experiment logging (full transcripts)"
    item from the old backlog below, now done. Added a full FastAPI +
    vanilla-JS dashboard (`src/tournament/webapp/`, `run_webapp.py`) with six
    views — standings, model comparison (size vs. score/cooperation-rate
    scatter, cooperation-vs-round convergence line chart, matchup heatmap),
    a transcript explorer, spatial grid, noise-sweep/ecological, and a live
    run panel that starts a tournament in the background and streams
    match/round progress over SSE. Blocked on live verification the same way
    as phase 9 — `GROQ_API_KEY` / `OLLAMA_API_KEY` need to actually be set to
    prove the roster and the `https://ollama.com/v1` base URL guess are
    right; the live-run UI itself was verified end-to-end with a real
    (free, classic-only) run — see `DESIGN.md` for the dashboard's design
    system.
11. **Live LLM roster verified working + last-round A/B experiment — done.**
    A live 20-round LLM+classic round-robin run (all 4 configured models:
    2 Groq instruct tiers, `gemma4:31b-cloud`, local `qwen2.5`) completed
    with zero errors, confirming phases 9/10's roster and Groq pacing are
    correct in practice, not just in tests. That run also surfaced the
    limits of what could be concluded from it: every `LLMStrategy` move
    always announced the final round whenever it truly was one, so the
    striking round-19 cooperation collapse seen in two of the four models
    couldn't be attributed to the announcement itself vs. just a short
    20-round horizon. Built `announce_last_round` on `LLMStrategy` (see
    architecture above) plus `last_round_experiment.py` to make that
    A/B comparison real — the first of the two backlog items below is now
    done. Two live-verification side notes from diagnosing that run's
    dashboard: (a) `run_webapp.py` doesn't hot-reload — restarting the
    process is required after any code change for a live run to reflect it,
    a long-running dashboard process will otherwise silently keep using
    whatever roster/pacing logic was in memory when it started; (b) Groq's
    30 req/min cap is per **API key**, shared across every model under it,
    not per model — `groq_client()`'s per-instance pacing (`_wait_for_pacing`
    tracking its own `_last_request_time`) didn't account for this, so two
    Groq models called in the same process could together exceed the shared
    cap even though each individually paced itself; fixed by giving every
    `groq_client()` instance a shared `RequestPacer`
    (`llm_clients/openai_compatible.py`) instead of independent per-instance
    pacing state.
12. **"So-what" interpretation layer + run history — done.** Prompted by the
    user pasting dashboard screenshots and asking whether the results were
    evaluable — that question shouldn't need an LLM in the loop every time,
    the dashboard should say it itself. Two additions, deliberately scoped
    down from a larger "make it a proper project" brainstorm (see the
    deferred ideas below):
    - **So-what layer**: `static/insights.js` (new) — deterministic/
      rule-based takeaway text per view (explicitly *not* an LLM call, see
      backlog note below for why and when that might change), a `MIN_N=5`
      sample-size gate below which a claim is replaced with "not enough
      data yet," and n-badges (`.badge.n-low`/default `.badge`) next to any
      stat resting on a small sample. Reuses `.panel`/`.caveat` — no new
      container pattern, per `DESIGN.md`. New **Research Questions** view
      maps all 5 `AGENTS.md`-listed research questions to a live
      open/partial/answered status computed from whatever data already
      exists (`GET /api/last-round-experiment`, new, is what lets RQ2 go
      from permanently-open to answered once `last_round_experiment.py`
      has run). Manually verified in-browser: the endgame-collapse
      detector on the Model Comparison view reproduced, automatically, the
      exact same "collapsed to 0% in the final round" reading a human
      previously had to ask for by pasting screenshots — and the noise-sweep
      takeaway correctly re-derived the `endgame_defector`/`grim_trigger`
      crossover already documented in phase 7, from data alone.
    - **Run history**: every live run previously overwrote the prior run's
      flat result files with no history. New `src/tournament/archive.py`
      (`archive_run`/`list_archived_runs`) copies each experiment's fixed-
      name output files into `results/runs/<run_id>/` plus a
      `manifest.json`, called right after each experiment's existing write
      step — `reporting.py`'s writers themselves are untouched, and the
      flat "latest" files still work exactly as before for any existing
      consumer. Webapp runs use the already-existing `RunState.run_id`;
      the five top-level `run_*.py` scripts each generate their own
      `uuid.uuid4()` at the top of `main()`. `results/llm_transcripts.jsonl`
      gained a `run_id` field per line (still append-only, still never
      truncated). New `GET /api/runs/history` lists archived runs from
      disk, so history survives a server restart (unlike the existing
      in-memory `GET /api/runs`, which only ever answers for the current
      process's lifetime — deliberately not merged with it, different
      shape/lifetime). Verified live: two `run_v3.py` runs plus one webapp
      live run all produced independent `results/runs/<uuid>/` folders
      while `results/spatial_*` kept reflecting only the latest run, and
      `GET /api/runs/history` listed all of them correctly after a server
      restart.

    **Also fixed in passing**: the same "webapp process doesn't hot-reload"
    gotcha from phase 11 recurred here — a leftover `run_webapp.py` process
    from earlier the same day was still serving pre-phase-12 code and had
    to be restarted before any of this could be verified in-browser. Worth
    remembering as a standing gotcha, not a one-off: **always restart
    `run_webapp.py` after pulling/making backend or frontend changes**
    before trusting what the browser shows.
13. **Reasoning capture, opponent-is-AI experiment, and model
    selection/last-round experiment in the webapp — done.** Three items
    picked from the "make it a proper project" list below:
    - **Reasoning capture**: `LLMStrategy` now asks for `<C or D> - <reason>`
      (`prompts/baseline.txt`, `render_history()`) and exposes the parsed
      reason via a `last_reasoning` side-channel attribute (not a
      `Strategy.move()` return-type change, which would have broken the
      protocol for every classic strategy) — a new `parse_move_and_reason()`
      wraps the existing strict `parse_move()` unchanged, so unparseable
      responses still raise before any reasoning is touched.
      `Match.play()`/`Tournament.play()`'s `on_round` callbacks and the
      transcript JSONL schema all gained two new trailing fields
      (`reason_a`, `reason_b`) — additive, old 3-tuple transcript rows still
      read fine. Known, currently-dormant caveat: reasoning is captured for
      the *intended* pre-noise move, not the *executed* post-noise one — a
      real distinction only if an LLM+noise run path is ever added (none
      exists today). Transcript explorer shows it as a `title=` tooltip on
      each move chip.
    - **Opponent-is-AI experiment**: new `prompts/opponent_is_ai.txt` +
      `src/tournament/opponent_is_ai_experiment.py` +
      `run_opponent_is_ai_experiment.py`, mirroring
      `last_round_experiment.py`'s shape but comparing *aggregate*
      cooperation rate (no single "critical round" exists for this framing,
      unlike last-round). `build_llm_strategies()` needed **no** signature
      change — unlike `announce_last_round` (genuinely dynamic per-round
      behavior baked into `LLMStrategy.move()`), the AI-reveal condition is
      just "which prompt file got loaded," decided once by the caller;
      `cache_key()` already hashes `system_prompt`, so the two conditions'
      cache entries separate automatically with no filename suffix needed.
      Shared z-test math (`_two_proportion_z`/`_two_tailed_p_value`)
      extracted out of `last_round_experiment.py` into new
      `experiment_stats.py` first, so both experiments use the same,
      already-tested statistics code instead of a second copy.
    - **Model selection + last-round experiment in the webapp**: new
      `configured_model_names()` (`llm_roster.py`, checks env vars only, no
      client construction) backs a new `GET /api/configured-models` and
      Live Run panel checkbox list — "all checked" round-trips as
      `models=None` so the common case hits the pre-existing unfiltered
      path. `last_round_experiment.py` gained progress callbacks
      (`on_repeat_start`/`on_repeat_end`/`on_model_done`, mirroring
      `Tournament.play()`'s callback style) since it previously had zero
      instrumentation and would sit silent in the SSE log for the whole
      ~400-calls-per-model duration. New `last_round_experiment` entry in
      `EXPERIMENTS`, a repeats-count input in the Live Run form, and
      `streamRun()`'s completion refresh now calls `loadComparison()`
      instead of `loadStandings()` for this experiment type.

    **Near-miss during manual verification, worth remembering**: the first
    live browser test of the last-round-experiment panel unchecked every
    Groq model and left only the free local `qwen2.5` checked — but the run
    still called Groq. Root cause: `models` was deliberately *not* threaded
    into `_run_last_round_experiment` in the first implementation pass (a
    documented scope decision at the time), while the UI showed the model
    checkboxes for that experiment type anyway, implying they did something
    there. Fixed by actually wiring `models` through
    `run_last_round_experiment()` end-to-end rather than hiding the now-
    misleading checkboxes — verified live afterward with only `qwen2.5`
    checked, confirmed via the event log that no other model ran. **Lesson**:
    if a UI control is shown for an experiment type, it must actually affect
    that experiment type, or a user's attempt to scope down a run (for cost
    or any other reason) will silently fail. Also worth remembering
    independent of this project: `python-dotenv`'s `load_dotenv()` reloads
    keys from `.env` on every fresh process regardless of shell-level
    `env -u FOO` — trying to simulate "no providers configured" via shell
    env-unset for a manual CLI smoke test doesn't work here and can trigger
    a real live run by accident; use `monkeypatch.delenv` in a test instead.

**Backlog (not started, not currently planned in a specific order):**
- Open question from the first `last_round_experiment.py` smoke test: the
  smallest configured models (`llama-3.1-8b-instant`, local `qwen2.5`) showed
  0% last-round defection under *both* the told and untold condition, while
  `llama-3.3-70b-versatile` and `gemma4:31b-cloud` clearly differentiated
  (100% told vs. 0% untold). Reads as a real floor effect — small/fast
  instruct models may simply not act on the last-round cue at all rather
  than reacting more weakly — but was only observed at `repeats=1`; worth
  revisiting once there's more repeat data, and worth trying additional
  model tiers/providers (not necessarily swapping the current Groq pair,
  which is a clean same-family 8B/70B size ladder) if the pattern holds, to
  see where the threshold actually sits. The `run_last_round_experiment.py`
  CLI run to get that repeat data got interrupted by the machine sleeping
  mid-run on 2026-08-07 (background process silently killed, no partial
  results) — re-run with the machine plugged in/awake, or via the webapp's
  new Live Run panel support for this experiment type (see phase 13).

**"Make it a proper project" ideas (2026-08-07 scoping session, deliberately
deferred — see build-order phases 12-13 above for the items that got picked
up first: the so-what layer, run history, reasoning capture, the
opponent-is-AI experiment, and model selection/last-round-in-webapp):**
- **Noise x last-round combined experiment**: does trembling-hand noise
  (`match.py`'s noise model) wash out or amplify the announcement-driven
  endgame defection seen in `last_round_experiment.py`?
- **LLM-powered "smart summary" as a deliberate future upgrade of the
  so-what layer.** The so-what layer built in phase 12 above is
  intentionally deterministic/rule-based, not an LLM call — that's the
  right choice today because the underlying data is still simple enough
  that fixed thresholds cover it, and a click-to-summarize button has real
  latency/cost for zero benefit at this data volume. But the user
  explicitly wants this reconsidered once the project has enough moving
  parts (more experiment types, richer per-move data like captured
  reasoning — see the item above) that a fixed rule set stops being able to
  synthesize across them well. At that point, a "smart summary" button that
  makes a real LLM call over the richer gathered data (not just the current
  handful of numbers) becomes worth it — both functionally (genuine
  cross-cutting synthesis a rule table can't express) and as a portfolio/CV
  signal: this project is explicitly meant to demonstrate range across
  approaches (deterministic *and* LLM-driven UI), not just be internally
  correct. Don't build this yet — deliberately deferred until the
  deterministic layer's limits are actually felt, not preemptively.
- **Engineering polish**: CI (GitHub Actions running `uv run pytest` on
  push), finish the in-progress README rewrite (already underway per git
  status) for external readers who aren't Codex.

## Conventions

- Type hints everywhere.
- Every classic strategy gets a unit test with a known, hand-computed expected
  sequence of moves (see `tests/test_classic_strategies.py` for the pattern).
- Never call the live API inside a test. LLM-backed strategies must get a
  mock/stub mode for testing (see `tests/test_llm_strategy.py`'s `StubClient`);
  cache real responses separately during dev (`DiskCache`, see `cache.py`).
- Keep prompts for LLM strategies in separate files under `prompts/` (see
  `prompts/baseline.txt`), not inline in code, so wording can be iterated on
  without touching logic. Changing a prompt file's contents naturally
  invalidates that strategy's disk cache (the cache key hashes the prompt text).

## Gotchas

- API calls cost money and are rate-limited. Cache LLM responses to disk
  during development so re-running the tournament doesn't re-spend on
  identical (strategy, history) states.
- `run_v1.py`/`run_v2.py`/`run_webapp.py`'s live-run panel all include an LLM
  strategy per configured provider: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`,
  `OLLAMA_API_KEY` (Ollama Cloud), and `OLLAMA_ENABLED=1` (local Ollama, plus
  a server actually running on `localhost:11434`) are all independent — any
  subset can be set, unset providers are skipped with a printed notice, not
  an error.
- Ollama Cloud's free tier allows only one cloud model in flight at once.
  `Tournament` is fully sequential so this holds automatically within a run;
  `webapp/runs.py` additionally refuses to start a second *run* while one is
  in progress (`409` from `POST /api/runs`) so two live runs can't each open
  their own concurrent Ollama Cloud stream.
- The payoff matrix must satisfy `T > R > P > S` and `2R > T + S` — enforced
  by `validate_payoffs()` in `payoff.py`, but keep that invariant in mind if
  you ever touch the constants.
