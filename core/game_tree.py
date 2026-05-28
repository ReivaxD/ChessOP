"""
Arbre de coups avec support des variantes.
Chaque nœud = une position, avec N enfants possibles (variantes).
"""
import chess
import chess.pgn
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal


class Node:
    """Un nœud dans l'arbre de coups."""

    def __init__(self, board: chess.Board, move: Optional[chess.Move] = None,
                 parent: Optional["Node"] = None):
        self.board    = board.copy()   # position APRÈS le coup
        self.move     = move           # coup qui a mené ici (None = racine)
        self.parent   = parent
        self.children: list["Node"] = []
        self.comment  = ""
        self.eval_cp: Optional[float] = None   # évaluation Stockfish après ce coup
        self.quality: str = ""                  # icône qualité du coup

    @property
    def is_root(self) -> bool:
        return self.parent is None

    def add_child(self, move: chess.Move) -> "Node":
        """Ajoute un enfant (nouveau coup). Retourne le nœud créé."""
        new_board = self.board.copy()
        new_board.push(move)
        child = Node(new_board, move, parent=self)
        self.children.append(child)
        return child

    def find_child(self, move: chess.Move) -> Optional["Node"]:
        """Cherche un enfant correspondant à ce coup."""
        for child in self.children:
            if child.move == move:
                return child
        return None

    def san(self) -> str:
        """Notation algébrique du coup qui mène à ce nœud."""
        if self.move is None or self.parent is None:
            return ""
        return self.parent.board.san(self.move)

    def move_number(self) -> str:
        """Retourne '1.' pour un coup blanc, '1...' pour un coup noir."""
        if self.parent is None:
            return ""
        # Le coup a été joué DEPUIS parent.board, donc c'est parent.board.turn
        # qui indique quelle couleur vient de jouer
        full = self.board.fullmove_number
        if self.parent.board.turn == chess.WHITE:
            # coup blanc : afficher le numéro
            return f"{full}."
        else:
            # coup noir : afficher le numéro seulement si nécessaire
            # (dans le rendu on n'affiche '...' que pour les variantes)
            return f"{full}."

    @staticmethod
    def classify_move(delta_cp: float, is_best: bool) -> str:
        """
        Calcule la qualité d'un coup selon la perte en centipions.
        delta_cp = eval_avant - eval_apres (du point de vue du joueur qui vient de jouer)
        Positif = perte, négatif = gain.
        """
        #print(is_best)
        if delta_cp < -90 and is_best:
            return "!!!"
        if delta_cp < -80:
            return "!!"   # Brillant : meilleur coup + gain inattendu
        if delta_cp < -15:
            return "!"    # Excellent
        if delta_cp < 25:
            return "✓✓"  # Très bon
        if delta_cp < 70:
            return "✓"   # Bon
        if delta_cp < 150:
            return "?!"   # Imprécis
        if delta_cp < 300:
            return "?"    # Erreur
        return "??"       # Blunder

    @staticmethod
    def quality_color(quality: str) -> str:
        colors = {
            "!!!": "#ffffff",
            "!!": "#00f7ff",
            "!":  "#0f7de4",
            "✓✓": "#01B136",
            "✓":  "#58d68d",
            "?!": "#f39c12",
            "?":  "#e67e22",
            "✕":  "#db4747",
            "??": "#e92e19",
        }
        return colors.get(quality, "#888888")

    def path_from_root(self) -> list["Node"]:
        """Retourne la liste des nœuds de la racine jusqu'ici."""
        nodes = []
        current = self
        while current is not None:
            nodes.append(current)
            current = current.parent
        return list(reversed(nodes))


