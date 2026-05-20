"""
Point d'entrée principal de ChessOP.
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_launcher import MainLauncher


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ChessOP")
    app.setApplicationVersion("1.5.0")

    launcher = MainLauncher()
    launcher.show()

    code = app.exec()
    # S'assurer que le moteur est bien arrêté avant de quitter
    app.closeAllWindows()
    sys.exit(code)


if __name__ == "__main__":
    main()
