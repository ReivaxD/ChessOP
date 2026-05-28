"""
Widget d'affichage de l'arbre de coups avec variantes.
Chaque tour s'affiche sur une ligne : "1. e4   e5"
Variantes entre parenthèses après le tour concerné.
Les coups sont cliquables pour naviguer.
"""
import chess
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QFont,
    QMouseEvent
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.game_tree import Node, GameTree

COLOR_MAIN_MOVE  = "#dce0e8"
COLOR_VARIATION  = "#89b4fa"
COLOR_MOVE_NUM   = "#6c7086"
COLOR_CURRENT    = "#a6e3a1"
COLOR_BG         = "#1e1e2e"
COLOR_PAREN      = "#7f849c"


class MoveTreeWidget(QTextEdit):
    node_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"background: {COLOR_BG}; border-radius: 4px; padding: 4px;")
        self.setFont(QFont("Courier New", 11))
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._game: GameTree = None
        self._current_node: Node = None
        self._anchor_map: dict[str, Node] = {}

    def set_game(self, game: GameTree):
        self._game = game

    def refresh(self, current_node: Node):
        self._current_node = current_node
        self._anchor_map.clear()
        self.clear()
        if self._game is None:
            return
        cursor = self.textCursor()
        self._render_main(cursor, self._game.root)
        self.ensureCursorVisible()

    # ---------------------------------------------------------------- #
    #  Rendu ligne principale                                            #
    # ---------------------------------------------------------------- #

    def _render_main(self, cursor: QTextCursor, node: Node):
        """Parcourt la ligne principale, 1 tour par ligne."""
        current = node
        while current.children:
            white_node = current.children[0]
            alts_after_white = current.children[1:]

            # Numéro de tour
            full = white_node.board.fullmove_number
            self._write(cursor, f"{full}. ", COLOR_MOVE_NUM)

            # Coup blanc
            self._write_move(cursor, white_node.san(), white_node,
                             COLOR_CURRENT if white_node is self._current_node
                             else COLOR_MAIN_MOVE,
                             bold=(white_node is self._current_node))

            # Variantes après le coup blanc
            for alt in alts_after_white:
                self._write(cursor, "  (", COLOR_PAREN)
                self._write(cursor, f"{full}. ", COLOR_MOVE_NUM)
                is_cur = (alt is self._current_node)
                self._write_move(cursor, alt.san(), alt, COLOR_VARIATION, bold=is_cur)
                self._write(cursor, " ", COLOR_MAIN_MOVE)
                self._render_variation(cursor, alt)
                self._write(cursor, ")", COLOR_PAREN)

            # Coup noir (si existe)
            if white_node.children:
                black_node = white_node.children[0]
                alts_after_black = white_node.children[1:]

                self._write(cursor, "   ", COLOR_MAIN_MOVE)
                self._write_move(cursor, black_node.san(), black_node,
                                 COLOR_CURRENT if black_node is self._current_node
                                 else COLOR_MAIN_MOVE,
                                 bold=(black_node is self._current_node))

                # Variantes après le coup noir
                for alt in alts_after_black:
                    self._write(cursor, "  (", COLOR_PAREN)
                    self._write(cursor, f"{full}... ", COLOR_MOVE_NUM)
                    is_cur = (alt is self._current_node)
                    self._write_move(cursor, alt.san(), alt, COLOR_VARIATION, bold=is_cur)
                    self._write(cursor, " ", COLOR_MAIN_MOVE)
                    self._render_variation(cursor, alt)
                    self._write(cursor, ")", COLOR_PAREN)

                current = black_node
            else:
                current = white_node

            # Retour à la ligne entre chaque tour
            cursor.insertText("\n")

    def _render_variation(self, cursor: QTextCursor, node: Node):
        """Affiche récursivement une variante en ligne."""
        if not node.children:
            return
        main = node.children[0]
        alts = node.children[1:]

        is_white = node.board.turn == chess.WHITE
        full = main.board.fullmove_number
        num_str = f"{full}. " if is_white else f"{full}... "
        self._write(cursor, num_str, COLOR_MOVE_NUM)

        is_cur = (main is self._current_node)
        self._write_move(cursor, main.san(), main, COLOR_VARIATION, bold=is_cur)
        self._write(cursor, " ", COLOR_MAIN_MOVE)

        for alt in alts:
            self._write(cursor, "(", COLOR_PAREN)
            self._render_variation(cursor, alt)
            self._write(cursor, ") ", COLOR_PAREN)

        self._render_variation(cursor, main)

    # ---------------------------------------------------------------- #
    #  Helpers                                                           #
    # ---------------------------------------------------------------- #

    def _fmt(self, color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def _write(self, cursor: QTextCursor, text: str,
               color: str, bold: bool = False):
        cursor.insertText(text, self._fmt(color, bold))

    def _write_move(self, cursor: QTextCursor, san: str, node: Node,
                    color: str, bold: bool = False):
        anchor = f"node_{id(node)}"
        fmt = self._fmt(color, bold)
        fmt.setAnchor(True)
        fmt.setAnchorHref(anchor)
        cursor.insertText(san, fmt)
        self._anchor_map[anchor] = node

    # ---------------------------------------------------------------- #
    #  Souris                                                            #
    # ---------------------------------------------------------------- #

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            anchor = self.anchorAt(event.pos())
            if anchor and anchor in self._anchor_map:
                self.node_clicked.emit(self._anchor_map[anchor])
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        anchor = self.anchorAt(event.pos())
        if anchor and anchor in self._anchor_map:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)
