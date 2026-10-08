# CATEGORÍA DICCIONARIO
import json
import os
import subprocess
import sys

import markdown2
import requests
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QAction,
)

url = "https://raw.githubusercontent.com/sapoclay/diccionario/main/diccionario.md"

RUTA_DATOS = os.path.join(os.path.expanduser("~"), ".local", "share", "Manten1d0")
RUTA_CONCEPTOS = os.path.join(RUTA_DATOS, "diccionario_usuario.json")


def _asegurar_carpeta():
    os.makedirs(RUTA_DATOS, exist_ok=True)


def leer_conceptos_usuario():
    """Lista de dicts {termino, definicion} del diccionario personal."""
    if not os.path.exists(RUTA_CONCEPTOS):
        return []
    try:
        with open(RUTA_CONCEPTOS, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, list):
            return []
        limpios = []
        for item in datos:
            if not isinstance(item, dict):
                continue
            termino = str(item.get("termino", "")).strip()
            definicion = str(item.get("definicion", "")).strip()
            if termino and definicion:
                limpios.append({"termino": termino, "definicion": definicion})
        return limpios
    except (OSError, json.JSONDecodeError):
        return []


def guardar_conceptos_usuario(conceptos):
    _asegurar_carpeta()
    with open(RUTA_CONCEPTOS, "w", encoding="utf-8") as archivo:
        json.dump(conceptos, archivo, ensure_ascii=False, indent=2)


def anadir_concepto_usuario(termino, definicion):
    termino = (termino or "").strip()
    definicion = (definicion or "").strip()
    if not termino or not definicion:
        raise ValueError("El término y la definición no pueden estar vacíos.")
    conceptos = leer_conceptos_usuario()
    for item in conceptos:
        if item["termino"].lower() == termino.lower():
            item["definicion"] = definicion
            guardar_conceptos_usuario(conceptos)
            return "actualizado"
    conceptos.append({"termino": termino, "definicion": definicion})
    conceptos.sort(key=lambda c: c["termino"].lower())
    guardar_conceptos_usuario(conceptos)
    return "añadido"


def eliminar_concepto_usuario(termino):
    termino = (termino or "").strip().lower()
    conceptos = [c for c in leer_conceptos_usuario() if c["termino"].lower() != termino]
    guardar_conceptos_usuario(conceptos)


def markdown_conceptos_usuario():
    conceptos = leer_conceptos_usuario()
    if not conceptos:
        return ""
    lineas = [
        "",
        "---",
        "",
        "## Mis conceptos",
        "",
        "Conceptos añadidos por ti en Manten1d0. Se guardan solo en este equipo.",
        "",
    ]
    for item in conceptos:
        lineas.append(f"### {item['termino']}")
        lineas.append("")
        lineas.append(item["definicion"])
        lineas.append("")
    return "\n".join(lineas)


def fusionar_markdown(contenido_md):
    base = (contenido_md or "").rstrip()
    extra = markdown_conceptos_usuario()
    if not extra:
        return base
    if not base:
        return extra.lstrip()
    return base + "\n" + extra


_MD_EXTRAS = ["fenced-code-blocks", "tables", "strike", "break-on-newline", "cuddled-lists"]


def render_markdown(fragmento_md):
    """Convierte un fragmento Markdown a HTML (definiciones de conceptos)."""
    return markdown2.markdown(fragmento_md or "", extras=_MD_EXTRAS)


def _html_a_texto_plano(html):
    """Aproxima HTML a texto para la vista previa en Tk (sin motor HTML)."""
    import html as html_mod
    import re

    texto = html or ""
    texto = re.sub(r"(?i)<br\s*/?>", "\n", texto)
    texto = re.sub(r"(?i)</p\s*>", "\n\n", texto)
    texto = re.sub(r"(?i)</(h[1-6]|li|tr|div)\s*>", "\n", texto)
    texto = re.sub(r"(?i)<li[^>]*>", "- ", texto)
    texto = re.sub(r"(?i)<[^>]+>", "", texto)
    return html_mod.unescape(texto).strip()


