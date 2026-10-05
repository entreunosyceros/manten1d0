import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import preferencias
from cat_archivos import (
    BulkRenameApp,
    FileSearchApp,
    RestaurarCopiaSeguridad,
    cifrar_archivo,
    descifrar_archivo,
)
from cat_archivos_extra import PermisosArchivos, DispositivosBloque, ArchivosGrandes, HashArchivo, CopiaUSB
from cat_diccionario import abrir_ventana_diccionario, cargar_contenido_html
from cat_editorTexto import EditorTextos, carpeta_notas, listar_notas
from cat_informacion import Informacion
from cat_internet import RedTools, hacer_ping, reiniciar_tarjeta_red
from cat_red_extra import RedesWifi, EditorHosts, SelectorDns, PuertoDesdeInternet
from cat_vpn import PanelExpressVPN, expressvpn_disponible
from cat_navegadores import (
    InstalarNavegadores,
    InstalarNavegadoresExtra,
    LimpiadorNavegadores,
    PerfilesNavegadores,
    abrir_navegador,
    _limpiar_directorio,
)
from cat_perfil import PerfilUsuario, crear_panel_perfil
from cat_redLocal import (
    CompartirCarpeta,
    EncenderPC,
    RouterCasa,
    doble_clic,
    encontrar_dispositivos_en_red,
    formatear_dispositivo,
    recordar_equipos,
)
from cat_sistema import (
    AdministrarProcesos,
    AplicacionBuscadorDuplicados,
    AplicacionesAutostart,
    DebInstalador,
    DesinstalarPaquetes,
    Limpieza,
    Repositorios,
    actualizar_sistema,
    consultaLogs,
    limpiar_cache,
    abrir_gestor_software,
)
from cat_sistema_extra import LimpiezaEspacio, SaludDiscos, ServiciosSystemd, Impresoras, EspacioDiscos, Cortafuegos, SnapFlatpak, Bluetooth, ServiciosFallidos, Sonido, Pantallas
from tooltip import ToolTip, con_tooltip
from registro import confirmar, en_hilo, sudo_run, ventana_progreso, mostrar_registro, mostrar_historial_comandos, _widget_vivo
from diagnostico import analizar_equipo
from reparar import RepararUbuntu
from actualizar_todo import ActualizarTodo
from informe_asistencia import InformeAsistencia
from centro_aplicaciones import CentroAplicaciones
from centro_seguridad import CentroSeguridad
from analisis_arranque import AnalisisArranque
from monitor_recursos import MonitorRecursos
from asistente_internet import AsistenteInternet
from asistente_problemas import AsistenteProblemas

COLORES_AVISO = {
    "error": ("#c0392b", "white"),
    "aviso": ("#e67e22", "white"),
    "ok": ("#1e8449", "white"),
    "info": ("#2471a3", "white"),
}

PANELES_DIAGNOSTICO = {
    "ServiciosFallidos": ServiciosFallidos,
    "SaludDiscos": SaludDiscos,
    "Cortafuegos": Cortafuegos,
    "CentroSeguridad": CentroSeguridad,
    "LimpiezaEspacio": LimpiezaEspacio,
    "EspacioDiscos": EspacioDiscos,
    "RepararUbuntu": RepararUbuntu,
    "ActualizarTodo": ActualizarTodo,
    "InformeAsistencia": InformeAsistencia,
    "AsistenteInternet": AsistenteInternet,
    "AsistenteProblemas": AsistenteProblemas,
}

RUTA_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manten1do.png")


def _colocar_logo_inicio(self):
    """Muestra el logo adaptado al espacio del área central."""
    fondo = preferencias.color_fondo()
    marco = tk.Frame(self.area_central, bg=fondo)
    marco.pack(fill=tk.X, padx=16, pady=(12, 4))
    etiqueta = tk.Label(marco, bg=fondo)
    etiqueta.pack()

    try:
        original = Image.open(RUTA_LOGO)
    except OSError:
        etiqueta.config(text="Manten1d0", font=("Arial", 22, "bold"))
        return

    estado = {"ultimo": (0, 0)}

    def ajustar(_event=None):
        if not etiqueta.winfo_exists():
            return
        ancho = self.area_central.winfo_width()
        alto = self.area_central.winfo_height()
        if ancho < 80 or alto < 80:
            return
        max_w = max(180, ancho - 48)
        max_h = max(90, min(int(alto * 0.38), 260))
        if (max_w, max_h) == estado["ultimo"]:
            return
        estado["ultimo"] = (max_w, max_h)
        imagen = original.copy()
        resample = getattr(Image, "LANCZOS", Image.NEAREST)
        imagen.thumbnail((max_w, max_h), resample)
        foto = ImageTk.PhotoImage(imagen)
        etiqueta.configure(image=foto)
        etiqueta.image = foto
        self._inicio_logo_tk = foto

    def programar(_event=None):
        pendiente = getattr(self, "_inicio_logo_after", None)
        if pendiente:
            try:
                self.area_central.after_cancel(pendiente)
            except tk.TclError:
                pass
        self._inicio_logo_after = self.area_central.after(80, ajustar)

    self.area_central.bind("<Configure>", programar)
    self.area_central.after(40, ajustar)


def _reiniciar_equipo(parent):
    if not confirmar(
        "El equipo se va a reiniciar ahora para terminar de aplicar las actualizaciones.\n\n"
        "Guarda lo que tengas abierto. ¿Quieres reiniciar?",
        parent,
        "Reiniciar El Equipo",
    ):
        return

    def trabajo():
        return sudo_run(["systemctl", "reboot"], "Reiniciar el equipo", timeout=40)

    def al_terminar(resultado):
        if resultado is None or getattr(resultado, "returncode", 1) == 0:
            return
        texto = (resultado.stderr or resultado.stdout or "No se pudo reiniciar.").strip()
        messagebox.showerror("Reiniciar El Equipo", texto, parent=parent)

    en_hilo(parent, trabajo, al_terminar=al_terminar)


