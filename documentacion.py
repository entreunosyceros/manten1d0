"""Ventana de documentación de las opciones de Manten1d0."""

import os
import tkinter as tk
from tkinter import ttk

import preferencias

RUTA_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manten1do.png")

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
        "Opciones: cambia el tema (claro, o el oscuro del sistema) y el tamaño del texto.\n\n"
        "Registro de acciones: muestra el historial de operaciones realizadas "
        "(sin guardar la contraseña de sudo). Desde esa ventana se puede vaciar el registro "
        "con confirmación; no borra el historial de comandos repetibles.\n\n"
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
        "Diagnóstico del equipo. Muestra el logo, una checklist de estado y accesos rápidos.\n\n"
        "Cada comprobación aparece siempre (ok, aviso o error):\n"
        "- Conexión a Internet (al pulsar se abre el asistente de problemas de Internet).\n"
        "- Disco raíz o carpeta personal (aviso >=80 %, crítico >=90 %). "
        "Si hay poco espacio, nombra las tres carpetas que más ocupan. Se puede borrar sin miedo la caché, "
        "las miniaturas y la papelera. No se deben borrar máquinas virtuales ni documentos.\n"
        "- Reinicio pendiente tras una actualización. Al pulsarlo, pide confirmación y reinicia.\n"
        "- Actualizaciones de APT pendientes, incluidas las de seguridad.\n"
        "- Estado SMART de los discos (o aviso si no se puede leer).\n"
        "- Temperatura de CPU (y ventiladores si hay sensores).\n"
        "- Servicios systemd que han fallado.\n"
        "- Cortafuegos ufw (activo, inactivo o no instalado); al pulsar se abre el Centro de seguridad.\n\n"
        "Arriba se muestra un resumen (problemas / avisos, o «Sin problemas detectados»).\n"
        "Al pulsar un resultado se abre la herramienta concreta (limpieza, Salud discos, "
        "servicios que fallan, Centro de seguridad...) o la categoría relacionada.\n"
        "Analizar mi equipo vuelve a ejecutar el diagnóstico.\n"
        "Que problema tienes? abre un asistente por sintoma (Internet, sonido, "
        "impresora, pantalla, lentitud, espacio, instalar, actualizaciones, "
        "Bluetooth, arranque). Diagnostica solo ese caso y propone la herramienta "
        "o reparacion adecuada.\n"
        "Reparar Ubuntu continúa el diagnóstico con tarjetas «Problema detectado» "
        "(dependencias APT, paquetes a medias, cada servicio fallido, red, CUPS). "
        "Antes de actuar explica qué va a hacer, por qué y qué riesgos tiene. "
        "«Otras reparaciones» incluye audio, red, limpia caché APT, etc.\n"
        "Liberar espacio analiza qué ocupa la carpeta personal y el espacio recuperable; "
        "permite limpieza rápida (segura) o profunda (Snap antiguos y kernels) "
        "o elegir categorías a mano.\n"
        "Actualizar todo cuenta pendientes de APT, Snap y Flatpak y los instala "
        "en un solo flujo con progreso.\n"
        "Informe de asistencia genera un texto con el diagnóstico y datos del equipo "
        "para copiarlo o guardarlo y enviárselo a quien te ayude (sin contraseñas).\n"
        "Ver registro de acciones abre el mismo historial que Preferencias.",
    ),
    (
        "Perfil Usuario",
        "Muestra lo esencial de tu cuenta: foto, usuario y nombre visible. "
        "La pestana tiene desplazamiento vertical si el contenido no cabe.\n\n"
        "Mi carpeta personal: muestra la ruta de tu home con acciones para "
        "abrirla en el explorador, ver el espacio utilizado (Documentos, Descargas, "
        "Videos, Imagenes, etc.) o abrir Liberar espacio para limpiar el disco.\n\n"
        "Aplicaciones predeterminadas: elige navegador, cliente de correo, visor de "
        "imagenes, reproductor de video y editor de texto. El cambio se aplica al "
        "elegir en la lista. Restaurar valores del sistema quita esas personalizaciones.\n\n"
        "Carpetas personales: muestra las rutas XDG (Documentos, Descargas, Musica, "
        "Imagenes, Videos, Escritorio). Solo consulta; Abrir las abre en el explorador. "
        "No se cambian rutas desde aqui.\n\n"
        "Configuracion regional: pais, idioma, formato de fecha y hora, separador decimal, "
        "moneda y zona horaria. Es solo informativo; el boton «Abrir ajustes de Ubuntu» "
        "lanza el panel de Region e idioma del sistema para cambiar esos formatos.\n\n"
        "Idioma de la interfaz: elige entre los idiomas instalados (Español, English, Galego...). "
        "El cambio se guarda para la proxima sesion; la actual no cambia hasta cerrar sesion.\n\n"
        "Contrasena: muestra el ultimo cambio y si la cuenta esta protegida. "
        "Cambiar contraseña abre un dialogo con indicador de fuerza (longitud, mayusculas, "
        "minusculas, numeros, simbolo), opcion de mostrar lo escrito y aviso de no reutilizar "
        "claves de otros servicios. Si el sistema tiene caducidad configurada, se indica.\n\n"
        "Modificar Perfil Usuario abre un formulario para cambiar:\n"
        "- Nombre visible (campo GECOS).\n"
        "- Imagen de perfil.\n\n"
        "El nombre de usuario de login no se modifica desde aquí.",
    ),
    (
        "Información",
        "Consulta de solo lectura sobre el equipo: usuario, sistema, versión de Ubuntu, "
        "escritorio, tiempo encendido, tiempo de arranque (systemd-analyze), gráfica, "
        "interfaces de red, IP local y pública, DNS, procesador, memoria, zona horaria "
        "y temperatura de CPU si está disponible.\n\n"
        "La gráfica se detecta con lspci y sysfs para Intel, AMD y NVIDIA. nvidia-smi "
        "solo se usa si hay una GPU NVIDIA; el resto no depende de ella.\n\n"
        "Copiar informe deja el texto en el portapapeles. Exportar a .txt lo guarda en un archivo.\n"
        "Informe de asistencia añade el diagnóstico del equipo (ok/aviso/error) y permite "
        "copiarlo o guardarlo para enviárselo a quien te ayude.",
    ),
    (
        "Sistema",
        "Herramientas de mantenimiento del sistema operativo, agrupadas en "
        "poner al día, espacio, el equipo, y al arrancar:\n\n"
        "Actualizar Sistema: instala las actualizaciones APT disponibles.\n"
        "Actualizar todo: cuenta e instala pendientes de APT, Snap y Flatpak en un solo flujo.\n"
        "Centro de aplicaciones: lista unificada de apps de escritorio (APT), Snap y Flatpak. "
        "Permite buscar, ver origen/versión/tamaño, abrir, actualizar o desinstalar, "
        "y muestra las que más ocupan. Atajos a Instalar .deb y a la tienda (Snap Store).\n"
        "Limpiar Caché: vacía la caché de paquetes.\n"
        "Abrir Gestor Software: lanza el centro de software de Ubuntu (snaps).\n"
        "Aplicaciones Inicio: añade o quita programas que arrancan con la sesión (.desktop).\n"
        "Por que tarda en arrancar?: lee systemd-analyze y muestra el tiempo total, "
        "las fases (firmware, cargador, kernel, userspace) con barras visuales, "
        "y los servicios que mas tardaron en el ultimo arranque (blame), con explicaciones "
        "en lenguaje sencillo. No desactiva servicios automaticamente; puedes abrir "
        "Servicios systemd si quieres actuar a mano.\n"
        "Eliminar Archivo/s: borra archivos o carpetas de forma permanente.\n"
        "Vaciar Papelera: vacía la papelera del usuario.\n"
        "Administrar Procesos: lista procesos y permite gestionarlos.\n"
        "Buscar Archivos Duplicados: localiza ficheros repetidos para liberar espacio.\n"
        "Gestiona Repositorios: añade, quita o edita repositorios y PPA.\n"
        "Monitorizar: panel simplificado con barras de CPU, RAM, disco (raiz) y temperatura; "
        "lista los procesos que mas consumen (orden por CPU, RAM, disco I/O o conexiones de red). "
        "Permite Abrir (activar ventana con wmctrl o ver ruta) y Finalizar con confirmacion "
        "que explica riesgos. Se actualiza solo; Ver grafico abre el monitor matplotlib anterior.\n"
        "Instalar .deb: elige un paquete .deb e instálalo con dpkg.\n"
        "Desinstalar Paquetes: quita paquetes instalados por el usuario.\n"
        "Ver logs: consulta registros importantes del sistema.\n"
        "Limpieza disco / Liberar espacio: analiza el uso del disco y la carpeta personal, "
        "muestra el espacio recuperable y limpia con perfil rápido (caché APT, journal, "
        "miniaturas, papelera, pip, huérfanos) o profundo (añade Snap antiguos y "
        "versiones viejas del sistema). Esa última casilla no se marca sola en el análisis "
        "inicial; la profunda sí la incluye tras confirmación. "
        "Se conserva la versión que está en marcha y la anterior. "
        "Atajos a Ver carpetas, Snap/Flatpak y Archivos grandes.\n"
        "Salud discos: estado SMART, temperatura y avisos de fallo.\n"
        "Servicios: iniciar, detener, reiniciar, habilitar o deshabilitar unidades systemd.\n"
        "Reparar Ubuntu: continúa el diagnóstico con una tarjeta por problema "
        "(APT, dpkg, cada servicio fallido, red, CUPS). Cada reparación pide confirmación "
        "explicando qué hará, por qué y los riesgos. Otras reparaciones útiles: audio, "
        "caché APT, etc.\n"
        "Servicios que fallan: lista solo las unidades que systemd marca como fallidas, "
        "permite reiniciar la seleccionada o ver las últimas líneas del registro (journalctl).\n"
        "Historial comandos: lista las limpiezas y acciones ya ejecutadas para repetirlas "
        "con confirmación. No guarda la contraseña de sudo.\n"
        "Impresoras: busca impresoras enchufadas por USB o anunciadas en la red local "
        "(mDNS/CUPS), lista las colas instaladas, envía una página de prueba y abre "
        "la configuración de impresoras del sistema.\n"
        "Espacio discos: espacio ocupado, libre y porcentaje de cada disco local. "
        "Al elegir uno, lista las carpetas que más ocupan. Doble clic entra en una "
        "carpeta. No cruza a otro disco montado dentro. La casilla de carpetas "
        "protegidas vuelve a medir con sudo las rutas que el usuario no puede leer.\n"
        "Snap y Flatpak: lista las aplicaciones Snap y Flatpak con el espacio que "
        "ocupan (van aparte de APT). Permite actualizar una, actualizar todas según "
        "el filtro, o desinstalar. Si Flatpak no está instalado, la misma ventana "
        "puede instalarlo.\n"
        "Bluetooth: lista los dispositivos emparejados, indica si están conectados, "
        "permite olvidar uno que no conecta y reiniciar el servicio Bluetooth "
        "(como apagar y encender). No empareja dispositivos nuevos: eso se hace "
        "desde los ajustes de Ubuntu.\n"
        "Sonido: muestra la salida de audio por defecto (PipeWire o PulseAudio), "
        "permite elegir otra (auriculares, HDMI) y reiniciar el servicio cuando "
        "no hay sonido. También puede abrir los ajustes de sonido de GNOME.\n"
        "Pantallas: lista monitores conectados con xrandr, permite detectar de nuevo, "
        "dejar solo una, extender a la derecha o poner en espejo (portátil + TV). "
        "Si xrandr falla (p. ej. en Wayland), usa los ajustes de GNOME.\n"
        "Centro de seguridad: resumen claro del cortafuegos, actualizaciones APT "
        "(incluidas las de seguridad), si tu usuario tiene contraseña, y los puertos "
        "que escuchan en la red, con explicaciones en lenguaje sencillo "
        "(por ejemplo SSH, CUPS, Avahi). Desde ahí puedes abrir el cortafuegos, "
        "Actualizar todo, o desactivar un servicio conocido (SSH, Samba, CUPS, Avahi) "
        "con confirmación de qué, por qué y riesgos.\n"
        "Cortafuegos (desde el Centro de seguridad): enciende o apaga ufw. "
        "Activado significa que solo entran las conexiones que tú permites; "
        "la salida a Internet no se corta. Pide confirmación y la contraseña de administrador. "
        "Si ufw no está instalado, la misma ventana puede instalarlo. "
        "También permite reglas frecuentes sin editar ufw a mano: permitir o quitar SSH, "
        "Samba (carpetas compartidas) y el acceso solo desde tu red local detectada.",
    ),
    (
        "Archivos",
        "Copiar A Un USB: copia Documentos o el escritorio a un USB, en una carpeta "
        "con la fecha en el nombre (por ejemplo Documentos-2026-09-29). "
        "Los archivos se copian tal cual, sin comprimir. Si el USB no está abierto, se monta. "
        "Si no cabe, avisa y no copia.\n"
        "Restaurar Copia de Seguridad: extrae un archivo .gz antiguo en la carpeta que elijas "
        "(puede sobrescribir archivos).\n\n"
        "Las acciones están agrupadas en copias, proteger, organizar, y comprobar y liberar.\n\n"
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
        "Selecciona una interfaz de red para trabajar con ella. Las acciones están "
        "agrupadas en conexión, ajustes de red y herramientas.\n\n"
        "Tengo problemas con Internet: analiza adaptador, router, DNS, salida a Internet, "
        "latencia y pérdida de paquetes. Muestra un resultado y una solución recomendada "
        "(por ejemplo cambiar DNS a Cloudflare o reiniciar NetworkManager) con confirmación. "
        "También permite abrir el selector de DNS o medir el nivel de ruido.\n"
        "Reiniciar Tarjeta de Red: baja y vuelve a levantar la interfaz (pide confirmación).\n"
        "Hacer Ping: comprueba si una URL o host responde.\n"
        "Redes Wi-Fi: lista redes con nmcli, conecta (pidiendo clave si hace falta) o desconecta.\n"
        "DNS: cambia entre el automático del router, Cloudflare 1.1.1.1 o Google 8.8.8.8.\n"
        "Hosts locales: edita /etc/hosts con validación y copia de seguridad.\n"
        "VPN: solo ExpressVPN. El botón aparece si está instalado expressvpnctl. "
        "Muestra el estado y permite conectar, desconectar, elegir región y protocolo, "
        "y cambiar el bloqueo de red, la red local, el arranque automático y el túnel dividido. "
        "La sesión se inicia y se cierra en la aplicación oficial de ExpressVPN. "
        "NordVPN, Surfshark, Proton VPN, CyberGhost, Mullvad y otros clientes no se configuran desde aquí.\n"
        "Escanear Puertos: revisa puertos abiertos de una IP.\n"
        "Puerto desde Internet: con aviso de riesgos, muestra tu IP pública, "
        "comprueba si este PC escucha un puerto y abre una página web para "
        "probar si ese puerto es alcanzable desde fuera. No escanea redes ajenas.\n"
        "Test Velocidad: mide descarga y subida de la conexión.\n"
        "Diagnóstico Red: traceroute y netstat para ver por dónde falla la conectividad.\n"
        "Nivel de ruido: en Wi-Fi lee señal y ruido de radio (SNR). En cualquier conexión "
        "mide pérdida de paquetes y jitter hacia Internet. En cable muestra errores del adaptador.\n\n"
        "El indicador del menú lateral muestra si hay conexión a Internet. Debajo aparecen "
        "la IP privada (la de la red de casa, no la del túnel VPN), la IP pública y si "
        "el equipo está usando una VPN (ExpressVPN conectada o un túnel típico como tun/WireGuard).",
    ),
    (
        "Red Local",
        "Quién hay en la red: recorre la red (Wi-Fi o cable) y lista cada dispositivo "
        "con IP, nombre, MAC y si comparte Samba (puertos 139/445). Es la forma fiable "
        "de ver quién está conectado sin entrar en el router; el listado del router "
        "solo está en la web del fabricante.\n\n"
        "Haz doble clic en un equipo para abrir smb:// en el administrador de archivos "
        "si el servicio está disponible.\n\n"
        "¿Responde el router?: hace ping a la puerta de enlace de casa y muestra si "
        "contesta y la latencia. Puede abrir la página de configuración del router "
        "(http://su-IP) en el navegador.\n\n"
        "Compartir carpeta: elige una carpeta de tu usuario para que otro equipo de casa "
        "la vea, solo para leer o también para cambiar archivos. Cualquiera de la red puede "
        "abrirla sin contraseña. Hace falta pertenecer al grupo sambashare; si no, se ofrece "
        "añadirte y hay que cerrar la sesión. Si el cortafuegos está activado, pregunta si "
        "hay que permitir Samba. Al terminar indica la dirección smb:// de este equipo.\n"
        "Encender un PC: envía la señal de encendido a un equipo guardado al buscar la red, "
        "o a una dirección MAC que anotes. El otro PC tiene que estar apagado y enchufado, "
        "y su placa debe permitir el encendido por red (Wake-on-LAN).",
    ),
    (
        "Navegadores",
        "Abrir Chrome, Firefox o Edge en modo normal o privado/incógnito, e instalarlos "
        "si no están en el sistema. También Brave, Chromium y Vivaldi. "
        "Las acciones están agrupadas en abrir, instalar, limpiar y perfiles.\n\n"
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
        "- Mostrar ventana / Ocultar a la bandeja.\n"
        "- Ir a una categoría (Inicio, Sistema, Archivos, etc.).\n"
        "- Abrir terminal, Opciones, registro y buscar actualizaciones.\n"
        "- Documentación y Acerca de.\n"
        "- Salir (cierra el programa de verdad y borra la contraseña cifrada de esta sesión).\n\n"
        "La X de la ventana oculta Manten1d0 a la bandeja; no lo cierra. Para salir usa "
        "Archivo -> Salir o la opción Salir del icono.",
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

    colores = preferencias.colores_de(preferencias.tema_seleccionado)
    fondo = colores["bg"]
    frente = colores["fg"]
    fondo_texto = colores["base"]

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
        selectbackground=colores["select"],
        selectforeground=colores["select_fg"],
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
    texto.tag_configure("logo", justify=tk.CENTER, spacing1=6, spacing3=12)
    _logo_doc = {"foto": None}

    def _cargar_logo_doc():
        if _logo_doc["foto"] is not None:
            return _logo_doc["foto"]
        try:
            from PIL import Image, ImageTk

            imagen = Image.open(RUTA_LOGO)
            imagen.thumbnail((220, 220), getattr(Image, "LANCZOS", Image.NEAREST))
            foto = ImageTk.PhotoImage(imagen, master=ventana)
            _logo_doc["foto"] = foto
            return foto
        except Exception:
            return None

    def mostrar_seccion(indice):
        if indice < 0 or indice >= len(SECCIONES):
            return
        titulo, cuerpo_seccion = SECCIONES[indice]
        texto.configure(state=tk.NORMAL)
        texto.delete("1.0", tk.END)
        texto.insert("1.0", titulo + "\n", "titulo")
        # Pantalla inicial (Presentación): logo bajo el título
        if indice == 0:
            foto = _cargar_logo_doc()
            if foto is not None:
                texto.insert(tk.END, "\n", "logo")
                texto.image_create(tk.END, image=foto)
                texto.insert(tk.END, "\n\n", "logo")
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
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)
        texto.configure(bg=fondo_texto, fg=frente, selectbackground=colores["select"], selectforeground=colores["select_fg"])
        lista.configure(bg=fondo_texto, fg=frente, selectbackground=colores["select"], selectforeground=colores["select_fg"])
