"""
Widget d'affichage de l'arbre de coups avec variantes.
Affiche les coups inline, variantes entre parenthèses et indentées.
Les coups sont cliquables pour naviguer.
"""
import chess
from PyQt6.QtWidgets import QTextEdit, QApplication
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QFont,
    QMouseEvent, QTextDocument
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint

from core.game_tree import Node, GameTree


# Couleurs
COLOR_MAIN_MOVE     = "#dce0e8"   # coup ligne principale
COLOR_VARIATION     = "#89b4fa"   # coup variante (bleu)
COLOR_MOVE_NUMBER   = "#6c7086"   # numéro de coup (gris)
COLOR_CURRENT       = "#a6e3a1"   # coup actif (vert)
COLOR_BG            = "#1e1e2e"
COLOR_PAREN         = "#7f849c"   # parenthèses


class MoveTreeWidget(QTextEdit):
    """Affiche l'arbre de coups ; émet node_clicked quand on clique un coup."""

    node_clicked = pyqtSignal(object)   # Node

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"background: {COLOR_BG}; border-radius: 4px; padding: 4px;")
        self.setFont(QFont("Courier New", 11))
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        self._game: GameTree = None
        self._current_node: Node = None
        # Mapping position_dans_le_texte → Node
        self._anchor_map: dict[str, Node] = {}

    def set_game(self, game: GameTree):
        self._game = game

    def refresh(self, current_node: Node):
        """Reconstruit entièrement l'affichage."""
        self._current_node = current_node
        self._anchor_map.clear()
        self.clear()

        if self._game is None:
            return

        cursor = self.textCursor()
        self._render_node(cursor, self._game.root, depth=0, is_main=True)

        # Scroll vers le coup courant
        if current_node and not current_node.is_root:
            anchor = self._node_anchor(current_node)
            found = self.document().find(f'<a name="{anchor}">')
            # On scrolle via la sélection du bloc courant
            cursor2 = self.textCursor()
            self.ensureCursorVisible()

    # ---------------------------------------------------------------- #
    #  Rendu récursif                                                    #
    # ---------------------------------------------------------------- #

    def _render_node(self, cursor: QTextCursor, node: Node,
                     depth: int, is_main: bool):
        """Rend récursivement les enfants du nœud."""
        for i, child in enumerate(node.children):
            is_variation = (i > 0) or (not is_main)

            # Numéro de coup
            self._write(cursor, child.move_number(),
                        COLOR_MOVE_NUMBER, bold=False)
            self._write(cursor, " ", COLOR_MOVE_NUMBER)

            # Coup cliquable
            san = child.san()
            is_current = (child is self._current_node)
            color = COLOR_CURRENT if is_current else (
                COLOR_VARIATION if is_variation else COLOR_MAIN_MOVE
            )
            self._write_move(cursor, san, child, color, bold=is_current)
            self._write(cursor, " ", COLOR_MAIN_MOVE)

            # Variantes (enfants alternatifs dès le 2e)
            for alt in node.children[1:] if i == 0 else []:
                pass  # gérées par la récursion ci-dessous

            # Descendre dans les enfants du coup principal
            if i == 0:
                self._render_node(cursor, child, depth, is_main)

            # Variantes alternatives (i > 0) → entre parenthèses
            if i > 0:
                self._write(cursor, "(", COLOR_PAREN, bold=False)
                self._render_node(cursor, child, depth + 1, is_main=False)
                self._write(cursor, ") ", COLOR_PAREN, bold=False)

    def _render_node(self, cursor: QTextCursor, node: Node,
                     depth: int, is_main: bool):
        """Version correcte : parcourt tous les enfants."""
        if not node.children:
            return

        main_child = node.children[0]
        alt_children = node.children[1:]

        # --- Coup principal ---
        num = self._move_number_str(main_child, force=False)
        if num:
            self._write(cursor, num + " ", COLOR_MOVE_NUMBER)
        is_cur = (main_child is self._current_node)
        color = COLOR_CURRENT if is_cur else (
            COLOR_VARIATION if not is_main else COLOR_MAIN_MOVE
        )
        self._write_move(cursor, main_child.san(), main_child, color, bold=is_cur)
        self._write(cursor, " ", COLOR_MAIN_MOVE)

        # --- Variantes alternatives (entre parenthèses) ---
        for alt in alt_children:
            self._write(cursor, "(", COLOR_PAREN)
            # Toujours afficher le numéro en début de variante
            num_alt = self._move_number_str(alt, force=True)
            if num_alt:
                self._write(cursor, num_alt + " ", COLOR_MOVE_NUMBER)
            is_cur2 = (alt is self._current_node)
            self._write_move(cursor, alt.san(), alt, COLOR_VARIATION, bold=is_cur2)
            self._write(cursor, " ", COLOR_MAIN_MOVE)
            self._render_node(cursor, alt, depth + 1, is_main=False)
            self._write(cursor, ") ", COLOR_PAREN)

        # --- Suite de la ligne principale ---
        self._render_node(cursor, main_child, depth, is_main)

    # ---------------------------------------------------------------- #
    #  Helpers d'écriture                                               #
    # ---------------------------------------------------------------- #

    def _move_number_str(self, node: Node, force: bool) -> str:
        """
        Retourne le numéro à afficher devant un coup.
        - Coup blanc        → toujours '1.'
        - Coup noir normal  → '' (pas de numéro, le blanc précédent suffit)
        - Coup noir forcé   → '1...' (début de variante, après parenthèse)
        """
        if node.parent is None:
            return ""
        is_white_move = node.parent.board.turn == chess.WHITE
        full = node.board.fullmove_number
        if is_white_move:
            return f"{full}."
        elif force:
            return f"{full}..."
        return ""

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
        """Écrit un coup cliquable en stockant sa position dans _anchor_map."""
        anchor = self._node_anchor(node)
        pos = cursor.position()
        fmt = self._fmt(color, bold)
        fmt.setAnchor(True)
        fmt.setAnchorHref(anchor)
        # Soulignement léger au survol via stylesheet n'est pas dispo ici
        cursor.insertText(san, fmt)
        self._anchor_map[anchor] = node

    @staticmethod
    def _node_anchor(node: Node) -> str:
        return f"node_{id(node)}"

    # ---------------------------------------------------------------- #
    #  Clic souris                                                       #
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