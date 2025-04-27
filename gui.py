import os
import io
import dearpygui.dearpygui as dpg
import cairosvg
from PIL import Image
import chess

from models.ai import AI
from models.models import Models


class ChessBoard:
    # --- Configuration ---
    _SQUARE_SIZE = 64
    _BOARD_SIZE = 8 * _SQUARE_SIZE
    _LIGHT_COLOR = (238, 238, 210, 255)
    _DARK_COLOR = (118, 150, 86, 255)
    _HIGHLIGHT_COLOR = (255, 215, 0, 128)
    _MOVE_DOT_COLOR = (0, 0, 0, 180)
    _TEX_REGISTRY = "tex_reg"

    # --- State ---
    _board = chess.Board()
    _selected_square = None
    _piece_textures = {}
    _pending_promotion = None
    _piece_style = "cooke"
    _ai = Models.MINIMAX_DEPTH_4
    _label_to_model = {str(m): m for m in Models}

    def __play_move(self, move: chess.Move):
        self._board.push(move)
        self.__draw_board()
        ai_move = self._ai.value.move(self._board)
        self._board.push(ai_move)
        self.__draw_board()

    def __fen_to_symbol(self, fen_sym: str) -> str:
        color = "w" if fen_sym.isupper() else "b"
        return f"{color}{fen_sym.upper()}"

    def reload_textures(self):
        dpg.delete_item(self._TEX_REGISTRY, children_only=True)
        self._piece_textures.clear()
        self.__load_piece_textures()
        self.__draw_board()

    def __load_piece_textures(self):
        for sym in ("P", "N", "B", "R", "Q", "K"):
            for color in ("w", "b"):
                key = f"{color}{sym}"
                path = os.path.join("assets", self._piece_style, f"{key}.svg")
                if not os.path.isfile(path):
                    raise FileNotFoundError(f"Missing SVG: {path}")

                png = cairosvg.svg2png(
                    url=path,
                    output_width=self._SQUARE_SIZE,
                    output_height=self._SQUARE_SIZE,
                )
                img = Image.open(io.BytesIO(png)).convert("RGBA")
                raw = [c / 255.0 for px in img.getdata() for c in px]

                tex_id = dpg.add_static_texture(
                    self._SQUARE_SIZE,
                    self._SQUARE_SIZE,
                    raw,
                    parent=self._TEX_REGISTRY,
                )
                self._piece_textures[key] = tex_id

    def __on_chess_window_resize(self):
        win_w, win_h = dpg.get_item_rect_size("ChessWindow")

        content_w = win_w - 20
        content_h = win_h - 40
        size = min(content_w, content_h)

        dpg.configure_item(
            "board_drawlist",
            width=int(size),
            height=int(size),
        )

        self.__draw_board()

    def __draw_board(self):
        # clear previous draw calls
        dpg.delete_item("board_drawlist", children_only=True)

        full_w, full_h = dpg.get_item_rect_size("board_drawlist")
        board_pixels = min(full_w, full_h)
        cell = board_pixels / 8.0

        offset_x = (full_w - board_pixels) / 2.0
        offset_y = (full_h - board_pixels) / 2.0

        for rank in range(8):
            for file in range(8):
                x0 = offset_x + file * cell
                y0 = offset_y + (7 - rank) * cell
                x1 = x0 + cell
                y1 = y0 + cell
                color = (
                    self._LIGHT_COLOR if (file + rank) % 2 == 0 else self._DARK_COLOR
                )
                dpg.draw_rectangle(
                    (x0, y0), (x1, y1), fill=color, parent="board_drawlist"
                )

        # highlight selected square and show move dots
        if self._selected_square is not None:
            f0 = chess.square_file(self._selected_square)
            r0 = chess.square_rank(self._selected_square)
            x0 = offset_x + f0 * cell
            y0 = offset_y + (7 - r0) * cell
            dpg.draw_rectangle(
                (x0, y0),
                (x0 + cell, y0 + cell),
                fill=self._HIGHLIGHT_COLOR,
                parent="board_drawlist",
            )
            for mv in self._board.legal_moves:
                if mv.from_square == self._selected_square:
                    f1 = chess.square_file(mv.to_square)
                    r1 = chess.square_rank(mv.to_square)
                    cx = offset_x + f1 * cell + cell * 0.5
                    cy = offset_y + (7 - r1) * cell + cell * 0.5
                    dpg.draw_circle(
                        (cx, cy),
                        radius=cell * 0.15,
                        fill=self._MOVE_DOT_COLOR,
                        parent="board_drawlist",
                    )

        # draw each piece scaled to the current cell size
        for sq in chess.SQUARES:
            pc = self._board.piece_at(sq)
            if not pc:
                continue
            key = self.__fen_to_symbol(pc.symbol())
            tex_id = self._piece_textures[key]
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            x0 = offset_x + f * cell
            y0 = offset_y + (7 - r) * cell
            dpg.draw_image(
                tex_id, (x0, y0), (x0 + cell, y0 + cell), parent="board_drawlist"
            )

    def __on_promote(self, sender, app_data, user_data):
        promo_piece = user_data
        from_sq, to_sq = self._pending_promotion
        mv = chess.Move(from_sq, to_sq, promotion=promo_piece)
        self._pending_promotion = None
        dpg.hide_item("PromotionPopup")
        self._selected_square = None
        if mv in self._board.legal_moves:
            self.__play_move(mv)
            self.__play_move(self._ai.value.move(self._board))

    def __on_click(self, sender):
        minx, miny = dpg.get_item_rect_min(sender)
        sender_width, sender_height = dpg.get_item_rect_size(sender)
        mx, my = dpg.get_mouse_pos()
        x, y = mx - minx, my - miny
        f = int(x / sender_width * 8)
        r = 7 - int(y / sender_height * 8)
        if not (0 <= f < 8 and 0 <= r < 8):
            return
        sq = chess.square(f, r)

        # select a square
        if self._selected_square is None:
            if self._board.piece_at(sq):
                self._selected_square = sq
            self.__draw_board()
            return

        # move or promotion
        mv = chess.Move(self._selected_square, sq)
        if mv in self._board.legal_moves:
            self.__play_move(mv)
        else:
            piece = self._board.piece_at(self._selected_square)
            is_pawn = piece and piece.piece_type == chess.PAWN
            last = r in (0, 7)
            if is_pawn and last:
                self._pending_promotion = (self._selected_square, sq)
                dpg.show_item("PromotionPopup")
            else:
                self._selected_square = None

        self.__draw_board()

    def __change_model(self, sender, model: Models):
        self._ai = self._label_to_model[model]

    def start_gui(self):
        dpg.create_context()
        dpg.configure_app(docking=True, docking_space=True)

        # create one texture registry up front
        with dpg.texture_registry(tag=self._TEX_REGISTRY, show=False):
            self.__load_piece_textures()

        # Chess Board Window
        with dpg.window(label="Chess", tag="ChessWindow", no_resize=True):
            dpg.add_drawlist(
                self._BOARD_SIZE,
                self._BOARD_SIZE,
                tag="board_drawlist",
                callback=self.__on_click,
            )

            handler_reg = dpg.add_item_handler_registry()
            dpg.add_item_resize_handler(
                callback=lambda s, a, u: self.__on_chess_window_resize(),
                parent=handler_reg,
            )
            dpg.bind_item_handler_registry("ChessWindow", handler_reg)

        # Promotion picker window
        with dpg.window(
            label="Promote Pawn",
            modal=True,
            show=False,
            no_close=True,
            tag="PromotionPopup",
            no_resize=True,
        ):
            dpg.add_text("Choose piece to promote to:")
            for lbl, pt in [
                ("Queen", chess.QUEEN),
                ("Rook", chess.ROOK),
                ("Bishop", chess.BISHOP),
                ("Knight", chess.KNIGHT),
            ]:
                dpg.add_button(label=lbl, callback=self.__on_promote, user_data=pt)

        # Configuration WIndow
        with dpg.window(
            label="Model Configuration",
            autosize=True,
            no_collapse=True,
        ):
            dpg.add_text("Select AI model:")
            dpg.add_combo(
                items=list(Models), callback=self.__change_model, default_value=self._ai
            )

        dpg.load_init_file("app_layout.ini")
        dpg.create_viewport(
            title="Chess GUI",
        )

        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()
