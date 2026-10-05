"""Estilo comun para dialogos y ventanas secundarias (adapta claro/oscuro)."""

import tkinter as tk
import tkinter.messagebox as messagebox_mod

# Semanticos (igual en claro y oscuro)
FRANJA_OK = "#1e8449"
FRANJA_AVISO = "#b9770e"
FRANJA_ERROR = "#922b21"

_MESSAGEBOX_PARCHE = False


def paleta():
    """Colores del chrome segun el tema actual (Claro / Oscuro)."""
    try:
        import preferencias

        tema = preferencias.tema_seleccionado
        colores = preferencias.colores_de(tema)
    except Exception:
        tema = "Claro"
        colores = {
            "bg": "#f6f5f4",
            "fg": "#5e5c64",
            "select": "#3584e4",
        }

    if tema == "Oscuro":
        fondo = colores.get("bg", "#2c2c2c")
        frente = colores.get("fg", "#e6e6e6")
        hover = colores.get("hover", "#1a1a1a")
        return {
            "bg": fondo,
            "texto": frente,
            "titulo": frente,
            "franja": colores.get("sidebar_activa", hover),
            "franja_fg": "#ffffff",
            "boton": fondo,
            "boton_activo": hover,
            "campo": colores.get("base", fondo),
        }
    return {
        "bg": colores.get("bg", "#f6f5f4"),
        "texto": colores.get("fg", "#5e5c64"),
        "titulo": "#1a5276",
        "franja": "#1a5276",
        "franja_fg": "#ffffff",
        "boton": "#1a5276",
        "boton_activo": "#2874a6",
        "campo": colores.get("base", colores.get("bg", "#f6f5f4")),
    }