def inicio_cat(self, mensaje_personalizado=None):
    self.contenedor_texto.pack_forget()
    for widget in self.area_central.winfo_children():
        widget.destroy()

    _colocar_logo_inicio(self)

    titulo = tk.Label(
        self.area_central,
        text="Diagnóstico del equipo",
        font=("Arial", 16, "bold"),
        bg=preferencias.color_fondo(),
        padx=10,
        pady=16,
    )
    titulo.pack()
    canvas_linea = tk.Canvas(self.area_central, width=500, height=2, bg=preferencias.color_fondo(), highlightthickness=0)
    canvas_linea.create_line(0, 1, 500, 1, fill="black")
    canvas_linea.pack(pady=8)

    tk.Label(
        self.area_central,
        text=(
            "Checklist del estado del equipo. Pulsa un resultado para abrir "
            "la herramienta relacionada.\n"
            "Atajos: Alt+1 Inicio, Alt+2 a Alt+0 el resto de categorías."
        ),
        bg=preferencias.color_fondo(),
        font=("Arial", 10),
        justify=tk.CENTER,
    ).pack(pady=(0, 8))

    marco_avisos = tk.Frame(self.area_central, bg=preferencias.color_fondo())
    marco_avisos.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)
    etiqueta_carga = tk.Label(marco_avisos, text="Analizando el equipo...", bg=preferencias.color_fondo())
    etiqueta_carga.pack(pady=20)

    def refrescar_checklist():
        """Vuelve a diagnosticar sin reconstruir toda la pantalla de Inicio."""
        if not _widget_vivo(marco_avisos):
            return
        for hijo in marco_avisos.winfo_children():
            hijo.destroy()
        tk.Label(
            marco_avisos,
            text="Analizando el equipo...",
            bg=preferencias.color_fondo(),
        ).pack(pady=20)
        en_hilo(self.area_central, analizar_equipo, al_terminar=pintar)

    def abrir_toplevel(factory):
        """Abre un Toplevel y, al cerrarlo, refresca el diagnostico de Inicio."""
        ventana = tk.Toplevel(self.area_central)
        factory(ventana)

        def al_destruir(event):
            if event.widget is not ventana:
                return
            if _widget_vivo(marco_avisos):
                # Diferir un tick: el Destroy aun esta en curso
                self.area_central.after(50, refrescar_checklist)

        ventana.bind("<Destroy>", al_destruir)
        return ventana

    def abrir_panel(nombre):
        clase = PANELES_DIAGNOSTICO.get(nombre)
        if clase is None:
            return
        abrir_toplevel(clase)

    def comando_item(item):
        accion = item.get("accion")
        panel = item.get("panel")
        destino = item.get("destino")
        if accion == "reiniciar":
            return lambda: _reiniciar_equipo(self.root)
        if panel and panel in PANELES_DIAGNOSTICO:
            return lambda p=panel: abrir_panel(p)
        if destino:
            return lambda d=destino: self.mostrar_subcategorias(d)
        return None

    def pintar(items):
        if not _widget_vivo(marco_avisos):
            return
        for hijo in marco_avisos.winfo_children():
            hijo.destroy()

        errores = sum(1 for i in items if i.get("nivel") == "error")
        avisos = sum(1 for i in items if i.get("nivel") == "aviso")
        if errores or avisos:
            partes = []
            if errores:
                partes.append(f"{errores} problema" + ("s" if errores != 1 else ""))
            if avisos:
                partes.append(f"{avisos} aviso" + ("s" if avisos != 1 else ""))
            texto_resumen = " · ".join(partes)
            color_resumen = COLORES_AVISO["error"][0] if errores else COLORES_AVISO["aviso"][0]
        else:
            texto_resumen = "Sin problemas detectados"
            color_resumen = COLORES_AVISO["ok"][0]
        tk.Label(
            marco_avisos,
            text=texto_resumen,
            font=("Arial", 11, "bold"),
            fg=color_resumen,
            bg=preferencias.color_fondo(),
        ).pack(anchor="w", pady=(0, 8))

        marco_botones = tk.Frame(marco_avisos, bg=preferencias.color_fondo())
        marco_botones.pack(side=tk.BOTTOM, pady=12)
        fila0 = tk.Frame(marco_botones, bg=preferencias.color_fondo())
        fila0.pack()
        fila1 = tk.Frame(marco_botones, bg=preferencias.color_fondo())
        fila1.pack(pady=(6, 0))
        fila2 = tk.Frame(marco_botones, bg=preferencias.color_fondo())
        fila2.pack(pady=(6, 0))
        con_tooltip(
            tk.Button(
                fila0,
                text="Que problema tienes?",
                command=lambda: abrir_toplevel(AsistenteProblemas),
                font=("Arial", 10, "bold"),
            ),
            "Asistente: elige Internet, sonido, impresora, espacio, arranque... y diagnostica solo eso",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(fila1, text="Analizar mi equipo", command=refrescar_checklist),
            "Vuelve a ejecutar el diagnóstico completo del equipo",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(
                fila1,
                text="Reparar Ubuntu",
                command=lambda: abrir_toplevel(RepararUbuntu),
            ),
            "Detecta fallos y ofrece reparaciones guiadas por tarjeta (qué, por qué, riesgos)",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(
                fila1,
                text="Liberar espacio",
                command=lambda: abrir_toplevel(LimpiezaEspacio),
            ),
            "Analiza qué ocupa el disco y limpia con perfil rápido o profundo",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(
                fila2,
                text="Actualizar todo",
                command=lambda: abrir_toplevel(ActualizarTodo),
            ),
            "Actualiza APT, Snap y Flatpak en un solo flujo",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(
                fila2,
                text="Informe de asistencia",
                command=lambda: abrir_toplevel(InformeAsistencia),
            ),
            "Genera un informe del diagnóstico y del equipo para enviárselo a quien te ayude",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(fila2, text="Ver registro de acciones", command=lambda: mostrar_registro(self.root)),
            "Muestra el historial de acciones realizadas en esta sesión y anteriores",
        ).pack(side=tk.LEFT, padx=6)

        marco_lista = tk.Frame(marco_avisos, bg=preferencias.color_fondo())
        marco_lista.pack(fill=tk.BOTH, expand=True)
        lienzo = tk.Canvas(marco_lista, bg=preferencias.color_fondo(), highlightthickness=0)
        scroll = ttk.Scrollbar(marco_lista, orient=tk.VERTICAL, command=lienzo.yview)
        interior = tk.Frame(lienzo, bg=preferencias.color_fondo())
        interior.bind(
            "<Configure>",
            lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")),
        )
        ventana_id = lienzo.create_window((0, 0), window=interior, anchor="nw")

        def _ajustar_ancho(event):
            lienzo.itemconfigure(ventana_id, width=event.width)

        lienzo.bind("<Configure>", _ajustar_ancho)
        lienzo.configure(yscrollcommand=scroll.set)
        lienzo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for item in items:
            fondo, frente = COLORES_AVISO.get(item["nivel"], COLORES_AVISO["info"])
            comando = comando_item(item)
            boton = tk.Button(
                interior,
                text=f"{item['titulo']}\n{item['detalle']}",
                bg=fondo,
                fg=frente,
                justify=tk.LEFT,
                anchor="w",
                wraplength=480,
                padx=12,
                pady=8,
                command=comando,
            )
            boton.pack(fill=tk.X, pady=5)
            if item.get("accion") == "reiniciar":
                ToolTip(boton, "Reinicia el equipo para terminar de aplicar las actualizaciones")
            elif item.get("panel"):
                ToolTip(boton, "Abre la herramienta relacionada con este resultado")
            elif item.get("destino"):
                ToolTip(boton, "Abre la categoría relacionada con este resultado")
            else:
                ToolTip(boton, item.get("detalle") or "Resultado informativo")

        preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

    en_hilo(self.area_central, analizar_equipo, al_terminar=pintar)
    preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)


