"""
Widget PyQt6 représentant l'échiquier interactif.
"""
import chess
from typing import Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen,
    QMouseEvent, QPaintEvent
)
from PyQt6.QtCore import Qt, QRect, pyqtSignal

PALETTE = {
    "light_square":    QColor("#F0D9B5"),
    "dark_square":     QColor("#B58863"),
    "selected":        QColor(20,  85,  30, 160),
    "legal_move":      QColor(20,  85,  30,  80),
    "last_move_light": QColor("#CDD16E"),
    "last_move_dark":  QColor("#AABA44"),
    "check":           QColor(220,  30,  30, 180),
    "border_bg":       QColor("#8B6914"),   # fond de la bordure
    "border_text":     QColor("#F0D9B5"),   # texte dans la bordure
}

PIECE_UNICODE = {
    (chess.KING,   chess.WHITE): "♔",
    (chess.QUEEN,  chess.WHITE): "♕",
    (chess.ROOK,   chess.WHITE): "♖",
    (chess.BISHOP, chess.WHITE): "♗",
    (chess.KNIGHT, chess.WHITE): "♘",
    (chess.PAWN,   chess.WHITE): "♙",
    (chess.KING,   chess.BLACK): "♚",
    (chess.QUEEN,  chess.BLACK): "♛",
    (chess.ROOK,   chess.BLACK): "♜",
    (chess.BISHOP, chess.BLACK): "♝",
    (chess.KNIGHT, chess.BLACK): "♞",
    (chess.PAWN,   chess.BLACK): "♟",
}

BORDER = 24   # épaisseur de la bordure en pixels


