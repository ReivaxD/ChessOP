"""
Panneau latéral gauche listant les variantes sauvegardées.
"""
import os
import chess
import chess.pgn
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class VariantsPanel(QFrame):
    """Panneau qui liste et charge les fichiers PGN du dossier variantes."""

    variant_load_requested = pyqtSignal(str)   # chemin du fichier PGN

    def __init__(self, variants_folder: str, parent=None):
        super().__init__(parent)
        self.variants_folder = variants_folder
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Titre
        title = QLabel("Variantes sauvegardées")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Liste
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #181825;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #313244;
            }
            QListWidget::item:selected {
                background: #313244;
                color: #89b4fa;
            }
            QListWidget::item:hover {
                background: #252535;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        # Boutons
        btn_layout = QHBoxLayout()

        self.btn_refresh = QPushButton("↻ Rafraîchir")
        self.btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_refresh.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        self.btn_refresh.clicked.connect(self.refresh)

        self.btn_load = QPushButton("Charger")
        self.btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_load.setStyleSheet(
            "color: white; background: #2a7a2a; border-radius: 4px; font-weight: bold;"
        )
        self.btn_load.clicked.connect(self._on_load_clicked)

        self.btn_delete = QPushButton("🗑 Supprimer")
        self.btn_delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_delete.setStyleSheet(
            "color: #f38ba8; background: #313244; border-radius: 4px;"
        )
        self.btn_delete.clicked.connect(self._on_delete_clicked)

        for btn in (self.btn_refresh, self.btn_load, self.btn_delete):
            btn.setMinimumHeight(30)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        # Double-clic = charger directement
        self.lbl_hint = QLabel("Double-clic pour charger")
        self.lbl_hint.setStyleSheet("color: #6c7086; font-size: 10px;")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_hint)

        self.refresh()

    def refresh(self):
        """Recharge la liste des fichiers PGN."""
        self.list_widget.clear()
        if not os.path.isdir(self.variants_folder):
            return
        files = sorted(
            [f for f in os.listdir(self.variants_folder) if f.endswith(".pgn")],
            key=lambda f: os.path.getmtime(os.path.join(self.variants_folder, f)),
            reverse=True   # plus récents en premier
        )
        for filename in files:
            item = QListWidgetItem(filename[:-4])  # sans .pgn
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(self.variants_folder, filename))
            self.list_widget.addItem(item)

        self.lbl_hint.setText(
            f"{len(files)} variante{'s' if len(files) != 1 else ''} — sélectionner puis Charger"
        )
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_load_clicked(self):
        item = self.list_widget.currentItem()
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            self.variant_load_requested.emit(path)

    def _on_delete_clicked(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        path = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "Supprimer la variante",
            f"Etes-vous sur de vouloir supprimer '{name}' ?\n\nCette action est irreversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Impossible de supprimer : {e}")

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.variant_load_requested.emit(path)