def informacion_cat(self, mensaje_personalizado):
    """
Función informacion_cat.

Esta función se encarga de mostrar información en el área central de la interfaz gráfica.

Args:
    self: La instancia de la clase que llama a la función.
    mensaje_personalizado (str): Mensaje opcional que se mostrará en la interfaz.

Returns:
    No retorna ningún valor.

Steps:
    - Oculta todos los elementos en el área central.
    - Muestra el contenedor de texto para mostrar información.
    - Aplica el tema seleccionado a la nueva ventana si no es "Claro".
    - Actualiza el mensaje personalizado si existe, mostrándolo en un label.
    - Agrega una línea horizontal debajo del mensaje personalizado.
    - Muestra la información del sistema llamando a la función mostrar_informacion_sistema().
    - Empaqueta el contenedor de texto en el área central de la interfaz.
"""

    # Ocultar todos los elementos en el área central
    for widget in self.area_central.winfo_children():
        widget.destroy()

    # Mostrar el contenedor de texto para mostrar información
    self.contenedor_texto.pack(expand=True, fill="both", padx=10, pady=(20, 10))

    if preferencias.tema_seleccionado != "Claro":
        # Aplicar el tema seleccionado a la nueva ventana
        preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

    # Actualizar el mensaje personalizado si existe
    if mensaje_personalizado:
        label_subcategorias = tk.Label(self.area_central, text=mensaje_personalizado, font=("Arial", 16, "bold"), bg=preferencias.color_fondo(), padx=10, pady=20)
        
        if preferencias.tema_seleccionado != "Claro":
            # Aplicar el tema seleccionado al mensaje personalizado
            preferencias.cambiar_tema(label_subcategorias, preferencias.tema_seleccionado)
            label_subcategorias.config(bg=preferencias.color_fondo(), fg=preferencias.color_texto())

        label_subcategorias.pack()

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(self.area_central, width=500, height=2, bg=preferencias.color_fondo(), highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="black")
        self.canvas.pack(pady=1) 

    # Mostrar la información del sistema
    self.mostrar_informacion_sistema()

    marco_informe = tk.Frame(self.area_central, bg=preferencias.color_fondo())
    marco_informe.pack(pady=(6, 0))
    con_tooltip(
        tk.Button(marco_informe, text="Copiar informe", command=self.copiar_informe_sistema),
        "Copia el informe del sistema al portapapeles",
    ).pack(side=tk.LEFT, padx=6)
    con_tooltip(
        tk.Button(marco_informe, text="Exportar a .txt", command=self.exportar_informe_sistema),
        "Guarda el informe del sistema en un archivo de texto",
    ).pack(side=tk.LEFT, padx=6)
    con_tooltip(
        tk.Button(
            marco_informe,
            text="Informe de asistencia",
            command=lambda: InformeAsistencia(tk.Toplevel(self.area_central)),
        ),
        "Diagnóstico + datos del equipo para enviárselo a quien te ayude",
    ).pack(side=tk.LEFT, padx=6)
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(marco_informe, preferencias.tema_seleccionado)

    # Texto de información se muestre justo debajo de la línea
    self.texto_informacion.pack(expand=True, fill="both", padx=10, pady=(1, 30))  

    
def diccionario_cat(self, mensaje_personalizado):
    """Muestra la categoría Diccionario."""

    def aplicar_tema(widget):
        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(widget, preferencias.tema_seleccionado)
            if isinstance(widget, (tk.Label, tk.Button, tk.Entry, tk.Text, tk.Listbox)):
                widget.config(bg=preferencias.color_fondo(), fg=preferencias.color_texto())
            else:
                widget.config(bg=preferencias.color_fondo())

    def abrir_diccionario():
        contenido_html = cargar_contenido_html()
        abrir_ventana_diccionario(contenido_html)

    self.contenedor_texto.pack_forget()
    for widget in self.area_central.winfo_children():
        widget.destroy()

    if mensaje_personalizado:
        label_subcategorias = tk.Label(
            self.area_central, text=mensaje_personalizado,
            font=("Arial", 16, "bold"), bg=preferencias.color_fondo(), padx=10, pady=20
        )
    else:
        label_subcategorias = tk.Label(
            self.area_central, text="DICCIONARIO", font=("Arial", 12, "bold"), bg=preferencias.color_fondo()
        )
    aplicar_tema(label_subcategorias)
    label_subcategorias.pack()
    canvas_linea = tk.Canvas(self.area_central, width=500, height=2, bg=preferencias.color_fondo(), highlightthickness=0)
    canvas_linea.create_line(0, 1, 500, 1, fill="black")
    canvas_linea.pack(pady=10)

    boton_diccionario = tk.Button(self.area_central, text="Abrir diccionario GNU/Linux", command=abrir_diccionario)
    aplicar_tema(boton_diccionario)
    boton_diccionario.pack(pady=16)
    ToolTip(boton_diccionario, "Consulta comandos GNU/Linux (hace falta Internet)")
    aplicar_tema(self.area_central)

