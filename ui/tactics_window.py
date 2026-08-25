"""
Mode Tactique — ChessOP
Charge des puzzles PGN avec FEN, Puzzle_Length et Tactic_line.
"""
import os
import random
import chess
import chess.pgn
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy,
    QStatusBar, QProgressBar, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ui.board_widget import BoardWidget


# ------------------------------------------------------------------ #
#  Structure d'un puzzle                                              #
# ------------------------------------------------------------------ #

class Puzzle:
    def __init__(self, fen: str, solution_moves: list[chess.Move],
                 solution_san: list[str], link: str = ""):
        self.fen            = fen
        self.solution_moves = solution_moves   # coups à jouer dans l'ordre
        self.solution_san   = solution_san
        self.link           = link

    @property
    def length(self) -> int:
        return len(self.solution_moves)


# ------------------------------------------------------------------ #
#  Session tactique                                                   #
# ------------------------------------------------------------------ #

class TacticsSession:
    def __init__(self, puzzles: list[Puzzle]):
        self.puzzles  = puzzles
        self.index    = 0
        self.score         = 0
        self.incorrect     = 0
        self.neutral       = 0
        self.total         = len(puzzles)
        self.move_idx       = 0
        self.puzzle_failed  = False
        self.puzzle_skipped = False
        self.puzzle_skipped = False   # True si indice ou passé

    @property
    def current(self) -> Puzzle | None:
        return self.puzzles[self.index] if self.index < self.total else None

    @property
    def finished(self) -> bool:
        return self.index >= self.total

    def next_puzzle(self):
        self.index        += 1
        self.move_idx       = 0
        self.puzzle_failed  = False
        self.puzzle_skipped = False


# ------------------------------------------------------------------ #
#  Fenêtre principale                                                 #
# ------------------------------------------------------------------ #

