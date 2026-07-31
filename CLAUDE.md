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
- `uv run python run_v0.py` — run the v0 demo (tit-for-tat vs always-defect, 100 rounds, prints scores)

## Architecture

- `src/tournament/strategies/base.py` — the `Strategy` protocol every player implements:
  `move(history: list[tuple[Move, Move]]) -> Move`, where `Move` is `Literal["C", "D"]`
  and `history` is `(my_move, opponent_move)` pairs, oldest first. Both classic and
  LLM-backed strategies implement this same interface.
- `src/tournament/strategies/classic.py` — hardcoded strategies (`TitForTat`,
  `AlwaysDefect` so far).
- `src/tournament/payoff.py` — the payoff matrix (`T=5, R=3, P=1, S=0`) and
  `score_round(move_a, move_b)`. `validate_payoffs()` runs at import time and
  enforces `T > R > P > S` and `2R > T + S` — the two conditions that make this
  a well-formed Prisoner's Dilemma. Never let a "just try something" edit to
  these constants silently violate them.
- `src/tournament/match.py` — `Match(strategy_a, strategy_b, rounds)`: runs two
  strategies against each other, gives each side its own view of history, and
  returns final scores plus the move log.
- A `Tournament` class (round-robin across many strategies, result aggregation)
  does not exist yet — it belongs to v2, below.

## Build order (do NOT skip ahead)

1. **v0 — done.** Two hardcoded classic strategies (tit-for-tat vs
   always-defect), 100 rounds, print the scores. No LLM calls.
2. **v1 — not started.** Add one LLM-backed strategy via a system prompt,
   single match against tit-for-tat.
3. **v2 — not started.** Full round-robin among all classic strategies (add
   grim trigger, Pavlov, always-cooperate, random) + 1-2 LLM strategies,
   results logged to CSV/JSON. This is where the `Tournament` class gets built.
4. **v3 (stretch, only after v2 works) — not started.** Spatial/evolutionary
   variant — strategies placed on a grid, reproduce proportional to local
   payoff (Nowak-May dynamics), visualize over generations.

## Conventions

- Type hints everywhere.
- Every classic strategy gets a unit test with a known, hand-computed expected
  sequence of moves (see `tests/test_classic_strategies.py` for the pattern).
- Never call the live API inside a test. LLM-backed strategies must get a
  mock/stub mode for testing; cache real responses separately during dev.
- Keep prompts for LLM strategies in separate files under `prompts/` (not
  created yet — first needed in v1), not inline in code, so wording can be
  iterated on without touching logic.

## Gotchas

- API calls cost money and are rate-limited. Cache LLM responses to disk
  during development so re-running the tournament doesn't re-spend on
  identical (strategy, history) states.
- The payoff matrix must satisfy `T > R > P > S` and `2R > T + S` — enforced
  by `validate_payoffs()` in `payoff.py`, but keep that invariant in mind if
  you ever touch the constants.