def _preparar_categoria(self, titulo, mensaje=None):
    """Limpia el área central, pone el título y deja un marco con desplazamiento."""
    self.contenedor_texto.pack_forget()
    for widget in self.area_central.winfo_children():
        widget.destroy()

    colores = preferencias.colores_de(preferencias.tema_seleccionado)
    fondo = colores["bg"]
    texto = colores["fg"]
    self.area_central.config(bg=fondo)

    tk.Label(
        self.area_central,
        text=titulo,
        font=preferencias.fuente_ui(18, "bold"),
        bg=fondo,
        fg=texto,
    ).pack(anchor="w", padx=20, pady=(16, 0))
    if mensaje:
        tk.Label(
            self.area_central,
            text=mensaje,
            font=preferencias.fuente_ui(11),
            bg=fondo,
            fg=texto,
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=20, pady=(2, 8))

    marco_scroll = tk.Frame(self.area_central, bg=fondo)
    marco_scroll.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))
    lienzo = tk.Canvas(marco_scroll, bg=fondo, highlightthickness=0, borderwidth=0)
    barra = ttk.Scrollbar(marco_scroll, orient="vertical", command=lienzo.yview)
    interior = tk.Frame(lienzo, bg=fondo)
    interior.bind("<Configure>", lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all")))
    ventana_interior = lienzo.create_window((0, 0), window=interior, anchor="nw")
    lienzo.configure(yscrollcommand=barra.set)
    lienzo.bind("<Configure>", lambda e: lienzo.itemconfigure(ventana_interior, width=e.width))
    lienzo.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    def _subir(_evento=None):
        lienzo.yview_scroll(-3, "units")

    def _bajar(_evento=None):
        lienzo.yview_scroll(3, "units")

    def _activar_rueda(_evento=None):
        lienzo.bind_all("<Button-4>", _subir)
        lienzo.bind_all("<Button-5>", _bajar)

    def _desactivar_rueda(_evento=None):
        lienzo.unbind_all("<Button-4>")
        lienzo.unbind_all("<Button-5>")

    marco_scroll.bind("<Enter>", _activar_rueda)
    marco_scroll.bind("<Leave>", _desactivar_rueda)
    marco_scroll.bind("<Destroy>", _desactivar_rueda)
    return colores, interior


def _boton_categoria(contenedor, colores, titulo, comando, ayuda):
    borde = colores.get("borde", colores.get("sidebar", colores["bg"]))
    hover = colores.get("hover", colores["bg"])
    boton = tk.Button(
        contenedor,
        text=titulo,
        command=comando,
        relief="flat",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=borde,
        highlightcolor=borde,
        bg=colores["base"],
        fg=colores["fg"],
        activebackground=hover,
        activeforeground=colores["fg"],
        font=preferencias.fuente_ui(10),
        padx=12,
        pady=8,
        cursor="hand2",
        anchor="w",
    )
    ToolTip(boton, ayuda)
    preferencias.aplicar_hover(
        boton,
        fondo_normal=colores["base"],
        fondo_hover=hover,
    )
    return boton


def _grupo_acciones(interior, colores, titulo, frase, acciones, columnas=2):
    """Dibuja un bloque con título, frase y botones en rejilla."""
    fondo = colores["bg"]
    texto = colores["fg"]
    bloque = tk.Frame(interior, bg=fondo)
    bloque.pack(fill="x", padx=12, pady=(10, 6))
    tk.Label(
        bloque,
        text=titulo,
        font=preferencias.fuente_ui(13, "bold"),
        bg=fondo,
        fg=texto,
        anchor="w",
    ).pack(anchor="w")
    if frase:
        tk.Label(
            bloque,
            text=frase,
            font=preferencias.fuente_ui(10),
            bg=fondo,
            fg=texto,
            anchor="w",
            wraplength=540,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 6))
    fila = tk.Frame(bloque, bg=fondo)
    fila.pack(anchor="w", fill="x")
    creados = {}
    for indice, (nombre, comando, ayuda) in enumerate(acciones):
        boton = _boton_categoria(fila, colores, nombre, comando, ayuda)
        boton.grid(
            row=indice // columnas,
            column=indice % columnas,
            padx=6,
            pady=5,
            sticky="ew",
        )
        creados[nombre] = boton
    for columna in range(columnas):
        fila.columnconfigure(columna, weight=1, uniform="acciones")
    return creados


def sistema_cat(self, mensaje_personalizado):
    """
    Función sistema_cat.

    Esta función se encarga de realizar diversas tareas en el sistema operativo a través de la interfaz gráfica.

    Args:
        self: La instancia de la clase que llama a la función.
        mensaje_personalizado (str): Mensaje opcional que se mostrará en la interfaz.

    Returns:
        No retorna ningún valor.

    Steps:
        - Oculta el contenedor de texto y destruye los elementos en el área central.
        - Crea un label con el mensaje personalizado o uno predeterminado si no se proporciona.
        - Crea botones para realizar distintas tareas del sistema.
    """

    colores, interior = _preparar_categoria(
        self, "Sistema", mensaje_personalizado or "Configuraciones y detalles del Sistema Operativo."
    )

    grupos = (
        (
            "Poner al día",
            "Instala, quita y actualiza programas.",
            (
                ("Actualizar Sistema", lambda: actualizar_sistema(self.root), "Instala todas las actualizaciones disponibles para la versión de tu sistema operativo"),
                ("Actualizar todo", lambda: ActualizarTodo(tk.Toplevel(self.area_central)), "Actualiza APT, Snap y Flatpak juntos, con el recuento de pendientes"),
                ("Centro de aplicaciones", lambda: CentroAplicaciones(tk.Toplevel(self.area_central)), "Lista APT, Snap y Flatpak: buscar, abrir, actualizar o desinstalar; muestra las que más ocupan"),
                ("Limpiar Caché", lambda: limpiar_cache(self.root), "Limpia la caché del sistema operativo"),
                ("Abrir Gestor Software", abrir_gestor_software, "Instala o desinstala paquetes snap desde el gestor de software de Ubuntu"),
                ("Instalar .deb", lambda: DebInstalador().ejecutar(self.root), "Selecciona e instala un paquete .deb usando dpkg"),
                ("Desinstalar Paquetes", lambda: DesinstalarPaquetes(tk.Toplevel(self.area_central)), "Desinstalar paquetes instalados por el usuario"),
                ("Gestiona Repositorios", lambda: Repositorios(tk.Toplevel(self.area_central)), "Gestiona los repositorios del sistema"),
            ),
        ),
        (
            "Espacio",
            "Mira qué ocupa el disco y libera lo que se puede borrar.",
            (
                ("Liberar espacio", lambda: LimpiezaEspacio(tk.Toplevel(self.area_central)), "Analiza qué ocupa el disco y limpia con perfil rápido o profundo: caché, papelera, snaps y kernels viejos"),
                ("Snap y Flatpak", lambda: SnapFlatpak(tk.Toplevel(self.area_central)), "Lista aplicaciones Snap y Flatpak, el espacio que usan, las actualiza o las quita (van aparte de APT)"),
                ("Espacio discos", lambda: EspacioDiscos(tk.Toplevel(self.area_central)), "Muestra el espacio ocupado de cada disco y las carpetas que más pesan"),
                ("Vaciar Papelera", Limpieza.vaciar_papelera, "Vacía la papelera de reciclaje del equipo"),
                ("Eliminar Archivo/s", Limpieza.eliminar_elemento, "Eliminar permanentemente archivos o carpetas del equipo"),
                ("Buscar Archivos Duplicados", lambda: AplicacionBuscadorDuplicados(tk.Toplevel(self.area_central)), "Abre una ventana buscar archivos duplicados en el sistema"),
            ),
        ),
        (
            "El equipo",
            "Procesos, discos, servicios y lo que protege el equipo.",
            (
                ("Administrar Procesos", lambda: AdministrarProcesos(tk.Toplevel(self.area_central)), "Abre una ventana para administrar los procesos del sistema"),
                ("Monitorizar", lambda: MonitorRecursos(tk.Toplevel(self.area_central)), "CPU, RAM, disco y temperatura con barras; procesos ordenables por consumo; Abrir o Finalizar con confirmacion"),
                ("Reparar Ubuntu", lambda: RepararUbuntu(tk.Toplevel(self.area_central)), "Continúa el diagnóstico: tarjetas por problema (APT, dpkg, cada servicio…) con confirmación guiada"),
                ("Servicios", lambda: ServiciosSystemd(tk.Toplevel(self.area_central)), "Inicia, detiene, habilita o deshabilita servicios systemd"),
                ("Servicios que fallan", lambda: ServiciosFallidos(tk.Toplevel(self.area_central)), "Lista unidades systemd en fallo, las reinicia o muestra un log corto"),
                ("Ver logs", lambda: consultaLogs(tk.Toplevel(self.area_central)), "Consulta los registros más importantes del sistema"),
                ("Salud discos", lambda: SaludDiscos(tk.Toplevel(self.area_central)), "Consulta el estado SMART, temperatura y avisos de los discos"),
                ("Centro de seguridad", lambda: CentroSeguridad(tk.Toplevel(self.area_central)), "Resumen de firewall, actualizaciones, usuario y puertos abiertos, con explicaciones claras"),
                ("Bluetooth", lambda: Bluetooth(tk.Toplevel(self.area_central)), "Lista dispositivos Bluetooth, olvida uno que no conecta o reinicia el servicio (como apagar y encender)"),
                ("Sonido", lambda: Sonido(tk.Toplevel(self.area_central)), "Reinicia el audio o cambia la salida (auriculares, HDMI) cuando no hay sonido"),
                ("Pantallas", lambda: Pantallas(tk.Toplevel(self.area_central)), "Detecta monitores o la TV: espejo, escritorio extendido o una sola pantalla"),
                ("Impresoras", lambda: Impresoras(tk.Toplevel(self.area_central)), "Busca impresoras USB o de la red local y las colas ya instaladas en CUPS"),
            ),
        ),
        (
            "Al arrancar y repetir",
            "Qué se abre al iniciar sesión, y acciones que ya habías hecho.",
            (
                ("Aplicaciones Inicio", lambda: AplicacionesAutostart(tk.Toplevel(self.area_central)), "Añade o elimina aplicaciones que se ejecuten al arrancar el equipo. Permite archivos .desktop"),
                ("Por que tarda en arrancar?", lambda: AnalisisArranque(tk.Toplevel(self.area_central)), "Muestra tiempos de arranque (firmware, kernel, userspace) y los servicios mas lentos, con explicaciones"),
                ("Historial comandos", lambda: mostrar_historial_comandos(self.root), "Repite limpiezas y otras acciones ya ejecutadas desde la aplicación"),
            ),
        ),
    )
    for titulo, frase, acciones in grupos:
        _grupo_acciones(interior, colores, titulo, frase, acciones)
    
