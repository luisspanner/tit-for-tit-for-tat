import json
import uuid
from pathlib import Path

from tournament.archive import archive_run
from tournament.last_round_experiment import run_last_round_experiment
from tournament.visualization import render_line_chart

# Matches the 20-round live run this experiment is meant to be compared
# against. REPEATS=5 means, per configured model:
#   2 conditions x 2 opponents x 5 repeats x ROUNDS calls
# e.g. for the 2 Groq models sharing one paced client, that's ~400 calls
# each - expect a good chunk of time just for the Groq portion. Lower
# REPEATS for a quick smoke test before committing to a full run.
ROUNDS = 20
REPEATS = 5

PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_DIR = Path(__file__).parent / "cache"
RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()
    summary = run_last_round_experiment(system_prompt, CACHE_DIR, rounds=ROUNDS, repeats=REPEATS)

    if not summary:
        print("No LLM providers configured - nothing to run.")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_round_experiment.json").write_text(json.dumps(summary, indent=2))

    series = {}
    round_indices = list(range(ROUNDS))
    for model, result in summary.items():
        series[f"{model}_told"] = result["told"]["cooperation_by_round"]
        series[f"{model}_untold"] = result["untold"]["cooperation_by_round"]
    render_line_chart(
        round_indices, series, RESULTS_DIR / "last_round_cooperation.png",
        xlabel="round", ylabel="cooperation rate",
    )
    archive_run(
        RESULTS_DIR,
        str(uuid.uuid4()),
        "last_round_experiment",
        ["last_round_experiment.json", "last_round_cooperation.png"],
    )

    print(f"Ran {REPEATS} repeats x {ROUNDS} rounds per model, told vs. untold last-round framing.\n")
    header = f"{'model':<28}{'told defect%':>14}{'untold defect%':>16}{'z-score':>10}{'p-value':>10}"
    print(header)
    print("-" * len(header))
    for model, result in summary.items():
        told_rate = result["told"]["last_round_defect_rate"]
        untold_rate = result["untold"]["last_round_defect_rate"]
        z = result["z_score"]
        p = result["p_value"]
        if told_rate is None or untold_rate is None or z is None or p is None:
            print(f"{model:<28}{'n/a':>14}{'n/a':>16}{'n/a':>10}{'n/a':>10}")
        else:
            print(f"{model:<28}{told_rate * 100:>13.1f}%{untold_rate * 100:>15.1f}%{z:>10.2f}{p:>10.3f}")


if __name__ == "__main__":
    main()