class BoardWidget(QWidget):
    move_requested = pyqtSignal(chess.Move)
    square_clicked = pyqtSignal(chess.Square)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._board: chess.Board = chess.Board()
        self._selected_square: Optional[chess.Square] = None
        self._legal_moves: list[chess.Move] = []
        self._last_move: Optional[chess.Move] = None
        self._flipped: bool = False
        self._human_color: chess.Color = chess.WHITE
        self.setMinimumSize(400, 400)

    # ---------------------------------------------------------------- #
    #  API publique                                                      #
    # ---------------------------------------------------------------- #

    def update_board(self, board: chess.Board):
        self._board = board
        if self._selected_square is not None:
            piece = board.piece_at(self._selected_square)
            if piece is None or piece.color != board.turn:
                self._clear_selection()
        self.update()

    def set_last_move(self, move: Optional[chess.Move]):
        self._last_move = move
        self.update()

    def flip_board(self):
        self._flipped = not self._flipped
        self.update()

    def set_human_color(self, color: chess.Color):
        self._human_color = color

    # ---------------------------------------------------------------- #
    #  Géométrie                                                         #
    # ---------------------------------------------------------------- #

    def _square_size(self) -> int:
        """Taille d'une case en tenant compte de la bordure."""
        return (min(self.width(), self.height()) - 2 * BORDER) // 8

    def _board_origin(self):
        """Coin haut-gauche de l'échiquier (après la bordure)."""
        return BORDER, BORDER

    def _square_rect(self, col: int, row: int) -> QRect:
        sq = self._square_size()
        ox, oy = self._board_origin()
        return QRect(ox + col * sq, oy + row * sq, sq, sq)

    def _screen_to_square(self, col: int, row: int) -> chess.Square:
        if self._flipped:
            file = 7 - col
            rank = row
        else:
            file = col
            rank = 7 - row
        return chess.square(file, rank)

    # ---------------------------------------------------------------- #
    #  Dessin principal                                                  #
    # ---------------------------------------------------------------- #

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sq = self._square_size()
        ox, oy = self._board_origin()

        # 1. Fond de la bordure
        total = sq * 8 + 2 * BORDER
        painter.fillRect(QRect(0, 0, total, total), PALETTE["border_bg"])

        # 2. Cases + pièces
        for row in range(8):
            for col in range(8):
                square = self._screen_to_square(col, row)
                rect = self._square_rect(col, row)
                f = chess.square_file(square)
                r = chess.square_rank(square)
                is_light = (f + r) % 2 != 0
                self._draw_square(painter, rect, square, is_light, sq)

        # 3. Coordonnées dans la bordure (par-dessus tout)
        self._draw_coordinates(painter, sq, ox, oy)

        painter.end()

    def _draw_square(self, p: QPainter, rect: QRect,
                     square: chess.Square, is_light: bool, sq_size: int):
        # Fond
        p.fillRect(rect, self._square_background(square, is_light))

        # Indicateurs coups légaux
        if square in [m.to_square for m in self._legal_moves]:
            if self._board.piece_at(square):
                p.setPen(QPen(PALETTE["selected"], 4))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(rect.adjusted(3, 3, -3, -3))
            else:
                dot_r = sq_size // 6
                cx, cy = rect.center().x(), rect.center().y()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(PALETTE["legal_move"])
                p.drawEllipse(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2)

        # Pièce
        piece = self._board.piece_at(square)
        if piece:
            self._draw_piece(p, rect, piece, sq_size)

    def _draw_piece(self, p: QPainter, rect: QRect, piece: chess.Piece, sq_size: int):
        symbol = PIECE_UNICODE.get((piece.piece_type, piece.color), "?")
        font = QFont("Segoe UI Symbol", int(sq_size * 0.72))
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        p.setFont(font)
        p.setPen(QColor(0, 0, 0, 60))
        p.drawText(rect.adjusted(2, 2, 2, 2), Qt.AlignmentFlag.AlignCenter, symbol)
        p.setPen(QColor("#1a1a1a") if piece.color == chess.BLACK else QColor("#FFFDE7"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)

    def _draw_coordinates(self, p: QPainter, sq: int, ox: int, oy: int):
        """Dessine a-h et 1-8 dans la bordure autour de l'échiquier."""
        font = QFont("Arial", max(9, BORDER * 55 // 100), QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(PALETTE["border_text"])

        for i in range(8):
            # Rangs (1-8) — bordure gauche, centré verticalement sur chaque case
            rank_num = i if self._flipped else 7 - i
            p.drawText(
                QRect(0, oy + i * sq, BORDER, sq),
                Qt.AlignmentFlag.AlignCenter,
                str(rank_num + 1),
            )

            # Fichiers (a-h) — bordure basse, centré horizontalement sur chaque case
            file_num = 7 - i if self._flipped else i
            p.drawText(
                QRect(ox + i * sq, oy + 8 * sq, sq, BORDER),
                Qt.AlignmentFlag.AlignCenter,
                chess.FILE_NAMES[file_num],
            )

    def _square_background(self, square: chess.Square, is_light: bool) -> QColor:
        king_sq = self._board.king(self._board.turn)
        if self._board.is_check() and square == king_sq:
            return PALETTE["check"]
        if self._last_move and square in (self._last_move.from_square,
                                          self._last_move.to_square):
            return PALETTE["last_move_light"] if is_light else PALETTE["last_move_dark"]
        if square == self._selected_square:
            return PALETTE["selected"]
        return PALETTE["light_square"] if is_light else PALETTE["dark_square"]

    # ---------------------------------------------------------------- #
    #  Souris                                                            #
    # ---------------------------------------------------------------- #

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()  # reprendre le focus pour les flèches
        if event.button() != Qt.MouseButton.LeftButton:
            return
        sq = self._square_size()
        ox, oy = self._board_origin()
        x = int(event.position().x()) - ox
        y = int(event.position().y()) - oy
        col = x // sq
        row = y // sq
        if not (0 <= col < 8 and 0 <= row < 8):
            return
        square = self._screen_to_square(col, row)
        self.square_clicked.emit(square)
        self._handle_click(square)

    def _handle_click(self, square: chess.Square):
        if self._selected_square is not None:
            move = self._find_move(self._selected_square, square)
            if move:
                self._clear_selection()
                self.move_requested.emit(move)
                return
            self._clear_selection()

        piece = self._board.piece_at(square)
        if piece and piece.color == self._board.turn:
            self._selected_square = square
            self._legal_moves = [
                m for m in self._board.legal_moves if m.from_square == square
            ]
            self.update()

    def _find_move(self, from_sq: chess.Square,
                   to_sq: chess.Square) -> Optional[chess.Move]:
        for move in self._legal_moves:
            if move.to_square == to_sq:
                if move.promotion:
                    return chess.Move(from_sq, to_sq, chess.QUEEN)
                return move
        return None

    def _clear_selection(self):
        self._selected_square = None
        self._legal_moves = []

    def keyPressEvent(self, event):
        # Déléguer les flèches à la fenêtre principale
        from PyQt6.QtCore import QCoreApplication
        QCoreApplication.sendEvent(self.parent(), event)

    def resizeEvent(self, event):
        self.update()