# Función para mostrar la categoría INTERNET
def internet_cat(self, mensaje_personalizado, entry_url=None):
    """Categoría Internet: conexión, ajustes y herramientas de red."""
    colores, interior = _preparar_categoria(
        self,
        "Internet",
        mensaje_personalizado or "Configuraciones y detalles sobre la conexión a Internet.",
    )
    fondo = colores["bg"]
    texto = colores["fg"]

    informacion = Informacion()
    interfaces_red = informacion.obtener_interfaces_red()
    if not interfaces_red:
        tk.Label(
            interior,
            text="No se encontraron interfaces de red disponibles.",
            font=preferencias.fuente_ui(12, "bold"),
            bg=fondo,
            fg=texto,
        ).pack(anchor="w", padx=12, pady=20)
        return

    bloque = tk.Frame(interior, bg=fondo)
    bloque.pack(fill="x", padx=12, pady=(10, 6))
    tk.Label(
        bloque,
        text="Conexión",
        font=preferencias.fuente_ui(13, "bold"),
        bg=fondo,
        fg=texto,
        anchor="w",
    ).pack(anchor="w")
    tk.Label(
        bloque,
        text="Elige la tarjeta de red y comprueba si responde.",
        font=preferencias.fuente_ui(10),
        bg=fondo,
        fg=texto,
        anchor="w",
    ).pack(anchor="w", pady=(0, 6))

    seleccion_interfaz = tk.StringVar()
    fila_if = tk.Frame(bloque, bg=fondo)
    fila_if.pack(anchor="w", fill="x", pady=2)
    tk.Label(fila_if, text="Interfaz", bg=fondo, fg=texto, font=preferencias.fuente_ui(10)).pack(side=tk.LEFT)
    combobox_interfaz = ttk.Combobox(
        fila_if, textvariable=seleccion_interfaz, values=interfaces_red, state="readonly", width=28
    )
    combobox_interfaz.pack(side=tk.LEFT, padx=8)
    if interfaces_red:
        combobox_interfaz.current(0)

    def reiniciar_tarjeta_seleccionada():
        reiniciar_tarjeta_red(seleccion_interfaz.get(), parent=self.root)

    _boton_categoria(
        bloque,
        colores,
        "Tengo problemas con Internet",
        lambda: AsistenteInternet(tk.Toplevel(self.root)),
        "Analiza adaptador, router, DNS, Internet, latencia y perdida; propone una solucion",
    ).pack(anchor="w", pady=6, fill="x")

    _boton_categoria(
        bloque,
        colores,
        "Reiniciar Tarjeta de Red",
        reiniciar_tarjeta_seleccionada,
        "Reinicia la tarjeta de red. Tras unos segundos se volverá a iniciar automáticamente",
    ).pack(anchor="w", pady=6, fill="x")

    fila_ping = tk.Frame(bloque, bg=fondo)
    fila_ping.pack(anchor="w", fill="x", pady=(8, 2))
    tk.Label(fila_ping, text="URL o host", bg=fondo, fg=texto, font=preferencias.fuente_ui(10)).pack(side=tk.LEFT)
    entry_url_local = tk.Entry(fila_ping, width=36)
    entry_url_local.pack(side=tk.LEFT, padx=8)
    _boton_categoria(
        fila_ping,
        colores,
        "Hacer Ping",
        lambda: hacer_ping(entry_url_local),
        "Hacer ping a una URL",
    ).pack(side=tk.LEFT, padx=4)

    ajustes = [
        ("Redes Wi-Fi", lambda: RedesWifi(tk.Toplevel(self.root)), "Lista, conecta o desconecta redes Wi-Fi con nmcli"),
        ("DNS", lambda: SelectorDns(tk.Toplevel(self.root)), "Cambia el DNS de la conexión activa (router, Cloudflare o Google)"),
        ("Hosts locales", lambda: EditorHosts(tk.Toplevel(self.root)), "Edita /etc/hosts (se crea una copia de seguridad al guardar)"),
    ]
    if expressvpn_disponible():
        ajustes.append(
            ("VPN", lambda: PanelExpressVPN(tk.Toplevel(self.root)), "Estado, región, protocolo y bloqueo de red de ExpressVPN")
        )
    _grupo_acciones(interior, colores, "Ajustes de red", "Wi-Fi, DNS, hosts y VPN si está instalada.", ajustes)

    red_tools = RedTools(self.root)
    red_tools.set_area_central(self.area_central)
    _grupo_acciones(
        interior,
        colores,
        "Herramientas",
        "Comprueba puertos, velocidad y posibles fallos de la conexión.",
        (
            ("Escanear Puertos", lambda: red_tools.escanear_puertos(), "Escanea los puertos de una IP específica"),
            ("Puerto desde Internet", lambda: PuertoDesdeInternet(tk.Toplevel(self.root)), "Comprueba si un puerto de este PC es alcanzable desde fuera (con aviso de riesgos)"),
            ("Test Velocidad", red_tools.test_velocidad, "Mide la velocidad de descarga y carga de la conexión a Internet"),
            ("Diagnóstico Red", red_tools.diagnostico_red, "Diagnostica problemas de conectividad de red con traceroute y netstat"),
            (
                "Nivel de ruido",
                lambda: red_tools.nivel_ruido(seleccion_interfaz.get()),
                "Mide el ruido de radio del Wi-Fi (SNR) y el jitter/pérdida de paquetes hacia Internet",
            ),
        ),
    )


