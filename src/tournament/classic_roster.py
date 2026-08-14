import random
from typing import Callable

from tournament.strategies.base import Strategy
from tournament.strategies.classic import (
    AlwaysCooperate,
    AlwaysDefect,
    EndgameDefector,
    GenerousTitForTat,
    GrimTrigger,
    Joss,
    Pavlov,
    RandomStrategy,
    TitForTat,
)


def build_classic_strategies() -> list[Strategy]:
    return [
        TitForTat(),
        AlwaysDefect(),
        AlwaysCooperate(),
        GrimTrigger(),
        Pavlov(),
        RandomStrategy(seed=42),
        GenerousTitForTat(seed=43),
        Joss(seed=44),
        EndgameDefector(),
    ]


CLASSIC_STRATEGY_FACTORIES: dict[str, Callable[[random.Random], Strategy]] = {
    "tit_for_tat": lambda rng: TitForTat(),
    "always_defect": lambda rng: AlwaysDefect(),
    "always_cooperate": lambda rng: AlwaysCooperate(),
    "grim_trigger": lambda rng: GrimTrigger(),
    "pavlov": lambda rng: Pavlov(),
    "random": lambda rng: RandomStrategy(seed=rng.getrandbits(32)),
    "generous_tit_for_tat": lambda rng: GenerousTitForTat(seed=rng.getrandbits(32)),
    "joss": lambda rng: Joss(seed=rng.getrandbits(32)),
    "endgame_defector": lambda rng: EndgameDefector(),
}