def markdown_a_html(contenido_md):
    return markdown2.markdown(fusionar_markdown(contenido_md), extras=_MD_EXTRAS)


class DialogoConcepto(QDialog):
    def __init__(self, parent=None, termino="", definicion=""):
        super().__init__(parent)
        self.setWindowTitle("Añadir concepto al diccionario")
        self.resize(560, 480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.entrada_termino = QLineEdit(termino)
        self.entrada_termino.setPlaceholderText("Ej.: rsync, ufw, journalctl...")
        form.addRow("Término:", self.entrada_termino)
        layout.addLayout(form)

        layout.addWidget(
            QLabel(
                "Definición (Markdown): **negrita**, *cursiva*, `código`, listas, "
                "enlaces [texto](url), bloques ```..."
            )
        )
        self.entrada_definicion = QTextEdit()
        self.entrada_definicion.setPlainText(definicion)
        self.entrada_definicion.setPlaceholderText(
            "Ejemplo:\n\n"
            "Reinicia la red:\n\n"
            "```bash\nsudo systemctl restart NetworkManager\n```\n\n"
            "- Útil tras cambiar el DNS\n"
            "- Ver también **nmcli**"
        )
        self.entrada_definicion.setMinimumHeight(140)
        layout.addWidget(self.entrada_definicion)

        layout.addWidget(QLabel("Vista previa:"))
        self.vista_previa = QTextBrowser()
        self.vista_previa.setOpenExternalLinks(True)
        self.vista_previa.setMinimumHeight(120)
        layout.addWidget(self.vista_previa)
        self.entrada_definicion.textChanged.connect(self._actualizar_previa)
        self._actualizar_previa()

        botones = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_cancelar = QPushButton("Cancelar")
        btn_guardar.clicked.connect(self.accept)
        btn_cancelar.clicked.connect(self.reject)
        botones.addStretch(1)
        botones.addWidget(btn_guardar)
        botones.addWidget(btn_cancelar)
        layout.addLayout(botones)

    def _actualizar_previa(self):
        self.vista_previa.setHtml(render_markdown(self.entrada_definicion.toPlainText()))

    def datos(self):
        return self.entrada_termino.text().strip(), self.entrada_definicion.toPlainText().strip()


class DialogoGestionConceptos(QDialog):
    def __init__(self, parent=None, al_cambiar=None):
        super().__init__(parent)
        self.setWindowTitle("Mis conceptos")
        self.resize(520, 380)
        self._al_cambiar = al_cambiar
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Conceptos personales (se muestran al final del diccionario):")
        )
        self.lista = QListWidget()
        layout.addWidget(self.lista)
        botones = QHBoxLayout()
        btn_anadir = QPushButton("Añadir")
        btn_editar = QPushButton("Editar")
        btn_borrar = QPushButton("Eliminar")
        btn_cerrar = QPushButton("Cerrar")
        btn_anadir.clicked.connect(self._anadir)
        btn_editar.clicked.connect(self._editar)
        btn_borrar.clicked.connect(self._borrar)
        btn_cerrar.clicked.connect(self.accept)
        botones.addWidget(btn_anadir)
        botones.addWidget(btn_editar)
        botones.addWidget(btn_borrar)
        botones.addStretch(1)
        botones.addWidget(btn_cerrar)
        layout.addLayout(botones)
        self._rellenar()

    def _rellenar(self):
        self.lista.clear()
        for item in leer_conceptos_usuario():
            self.lista.addItem(item["termino"])

    def _concepto_seleccionado(self):
        fila = self.lista.currentRow()
        conceptos = leer_conceptos_usuario()
        if fila < 0 or fila >= len(conceptos):
            return None
        return conceptos[fila]

    def _avisar_cambio(self):
        if self._al_cambiar:
            self._al_cambiar()

    def _anadir(self):
        dialogo = DialogoConcepto(self)
        if dialogo.exec_() != QDialog.Accepted:
            return
        termino, definicion = dialogo.datos()
        try:
            anadir_concepto_usuario(termino, definicion)
        except ValueError as error:
            QMessageBox.warning(self, "Concepto", str(error))
            return
        self._rellenar()
        self._avisar_cambio()

    def _editar(self):
        actual = self._concepto_seleccionado()
        if not actual:
            QMessageBox.information(self, "Concepto", "Selecciona un concepto de la lista.")
            return
        dialogo = DialogoConcepto(self, actual["termino"], actual["definicion"])
        if dialogo.exec_() != QDialog.Accepted:
            return
        termino, definicion = dialogo.datos()
        try:
            # Si cambia el nombre, quitar el anterior
            if termino.lower() != actual["termino"].lower():
                eliminar_concepto_usuario(actual["termino"])
            anadir_concepto_usuario(termino, definicion)
        except ValueError as error:
            QMessageBox.warning(self, "Concepto", str(error))
            return
        self._rellenar()
        self._avisar_cambio()

    def _borrar(self):
        actual = self._concepto_seleccionado()
        if not actual:
            QMessageBox.information(self, "Concepto", "Selecciona un concepto de la lista.")
            return
        if (
            QMessageBox.question(
                self,
                "Eliminar concepto",
                f"¿Eliminar «{actual['termino']}»?",
            )
            != QMessageBox.Yes
        ):
            return
        eliminar_concepto_usuario(actual["termino"])
        self._rellenar()
        self._avisar_cambio()


