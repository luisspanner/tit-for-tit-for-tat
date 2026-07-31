import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2", "#937860", "#DA8BC3",
]


def render_generations_gif(
    generations: list[list[list[str]]],
    strategy_names: list[str],
    gif_path: Path,
    legend_path: Path,
    seconds_per_frame: float = 0.3,
) -> None:
    if len(strategy_names) > len(_PALETTE):
        raise ValueError(f"Only {len(_PALETTE)} colors available, got {len(strategy_names)} strategies")

    name_to_index = {name: i for i, name in enumerate(strategy_names)}
    colors = _PALETTE[: len(strategy_names)]
    cmap = ListedColormap(colors)

    gif_path.parent.mkdir(parents=True, exist_ok=True)
    legend_path.parent.mkdir(parents=True, exist_ok=True)
    legend_path.write_text(json.dumps(dict(zip(strategy_names, colors)), indent=2))

    fig, ax = plt.subplots()
    ax.set_xticks([])
    ax.set_yticks([])

    frames = []
    for generation in generations:
        grid = [[name_to_index[name] for name in row] for row in generation]
        frame = ax.imshow(grid, cmap=cmap, vmin=0, vmax=len(strategy_names) - 1, animated=True)
        frames.append([frame])

    anim = animation.ArtistAnimation(fig, frames, interval=seconds_per_frame * 1000)
    anim.save(gif_path, writer=animation.PillowWriter(fps=1 / seconds_per_frame))
    plt.close(fig)
