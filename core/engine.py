"""
Interface avec le moteur Stockfish via python-chess.
Utilise un QThread pour ne pas bloquer l'interface.
"""
import chess
import chess.engine
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


# ------------------------------------------------------------------ #
#  Structures de données                                              #
# ------------------------------------------------------------------ #

class MoveInfo:
    """Représente un coup analysé avec son évaluation."""
    def __init__(self, move: chess.Move, score_cp: float, pv: list):
        self.move = move
        self.score_cp = score_cp   # centipions (positif = avantage blancs)
        self.pv = pv               # ligne principale

    def score_text(self) -> str:
        if abs(self.score_cp) >= 29000:
            side = "+" if self.score_cp > 0 else "-"
            return f"Mat {side}"
        pawns = self.score_cp / 100.0
        return f"{'+' if pawns >= 0 else ''}{pawns:.2f}"


# ------------------------------------------------------------------ #
#  Worker                                                             #
# ------------------------------------------------------------------ #

class EngineWorker(QObject):
    best_move_found  = pyqtSignal(chess.Move, float)
    multipv_ready    = pyqtSignal(list)          # list[MoveInfo]
    error_occurred   = pyqtSignal(str)

    def __init__(self, engine_path: str, parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def start_engine(self):
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self._engine.configure({"Threads": 2, "Hash": 128})
        except Exception as e:
            self.error_occurred.emit(f"Impossible de démarrer Stockfish : {e}")

    def stop_engine(self):
        if self._engine:
            self._engine.quit()
            self._engine = None

    @pyqtSlot(chess.Board, int, float)
    def find_best_move(self, board: chess.Board, depth: int, time_limit: float):
        if not self._engine:
            self.error_occurred.emit("Moteur non initialisé")
            return
        try:
            limit = chess.engine.Limit(depth=depth, time=time_limit)
            result = self._engine.play(board, limit, info=chess.engine.INFO_SCORE)
            score_cp = 0.0
            if result.info.get("score"):
                pov = result.info["score"].white()
                score_cp = 30000 if (pov.is_mate() and pov.mate() > 0) else \
                          -30000 if pov.is_mate() else float(pov.score() or 0)
            if result.move:
                self.best_move_found.emit(result.move, score_cp)
        except Exception as e:
            self.error_occurred.emit(f"Erreur moteur : {e}")

    @pyqtSlot(chess.Board, int, int)
    def find_multipv(self, board: chess.Board, depth: int, num_lines: int):
        """Calcule les N meilleurs coups (MultiPV)."""
        if not self._engine:
            return
        try:
            results = self._engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=num_lines,
            )
            moves = []
            for info in results:
                pv = info.get("pv", [])
                if not pv:
                    continue
                move = pv[0]
                score_cp = 0.0
                if info.get("score"):
                    pov = info["score"].white()
                    score_cp = 30000 if (pov.is_mate() and pov.mate() > 0) else \
                              -30000 if pov.is_mate() else float(pov.score() or 0)
                moves.append(MoveInfo(move, score_cp, pv))
            self.multipv_ready.emit(moves)
        except Exception as e:
            self.error_occurred.emit(f"Erreur multipv : {e}")


# ------------------------------------------------------------------ #
#  Contrôleur public                                                  #
# ------------------------------------------------------------------ #

class StockfishController(QObject):
    best_move_ready = pyqtSignal(chess.Move, float)
    multipv_ready   = pyqtSignal(list)           # list[MoveInfo]
    engine_error    = pyqtSignal(str)
    engine_ready    = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker: Optional[EngineWorker] = None
        self._available = False

    def load(self, engine_path: str = ""):
        path = self._resolve_path(engine_path)
        if not path:
            self.engine_error.emit("Stockfish introuvable.")
            self.engine_ready.emit(False)
            return
        self._worker = EngineWorker(path)
        self._worker.moveToThread(self._thread)
        self._worker.best_move_found.connect(self.best_move_ready)
        self._worker.multipv_ready.connect(self.multipv_ready)
        self._worker.error_occurred.connect(self.engine_error)
        self._thread.started.connect(self._worker.start_engine)
        self._thread.start()
        self._available = True
        self.engine_ready.emit(True)

    def unload(self):
        if self._worker:
            self._worker.stop_engine()
        self._thread.quit()
        self._thread.wait()

    def request_move(self, board: chess.Board, depth: int = 15, time_limit: float = 1.0):
        if self._available and self._worker:
            self._worker.find_best_move(board.copy(), depth, time_limit)

    def request_multipv(self, board: chess.Board, depth: int = 15, num_lines: int = 5):
        if self._available and self._worker:
            self._worker.find_multipv(board.copy(), depth, num_lines)

    def request_analysis(self, board: chess.Board, depth: int = 18):
        self.request_multipv(board, depth)

    @property
    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def _resolve_path(hint: str) -> Optional[str]:
        import shutil
        if hint and Path(hint).is_file():
            return hint
        found = shutil.which("stockfish")
        if found:
            return found
        for c in ["/usr/bin/stockfish", "/usr/local/bin/stockfish",
                  "/opt/homebrew/bin/stockfish", "stockfish", "stockfish.exe",
                  "./engines/stockfish", "./engines/stockfish.exe"]:
            if Path(c).is_file():
                return c
        return None