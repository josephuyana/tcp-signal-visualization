from __future__ import annotations

import sys
 
from PySide6.QtWidgets import QApplication

 
from views.main_window import MainWindow
from viewmodels.main_viewmodel import MainViewModel
from viewmodels.backend_service import BackendService
 
 
def main():
    app = QApplication(sys.argv)
 
    window = MainWindow()
    backend_service = BackendService()
 
    _vm = MainViewModel(window, backend_service)
 
    window.show()
    sys.exit(app.exec())
 
 
if __name__ == "__main__":
    main()
 