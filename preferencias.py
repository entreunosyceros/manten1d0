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
from tkinter import font as tkfont
from tkinter import ttk
from tkinter import messagebox
from tooltip import ToolTip


# Variable global para almacenar el tema seleccionado

tema_seleccionado = "Claro"  # Tema predeterminado

_COLORES_CLARO = {
    "bg": "#f6f5f4",
    "fg": "#5e5c64",
    "base": "#f6f5f4",
    "text": "#5e5c64",
    "select": "#3584e4",
    "select_fg": "#ffffff",
    "sidebar": "#f0efed",
    "sidebar_activa": "#e4ebf5",
    "borde": "#dcdad5",
    "hover": "#d9e5f5",
}
_familia_ui = None
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


def color_barra():
    return colores_de(tema_seleccionado).get("sidebar", color_fondo())


def color_barra_activa():
    return colores_de(tema_seleccionado).get("sidebar_activa", color_campo())


def color_borde():
    return colores_de(tema_seleccionado).get("borde", color_barra())


def color_hover():
    return colores_de(tema_seleccionado).get("hover", color_barra_activa())


def aplicar_hover(boton, fondo_normal=None, fondo_hover=None):
    """Resalta el botón al pasar el ratón. No toca botones de aviso (rojo, verde, etc.)."""
    try:
        if str(boton.cget("bg")).lower() in _FONDOS_ESTADO:
            return boton
    except tk.TclError:
        return boton

    if fondo_normal is not None:
        boton._hover_fondo = fondo_normal
    elif not hasattr(boton, "_hover_fondo"):
        boton._hover_fondo = None
    if fondo_hover is not None:
        boton._hover_sobre = fondo_hover
    elif not hasattr(boton, "_hover_sobre"):
        boton._hover_sobre = None

    if getattr(boton, "_hover_aplicado", False):
        return boton

    boton._hover_aplicado = True
    boton._hover_dentro = False
    boton._hover_antes = None

    def _fondo_reposo():
        if getattr(boton, "_nav_activa", False):
            return color_barra_activa()
        if boton._hover_fondo is not None:
            return boton._hover_fondo
        if getattr(boton, "_zona", None) == "barra":
            return color_barra()
        return color_campo()

    def _fondo_sobre():
        if boton._hover_sobre is not None:
            return boton._hover_sobre
        return color_hover()

    def al_entrar(_evento=None):
        try:
            if getattr(boton, "_hover_dentro", False):
                return
            actual = str(boton.cget("bg")).lower()
            if actual in _FONDOS_ESTADO:
                return
            boton._hover_dentro = True
            boton._hover_antes = actual
            color = _fondo_sobre()
            boton.configure(bg=color, activebackground=color)
        except tk.TclError:
            boton._hover_dentro = False

    def al_salir(_evento=None):
        try:
            if not getattr(boton, "_hover_dentro", False):
                return
            boton._hover_dentro = False
            actual = str(boton.cget("bg")).lower()
            if actual in _FONDOS_ESTADO:
                return
            color = boton._hover_antes or _fondo_reposo()
            boton._hover_antes = None
            boton.configure(bg=color, activebackground=color)
        except tk.TclError:
            boton._hover_dentro = False

    boton.bind("<Enter>", al_entrar, add="+")
    boton.bind("<Leave>", al_salir, add="+")
    boton._hover_entrar = al_entrar
    boton._hover_salir = al_salir
    return boton


def fuente_ui(tamano=11, peso="normal"):
    """Ubuntu si está instalada; si no, la tipografía que ya usaba la interfaz."""
    global _familia_ui
    if _familia_ui is None:
        try:
            familias = set(tkfont.families())
        except tk.TclError:
            familias = set()
        _familia_ui = "Ubuntu" if "Ubuntu" in familias else "Arial"
    if peso == "bold":
        return (_familia_ui, tamano, "bold")
    return (_familia_ui, tamano)


def _mezclar(hex_a, hex_b, peso_a=0.7):
    """Acerca dos colores para que no haya saltos bruscos."""
    try:
        a = hex_a.lstrip("#")
        b = hex_b.lstrip("#")
        if len(a) != 6 or len(b) != 6:
            return hex_a
        ra, ga, ba = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
        rb, gb, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
        peso_b = 1.0 - peso_a
        return "#{:02x}{:02x}{:02x}".format(
            int(ra * peso_a + rb * peso_b),
            int(ga * peso_a + gb * peso_b),
            int(ba * peso_a + bb * peso_b),
        )
    except ValueError:
        return hex_a


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
            "bg": "#383838",
            "fg": "#deddda",
            "base": "#404040",
            "text": "#deddda",
            "select": "#E95420",
            "select_fg": "#FFFFFF",
            "sidebar": "#333333",
            "sidebar_activa": "#454545",
            "borde": "#4a4a4a",
            "hover": "#555555",
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
    fondo = encontrados.get("bg_color", "#383838")
    frente = encontrados.get("fg_color", "#deddda")
    campo = encontrados.get("base_color", fondo)
    # Acerca barra y contenido al color de fondo para que no haya un corte duro.
    frente_suave = _mezclar(frente, fondo, 0.82)
    return {
        "bg": fondo,
        "fg": frente_suave,
        "base": _mezclar(campo, fondo, 0.55),
        "text": frente_suave,
        "select": encontrados.get("selected_bg_color", "#E95420"),
        "select_fg": encontrados.get("selected_fg_color", "#FFFFFF"),
        "sidebar": _mezclar(fondo, "#000000", 0.92),
        "sidebar_activa": _mezclar(campo, fondo, 0.45),
        "borde": _mezclar(campo, fondo, 0.35),
        # Gris un poco más claro que el botón, para leer el texto claro.
        "hover": _mezclar("#ffffff", fondo, 0.28),
    }


