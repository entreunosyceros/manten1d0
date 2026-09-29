"""
Funciones y utilidades para la personalización de la interfaz gráfica de usuario.

Este módulo proporciona funciones y herramientas para cambiar el tema de la interfaz gráfica de usuario (GUI) de tkinter, así como para abrir una ventana de configuración para ajustar diferentes aspectos de la apariencia de la GUI.

Attributos:
    tema_seleccionado (str): Tema actualmente seleccionado para la GUI, que puede ser "Claro" o "Oscuro".
    ventanas_secundarias (list): Lista global para almacenar todas las ventanas secundarias abiertas.

Funciones:
    cambiar_tema(ventana, tema_seleccionado): Cambia el tema de la ventana y todos sus elementos hijos.
    abrir_ventana_configuracion(root): Abre una ventana de configuración para ajustar diferentes aspectos de la apariencia de la GUI. 
""" 

import os
import re
import subprocess
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tooltip import ToolTip


# Variable global para almacenar el tema seleccionado

tema_seleccionado = "Claro"  # Tema predeterminado

_COLORES_CLARO = {
    "bg": "lightgrey",
    "fg": "black",
    "base": "white",
    "text": "black",
    "select": "#3584e4",
    "select_fg": "white",
}
_cache_oscuro = None
_FONDOS_ESTADO = {
    "green", "red",
    "#c0392b", "#e67e22", "#1e8449", "#2471a3",
}


def invalidar_colores_sistema():
    global _cache_oscuro
    _cache_oscuro = None


def colores_de(tema):
    """Colores del tema. Oscuro usa la paleta del tema GTK oscuro del sistema."""
    if tema == "Claro":
        return _COLORES_CLARO
    global _cache_oscuro
    if _cache_oscuro is None:
        _cache_oscuro = _colores_oscuros_sistema()
    return _cache_oscuro


def color_fondo():
    return colores_de(tema_seleccionado)["bg"]


def color_texto():
    return colores_de(tema_seleccionado)["fg"]


def color_campo():
    return colores_de(tema_seleccionado)["base"]


def _gsettings(clave):
    try:
        proceso = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", clave],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proceso.stdout.strip().strip("'\"")


def _tema_gtk_oscuro():
    nombre = _gsettings("gtk-theme")
    if not nombre:
        nombre = _tema_en_settings_ini()
    if not nombre:
        nombre = "Yaru-dark"
    if "dark" not in nombre.lower() and _gsettings("color-scheme") == "prefer-dark":
        candidato = f"{nombre}-dark"
        if _ruta_tema(candidato):
            nombre = candidato
    return nombre


def _tema_en_settings_ini():
    ruta = os.path.expanduser("~/.config/gtk-3.0/settings.ini")
    if not os.path.isfile(ruta):
        return ""
    try:
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            for linea in archivo:
                if linea.strip().startswith("gtk-theme-name"):
                    return linea.split("=", 1)[1].strip()
    except OSError:
        return ""
    return ""


def _ruta_tema(nombre):
    for base in (
        os.path.expanduser("~/.themes"),
        os.path.expanduser("~/.local/share/themes"),
        "/usr/share/themes",
    ):
        ruta = os.path.join(base, nombre, "gtk-2.0", "gtkrc")
        if os.path.isfile(ruta):
            return ruta
    return ""


def _colores_oscuros_sistema():
    ruta = _ruta_tema(_tema_gtk_oscuro()) or _ruta_tema("Yaru-dark") or _ruta_tema("Adwaita-dark")
    if not ruta:
        return {
            "bg": "#353535",
            "fg": "#F7F7F7",
            "base": "#3d3d3d",
            "text": "#F7F7F7",
            "select": "#E95420",
            "select_fg": "#FFFFFF",
        }
    try:
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            texto = archivo.read().replace("\\n", "\n")
    except OSError:
        texto = ""
    encontrados = {}
    for clave, valor in re.findall(
        r"(text_color|base_color|fg_color|bg_color|selected_fg_color|selected_bg_color)\s*:\s*(#[0-9A-Fa-f]{3,8})",
        texto,
    ):
        encontrados[clave] = valor
    fondo = encontrados.get("bg_color", "#353535")
    frente = encontrados.get("fg_color", "#F7F7F7")
    return {
        "bg": fondo,
        "fg": frente,
        "base": encontrados.get("base_color", fondo),
        "text": encontrados.get("text_color", frente),
        "select": encontrados.get("selected_bg_color", "#E95420"),
        "select_fg": encontrados.get("selected_fg_color", "#FFFFFF"),
    }


def _estilo_ttk(colores):
    estilo = ttk.Style()
    fondo = colores["bg"]
    frente = colores["fg"]
    campo = colores["base"]
    texto = colores["text"]
    seleccionado = colores["select"]
    seleccionado_fg = colores["select_fg"]
    estilo.configure("TFrame", background=fondo)
    estilo.configure("TLabel", background=fondo, foreground=frente)
    estilo.configure("TButton", background=fondo, foreground=frente)
    estilo.configure("TCheckbutton", background=fondo, foreground=frente)
    estilo.configure("TRadiobutton", background=fondo, foreground=frente)
    estilo.configure("TEntry", fieldbackground=campo, foreground=texto)
    estilo.configure("TSpinbox", fieldbackground=campo, foreground=texto)
    estilo.configure("TCombobox", fieldbackground=campo, foreground=texto)
    estilo.configure("Treeview", background=campo, fieldbackground=campo, foreground=texto)
    estilo.configure("Treeview.Heading", background=fondo, foreground=frente)
    estilo.map(
        "Treeview",
        background=[("selected", seleccionado)],
        foreground=[("selected", seleccionado_fg)],
    )
    estilo.configure("Horizontal.TProgressbar", background=seleccionado, troughcolor=campo)
    estilo.configure("Vertical.TProgressbar", background=seleccionado, troughcolor=campo)


