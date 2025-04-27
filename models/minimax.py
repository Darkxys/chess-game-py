from typing import Optional, Tuple
import chess, math

from models.ai import AI

PIECE_VALUES = {
    chess.PAWN: 5,
    chess.KNIGHT: 30,
    chess.BISHOP: 45,
    chess.ROOK: 60,
    chess.QUEEN: 90,
}


class MiniMax(AI):
    def __init__(self, max_depth: int = 4):
        self.max_depth = max_depth
        # transposition table: key → (score, best_move, depth_searched, flag)
        # flag: 0=EXACT, -1=LOWERBOUND, +1=UPPERBOUND
        self.tt: dict[int, Tuple[float, chess.Move, int, int]] = {}
        # killer moves per depth
        self.killers: dict[int, chess.Move] = {}

    def __evaluate_position(self, board: chess.Board) -> float:
        total = 0.0
        vals = PIECE_VALUES
        for p in board.piece_map().values():
            total += vals.get(p.piece_type, 0) * (1 if p.color else -1)
        return total

    def _order_moves(self, board: chess.Board, depth: int) -> list[chess.Move]:
        """Killer first, then MVV-LVA on captures, then the rest."""
        km = self.killers.get(depth)
        moves = list(board.legal_moves)
        ordered: list[chess.Move] = []
        if km in moves:
            ordered.append(km)
            moves.remove(km)

        # capture MVV–LVA
        def mvv_lva(m: chess.Move) -> int:
            if board.is_capture(m):
                vic = board.piece_at(
                    m.to_square
                    if not board.is_en_passant(m)
                    else (m.to_square + (-8 if board.turn else +8))
                )
                atk = board.piece_at(m.from_square)
                v = PIECE_VALUES.get(vic.piece_type, 0) if vic else 0
                a = PIECE_VALUES.get(atk.piece_type, 0) if atk else 0
                return v * 100 - a
            return -1  # so non-captures sort last

        captures = [m for m in moves if board.is_capture(m)]
        captures.sort(key=mvv_lva, reverse=True)
        ordered += captures

        # the rest
        ordered += [m for m in moves if not board.is_capture(m)]
        return ordered

    def __min(
        self, board: chess.Board, depth: int, alpha: float, beta: float
    ) -> Tuple[float, Optional[chess.Move]]:
        key = board.fen()
        entry = self.tt.get(key)
        if entry and entry[2] >= depth:
            sc, mv, _, flag = entry
            if flag == 0 or (flag > 0 and sc <= alpha) or (flag < 0 and sc < beta):
                return sc, mv

        if depth == 0:
            return self.__evaluate_position(board), None

        best_score = math.inf
        best_move: Optional[chess.Move] = None
        alpha0 = alpha

        push, pop = board.push, board.pop
        for move in self._order_moves(board, depth):
            push(move)
            score, _ = self.__max(board, depth - 1, alpha, beta)
            pop()

            if score < best_score:
                best_score, best_move = score, move

            beta = min(beta, best_score)
            if alpha >= beta:
                # record killer and cutoff
                self.killers[depth] = move
                break

        # store in TT
        if best_score <= alpha0:
            flag = +1  # upperbound
        elif best_score >= beta:
            flag = -1  # lowerbound
        else:
            flag = 0  # exact
        self.tt[key] = (best_score, best_move or chess.Move.null(), depth, flag)

        return best_score, best_move

    def __max(
        self, board: chess.Board, depth: int, alpha: float, beta: float
    ) -> Tuple[float, Optional[chess.Move]]:
        key = board.fen()
        entry = self.tt.get(key)
        if entry and entry[2] >= depth:
            sc, mv, _, flag = entry
            if flag == 0 or (flag < 0 and sc >= beta) or (flag > 0 and sc > alpha):
                return sc, mv

        if depth == 0:
            return self.__evaluate_position(board), None

        best_score = -math.inf
        best_move: Optional[chess.Move] = None
        beta0 = beta

        push, pop = board.push, board.pop
        for move in self._order_moves(board, depth):
            push(move)
            score, _ = self.__min(board, depth - 1, alpha, beta)
            pop()

            if score > best_score:
                best_score, best_move = score, move

            alpha = max(alpha, best_score)
            if alpha >= beta:
                self.killers[depth] = move
                break

        # store in TT
        if best_score <= alpha:
            flag = +1
        elif best_score >= beta0:
            flag = -1
        else:
            flag = 0
        self.tt[key] = (best_score, best_move or chess.Move.null(), depth, flag)

        return best_score, best_move

    def move(self, board: chess.Board) -> chess.Move:
        board_copy = board.copy()
        best_move: Optional[chess.Move] = None

        for d in range(1, self.max_depth + 1):
            alpha, beta = -math.inf, math.inf
            if board_copy.turn == chess.WHITE:
                _, mv = self.__max(board_copy, d, alpha, beta)
            else:
                _, mv = self.__min(board_copy, d, alpha, beta)
            if mv is not None:
                best_move = mv

        assert best_move is not None, "No legal move found"
        return best_move
