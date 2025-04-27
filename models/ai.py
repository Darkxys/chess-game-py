import chess
from abc import ABC, abstractmethod


class AI(ABC):
    @abstractmethod
    def move(self, board: chess.Board) -> chess.Move:
        """
        Given a chess.Board, return the "best" move.
        """
