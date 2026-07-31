import json
from pathlib import Path

from tournament.visualization import render_generations_gif


def test_render_generations_gif_produces_valid_gif_and_legend(tmp_path: Path) -> None:
    generations = [
        [["a", "b"], ["b", "a"]],
        [["a", "a"], ["b", "b"]],
    ]
    gif_path = tmp_path / "nested" / "evolution.gif"
    legend_path = tmp_path / "nested" / "legend.json"

    render_generations_gif(generations, strategy_names=["a", "b"], gif_path=gif_path, legend_path=legend_path)

    assert gif_path.exists()
    assert gif_path.stat().st_size > 0
    with gif_path.open("rb") as f:
        assert f.read(6) in (b"GIF87a", b"GIF89a")

    legend = json.loads(legend_path.read_text())
    assert set(legend) == {"a", "b"}