def red_local_cat(self, mensaje_personalizado):
    """Categoría Red Local: buscar equipos, compartir y encender."""
    colores, interior = _preparar_categoria(
        self,
        "Red Local",
        mensaje_personalizado or "Configuraciones y acciones sobre la red local.",
    )
    fondo = colores["bg"]
    texto = colores["fg"]

    zona_resultados = tk.Frame(interior, bg=fondo)

    def buscar_equipos_red_local():
        boton_buscar.config(state="disabled")
        for hijo in zona_resultados.winfo_children():
            hijo.destroy()
        mensaje_busqueda = tk.Label(
            zona_resultados,
            text="Buscando equipos en la red local...",
            bg=fondo,
            fg=texto,
            font=preferencias.fuente_ui(10),
        )
        mensaje_busqueda.pack(pady=8)
        preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        def mostrar(dispositivos):
            if not _widget_vivo(zona_resultados):
                return
            for hijo in zona_resultados.winfo_children():
                hijo.destroy()
            tk.Label(
                zona_resultados,
                text="Quién hay en tu red (Wi-Fi o cable):",
                font=preferencias.fuente_ui(12, "bold"),
                bg=fondo,
                fg=texto,
            ).pack(anchor="w")
            if dispositivos:
                self.lista_dispositivos = tk.Listbox(
                    zona_resultados, width=88, height=12, font=("monospace", 9)
                )
                self.lista_dispositivos.pack(padx=4, pady=6, fill="both", expand=True)
                self.lista_dispositivos.dispositivos = dispositivos
                for dispositivo in dispositivos:
                    if isinstance(dispositivo, dict):
                        self.lista_dispositivos.insert(tk.END, formatear_dispositivo(dispositivo))
                    else:
                        self.lista_dispositivos.insert(tk.END, dispositivo)
                self.lista_dispositivos.bind(
                    "<Double-1>", lambda event: doble_clic(event, self.lista_dispositivos)
                )
            else:
                messagebox.showinfo("Buscar Equipos", "No se encontraron dispositivos en la red local.")
            recordar_equipos(dispositivos)
            tk.Label(
                zona_resultados,
                text=(
                    "IP, nombre, MAC y si comparte Samba. Doble clic abre smb:// si está disponible. "
                    "Es la forma fiable de ver quién hay en la red sin entrar en el router; "
                    "el listado del router solo está en la web del fabricante."
                ),
                font=preferencias.fuente_ui(9),
                bg=fondo,
                fg=texto,
                wraplength=720,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=(0, 4))
            boton_buscar.config(state="normal")
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        en_hilo(self.area_central, encontrar_dispositivos_en_red, al_terminar=mostrar)

    creados = _grupo_acciones(
        interior,
        colores,
        "En la red de casa",
        "Quién hay en la red, si el router responde, compartir carpeta o encender un PC.",
        (
            ("Quién hay en la red", buscar_equipos_red_local, "Lista quién hay en tu red (Wi-Fi o cable); no hace falta entrar en el router"),
            ("¿Responde el router?", lambda: RouterCasa(tk.Toplevel(self.area_central)), "Hace ping al router de casa y puede abrir su página de configuración"),
            ("Compartir carpeta", lambda: CompartirCarpeta(tk.Toplevel(self.area_central)), "Comparte una carpeta para que otro equipo de casa la vea"),
            ("Encender un PC", lambda: EncenderPC(tk.Toplevel(self.area_central)), "Enciende un equipo apagado de la red si su placa lo permite"),
        ),
    )
    boton_buscar = creados["Quién hay en la red"]
    zona_resultados.pack(fill="both", expand=True, padx=12, pady=(4, 8))


