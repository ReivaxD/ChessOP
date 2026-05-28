"""
Fenêtre principale — utilise GameTree pour les variantes.
"""
import chess
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QTextEdit,
    QStatusBar, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.game_tree import GameTree, Node
from core.engine import StockfishController
from ui.board_widget import BoardWidget
from ui.move_tree_widget import MoveTreeWidget
from ui.variants_panel import VariantsPanel

ANALYSIS_PANEL_WIDTH = 380
VARIANTS_PANEL_WIDTH  = 240
VARIANTS_PANEL_WIDTH  = 240


class AnalysisWindow(QMainWindow):

    home_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessOP")
        self.resize(1200, 800)

        self.game   = GameTree(self)
        self.engine = StockfishController(self)
        self._pending_move: chess.Move = None   # coup en attente d'éval
        self._best_move_before: chess.Move = None  # meilleur coup avant le coup joué
        self._eval_in_progress: bool = False       # bloque _auto_hint pendant l'éval
        self._best_moves_cache: dict = {}           # {fen: meilleur_coup} pour is_best variante
        self._eval_stage: int = 0               # 0=inactif 1=avant 2=après
        self._eval_queue: list = []             # file d'attente pour éval variante chargée

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
        self._variants_folder = os.path.join(_base, "ressources", "echec", "analyses")
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

        # Bouton retour accueil
        self.btn_home = QPushButton("⌂  Accueil")
        self.btn_home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_home.setStyleSheet(
            "color: #89b4fa; background: #313244; border-radius: 4px; font-weight: bold;"
        )
        self.btn_home.setMinimumHeight(34)
        self.btn_home.clicked.connect(self._go_home)
        side.addWidget(self.btn_home)

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

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        layout.addWidget(sep)

        # Titre ligne principale
        title2 = QLabel("Ligne principale")
        title2.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title2.setStyleSheet("color: #cdd6f4;")
        title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title2)

        # Tableau ligne principale
        self.mainline_table = QTableWidget(0, 5)
        self.mainline_table.setHorizontalHeaderLabels(["#", "Blancs", "★", "Noirs", "★"])
        hh = self.mainline_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.mainline_table.setColumnWidth(0, 28)
        self.mainline_table.setColumnWidth(2, 30)
        self.mainline_table.setColumnWidth(4, 30)
        self.mainline_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.mainline_table.verticalHeader().setVisible(False)
        self.mainline_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mainline_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.mainline_table.setStyleSheet("""
            QTableWidget { background:#181825; color:#cdd6f4;
                           gridline-color:#313244; border:none; font-size:12px; }
            QHeaderView::section { background:#313244; color:#cdd6f4;
                                   font-weight:bold; border:none; padding:4px; }
            QTableWidget::item { padding:4px; }
        """)
        layout.addWidget(self.mainline_table, stretch=1)
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
        self.engine.eval_ready.connect(self._on_eval_ready)
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
        self.variants_panel.save_requested.connect(self._export_pgn_to_folder)
        self.slider_depth.valueChanged.connect(
            lambda v: self.lbl_depth.setText(f"Profondeur : {v}"))

        self.move_tree.set_game(self.game)
        self.move_tree.node_clicked.connect(self.game.go_to_node)

    # ---------------------------------------------------------------- #
    #  Slots                                                             #
    # ---------------------------------------------------------------- #

    def _on_human_move(self, move: chess.Move):
        self.board_widget.set_hint_move(None)
        self._pending_move = move
        node = self.game.current_node
        if node.eval_cp is not None:
            # Eval déjà connue → jouer directement et évaluer après
            self._eval_stage = 2
            self._eval_before_val = node.eval_cp
            self.game.make_move(move)
            self.engine.request_eval(self.game.board, depth=14)
        else:
            # Eval inconnue → évaluer d'abord la position courante
            self._eval_stage = 1
            self._eval_before_val = 0.0
            self.engine.request_eval(node.board, depth=14)

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
        self._refresh_mainline()

    def _refresh_mainline(self):
        """Affiche la ligne principale dans le tableau 2 coups par ligne."""
        if not hasattr(self, "mainline_table"):
            return
        # Reconstruire la ligne principale depuis la racine
        from core.game_tree import Node
        moves_san = []
        board = chess.Board()
        node = self.game.root
        while node.children:
            node = node.children[0]
            try:
                san = board.san(node.move)
                board.push(node.move)
                moves_san.append(san)
            except Exception:
                break

        # Remplir le tableau par paires
        pairs = []
        for i in range(0, len(moves_san), 2):
            white = moves_san[i]
            black = moves_san[i + 1] if i + 1 < len(moves_san) else ""
            pairs.append((i // 2 + 1, white, black))

        # Collecter les nœuds de la ligne principale pour les qualités
        main_nodes = []
        nd = self.game.root
        while nd.children:
            nd = nd.children[0]
            main_nodes.append(nd)

        current_ply = len([n for n in self.game.current_node.path_from_root() if n.move])
        self.mainline_table.setRowCount(len(pairs))

        for row, (num, white, black) in enumerate(pairs):
            wp = row * 2 + 1   # ply blanc
            bp = row * 2 + 2   # ply noir
            wn = main_nodes[wp - 1] if wp - 1 < len(main_nodes) else None
            bn = main_nodes[bp - 1] if bp - 1 < len(main_nodes) else None

            # Col 0 : numéro
            i0 = QTableWidgetItem(str(num))
            i0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.mainline_table.setItem(row, 0, i0)

            # Col 1 : coup blanc
            i1 = QTableWidgetItem(white)
            i1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if wp == current_ply:
                i1.setForeground(QColor("#a6e3a1"))
                i1.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.mainline_table.setItem(row, 1, i1)

            # Col 2 : icône blanc
            from core.game_tree import Node as _N
            q_w = wn.quality if wn else ""
            i2 = QTableWidgetItem(q_w)
            i2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if q_w:
                i2.setForeground(QColor(_N.quality_color(q_w)))
                i2.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.mainline_table.setItem(row, 2, i2)

            # Col 3 : coup noir
            i3 = QTableWidgetItem(black)
            i3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if bp == current_ply:
                i3.setForeground(QColor("#a6e3a1"))
                i3.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.mainline_table.setItem(row, 3, i3)

            # Col 4 : icône noir
            q_b = bn.quality if bn else ""
            i4 = QTableWidgetItem(q_b)
            i4.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if q_b:
                i4.setForeground(QColor(_N.quality_color(q_b)))
                i4.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.mainline_table.setItem(row, 4, i4)

        if current_ply > 0:
            self.mainline_table.scrollToItem(
                self.mainline_table.item(max(0, (current_ply - 1) // 2), 0)
            )

    _engine_is_playing: bool = False

    def _on_eval_ready(self, fen: str, score_cp: float):
        """Reçoit une évaluation Stockfish — gère le pipeline en 2 étapes."""
        from core.game_tree import Node

        # Mode éval variante chargée — traitement séquentiel
        if self._eval_stage == 10:
            if self._eval_queue:
                node, _ = self._eval_queue.pop(0)
                node.eval_cp = score_cp
                parent = node.parent
                if parent and parent.eval_cp is not None:
                    if parent.board.turn == chess.WHITE:
                        delta = parent.eval_cp - score_cp
                    else:
                        delta = score_cp - parent.eval_cp
                    # is_best : vérifier si le coup joué était le meilleur
                    parent_fen = parent.board.fen() if parent else None
                    best = self._best_moves_cache.get(parent_fen)
                    is_best = (best is not None and best == node.move)
                    node.quality = Node.classify_move(delta, is_best)
            self._process_eval_queue()
            return

        if self._eval_stage == 1:
            # Étape 1 : on vient d'évaluer AVANT le coup → jouer maintenant
            self._eval_before_val = score_cp
            self.game.current_node.eval_cp = score_cp
            self._eval_stage = 2
            self.game.make_move(self._pending_move)
            self.engine.request_eval(self.game.board, depth=14)

        elif self._eval_stage == 2:
            # Étape 2 : on vient d'évaluer APRÈS le coup → calculer qualité
            self._eval_stage = 0
            node = self.game.current_node
            if node.is_root:
                return
            node.eval_cp = score_cp

            # Delta du point de vue du joueur qui vient de jouer
            if node.parent and node.parent.board.turn == chess.WHITE:
                delta = self._eval_before_val - score_cp
            else:
                delta = score_cp - self._eval_before_val

            is_best = (self._best_move_before == node.move)
            node.quality = Node.classify_move(delta, is_best)
            self._eval_in_progress = False
            self._refresh_mainline()

        else:
            # Éval de conseil ou autre — mettre à jour le nœud courant
            node = self.game.current_node
            if not node.is_root:
                node.eval_cp = score_cp

    def _on_engine_move(self, move: chess.Move, score: float):
        self._last_best_move = move   # mémoriser le meilleur coup Stockfish
        # Stocker dans le cache pour is_best lors du chargement variante
        if hasattr(self, '_best_moves_cache') and self._eval_stage != 3:
            # Associer ce meilleur coup aux FEN en attente dans le cache
            for fen, val in self._best_moves_cache.items():
                if val is None:
                    self._best_moves_cache[fen] = move
                    break

        # Stage 3 : on a le meilleur coup, maintenant lancer l'éval
        if self._eval_stage == 3:
            self._best_move_before = move
            node = self.game.current_node
            if self._eval_before_val is not None:
                # Eval connue → jouer et évaluer après
                self._eval_stage = 2
                self.game.make_move(self._pending_move)
                self.engine.request_eval(self.game.board, depth=14)
            else:
                # Eval inconnue → évaluer avant puis jouer
                self._eval_stage = 1
                self._eval_before_val = 0.0
                self.engine.request_eval(node.board, depth=14)
            return
        if abs(score) >= 29000:
            eval_text = f"Évaluation : Mat {'+' if score > 0 else '-'}"
        else:
            p = score / 100.0
            eval_text = f"Évaluation : {'+' if p >= 0 else ''}{p:.2f}"
        self.lbl_eval.setText(eval_text)

        if self._engine_is_playing:
            self._engine_is_playing = False
            self.lbl_hint.setText("Conseil : —")
            self.board_widget.set_hint_move(None)
            self.game.make_move(move)
        else:
            try:
                san = self.game.board.san(move)
            except Exception:
                san = move.uci()
            self.lbl_hint.setText(f"Conseil : {san}")
            self.status_bar.showMessage(f"Conseil : {san}  ({eval_text})")
            self.board_widget.set_hint_move(move)

    def _on_multipv(self, moves: list):
        self.lbl_thinking.setText("Analyse terminée")
        # Stocker le meilleur coup par FEN pour is_best lors du chargement variante
        if moves:
            # On ne peut pas retrouver le FEN ici, on utilise une queue séparée
            pass
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
            self.board_widget.set_hint_move(None)
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
        if self.btn_hint.isChecked() and not self._engine_is_playing and not self._eval_in_progress:
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
            self.btn_load_var.setChecked(False)
            # Lancer l'éval en chaîne de tous les nœuds de la ligne principale
            self._start_variant_eval()
        else:
            self.status_bar.showMessage("Erreur lors du chargement de la variante.")

    def _start_variant_eval(self):
        """Construit la file d'éval — racine + tous les nœuds de la ligne principale."""
        self._eval_queue = []
        self._best_moves_cache = {}
        root = self.game.root
        self._eval_queue.append((root, None))
        node = root
        while node.children:
            node = node.children[0]
            self._eval_queue.append((node, None))
        # Demander le meilleur coup pour chaque position PARENT
        # (pour savoir si le coup joué était le meilleur)
        nd = root
        while nd.children:
            # Stocker le meilleur coup pour chaque position
            fen = nd.board.fen()
            self._best_moves_cache[fen] = None  # sera rempli par _on_engine_move
            self.engine.request_move(nd.board, depth=12, time_limit=0.3)
            nd = nd.children[0]
        self._process_eval_queue()

    def _process_eval_queue(self):
        """Évalue le prochain nœud de la file."""
        if not self._eval_queue:
            self._eval_stage = 0   # IMPORTANT : libérer le stage pour les coups humains
            self._refresh_mainline()
            self.status_bar.showMessage("Analyse terminée")
            return
        node, _ = self._eval_queue[0]
        self._eval_stage = 10
        self.engine.request_eval(node.board, depth=12)

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

    def _export_pgn_to_folder(self, folder: str, name: str):
        import os, re as _re
        safe = _re.sub(r'[\/:*?"<>|]', "_", name.strip())
        if not safe:
            import datetime
            safe = "variante_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{safe}.pgn")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.game.to_pgn())
        self.status_bar.showMessage(f"Variante sauvegardee : {os.path.basename(path)}")
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

    def _go_home(self):
        self.hide()
        self.home_requested.emit()

    def closeEvent(self, event):
        self.engine.unload()
        super().closeEvent(event)

    def hideEvent(self, event):
        """Appelé aussi quand on revient à l'accueil — rien à faire."""
        super().hideEvent(event)
