"""
Fenêtre principale — utilise GameTree pour les variantes.
"""
import chess
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QTextEdit,
    QStatusBar, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from core.game_tree import GameTree, Node
from core.engine import StockfishController
from ui.board_widget import BoardWidget
from ui.move_tree_widget import MoveTreeWidget
from ui.variants_panel import VariantsPanel

ANALYSIS_PANEL_WIDTH = 260
VARIANTS_PANEL_WIDTH  = 240
VARIANTS_PANEL_WIDTH  = 240


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessOP")
        self.resize(1200, 800)

        self.game   = GameTree(self)
        self.engine = StockfishController(self)

        self._build_ui()
        self._connect_signals()

        self.engine.load(r"E:\ChessOP\stockfish\stockfish.exe")
        self.game.new_game()
        # Focus sur l'échiquier pour que les flèches fonctionnent
        self.board_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.board_widget.setFocus()

    # ---------------------------------------------------------------- #
    #  UI                                                                #
    # ---------------------------------------------------------------- #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.root_layout = QHBoxLayout(central)
        self.root_layout.setSpacing(12)
        self.root_layout.setContentsMargins(12, 12, 12, 12)

        # Panneau variantes (gauche, masqué par défaut)
        import os
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # ---- Panneau variantes (gauche, masqué par défaut) ----
        import os
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._variants_folder = os.path.join(_base, "variantes")
        self.variants_panel = VariantsPanel(self._variants_folder)
        self.variants_panel.setFixedWidth(0)
        self.variants_panel.setVisible(False)
        self.root_layout.addWidget(self.variants_panel)

        self.board_widget = BoardWidget()
        self.board_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.root_layout.addWidget(self.board_widget, stretch=1)
        controls = QWidget()
        controls.setFixedWidth(280)
        controls_layout = self._build_controls_panel()
        controls.setLayout(controls_layout)
        self.root_layout.addWidget(controls)

        self.analysis_panel = self._build_analysis_panel()
        self.analysis_panel.setFixedWidth(0)
        self.analysis_panel.setVisible(False)
        self.root_layout.addWidget(self.analysis_panel)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Prêt")

    def _build_controls_panel(self) -> QVBoxLayout:
        side = QVBoxLayout()
        side.setSpacing(10)

        self.lbl_turn = QLabel("Tour : Blancs")
        self.lbl_turn.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        side.addWidget(self.lbl_turn)

        self.lbl_eval = QLabel("Évaluation : —")
        self.lbl_eval.setFont(QFont("Arial", 11))
        side.addWidget(self.lbl_eval)

        self.lbl_hint = QLabel("Conseil : —")
        self.lbl_hint.setFont(QFont("Arial", 11))
        self.lbl_hint.setStyleSheet("color: #2a7a2a; font-weight: bold;")
        side.addWidget(self.lbl_hint)

        # Contrôles
        grp = QGroupBox("Contrôles")
        ctrl = QVBoxLayout(grp)
        self.btn_new   = QPushButton("Nouvelle partie")
        self.btn_back  = QPushButton("◀  Reculer")
        self.btn_fwd   = QPushButton("Avancer  ▶")
        self.btn_flip  = QPushButton("Retourner l'échiquier")
        self.btn_hint  = QPushButton("Conseil automatique : OFF")
        self.btn_hint.setCheckable(True)
        self.btn_hint.setStyleSheet(
            "QPushButton:checked { background-color: #2a7a2a; color: white; font-weight: bold; }"
        )
        self.btn_load_var = QPushButton("Charger variante")
        self.btn_load_var.setCheckable(True)
        self.btn_load_var.setStyleSheet(
            "QPushButton:checked { background-color: #313244; color: #89b4fa; font-weight: bold; }"
        )
        self.btn_del_var = QPushButton("Supprimer cette variante")
        self.btn_del_var.setStyleSheet("color: #c0392b;")
        for btn in (self.btn_new, self.btn_back, self.btn_fwd,
                    self.btn_flip, self.btn_hint, self.btn_del_var,
                    self.btn_load_var):
            btn.setMinimumHeight(32)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            ctrl.addWidget(btn)
        side.addWidget(grp)

        # Moteur
        grp_eng = QGroupBox("Moteur Stockfish")
        eng = QVBoxLayout(grp_eng)
        self.lbl_depth = QLabel("Profondeur : 15")
        self.slider_depth = QSlider(Qt.Orientation.Horizontal)
        self.slider_depth.setRange(1, 30)
        self.slider_depth.setValue(15)
        self.btn_engine_move = QPushButton("Jouer le meilleur coup")
        self.btn_engine_move.setMinimumHeight(34)
        self.lbl_engine_status = QLabel("Moteur : chargement…")
        self.lbl_engine_status.setStyleSheet("color: #888;")
        self.btn_engine_move.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for w in (self.lbl_depth, self.slider_depth,
                  self.btn_engine_move, self.lbl_engine_status):
            eng.addWidget(w)
        side.addWidget(grp_eng)

        # Arbre de coups
        grp_hist = QGroupBox("Coups et variantes")
        hist = QVBoxLayout(grp_hist)

        self.move_tree = MoveTreeWidget()
        self.move_tree.setMinimumHeight(250)
        self.move_tree.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hist.addWidget(self.move_tree)

        self.txt_variant_name = QLineEdit()
        self.txt_variant_name.setPlaceholderText("Nom de la variante…")
        self.txt_variant_name.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        hist.addWidget(self.txt_variant_name)
        btn_export = QPushButton("SAV variante")
        btn_export.clicked.connect(self._export_pgn)
        hist.addWidget(btn_export)
        side.addWidget(grp_hist)

        side.addStretch()
        return side

    def _build_analysis_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Meilleurs coups")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.analysis_table = QTableWidget(5, 3)
        self.analysis_table.setHorizontalHeaderLabels(["#", "Coup", "Éval"])
        self.analysis_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.analysis_table.verticalHeader().setVisible(False)
        self.analysis_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.analysis_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.analysis_table.setStyleSheet("""
            QTableWidget { background:#181825; color:#cdd6f4;
                           gridline-color:#313244; border:none; font-size:13px; }
            QHeaderView::section { background:#313244; color:#cdd6f4;
                                   font-weight:bold; border:none; padding:4px; }
            QTableWidget::item { padding:4px; }
        """)
        layout.addWidget(self.analysis_table)

        self.lbl_thinking = QLabel("En attente…")
        self.lbl_thinking.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thinking.setStyleSheet("color:#6c7086; font-style:italic;")
        layout.addWidget(self.lbl_thinking)
        layout.addStretch()
        return frame

    # ---------------------------------------------------------------- #
    #  Signaux                                                           #
    # ---------------------------------------------------------------- #

    def _connect_signals(self):
        self.board_widget.move_requested.connect(self._on_human_move)

        self.game.board_changed.connect(self.board_widget.update_board)
        self.game.board_changed.connect(self._on_board_changed)
        self.game.move_made.connect(self.board_widget.set_last_move)
        self.game.turn_changed.connect(self._on_turn_changed)
        self.game.game_over.connect(self._on_game_over)
        self.game.tree_changed.connect(self._refresh_tree)
        self.game.node_selected.connect(self._on_node_selected)

        self.engine.best_move_ready.connect(self._on_engine_move)
        self.engine.multipv_ready.connect(self._on_multipv)
        self.engine.engine_error.connect(self._on_engine_error)
        self.engine.engine_ready.connect(self._on_engine_ready)

        self.btn_new.clicked.connect(self._new_game)
        self.btn_back.clicked.connect(lambda: self.game.go_back())
        self.btn_fwd.clicked.connect(lambda: self.game.go_forward())
        self.btn_flip.clicked.connect(self.board_widget.flip_board)
        self.btn_hint.toggled.connect(self._toggle_hint)
        self.btn_engine_move.clicked.connect(self._engine_play)
        self.btn_load_var.toggled.connect(self._toggle_variants_panel)
        self.btn_del_var.clicked.connect(self._delete_variation)
        self.variants_panel.variant_load_requested.connect(self._load_variant)
        self.slider_depth.valueChanged.connect(
            lambda v: self.lbl_depth.setText(f"Profondeur : {v}"))

        self.move_tree.set_game(self.game)
        self.move_tree.node_clicked.connect(self.game.go_to_node)

    # ---------------------------------------------------------------- #
    #  Slots                                                             #
    # ---------------------------------------------------------------- #

    def _on_human_move(self, move: chess.Move):
        self.game.make_move(move)

    def _on_board_changed(self, board: chess.Board):
        self._refresh_tree()
        self._auto_hint()

    def _on_turn_changed(self, whites_turn: bool):
        self.lbl_turn.setText("Tour : Blancs" if whites_turn else "Tour : Noirs")

    def _on_game_over(self, message: str):
        self.lbl_turn.setText("Partie terminée")
        self.status_bar.showMessage(message)
        QMessageBox.information(self, "Fin de partie", message)

    def _on_node_selected(self, node: Node):
        self._refresh_tree()
        # Mettre à jour le dernier coup affiché
        self.board_widget.set_last_move(node.move)
        turn_text = "Blancs" if node.board.turn == chess.WHITE else "Noirs"
        self.lbl_turn.setText(f"Tour : {turn_text}")

    def _refresh_tree(self):
        self.move_tree.refresh(self.game.current_node)

    _engine_is_playing: bool = False

    def _on_engine_move(self, move: chess.Move, score: float):
        if abs(score) >= 29000:
            eval_text = f"Évaluation : Mat {'+' if score > 0 else '-'}"
        else:
            p = score / 100.0
            eval_text = f"Évaluation : {'+' if p >= 0 else ''}{p:.2f}"
        self.lbl_eval.setText(eval_text)

        if self._engine_is_playing:
            self._engine_is_playing = False
            self.lbl_hint.setText("Conseil : —")
            self.game.make_move(move)
        else:
            try:
                san = self.game.board.san(move)
            except Exception:
                san = move.uci()
            self.lbl_hint.setText(f"Conseil : {san}")
            self.status_bar.showMessage(f"Conseil : {san}  ({eval_text})")

    def _on_multipv(self, moves: list):
        self.lbl_thinking.setText("Analyse terminée")
        board = self.game.board
        for i in range(5):
            if i < len(moves):
                info = moves[i]
                try:
                    san = board.san(info.move)
                except Exception:
                    san = info.move.uci()
                items = [QTableWidgetItem(str(i+1)),
                         QTableWidgetItem(san),
                         QTableWidgetItem(info.score_text())]
                score_color = (QColor("#a6e3a1") if info.score_cp > 50
                               else QColor("#f38ba8") if info.score_cp < -50
                               else QColor("#cdd6f4"))
                for col, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if col == 2:
                        item.setForeground(score_color)
                    if i == 0:
                        item.setFont(QFont("Arial", 13, QFont.Weight.Bold))
                    self.analysis_table.setItem(i, col, item)
            else:
                for col in range(3):
                    self.analysis_table.setItem(i, col, QTableWidgetItem("—"))

    def _on_engine_error(self, msg: str):
        self.status_bar.showMessage(f"Erreur moteur : {msg}")
        self.lbl_engine_status.setText("Moteur : erreur")
        self.lbl_engine_status.setStyleSheet("color: red;")

    def _on_engine_ready(self, available: bool):
        if available:
            self.lbl_engine_status.setText("Moteur : prêt ✓")
            self.lbl_engine_status.setStyleSheet("color: green;")
        else:
            self.lbl_engine_status.setText("Moteur : non disponible")
            self.lbl_engine_status.setStyleSheet("color: orange;")

    # ---------------------------------------------------------------- #
    #  Conseil                                                           #
    # ---------------------------------------------------------------- #

    def _toggle_hint(self, checked: bool):
        if checked:
            self.btn_hint.setText("Conseil automatique : ON")
            self._show_analysis_panel(True)
            self._do_hint()
        else:
            self.btn_hint.setText("Conseil automatique : OFF")
            self._show_analysis_panel(False)
            self.lbl_hint.setText("Conseil : —")
            self.status_bar.showMessage("Conseil désactivé")

    def _show_analysis_panel(self, show: bool):
        if show:
            self.analysis_panel.setVisible(True)
            self.analysis_panel.setFixedWidth(ANALYSIS_PANEL_WIDTH)
            self.resize(self.width() + ANALYSIS_PANEL_WIDTH + 12, self.height())
        else:
            self.resize(self.width() - ANALYSIS_PANEL_WIDTH - 12, self.height())
            self.analysis_panel.setFixedWidth(0)
            self.analysis_panel.setVisible(False)

    def _auto_hint(self):
        if self.btn_hint.isChecked() and not self._engine_is_playing:
            self._do_hint()

    def _do_hint(self):
        if self.game.is_game_over:
            return
        self._engine_is_playing = False
        depth = self.slider_depth.value()
        self.engine.request_move(self.game.board, depth=depth, time_limit=1.0)
        self.engine.request_multipv(self.game.board, depth=depth, num_lines=5)
        self.lbl_thinking.setText("Stockfish réfléchit…")
        self.status_bar.showMessage("Stockfish réfléchit…")

    # ---------------------------------------------------------------- #
    #  Boutons                                                           #
    # ---------------------------------------------------------------- #

    def _toggle_variants_panel(self, checked: bool):
        if checked:
            self.btn_load_var.setText("✕ Fermer variantes")
            self.variants_panel.refresh()
            self.variants_panel.setVisible(True)
            self.variants_panel.setFixedWidth(VARIANTS_PANEL_WIDTH)
            self.resize(self.width() + VARIANTS_PANEL_WIDTH + 12, self.height())
        else:
            self.btn_load_var.setText("Charger variante")
            self.resize(self.width() - VARIANTS_PANEL_WIDTH - 12, self.height())
            self.variants_panel.setFixedWidth(0)
            self.variants_panel.setVisible(False)

    def _load_variant(self, path: str):
        ok = self.game.load_pgn(path)
        if ok:
            self.lbl_eval.setText("Évaluation : —")
            self.lbl_hint.setText("Conseil : —")
            self._clear_table()
            import os
            self.status_bar.showMessage(f"Variante chargée : {os.path.basename(path)}")
            # Fermer le panneau après chargement
            self.btn_load_var.setChecked(False)
        else:
            self.status_bar.showMessage("Erreur lors du chargement de la variante.")

    def _new_game(self):
        self.game.new_game()
        self.lbl_eval.setText("Évaluation : —")
        self.lbl_hint.setText("Conseil : —")
        self._clear_table()
        self.status_bar.showMessage("Nouvelle partie")

    def _delete_variation(self):
        node = self.game.current_node
        if node.is_root:
            return
        if node.parent and node in node.parent.children[1:]:
            reply = QMessageBox.question(
                self, "Supprimer la variante",
                "Supprimer ce coup et toute sa suite ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.game.delete_current_variation()
        else:
            self.status_bar.showMessage("Sélectionnez un coup de variante à supprimer.")

    def _engine_play(self):
        if self.game.is_game_over:
            return
        self._engine_is_playing = True
        self.engine.request_move(self.game.board,
                                  depth=self.slider_depth.value(), time_limit=2.0)
        self.status_bar.showMessage("Stockfish joue…")

    def _export_pgn(self):
        import os, datetime, re
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = os.path.join(base, "variantes")
        os.makedirs(folder, exist_ok=True)

        # Nom saisi ou horodatage par défaut
        raw = self.txt_variant_name.text().strip()
        if raw:
            # Nettoyer les caractères interdits dans un nom de fichier
            safe = re.sub(r'[\/:*?"<>|]', "_", raw)
        else:
            safe = "variante_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        path = os.path.join(folder, f"{safe}.pgn")

        with open(path, "w", encoding="utf-8") as f:
            f.write(self.game.to_pgn())
        self.txt_variant_name.clear()
        self.status_bar.showMessage(f"Variante sauvegardée : {path}")
        if self.variants_panel.isVisible():
            self.variants_panel.refresh()

    def _clear_table(self):
        for i in range(5):
            for col in range(3):
                self.analysis_table.setItem(i, col, QTableWidgetItem("—"))

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.game.go_back()
        elif key == Qt.Key.Key_Right:
            self.game.go_forward()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.engine.unload()
        super().closeEvent(event)