class VentanaDiccionario(QMainWindow):
    """Ventana de consulta del diccionario GNU/Linux (remoto + conceptos del usuario)."""

    closed = pyqtSignal()

    def __init__(self, contenido_html, contenido_md_base=""):
        super().__init__()
        self.setWindowTitle("Diccionario")
        self.resize(800, 600)
        self.contenido_md_base = contenido_md_base or ""
        self.contenido_html_original = contenido_html
        self.cargar_contenido(contenido_html)
        self.crear_menu()

    def cargar_contenido(self, contenido_html):
        self.contenido_html_original = contenido_html
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

    def _refrescar_desde_base(self):
        html = markdown_a_html(self.contenido_md_base)
        busqueda = self.search_input.text() if hasattr(self, "search_input") else ""
        self.cargar_contenido(html)
        if busqueda:
            self.search_input.setText(busqueda)
            self.buscar()

    def buscar(self):
        search_term = self.search_input.text().lower().strip()
        if search_term:
            self.browser.setHtml(self.filter_html(search_term))
        else:
            self.browser.setHtml(self.contenido_html_original)

    def filter_html(self, search_term):
        # Siempre filtrar desde el original (no desde un resultado ya filtrado)
        filtered_html = ""
        for line in self.contenido_html_original.split("\n"):
            if search_term in line.lower():
                filtered_html += line + "\n"
        return filtered_html or "<p><em>Sin coincidencias.</em></p>"

    def cargar_desde_archivo(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", "", "Archivos Markdown (*.md)"
        )
        if filename:
            with open(filename, "r", encoding="utf-8") as file:
                contenido_md = file.read()
            self.contenido_md_base = contenido_md
            self.cargar_contenido(markdown_a_html(contenido_md))

    def recargar_desde_url(self):
        try:
            contenido_md = requests.get(url, timeout=20).text
            self.contenido_md_base = contenido_md
            self.cargar_contenido(markdown_a_html(contenido_md))
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"No se pudo cargar el contenido desde la URL:\n\n{e}"
            )

    def _anadir_concepto(self):
        dialogo = DialogoConcepto(self)
        if dialogo.exec_() != QDialog.Accepted:
            return
        termino, definicion = dialogo.datos()
        try:
            estado = anadir_concepto_usuario(termino, definicion)
        except ValueError as error:
            QMessageBox.warning(self, "Concepto", str(error))
            return
        self._refrescar_desde_base()
        QMessageBox.information(
            self,
            "Concepto",
            f"Concepto «{termino}» {'actualizado' if estado == 'actualizado' else 'añadido'}.",
        )

    def _gestionar_conceptos(self):
        DialogoGestionConceptos(self, al_cambiar=self._refrescar_desde_base).exec_()

    def crear_menu(self):
        menu_bar = self.menuBar()
        archivo_menu = menu_bar.addMenu("Archivo")

        abrir_action = QAction("Abrir archivo", self)
        abrir_action.triggered.connect(self.cargar_desde_archivo)
        archivo_menu.addAction(abrir_action)

        recargar_action = QAction("Diccionario por defecto", self)
        recargar_action.triggered.connect(self.recargar_desde_url)
        archivo_menu.addAction(recargar_action)

        archivo_menu.addSeparator()

        anadir_action = QAction("Añadir concepto...", self)
        anadir_action.triggered.connect(self._anadir_concepto)
        archivo_menu.addAction(anadir_action)

        gestionar_action = QAction("Mis conceptos...", self)
        gestionar_action.triggered.connect(self._gestionar_conceptos)
        archivo_menu.addAction(gestionar_action)

        archivo_menu.addSeparator()

        terminal_action = QAction("Abrir Terminal", self)
        terminal_action.triggered.connect(self.abrir_terminal)
        archivo_menu.addAction(terminal_action)

        salir_action = QAction("Salir", self)
        salir_action.triggered.connect(self.close)
        archivo_menu.addAction(salir_action)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()

    def abrir_terminal(self):
        try:
            subprocess.Popen(["gnome-terminal"])
        except Exception as e:
            print(f"No se pudo abrir la terminal: {e}")


