"""
Panneau latéral gauche — explorateur de variantes.
Supporte la navigation dans les sous-dossiers du dossier "variantes".
"""
import os
import chess
import chess.pgn
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QMessageBox, QInputDialog, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon


class VariantsPanel(QFrame):
    variant_load_requested = pyqtSignal(str)   # chemin du fichier PGN
    save_requested = pyqtSignal(str, str)        # (dossier, nom)

    def __init__(self, variants_folder: str, parent=None):
        super().__init__(parent)
        self.root_folder    = variants_folder
        self.current_folder = variants_folder   # dossier affiché actuellement
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background: #1e1e2e; border-radius: 6px; }")
        self._build_ui()

    # ---------------------------------------------------------------- #
    #  Construction UI                                                   #
    # ---------------------------------------------------------------- #

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

        # Chemin courant
        self.lbl_path = QLabel("")
        self.lbl_path.setStyleSheet("color: #89b4fa; font-size: 10px;")
        self.lbl_path.setWordWrap(True)
        layout.addWidget(self.lbl_path)

        # Bouton retour
        self.btn_back = QPushButton("⬆  Dossier parent")
        self.btn_back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_back.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        self.btn_back.setMinimumHeight(28)
        self.btn_back.clicked.connect(self._go_up)
        layout.addWidget(self.btn_back)

        # Liste
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #181825; color: #cdd6f4;
                border: none; border-radius: 4px; font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #313244;
            }
            QListWidget::item:selected { background: #313244; color: #89b4fa; }
            QListWidget::item:hover    { background: #252535; }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        # Boutons d'action
        btn_row = QHBoxLayout()

        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_refresh.setStyleSheet("color: #cdd6f4; background: #313244; border-radius: 4px;")
        self.btn_refresh.setToolTip("Rafraîchir")
        self.btn_refresh.clicked.connect(self.refresh)

        self.btn_load = QPushButton("Charger")
        self.btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_load.setStyleSheet(
            "color: white; background: #2a7a2a; border-radius: 4px; font-weight: bold;"
        )
        self.btn_load.clicked.connect(self._on_load_clicked)

        self.btn_delete = QPushButton("🗑")
        self.btn_delete.setFixedWidth(36)
        self.btn_delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_delete.setStyleSheet("color: #f38ba8; background: #313244; border-radius: 4px;")
        self.btn_delete.setToolTip("Supprimer")
        self.btn_delete.clicked.connect(self._on_delete_clicked)

        for btn in (self.btn_refresh, self.btn_load, self.btn_delete):
            btn.setMinimumHeight(30)
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)

        # Nouveau dossier
        self.btn_new_folder = QPushButton("📁  Nouveau dossier")
        self.btn_new_folder.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_new_folder.setStyleSheet(
            "color: #f9e2af; background: #313244; border-radius: 4px;"
        )
        self.btn_new_folder.setMinimumHeight(30)
        self.btn_new_folder.clicked.connect(self._on_new_folder)
        layout.addWidget(self.btn_new_folder)

        # Sauvegarde dans le dossier courant
        save_row = QHBoxLayout()
        self.txt_save_name = QLineEdit()
        self.txt_save_name.setPlaceholderText("Nom de la variante…")
        self.txt_save_name.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.txt_save_name.setStyleSheet(
            "background: #181825; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px; padding: 3px;"
        )
        self.btn_save = QPushButton("💾 SAV")
        self.btn_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save.setFixedWidth(60)
        self.btn_save.setStyleSheet(
            "color: white; background: #2a7a2a; border-radius: 4px; font-weight: bold;"
        )
        self.btn_save.setMinimumHeight(30)
        self.btn_save.clicked.connect(self._on_save_clicked)
        save_row.addWidget(self.txt_save_name)
        save_row.addWidget(self.btn_save)
        layout.addLayout(save_row)

        # Statut
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #6c7086; font-size: 10px;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.refresh()

    # ---------------------------------------------------------------- #
    #  Navigation                                                        #
    # ---------------------------------------------------------------- #

    def refresh(self):
        """Affiche le contenu du dossier courant."""
        self.list_widget.clear()
        os.makedirs(self.current_folder, exist_ok=True)

        # Chemin relatif depuis root
        rel = os.path.relpath(self.current_folder, self.root_folder)
        self.lbl_path.setText("/" if rel == "." else f"/{rel.replace(os.sep, '/')}")
        self.btn_back.setEnabled(self.current_folder != self.root_folder)

        entries = os.listdir(self.current_folder)

        # Dossiers en premier
        folders = sorted([e for e in entries
                          if os.path.isdir(os.path.join(self.current_folder, e))])
        pgn_files = sorted([e for e in entries if e.endswith(".pgn")],
                           key=lambda f: os.path.getmtime(
                               os.path.join(self.current_folder, f)),
                           reverse=True)

        for folder in folders:
            item = QListWidgetItem(f"📁  {folder}")
            item.setData(Qt.ItemDataRole.UserRole, ("folder",
                         os.path.join(self.current_folder, folder)))
            item.setForeground(Qt.GlobalColor.yellow)
            self.list_widget.addItem(item)

        for filename in pgn_files:
            item = QListWidgetItem(f"♟  {filename[:-4]}")
            item.setData(Qt.ItemDataRole.UserRole, ("pgn",
                         os.path.join(self.current_folder, filename)))
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

        nb_pgn = len(pgn_files)
        nb_dir = len(folders)
        parts = []
        if nb_dir:
            parts.append(f"{nb_dir} dossier{'s' if nb_dir > 1 else ''}")
        if nb_pgn:
            parts.append(f"{nb_pgn} variante{'s' if nb_pgn > 1 else ''}")
        self.lbl_status.setText("  —  ".join(parts) if parts else "Dossier vide")

    def _go_up(self):
        if self.current_folder != self.root_folder:
            self.current_folder = os.path.dirname(self.current_folder)
            self.refresh()

    def _navigate(self, item: QListWidgetItem):
        """Double-clic : ouvre un dossier ou charge un PGN."""
        kind, path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "folder":
            self.current_folder = path
            self.refresh()
        elif kind == "pgn":
            self.variant_load_requested.emit(path)

    # ---------------------------------------------------------------- #
    #  Actions                                                           #
    # ---------------------------------------------------------------- #

    def _on_double_click(self, item: QListWidgetItem):
        self._navigate(item)

    def _on_load_clicked(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        kind, path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "folder":
            self.current_folder = path
            self.refresh()
        elif kind == "pgn":
            self.variant_load_requested.emit(path)

    def _on_save_clicked(self):
        name = self.txt_save_name.text().strip()
        if not name:
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Nom de la variante")
            dlg.setLabelText("Nom de la variante :")
            dlg.setStyleSheet("QWidget { background: white; color: black; }")
            if not dlg.exec():
                return
            name = dlg.textValue().strip()
        if name:
            self.save_requested.emit(self.current_folder, name)
            self.txt_save_name.clear()
            self.refresh()

    def _on_new_folder(self):
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Nouveau dossier")
        dlg.setLabelText("Nom du dossier :")
        dlg.setStyleSheet("QWidget { background: white; color: black; }")
        ok = dlg.exec()
        name = dlg.textValue()
        if not ok or not name.strip():
            return
        if not ok or not name.strip():
            return
        import re
        safe = re.sub(r'[\/:*?"<>|]', "_", name.strip())
        path = os.path.join(self.current_folder, safe)
        try:
            os.makedirs(path, exist_ok=False)
            self.refresh()
        except FileExistsError:
            b = self._msg(QMessageBox.Icon.Warning, "Erreur", f"Le dossier '{safe}' existe deja."); b.exec()
        except Exception as e:
            b = self._msg(QMessageBox.Icon.Warning, "Erreur", f"Impossible de creer le dossier : {e}"); b.exec()

    def _msg(self, icon, title, text):
        """QMessageBox avec fond blanc et texte noir."""
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStyleSheet("QWidget { background: white; color: black; }")
        return box

    def _on_delete_clicked(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        kind, path = item.data(Qt.ItemDataRole.UserRole)
        name = item.text().replace("📁  ", "").replace("♟  ", "")

        if kind == "folder":
            msg = f"Supprimer le dossier '{name}' et tout son contenu ?"
        else:
            msg = f"Supprimer la variante '{name}' ?"

        box = QMessageBox(self)
        box.setWindowTitle("Confirmer la suppression")
        box.setText(msg + "\n\nCette action est irreversible.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet("QWidget { background: white; color: black; }")
        reply = box.exec()
        if reply != QMessageBox.StandardButton.Yes.value:
            return

        try:
            if kind == "folder":
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
            self.refresh()
        except Exception as e:
            b = self._msg(QMessageBox.Icon.Warning, "Erreur", f"Impossible de supprimer : {e}"); b.exec()
