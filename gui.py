import os
import io
import dearpygui.dearpygui as dpg
import cairosvg
from PIL import Image
import chess


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

                # no explicit `tag=` here—just parent it
                tex_id = dpg.add_static_texture(
                    self._SQUARE_SIZE,
                    self._SQUARE_SIZE,
                    raw,
                    parent=self._TEX_REGISTRY,
                )
                self._piece_textures[key] = tex_id

    def __draw_board(self):
        dpg.delete_item("board_drawlist", children_only=True)

        # draw squares
        for r in range(8):
            for f in range(8):
                color = self._LIGHT_COLOR if (r + f) % 2 == 0 else self._DARK_COLOR
                x, y = f * self._SQUARE_SIZE, (7 - r) * self._SQUARE_SIZE
                dpg.draw_rectangle(
                    (x, y),
                    (x + self._SQUARE_SIZE, y + self._SQUARE_SIZE),
                    fill=color,
                    parent="board_drawlist",
                )

        # highlight + move dots
        if self._selected_square is not None:
            f0, r0 = chess.square_file(self._selected_square), chess.square_rank(
                self._selected_square
            )
            x0, y0 = f0 * self._SQUARE_SIZE, (7 - r0) * self._SQUARE_SIZE
            dpg.draw_rectangle(
                (x0, y0),
                (x0 + self._SQUARE_SIZE, y0 + self._SQUARE_SIZE),
                fill=self._HIGHLIGHT_COLOR,
                parent="board_drawlist",
            )
            for mv in self._board.legal_moves:
                if mv.from_square == self._selected_square:
                    f1, r1 = chess.square_file(mv.to_square), chess.square_rank(
                        mv.to_square
                    )
                    cx = f1 * self._SQUARE_SIZE + self._SQUARE_SIZE / 2
                    cy = (7 - r1) * self._SQUARE_SIZE + self._SQUARE_SIZE / 2
                    dpg.draw_circle(
                        (cx, cy),
                        self._SQUARE_SIZE * 0.15,
                        fill=self._MOVE_DOT_COLOR,
                        parent="board_drawlist",
                    )

        # draw pieces
        for sq in chess.SQUARES:
            pc = self._board.piece_at(sq)
            if not pc:
                continue
            key = self.__fen_to_symbol(pc.symbol())
            tex_id = self._piece_textures[key]
            f, r = chess.square_file(sq), chess.square_rank(sq)
            x, y = f * self._SQUARE_SIZE, (7 - r) * self._SQUARE_SIZE
            dpg.draw_image(
                tex_id,
                (x, y),
                (x + self._SQUARE_SIZE, y + self._SQUARE_SIZE),
                parent="board_drawlist",
            )

    def __on_promote(self, sender, app_data, user_data):
        promo_piece = user_data
        from_sq, to_sq = self._pending_promotion
        mv = chess.Move(from_sq, to_sq, promotion=promo_piece)
        if mv in self._board.legal_moves:
            self._board.push(mv)
        self._pending_promotion = None
        dpg.hide_item("PromotionPopup")
        self._selected_square = None
        self.__draw_board()

    def __on_click(self, sender):
        minx, miny = dpg.get_item_rect_min(sender)
        mx, my = dpg.get_mouse_pos()
        x, y = mx - minx, my - miny
        f = int(x // self._SQUARE_SIZE)
        r = 7 - int(y // self._SQUARE_SIZE)
        if not (0 <= f < 8 and 0 <= r < 8):
            return
        sq = chess.square(f, r)

        # select
        if self._selected_square is None:
            if self._board.piece_at(sq):
                self._selected_square = sq
            self.__draw_board()
            return

        # move or promotion
        mv = chess.Move(self._selected_square, sq)
        if mv in self._board.legal_moves:
            self._board.push(mv)
            self._selected_square = None
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

    def start_gui(self):
        dpg.create_context()

        # create one texture registry up front
        with dpg.texture_registry(tag=self._TEX_REGISTRY, show=False):
            self.__load_piece_textures()

        # main UI
        with dpg.window(
            label="Chess",
            tag="ChessWindow",
            width=self._BOARD_SIZE + 20,
            height=self._BOARD_SIZE + 40,
        ):
            dpg.add_drawlist(
                self._BOARD_SIZE,
                self._BOARD_SIZE,
                tag="board_drawlist",
                callback=self.__on_click,
            )

        # promotion picker
        with dpg.window(
            label="Promote Pawn",
            modal=True,
            show=False,
            no_close=True,
            tag="PromotionPopup",
            autosize=True,
        ):
            dpg.add_text("Choose piece to promote to:")
            for lbl, pt in [
                ("Queen", chess.QUEEN),
                ("Rook", chess.ROOK),
                ("Bishop", chess.BISHOP),
                ("Knight", chess.KNIGHT),
            ]:
                dpg.add_button(label=lbl, callback=self.__on_promote, user_data=pt)

        dpg.set_primary_window("ChessWindow", True)
        self.__draw_board()
        dpg.create_viewport(
            title="Chess GUI",
            width=self._BOARD_SIZE + 35,
            height=self._BOARD_SIZE + 55,
        )
        dpg.set_viewport_resizable(False)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()
