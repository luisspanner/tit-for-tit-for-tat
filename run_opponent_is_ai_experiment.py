import json
import uuid
from pathlib import Path

from tournament.archive import archive_run
from tournament.opponent_is_ai_experiment import run_opponent_is_ai_experiment
from tournament.visualization import render_bar_chart

ROUNDS = 20
REPEATS = 5

PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_DIR = Path(__file__).parent / "cache"
RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    summary = run_opponent_is_ai_experiment(CACHE_DIR, PROMPTS_DIR, rounds=ROUNDS, repeats=REPEATS)

    if not summary:
        print("No LLM providers configured - nothing to run.")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "opponent_is_ai_experiment.json").write_text(json.dumps(summary, indent=2))

    labels = list(summary.keys())
    series = {
        "baseline": [summary[m]["baseline"]["cooperation_rate"] or 0.0 for m in labels],
        "ai_revealed": [summary[m]["ai_revealed"]["cooperation_rate"] or 0.0 for m in labels],
    }
    render_bar_chart(labels, series, RESULTS_DIR / "opponent_is_ai_cooperation.png", ylabel="cooperation rate")
    archive_run(
        RESULTS_DIR,
        str(uuid.uuid4()),
        "opponent_is_ai_experiment",
        ["opponent_is_ai_experiment.json", "opponent_is_ai_cooperation.png"],
    )

    print(f"Ran {REPEATS} repeats x {ROUNDS} rounds per model, baseline vs. opponent-is-AI framing.\n")
    header = f"{'model':<28}{'baseline coop%':>16}{'ai-revealed coop%':>19}{'z-score':>10}{'p-value':>10}"
    print(header)
    print("-" * len(header))
    for model, result in summary.items():
        baseline_rate = result["baseline"]["cooperation_rate"]
        ai_rate = result["ai_revealed"]["cooperation_rate"]
        z = result["z_score"]
        p = result["p_value"]
        if baseline_rate is None or ai_rate is None or z is None or p is None:
            print(f"{model:<28}{'n/a':>16}{'n/a':>19}{'n/a':>10}{'n/a':>10}")
        else:
            print(f"{model:<28}{baseline_rate * 100:>15.1f}%{ai_rate * 100:>18.1f}%{z:>10.2f}{p:>10.3f}")


if __name__ == "__main__":
    main()
