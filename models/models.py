from enum import Enum

from models.ai import AI
from models.minimax import MiniMax


class Models(Enum):
    MINIMAX_DEPTH_2 = (MiniMax, (2,))
    MINIMAX_DEPTH_4 = (MiniMax, (4,))
    MINIMAX_DEPTH_6 = (MiniMax, (6,))

    def __init__(self, ai_cls: AI, init_args: tuple):
        inst = ai_cls(*init_args)
        self._value_: AI = inst
        self.label = f"{ai_cls.__name__}{init_args}"

    def __str__(self) -> str:
        return self.label
