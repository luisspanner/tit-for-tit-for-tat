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

**v0**: two hardcoded classic strategies (tit-for-tat vs always-defect), 100
rounds, scores printed to stdout. See `CLAUDE.md` for the full architecture
and build-order roadmap (v1: LLM-backed strategies, v2: full round-robin +
CSV/JSON output, v3: spatial/evolutionary variant).

## Usage

```
uv sync
uv run python run_v0.py
uv run pytest
```