def navegadores_cat(self, mensaje_personalizado):
    """Categoría Navegadores: abrir, instalar y limpiar."""
    colores, interior = _preparar_categoria(
        self,
        "Navegadores",
        mensaje_personalizado or "Acciones con los navegadores web.",
    )

    def abrir_chrome():
        try:
            subprocess.run(["google-chrome"])
        except Exception as error:
            print(f"Error al abrir Chrome: {error}")

    def abrir_firefox():
        try:
            subprocess.run(["firefox"])
        except Exception as error:
            print(f"Error al abrir Firefox: {error}")

    def abrir_edge():
        try:
            subprocess.run(["microsoft-edge"])
        except Exception as error:
            print(f"Error al abrir Edge: {error}")

    def abrir_chrome_incognito():
        try:
            subprocess.run(["google-chrome", "--incognito"])
        except Exception as error:
            print(f"Error al abrir Chrome: {error}")

    def abrir_firefox_incognito():
        try:
            subprocess.run(["firefox", "--private-window"])
        except Exception as error:
            print(f"Error al abrir Firefox: {error}")

    def abrir_edge_incognito():
        try:
            subprocess.run(["microsoft-edge", "--inprivate"])
        except Exception as error:
            print(f"Error al abrir Edge: {error}")

    def abrir_chromium(privado=False):
        extra = ["--incognito"] if privado else []
        for binario in ("chromium-browser", "chromium"):
            if os.path.exists(f"/usr/bin/{binario}"):
                abrir_navegador([binario, *extra], "Chromium")
                return
        abrir_navegador(["chromium-browser", *extra], "Chromium")

    _grupo_acciones(
        interior,
        colores,
        "Abrir",
        "Abre el navegador en normal o en privado.",
        (
            ("Chrome", abrir_chrome, "Abrir Google Chrome"),
            ("Firefox", abrir_firefox, "Abrir Mozilla Firefox"),
            ("Edge", abrir_edge, "Abrir Microsoft Edge"),
            ("Brave", lambda: abrir_navegador(["brave-browser"], "Brave"), "Abre Brave si está instalado"),
            ("Chromium", lambda: abrir_chromium(), "Abre Chromium si está instalado"),
            ("Vivaldi", lambda: abrir_navegador(["vivaldi"], "Vivaldi"), "Abre Vivaldi si está instalado"),
            ("Chrome Incognito", abrir_chrome_incognito, "Abrir Google Chrome en modo incógnito"),
            ("Firefox privado", abrir_firefox_incognito, "Abrir Mozilla Firefox en modo privado"),
            ("Edge InPrivate", abrir_edge_incognito, "Abrir Microsoft Edge en modo InPrivate"),
            ("Brave privado", lambda: abrir_navegador(["brave-browser", "--incognito"], "Brave"), "Abre Brave en modo privado"),
            ("Chromium privado", lambda: abrir_chromium(True), "Abre Chromium en modo incógnito"),
            ("Vivaldi privado", lambda: abrir_navegador(["vivaldi", "--incognito"], "Vivaldi"), "Abre Vivaldi en modo privado"),
        ),
        columnas=3,
    )

    _grupo_acciones(
        interior,
        colores,
        "Instalar",
        "Instala el navegador si todavía no está en el equipo.",
        (
            ("Instalar Chrome", InstalarNavegadores.instalar_chrome, "Instalar Google Chrome"),
            ("Instalar Firefox", InstalarNavegadores.instalar_firefox, "Instalar Mozilla Firefox"),
            ("Instalar Edge", InstalarNavegadores.instalar_edge, "Instalar Microsoft Edge"),
            ("Instalar Brave", lambda: InstalarNavegadoresExtra.instalar_brave(self.root), "Instala Brave desde su repositorio oficial"),
            ("Instalar Chromium", lambda: InstalarNavegadoresExtra.instalar_chromium(self.root), "Instala Chromium desde los repositorios de Ubuntu"),
            ("Instalar Vivaldi", lambda: InstalarNavegadoresExtra.instalar_vivaldi(self.root), "Instala Vivaldi desde su repositorio oficial"),
        ),
    )

    refs = {}

    def limpia(clave, funcion):
        def _comando():
            funcion(self, refs[clave], lambda mensaje: messagebox.showinfo("Resultado", mensaje))
        return _comando

    creados = _grupo_acciones(
        interior,
        colores,
        "Limpiar",
        "Borra caché o historial del navegador, si está instalado.",
        (
            ("Caché Chrome", limpia("chrome", LimpiadorNavegadores.limpiar_cache_chrome), "Limpia la caché de Chrome (si está instalado)"),
            ("Caché Firefox", limpia("firefox", LimpiadorNavegadores.limpiar_cache_firefox), "Limpia la caché de Firefox (si está instalado)"),
            ("Caché Edge", limpia("edge", LimpiadorNavegadores.limpiar_cache_edge), "Limpia la caché de Edge (si está instalado)"),
            ("Caché Brave", lambda: _limpiar_directorio("~/.cache/BraveSoftware", "Brave"), "Borra la caché de Brave (si está instalado)"),
            ("Caché Chromium", lambda: _limpiar_directorio("~/.cache/chromium", "Chromium"), "Borra la caché de Chromium (si está instalado)"),
            ("Caché Vivaldi", lambda: _limpiar_directorio("~/.cache/vivaldi", "Vivaldi"), "Borra la caché de Vivaldi (si está instalado)"),
            ("Historial Chrome", LimpiadorNavegadores.limpiar_historial_chrome, "Limpia el historial de Chrome (si está instalado)"),
            ("Historial Firefox", LimpiadorNavegadores.limpiar_historial_firefox, "Limpia el historial de Firefox (si está instalado)"),
            ("Historial Edge", LimpiadorNavegadores.limpiar_historial_edge, "Limpia el historial de Edge (si está instalado)"),
        ),
    )
    refs["chrome"] = creados["Caché Chrome"]
    refs["firefox"] = creados["Caché Firefox"]
    refs["edge"] = creados["Caché Edge"]

    _grupo_acciones(
        interior,
        colores,
        "Perfiles",
        "Consulta perfiles locales y exporta marcadores.",
        (
            ("Perfiles y marcadores", lambda: PerfilesNavegadores(tk.Toplevel(self.root)), "Lista perfiles de navegador y exporta marcadores a HTML"),
        ),
        columnas=1,
    )


def archivos_cat(self, mensaje_personalizado):
    """Categoría Archivos: copias, cifrado, búsqueda y utilidades."""
    colores, interior = _preparar_categoria(
        self,
        "Archivos",
        mensaje_personalizado or "Opciones sobre archivos del Sistema Operativo",
    )

    def restaurar_copia_seguridad():
        directorio_home = os.path.expanduser("~")
        destino = filedialog.askdirectory(title="Seleccionar carpeta de destino", initialdir=directorio_home)
        if not destino:
            messagebox.showwarning("Advertencia", "Al no seleccionar la carpeta de destino, se aborta la restauración de la copia de seguridad.")
            return
        origen = filedialog.askopenfilename(
            title="Seleccionar archivo de copia de seguridad",
            initialdir=directorio_home,
            filetypes=(("Archivos comprimidos", "*.gz"), ("Todos los archivos", "*.*")),
        )
        if not origen:
            messagebox.showwarning("Advertencia", "Al no seleccionar el archivo .gz a restaurar, se aborta la restauración de la copia de seguridad.")
            return
        if not confirmar(
            f"¿Restaurar la copia\n{origen}\nen\n{destino}?\nSe pueden sobrescribir archivos.",
            self.root,
        ):
            return
        progreso, _et = ventana_progreso(self.root, "Restaurar Copia", "Extrayendo archivo .gz...")

        def trabajador():
            return RestaurarCopiaSeguridad(origen, destino).restaurar_copia_seguridad()

        def terminar(_ok):
            if progreso.winfo_exists():
                progreso.destroy()
            messagebox.showinfo("Restaurar Copia de Seguridad", "Copia de seguridad restaurada con éxito.")

        en_hilo(self.root, trabajador, al_terminar=terminar)

    def abrir_ventana_busqueda():
        FileSearchApp(tk.Toplevel())

    def abrir_ventana_renombrado():
        BulkRenameApp(tk.Toplevel())

    _grupo_acciones(
        interior,
        colores,
        "Copias",
        "Copia Documentos o el escritorio a un USB, o restaura un .gz antiguo.",
        (
            ("Copiar A Un USB", lambda: CopiaUSB(tk.Toplevel(self.area_central)), "Copia Documentos o el escritorio a un USB, en una carpeta con la fecha en el nombre"),
            ("Restaurar Copia de Seguridad", restaurar_copia_seguridad, "Restaurar una copia de seguridad"),
        ),
    )
    _grupo_acciones(
        interior,
        colores,
        "Proteger",
        "Cifra o descifra archivos.",
        (
            ("Cifrar Archivos", cifrar_archivo, "Cifrar Archivos"),
            ("Descifrar Archivos", descifrar_archivo, "Descifrar Archivos"),
        ),
    )
    _grupo_acciones(
        interior,
        colores,
        "Organizar",
        "Busca, renombra y revisa permisos.",
        (
            ("Busca archivos", abrir_ventana_busqueda, "Busca archivos en el sistema"),
            ("Renombrar archivos", abrir_ventana_renombrado, "Renombrar archivos de forma masiva"),
            ("Permisos / propietario", lambda: PermisosArchivos(tk.Toplevel(self.root)), "Cambia permisos (chmod) y propietario (chown) de un archivo o carpeta"),
            ("USB / discos", lambda: DispositivosBloque(tk.Toplevel(self.root)), "Monta o desmonta USB y otros discos de bloque"),
        ),
    )
    _grupo_acciones(
        interior,
        colores,
        "Comprobar y liberar",
        "Archivos grandes e integridad de descargas.",
        (
            ("Archivos grandes", lambda: ArchivosGrandes(tk.Toplevel(self.root)), "Busca ISO, archivos grandes y descargas antiguas para liberar espacio"),
            ("Hash MD5/SHA", lambda: HashArchivo(tk.Toplevel(self.root)), "Calcula MD5, SHA-1 y SHA-256 para comprobar una descarga"),
        ),
    )


