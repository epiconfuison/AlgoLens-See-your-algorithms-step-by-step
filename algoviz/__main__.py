import sys
from PySide6.QtWidgets import QApplication
from algoviz.ui.window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('AlgoViz')
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
