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

Backlog: a noise-sweep experiment (does GrimTrigger's/EndgameDefector's edge
survive real noise?), an ecological/population-proportional tournament, and
the actual multi-condition LLM experiment runner (last-round framing,
opponent-is-AI framing) — see `CLAUDE.md` for details.

See `CLAUDE.md` for full architecture.

## Usage

```
uv sync
uv run python run_v0.py
uv run python run_v1.py   # needs ANTHROPIC_API_KEY set
uv run python run_v2.py   # LLM strategy included only if ANTHROPIC_API_KEY is set
uv run python run_v3.py
uv run pytest
```

Always run scripts through `uv run`, not a directly-activated `python`. On
this machine that used to fail with `ModuleNotFoundError: No module named
'tournament'` because the project lived under `~/Desktop`, and macOS's
iCloud Desktop/Documents sync marks newly written files hidden
(`UF_HIDDEN`) — including `uv`'s editable-install `.pth` file — which
CPython 3.13's `site.py` then silently skips. The fix was moving the
project out of `~/Desktop` entirely (not a `uv run` workaround — `uv run`
hits the exact same bug, since it just execs the venv's own `python`).