def perfil_cat(self, mensaje_personalizado):
    """Perfil de usuario con desplazamiento vertical y carpeta personal."""

    def aplicar_tema(widget):
        """Aplica el tema seleccionado a un widget si el tema no es 'Claro'."""
        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(widget, preferencias.tema_seleccionado)
            if isinstance(widget, (tk.Label, tk.Button, tk.Entry, tk.Text, tk.Listbox)):
                widget.config(bg=preferencias.color_fondo(), fg=preferencias.color_texto())
            else:
                widget.config(bg=preferencias.color_fondo())

    def abrir_ventana_perfil():
        ventana_perfil = tk.Toplevel(self.area_central)
        PerfilUsuario(ventana_perfil)
        aplicar_tema(ventana_perfil)

    colores, interior = _preparar_categoria(
        self,
        "Perfil Usuario",
        mensaje_personalizado
        or "Tu cuenta, idioma, region y carpeta personal.",
    )
    fondo = colores["bg"]
    panel_perfil, foto_perfil = crear_panel_perfil(interior, fondo=fondo)
    self._perfil_foto_tk = foto_perfil
    aplicar_tema(panel_perfil)
    panel_perfil.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

    frame_botones_perfil = tk.Frame(interior, bg=fondo)
    aplicar_tema(frame_botones_perfil)
    frame_botones_perfil.pack(pady=(4, 16), padx=12, anchor="w")

    boton_perfil = tk.Button(
        frame_botones_perfil,
        text="Modificar Perfil Usuario",
        width=24,
        command=abrir_ventana_perfil,
    )
    aplicar_tema(boton_perfil)
    boton_perfil.pack(side=tk.LEFT, padx=5, pady=5)
    ToolTip(boton_perfil, "Modifica el nombre visible o la imagen de perfil")

def notas_cat(self, mensaje_personalizado):
    """
    Función notas_cat.

    Esta función muestra la pantalla de la categoría "Notas" en la interfaz gráfica.

    Args:
        self: La instancia de la clase que llama a la función.
        mensaje_personalizado (str): Mensaje opcional que se mostrará en la interfaz.

    Returns:
        No retorna ningún valor.

    Steps:
        - Limpia el área central de la interfaz gráfica.
        - Crea un label con el mensaje personalizado o uno predeterminado si no se proporciona, seguido de una línea horizontal.
        - Crea un botón para lanzar el editor de texto desde cat_editorTexto.py
    """

    def aplicar_tema(widget):
        """Aplica el tema seleccionado a un widget si el tema no es 'Claro'."""
        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(widget, preferencias.tema_seleccionado)
            if isinstance(widget, (tk.Label, tk.Button, tk.Entry, tk.Text, tk.Listbox)):
                widget.config(bg=preferencias.color_fondo(), fg=preferencias.color_texto())
            else:
                widget.config(bg=preferencias.color_fondo())

    def crear_label_y_linea(mensaje, font_size, padding):
        """Crea un label con un mensaje y dibuja una línea horizontal."""
        label = tk.Label(self.area_central, text=mensaje, font=("Arial", font_size, "bold"), bg=preferencias.color_fondo(), padx=10, pady=padding)
        aplicar_tema(label)
        label.pack()
        
        canvas_linea = tk.Canvas(self.area_central, width=500, height=2, bg=preferencias.color_fondo(), highlightthickness=0)
        canvas_linea.create_line(0, 1, 500, 1, fill="black")
        aplicar_tema(canvas_linea)
        canvas_linea.pack(pady=10)

    def abrir_ventana_toma_notas(ruta=None):
        ventana_notas = tk.Toplevel(self.area_central)
        EditorTextos(ventana_notas, ruta_inicial=ruta)

    def abrir_seleccionada():
        notas = getattr(lista, "notas", [])
        seleccion = lista.curselection()
        if not notas or not seleccion:
            messagebox.showinfo("Notas", "Selecciona una nota de la lista.")
            return
        abrir_ventana_toma_notas(notas[seleccion[0]][1])

    def rellenar_notas():
        lista.delete(0, tk.END)
        notas = listar_notas()
        lista.notas = notas
        if not notas:
            lista.insert(tk.END, "Todavía no hay notas en la carpeta del usuario.")
            return
        for _mtime, _ruta, nombre in notas:
            lista.insert(tk.END, nombre)

    # Limpiar el área central
    self.contenedor_texto.pack_forget()
    for widget in self.area_central.winfo_children():
        widget.destroy()

    # Crear el label con el mensaje personalizado o un mensaje predeterminado
    if mensaje_personalizado:
        crear_label_y_linea(mensaje_personalizado, 16, 20)
    else:
        crear_label_y_linea("TOMA NOTAS", 12, 0)

    tk.Label(
        self.area_central,
        text=f"Carpeta: {carpeta_notas()}",
        bg=preferencias.color_fondo(),
        font=("Arial", 9),
    ).pack(pady=(0, 6))

    frame_botones_notas = tk.Frame(self.area_central, bg=preferencias.color_fondo())
    aplicar_tema(frame_botones_notas)
    frame_botones_notas.pack()

    boton_tomar_notas = tk.Button(
        frame_botones_notas,
        text="Nueva nota",
        command=lambda: abrir_ventana_toma_notas(),
    )
    aplicar_tema(boton_tomar_notas)
    boton_tomar_notas.pack(side=tk.LEFT, padx=6, pady=8)
    ToolTip(boton_tomar_notas, "Crea una nota. Se guarda en la carpeta fija del usuario")

    boton_abrir = tk.Button(frame_botones_notas, text="Abrir seleccionada", command=abrir_seleccionada)
    aplicar_tema(boton_abrir)
    boton_abrir.pack(side=tk.LEFT, padx=6, pady=8)
    ToolTip(boton_abrir, "Abre la nota seleccionada en el editor")

    boton_actualizar = tk.Button(frame_botones_notas, text="Actualizar lista", command=rellenar_notas)
    aplicar_tema(boton_actualizar)
    boton_actualizar.pack(side=tk.LEFT, padx=6, pady=8)
    ToolTip(boton_actualizar, "Vuelve a leer las notas de la carpeta fija del usuario")

    tk.Label(
        self.area_central,
        text="Últimas notas",
        bg=preferencias.color_fondo(),
        font=("Arial", 11, "bold"),
    ).pack(pady=(8, 4))
    lista = tk.Listbox(self.area_central, height=12)
    lista.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
    lista.bind("<Double-Button-1>", lambda _e: abrir_seleccionada())
    lista.notas = []
    aplicar_tema(lista)
    rellenar_notas()
    