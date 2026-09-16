# CATEGORÍA DICCIONARIO
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextBrowser, QVBoxLayout, QWidget, QLineEdit, QAction, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal
import markdown2
import requests
import subprocess

url = "https://raw.githubusercontent.com/sapoclay/diccionario/main/diccionario.md"  # Coloca la URL del archivo markdown que deseas cargar


class VentanaDiccionario(QMainWindow):
    
    """
    Clase que define una ventana de visualización de un diccionario.

    Esta ventana permite cargar contenido desde un archivo markdown o una URL, realizar búsquedas en el contenido y abrir una terminal desde la aplicación.

    Attributes:
        closed (pyqtSignal): Señal para indicar que la ventana se ha cerrado.
    """
    
    closed = pyqtSignal()  # Señal para indicar que la ventana se ha cerrado
    
    def __init__(self, contenido_html):
        
        """
        Inicializa una instancia de VentanaDiccionario.

        Parameters:
            contenido_html (str): Contenido HTML a mostrar en la ventana.
        """
        
        super().__init__()
        self.setWindowTitle("Diccionario")
        self.resize(800, 600)  # Establecer un tamaño inicial más grande
        self.contenido_html_original = contenido_html
        self.contenido_html_actual = contenido_html  # Mantener una referencia al contenido HTML actual
        self.cargar_contenido(contenido_html)
        self.crear_menu()

    def cargar_contenido(self, contenido_html):
        
        """
        Carga el contenido HTML en la ventana.

        Parameters:
            contenido_html (str): Contenido HTML a cargar en la ventana.
        """
        
        self.browser = QTextBrowser()
        self.browser.setHtml(contenido_html)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar...")
        self.search_input.textChanged.connect(self.buscar)
        
        layout = QVBoxLayout()
        layout.addWidget(self.search_input)
        layout.addWidget(self.browser)
        
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def buscar(self):
        
        """
        Filtra el contenido HTML según el término de búsqueda que el usuario escriba en el campo de búsqueda.
        """
        
        search_term = self.search_input.text().lower()
        if search_term:
            filtered_html = self.filter_html(search_term)
            self.browser.setHtml(filtered_html)
            self.contenido_html_actual = filtered_html  # Actualizar el contenido HTML actual
        else:
            self.browser.setHtml(self.contenido_html_original)
            self.contenido_html_actual = self.contenido_html_original  # Restaurar el contenido HTML actual al original

    def filter_html(self, search_term):
        # Filtrar el contenido HTML actual para mostrar solo los elementos que contienen el término de búsqueda
        filtered_html = ""
        lines = self.contenido_html_actual.split('\n')
        for line in lines:
            if search_term in line.lower():
                filtered_html += line + '\n'
        return filtered_html

    def cargar_desde_archivo(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", "", "Archivos Markdown (*.md)")
        if filename:
            with open(filename, "r") as file:
                contenido_md = file.read()
            contenido_html = markdown2.markdown(contenido_md)
            self.contenido_html_original = contenido_html  # Actualizar el contenido HTML original
            self.contenido_html_actual = contenido_html  # Actualizar el contenido HTML actual
            self.cargar_contenido(contenido_html)

    def recargar_desde_url(self):
        try:
            contenido_md = requests.get(url).text
            contenido_html = markdown2.markdown(contenido_md)
            self.contenido_html_original = contenido_html  # Actualizar el contenido HTML original
            self.contenido_html_actual = contenido_html  # Actualizar el contenido HTML actual
            self.cargar_contenido(contenido_html)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo cargar el contenido desde la URL:\n\n{e}")

    def crear_menu(self):
        menu_bar = self.menuBar()
        archivo_menu = menu_bar.addMenu("Archivo")

        # Opción para abrir archivo
        abrir_action = QAction("Abrir archivo", self)
        abrir_action.triggered.connect(self.cargar_desde_archivo)
        archivo_menu.addAction(abrir_action)

        # Opción para recargar desde URL
        recargar_action = QAction("Diccionario por defecto", self)
        recargar_action.triggered.connect(self.recargar_desde_url)
        archivo_menu.addAction(recargar_action)

        # Opción para abrir la terminal
        terminal_action = QAction("Abrir Terminal", self)
        terminal_action.triggered.connect(self.abrir_terminal)
        archivo_menu.addAction(terminal_action)

        # Opción para salir de la aplicación
        salir_action = QAction("Salir", self)
        salir_action.triggered.connect(self.close)
        archivo_menu.addAction(salir_action)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()

    def abrir_terminal(self):
        try:
            # Comando para abrir la terminal predeterminada en Ubuntu
            subprocess.Popen(["gnome-terminal"])
        except Exception as e:
            # Manejar cualquier excepción que pueda ocurrir al intentar abrir la terminal
            print(f"No se pudo abrir la terminal: {e}")
 

def abrir_ventana_diccionario(contenido_html):
    
    """
    Función para abrir una ventana de visualización del diccionario.

    Parameters:
        contenido_html (str): Contenido HTML a mostrar en la ventana del diccionario.
    """
    
    app = QApplication.instance()
    propio = app is None
    if propio:
        app = QApplication(sys.argv)
    ventana = VentanaDiccionario(contenido_html)
    abrir_ventana_diccionario._ventana = ventana
    ventana.show()
    ventana.raise_()
    ventana.activateWindow()
    if propio:
        ventana.closed.connect(app.quit)
        app.exec_()
        abrir_ventana_diccionario._ventana = None

def cargar_contenido_html():
    
    """
    Carga el contenido HTML del diccionario desde una URL.

    Returns:
        str: Contenido HTML del diccionario.
    """
    
    contenido_md = requests.get(url).text
    contenido_html = markdown2.markdown(contenido_md)
    return contenido_html