class TacticsWindow(QMainWindow):

    home_requested = pyqtSignal()

    DIFFICULTIES = {
        "Facile":  "easy",
        "Normal":  "normal",
        "Difficile": "hard",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessOP — Tactique")
        self.resize(1200, 800)

        self._session: TacticsSession = None
        self._all_puzzles: list = []
        self._waiting      = False
        self._board_state  = None
        self._difficulty   = "easy"
        self._tactics_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "ressources", "echec", "tactics"
        )
        for d in ("easy", "normal", "hard"):
            os.makedirs(os.path.join(self._tactics_root, d), exist_ok=True)

        self._build_ui()

    # ---------------------------------------------------------------- #
    #  UI                                                                #
    # ---------------------------------------------------------------- #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)

        # Créer le board EN PREMIER pour que les panneaux puissent y accéder
        self.board = BoardWidget()
        self.board.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.board.move_requested.connect(self._on_move)

        root.addLayout(self._build_left_panel())
        root.addWidget(self.board, stretch=2)
        root.addLayout(self._build_right_panel())

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Choisissez une difficulté et lancez")

    def _build_left_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Accueil
        btn_home = QPushButton("⌂  Accueil")
        btn_home.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_home.setStyleSheet(
            "color: #89b4fa; background: #313244; border-radius: 4px; font-weight: bold;"
        )
        btn_home.setMinimumHeight(34)
        btn_home.clicked.connect(self._go_home)
        layout.addWidget(btn_home)

        # Difficulté
        grp = QFrame()
        grp.setFrameShape(QFrame.Shape.StyledPanel)
        grp.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        grp_layout = QVBoxLayout(grp)

        lbl_diff = QLabel("Difficulté")
        lbl_diff.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        lbl_diff.setStyleSheet("color: #cdd6f4;")
        lbl_diff.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grp_layout.addWidget(lbl_diff)

        self._diff_buttons = {}
        styles = {
            "Facile":    "color: white; background: #2a7a2a; border-radius: 4px; font-weight: bold;",
            "Normal":    "color: white; background: #8a7a1a; border-radius: 4px; font-weight: bold;",
            "Difficile": "color: white; background: #8a1a1a; border-radius: 4px; font-weight: bold;",
        }
        for label, folder in self.DIFFICULTIES.items():
            btn = QPushButton(label)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCheckable(True)
            btn.setStyleSheet(styles[label])
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda _, f=folder, b=btn: self._set_difficulty(f, b))
            grp_layout.addWidget(btn)
            self._diff_buttons[folder] = btn

        # Sélectionner "easy" par défaut
        self._diff_buttons["easy"].setChecked(True)
        layout.addWidget(grp)

        # Bouton lancer
        self.btn_start = QPushButton("▶  Lancer")
        self.btn_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_start.setStyleSheet(
            "color: white; background: #2a7a2a; border-radius: 6px;"
            "font-weight: bold; font-size: 14px;"
        )
        self.btn_start.setMinimumHeight(42)
        self.btn_start.clicked.connect(self._start_session)
        layout.addWidget(self.btn_start)

        # Retourner
        btn_flip = QPushButton("⇄  Retourner l'échiquier")
        btn_flip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_flip.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        btn_flip.setMinimumHeight(30)
        btn_flip.clicked.connect(self.board.flip_board)
        layout.addWidget(btn_flip)

        layout.addStretch()
        return layout

    def _build_right_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Score
        grp = QFrame()
        grp.setFrameShape(QFrame.Shape.StyledPanel)
        grp.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        grp_layout = QVBoxLayout(grp)

        lbl_title = QLabel("Score")
        lbl_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #cdd6f4;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grp_layout.addWidget(lbl_title)

        score_row = QHBoxLayout()
        self.lbl_score = QLabel("0 ✓")
        self.lbl_score.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.lbl_score.setStyleSheet("color: #a6e3a1;")
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_incorrect = QLabel("0 ✗")
        self.lbl_incorrect.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.lbl_incorrect.setStyleSheet("color: #f38ba8;")
        self.lbl_incorrect.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_neutral = QLabel("0 —")
        self.lbl_neutral.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.lbl_neutral.setStyleSheet("color: #6c7086;")
        self.lbl_neutral.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_row.addWidget(self.lbl_score)
        score_row.addWidget(self.lbl_incorrect)
        score_row.addWidget(self.lbl_neutral)
        grp_layout.addLayout(score_row)


        layout.addWidget(grp)

        # Feedback
        self.lbl_feedback = QLabel("Trouvez le meilleur coup !")
        self.lbl_feedback.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setMinimumHeight(70)
        self.lbl_feedback.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(self.lbl_feedback)

        # Infos puzzle
        grp2 = QFrame()
        grp2.setFrameShape(QFrame.Shape.StyledPanel)
        grp2.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        grp2_layout = QVBoxLayout(grp2)

        self.lbl_puzzle_nb = QLabel("Puzzle : —")
        self.lbl_puzzle_nb.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.lbl_turn = QLabel("")
        self.lbl_turn.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: bold;")
        self.lbl_length = QLabel("")
        self.lbl_length.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.lbl_link = QLabel("")
        self.lbl_link.setStyleSheet("color: #89b4fa; font-size: 10px;")
        self.lbl_link.setWordWrap(True)

        for w in (self.lbl_puzzle_nb, self.lbl_turn, self.lbl_length, self.lbl_link):
            grp2_layout.addWidget(w)
        layout.addWidget(grp2)

        # Solution (masquée par défaut)
        self.lbl_solution = QLabel("")
        self.lbl_solution.setStyleSheet("color: #f0c040; font-size: 12px;")
        self.lbl_solution.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_solution.setVisible(False)
        layout.addWidget(self.lbl_solution)

        # Boutons
        self.btn_hint = QPushButton("💡 Indice")
        self.btn_hint.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_hint.setStyleSheet("color: #f9e2af; background: #313244; border-radius: 4px;")
        self.btn_hint.setMinimumHeight(30)
        self.btn_hint.clicked.connect(self._show_hint)
        self.btn_hint.setEnabled(False)
        layout.addWidget(self.btn_hint)

        self.btn_skip = QPushButton("Passer →")
        self.btn_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_skip.setStyleSheet("color: #f38ba8; background: #313244; border-radius: 4px;")
        self.btn_skip.setMinimumHeight(30)
        self.btn_skip.clicked.connect(self._skip_puzzle)
        self.btn_skip.setEnabled(False)
        layout.addWidget(self.btn_skip)

        layout.addStretch()
        return layout

    # ---------------------------------------------------------------- #
    #  Difficulté / Nb puzzles                                           #
    # ---------------------------------------------------------------- #

    def _set_difficulty(self, folder: str, btn: QPushButton):
        self._difficulty = folder
        for f, b in self._diff_buttons.items():
            b.setChecked(f == folder)

    # ---------------------------------------------------------------- #
    #  Chargement des puzzles                                            #
    # ---------------------------------------------------------------- #

    def _start_session(self):
        folder = os.path.join(self._tactics_root, self._difficulty)
        puzzles = self._load_puzzles(folder)
        if not puzzles:
            self.status_bar.showMessage(f"Aucun puzzle trouvé dans : {folder}")
            return
        random.shuffle(puzzles)
        self._all_puzzles = puzzles   # réserve pour la boucle infinie
        self._session = TacticsSession(list(puzzles))
        self.status_bar.showMessage(f"{len(puzzles)} puzzle(s) chargé(s) — bonne chance !")
        self._load_puzzle()

    def _load_puzzles(self, folder: str) -> list[Puzzle]:
        puzzles = []
        if not os.path.isdir(folder):
            return []
        for fname in os.listdir(folder):
            if not fname.endswith(".pgn"):
                continue
            path = os.path.join(folder, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    while True:
                        game = chess.pgn.read_game(f)
                        if game is None:
                            break
                        p = self._parse_puzzle(game)
                        if p:
                            puzzles.append(p)
            except Exception as e:
                print(f"Erreur lecture {fname} : {e}")
        return puzzles

    def _parse_puzzle(self, game) -> Puzzle | None:
        fen  = game.headers.get("FEN", "")
        link = game.headers.get("Link", "")
        tactic_line = game.headers.get("Tactic_line", "")
        if not fen:
            return None

        try:
            board = chess.Board(fen)
        except Exception:
            return None

        # Le 1er coup est informatif (joué automatiquement), les suivants = solution
        all_moves = list(game.mainline_moves())
        if not all_moves:
            return None

        b = board.copy()
        # Jouer le premier coup (informatif) et mettre à jour le board de départ
        info_move = all_moves[0]
        info_san  = b.san(info_move)
        b.push(info_move)
        # Mettre à jour le FEN après le coup informatif
        fen = b.fen()
        board = b.copy()

        puzzle_length = int(game.headers.get("Puzzle_Length", 1))
        solution_moves = []
        solution_san   = []
        for move in all_moves[1:]:
            san = b.san(move)
            b.push(move)
            solution_moves.append(move)
            solution_san.append(san)
            if len(solution_moves) >= puzzle_length * 2 - 1:
                break

        if not solution_moves:
            return None

        return Puzzle(fen, solution_moves, solution_san, link)

    # ---------------------------------------------------------------- #
    #  Affichage d'un puzzle                                             #
    # ---------------------------------------------------------------- #

    def _load_puzzle(self):
        if self._session is None or self._session.finished:
            self._show_final()
            return

        puzzle = self._session.current
        try:
            self._board_state = chess.Board(puzzle.fen)
        except Exception:
            self._session.next_puzzle()
            self._load_puzzle()
            return

        self.board.update_board(self._board_state)
        self.board.set_hint_move(None)
        self.board.set_last_move(None)
        self.lbl_solution.setVisible(False)

        # Afficher quel camp joue
        turn = "Blancs" if self._board_state.turn == chess.WHITE else "Noirs"
        self.lbl_turn.setText(f"{turn} jouent — trouvez le coup !")
        self.lbl_puzzle_nb.setText(
            f"Puzzle {self._session.index + 1} / {self._session.total}"
        )
        self.lbl_length.setText(
            f"Longueur : {puzzle.length} coup{'s' if puzzle.length > 1 else ''}"
        )
        self.lbl_link.setText(puzzle.link)
        self._update_score()
        self.lbl_feedback.setText("Trouvez le meilleur coup !")
        self.lbl_feedback.setStyleSheet("color: #cdd6f4; font-size: 13px; font-weight: bold;")

        self._waiting = True
        self._session.move_idx = 0
        self.btn_hint.setEnabled(True)
        self.btn_skip.setEnabled(True)

    # ---------------------------------------------------------------- #
    #  Interaction joueur                                                #
    # ---------------------------------------------------------------- #

    def _on_move(self, move: chess.Move):
        if not self._waiting or self._session is None:
            return
        puzzle = self._session.current
        if puzzle is None:
            return

        idx        = self._session.move_idx
        # Vérifier si c'est le tour du joueur (coups impairs : 0, 2, 4…)
        # Le joueur joue les coups d'index pair, l'adversaire les impairs
        expected   = puzzle.solution_moves[idx]
        san        = puzzle.solution_san[idx]

        if move == expected:
            # Bon coup
            self._board_state.push(move)
            self.board.update_board(self._board_state)
            self.board.set_last_move(move)
            self._session.move_idx += 1

            if self._session.move_idx >= puzzle.length:
                if self._session.puzzle_skipped:
                    # Indice utilisé → point neutre
                    self._session.neutral += 1
                elif not self._session.puzzle_failed:
                    # Trouvé sans erreur → point correct
                    self._session.score += 1
                self.lbl_feedback.setText(f"✓  Excellent !\n{san}")
                self.lbl_feedback.setStyleSheet(
                    "color: #a6e3a1; font-size: 16px; font-weight: bold;"
                )
                self._waiting = False
                self._update_score()
                QTimer.singleShot(1500, self._next_puzzle)
            else:
                # Coup correct mais il reste des coups — jouer la réponse adverse
                self.lbl_feedback.setText(f"✓  {san}")
                self.lbl_feedback.setStyleSheet("color: #a6e3a1; font-size: 13px;")
                QTimer.singleShot(600, self._play_opponent_move)
        else:
            # Mauvais coup
            try:
                played_san = self._board_state.san(move)
            except Exception:
                played_san = move.uci()
            if not self._session.puzzle_failed:
                self._session.incorrect += 1
                self._session.puzzle_failed = True
            self.lbl_feedback.setText(f"✗  {played_san}\nEssayez encore !")
            self.lbl_feedback.setStyleSheet(
                "color: #f38ba8; font-size: 13px; font-weight: bold;"
            )
            # Afficher la flèche de la bonne case de départ
            self.board.set_hint_move(None)
            self.board.update_board(self._board_state)

    def _play_opponent_move(self):
        """Joue automatiquement le coup de l'adversaire."""
        if self._session is None:
            return
        puzzle = self._session.current
        idx = self._session.move_idx
        if idx >= len(puzzle.solution_moves):
            return
        move = puzzle.solution_moves[idx]
        san  = puzzle.solution_san[idx]
        self._board_state.push(move)
        self.board.update_board(self._board_state)
        self.board.set_last_move(move)
        self._session.move_idx += 1
        self.lbl_feedback.setText(f"Adversaire : {san}\nVotre tour !")
        self.lbl_feedback.setStyleSheet("color: #cdd6f4; font-size: 13px;")

    def _show_hint(self):
        """Montre une flèche vers le bon coup."""
        if self._session is None or not self._waiting:
            return
        puzzle = self._session.current
        idx    = self._session.move_idx
        if idx < len(puzzle.solution_moves):
            move = puzzle.solution_moves[idx]
            self.board.set_hint_move(move)
            self.lbl_feedback.setText("💡 Indice affiché")
            self.lbl_feedback.setStyleSheet("color: #f9e2af; font-size: 13px;")
            self._session.puzzle_skipped = True

    def _skip_puzzle(self):
        if self._session is None:
            return
        self._session.puzzle_skipped = True
        self._session.neutral += 1
        puzzle = self._session.current
        sol = " ".join(puzzle.solution_san[:puzzle.length])
        self.lbl_solution.setText(f"Solution : {sol}")
        self.lbl_solution.setVisible(True)
        self.lbl_feedback.setText("Passé —")
        self.lbl_feedback.setStyleSheet("color: #6c7086; font-size: 13px;")
        self._waiting = False
        self._update_score()
        QTimer.singleShot(2000, self._next_puzzle)

    def _next_puzzle(self):
        self.board.set_hint_move(None)
        self._session.next_puzzle()
        if self._session.finished:
            # Recharger un nouveau lot mélangé pour la boucle infinie
            puzzles = list(self._all_puzzles)
            random.shuffle(puzzles)
            score_saved   = self._session.score
            incorr_saved  = self._session.incorrect
            neutral_saved = self._session.neutral
            self._session = TacticsSession(puzzles)
            self._session.score     = score_saved
            self._session.incorrect = incorr_saved
            self._session.neutral   = neutral_saved
        self._load_puzzle()

    def _update_score(self):
        if self._session:
            s    = self._session.score
            inc  = self._session.incorrect
            done = self._session.index
            t    = self._session.total
            n = self._session.neutral
            self.lbl_score.setText(f"{s} ✓")
            self.lbl_incorrect.setText(f"{inc} ✗")
            self.lbl_neutral.setText(f"{n} —")

    def _show_final(self):
        # Ne devrait plus être atteint (boucle infinie), mais sécurité
        self._next_puzzle()

    def _go_home(self):
        self.hide()
        self.home_requested.emit()

    def closeEvent(self, event):
        super().closeEvent(event)
