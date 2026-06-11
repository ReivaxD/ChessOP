"""
Mode Entraînement — ChessOP
Charge des variantes PGN, choisit une position aléatoire,
et demande au joueur de deviner le prochain coup.
"""
import os
import random
import chess
import chess.pgn
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QFrame, QSizePolicy, QStatusBar, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from ui.board_widget import BoardWidget


# ------------------------------------------------------------------ #
#  Données d'une session d'entraînement                               #
# ------------------------------------------------------------------ #

class TrainingSession:
    """Représente une séquence de positions à deviner."""

    def __init__(self, nodes: list):
        """nodes : liste de (board_before, correct_move, board_after)"""
        self.exercises = nodes
        self.index     = 0
        self.score     = 0
        self.total     = len(nodes)

    @property
    def current(self):
        if self.index < self.total:
            return self.exercises[self.index]
        return None

    @property
    def finished(self):
        return self.index >= self.total

    def advance(self):
        self.index += 1


# ------------------------------------------------------------------ #
#  Fenêtre principale                                                  #
# ------------------------------------------------------------------ #

class TrainingWindow(QMainWindow):

    from PyQt6.QtCore import pyqtSignal
    home_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessOP — Entraînement")
        self.resize(1200, 800)

        self._session: TrainingSession = None
        self._waiting_for_move = False
        self._training_folder = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "ressources", "echec", "entrainement"
        )
        os.makedirs(self._training_folder, exist_ok=True)

        self._build_ui()
        self._refresh_file_list()

    # ---------------------------------------------------------------- #
    #  UI                                                                #
    # ---------------------------------------------------------------- #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)

        # Panneau gauche — fichiers
        root.addWidget(self._build_file_panel())

        # Échiquier
        self.board = BoardWidget()
        self.board.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.board.move_requested.connect(self._on_move)
        root.addWidget(self.board, stretch=2)

        # Panneau droit — score et contrôles
        root.addLayout(self._build_score_panel())

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sélectionnez un fichier et lancez l'entraînement")

    def _build_file_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(220)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Fichiers d'entraînement")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Chemin courant
        self._current_folder = self._training_folder
        self.lbl_path = QLabel("/")
        self.lbl_path.setStyleSheet("color: #89b4fa; font-size: 10px;")
        self.lbl_path.setWordWrap(True)
        layout.addWidget(self.lbl_path)

        # Bouton dossier parent
        self.btn_up = QPushButton("⬆  Dossier parent")
        self.btn_up.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_up.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        self.btn_up.setMinimumHeight(26)
        self.btn_up.clicked.connect(self._go_up)
        layout.addWidget(self.btn_up)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget { background: #181825; color: #cdd6f4;
                          border: none; border-radius: 4px; font-size: 12px; }
            QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #313244; }
            QListWidget::item:selected { background: #313244; color: #89b4fa; }
            QListWidget::item:hover { background: #252535; }
        """)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.file_list)

        btn_refresh = QPushButton("↻ Rafraîchir")
        btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_refresh.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        btn_refresh.setMinimumHeight(26)
        btn_refresh.clicked.connect(self._refresh_file_list)
        layout.addWidget(btn_refresh)

        self.btn_start = QPushButton("▶  Lancer")
        self.btn_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_start.setStyleSheet(
            "color: white; background: #2a7a2a; border-radius: 4px; font-weight: bold;"
        )
        self.btn_start.setMinimumHeight(34)
        self.btn_start.clicked.connect(self._start_training)
        layout.addWidget(self.btn_start)

        return frame

    def _build_score_panel(self) -> QVBoxLayout:
        side = QVBoxLayout()
        side.setSpacing(10)

        # Bouton accueil
        self.btn_home = QPushButton("⌂  Accueil")
        self.btn_home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_home.setStyleSheet(
            "color: #89b4fa; background: #313244; border-radius: 4px; font-weight: bold;"
        )
        self.btn_home.setMinimumHeight(34)
        self.btn_home.clicked.connect(self._go_home)
        side.addWidget(self.btn_home)

        # Score
        grp_score = QFrame()
        grp_score.setFrameShape(QFrame.Shape.StyledPanel)
        grp_score.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        score_layout = QVBoxLayout(grp_score)

        lbl_score_title = QLabel("Score")
        lbl_score_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        lbl_score_title.setStyleSheet("color: #cdd6f4;")
        lbl_score_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(lbl_score_title)

        self.lbl_score = QLabel("0 / 0")
        self.lbl_score.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.lbl_score.setStyleSheet("color: #a6e3a1;")
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.lbl_score)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: #313244; border-radius: 4px; height: 12px; text-align: center; }
            QProgressBar::chunk { background: #a6e3a1; border-radius: 4px; }
        """)
        score_layout.addWidget(self.progress_bar)
        side.addWidget(grp_score)

        # Feedback
        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setMinimumHeight(60)
        side.addWidget(self.lbl_feedback)

        # Infos position
        grp_info = QFrame()
        grp_info.setFrameShape(QFrame.Shape.StyledPanel)
        grp_info.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        info_layout = QVBoxLayout(grp_info)

        self.lbl_file = QLabel("Fichier : —")
        self.lbl_file.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.lbl_file.setWordWrap(True)
        info_layout.addWidget(self.lbl_file)

        self.lbl_position = QLabel("Position : —")
        self.lbl_position.setStyleSheet("color: #6c7086; font-size: 11px;")
        info_layout.addWidget(self.lbl_position)

        self.lbl_turn = QLabel("")
        self.lbl_turn.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: bold;")
        info_layout.addWidget(self.lbl_turn)
        side.addWidget(grp_info)

        # Bouton passer
        self.btn_skip = QPushButton("Passer →")
        self.btn_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_skip.setStyleSheet(
            "color: #f38ba8; background: #313244; border-radius: 4px;"
        )
        self.btn_skip.setMinimumHeight(32)
        self.btn_skip.clicked.connect(self._skip_exercise)
        self.btn_skip.setEnabled(False)
        side.addWidget(self.btn_skip)

        side.addStretch()
        return side

    # ---------------------------------------------------------------- #
    #  Fichiers                                                          #
    # ---------------------------------------------------------------- #

    def _refresh_file_list(self):
        self.file_list.clear()
        if not os.path.isdir(self._current_folder):
            return

        rel = os.path.relpath(self._current_folder, self._training_folder)
        self.lbl_path.setText("/" if rel == "." else f"/{rel.replace(os.sep, '/')}")
        self.btn_up.setEnabled(self._current_folder != self._training_folder)

        entries = os.listdir(self._current_folder)
        folders = sorted([e for e in entries
                          if os.path.isdir(os.path.join(self._current_folder, e))])
        files   = sorted([e for e in entries if e.endswith(".pgn")])

        for folder in folders:
            item = QListWidgetItem(f"📁  {folder}")
            item.setData(Qt.ItemDataRole.UserRole,
                         ("folder", os.path.join(self._current_folder, folder)))
            item.setForeground(QColor("#f9e2af"))
            self.file_list.addItem(item)

        for f in files:
            item = QListWidgetItem(f"♟  {f[:-4]}")
            item.setData(Qt.ItemDataRole.UserRole,
                         ("pgn", os.path.join(self._current_folder, f)))
            self.file_list.addItem(item)

        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def _go_up(self):
        if self._current_folder != self._training_folder:
            self._current_folder = os.path.dirname(self._current_folder)
            self._refresh_file_list()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data[0] == "folder":
            self._current_folder = data[1]
            self._refresh_file_list()
        elif data and data[0] == "pgn":
            self._start_training()

    # ---------------------------------------------------------------- #
    #  Démarrage de la session                                           #
    # ---------------------------------------------------------------- #

    def _start_training(self):
        item = self.file_list.currentItem()
        if not item:
            self.status_bar.showMessage("Sélectionnez un fichier d'abord.")
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or data[0] != "pgn":
            self.status_bar.showMessage("Sélectionnez un fichier PGN.")
            return
        path = data[1]
        exercises = self._build_exercises(path)

        if not exercises:
            self.status_bar.showMessage("Aucune position jouable dans ce fichier.")
            return

        self._session = TrainingSession(exercises)
        filename = os.path.basename(path)[:-4]
        folder_name = os.path.basename(os.path.dirname(path))
        self.lbl_file.setText(f"{folder_name} / {filename}")
        self._load_exercise()

    def _build_exercises(self, path: str) -> list:
        """
        Charge le PGN, collecte toutes les positions où il y a un coup suivant,
        choisit une position aléatoire et construit une séquence linéaire depuis là.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                game = chess.pgn.read_game(f)
            if game is None:
                return []

            # Reconstruire la liste de tous les coups de la ligne principale
            board = game.board()
            moves = list(game.mainline_moves())
            if len(moves) < 2:
                return []

            # Choisir un point de départ aléatoire (pas le dernier coup)
            max_start = len(moves) - 1
            start_idx = random.randint(0, max_start - 1)

            # Construire la liste des exercices depuis start_idx
            exercises = []
            b = game.board()
            for i, move in enumerate(moves):
                if i >= start_idx:
                    board_before = b.copy()
                    san = b.san(move)
                    b.push(move)
                    exercises.append((board_before, move, san, b.copy()))
                else:
                    b.push(move)

            return exercises

        except Exception as e:
            print(f"Erreur chargement entraînement : {e}")
            return []

    # ---------------------------------------------------------------- #
    #  Exercice courant                                                  #
    # ---------------------------------------------------------------- #

    def _load_exercise(self):
        if self._session is None or self._session.finished:
            self._show_final_score()
            return

        board_before, correct_move, san, board_after = self._session.current
        self.board.update_board(board_before)
        self.board.set_hint_move(None)
        self.board.set_last_move(None)

        turn = "Blancs" if board_before.turn == chess.WHITE else "Noirs"
        move_num = board_before.fullmove_number
        self.lbl_turn.setText(f"Tour {move_num} — {turn} jouent")
        self.lbl_position.setText(
            f"Exercice {self._session.index + 1} / {self._session.total}"
        )
        self._update_score_display()
        self.lbl_feedback.setText("Quel est le meilleur coup ?")
        self.lbl_feedback.setStyleSheet("color: #cdd6f4; font-size: 13px; font-weight: bold;")
        self._waiting_for_move = True
        self.btn_skip.setEnabled(True)
        self.status_bar.showMessage(f"Exercice {self._session.index + 1}/{self._session.total} — jouez !")

    def _on_move(self, move: chess.Move):
        if not self._waiting_for_move or self._session is None:
            return

        self._waiting_for_move = False
        board_before, correct_move, san, board_after = self._session.current

        if move == correct_move:
            # Bon coup
            self._session.score += 1
            self.lbl_feedback.setText(f"✓  Correct !  {san}")
            self.lbl_feedback.setStyleSheet(
                "color: #a6e3a1; font-size: 15px; font-weight: bold;"
            )
            self.board.update_board(board_after)
            self.board.set_last_move(move)
            self._update_score_display()
            QTimer.singleShot(1200, self._next_exercise)
        else:
            # Mauvais coup — montrer le bon
            try:
                played_san = board_before.san(move)
            except Exception:
                played_san = move.uci()
            self.lbl_feedback.setText(f"✗  {played_san}\nBon coup : {san}")
            self.lbl_feedback.setStyleSheet(
                "color: #f38ba8; font-size: 13px; font-weight: bold;"
            )
            # Afficher la flèche du bon coup
            self.board.set_hint_move(correct_move)
            self.board.update_board(board_before)
            QTimer.singleShot(2000, self._next_exercise)

    def _skip_exercise(self):
        if not self._session or self._session.finished:
            return
        _, correct_move, san, _ = self._session.current
        self.lbl_feedback.setText(f"Passé — coup : {san}")
        self.lbl_feedback.setStyleSheet("color: #f39c12; font-size: 13px;")
        self.board.set_hint_move(correct_move)
        self._waiting_for_move = False
        QTimer.singleShot(1500, self._next_exercise)

    def _next_exercise(self):
        self.board.set_hint_move(None)
        self._session.advance()
        self._load_exercise()

    def _update_score_display(self):
        if self._session:
            s = self._session.score
            t = self._session.total
            done = self._session.index
            self.lbl_score.setText(f"{s} / {t}")
            pct = int((done / t) * 100) if t > 0 else 0
            self.progress_bar.setValue(pct)

    def _show_final_score(self):
        self._waiting_for_move = False
        self.btn_skip.setEnabled(False)
        s = self._session.score
        t = self._session.total
        pct = int((s / t) * 100) if t > 0 else 0
        self.lbl_feedback.setText(
            f"Terminé !\n{s}/{t} coups corrects ({pct}%)"
        )
        self.lbl_feedback.setStyleSheet(
            "color: #f0c040; font-size: 15px; font-weight: bold;"
        )
        self.progress_bar.setValue(100)
        self.status_bar.showMessage(f"Session terminée — score : {s}/{t} ({pct}%)")

    # ---------------------------------------------------------------- #
    #  Navigation                                                        #
    # ---------------------------------------------------------------- #

    def _go_home(self):
        self.hide()
        self.home_requested.emit()

    def closeEvent(self, event):
        super().closeEvent(event)