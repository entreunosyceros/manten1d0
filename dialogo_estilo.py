"""Estilo comun para dialogos llamativos de arranque (contraseña, dependencias...)."""

import tkinter as tk

BG = "#f4f6f7"
FRANJA = "#1a5276"
FRANJA_OK = "#1e8449"
FRANJA_AVISO = "#b9770e"
FRANJA_ERROR = "#922b21"
TEXTO = "#2c3e50"
TITULO = "#1a5276"
BOTON_BG = "#1a5276"
BOTON_BG_ACTIVO = "#2874a6"


def centrar_ventana(ventana, ancho, alto):
    ventana.update_idletasks()
    pantalla_w = ventana.winfo_screenwidth()
    pantalla_h = ventana.winfo_screenheight()
    x = max(0, (pantalla_w - ancho) // 2)
    y = max(0, (pantalla_h - alto) // 3)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def preparar_dialogo(
    ventana,
    titulo_ventana,
    titulo_franja,
    ancho,
    alto,
    color_franja=None,
    topmost=False,
):
    """Aplica el marco visual y devuelve el frame del cuerpo."""
    color = color_franja or FRANJA
    ventana.title(titulo_ventana)
    ventana.resizable(False, False)
    ventana.configure(bg=BG)
    centrar_ventana(ventana, ancho, alto)
    if topmost:
        try:
            ventana.attributes("-topmost", True)
        except tk.TclError:
            pass
    try:
        ventana.lift()
        ventana.focus_force()
    except tk.TclError:
        pass

    franja = tk.Frame(ventana, bg=color, height=56)
    franja.pack(fill=tk.X)
    franja.pack_propagate(False)
    tk.Label(
        franja,
        text=titulo_franja,
        bg=color,
        fg="white",
        font=("Arial", 14, "bold"),
    ).pack(pady=14)

    cuerpo = tk.Frame(ventana, bg=BG, padx=24, pady=16)
    cuerpo.pack(fill=tk.BOTH, expand=True)
    return cuerpo


def etiqueta_titulo(parent, texto, wraplength=400):
    return tk.Label(
        parent,
        text=texto,
        bg=BG,
        fg=TITULO,
        font=("Arial", 12, "bold"),
        wraplength=wraplength,
        justify=tk.LEFT,
    )


def etiqueta_texto(parent, texto, wraplength=400):
    return tk.Label(
        parent,
        text=texto,
        bg=BG,
        fg=TEXTO,
        font=("Arial", 10),
        wraplength=wraplength,
        justify=tk.LEFT,
    )


def boton_primario(parent, texto, comando, width=14):
    return tk.Button(
        parent,
        text=texto,
        command=comando,
        width=width,
        font=("Arial", 11, "bold"),
        bg=BOTON_BG,
        fg="white",
        activebackground=BOTON_BG_ACTIVO,
        activeforeground="white",
        relief=tk.RAISED,
        borderwidth=2,
    )


def boton_secundario(parent, texto, comando, width=12):
    return tk.Button(parent, text=texto, command=comando, width=width)


def dialogo_mensaje(
    parent,
    titulo_ventana,
    titulo_franja,
    titulo,
    mensaje,
    botones=None,
    color_franja=None,
    ancho=460,
    alto=280,
):
    """Dialogo modal al estilo Manten1d0. Devuelve el valor del boton pulsado."""
    if botones is None:
        botones = (("Continuar", True),)

    propio = False
    if parent is None:
        parent = getattr(tk, "_default_root", None)
    if parent is None:
        parent = tk.Tk()
        parent.withdraw()
        propio = True

    resultado = {"valor": None}
    win = tk.Toplevel(parent)
    cuerpo = preparar_dialogo(
        win,
        titulo_ventana,
        titulo_franja,
        ancho,
        alto,
        color_franja=color_franja,
        topmost=True,
    )
    win.transient(parent)

    etiqueta_titulo(cuerpo, titulo).pack(anchor="w")
    etiqueta_texto(cuerpo, mensaje).pack(anchor="w", pady=(8, 12))

    fila = tk.Frame(cuerpo, bg=BG)
    fila.pack(anchor="w", pady=(8, 0))

    def elegir(valor):
        resultado["valor"] = valor
        win.destroy()

    for i, (texto, valor) in enumerate(botones):
        if i == 0:
            btn = boton_primario(fila, texto, lambda v=valor: elegir(v), width=max(12, len(texto) + 2))
        else:
            btn = boton_secundario(fila, texto, lambda v=valor: elegir(v), width=max(12, len(texto) + 2))
        btn.pack(side=tk.LEFT, padx=(0, 8))

    win.protocol("WM_DELETE_WINDOW", lambda: elegir(botones[-1][1] if botones else None))
    try:
        win.grab_set()
    except tk.TclError:
        pass
    parent.wait_window(win)

    if propio:
        try:
            parent.destroy()
        except tk.TclError:
            pass
    return resultado["valor"]