def _estilo_ttk(colores):
    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
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
    estilo.configure("TLabelframe", background=fondo, foreground=frente)
    estilo.configure("TLabelframe.Label", background=fondo, foreground=frente)
    estilo.configure("Treeview", background=campo, fieldbackground=campo, foreground=texto)
    estilo.configure("Treeview.Heading", background=fondo, foreground=frente)
    estilo.map(
        "Treeview",
        background=[("selected", seleccionado)],
        foreground=[("selected", seleccionado_fg)],
    )
    estilo.configure("Horizontal.TProgressbar", background=seleccionado, troughcolor=campo)
    estilo.configure("Vertical.TProgressbar", background=seleccionado, troughcolor=campo)


def _es_tipo(widget, *clases):
    """isinstance seguro: evita TypeError si alguna clase no es un type real."""
    validos = tuple(c for c in clases if isinstance(c, type))
    if not validos:
        return False
    try:
        return isinstance(widget, validos)
    except TypeError:
        return False


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
        try:
            hijos = list(widget.winfo_children())
        except tk.TclError:
            return
        for child in hijos:
            try:
                _pintar_hijo(child)
            except (tk.TclError, TypeError):
                continue

    def _pintar_hijo(child):
        # ttk: solo recorrer hijos (el estilo lo pone Style)
        widget_ttk = getattr(ttk, "Widget", None)
        if widget_ttk is not None and _es_tipo(child, widget_ttk):
            pintar(child)
            return
        if _es_tipo(child, tk.Label):
            actual = str(child.cget("bg")).lower()
            if actual not in _FONDOS_ESTADO:
                if getattr(child, "_zona", None) == "barra":
                    child.config(
                        background=colores.get("sidebar", fondo),
                        foreground=frente,
                    )
                else:
                    child.config(background=fondo, foreground=frente)
        elif _es_tipo(child, tk.Button) and getattr(child, "_zona", None) == "barra":
            activa = getattr(child, "_nav_activa", False)
            fondo_btn = colores.get("sidebar_activa" if activa else "sidebar", fondo)
            child.config(
                background=fondo_btn,
                foreground=frente,
                activebackground=fondo_btn,
                activeforeground=frente,
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                font=fuente_ui(11, "bold" if activa else "normal"),
            )
            if getattr(child, "_hover_aplicado", False):
                child._hover_fondo = colores.get("sidebar", fondo)
                child._hover_sobre = None
                child._hover_dentro = False
                child._hover_antes = None
        elif _es_tipo(child, tk.Button, tk.Menubutton):
            actual = str(child.cget("bg")).lower()
            if actual in _FONDOS_ESTADO:
                pintar(child)
                return
            child.config(
                background=fondo,
                foreground=frente,
                activebackground=fondo,
                activeforeground=frente,
            )
            if getattr(child, "_hover_aplicado", False):
                child._hover_fondo = campo
                child._hover_sobre = None
                child._hover_dentro = False
                child._hover_antes = None
        elif _es_tipo(child, tk.Checkbutton, tk.Radiobutton):
            child.config(
                background=fondo,
                foreground=frente,
                activebackground=fondo,
                activeforeground=frente,
                selectcolor=campo,
            )
        elif _es_tipo(child, tk.Listbox):
            child.config(
                background=campo,
                foreground=texto,
                selectbackground=seleccionado,
                selectforeground=seleccionado_fg,
            )
        elif _es_tipo(child, tk.Entry, tk.Text, tk.Spinbox):
            child.config(
                background=campo,
                foreground=texto,
                insertbackground=texto,
                selectbackground=seleccionado,
                selectforeground=seleccionado_fg,
            )
        elif _es_tipo(child, tk.Menu):
            child.config(background=fondo, foreground=frente)
        elif _es_tipo(child, tk.Canvas):
            child.config(background=fondo)
            for item in child.find_all():
                if child.type(item) == "line":
                    child.itemconfig(item, fill=frente)
        elif _es_tipo(child, tk.Frame, tk.LabelFrame, tk.Toplevel, tk.Tk):
            if getattr(child, "_zona", None) == "barra":
                child.config(background=colores.get("sidebar", fondo))
            else:
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