def cambiar_tema(ventana, tema):
    """
    Cambia el tema de la ventana y todos sus elementos hijos.

    Args:
        ventana (tk.Tk or tk.Toplevel): Ventana a la que se aplicará el cambio de tema.
        tema (str): Tema seleccionado para aplicar a la ventana. Puede ser "Claro" o "Oscuro".
    """
    colores = colores_de(tema)
    fondo = colores["bg"]
    frente = colores["fg"]
    campo = colores["base"]
    texto = colores["text"]
    seleccionado = colores["select"]
    seleccionado_fg = colores["select_fg"]
    _estilo_ttk(colores)

    def pintar(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Widget):
                pintar(child)
                continue
            if isinstance(child, tk.Label):
                actual = str(child.cget("bg")).lower()
                if actual not in _FONDOS_ESTADO:
                    child.config(background=fondo, foreground=frente)
            elif isinstance(child, (tk.Button, tk.Menubutton)):
                child.config(
                    background=fondo,
                    foreground=frente,
                    activebackground=fondo,
                    activeforeground=frente,
                )
            elif isinstance(child, (tk.Checkbutton, tk.Radiobutton)):
                child.config(
                    background=fondo,
                    foreground=frente,
                    activebackground=fondo,
                    activeforeground=frente,
                    selectcolor=campo,
                )
            elif isinstance(child, tk.Listbox):
                child.config(
                    background=campo,
                    foreground=texto,
                    selectbackground=seleccionado,
                    selectforeground=seleccionado_fg,
                )
            elif isinstance(child, (tk.Entry, tk.Text, tk.Spinbox)):
                child.config(
                    background=campo,
                    foreground=texto,
                    insertbackground=texto,
                    selectbackground=seleccionado,
                    selectforeground=seleccionado_fg,
                )
            elif isinstance(child, tk.Menu):
                child.config(background=fondo, foreground=frente)
            elif isinstance(child, tk.Canvas):
                child.config(background=fondo)
                for item in child.find_all():
                    if child.type(item) == "line":
                        child.itemconfig(item, fill=frente)
            elif isinstance(child, (tk.Frame, tk.Toplevel, tk.Tk)):
                child.config(background=fondo)
            pintar(child)

    pintar(ventana)
    try:
        ventana.config(background=fondo)
    except tk.TclError:
        pass


# Definir una lista global para almacenar todas las ventanas secundarias
ventanas_secundarias = []

def abrir_ventana_configuracion(root):
    """
    Abre una ventana de configuración para ajustar diferentes aspectos de la apariencia de la GUI.

    Args:
        root (tk.Tk): Ventana principal a la que está asociada la ventana de configuración.
    """
    def actualizar_tamanio_texto():
        size = int(size_spinner.get())
        size_label.config(text=f"Tamaño del Texto: {size}")
        for widget in root.winfo_children():
            actualizar_fuente(widget, size)

    def actualizar_fuente(widget, size):
        try:
            actual_font = str(widget.cget("font"))
            new_font = (actual_font.split()[0], size)
            widget.config(font=new_font)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            actualizar_fuente(child, size)

    def aplicar_cambios():
        global tema_seleccionado 
        nuevo_tema = tema_selector.get()  # Actualizar el tema seleccionado

        if nuevo_tema:
            invalidar_colores_sistema()
            # Aplicar el nuevo tema a la ventana principal y a las secundarias
            if root.winfo_exists():
                cambiar_tema(root, nuevo_tema)
            for ventana in ventanas_secundarias:
                if ventana.winfo_exists():
                    cambiar_tema(ventana, nuevo_tema)
            # Actualizar tema_seleccionado solo si se selecciona un nuevo tema
            tema_seleccionado = nuevo_tema
        else:
            messagebox.showwarning("Advertencia", "Debes seleccionar un tema antes de aplicar los cambios.")
        config_window.destroy()


    # Crear una nueva ventana para la configuración
    config_window = tk.Toplevel(root)
    config_window.title("Configuración")
    config_window.geometry("300x150")  # Tamaño personalizado
    config_window.resizable(False, False)
    # Agregar controles para la personalización
    size_frame = tk.Frame(config_window)  # Crear un marco para contener size_label y size_spinner
    size_frame.pack(pady=5)

    size_label = tk.Label(size_frame, text="Tamaño del Texto: 12", pady=10)
    size_label.pack(side="left", padx=10)

    size_spinner = tk.Spinbox(size_frame, from_=12, to=24, width=5, command=actualizar_tamanio_texto)
    size_spinner.pack(side="left", padx=10)

    # Resto de los elementos
    tema_selector = ttk.Combobox(config_window, values=["Claro", "Oscuro"], state="readonly")
    tema_selector.pack()

    apply_button = tk.Button(config_window, text="Aplicar", command=aplicar_cambios)
    apply_button.pack()
    ToolTip(apply_button, "Aplicar todos los cambios realizados")

    # Agregar una función de devolución de llamada para eliminar la ventana de la lista cuando se cierra
    def on_cerrar_ventana():
        ventanas_secundarias.remove(config_window)
        config_window.destroy()

    config_window.protocol("WM_DELETE_WINDOW", on_cerrar_ventana)

    # Agregar la ventana configuración a la lista de ventanas secundarias
    ventanas_secundarias.append(config_window)

