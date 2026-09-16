"""Ventana de documentación de las opciones de Manten1d0."""

import tkinter as tk
from tkinter import ttk

import preferencias

SECCIONES = (
    (
        "Presentación",
        "Manten1d0 es un programa de mantenimiento para Ubuntu. El menú lateral "
        "agrupa las herramientas por categoría. El menú superior da acceso a "
        "terminal, navegador, preferencias, registro de acciones y esta ayuda.\n\n"
        "Muchas acciones sensibles (actualizar el sistema, sudo, detener servicios) "
        "piden confirmación y quedan anotadas en el registro. La interfaz no debería "
        "quedarse bloqueada mientras una tarea larga termina.\n\n"
        "Elige una sección a la izquierda para ver qué permite hacer cada parte del programa.",
    ),
    (
        "Menú Archivo",
        "Abrir Terminal (Ctrl+Alt+T): lanza la terminal predeterminada (gnome-terminal).\n\n"
        "Abrir URL en Navegador: pide una dirección y la abre en el navegador del sistema.\n\n"
        "Salir: cierra Manten1d0.",
    ),
    (
        "Menú Preferencias",
        "Repositorio GitHub: abre el repositorio del proyecto en el navegador.\n\n"
        "Buscar Actualizaciones: comprueba si hay una versión nueva del programa.\n\n"
        "Opciones: cambia el tema (claro u oscuro) y el tamaño del texto.\n\n"
        "Registro de acciones: muestra el historial de operaciones realizadas "
        "(sin guardar la contraseña de sudo).\n\n"
        "Atajos de teclado: resumen de Alt+1 a Alt+0 para saltar entre categorías.",
    ),
    (
        "Atajos",
        "Alt+1  Inicio\n"
        "Alt+2  Perfil Usuario\n"
        "Alt+3  Información\n"
        "Alt+4  Sistema\n"
        "Alt+5  Archivos\n"
        "Alt+6  Internet\n"
        "Alt+7  Red Local\n"
        "Alt+8  Navegadores\n"
        "Alt+9  Diccionario\n"
        "Alt+0  Notas",
    ),
    (
        "Inicio",
        "Panel de estado del equipo. Muestra el logo, avisos y accesos rápidos.\n\n"
        "Avisos que puede mostrar:\n"
        "• Conexión a Internet caída.\n"
        "• Disco raíz o carpeta personal por encima del 80 % (aviso) o del 90 % (crítico).\n"
        "• Actualizaciones de APT pendientes, incluidas las de seguridad.\n"
        "• Problemas SMART en los discos (si smartctl está disponible).\n\n"
        "Al pulsar un aviso se abre la categoría relacionada.\n"
        "Actualizar avisos vuelve a comprobar el estado.\n"
        "Ver registro de acciones abre el mismo historial que Preferencias.",
    ),
    (
        "Perfil Usuario",
        "Muestra los datos actuales de la cuenta: foto, usuario, nombre visible, "
        "carpeta personal, intérprete y grupos.\n\n"
        "Modificar Perfil Usuario abre un formulario con esos datos ya rellenados. "
        "Se puede cambiar:\n"
        "• Nombre visible (campo GECOS).\n"
        "• Imagen de perfil.\n"
        "• Contraseña (déjala vacía si no quieres cambiarla).\n\n"
        "El nombre de usuario de login no se modifica desde aquí. Guardar puede "
        "pedir privilegios de administrador y, si lo deseas, reiniciar la sesión.",
    ),
    (
        "Información",
        "Consulta de solo lectura sobre el equipo: usuario, sistema, versión de Ubuntu, "
        "escritorio, tiempo encendido, tiempo de arranque (systemd-analyze), gráfica, "
        "interfaces de red, IP local y pública, DNS, procesador, memoria, zona horaria "
        "y temperatura de CPU si está disponible.\n\n"
        "La gráfica se detecta con lspci y sysfs para Intel, AMD y NVIDIA. nvidia-smi "
        "solo se usa si hay una GPU NVIDIA; el resto no depende de ella.\n\n"
        "Copiar informe deja el texto en el portapapeles. Exportar a .txt lo guarda en un archivo.",
    ),
    (
        "Sistema",
        "Herramientas de mantenimiento del sistema operativo:\n\n"
        "Actualizar Sistema: instala las actualizaciones APT disponibles.\n"
        "Limpiar Caché: vacía la caché de paquetes.\n"
        "Abrir Gestor Software: lanza el centro de software de Ubuntu (snaps).\n"
        "Aplicaciones Inicio: añade o quita programas que arrancan con la sesión (.desktop).\n"
        "Eliminar Archivo/s: borra archivos o carpetas de forma permanente.\n"
        "Vaciar Papelera: vacía la papelera del usuario.\n"
        "Administrar Procesos: lista procesos y permite gestionarlos.\n"
        "Buscar Archivos Duplicados: localiza ficheros repetidos para liberar espacio.\n"
        "Gestiona Repositorios: añade, quita o edita repositorios y PPA.\n"
        "Monitorizar: gráfico del uso de CPU, memoria, disco y red en ese momento.\n"
        "Instalar .deb: elige un paquete .deb e instálalo con dpkg.\n"
        "Desinstalar Paquetes: quita paquetes instalados por el usuario.\n"
        "Ver logs: consulta registros importantes del sistema.\n"
        "Limpieza disco: analiza y puede liberar caché APT, journal, miniaturas, "
        "papelera y snaps antiguos.\n"
        "Salud discos: estado SMART, temperatura y avisos de fallo.\n"
        "Servicios: iniciar, detener, reiniciar, habilitar o deshabilitar unidades systemd.\n"
        "Historial comandos: lista las limpiezas y acciones ya ejecutadas para repetirlas "
        "con confirmación. No guarda la contraseña de sudo.\n"
        "Impresoras: busca impresoras enchufadas por USB o anunciadas en la red local "
        "(mDNS/CUPS), lista las colas instaladas, envía una página de prueba y abre "
        "la configuración de impresoras del sistema.",
    ),
    (
        "Archivos",
        "Copia de Seguridad: comprime una carpeta en un archivo .gz.\n"
        "Restaurar Copia de Seguridad: extrae un .gz en la carpeta que elijas "
        "(puede sobrescribir archivos).\n\n"
        "Cifrar Archivos / Descifrar Archivos: protege o recupera ficheros con cifrado.\n\n"
        "Busca archivos: localiza ficheros en el sistema por nombre.\n"
        "Renombrar archivos: cambia el nombre de muchos ficheros a la vez.\n\n"
        "Permisos / propietario: chmod y chown con casillas o modo octal, opcionalmente recursivo.\n"
        "USB / discos: lista dispositivos de bloque y monta o desmonta USB (udisksctl).\n"
        "Archivos grandes: encuentra ficheros pesados, .iso y descargas antiguas para enviarlas a la papelera.\n"
        "Hash MD5/SHA: calcula MD5, SHA-1 y SHA-256 y los compara con el hash de una descarga.",
    ),
    (
        "Internet",
        "Selecciona una interfaz de red para trabajar con ella.\n\n"
        "Reiniciar Tarjeta de Red: baja y vuelve a levantar la interfaz (pide confirmación).\n"
        "Hacer Ping: comprueba si una URL o host responde.\n"
        "Redes Wi-Fi: lista redes con nmcli, conecta (pidiendo clave si hace falta) o desconecta.\n"
        "DNS: cambia entre el automático del router, Cloudflare 1.1.1.1 o Google 8.8.8.8.\n"
        "Hosts locales: edita /etc/hosts con validación y copia de seguridad.\n"
        "Escanear Puertos: revisa puertos abiertos de una IP.\n"
        "Test Velocidad: mide descarga y subida de la conexión.\n"
        "Diagnóstico Red: traceroute y netstat para ver por dónde falla la conectividad.\n"
        "Nivel de ruido: en Wi-Fi lee señal y ruido de radio (SNR). En cualquier conexión "
        "mide pérdida de paquetes y jitter hacia Internet. En cable muestra errores del adaptador.\n\n"
        "El indicador del menú lateral muestra si hay conexión a Internet.",
    ),
    (
        "Red Local",
        "Buscar Equipos en Red Local recorre la red y lista cada dispositivo con IP, "
        "nombre, MAC y si comparte Samba (puertos 139/445).\n\n"
        "Haz doble clic en un equipo para abrir smb:// en el administrador de archivos "
        "si el servicio está disponible.",
    ),
    (
        "Navegadores",
        "Abrir Chrome, Firefox o Edge en modo normal o privado/incógnito, e instalarlos "
        "si no están en el sistema. También Brave, Chromium y Vivaldi.\n\n"
        "Limpiar caché e historial de cada navegador (si está instalado).\n"
        "Perfiles y marcadores: lista los perfiles locales y exporta el archivo de marcadores.",
    ),
    (
        "Diccionario",
        "Abrir diccionario GNU/Linux carga un documento Markdown en línea con comandos "
        "de Linux. Permite buscar términos, guardar el contenido y abrir una terminal.\n\n"
        "Hace falta conexión a Internet para descargar el diccionario.",
    ),
    (
        "Notas",
        "Las notas se guardan en una carpeta fija del usuario:\n"
        "Documentos/Manten1d0/Notas (o Documents/Manten1d0/Notas).\n\n"
        "La pestaña lista las últimas notas. Doble clic o Abrir seleccionada las edita. "
        "Nueva nota abre el editor; Guardar las deja en esa carpeta (Ctrl+S).\n\n"
        "Desde Archivo: nuevo, abrir, guardar y guardar como. "
        "Desde Opciones: buscar, deshacer, rehacer, copiar y pegar.",
    ),
    (
        "Ayuda",
        "Documentación: esta ventana, con la explicación de cada categoría y menú.\n\n"
        "Acerca de: versión del programa, aviso de que no hay garantías y enlace al repositorio.",
    ),
    (
        "Bandeja del sistema",
        "Al abrir el programa aparece un icono con el logo Manten1do.png en la bandeja "
        "del sistema (zona de indicadores).\n\n"
        "Clic izquierdo: muestra u oculta la ventana principal.\n"
        "Clic derecho: menú contextual con las acciones habituales:\n"
        "• Mostrar ventana / Ocultar a la bandeja.\n"
        "• Ir a una categoría (Inicio, Sistema, Archivos, etc.).\n"
        "• Abrir terminal, Opciones, registro y buscar actualizaciones.\n"
        "• Documentación y Acerca de.\n"
        "• Salir (cierra el programa de verdad y borra la contraseña cifrada de esta sesión).\n\n"
        "La X de la ventana oculta Manten1d0 a la bandeja; no lo cierra. Para salir usa "
        "Archivo → Salir o la opción Salir del icono.",
    ),
)

