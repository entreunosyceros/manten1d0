"""Asistente de problemas: el usuario elige que le falla y se diagnostica en concreto."""

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import preferencias
from registro import confirmar, en_hilo, registrar
from tooltip import ToolTip, con_tooltip

_COLORES = {
    "ok": "#1e8449",
    "aviso": "#e67e22",
    "error": "#c0392b",
    "info": "#2471a3",
}
_MARCAS = {"ok": "OK", "aviso": "AVISO", "error": "ERROR", "info": "INFO"}
_BG_UI = "#f4f6f7"
_FRANJA = "#1a5276"


def _comando(args, timeout=20):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def _item(nivel, titulo, detalle, accion=None):
    return {
        "nivel": nivel,
        "titulo": titulo,
        "detalle": detalle,
        "accion": accion,
    }


def _apt_check_con_clave_guardada():
    """apt-get check con la contraseña de sesion, sin dialogo. None si no hay clave."""
    try:
        from password import CLAVE_ARCHIVO, CONFIG_FILE, cargar_clave, descifrar_contrasena

        if not os.path.isfile(CONFIG_FILE):
            return None
        with open(CONFIG_FILE, "rb") as fichero:
            contrasena = descifrar_contrasena(fichero.read(), cargar_clave(CLAVE_ARCHIVO))
    except Exception:
        return None
    if not contrasena:
        return None
    try:
        return subprocess.run(
            ["sudo", "-S", "-p", "", "apt-get", "-qq", "check"],
            input=f"{contrasena}\n",
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _es_fallo_privilegios_apt(proceso):
    """True si el fallo es por bloqueo/permisos, no por dependencias rotas."""
    if proceso is None:
        return True
    texto = f"{proceso.stderr or ''}{proceso.stdout or ''}".lower()
    indicios = (
        "lock",
        "permiso denegado",
        "permission denied",
        "are you root",
        "superusuario",
        "password is required",
        "a password is required",
        "contrase",
    )
    return any(p in texto for p in indicios)


def _comprobar_apt_y_dpkg():
    """
    Estado real de dpkg/APT sin confundir 'sin sudo' con 'dependencias rotas'.
    Devuelve lista de items de diagnostico.
    """
    items = []
    dpkg = _comando(["dpkg", "--audit"], timeout=30)
    audit = (dpkg.stdout or "").strip()
    if dpkg.returncode == 0 and not audit:
        items.append(_item("ok", "dpkg", "No hay paquetes a medias segun dpkg --audit."))
    else:
        items.append(
            _item(
                "error",
                "Paquetes a medias",
                (audit[:300] + "...") if len(audit) > 300 else (audit or "dpkg reporta problemas."),
                "repair_dpkg",
            )
        )

    # apt-get check sin privilegios falla siempre por el lock; no es un error de APT.
    check = _comando(["sudo", "-n", "apt-get", "-qq", "check"], timeout=60)
    if check.returncode != 0 and _es_fallo_privilegios_apt(check):
        check = _apt_check_con_clave_guardada() or check

    if check is not None and check.returncode == 0:
        items.append(_item("ok", "APT", "Sin errores de dependencias (apt-get check)."))
    elif check is not None and not _es_fallo_privilegios_apt(check) and check.returncode != 0:
        detalle = (check.stderr or check.stdout or "Dependencias rotas.").strip()[:300]
        items.append(_item("error", "APT con errores", detalle, "repair_apt"))
    else:
        # Sin privilegios para comprobar: no marcar error falso
        if any(i["nivel"] == "error" for i in items):
            items.append(
                _item(
                    "info",
                    "APT",
                    "Hay avisos de dpkg; repara dpkg/APT. No se pudo completar apt-get check.",
                )
            )
        else:
            items.append(
                _item(
                    "ok",
                    "APT",
                    "dpkg esta bien. No hace falta reparar APT solo por el bloqueo de permisos.",
                )
            )
    return items


# --- Diagnosticos por problema ---


def _diag_internet():
    from asistente_internet import diagnosticar_internet

    datos = diagnosticar_internet()
    items = datos.get("items") or []
    solucion = datos.get("solucion") or {}
    errores = sum(1 for i in items if i.get("nivel") == "error")
    avisos = sum(1 for i in items if i.get("nivel") == "aviso")
    if errores:
        resumen = "Hay fallos en la conexion. Revisa el asistente de Internet."
        nivel = "error"
    elif avisos:
        resumen = "La red responde, pero hay avisos (DNS, latencia o perdida)."
        nivel = "aviso"
    else:
        resumen = "Internet parece correcto en las comprobaciones basicas."
        nivel = "ok"
    acciones = [
        {
            "etiqueta": "Abrir asistente de Internet",
            "panel": "AsistenteInternet",
            "ayuda": "Checklist completa y solucion recomendada",
        }
    ]
    if solucion.get("accion"):
        acciones.append(
            {
                "etiqueta": solucion.get("etiqueta_boton") or "Aplicar solucion sugerida",
                "panel": "AsistenteInternet",
                "ayuda": solucion.get("texto") or "",
            }
        )
    return {"nivel": nivel, "resumen": resumen, "items": items, "acciones": acciones}


def _diag_sonido():
    items = []
    pulse = _comando(["pactl", "info"], timeout=8)
    pipewire = _comando(["systemctl", "--user", "is-active", "pipewire"], timeout=8)
    activo_pw = (pipewire.stdout or "").strip() == "active"
    if pulse.returncode == 0:
        items.append(_item("ok", "Servidor de audio", "PulseAudio/PipeWire responde a pactl."))
    elif activo_pw:
        items.append(
            _item(
                "aviso",
                "PipeWire activo",
                "PipeWire esta activo pero pactl no respondio. Prueba a reiniciar el audio.",
                "reiniciar_audio",
            )
        )
    else:
        items.append(
            _item(
                "error",
                "Sin servidor de audio",
                "No se detecta PulseAudio/PipeWire operativo.",
                "reiniciar_audio",
            )
        )

    sumideros = _comando(["pactl", "list", "short", "sinks"], timeout=8)
    if sumideros.returncode == 0 and (sumideros.stdout or "").strip():
        lineas = [l for l in sumideros.stdout.splitlines() if l.strip()]
        items.append(
            _item("ok", "Salidas de audio", f"Hay {len(lineas)} salida(s) disponible(s).")
        )
    else:
        items.append(
            _item(
                "aviso",
                "Sin salidas",
                "No se listan altavoces/auriculares. Revisa cable, HDMI o Bluetooth.",
                "panel_sonido",
            )
        )

    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    return {
        "nivel": nivel,
        "resumen": "Revisa el panel de Sonido: reiniciar audio o cambiar de salida.",
        "items": items,
        "acciones": [
            {
                "etiqueta": "Abrir Sonido",
                "panel": "Sonido",
                "ayuda": "Reinicia PipeWire/PulseAudio o cambia la salida",
            },
            {
                "etiqueta": "Reiniciar audio ahora",
                "repair": "audio",
                "ayuda": "Reinicia el servicio de audio",
            },
        ],
    }


def _diag_impresora():
    from reparar import _cups_activo, _cups_instalado

    items = []
    if not _cups_instalado():
        items.append(
            _item(
                "aviso",
                "CUPS no instalado",
                "No se encontro el servicio de impresion CUPS.",
            )
        )
    elif not _cups_activo():
        items.append(
            _item(
                "error",
                "CUPS parado",
                "cups.service no esta activo. Sin el no se imprime.",
                "repair_cups",
            )
        )
    else:
        items.append(_item("ok", "CUPS", "El servicio de impresion esta activo."))

    lpstat = _comando(["lpstat", "-p"], timeout=10)
    if lpstat.returncode == 0 and (lpstat.stdout or "").strip():
        items.append(_item("ok", "Impresoras", "Hay colas de impresion configuradas."))
    else:
        items.append(
            _item(
                "aviso",
                "Sin impresoras",
                "No hay impresoras en CUPS o lpstat no esta disponible.",
                "panel_impresoras",
            )
        )

    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    return {
        "nivel": nivel,
        "resumen": "Revisa Impresoras o repara CUPS si el servicio esta parado.",
        "items": items,
        "acciones": [
            {
                "etiqueta": "Abrir Impresoras",
                "panel": "Impresoras",
                "ayuda": "Lista colas, prueba de pagina y busca equipos",
            },
            {
                "etiqueta": "Reparar CUPS",
                "repair": "cups",
                "ayuda": "Reinicia el servicio cups.service",
            },
            {
                "etiqueta": "Reparar Ubuntu",
                "panel": "RepararUbuntu",
                "ayuda": "Tarjetas de reparacion guiada (incluye CUPS)",
            },
        ],
    }


def _diag_pantalla():
    items = []
    xrandr = _comando(["xrandr", "--query"], timeout=10)
    if xrandr.returncode != 0:
        items.append(
            _item(
                "aviso",
                "xrandr",
                "No se pudo consultar monitores (¿sesion Wayland sin xrandr?).",
                "panel_pantallas",
            )
        )
    else:
        conectados = [
            l.split()[0]
            for l in xrandr.stdout.splitlines()
            if " connected" in l
        ]
        if len(conectados) >= 2:
            items.append(
                _item(
                    "info",
                    "Varios monitores",
                    f"Detectados: {', '.join(conectados)}. Puedes elegir espejo o extendido.",
                    "panel_pantallas",
                )
            )
        elif conectados:
            items.append(
                _item("ok", "Monitor", f"Conectado: {conectados[0]}.")
            )
        else:
            items.append(
                _item(
                    "error",
                    "Sin monitor",
                    "xrandr no marca ninguna salida connected.",
                    "panel_pantallas",
                )
            )

    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    return {
        "nivel": nivel,
        "resumen": "Usa Pantallas para espejo, extendido o una sola salida.",
        "items": items,
        "acciones": [
            {
                "etiqueta": "Abrir Pantallas",
                "panel": "Pantallas",
                "ayuda": "Espejo / extendido / una sola pantalla",
            }
        ],
    }


def _diag_lento():
    from diagnostico import _check_disco, _check_temperatura

    items = []
    try:
        import psutil
    except ImportError:
        psutil = None

    if psutil:
        carga = psutil.cpu_percent(interval=0.4)
        ram = psutil.virtual_memory()
        if carga >= 90:
            items.append(
                _item(
                    "aviso",
                    "CPU muy ocupada",
                    f"Uso de CPU: {carga:.0f} %. Mira que programas consumen.",
                    "panel_monitor",
                )
            )
        else:
            items.append(_item("ok", "CPU", f"Uso actual: {carga:.0f} %."))
        if ram.percent >= 90:
            items.append(
                _item(
                    "aviso",
                    "Poca memoria libre",
                    f"RAM al {ram.percent:.0f} %. Cierra programas pesados.",
                    "panel_monitor",
                )
            )
        else:
            items.append(
                _item("ok", "Memoria", f"RAM en uso: {ram.percent:.0f} %.")
            )
    else:
        items.append(_item("info", "psutil", "No disponible; abre el monitor de recursos."))

    items.extend(_check_disco())
    items.extend(_check_temperatura())

    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    return {
        "nivel": nivel,
        "resumen": "Mira CPU/RAM/disco y temperatura; libera espacio si el disco esta lleno.",
        "items": items,
        "acciones": [
            {
                "etiqueta": "Monitorizar recursos",
                "panel": "MonitorRecursos",
                "ayuda": "Barras CPU/RAM/disco y procesos",
            },
            {
                "etiqueta": "Liberar espacio",
                "panel": "LimpiezaEspacio",
                "ayuda": "Limpieza rapida o profunda del disco",
            },
            {
                "etiqueta": "Analisis de arranque",
                "panel": "AnalisisArranque",
                "ayuda": "Si tambien tarda al encender",
            },
        ],
    }


def _diag_espacio():
    from diagnostico import _check_disco

    items = list(_check_disco())
    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    if nivel == "ok":
        resumen = "El disco no esta critico, pero puedes revisar que ocupa la carpeta personal."
    else:
        resumen = "Conviene liberar espacio o revisar las carpetas que mas ocupan."
    return {
        "nivel": nivel,
        "resumen": resumen,
        "items": items,
        "acciones": [
            {
                "etiqueta": "Liberar espacio",
                "panel": "LimpiezaEspacio",
                "ayuda": "Que ocupa el home y limpiezas guiadas",
            },
            {
                "etiqueta": "Espacio por disco",
                "panel": "EspacioDiscos",
                "ayuda": "Carpetas que mas ocupan en cada disco",
            },
        ],
    }


def _diag_instalar():
    items = _comprobar_apt_y_dpkg()
    nivel = "error" if any(i["nivel"] == "error" for i in items) else "ok"
    return {
        "nivel": nivel,
        "resumen": (
            "Hay que reparar dpkg/APT antes de instalar."
            if nivel == "error"
            else "El sistema de paquetes parece sano; prueba el Centro de aplicaciones."
        ),
        "items": items,
        "acciones": [
            {
                "etiqueta": "Reparar Ubuntu",
                "panel": "RepararUbuntu",
                "ayuda": "Tarjetas APT/dpkg guiadas",
            },
            {
                "etiqueta": "Centro de aplicaciones",
                "panel": "CentroAplicaciones",
                "ayuda": "Buscar, instalar o quitar programas",
            },
            {
                "etiqueta": "Reparar dpkg ahora",
                "repair": "dpkg",
                "ayuda": "dpkg --configure -a",
            },
            {
                "etiqueta": "Reparar APT ahora",
                "repair": "apt",
                "ayuda": "apt-get -f install",
            },
        ],
    }


def _diag_actualizaciones():
    from diagnostico import _check_actualizaciones

    items = list(_check_actualizaciones())
    items.extend(_comprobar_apt_y_dpkg())
    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    hay_rotos = any(
        i["nivel"] == "error" and i["titulo"] in ("APT con errores", "Paquetes a medias")
        for i in items
    )
    return {
        "nivel": nivel,
        "resumen": (
            "Hay errores de paquetes o dependencias; repara APT antes de actualizar."
            if hay_rotos
            else "Actualiza APT/Snap/Flatpak cuando haya pendientes."
        ),
        "items": items,
        "acciones": [
            {
                "etiqueta": "Actualizar todo",
                "panel": "ActualizarTodo",
                "ayuda": "APT + Snap + Flatpak",
            },
            {
                "etiqueta": "Reparar Ubuntu",
                "panel": "RepararUbuntu",
                "ayuda": "Si las actualizaciones fallan por dependencias",
            },
            {
                "etiqueta": "Reparar APT ahora",
                "repair": "apt",
                "ayuda": "apt-get -f install",
            },
        ],
    }


def _diag_bluetooth():
    items = []
    servicio = _comando(["systemctl", "is-active", "bluetooth"], timeout=8)
    estado = (servicio.stdout or "").strip()
    if estado == "active":
        items.append(_item("ok", "Servicio Bluetooth", "bluetooth.service esta activo."))
    elif estado == "inactive":
        items.append(
            _item(
                "error",
                "Bluetooth parado",
                "El servicio bluetooth no esta activo.",
                "panel_bluetooth",
            )
        )
    else:
        items.append(
            _item(
                "aviso",
                "Servicio Bluetooth",
                f"Estado: {estado or 'desconocido'}.",
                "panel_bluetooth",
            )
        )

    if shutil.which("bluetoothctl"):
        mostrar = _comando(["bluetoothctl", "show"], timeout=8)
        texto = mostrar.stdout or ""
        if "Powered: yes" in texto:
            items.append(_item("ok", "Adaptador", "El adaptador esta encendido (Powered: yes)."))
        elif "Powered: no" in texto:
            items.append(
                _item(
                    "aviso",
                    "Adaptador apagado",
                    "Bluetooth esta Powered: no. Enciendelo desde el panel.",
                    "panel_bluetooth",
                )
            )
        else:
            items.append(
                _item(
                    "info",
                    "Adaptador",
                    "No se pudo leer el estado Powered.",
                    "panel_bluetooth",
                )
            )
    else:
        items.append(_item("aviso", "bluetoothctl", "No esta instalado bluetoothctl."))

    nivel = "error" if any(i["nivel"] == "error" for i in items) else (
        "aviso" if any(i["nivel"] == "aviso" for i in items) else "ok"
    )
    return {
        "nivel": nivel,
        "resumen": "Usa el panel Bluetooth para reiniciar el servicio u olvidar un dispositivo.",
        "items": items,
        "acciones": [
            {
                "etiqueta": "Abrir Bluetooth",
                "panel": "Bluetooth",
                "ayuda": "Listar, olvidar dispositivo o reiniciar el servicio",
            }
        ],
    }


def _diag_arranque():
    items = []
    blame = _comando(["systemd-analyze"], timeout=20)
    if blame.returncode != 0:
        items.append(
            _item(
                "aviso",
                "systemd-analyze",
                "No se pudo leer el tiempo de arranque.",
                "panel_arranque",
            )
        )
    else:
        texto = (blame.stdout or "").strip().splitlines()
        primera = texto[0] if texto else "Sin datos"
        items.append(_item("info", "Tiempo de arranque", primera, "panel_arranque"))
        # Heuristica simple: si menciona minutos, avisar
        if "min" in primera.lower():
            items.append(
                _item(
                    "aviso",
                    "Arranque largo",
                    "El arranque supera el minuto. Revisa servicios lentos.",
                    "panel_arranque",
                )
            )
        else:
            items.append(
                _item("ok", "Arranque", "No parece extremadamente lento a primera vista.")
            )

    fallidos, error = __import__("diagnostico", fromlist=["listar_unidades_fallidas"]).listar_unidades_fallidas()
    if error:
        items.append(_item("info", "Servicios", error))
    elif fallidos:
        nombres = ", ".join(u["unidad"] for u in fallidos[:5])
        items.append(
            _item(
                "aviso",
                "Servicios fallidos",
                f"{len(fallidos)} unidad(es): {nombres}",
                "panel_servicios",
            )
        )
    else:
        items.append(_item("ok", "Servicios", "No hay unidades systemd en failed."))

    nivel = "aviso" if any(i["nivel"] in ("aviso", "error") for i in items) else "ok"
    return {
        "nivel": nivel,
        "resumen": "Mira el analisis de arranque y los servicios que fallan.",
        "items": items,
        "acciones": [
            {
                "etiqueta": "Por que tarda en arrancar?",
                "panel": "AnalisisArranque",
                "ayuda": "Fases y servicios mas lentos",
            },
            {
                "etiqueta": "Servicios que fallan",
                "panel": "ServiciosFallidos",
                "ayuda": "Listar y reiniciar unidades failed",
            },
            {
                "etiqueta": "Reparar Ubuntu",
                "panel": "RepararUbuntu",
                "ayuda": "Reparacion guiada de servicios",
            },
        ],
    }


PROBLEMAS = (
    {
        "id": "internet",
        "titulo": "Internet no funciona",
        "resumen": "Adaptador, router, DNS y conexion a Internet.",
        "diagnosticar": _diag_internet,
    },
    {
        "id": "sonido",
        "titulo": "No tengo sonido",
        "resumen": "Servidor de audio y salidas (altavoces, HDMI, auriculares).",
        "diagnosticar": _diag_sonido,
    },
    {
        "id": "impresora",
        "titulo": "La impresora no funciona",
        "resumen": "Servicio CUPS y colas de impresion.",
        "diagnosticar": _diag_impresora,
    },
    {
        "id": "pantalla",
        "titulo": "La pantalla no funciona bien",
        "resumen": "Monitores detectados, espejo o escritorio extendido.",
        "diagnosticar": _diag_pantalla,
    },
    {
        "id": "lento",
        "titulo": "El ordenador va lento",
        "resumen": "CPU, memoria, disco y temperatura.",
        "diagnosticar": _diag_lento,
    },
    {
        "id": "espacio",
        "titulo": "Me estoy quedando sin espacio",
        "resumen": "Uso del disco y limpieza de la carpeta personal.",
        "diagnosticar": _diag_espacio,
    },
    {
        "id": "instalar",
        "titulo": "No puedo instalar un programa",
        "resumen": "dpkg a medias y dependencias APT rotas.",
        "diagnosticar": _diag_instalar,
    },
    {
        "id": "actualizaciones",
        "titulo": "Las actualizaciones dan error",
        "resumen": "Pendientes APT y errores que bloquean el update.",
        "diagnosticar": _diag_actualizaciones,
    },
    {
        "id": "bluetooth",
        "titulo": "Bluetooth no funciona",
        "resumen": "Servicio bluetooth y estado del adaptador.",
        "diagnosticar": _diag_bluetooth,
    },
    {
        "id": "arranque",
        "titulo": "Ubuntu tarda mucho en arrancar",
        "resumen": "Tiempos de systemd-analyze y servicios fallidos.",
        "diagnosticar": _diag_arranque,
    },
)


def _constructores_panel():
    from analisis_arranque import AnalisisArranque
    from asistente_internet import AsistenteInternet
    from actualizar_todo import ActualizarTodo
    from cat_sistema_extra import (
        Bluetooth,
        EspacioDiscos,
        Impresoras,
        LimpiezaEspacio,
        Pantallas,
        ServiciosFallidos,
        Sonido,
    )
    from centro_aplicaciones import CentroAplicaciones
    from monitor_recursos import MonitorRecursos
    from reparar import RepararUbuntu

    return {
        "AsistenteInternet": AsistenteInternet,
        "Sonido": Sonido,
        "Impresoras": Impresoras,
        "Pantallas": Pantallas,
        "MonitorRecursos": MonitorRecursos,
        "LimpiezaEspacio": LimpiezaEspacio,
        "EspacioDiscos": EspacioDiscos,
        "RepararUbuntu": RepararUbuntu,
        "CentroAplicaciones": CentroAplicaciones,
        "ActualizarTodo": ActualizarTodo,
        "Bluetooth": Bluetooth,
        "AnalisisArranque": AnalisisArranque,
        "ServiciosFallidos": ServiciosFallidos,
    }


def _ejecutar_repair(clave):
    from reparar import repair_apt, repair_cups, repair_dpkg, restart_audio

    mapa = {
        "audio": restart_audio,
        "cups": repair_cups,
        "dpkg": repair_dpkg,
        "apt": repair_apt,
    }
    funcion = mapa.get(clave)
    if not funcion:
        return False, f"Reparacion desconocida: {clave}"
    return funcion()


class AsistenteProblemas:
    """Elige un problema cotidiano y ejecuta el diagnostico concreto."""

    def __init__(self, root):
        self.root = root
        self.root.title("En que podemos ayudarte?")
        self.root.minsize(640, 560)
        self._centrar(700, 620)
        self._problema = None
        self._resultado = None
        self._ocupado = False

        self.root.configure(bg=_BG_UI)
        self.contenedor = tk.Frame(self.root, bg=_BG_UI)
        self.contenedor.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        self._mostrar_lista()

    def _centrar(self, ancho, alto):
        self.root.update_idletasks()
        x = max(0, (self.root.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.root.winfo_screenheight() - alto) // 3)
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _limpiar(self):
        for hijo in self.contenedor.winfo_children():
            hijo.destroy()

    def _mostrar_lista(self):
        self._limpiar()
        self._problema = None
        self._resultado = None
        tk.Label(
            self.contenedor,
            text="Que problema tienes?",
            font=("Arial", 14, "bold"),
            bg=_BG_UI,
            fg=_FRANJA,
        ).pack(anchor="w")
        tk.Label(
            self.contenedor,
            text=(
                "Elige lo que te esta pasando. Manten1d0 hara un diagnostico "
                "especifico y te propondrá la herramienta o reparacion adecuada."
            ),
            wraplength=640,
            justify=tk.LEFT,
            bg=_BG_UI,
            fg="#2c3e50",
        ).pack(anchor="w", pady=(4, 10))

        rejilla = tk.Frame(self.contenedor, bg=_BG_UI)
        rejilla.pack(fill=tk.BOTH, expand=True)
        columnas = 2
        for indice, problema in enumerate(PROBLEMAS):
            fila = indice // columnas
            col = indice % columnas
            btn = tk.Button(
                rejilla,
                text=problema["titulo"],
                anchor="w",
                justify=tk.LEFT,
                font=("Arial", 10, "bold"),
                width=36,
                command=lambda p=problema: self._elegir(p),
            )
            btn.grid(row=fila, column=col, sticky="ew", padx=4, pady=4)
            ToolTip(btn, problema["resumen"])
        rejilla.columnconfigure(0, weight=1)
        rejilla.columnconfigure(1, weight=1)

    def _elegir(self, problema):
        self._problema = problema
        self._mostrar_diagnostico_cargando()
        en_hilo(self.root, problema["diagnosticar"], al_terminar=self._pintar_resultado)

    def _mostrar_diagnostico_cargando(self):
        self._limpiar()
        tk.Label(
            self.contenedor,
            text=self._problema["titulo"],
            font=("Arial", 14, "bold"),
            bg=_BG_UI,
            fg=_FRANJA,
        ).pack(anchor="w")
        self.lbl_estado = tk.Label(
            self.contenedor,
            text="Analizando...",
            font=("Arial", 10, "bold"),
            bg=_BG_UI,
            anchor="w",
        )
        self.lbl_estado.pack(fill=tk.X, pady=(6, 2))
        self.progreso = ttk.Progressbar(self.contenedor, mode="indeterminate")
        self.progreso.pack(fill=tk.X, pady=(0, 8))
        self.progreso.start(12)
        con_tooltip(
            tk.Button(self.contenedor, text="Volver a la lista", command=self._mostrar_lista),
            "Cancelar y elegir otro problema",
        ).pack(anchor="w")

    def _pintar_resultado(self, resultado):
        if not self.root.winfo_exists():
            return
        self._resultado = resultado or {
            "nivel": "info",
            "resumen": "Sin datos.",
            "items": [],
            "acciones": [],
        }
        self._limpiar()

        tk.Label(
            self.contenedor,
            text=self._problema["titulo"],
            font=("Arial", 14, "bold"),
            bg=_BG_UI,
            fg=_FRANJA,
        ).pack(anchor="w")

        nivel = self._resultado.get("nivel", "info")
        color = _COLORES.get(nivel, _COLORES["info"])
        tk.Label(
            self.contenedor,
            text=f"[{_MARCAS.get(nivel, 'INFO')}]  {self._resultado.get('resumen', '')}",
            font=("Arial", 11, "bold"),
            fg=color,
            bg=_BG_UI,
            wraplength=640,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(6, 8))

        tk.Label(
            self.contenedor,
            text="Comprobaciones",
            font=("Arial", 11, "bold"),
            bg=_BG_UI,
            anchor="w",
        ).pack(fill=tk.X)
        lista = tk.Listbox(self.contenedor, height=8, font=("Arial", 10), exportselection=False)
        lista.pack(fill=tk.BOTH, expand=True, pady=(2, 4))
        self._items = self._resultado.get("items") or []
        for item in self._items:
            marca = _MARCAS.get(item.get("nivel"), "INFO")
            lista.insert(tk.END, f"[{marca}] {item.get('titulo', '')}")
        detalle = tk.Label(
            self.contenedor,
            text="Pulsa una comprobacion para ver el detalle.",
            bg=_BG_UI,
            anchor="w",
            justify=tk.LEFT,
            wraplength=640,
        )
        detalle.pack(fill=tk.X, pady=(0, 8))

        def al_sel(_e=None):
            sel = lista.curselection()
            if not sel:
                return
            item = self._items[sel[0]]
            detalle.config(text=item.get("detalle") or "")

        lista.bind("<<ListboxSelect>>", al_sel)
        if self._items:
            lista.selection_set(0)
            al_sel()

        tk.Label(
            self.contenedor,
            text="Que puedes hacer",
            font=("Arial", 11, "bold"),
            bg=_BG_UI,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 2))
        fila_acc = tk.Frame(self.contenedor, bg=_BG_UI)
        fila_acc.pack(fill=tk.X)
        for accion in self._resultado.get("acciones") or []:
            con_tooltip(
                tk.Button(
                    fila_acc,
                    text=accion["etiqueta"],
                    command=lambda a=accion: self._lanzar_accion(a),
                ),
                accion.get("ayuda") or accion["etiqueta"],
            ).pack(side=tk.LEFT, padx=(0, 6), pady=2)

        fila_nav = tk.Frame(self.contenedor, bg=_BG_UI)
        fila_nav.pack(fill=tk.X, pady=(12, 0))
        con_tooltip(
            tk.Button(fila_nav, text="Analizar de nuevo", command=lambda: self._elegir(self._problema)),
            "Repite el diagnostico de este problema",
        ).pack(side=tk.LEFT, padx=(0, 6))
        con_tooltip(
            tk.Button(fila_nav, text="Otro problema", command=self._mostrar_lista),
            "Volver a la lista de problemas",
        ).pack(side=tk.LEFT)

    def _lanzar_accion(self, accion):
        if self._ocupado:
            return
        panel = accion.get("panel")
        repair = accion.get("repair")
        if panel:
            clase = _constructores_panel().get(panel)
            if clase is None:
                messagebox.showinfo(
                    "Asistente",
                    f"No se encontro el panel {panel}.",
                    parent=self.root,
                )
                return
            clase(tk.Toplevel(self.root))
            return
        if repair:
            textos = {
                "audio": (
                    "Se reiniciara el servicio de audio (PipeWire/PulseAudio).",
                    "A veces el audio se queda colgado tras cambiar de salida.",
                    "Bajo: se corta el sonido unos segundos.",
                ),
                "cups": (
                    "Se reiniciara cups.service.",
                    "Sin CUPS no se puede imprimir.",
                    "Bajo: trabajos en cola pueden interrumpirse.",
                ),
                "dpkg": (
                    "Se ejecutara dpkg --configure -a.",
                    "Termina instalaciones a medias que bloquean apt.",
                    "Medio: no interrumpas el proceso.",
                ),
                "apt": (
                    "Se ejecutara apt-get -f install -y.",
                    "Intenta corregir dependencias rotas.",
                    "Medio: puede instalar o quitar paquetes para cuadrar dependencias.",
                ),
            }
            que, por_que, riesgos = textos.get(
                repair,
                ("Se aplicara una reparacion.", "Para intentar solucionar el problema.", "Revisa el resultado."),
            )
            if not confirmar(
                f"Que se va a hacer?\n{que}\n\n"
                f"Por que?\n{por_que}\n\n"
                f"Que riesgos tiene?\n{riesgos}\n\n"
                "Continuar?",
                self.root,
                "Reparar",
            ):
                return

            self._ocupado = True

            def trabajo():
                return _ejecutar_repair(repair)

            def terminar(resultado):
                self._ocupado = False
                ok, mensaje = resultado
                registrar(f"Asistente problemas ({repair})", mensaje[:200], ok)
                if ok:
                    messagebox.showinfo("Reparacion", mensaje, parent=self.root)
                    self._elegir(self._problema)
                else:
                    messagebox.showerror("Reparacion", mensaje, parent=self.root)

            en_hilo(self.root, trabajo, al_terminar=terminar)