def __getattr__(name):
    """Compat: estilo.BG / FRANJA / etc. leen la paleta del tema actual."""
    p = paleta()
    mapa = {
        "BG": "bg",
        "TEXTO": "texto",
        "TITULO": "titulo",
        "FRANJA": "franja",
        "BOTON_BG": "boton",
        "BOTON_BG_ACTIVO": "boton_activo",
    }
    if name in mapa:
        return p[mapa[name]]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def centrar_ventana(ventana, ancho, alto):
    ventana.update_idletasks()
    pantalla_w = ventana.winfo_screenwidth()
    pantalla_h = ventana.winfo_screenheight()
    x = max(0, (pantalla_w - ancho) // 2)
    y = max(0, (pantalla_h - alto) // 3)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def _texto_franja(titulo):
    texto = (titulo or "").strip()
    if not texto:
        return "MANTEN1D0"
    bajo = texto.lower().replace(" ", "")
    # Titulo principal de la app
    if bajo in ("manten1-d0", "manten1d0", "manten1do"):
        return "MANTEN1D0"
    if bajo.startswith("manten1d0") or bajo.startswith("manten1-d0"):
        resto = texto.split("-", 1)
        if len(resto) > 1 and resto[1].strip().lower() not in ("d0", "do"):
            texto = resto[1].strip()
        else:
            return "MANTEN1D0"
    return texto.upper()[:64]


def _marcar_franja(widget):
    widget._zona = "franja_estilo"


def ventana_estilo_real(widget):
    """Toplevel real cuando el master es el frame de contenido del chrome."""
    return getattr(widget, "_ventana_real", widget)


def panel_contenido(ventana):
    """Frame bajo la franja para grid/pack de contenido; si no hay chrome, la propia ventana."""
    real = ventana_estilo_real(ventana)
    return getattr(real, "_contenedor_estilo", None) or real


def _actualizar_franja(ventana, titulo=None, color=None):
    ventana = ventana_estilo_real(ventana)
    lbl = getattr(ventana, "_lbl_franja_estilo", None)
    franja = getattr(ventana, "_franja_estilo", None)
    if franja is None or lbl is None:
        return
    p = paleta()
    color_final = color or getattr(ventana, "_color_franja_estilo", None) or p["franja"]
    try:
        franja.config(bg=color_final)
        lbl.config(bg=color_final, fg=p["franja_fg"])
    except tk.TclError:
        pass
    if titulo is not None:
        try:
            lbl.config(text=_texto_franja(titulo))
        except tk.TclError:
            pass


def refrescar_chrome_tema(ventana):
    """Reaplica colores de franja/fondo tras cambiar Claro/Oscuro."""
    real = ventana_estilo_real(ventana)
    if not getattr(real, "_chrome_manten", False) and not getattr(
        ventana, "_chrome_manten", False
    ):
        return
    p = paleta()
    color = getattr(real, "_color_franja_estilo", None) or p["franja"]
    contenedor = getattr(real, "_contenedor_estilo", ventana)
    try:
        real.configure(bg=p["bg"])
        if contenedor is not real:
            contenedor.configure(bg=p["bg"])
    except tk.TclError:
        pass
    _actualizar_franja(real, color=color)
    try:
        for hijo in contenedor.winfo_children():
            if hijo is getattr(real, "_franja_estilo", None):
                continue
            zona = getattr(hijo, "_zona", None)
            if zona in ("franja_estilo", "barra"):
                continue
            try:
                if isinstance(hijo, (tk.Frame, tk.LabelFrame)):
                    hijo.config(bg=p["bg"])
            except tk.TclError:
                continue
    except tk.TclError:
        pass


def enganchar_cuerpo_toplevel(contenedor, ventana):
    """Devuelve el frame de contenido con metodos de ventana delegados (title, geometry…)."""
    contenedor._ventana_real = ventana
    contenedor._chrome_manten = True

    destroy_ventana = ventana.destroy

    def destroy_ventana_marcada():
        ventana._en_destroy_cascada = True
        try:
            destroy_ventana()
        finally:
            ventana._en_destroy_cascada = False

    ventana.destroy = destroy_ventana_marcada

    def destroy_cuerpo():
        if getattr(ventana, "_en_destroy_cascada", False):
            tk.Frame.destroy(contenedor)
            return
        destroy_ventana_marcada()

    contenedor.destroy = destroy_cuerpo

    for nombre in (
        "title",
        "geometry",
        "minsize",
        "maxsize",
        "resizable",
        "protocol",
        "transient",
        "grab_set",
        "grab_release",
        "lift",
        "focus_force",
        "withdraw",
        "deiconify",
        "iconify",
        "state",
        "update_idletasks",
        "update",
        "after",
        "after_cancel",
        "wm_attributes",
        "attributes",
        "iconphoto",
        "bind",
        "unbind",
        "bind_all",
        "unbind_all",
        "winfo_exists",
        "winfo_screenwidth",
        "winfo_screenheight",
        "winfo_width",
        "winfo_height",
        "winfo_x",
        "winfo_y",
        "clipboard_clear",
        "clipboard_append",
        "clipboard_get",
        "wait_window",
        "wait_visibility",
    ):
        setattr(contenedor, nombre, getattr(ventana, nombre))

    def winfo_toplevel():
        return ventana

    contenedor.winfo_toplevel = winfo_toplevel
    return contenedor


def aplicar_chrome_toplevel(ventana, color_franja=None):
    """Fondo + franja superior sincronizada con el titulo (Tk y Toplevel)."""
    if getattr(ventana, "_chrome_manten", False):
        return
    if type(ventana).__name__ not in ("Toplevel", "Tk"):
        return

    try:
        import preferencias

        preferencias.aplicar_defaults_tema(ventana)
    except Exception:
        pass

    p = paleta()
    ventana._chrome_manten = True
    color = color_franja or p["franja"]
    ventana._color_franja_estilo = color_franja  # None = seguir tema
    try:
        ventana.configure(bg=p["bg"])
    except tk.TclError:
        pass

    shell = tk.Frame(ventana, bg=p["bg"])
    shell.pack(fill=tk.BOTH, expand=True)
    ventana._shell_estilo = shell

    franja = tk.Frame(shell, bg=color, height=48)
    _marcar_franja(franja)
    franja.pack(fill=tk.X, side=tk.TOP)
    franja.pack_propagate(False)
    lbl = tk.Label(
        franja,
        text="MANTEN1D0",
        bg=color,
        fg=p["franja_fg"],
        font=("Arial", 12, "bold"),
    )
    _marcar_franja(lbl)
    lbl.pack(pady=11)
    ventana._franja_estilo = franja
    ventana._lbl_franja_estilo = lbl

    contenedor = tk.Frame(shell, bg=p["bg"])
    contenedor.pack(fill=tk.BOTH, expand=True)
    ventana._contenedor_estilo = contenedor

    title_orig = ventana.title

    def title_wrap(string=None):
        if string is None:
            return title_orig()
        resultado = title_orig(string)
        _actualizar_franja(ventana, string)
        return resultado

    ventana.title = title_wrap

    def _sync_inicial():
        try:
            actual = title_orig()
            if actual:
                _actualizar_franja(ventana, actual)
        except tk.TclError:
            pass

    try:
        ventana.after_idle(_sync_inicial)
    except tk.TclError:
        _sync_inicial()


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
    p = paleta()
    color = color_franja or p["franja"]
    if color_franja:
        ventana._color_franja_estilo = color_franja
    ventana.resizable(False, False)
    ventana.configure(bg=p["bg"])
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

    real = ventana_estilo_real(ventana)
    if getattr(real, "_franja_estilo", None) is not None:
        ventana.title(titulo_ventana)
        _actualizar_franja(real, titulo_franja, color)
    else:
        real._chrome_manten = True
        franja = tk.Frame(ventana, bg=color, height=56)
        _marcar_franja(franja)
        franja.pack(fill=tk.X)
        franja.pack_propagate(False)
        lbl = tk.Label(
            franja,
            text=titulo_franja,
            bg=color,
            fg=p["franja_fg"],
            font=("Arial", 14, "bold"),
        )
        _marcar_franja(lbl)
        lbl.pack(pady=14)
        real._franja_estilo = franja
        real._lbl_franja_estilo = lbl
        ventana.title(titulo_ventana)

    cuerpo = tk.Frame(ventana, bg=p["bg"], padx=24, pady=16)
    cuerpo.pack(fill=tk.BOTH, expand=True)
    return cuerpo


def etiqueta_titulo(parent, texto, wraplength=400):
    p = paleta()
    return tk.Label(
        parent,
        text=texto,
        bg=p["bg"],
        fg=p["titulo"],
        font=("Arial", 12, "bold"),
        wraplength=wraplength,
        justify=tk.LEFT,
    )


def etiqueta_texto(parent, texto, wraplength=400):
    p = paleta()
    return tk.Label(
        parent,
        text=texto,
        bg=p["bg"],
        fg=p["texto"],
        font=("Arial", 10),
        wraplength=wraplength,
        justify=tk.LEFT,
    )


def boton_primario(parent, texto, comando, width=14):
    p = paleta()
    return tk.Button(
        parent,
        text=texto,
        command=comando,
        width=width,
        font=("Arial", 11, "bold"),
        bg=p["boton"],
        fg="white",
        activebackground=p["boton_activo"],
        activeforeground="white",
        relief=tk.RAISED,
        borderwidth=2,
    )


def boton_secundario(parent, texto, comando, width=12):
    p = paleta()
    return tk.Button(
        parent,
        text=texto,
        command=comando,
        width=width,
        bg=p["bg"],
        fg=p["texto"],
        activebackground=p["campo"],
        activeforeground=p["texto"],
    )


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

    lineas = max(3, mensaje.count("\n") + len(mensaje) // 60)
    alto_calc = max(alto, min(520, 180 + lineas * 18))
    p = paleta()

    resultado = {"valor": None}
    win = tk.Toplevel(parent)
    cuerpo = preparar_dialogo(
        win,
        titulo_ventana,
        titulo_franja,
        ancho,
        alto_calc,
        color_franja=color_franja,
        topmost=True,
    )
    try:
        win.transient(parent)
    except tk.TclError:
        pass

    etiqueta_titulo(cuerpo, titulo, wraplength=ancho - 60).pack(anchor="w")
    etiqueta_texto(cuerpo, mensaje, wraplength=ancho - 60).pack(anchor="w", pady=(8, 12))

    fila = tk.Frame(cuerpo, bg=p["bg"])
    fila.pack(anchor="w", pady=(8, 0))

    def elegir(valor):
        resultado["valor"] = valor
        win.destroy()

    for i, (texto, valor) in enumerate(botones):
        ancho_btn = max(12, min(22, len(texto) + 2))
        if i == 0:
            btn = boton_primario(fila, texto, lambda v=valor: elegir(v), width=ancho_btn)
        else:
            btn = boton_secundario(fila, texto, lambda v=valor: elegir(v), width=ancho_btn)
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


def dialogo_confirmar(mensaje, parent=None, titulo="Seguro?"):
    """Si/No con el estilo de Manten1d0."""
    franja = (titulo or "Confirmar").upper()[:48]
    return bool(
        dialogo_mensaje(
            parent,
            titulo or "Confirmar",
            franja,
            titulo or "Confirmar",
            mensaje,
            botones=(("Si", True), ("No", False)),
            color_franja=FRANJA_AVISO,
            ancho=480,
            alto=300,
        )
    )


def instalar_messagebox_estilo():
    """Sustituye messagebox estandar por dialogos con franja Manten1d0."""
    global _MESSAGEBOX_PARCHE
    if _MESSAGEBOX_PARCHE:
        return
    _MESSAGEBOX_PARCHE = True

    def _info(title, message, **kwargs):
        dialogo_mensaje(
            kwargs.get("parent"),
            title or "Informacion",
            (title or "Informacion").upper()[:48],
            title or "Informacion",
            message or "",
            botones=(("Continuar", True),),
            color_franja=paleta()["franja"],
        )
        return "ok"

    def _warning(title, message, **kwargs):
        dialogo_mensaje(
            kwargs.get("parent"),
            title or "Aviso",
            (title or "Aviso").upper()[:48],
            title or "Aviso",
            message or "",
            botones=(("Continuar", True),),
            color_franja=FRANJA_AVISO,
        )
        return "ok"

    def _error(title, message, **kwargs):
        dialogo_mensaje(
            kwargs.get("parent"),
            title or "Error",
            (title or "Error").upper()[:48],
            title or "Error",
            message or "",
            botones=(("Cerrar", True),),
            color_franja=FRANJA_ERROR,
        )
        return "ok"

    def _yesno(title, message, **kwargs):
        return bool(
            dialogo_mensaje(
                kwargs.get("parent"),
                title or "Confirmar",
                (title or "Confirmar").upper()[:48],
                title or "Confirmar",
                message or "",
                botones=(("Si", True), ("No", False)),
                color_franja=FRANJA_AVISO,
                ancho=480,
                alto=300,
            )
        )

    def _okcancel(title, message, **kwargs):
        return bool(
            dialogo_mensaje(
                kwargs.get("parent"),
                title or "Confirmar",
                (title or "Confirmar").upper()[:48],
                title or "Confirmar",
                message or "",
                botones=(("Continuar", True), ("Cancelar", False)),
                color_franja=FRANJA_AVISO,
                ancho=480,
                alto=300,
            )
        )

    messagebox_mod.showinfo = _info
    messagebox_mod.showwarning = _warning
    messagebox_mod.showerror = _error
    messagebox_mod.askyesno = _yesno
    messagebox_mod.askokcancel = _okcancel
    try:
        import tkinter as _tk

        if hasattr(_tk, "messagebox"):
            _tk.messagebox.showinfo = _info
            _tk.messagebox.showwarning = _warning
            _tk.messagebox.showerror = _error
            _tk.messagebox.askyesno = _yesno
            _tk.messagebox.askokcancel = _okcancel
    except Exception:
        pass