_ventana_documentacion = None


def mostrar_documentacion(parent=None):
    """Abre (o trae al frente) la ventana de documentación."""
    global _ventana_documentacion
    if _ventana_documentacion is not None and _ventana_documentacion.winfo_exists():
        _ventana_documentacion.lift()
        _ventana_documentacion.focus_force()
        return

    oscuro = preferencias.tema_seleccionado != "Claro"
    fondo = "black" if oscuro else "lightgrey"
    frente = "white" if oscuro else "black"
    fondo_texto = "#1a1a1a" if oscuro else "white"

    ventana = tk.Toplevel(parent) if parent else tk.Toplevel()
    ventana.title("Documentación")
    ventana.geometry("820x560")
    ventana.minsize(640, 420)
    _ventana_documentacion = ventana

    def al_cerrar():
        global _ventana_documentacion
        _ventana_documentacion = None
        ventana.destroy()

    ventana.protocol("WM_DELETE_WINDOW", al_cerrar)

    cabecera = tk.Label(
        ventana,
        text="Documentación de Manten1d0",
        font=("Arial", 16, "bold"),
        bg=fondo,
        fg=frente,
        pady=10,
    )
    cabecera.pack(fill=tk.X)

    cuerpo = tk.Frame(ventana, bg=fondo)
    cuerpo.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    marco_lista = tk.Frame(cuerpo, bg=fondo)
    marco_lista.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
    tk.Label(
        marco_lista,
        text="Secciones",
        bg=fondo,
        fg=frente,
        font=("Arial", 10, "bold"),
    ).pack(anchor="w", pady=(0, 4))

    lista = tk.Listbox(
        marco_lista,
        width=22,
        exportselection=False,
        bg=fondo_texto,
        fg=frente,
        selectbackground="#2471a3",
        selectforeground="white",
        highlightthickness=0,
        activestyle="none",
    )
    lista.pack(fill=tk.Y, expand=True)
    for titulo, _texto in SECCIONES:
        lista.insert(tk.END, titulo)

    marco_texto = tk.Frame(cuerpo, bg=fondo)
    marco_texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    texto = tk.Text(
        marco_texto,
        wrap=tk.WORD,
        font=("Arial", 11),
        bg=fondo_texto,
        fg=frente,
        padx=12,
        pady=10,
        relief=tk.FLAT,
        highlightthickness=0,
    )
    barra = ttk.Scrollbar(marco_texto, orient="vertical", command=texto.yview)
    texto.configure(yscrollcommand=barra.set)
    barra.pack(side=tk.RIGHT, fill=tk.Y)
    texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    texto.tag_configure("titulo", font=("Arial", 14, "bold"), spacing3=8)
    texto.tag_configure("cuerpo", font=("Arial", 11), spacing1=2)

    def mostrar_seccion(indice):
        if indice < 0 or indice >= len(SECCIONES):
            return
        titulo, cuerpo_seccion = SECCIONES[indice]
        texto.configure(state=tk.NORMAL)
        texto.delete("1.0", tk.END)
        texto.insert("1.0", titulo + "\n", "titulo")
        texto.insert(tk.END, cuerpo_seccion, "cuerpo")
        texto.configure(state=tk.DISABLED)

    def al_seleccionar(_event=None):
        seleccion = lista.curselection()
        if seleccion:
            mostrar_seccion(seleccion[0])

    lista.bind("<<ListboxSelect>>", al_seleccionar)
    lista.selection_set(0)
    mostrar_seccion(0)

    ventana.configure(bg=fondo)
    if oscuro:
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)
        texto.configure(bg=fondo_texto, fg=frente)
        lista.configure(bg=fondo_texto, fg=frente)
