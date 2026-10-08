import sys
import subprocess
import os


def _ruta_python_venv():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")


def _relanzar_en_venv_si_procede():
    python_venv = _ruta_python_venv()
    if not os.path.exists(python_venv):
        return
    if os.path.realpath(sys.executable) == os.path.realpath(python_venv):
        return
    os.execv(python_venv, [python_venv, os.path.abspath(__file__), *sys.argv[1:]])


_relanzar_en_venv_si_procede()

try:
    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog
except ImportError:
    # Instalar python3-tk automáticamente sin mostrar mensaje al usuario
    proceso_instalacion = subprocess.Popen(
        ["sudo", "apt", "install", "-y", "python3-tk"],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    proceso_instalacion.communicate(input="\n")

    if proceso_instalacion.returncode != 0:
        exit(1)

    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog

import threading
import time
import webbrowser
import requests
from about import mostrar_about
from documentacion import mostrar_documentacion
from cat_informacion import Informacion
from password import limpiar_archivos_configuracion, obtener_contrasena
from dependencias import instalar_dependencias, resumen_dependencias_faltantes
from menuCategorias import archivos_cat, diccionario_cat, informacion_cat, internet_cat, navegadores_cat, perfil_cat, red_local_cat, sistema_cat, notas_cat, inicio_cat
import preferencias  # Importar el módulo de preferencias para manejar el cambio de tema
from registro import mostrar_registro, vincular_bombeo_ui, detener_bombeo_ui
from bandeja import BandejaSistema, preparar_ventana_app, instalar_icono_en_toplevels, CLASE_VENTANA
from cat_vpn import vpn_en_uso
from tooltip import ToolTip
import dialogo_estilo as estilo

RUTA_LOGO_SPLASH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manten1do.png")


def mostrar_splash(parent, duracion_ms=3000):
    """Splash como Toplevel de la unica raiz Tk (evita Tcl_AsyncDelete al recrear Tk)."""
    try:
        splash = tk.Toplevel(parent, chrome=False)
    except TypeError:
        splash = tk.Toplevel(parent)
    splash.withdraw()
    splash.overrideredirect(True)
    try:
        splash.attributes("-topmost", True)
    except tk.TclError:
        pass

    fondo = "#2c2c2c"
    marco = tk.Frame(splash, bg=fondo, padx=28, pady=28)
    marco.pack(fill=tk.BOTH, expand=True)

    refs = {"foto": None, "lbl": None}
    try:
        from PIL import Image, ImageTk

        imagen = Image.open(RUTA_LOGO_SPLASH)
        imagen.thumbnail((360, 360), Image.LANCZOS)
        refs["foto"] = ImageTk.PhotoImage(imagen, master=splash)
        refs["lbl"] = tk.Label(marco, image=refs["foto"], bg=fondo)
        refs["lbl"].image = refs["foto"]
        refs["lbl"].pack()
    except Exception:
        refs["lbl"] = tk.Label(
            marco,
            text="Manten1d0",
            font=("Arial", 28, "bold"),
            bg=fondo,
            fg="#ffffff",
        )
        refs["lbl"].pack(pady=40)

    tk.Label(
        marco,
        text="Cargando...",
        font=("Arial", 11),
        bg=fondo,
        fg="#cccccc",
    ).pack(pady=(12, 0))

    splash.update_idletasks()
    ancho = max(splash.winfo_reqwidth(), 320)
    alto = max(splash.winfo_reqheight(), 280)
    x = max(0, (splash.winfo_screenwidth() - ancho) // 2)
    y = max(0, (splash.winfo_screenheight() - alto) // 2)
    splash.geometry(f"{ancho}x{alto}+{x}+{y}")
    splash.deiconify()
    splash.lift()

    cerrado = {"ok": False}

    def cerrar(_event=None):
        if cerrado["ok"]:
            return
        cerrado["ok"] = True
        # Liberar PhotoImage en el hilo de Tk antes de destruir el Toplevel
        try:
            if refs["lbl"] is not None:
                refs["lbl"].configure(image="")
                refs["lbl"].image = None
        except tk.TclError:
            pass
        refs["foto"] = None
        try:
            splash.destroy()
        except tk.TclError:
            pass

    splash.bind("<Button-1>", cerrar)
    splash.bind("<Escape>", cerrar)
    splash.after(max(500, min(int(duracion_ms), 3000)), cerrar)
    parent.wait_window(splash)


def instalar_dependencias_con_progreso(parent):
    progress_window = tk.Toplevel(parent)
    cuerpo = estilo.preparar_dialogo(
        progress_window,
        "Manten1d0 - Instalando dependencias",
        "INSTALANDO DEPENDENCIAS",
        460,
        220,
        topmost=True,
    )
    progress_window.transient(parent)
    progress_window.grab_set()

    estilo.etiqueta_titulo(cuerpo, "Instalando lo necesario").pack(anchor="w")
    progress_label = estilo.etiqueta_texto(
        cuerpo,
        "Puede tardar un poco segun lo que falte...",
    )
    progress_label.pack(anchor="w", pady=(6, 10))

    progress_bar = ttk.Progressbar(cuerpo, length=400, mode="determinate")
    progress_bar.pack(fill=tk.X, pady=4)
    progress_bar["value"] = 0
    progress_bar["maximum"] = 100

    resultado = {"ok": False, "error": None}

    def actualizar_progreso(valor, texto=""):
        if not progress_window.winfo_exists():
            return
        progress_bar["value"] = valor
        if texto:
            progress_label.config(text=texto)

    def finalizar():
        if progress_window.winfo_exists():
            progress_window.grab_release()
            progress_window.destroy()

    def trabajador():
        from registro import programar_ui

        ok, error = instalar_dependencias(
            on_progress=lambda valor, texto="": programar_ui(
                parent, actualizar_progreso, valor, texto
            )
        )
        resultado["ok"] = ok
        resultado["error"] = error
        programar_ui(parent, finalizar)

    threading.Thread(target=trabajador, daemon=True).start()
    parent.wait_window(progress_window)
    return resultado["ok"], resultado["error"]


def _limpiar_hijos(raiz):
    for hijo in list(raiz.winfo_children()):
        try:
            hijo.destroy()
        except tk.TclError:
            pass


def main():
    print(f"Ejecutando programa con: {sys.executable}")

    # Una sola raiz Tk para todo el ciclo de vida (splash -> password -> deps -> app).
    # Crear/destruir varios tk.Tk() + PhotoImage provoca Tcl_AsyncDelete.
    root = tk.Tk(className=CLASE_VENTANA, baseName=CLASE_VENTANA)
    root.withdraw()
    preparar_ventana_app(root)
    instalar_icono_en_toplevels()

    mostrar_splash(root, 3000)
    obtener_contrasena()

    vincular_bombeo_ui(root)
    _limpiar_hijos(root)
    root.deiconify()
    cuerpo = estilo.preparar_dialogo(
        root,
        "Manten1d0 - Comprobando dependencias",
        "COMPROBANDO DEPENDENCIAS",
        460,
        220,
        topmost=True,
    )
    estilo.etiqueta_titulo(cuerpo, "Revisando el equipo").pack(anchor="w")
    label = estilo.etiqueta_texto(
        cuerpo,
        "Comprobando que esten instalados los programas y librerias necesarios...",
    )
    label.pack(anchor="w", pady=(6, 12))

    progress_bar = ttk.Progressbar(cuerpo, orient="horizontal", length=400, mode="indeterminate")
    progress_bar.pack(fill=tk.X, pady=4)
    progress_bar.start()

    root.after(200, lambda: verificar_dependencias_con_progreso(root, progress_bar, label))
    root.mainloop()


def verificar_dependencias_con_progreso(root, progress_bar, label):
    faltan_sistema, faltan_pip = resumen_dependencias_faltantes()
    if faltan_sistema or faltan_pip:
        bloques = []
        if faltan_sistema:
            bloques.append("Sistema:\n- " + "\n- ".join(faltan_sistema))
        if faltan_pip:
            bloques.append("Python:\n- " + "\n- ".join(faltan_pip))
        detalle = "\n\n".join(bloques)
        instalar = estilo.dialogo_mensaje(
            root,
            "Manten1d0 - Dependencias",
            "FALTAN DEPENDENCIAS",
            "Hay componentes imprescindibles sin instalar",
            detalle + "\n\n¿Quieres instalarlos ahora?",
            botones=(("Instalar ahora", True), ("Cancelar", False)),
            color_franja=estilo.FRANJA_AVISO,
            ancho=480,
            alto=360,
        )
        if instalar:
            ok, error = instalar_dependencias_con_progreso(root)
            if not ok:
                estilo.dialogo_mensaje(
                    root,
                    "Manten1d0 - Error",
                    "ERROR DE INSTALACION",
                    "No se pudieron instalar las dependencias",
                    error or "Se produjo un error desconocido.",
                    botones=(("Cerrar", True),),
                    color_franja=estilo.FRANJA_ERROR,
                    ancho=480,
                    alto=300,
                )
                detener_bombeo_ui()
                root.destroy()
                return
            verificar_dependencias_con_progreso(root, progress_bar, label)
        else:
            estilo.dialogo_mensaje(
                root,
                "Manten1d0 - Dependencias",
                "NO SE PUEDE INICIAR",
                "Faltan dependencias imprescindibles",
                "El programa no puede iniciar sin instalar lo que falta.",
                botones=(("Cerrar", True),),
                color_franja=estilo.FRANJA_AVISO,
            )
            detener_bombeo_ui()
            root.destroy()
    else:
        close_progress(root, progress_bar, label)


def close_progress(root, progress_bar, label):
    try:
        progress_bar.stop()
    except tk.TclError:
        pass

    estilo.dialogo_mensaje(
        root,
        "Manten1d0 - Listo",
        "TODO LISTO",
        "Todas las dependencias estan instaladas",
        "Haz clic en Continuar para abrir Manten1d0.",
        botones=(("Continuar", True),),
        color_franja=estilo.FRANJA_OK,
        ancho=460,
        alto=240,
    )
    # Ocultar la raiz mientras se reconstruye (evita el flash de ventana en blanco)
    detener_bombeo_ui()
    try:
        root.attributes("-topmost", False)
    except tk.TclError:
        pass
    try:
        root.withdraw()
    except tk.TclError:
        pass
    root.update_idletasks()

    _limpiar_hijos(root)
    for attr in (
        "_chrome_manten",
        "_franja_estilo",
        "_contenedor_estilo",
        "_shell_estilo",
        "_color_franja_estilo",
    ):
        try:
            if hasattr(root, attr):
                delattr(root, attr)
        except Exception:
            pass
    root.resizable(True, True)
    preparar_ventana_app(root, estilo_dialogo=True)
    vincular_bombeo_ui(root)
    VentanaPrincipal(root)
    # Mostrar solo cuando la UI principal ya está montada
    try:
        root.update_idletasks()
        root.deiconify()
        root.lift()
        root.focus_force()
    except tk.TclError:
        pass
    # Ya estamos dentro de root.mainloop(); no crear otro Tk ni otro mainloop.

##############################################################VENTANA PRINCIPAL##############################################################

class VentanaPrincipal:
    def __init__(self, root):
        from tooltip import ToolTip

        self.root = root
        self.root.title("Manten1-d0")
        self.root.geometry("800x700")
        self.root.minsize(800, 700)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._al_pulsar_cerrar)
        self._bandeja = None

        self._categoria_activa = None
        # Contenedor bajo la franja (mismo chrome que las ventanas secundarias)
        self.cuerpo = estilo.panel_contenido(self.root)
        try:
            self.cuerpo.configure(bg=preferencias.color_fondo())
        except tk.TclError:
            pass
        self.root.config(bg=preferencias.color_fondo())
        preferencias.aplicar_defaults_tema(self.root)
        
##############################################################FUNCIONES PARA MENÚ SUPERIOR##########################################################

        # Función para abrir la ventana de Opciones/Personalización
        def abrir_ventana_personalizacion():
            preferencias.abrir_ventana_configuracion(root)
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        # Función para abrir la ventana de actualizaciones
        def abrir_ventana_actualizaciones():
            # Importar el módulo actualizaciones.py
            import actualizaciones
            # Llamar a la función para mostrar la ventana de actualizaciones
            actualizaciones.mostrar_ventana_actualizaciones()
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        def abrir_url():

            url = tk.simpledialog.askstring("Abrir URL", "Ingrese la URL que desea abrir:")
            if url:
                webbrowser.open_new(url)

        def abrir_url_github():

            webbrowser.open("https://github.com/sapoclay/manten1d0")
            
        def abrir_terminal():
            try:
                # Comando para abrir la terminal predeterminada en Ubuntu
                subprocess.Popen(["gnome-terminal"])
            except Exception as e:
                # Manejar cualquier excepción que pueda ocurrir al intentar abrir la terminal
                print(f"No se pudo abrir la terminal: {e}")

#################################################### MENÚ SUPERIOR ##############################################################
        def menu():
            # Crear el menú superior
            self.menu_superior = tk.Menu(self.root)
            self.menu_archivo = tk.Menu(self.menu_superior, tearoff=0)
            self.menu_archivo.add_command(label="Abrir Terminal (Ctrl+Alt+T)", command=abrir_terminal)
            self.menu_archivo.add_separator()
            self.menu_archivo.add_command(label="Abrir URL en Navegador", command=abrir_url)
            self.menu_archivo.add_separator()
            self.menu_archivo.add_command(label="Salir", command=self.cerrar_ventana_principal)
            self.menu_superior.add_cascade(label="Archivo", menu=self.menu_archivo)
            # Crear el menú Preferencias
            preferencias_menu = tk.Menu(self.root, tearoff=0)
            preferencias_menu.add_command(label="Repositorio GitHub", command=abrir_url_github)
            preferencias_menu.add_separator()
            preferencias_menu.add_command(
                label="Buscar Actualizaciones", command=abrir_ventana_actualizaciones
            )
            preferencias_menu.add_separator()
            preferencias_menu.add_command(label="Opciones", command=abrir_ventana_personalizacion)
            preferencias_menu.add_separator()
            preferencias_menu.add_command(label="Registro de acciones", command=lambda: mostrar_registro(self.root))
            preferencias_menu.add_command(
                label="Atajos de teclado",
                command=lambda: messagebox.showinfo(
                    "Atajos",
                    "Alt+1 Inicio\nAlt+2 Perfil Usuario\nAlt+3 Información\nAlt+4 Sistema\n"
                    "Alt+5 Archivos\nAlt+6 Internet\nAlt+7 Red Local\nAlt+8 Navegadores\n"
                    "Alt+9 Diccionario\nAlt+0 Notas",
                ),
            )
            self.menu_superior.add_cascade(label="Preferencias", menu=preferencias_menu)
            menu_ayuda = tk.Menu(self.menu_superior, tearoff=0)
            menu_ayuda.add_command(
                label="Documentación",
                command=lambda: mostrar_documentacion(self.root),
            )
            menu_ayuda.add_separator()
            menu_ayuda.add_command(label="Acerca de", command=mostrar_about)
            self.menu_superior.add_cascade(label="Ayuda", menu=menu_ayuda)
            self.root.config(menu=self.menu_superior)

        # Llamamos al menú superior creado con la función menú
        menu()
        
##################################################################################################################################
##############################################MENÚ LATERAL########################################################################
        def menu_lateral():
            barra = preferencias.color_barra()
            texto = preferencias.color_texto()
            campo = preferencias.color_campo()
            self.menu_lateral = tk.Frame(self.cuerpo, width=220, bg=barra)
            self.menu_lateral._zona = "barra"
            self.menu_lateral.pack(side="left", fill="y")
            self.menu_lateral.pack_propagate(False)

            # Buscador de herramientas (parte superior de la barra)
            marco_busqueda = tk.Frame(self.menu_lateral, bg=barra)
            marco_busqueda._zona = "barra"
            marco_busqueda.pack(side="top", fill="x", padx=8, pady=(10, 4))
            tk.Label(
                marco_busqueda,
                text="Buscar",
                bg=barra,
                fg=texto,
                font=preferencias.fuente_ui(9),
                anchor="w",
            ).pack(fill="x")
            self.var_busqueda = tk.StringVar()
            self.entry_busqueda = tk.Entry(
                marco_busqueda,
                textvariable=self.var_busqueda,
                font=preferencias.fuente_ui(10),
                bg=campo,
                fg=texto,
                insertbackground=texto,
                relief="flat",
                highlightthickness=1,
                highlightbackground=preferencias.color_borde(),
                highlightcolor=preferencias.color_borde(),
            )
            self.entry_busqueda._zona = "barra"
            self.entry_busqueda.pack(fill="x", pady=(2, 0), ipady=3)
            ToolTip(
                self.entry_busqueda,
                "Escribe el nombre de una herramienta (por ejemplo: procesos, Wi-Fi, limpiar)",
            )
            self.var_busqueda.trace_add("write", lambda *_: self._actualizar_busqueda_herramientas())
            self.entry_busqueda.bind("<Return>", lambda _e: self._activar_resultado_busqueda())
            self.entry_busqueda.bind("<Down>", lambda _e: self._enfocar_lista_busqueda())
            self.entry_busqueda.bind("<Escape>", lambda _e: self._limpiar_busqueda_herramientas())

            self.lista_busqueda = tk.Listbox(
                self.menu_lateral,
                font=preferencias.fuente_ui(9),
                bg=campo,
                fg=texto,
                selectbackground=preferencias.colores_de(preferencias.tema_seleccionado)["select"],
                selectforeground=preferencias.colores_de(preferencias.tema_seleccionado)["select_fg"],
                activestyle="none",
                highlightthickness=0,
                borderwidth=0,
                exportselection=False,
            )
            self.lista_busqueda._zona = "barra"
            self.lista_busqueda.bind("<Double-Button-1>", lambda _e: self._activar_resultado_busqueda())
            self.lista_busqueda.bind("<Return>", lambda _e: self._activar_resultado_busqueda())
            self.lista_busqueda.bind("<Escape>", lambda _e: self._limpiar_busqueda_herramientas())
            self._resultados_busqueda = []
            self._catalogo_herramientas = None

            marco_nav = tk.Frame(self.menu_lateral, bg=barra)
            marco_nav._zona = "barra"
            marco_nav.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))
            self.marco_nav_categorias = marco_nav

            self.categorias = [
                "Inicio",
                "Perfil Usuario",
                "Información",
                "Sistema",
                "Archivos",
                "Internet",
                "Red Local",
                "Navegadores",
                "Diccionario",
                "Notas",
            ]
            self.botones_categorias = []
            for indice, categoria in enumerate(self.categorias, start=1):
                tecla = "0" if indice == 10 else str(indice)
                boton = tk.Button(
                    marco_nav,
                    text=categoria,
                    command=lambda c=categoria: self.mostrar_subcategorias(c),
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=0,
                    anchor="w",
                    padx=12,
                    pady=6,
                    bg=barra,
                    fg=texto,
                    activebackground=preferencias.color_hover(),
                    activeforeground=texto,
                    font=preferencias.fuente_ui(11),
                    cursor="hand2",
                )
                boton._zona = "barra"
                boton._nav = categoria
                boton._nav_activa = False
                boton.pack(fill="x", pady=2)
                ToolTip(boton, f"Categoría {categoria} (Alt+{tecla})")
                preferencias.aplicar_hover(
                    boton,
                    fondo_normal=barra,
                    fondo_hover=preferencias.color_hover(),
                )
                self.botones_categorias.append(boton)
                self.root.bind_all(
                    f"<Alt-Key-{tecla}>",
                    lambda event, c=categoria: self.mostrar_subcategorias(c),
                )

            marco_estado = tk.Frame(self.menu_lateral, bg=barra)
            marco_estado._zona = "barra"
            marco_estado.pack(side="bottom", fill="x", padx=8, pady=12)

            self.indicador_internet = tk.Label(
                marco_estado,
                text="Estado de la conexión",
                bg="red",
                fg="white",
                font=preferencias.fuente_ui(9),
                padx=8,
                pady=4,
            )
            self.indicador_internet.pack(fill="x", pady=(0, 8))
            ToolTip(self.indicador_internet, "Estado de la conexión a internet del equipo")

            self.lbl_ip_privada = tk.Label(
                marco_estado,
                text="IP privada: ...",
                bg=barra,
                fg=texto,
                font=preferencias.fuente_ui(9),
                wraplength=190,
                justify=tk.LEFT,
                anchor="w",
            )
            self.lbl_ip_privada._zona = "barra"
            self.lbl_ip_privada.pack(fill="x", pady=(4, 0))
            ToolTip(self.lbl_ip_privada, "Dirección IP de este equipo en la red local")

            self.lbl_ip_publica = tk.Label(
                marco_estado,
                text="IP pública: ...",
                bg=barra,
                fg=texto,
                font=preferencias.fuente_ui(9),
                wraplength=190,
                justify=tk.LEFT,
                anchor="w",
            )
            self.lbl_ip_publica._zona = "barra"
            self.lbl_ip_publica.pack(fill="x", pady=(2, 0))
            ToolTip(self.lbl_ip_publica, "Dirección IP pública de la conexión a Internet")

            self.lbl_vpn = tk.Label(
                marco_estado,
                text="VPN: ...",
                bg=barra,
                fg=texto,
                font=preferencias.fuente_ui(9),
                wraplength=190,
                justify=tk.LEFT,
                anchor="w",
            )
            self.lbl_vpn._zona = "barra"
            self.lbl_vpn.pack(fill="x", pady=(2, 0))
            self._tip_vpn = ToolTip(self.lbl_vpn, "Indica si el equipo está usando una VPN")
            self._ip_publica_cache = ""
            self._ip_publica_momento = 0
            # Iniciar la verificación de conexión a Internet
            self.check_connection()

        menu_lateral()
