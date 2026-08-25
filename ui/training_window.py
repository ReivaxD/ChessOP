"""
Mode Entraînement — ChessOP
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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ui.board_widget import BoardWidget

# Modes d'entraînement
MODE_DEBUT  = "debut"
MODE_HASARD = "hasard"
MODE_BLANC  = "blanc"
MODE_NOIR   = "noir"


class TrainingSession:
    """Séquence de positions — chaque entrée = (board_avant, coup_correct, san, board_apres)"""

    def __init__(self, exercises: list, player_color=None):
        self.exercises    = exercises
        self.player_color = player_color  # None = tous, WHITE/BLACK = filtré
        self.index        = 0
        self.score        = 0
        self.total        = len(exercises)
        # Calculer max_score une seule fois à l'init
        if player_color is None:
            self.max_score = self.total
        else:
            self.max_score = sum(
                1 for board_before, _, _, _ in exercises
                if board_before.turn == player_color
            )
        print(f"[SESSION] total={self.total} max_score={self.max_score} color={player_color}")

    @property
    def current(self):
        return self.exercises[self.index] if self.index < self.total else None

    @property
    def finished(self):
        return self.index >= self.total

    def advance(self):
        self.index += 1

    def is_player_turn(self) -> bool:
        """Retourne True si c'est au joueur de deviner."""
        if self.player_color is None or self.current is None:
            return True
        board_before, _, _, _ = self.current
        return board_before.turn == self.player_color


