"""
Fenêtre principale de ChessOP — point d'entrée et menu des modules.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor


class ModuleCard(QFrame):
    """Carte cliquable représentant un module."""

    def __init__(self, icon: str, title: str, description: str,
                 available: bool = True, parent=None):
        super().__init__(parent)
        self.available = available
        self.setFixedSize(220, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor if available
                       else Qt.CursorShape.ForbiddenCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        if available:
            self.setStyleSheet("""
                QFrame {
                    background: #2a2a3e;
                    border: 2px solid #404060;
                    border-radius: 12px;
                }
                QFrame:hover {
                    background: #353550;
                    border: 2px solid #7c6af7;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: #1a1a28;
                    border: 2px solid #2a2a40;
                    border-radius: 12px;
                }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        lbl_icon = QLabel(icon)
        lbl_icon.setFont(QFont("Segoe UI Emoji", 32))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("border: none; background: transparent;")

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(
            f"color: {'#cdd6f4' if available else '#555570'}; border: none; background: transparent;"
        )

        lbl_desc = QLabel(description)
        lbl_desc.setFont(QFont("Arial", 9))
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(
            f"color: {'#6c7086' if available else '#35354a'}; border: none; background: transparent;"
        )

        if not available:
            lbl_soon = QLabel("Bientôt disponible")
            lbl_soon.setFont(QFont("Arial", 8))
            lbl_soon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_soon.setStyleSheet("color: #7c6af7; border: none; background: transparent;")
            layout.addWidget(lbl_icon)
            layout.addWidget(lbl_title)
            layout.addWidget(lbl_soon)
        else:
            layout.addWidget(lbl_icon)
            layout.addWidget(lbl_title)
            layout.addWidget(lbl_desc)

    def mousePressEvent(self, event):
        if self.available:
            self.parent().parent()._on_card_clicked(self)
        super().mousePressEvent(event)


class MainLauncher(QMainWindow):
    """Fenêtre d'accueil — menu principal de ChessOP."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessOP")
        self.resize(1200, 800)
        self._child_windows = {}
        self._build_ui()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self._cleanup)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background: #181825;")

        root = QVBoxLayout(central)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(20)

        # En-tête
        header = QVBoxLayout()
        lbl_logo = QLabel("♟")
        lbl_logo.setFont(QFont("Segoe UI Emoji", 48))
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_logo.setStyleSheet("color: #cdd6f4;")

        lbl_title = QLabel("ChessOP")
        lbl_title.setFont(QFont("Arial", 30, QFont.Weight.Bold))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("color: #cdd6f4;")

        lbl_sub = QLabel("Choisissez un module")
        lbl_sub.setFont(QFont("Arial", 12))
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("color: #6c7086;")

        header.addWidget(lbl_logo)
        header.addWidget(lbl_title)
        header.addWidget(lbl_sub)
        root.addLayout(header)

        # Grille de cartes — 2 lignes
        self._cards = {
            "analysis": ModuleCard("🔍", "Analyse",      "Analysez vos parties\net variantes"),
            "openings": ModuleCard("📖", "Ouvertures",   "Base d'ouvertures",           available=False),
            "training": ModuleCard("🎯", "Entraînement", "Puzzles et exercices",         available=False),
            "tactics":  ModuleCard("⚔️",  "Tactique",    "Exercices tactiques",          available=False),
            "database": ModuleCard("🗄️", "Base de données", "Parties de référence",     available=False),
        }

        row1 = QHBoxLayout()
        row1.setSpacing(20)
        row1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for key in ("analysis", "openings", "training"):
            card = self._cards[key]
            card.setParent(central)
            row1.addWidget(card)

        row2 = QHBoxLayout()
        row2.setSpacing(20)
        row2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for key in ("tactics", "database"):
            card = self._cards[key]
            card.setParent(central)
            row2.addWidget(card)

        root.addLayout(row1)
        root.addLayout(row2)
        root.addStretch()

        # Version
        lbl_version = QLabel("v1.5.0")
        lbl_version.setAlignment(Qt.AlignmentFlag.AlignRight)
        lbl_version.setStyleSheet("color: #313244; font-size: 10px;")
        root.addWidget(lbl_version)

    def _on_card_clicked(self, card: ModuleCard):
        key = [k for k, v in self._cards.items() if v is card][0]

        if key == "analysis":
            self._open_analysis()

    def _open_analysis(self):
        if "analysis" not in self._child_windows:
            from ui.analysis_window import AnalysisWindow
            win = AnalysisWindow()
            win.home_requested.connect(self._show_launcher)
            self._child_windows["analysis"] = win
        self.hide()
        self._child_windows["analysis"].show()
        self._child_windows["analysis"].activateWindow()

    def _show_launcher(self):
        self.show()
        self.activateWindow()

    def _cleanup(self):
        """Arrêt propre de tous les moteurs avant fermeture."""
        for win in self._child_windows.values():
            if hasattr(win, "engine"):
                win.engine.unload()