class GameTree(QObject):
    """
    Gestionnaire de l'arbre de coups.
    Remplace GameManager — supporte les variantes.
    """

    board_changed  = pyqtSignal(chess.Board)
    move_made      = pyqtSignal(chess.Move)
    turn_changed   = pyqtSignal(bool)
    game_over      = pyqtSignal(str)
    tree_changed   = pyqtSignal()          # arbre modifié → reconstruire l'affichage
    node_selected  = pyqtSignal(object)    # nœud courant changé

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root    = Node(chess.Board())
        self._current = self._root

    # ---------------------------------------------------------------- #
    #  Propriétés                                                        #
    # ---------------------------------------------------------------- #

    @property
    def board(self) -> chess.Board:
        return self._current.board

    @property
    def current_node(self) -> Node:
        return self._current

    @property
    def root(self) -> Node:
        return self._root

    @property
    def current_turn(self) -> bool:
        return self._current.board.turn == chess.WHITE

    @property
    def is_game_over(self) -> bool:
        return self._current.board.is_game_over()

    @property
    def move_history(self) -> list[chess.Move]:
        """Coups de la ligne principale depuis la racine."""
        return [n.move for n in self._current.path_from_root() if n.move]

    # ---------------------------------------------------------------- #
    #  Actions                                                           #
    # ---------------------------------------------------------------- #

    def new_game(self):
        self._root    = Node(chess.Board())
        self._current = self._root
        self._emit_all()
        self.tree_changed.emit()

    def make_move(self, move: chess.Move) -> bool:
        """
        Joue un coup.
        - Si le coup existe déjà comme enfant → on le suit.
        - Sinon → nouvelle variante.
        """
        if move not in self._current.board.legal_moves:
            return False

        existing = self._current.find_child(move)
        if existing:
            self._current = existing
        else:
            self._current = self._current.add_child(move)
            self.tree_changed.emit()

        self.move_made.emit(move)
        self._emit_all()

        if self._current.board.is_game_over():
            self.game_over.emit(self._result_message())
        else:
            self.turn_changed.emit(self.current_turn)
        return True

    def go_to_node(self, node: Node):
        """Navigue vers un nœud de l'arbre (clic dans l'historique)."""
        self._current = node
        self._emit_all()
        self.node_selected.emit(node)

    def go_to_root(self):
        self.go_to_node(self._root)

    def go_back(self) -> bool:
        if self._current.parent:
            self.go_to_node(self._current.parent)
            return True
        return False

    def go_forward(self) -> bool:
        """Avance sur le premier enfant (ligne principale)."""
        if self._current.children:
            self.go_to_node(self._current.children[0])
            return True
        return False

    def go_to_end(self):
        """Navigue jusqu'au dernier coup de la ligne principale."""
        node = self._current
        while node.children:
            node = node.children[0]
        self.go_to_node(node)

    def delete_current_variation(self):
        """Supprime le nœud courant et ses descendants."""
        node = self._current
        if node.is_root:
            return
        parent = node.parent
        parent.children.remove(node)
        self.go_to_node(parent)
        self.tree_changed.emit()

    # ---------------------------------------------------------------- #
    #  Export                                                            #
    # ---------------------------------------------------------------- #

    def to_pgn(self) -> str:
        game = chess.pgn.Game()
        self._build_pgn_node(game, self._root)
        return str(game)

    def _build_pgn_node(self, pgn_node, tree_node: Node):
        for i, child in enumerate(tree_node.children):
            if i == 0:
                next_pgn = pgn_node.add_variation(child.move)
            else:
                next_pgn = pgn_node.add_variation(child.move)
            self._build_pgn_node(next_pgn, child)

    def load_pgn(self, path: str) -> bool:
        """Charge un fichier PGN avec variantes dans l'arbre."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                game = chess.pgn.read_game(f)
            if game is None:
                return False
            self._root    = Node(chess.Board())
            self._current = self._root
            self._import_pgn_node(game, self._root)
            # Naviguer jusqu'au dernier coup de la ligne principale
            node = self._root
            while node.children:
                node = node.children[0]
            self._current = node
            self.tree_changed.emit()
            self._emit_all()
            self.turn_changed.emit(self.current_turn)
            if node.move:
                self.move_made.emit(node.move)
            return True
        except Exception as e:
            print(f"Erreur load_pgn : {e}")
            return False

    def _import_pgn_node(self, pgn_node, tree_node: Node):
        for variation in pgn_node.variations:
            child = tree_node.add_child(variation.move)
            self._import_pgn_node(variation, child)

    def get_fen(self) -> str:
        return self._current.board.fen()

    # ---------------------------------------------------------------- #
    #  Privé                                                             #
    # ---------------------------------------------------------------- #

    def _emit_all(self):
        self.board_changed.emit(self._current.board.copy())

    def _result_message(self) -> str:
        outcome = self._current.board.outcome()
        if outcome is None:
            return "Partie terminée"
        if outcome.winner == chess.WHITE:
            return "Les blancs gagnent !"
        if outcome.winner == chess.BLACK:
            return "Les noirs gagnent !"
        reasons = {
            chess.Termination.STALEMATE:             "Pat",
            chess.Termination.INSUFFICIENT_MATERIAL: "Matériel insuffisant",
            chess.Termination.FIVEFOLD_REPETITION:   "Répétition quintuple",
            chess.Termination.FIFTY_MOVES:            "Règle des 50 coups",
        }
        return f"Nulle — {reasons.get(outcome.termination, 'Accord mutuel')}"