class TrainingWindow(QMainWindow):

    home_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessOP — Entraînement")
        self.resize(1200, 800)

        self._session: TrainingSession = None
        self._waiting_for_move = False
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._training_folder = os.path.join(_base, "ressources", "echec")
        self._current_folder  = self._training_folder
        os.makedirs(os.path.join(_base, "ressources", "echec", "entrainement"), exist_ok=True)
        os.makedirs(os.path.join(_base, "ressources", "echec", "ouverture"), exist_ok=True)

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

        root.addWidget(self._build_file_panel())

        self.board = BoardWidget()
        self.board.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.board.move_requested.connect(self._on_move)
        root.addWidget(self.board, stretch=2)

        root.addLayout(self._build_score_panel())

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sélectionnez un fichier et lancez l'entraînement")

    def _build_file_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(230)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        title = QLabel("Fichiers d'entraînement")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.lbl_path = QLabel("/")
        self.lbl_path.setStyleSheet("color: #89b4fa; font-size: 10px;")
        self.lbl_path.setWordWrap(True)
        layout.addWidget(self.lbl_path)

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
            QListWidget::item { padding: 5px 8px; border-bottom: 1px solid #313244; }
            QListWidget::item:selected { background: #313244; color: #89b4fa; }
            QListWidget::item:hover { background: #252535; }
        """)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.file_list)

        btn_refresh = QPushButton("↻ Rafraîchir")
        btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_refresh.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        btn_refresh.setMinimumHeight(24)
        btn_refresh.clicked.connect(self._refresh_file_list)
        layout.addWidget(btn_refresh)

        # 4 boutons de lancement
        sep = QLabel("── Lancer ──")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("color: #6c7086; font-size: 10px;")
        layout.addWidget(sep)

        btn_style_green  = "color: white; background: #2a7a2a; border-radius: 4px; font-weight: bold;"
        btn_style_blue   = "color: white; background: #1a5a8a; border-radius: 4px; font-weight: bold;"
        btn_style_orange = "color: white; background: #8a5a1a; border-radius: 4px; font-weight: bold;"
        btn_style_purple = "color: white; background: #5a1a8a; border-radius: 4px; font-weight: bold;"

        self.btn_debut  = QPushButton("▶  Depuis le début")
        self.btn_hasard = QPushButton("🎲  Position aléatoire")
        self.btn_blanc  = QPushButton("♔  Entraîner les blancs")
        self.btn_noir   = QPushButton("♚  Entraîner les noirs")

        self.btn_debut.setStyleSheet(btn_style_green)
        self.btn_hasard.setStyleSheet(btn_style_blue)
        self.btn_blanc.setStyleSheet(btn_style_orange)
        self.btn_noir.setStyleSheet(btn_style_purple)

        for btn in (self.btn_debut, self.btn_hasard, self.btn_blanc, self.btn_noir):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setMinimumHeight(30)
            layout.addWidget(btn)

        self.btn_debut.clicked.connect(lambda: self._start_training(MODE_DEBUT))
        self.btn_hasard.clicked.connect(lambda: self._start_training(MODE_HASARD))
        self.btn_blanc.clicked.connect(lambda: self._start_training(MODE_BLANC))
        self.btn_noir.clicked.connect(lambda: self._start_training(MODE_NOIR))

        return frame

    def _build_score_panel(self) -> QVBoxLayout:
        side = QVBoxLayout()
        side.setSpacing(10)

        self.btn_home = QPushButton("⌂  Accueil")
        self.btn_home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_home.setStyleSheet(
            "color: #89b4fa; background: #313244; border-radius: 4px; font-weight: bold;"
        )
        self.btn_home.setMinimumHeight(34)
        self.btn_home.clicked.connect(self._go_home)
        side.addWidget(self.btn_home)

        # Retourner l'échiquier
        btn_flip = QPushButton("⇄  Retourner l'échiquier")
        btn_flip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_flip.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        btn_flip.setMinimumHeight(30)
        btn_flip.clicked.connect(self.board.flip_board)
        side.addWidget(btn_flip)

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

        # Mode actif
        self.lbl_mode = QLabel("")
        self.lbl_mode.setStyleSheet("color: #89b4fa; font-size: 11px;")
        self.lbl_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.lbl_mode)

        # Feedback
        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setMinimumHeight(60)
        side.addWidget(self.lbl_feedback)

        # Infos
        grp_info = QFrame()
        grp_info.setFrameShape(QFrame.Shape.StyledPanel)
        grp_info.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        info_layout = QVBoxLayout(grp_info)
        self.lbl_file     = QLabel("Fichier : —")
        self.lbl_file.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.lbl_file.setWordWrap(True)
        self.lbl_position = QLabel("Exercice : —")
        self.lbl_position.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.lbl_turn     = QLabel("")
        self.lbl_turn.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: bold;")
        for w in (self.lbl_file, self.lbl_position, self.lbl_turn):
            info_layout.addWidget(w)
        side.addWidget(grp_info)

        # Bouton passer
        self.btn_skip = QPushButton("Passer →")
        self.btn_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_skip.setStyleSheet("color: #f38ba8; background: #313244; border-radius: 4px;")
        self.btn_skip.setMinimumHeight(32)
        self.btn_skip.clicked.connect(self._skip_exercise)
        self.btn_skip.setEnabled(False)
        side.addWidget(self.btn_skip)

        side.addStretch()
        return side

    # ---------------------------------------------------------------- #
    #  Navigation fichiers                                               #
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
            self._start_training(MODE_DEBUT)

    def _get_selected_path(self):
        item = self.file_list.currentItem()
        if not item:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or data[0] != "pgn":
            return None
        return data[1]

    # ---------------------------------------------------------------- #
    #  Construction des exercices                                        #
    # ---------------------------------------------------------------- #

    def _start_training(self, mode: str):
        path = self._get_selected_path()
        if not path:
            self.status_bar.showMessage("Sélectionnez un fichier PGN.")
            return

        exercises = self._build_exercises(path, mode)
        if not exercises:
            self.status_bar.showMessage("Aucune position jouable dans ce fichier.")
            return

        player_color = None
        if mode == MODE_BLANC:
            player_color = chess.WHITE
        elif mode == MODE_NOIR:
            player_color = chess.BLACK

        self._session = TrainingSession(exercises, player_color)

        mode_labels = {
            MODE_DEBUT:  "Depuis le début",
            MODE_HASARD: "Position aléatoire",
            MODE_BLANC:  "Entraîner les blancs",
            MODE_NOIR:   "Entraîner les noirs",
        }
        self.lbl_mode.setText(f"Mode : {mode_labels.get(mode, mode)}")

        filename = os.path.basename(path)[:-4]
        folder   = os.path.basename(os.path.dirname(path))
        self.lbl_file.setText(f"{folder} / {filename}")

        self._load_exercise()

    def _build_exercises(self, path: str, mode: str) -> list:
        try:
            with open(path, "r", encoding="utf-8") as f:
                game = chess.pgn.read_game(f)
            if game is None:
                return []

            moves = list(game.mainline_moves())
            if len(moves) < 1:
                return []

            board = game.board()

            # Point de départ selon le mode
            if mode == MODE_HASARD and len(moves) > 1:
                start = random.randint(0, len(moves) - 2)
            else:
                start = 0

            exercises = []
            b = board.copy()
            for i, move in enumerate(moves):
                if i >= start:
                    board_before = b.copy()
                    san = b.san(move)
                    b.push(move)
                    exercises.append((board_before, move, san, b.copy()))
                else:
                    b.push(move)

            return exercises

        except Exception as e:
            print(f"Erreur : {e}")
            return []

    # ---------------------------------------------------------------- #
    #  Exercice courant                                                  #
    # ---------------------------------------------------------------- #

    def _load_exercise(self):
        if self._session is None or self._session.finished:
            self._show_final_score()
            return

        board_before, correct_move, san, _ = self._session.current
        self.board.update_board(board_before)
        self.board.set_hint_move(None)
        self.board.set_last_move(None)

        turn = "Blancs" if board_before.turn == chess.WHITE else "Noirs"
        self.lbl_turn.setText(f"Tour {board_before.fullmove_number} — {turn}")
        self.lbl_position.setText(
            f"Exercice {self._session.index + 1} / {self._session.total}"
        )
        self._update_score_display()

        if self._session.is_player_turn():
            self.lbl_feedback.setText("Quel est le meilleur coup ?")
            self.lbl_feedback.setStyleSheet("color: #cdd6f4; font-size: 13px; font-weight: bold;")
            self._waiting_for_move = True
            self.btn_skip.setEnabled(True)
            self.status_bar.showMessage(
                f"Exercice {self._session.index + 1}/{self._session.total} — jouez !"
            )
        else:
            # Coup adverse — jouer automatiquement après un court délai
            self._waiting_for_move = False
            self.btn_skip.setEnabled(False)
            self.lbl_feedback.setText(f"Adversaire : {san}")
            self.lbl_feedback.setStyleSheet("color: #6c7086; font-size: 12px;")
            QTimer.singleShot(800, self._auto_play_opponent)

    def _auto_play_opponent(self):
        """Joue automatiquement le coup de l'adversaire."""
        if self._session is None or self._session.finished:
            return
        _, correct_move, san, board_after = self._session.current
        self.board.update_board(board_after)
        self.board.set_last_move(correct_move)
        self._session.advance()
        QTimer.singleShot(400, self._load_exercise)

    def _on_move(self, move: chess.Move):
        if not self._waiting_for_move or self._session is None:
            return

        self._waiting_for_move = False
        board_before, correct_move, san, board_after = self._session.current

        if move == correct_move:
            self._session.score += 1
            self.lbl_feedback.setText(f"✓  Correct !  {san}")
            self.lbl_feedback.setStyleSheet(
                "color: #a6e3a1; font-size: 15px; font-weight: bold;"
            )
            self.board.update_board(board_after)
            self.board.set_last_move(move)
            self._update_score_display()
            self._session.advance()
            QTimer.singleShot(1200, self._load_exercise)
        else:
            try:
                played_san = board_before.san(move)
            except Exception:
                played_san = move.uci()
            self.lbl_feedback.setText(f"✗  {played_san}\nBon coup : {san}")
            self.lbl_feedback.setStyleSheet(
                "color: #f38ba8; font-size: 13px; font-weight: bold;"
            )
            self.board.set_hint_move(correct_move)
            self._session.advance()
            QTimer.singleShot(2000, self._load_exercise)

    def _skip_exercise(self):
        if not self._session or self._session.finished:
            return
        _, correct_move, san, _ = self._session.current
        self.lbl_feedback.setText(f"Passé — coup : {san}")
        self.lbl_feedback.setStyleSheet("color: #f39c12; font-size: 13px;")
        self.board.set_hint_move(correct_move)
        self._waiting_for_move = False
        self._session.advance()
        QTimer.singleShot(1500, self._load_exercise)

    def _update_score_display(self):
        if self._session:
            s  = self._session.score
            ms = self._session.max_score
            t  = self._session.total
            done = self._session.index
            self.lbl_score.setText(f"{s} / {ms}")
            self.progress_bar.setValue(int((done / t) * 100) if t > 0 else 0)

    def _show_final_score(self):
        self._waiting_for_move = False
        self.btn_skip.setEnabled(False)
        s  = self._session.score
        ms = self._session.max_score
        pct = int((s / ms) * 100) if ms > 0 else 0
        self.lbl_feedback.setText(f"Terminé !\n{s}/{ms} corrects ({pct}%)")
        self.lbl_feedback.setStyleSheet(
            "color: #f0c040; font-size: 15px; font-weight: bold;"
        )
        self.progress_bar.setValue(100)
        self.status_bar.showMessage(f"Session terminée — {s}/{ms} ({pct}%)")

    def _go_home(self):
        self.hide()
        self.home_requested.emit()

    def closeEvent(self, event):
        super().closeEvent(event)