############################################################################################################################################        
        
        # Crear el área central para mostrar subcategorías
        self.area_central = tk.Frame(self.cuerpo, bg=preferencias.color_fondo(), borderwidth=0)
        self.area_central.pack(side="top", fill="both", expand=True)

        self.label_bienvenida = tk.Label(
            self.area_central,
            text="¡Bienvenid@!\n Comienza haciendo clic\n en una categoría del menú lateral.",
            font=preferencias.fuente_ui(18, "bold"),
            bg=preferencias.color_fondo(),
            fg=preferencias.color_texto(),
        )
        self.label_bienvenida.pack(pady=50)

        # Contenedor para el label de subcategorías
        self.frame_subcategorias = tk.Frame(
            self.area_central, bg=preferencias.color_fondo(), padx=10, pady=10
        )
        self.frame_subcategorias.pack(
            anchor="n", pady=(0, 20)
        )  # Espaciado en la parte superior y anclar al norte

        self.label_subcategorias = tk.Label(
            self.area_central,
            text="",
            font=preferencias.fuente_ui(12),
            bg=preferencias.color_fondo(),
            fg=preferencias.color_texto(),
            padx=10,
            pady=0,
        )
        self.label_subcategorias.pack()

        # Crear el contenedor para el widget Text y la barra de desplazamiento para mostrar la categoría Información
        self.contenedor_texto = tk.Frame(self.cuerpo, bg=preferencias.color_fondo())
        # Contenedor Deshabilitado al inicio
        self.contenedor_texto.pack_forget()

        # Crear el widget Text para mostrar la información del sistema (inicialmente deshabilitado)
        self.texto_informacion = tk.Text(
            self.contenedor_texto, wrap=tk.WORD, font=("Arial", 12), state=tk.DISABLED
        )
        self.texto_informacion.pack(expand=True, fill="both", side="left")
        self.texto_informacion.pack_forget()  # Ocultar el widget Text

        # Agregar barra de desplazamiento vertical
        self.scrollbar_vertical = ttk.Scrollbar(
            self.contenedor_texto, orient="vertical", command=self.texto_informacion.yview
        )
        self.scrollbar_vertical.pack(side="right", fill="y")
        self.texto_informacion.config(yscrollcommand=self.scrollbar_vertical.set)

        # Mensajes personalizados para cada categoría
        self.mensajes_personalizados = {
            "Inicio": "Resumen del estado del equipo",
            "Información": "Información sobre el Sistema Operativo",
            "Perfil Usuario": "Modifica los datos de tu perfil de usuario en el sistema",
            "Sistema": "Configuraciones y detalles del Sistema Operativo.",
            "Archivos": "Opciones sobre archivos del Sistema Operativo",
            "Internet": "Configuraciones y detalles sobre la conexión a Internet.",
            "Red Local": "Configuraciones y acciones sobre la red local.",
            "Navegadores": "Acciones con los navegadores web.",
            "Diccionario": "Diccionario sobre comandos Gnu/Linux",
            "Notas": "Escribe tus apuntes y notas rápidas",
        }

        # Llenar el área de texto con la información inicial
        self.mostrar_informacion_sistema()
        preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)
        self.root.after(200, lambda: self.mostrar_subcategorias("Inicio"))
        self.root.after(
            400,
            lambda: self._iniciar_bandeja(
                abrir_terminal,
                abrir_ventana_personalizacion,
                abrir_ventana_actualizaciones,
            ),
        )

    # Función para mostrar u ocultar elementos en el área principal según la categoría seleccionada. También se hacen las llamadas a funciones
    def mostrar_subcategorias(self, categoria):
        mensaje_personalizado = self.mensajes_personalizados.get(categoria, None)

        if categoria == "Inicio":

            inicio_cat(self, mensaje_personalizado)

        elif categoria == "Información":

            informacion_cat(self, mensaje_personalizado)

        elif categoria == "Diccionario":

            diccionario_cat(self, mensaje_personalizado)
            
        elif categoria == "Notas":

            notas_cat(self, mensaje_personalizado)

        elif categoria == "Perfil Usuario":

            perfil_cat(self, mensaje_personalizado)

        elif categoria == "Sistema":

            sistema_cat(self, mensaje_personalizado)
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Archivos":

            archivos_cat(self, mensaje_personalizado)
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Internet":

            internet_cat(self, mensaje_personalizado)
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Red Local":

            red_local_cat(self, mensaje_personalizado)
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Navegadores":

            navegadores_cat(self, mensaje_personalizado)
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        else:
            self.contenedor_texto.pack_forget()  # Deshabilitar contenedor categoría Información
            self.texto_informacion.pack_forget()  # Ocultar el widget Text
            self.texto_informacion.delete('1.0', tk.END)  # Borrar el contenido del widget Text
            self.label_bienvenida.pack_forget()  # Ocultar el mensaje de bienvenida
            if mensaje_personalizado:
                self.label_subcategorias.config(
                    text=mensaje_personalizado, font=("Arial", 14, "bold")
                )  # Ajustar el texto al mensaje personalizado
            else:
                self.label_subcategorias.config(
                    text=f"Subcategorías de {categoria}", font=("Arial", 12)
                )  # Restaurar el texto original
            self.label_subcategorias.pack()  # Mostrar la etiqueta de subcategorías

        preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)
        self._marcar_categoria(categoria)

    def _marcar_categoria(self, categoria):
        """Deja visible qué sección del menú lateral está abierta."""
        self._categoria_activa = categoria
        hover = preferencias.color_hover()
        for boton in self.botones_categorias:
            activa = getattr(boton, "_nav", None) == categoria
            boton._nav_activa = activa
            fondo = preferencias.color_barra_activa() if activa else preferencias.color_barra()
            boton._hover_fondo = preferencias.color_barra()
            boton._hover_sobre = hover
            boton.config(
                background=fondo,
                foreground=preferencias.color_texto(),
                activebackground=hover,
                activeforeground=preferencias.color_texto(),
                font=preferencias.fuente_ui(11, "bold" if activa else "normal"),
            )

    def _obtener_catalogo_herramientas(self):
        if self._catalogo_herramientas is None:
            from catalogo_herramientas import construir_catalogo

            self._catalogo_herramientas = construir_catalogo(self)
        return self._catalogo_herramientas

    def _limpiar_busqueda_herramientas(self):
        try:
            self.var_busqueda.set("")
        except Exception:
            pass
        self.entry_busqueda.focus_set()

    def _actualizar_busqueda_herramientas(self):
        from catalogo_herramientas import filtrar_catalogo

        consulta = self.var_busqueda.get().strip()
        self.lista_busqueda.delete(0, tk.END)
        self._resultados_busqueda = []

        if not consulta:
            self.lista_busqueda.pack_forget()
            if not self.marco_nav_categorias.winfo_ismapped():
                self.marco_nav_categorias.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))
            return

        self.marco_nav_categorias.pack_forget()
        resultados = filtrar_catalogo(self._obtener_catalogo_herramientas(), consulta)[:40]
        self._resultados_busqueda = resultados
        if not self.lista_busqueda.winfo_ismapped():
            self.lista_busqueda.pack(side="top", fill="both", expand=True, padx=8, pady=(4, 0))

        if not resultados:
            self.lista_busqueda.insert(tk.END, "Sin resultados")
            return
        for item in resultados:
            self.lista_busqueda.insert(tk.END, f"{item['nombre']} | {item['categoria']}")
        self.lista_busqueda.selection_clear(0, tk.END)
        self.lista_busqueda.selection_set(0)
        self.lista_busqueda.activate(0)

    def _enfocar_lista_busqueda(self):
        if self._resultados_busqueda and self.lista_busqueda.winfo_ismapped():
            self.lista_busqueda.focus_set()
            if not self.lista_busqueda.curselection():
                self.lista_busqueda.selection_set(0)
                self.lista_busqueda.activate(0)

    def _activar_resultado_busqueda(self):
        if not self._resultados_busqueda:
            return
        seleccion = self.lista_busqueda.curselection()
        indice = seleccion[0] if seleccion else 0
        if indice < 0 or indice >= len(self._resultados_busqueda):
            return
        item = self._resultados_busqueda[indice]
        self._limpiar_busqueda_herramientas()
        try:
            item["abrir"]()
        except Exception as error:
            messagebox.showerror(
                "Buscar herramientas",
                f"No se pudo abrir «{item['nombre']}»:\n{error}",
                parent=self.root,
            )

    # Función para mostrar la información del sistema dentro de la categoría información. Toma los datos de información.py
    def mostrar_informacion_sistema(self):
        # Obtener la información del sistema utilizando la clase Informacion
        info_completa = Informacion.obtener_informacion_completa()
        usuario = info_completa["Usuario"]
        sistema_operativo = info_completa["Sistema Operativo"]
        version_sistema = info_completa["Versión de Sistema"]
        version_ubuntu = info_completa["Versión de Ubuntu"]
        tipo_escritorio = info_completa["Tipo de Escritorio"]
        tiempo_actividad = info_completa["Tiempo de Actividad"]
        tiempo_arranque = info_completa.get("Tiempo de Arranque", "No disponible")
        tarjeta_grafica = info_completa["Información de la Tarjeta Gráfica"]
        interfaces_red = ", ".join(
            info_completa["Interfaces de Red"]
        )  # Convertir la lista a cadena separada por comas
        ip_local = info_completa["Dirección IP Local"]
        ip_publica = info_completa["Dirección IP Pública"]
        dns_local = info_completa["dns local"]
        dns_publico = info_completa["dns publico"]
        zona_horaria = info_completa["Zona Horaria"]
        procesador = Informacion.obtener_informacion_procesador()
        memoria = Informacion.obtener_informacion_memoria()
        temperatura_cpu = info_completa.get("Temperatura CPU", Informacion.texto_temperatura_cpu())

        # Crear el texto con la información del sistema
        texto_info = [
            ("Usuario:", usuario),
            ("Sistema Operativo:", sistema_operativo),
            ("Versión del Sistema:", version_sistema),
            ("Versión de Ubuntu:", version_ubuntu),
            ("Tipo Escritorio:", tipo_escritorio),
            ("Tiempo de actividad:", tiempo_actividad),
            ("Tiempo de arranque:", tiempo_arranque),
            ("-" * 110, ""),
            ("Interfaces de Red:", interfaces_red),
            ("IP Local:", ip_local),
            ("IP Pública:", ip_publica),
            ("DNS Local:", dns_local),
            ("DNS Público:", dns_publico),
            ("Zona Horaria:", zona_horaria),
            ("Temperatura CPU:", temperatura_cpu),
            ("-" * 110, ""),
        ]

        # Insertar el texto en el widget Text
        self.texto_informacion.config(state=tk.NORMAL)  # Habilitar la edición
        self.texto_informacion.delete(
            '1.0', tk.END
        ) 

        for label, value in texto_info:
            self.texto_informacion.insert(
                tk.END, f"{label} ", "bold"
            )  # Insertar texto estático con negrita
            self.texto_informacion.insert(tk.END, f"{value}\n")  # Insertar valor de la variable
            self.texto_informacion.tag_configure(
                "bold", font=("Arial", 12, "bold")
            )  # Aplicar estilo de texto negrita al texto estático

        self.texto_informacion.insert(
            tk.END, "\nInformación de la tarjeta gráfica:\n", "bold"
        )
        if isinstance(tarjeta_grafica, dict):
            tarjetas = [tarjeta_grafica]
        else:
            tarjetas = tarjeta_grafica or []
        for indice, gpu in enumerate(tarjetas, start=1):
            if len(tarjetas) > 1:
                self.texto_informacion.insert(tk.END, f"\nGPU {indice}\n", "bold")
            for key, value in gpu.items():
                if str(key).startswith("_"):
                    continue
                self.texto_informacion.insert(tk.END, f"{key}: {value}\n")

        self.texto_informacion.insert(tk.END, "-" * 110 + "\n")  # Línea horizontal

        self.texto_informacion.insert(
            tk.END, "\nInformación del Procesador:\n", "bold"
        )  # Texto "Información del Procesador" en negrita
        for item in procesador:
            self.texto_informacion.insert(tk.END, f"{item[0]}: {item[1]}\n")

        self.texto_informacion.insert(tk.END, "-" * 110 + "\n")  # Línea horizontal

        self.texto_informacion.insert(
            tk.END, "\nInformación de la Memoria:\n", "bold"
        )  # Texto "Información de la Memoria" en negrita
        for key, value in memoria.items():
            self.texto_informacion.insert(tk.END, f"{key}: {value}\n")

        self.texto_informacion.config(state=tk.DISABLED)  # Deshabilitar la edición
        self._informe_texto = self.texto_informacion.get("1.0", "end-1c")

    def copiar_informe_sistema(self):
        texto = getattr(self, "_informe_texto", "") or self.texto_informacion.get("1.0", "end-1c")
        if not texto.strip():
            messagebox.showwarning("Informe", "No hay informe para copiar.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.root.update()
        messagebox.showinfo("Informe", "El informe se ha copiado al portapapeles.")

    def exportar_informe_sistema(self):
        texto = getattr(self, "_informe_texto", "") or self.texto_informacion.get("1.0", "end-1c")
        if not texto.strip():
            messagebox.showwarning("Informe", "No hay informe para exportar.")
            return
        destino = filedialog.asksaveasfilename(
            parent=self.root,
            title="Exportar informe",
            defaultextension=".txt",
            initialfile="informe-manten1d0.txt",
            filetypes=(("Texto", "*.txt"), ("Todos los archivos", "*.*")),
        )
        if not destino:
            return
        try:
            with open(destino, "w", encoding="utf-8") as archivo:
                archivo.write(texto.rstrip() + "\n")
        except OSError as error:
            messagebox.showerror("Informe", f"No se pudo guardar el archivo:\n{error}")
            return
        messagebox.showinfo("Informe", f"Informe guardado en:\n{destino}")

    def _iniciar_bandeja(self, abrir_terminal, abrir_opciones, abrir_actualizaciones):
        bandeja = BandejaSistema(
            self,
            {
                "terminal": abrir_terminal,
                "opciones": abrir_opciones,
                "actualizaciones": abrir_actualizaciones,
                "registro": lambda: mostrar_registro(self.root),
                "documentacion": lambda: mostrar_documentacion(self.root),
                "about": mostrar_about,
                "salir": self.cerrar_ventana_principal,
                "ir_a": self.mostrar_subcategorias,
            },
        )
        try:
            if bandeja.iniciar():
                self._bandeja = bandeja
        except Exception:
            self._bandeja = None

    def _al_pulsar_cerrar(self):
        if self._bandeja and self._bandeja.disponible:
            self._bandeja.ocultar()
            return
        self.cerrar_ventana_principal()

    def cerrar_ventana_principal(self):
        after_id = getattr(self, "_internet_check_after_id", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        if self._bandeja is not None:
            self._bandeja.detener()
            self._bandeja = None
        limpiar_archivos_configuracion()
        detener_bombeo_ui()
        self.root.destroy()

    def check_connection(self):
        # Programar la primera comprobación cuando el mainloop ya esté activo
        self._internet_check_after_id = self.root.after(200, self._comprobar_internet)

    def _comprobar_internet(self):
        def trabajador():
            try:
                requests.get("https://www.google.com", timeout=3)
                conectado = True
            except requests.RequestException:
                conectado = False
            privada = Informacion.obtener_direccion_ip_local()
            _vpn_activa, vpn_texto, vpn_detalle = vpn_en_uso()
            if conectado:
                ahora = time.time()
                if not self._ip_publica_cache or ahora - self._ip_publica_momento > 120:
                    publica = Informacion.obtener_direccion_ip_publica(timeout=4)
                    self._ip_publica_cache = publica
                    self._ip_publica_momento = ahora
                else:
                    publica = self._ip_publica_cache
                estado = ("green", "Conexión establecida", privada, publica, vpn_texto, vpn_detalle)
            else:
                self._ip_publica_cache = ""
                self._ip_publica_momento = 0
                estado = ("red", "Sin conexión", privada, "No disponible", vpn_texto, vpn_detalle)
            from registro import programar_ui

            programar_ui(self.root, lambda e=estado: self._aplicar_estado_internet(*e))

        threading.Thread(target=trabajador, daemon=True).start()

    def _aplicar_estado_internet(self, color, texto, privada, publica, vpn_texto="VPN: ...", vpn_detalle=""):
        if not self.root.winfo_exists():
            return
        self.indicador_internet.config(bg=color, text=texto)
        if self.lbl_ip_privada.winfo_exists():
            self.lbl_ip_privada.config(text=f"IP privada: {privada}")
        if self.lbl_ip_publica.winfo_exists():
            self.lbl_ip_publica.config(text=f"IP pública: {publica}")
        if getattr(self, "lbl_vpn", None) is not None and self.lbl_vpn.winfo_exists():
            self.lbl_vpn.config(text=vpn_texto)
            if vpn_detalle and getattr(self, "_tip_vpn", None) is not None:
                self._tip_vpn.text = vpn_detalle
        self._internet_check_after_id = self.root.after(10000, self._comprobar_internet)

if __name__ == "__main__":
    main()