def abrir_ventana_diccionario(contenido_html, contenido_md_base="", parent_tk=None):
    """
    Abre la ventana del diccionario (PyQt).

    parent_tk: ventana Tk principal. Al mezclar Tk+Qt, Tk suele quedar delante;
    se iconifica mientras el diccionario está abierto.
    """
    app = QApplication.instance()
    propio = app is None
    if propio:
        app = QApplication(sys.argv)

    ventana = VentanaDiccionario(contenido_html, contenido_md_base=contenido_md_base)
    abrir_ventana_diccionario._ventana = ventana

    # Forzar primer plano frente a la ventana Tk
    ventana.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    estado_tk = {"modo": None}
    if parent_tk is not None:
        try:
            estado_tk["modo"] = str(parent_tk.state())
            parent_tk.iconify()
        except Exception:
            try:
                parent_tk.withdraw()
                estado_tk["modo"] = "withdrawn"
            except Exception:
                estado_tk["modo"] = None

    def restaurar_tk():
        if parent_tk is None:
            return
        try:
            parent_tk.deiconify()
            parent_tk.lift()
            parent_tk.focus_force()
        except Exception:
            pass

    def al_cerrar():
        restaurar_tk()
        if propio:
            app.quit()

    ventana.closed.connect(al_cerrar)
    ventana.show()
    ventana.raise_()
    ventana.activateWindow()

    def quitar_topmost():
        # Tras ganar el foco, permitir cambiar a otras apps con normalidad
        if not ventana.isVisible():
            return
        ventana.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        ventana.show()
        ventana.raise_()
        ventana.activateWindow()

    QTimer.singleShot(500, quitar_topmost)

    if propio:
        app.exec_()
        abrir_ventana_diccionario._ventana = None
        restaurar_tk()
    else:
        # QApplication ya existía: bombear hasta que se cierre la ventana
        import time

        while ventana.isVisible():
            app.processEvents()
            if parent_tk is not None:
                try:
                    parent_tk.update_idletasks()
                except Exception:
                    pass
            time.sleep(0.02)
        abrir_ventana_diccionario._ventana = None
        restaurar_tk()


