# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An Axelrod-style iterated Prisoner's Dilemma tournament. Classic strategies
(tit-for-tat, grim trigger, Pavlov, always-cooperate, always-defect, random)
play round-robin against each other AND against LLM-driven strategies whose
behavior is defined by a system prompt instead of code.

The research questions this is actually for:
- Do LLM-driven players converge on cooperative strategies under repeated play?
- Does behavior change when the player is told the current round is the last one?
- Does behavior change when the player is told (vs. not told) that the opponent is an AI?

## Commands

- `uv sync` — install dependencies
- `uv run pytest` — run the full test suite
- `uv run pytest tests/test_classic_strategies.py::test_tit_for_tat_hand_computed_sequence` — run a single test
- `uv run python run_v0.py` — v0 demo: tit-for-tat vs always-defect, 100 rounds, prints scores
- `uv run python run_v1.py` — v1 demo: one LLM-backed strategy vs tit-for-tat, 10 rounds (needs `ANTHROPIC_API_KEY`)
- `uv run python run_v2.py` — v2 demo: full round-robin, writes `results/matches.csv` and `results/standings.json`
  (LLM strategy included automatically only if `ANTHROPIC_API_KEY` is set)
- `uv run python run_v3.py` — v3 demo: 8x8 spatial grid, 40 generations, writes
  `results/spatial_evolution.gif`, `results/spatial_legend.json`, `results/spatial_summary.json`
- `uv run python run_noise_sweep.py` — runs the round-robin + spatial grid across a
  range of noise levels, writes `results/noise_sweep_summary.json` and two charts
- `uv run python run_ecological.py` — 100-generation replicator-dynamics run against
  the whole mixed population, writes `results/ecological_trajectory.png` + `results/ecological_summary.json`

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
  true — calls an injected `LLMClient`, parses the raw text response back into
  a `Move` via `parse_move` (strict: raises `ValueError` rather than silently
  defaulting on an unparseable response). Optionally takes a `DiskCache` —
  checked before every network call, keyed on `(system_prompt, history,
  is_last_round)` so a prompt-wording change *or* a last-round framing change
  invalidates old cache entries instead of serving a stale answer under
  different conditions.
- `src/tournament/llm_client.py` — `LLMClient` protocol (`complete(system_prompt,
  user_message) -> str`) plus `AnthropicLLMClient`, the only real implementation.
  Tests never import this class — they inject a stub `LLMClient` instead, so no
  test can accidentally reach the network.
- `src/tournament/cache.py` — `DiskCache` (JSON-backed get/set) and `cache_key`
  (sha256 over `{prompt, history, is_last_round}`). Whole file gets rewritten
  on every `set`; fine at this scale.
- `src/tournament/payoff.py` — the payoff matrix (`T=5, R=3, P=1, S=0`) and
  `score_round(move_a, move_b)`. `validate_payoffs()` runs at import time and
  enforces `T > R > P > S` and `2R > T + S` — the two conditions that make this
  a well-formed Prisoner's Dilemma. Never let a "just try something" edit to
  these constants silently violate them.
- `src/tournament/match.py` — `Match(strategy_a, strategy_b, rounds, noise=0.0,
  rng=None)`: runs two strategies against each other, constructs a `RoundContext`
  each round and passes it to both `.move()` calls, gives each side its own view
  of history, and returns final scores plus the move log. `noise` is a
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
  `.play()` returns a list of per-match result dicts; `.standings()` aggregates
  total score per strategy name across every match it appeared in (both as
  `strategy_a` and `strategy_b`) and sorts descending.
- `src/tournament/reporting.py` — `write_results_csv` / `write_standings_json`:
  plain `csv.DictWriter` / `json.dumps` to a path, creating parent dirs as needed.
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

**Backlog (not started, not currently planned in a specific order):**
- The actual multi-condition LLM experiment runner: last-round framing in a
  real run, an "opponent is AI" prompt variant, and structured experiment
  logging (full transcripts + scores per condition) for real analysis — still
  blocked on `ANTHROPIC_API_KEY` for live execution, though buildable with the
  stub client any time.

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
- The payoff matrix must satisfy `T > R > P > S` and `2R > T + S` — enforced
  by `validate_payoffs()` in `payoff.py`, but keep that invariant in mind if
  you ever touch the constants.
