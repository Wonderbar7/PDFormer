import sys
import subprocess

def check_and_install_dependencies():
    required = {'fitz': 'PyMuPDF', 'PyQt5': 'PyQt5', 'qtawesome': 'qtawesome'}
    missing = []
    
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
            
    if missing:
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, 
                f"Preparando PDFormer por primera vez...\n\n"
                f"Se van a instalar las librerías necesarias: {', '.join(missing)}.\n"
                "Haz clic en Aceptar y espera un momento. El programa se abrirá automáticamente al terminar.", 
                "Instalando dependencias - PDFormer", 0x40)
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        except Exception as e:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"Error instalando los paquetes:\n{e}", "Error fatal", 0x10)
            sys.exit(1)

if __name__ == '__main__':
    check_and_install_dependencies()
    
    from PyQt5.QtWidgets import QApplication
    from ui.main_window import PDFFormEditor
    
    app = QApplication(sys.argv)
    # Importante para que los iconos de qtawesome carguen correctamente
    editor = PDFFormEditor()
    editor.show()
    sys.exit(app.exec_())