def cargar_contenido_html():
    """Carga el diccionario remoto + conceptos del usuario. Devuelve (html, md_base)."""
    contenido_md = requests.get(url, timeout=20).text
    return markdown_a_html(contenido_md), contenido_md


def _poner_delante(ventana, parent=None):
    """Asegura que un Toplevel quede delante de la ventana principal."""
    import tkinter as tk

    real = getattr(ventana, "_ventana_real", ventana)
    ancla = None
    if parent is not None:
        try:
            ancla = parent.winfo_toplevel()
        except tk.TclError:
            ancla = parent
    if ancla is not None:
        try:
            real.transient(ancla)
        except tk.TclError:
            pass
    try:
        real.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        real.lift()
        real.focus_force()
    except tk.TclError:
        pass
    try:
        real.grab_set()
    except tk.TclError:
        pass
    # topmost solo para ganar el foco; luego se quita para no tapar otros diálogos
    try:
        real.after(150, lambda: real.attributes("-topmost", False))
    except tk.TclError:
        pass
    return real


def gestionar_conceptos_tk(parent=None):
    """Diálogo Tk para añadir/editar/eliminar conceptos sin abrir PyQt."""
    import tkinter as tk
    from tkinter import messagebox, scrolledtext
    import preferencias

    colores = preferencias.colores_de(preferencias.tema_seleccionado)
    fondo = colores["bg"]
    frente = colores["fg"]

    # chrome=False: Toplevel real (el parche con franja devolvía el frame y
    # la ventana quedaba detrás de la principal).
    try:
        ventana = tk.Toplevel(parent, chrome=False) if parent else tk.Toplevel(chrome=False)
    except TypeError:
        ventana = tk.Toplevel(parent) if parent else tk.Toplevel()
    ventana.title("Mis conceptos del diccionario")
    ventana.geometry("560x420")
    ventana.minsize(480, 360)
    ventana.configure(bg=fondo)
    _poner_delante(ventana, parent)

    tk.Label(
        ventana,
        text="Conceptos personales (aparecen al final del diccionario)",
        bg=fondo,
        fg=frente,
        font=("Arial", 11, "bold"),
    ).pack(anchor="w", padx=12, pady=(12, 6))

    lista = tk.Listbox(ventana, exportselection=False, bg=colores["base"], fg=frente)
    lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

    def rellenar():
        lista.delete(0, tk.END)
        for item in leer_conceptos_usuario():
            lista.insert(tk.END, item["termino"])

    def seleccionado():
        sel = lista.curselection()
        if not sel:
            return None
        conceptos = leer_conceptos_usuario()
        if sel[0] >= len(conceptos):
            return None
        return conceptos[sel[0]]

    def dialogo_edicion(termino="", definicion=""):
        try:
            dlg = tk.Toplevel(ventana, chrome=False)
        except TypeError:
            dlg = tk.Toplevel(ventana)
        dlg.title("Concepto (Markdown)")
        dlg.geometry("560x520")
        dlg.minsize(480, 420)
        dlg.configure(bg=fondo)
        _poner_delante(dlg, ventana)
        resultado = {"ok": False, "termino": "", "definicion": ""}

        tk.Label(dlg, text="Término:", bg=fondo, fg=frente).pack(anchor="w", padx=10, pady=(10, 2))
        entrada = tk.Entry(dlg)
        entrada.insert(0, termino)
        entrada.pack(fill=tk.X, padx=10)

        tk.Label(
            dlg,
            text=(
                "Definición en Markdown: **negrita**, *cursiva*, `código`, "
                "listas, [enlaces](url), bloques ```..."
            ),
            bg=fondo,
            fg=frente,
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=10, pady=(8, 2))

        paneles = tk.PanedWindow(dlg, orient=tk.VERTICAL, bg=fondo, sashwidth=4)
        paneles.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        marco_edit = tk.Frame(paneles, bg=fondo)
        tk.Label(marco_edit, text="Editor:", bg=fondo, fg=frente).pack(anchor="w")
        texto = scrolledtext.ScrolledText(marco_edit, height=10, wrap=tk.WORD, font=("Consolas", 10))
        texto.insert("1.0", definicion)
        texto.pack(fill=tk.BOTH, expand=True)
        paneles.add(marco_edit, stretch="always")

        marco_prev = tk.Frame(paneles, bg=fondo)
        tk.Label(marco_prev, text="Vista previa:", bg=fondo, fg=frente).pack(anchor="w")
        previa = scrolledtext.ScrolledText(
            marco_prev, height=8, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 10)
        )
        previa.pack(fill=tk.BOTH, expand=True)
        paneles.add(marco_prev, stretch="always")

        def actualizar_previa(_event=None):
            md = texto.get("1.0", "end-1c")
            html = render_markdown(md)
            previa.configure(state=tk.NORMAL)
            previa.delete("1.0", tk.END)
            # Tk no renderiza HTML: mostramos una vista legible y el aviso
            previa.insert(tk.END, _html_a_texto_plano(html))
            previa.configure(state=tk.DISABLED)

        texto.bind("<KeyRelease>", actualizar_previa)
        texto.bind("<<Paste>>", lambda e: dlg.after(10, actualizar_previa))
        actualizar_previa()

        def guardar():
            resultado["termino"] = entrada.get().strip()
            resultado["definicion"] = texto.get("1.0", "end-1c").strip()
            resultado["ok"] = True
            dlg.destroy()

        marco = tk.Frame(dlg, bg=fondo)
        marco.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(marco, text="Guardar", command=guardar).pack(side=tk.RIGHT, padx=4)
        tk.Button(marco, text="Cancelar", command=dlg.destroy).pack(side=tk.RIGHT)
        entrada.focus_set()
        dlg.wait_window()
        # Recuperar el foco del diálogo padre
        _poner_delante(ventana, parent)
        return resultado

    def anadir():
        datos = dialogo_edicion()
        if not datos["ok"]:
            return
        try:
            anadir_concepto_usuario(datos["termino"], datos["definicion"])
        except ValueError as error:
            messagebox.showwarning("Concepto", str(error), parent=ventana)
            return
        rellenar()

    def editar():
        actual = seleccionado()
        if not actual:
            messagebox.showinfo("Concepto", "Selecciona un concepto.", parent=ventana)
            return
        datos = dialogo_edicion(actual["termino"], actual["definicion"])
        if not datos["ok"]:
            return
        try:
            if datos["termino"].lower() != actual["termino"].lower():
                eliminar_concepto_usuario(actual["termino"])
            anadir_concepto_usuario(datos["termino"], datos["definicion"])
        except ValueError as error:
            messagebox.showwarning("Concepto", str(error), parent=ventana)
            return
        rellenar()

    def borrar():
        actual = seleccionado()
        if not actual:
            messagebox.showinfo("Concepto", "Selecciona un concepto.", parent=ventana)
            return
        if not messagebox.askyesno(
            "Eliminar", f"¿Eliminar «{actual['termino']}»?", parent=ventana
        ):
            return
        eliminar_concepto_usuario(actual["termino"])
        rellenar()

    marco_btn = tk.Frame(ventana, bg=fondo)
    marco_btn.pack(fill=tk.X, padx=12, pady=(0, 12))
    tk.Button(marco_btn, text="Añadir", command=anadir).pack(side=tk.LEFT, padx=4)
    tk.Button(marco_btn, text="Editar", command=editar).pack(side=tk.LEFT, padx=4)
    tk.Button(marco_btn, text="Eliminar", command=borrar).pack(side=tk.LEFT, padx=4)
    tk.Button(marco_btn, text="Cerrar", command=ventana.destroy).pack(side=tk.RIGHT, padx=4)

    rellenar()
    return ventana
