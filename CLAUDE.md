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

Always invoke through `uv run` — see the README for why a directly-activated
`python` can silently fail to import `tournament` on this machine.

## Architecture

- `src/tournament/strategies/base.py` — the `Strategy` protocol every player implements:
  `move(history: list[tuple[Move, Move]]) -> Move`, where `Move` is `Literal["C", "D"]`
  and `history` is `(my_move, opponent_move)` pairs, oldest first. Both classic and
  LLM-backed strategies implement this same interface, and are pure functions of the
  `history` argument — no per-instance mutable state — which is what lets the same
  strategy instance be reused across every match in a round-robin.
- `src/tournament/strategies/classic.py` — `TitForTat`, `AlwaysDefect`,
  `AlwaysCooperate`, `GrimTrigger` (defects forever after the opponent's first
  defection), `Pavlov` (win-stay/lose-shift: repeats its last move after a good
  outcome (`R` or `T`), switches after a bad one (`P` or `S`)), `RandomStrategy`
  (seedable `random.Random` instance, `p_cooperate` controls the coin weighting).
- `src/tournament/strategies/llm.py` — `LLMStrategy`: renders `history` into a
  user-message prompt via `render_history`, calls an injected `LLMClient`, parses
  the raw text response back into a `Move` via `parse_move` (strict: raises
  `ValueError` rather than silently defaulting on an unparseable response).
  Optionally takes a `DiskCache` — checked before every network call, keyed on
  `(system_prompt, history)` so a prompt-wording change invalidates old cache
  entries instead of serving stale answers under a new prompt.
- `src/tournament/llm_client.py` — `LLMClient` protocol (`complete(system_prompt,
  user_message) -> str`) plus `AnthropicLLMClient`, the only real implementation.
  Tests never import this class — they inject a stub `LLMClient` instead, so no
  test can accidentally reach the network.
- `src/tournament/cache.py` — `DiskCache` (JSON-backed get/set) and `cache_key`
  (sha256 over `{prompt, history}`). Whole file gets rewritten on every `set`;
  fine at this scale.
- `src/tournament/payoff.py` — the payoff matrix (`T=5, R=3, P=1, S=0`) and
  `score_round(move_a, move_b)`. `validate_payoffs()` runs at import time and
  enforces `T > R > P > S` and `2R > T + S` — the two conditions that make this
  a well-formed Prisoner's Dilemma. Never let a "just try something" edit to
  these constants silently violate them.
- `src/tournament/match.py` — `Match(strategy_a, strategy_b, rounds)`: runs two
  strategies against each other, gives each side its own view of history, and
  returns final scores plus the move log.
- `src/tournament/tournament.py` — `Tournament(strategies, rounds)`: round-robin
  over every unordered pair **including each strategy against itself** (a
  strategy's self-play score is a real signal — e.g. two `GrimTrigger`s always
  mutually cooperate). `.play()` returns a list of per-match result dicts;
  `.standings()` aggregates total score per strategy name across every match it
  appeared in (both as `strategy_a` and `strategy_b`) and sorts descending.
- `src/tournament/reporting.py` — `write_results_csv` / `write_standings_json`:
  plain `csv.DictWriter` / `json.dumps` to a path, creating parent dirs as needed.
- `src/tournament/spatial.py` — `Grid(size, strategy_factories, seed)`: a toroidal
  (wraparound) grid running Nowak-May spatial dynamics. Each cell holds a strategy
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
  `strategy name -> hex color` legend JSON alongside it.

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
