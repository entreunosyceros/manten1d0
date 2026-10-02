"""Analisis de arranque con systemd-analyze: tiempos, fases y servicios lentos."""

import os
import re
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk

import preferencias
from cat_sistema_extra import ServiciosSystemd
from registro import en_hilo
from tooltip import ToolTip, con_tooltip

_ETIQUETAS_FASE = {
    "firmware": "Firmware",
    "loader": "Cargador",
    "kernel": "Kernel",
    "userspace": "Userspace",
}

# Clave (substring en nombre de unidad) -> explicacion
_EXPLICACIONES = (
    ("NetworkManager-wait-online", "Espera a que la red este lista antes de seguir. "
     "Si el router tarda o no hay cable/Wi-Fi, alarga el arranque."),
    ("NetworkManager.service", "Gestiona Wi-Fi y cable. Un arranque normal suele tardar un poco."),
    ("NetworkManager", "Gestiona la conexion de red al iniciar."),
    ("snapd.seeded", "Comprueba que las aplicaciones Snap esten listas. Normal en Ubuntu con snaps."),
    ("snapd.service", "Servicio de Snap. Inicializa paquetes snap al arrancar."),
    ("snapd", "Snap en segundo plano. Si no usas snaps, a veces se puede deshabilitar (con cuidado)."),
    ("cups", "Impresion (CUPS). Normal si imprimes; si no, puede ralentizar un poco el inicio."),
    ("plymouth-quit-wait", "Pantalla de arranque con logo. Espera a que termine la animacion."),
    ("plymouth", "Pantalla de arranque (logo al encender)."),
    ("apt-daily", "Tareas automaticas de actualizacion APT. Pueden coincidir con el arranque."),
    ("docker", "Docker: contenedores. Solo necesario si usas Docker."),
    ("mysql", "Base de datos MySQL/MariaDB. Solo si la usas."),
    ("mariadb", "Base de datos MariaDB. Solo si la usas."),
    ("postgresql", "Base de datos PostgreSQL. Solo si la usas."),
    ("blueman", "Bluetooth (Blueman). Normal si usas Bluetooth."),
    ("apparmor", "Seguridad de perfiles AppArmor. Suele ser necesario en Ubuntu."),
    ("smartmontools", "Monitor SMART de discos. Comprueba salud del disco al arrancar."),
    ("vboxdrv", "VirtualBox (modulo del kernel). Solo si usas maquinas virtuales VirtualBox."),
    ("logrotate", "Rota archivos de registro. Tarea de mantenimiento habitual."),
    ("e2scrub", "Comprobacion del sistema de archivos ext4."),
    ("apport", "Informes de errores de Ubuntu."),
    ("systemd-resolved", "Resolucion DNS del sistema."),
    ("accounts-daemon", "Cuentas de usuario y sesion."),
    ("gdm", "Pantalla de inicio de sesion (GNOME)."),
    ("lightdm", "Pantalla de inicio de sesion (LightDM)."),
    ("sddm", "Pantalla de inicio de sesion (SDDM)."),
    ("ufw", "Cortafuegos ufw al arrancar."),
    ("avahi", "Anuncia el equipo en la red local (impresoras, nombre)."),
)

_EXPLICACION_GENERICA = (
    "Este tiempo indica cuanto tardo esta unidad en completarse durante el ultimo arranque.\n\n"
    "No significa que debas desactivarla: muchas son necesarias. "
    "Si el arranque es muy lento, puedes revisar la lista y, solo si conoces el servicio, "
    "valorar deshabilitarlo desde Servicios (con precaucion)."
)


def _comando(args, timeout=30):
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


def _comando_systemd_analyze(subcomando=None):
    if shutil.which("systemd-analyze") is None:
        return ""
    args = ["systemd-analyze"]
    if subcomando:
        args.append(subcomando)
    timeout = 45 if subcomando == "blame" else 15
    proceso = _comando(args, timeout=timeout)
    if proceso.returncode != 0:
        return (proceso.stderr or proceso.stdout or "").strip()
    return (proceso.stdout or "").strip()


def _parsear_tiempos(salida):
    """Devuelve dict fases, total, target_info o None."""
    if not salida:
        return None
    lineas = [linea.strip() for linea in salida.splitlines() if linea.strip()]
    if not lineas:
        return None
    primera = lineas[0]
    fases = []
    for match in re.finditer(r"([\d.]+)s\s+\((\w+)\)", primera):
        segundos = float(match.group(1))
        clave = match.group(2).lower()
        fases.append({
            "clave": clave,
            "etiqueta": _ETIQUETAS_FASE.get(clave, clave.capitalize()),
            "segundos": segundos,
        })
    total = None
    m_total = re.search(r"=\s*([\d.]+)s", primera)
    if m_total:
        total = float(m_total.group(1))
    elif fases:
        total = sum(f["segundos"] for f in fases)
    target_info = ""
    for linea in lineas[1:]:
        if "reached after" in linea.lower() or "target" in linea.lower():
            target_info = linea
            break
    if not fases and total is None:
        return None
    return {"fases": fases, "total": total, "target_info": target_info, "linea": primera}


def _parsear_blame(salida, limite=15):
    servicios = []
    for linea in (salida or "").splitlines():
        m = re.match(r"^\s*([\d.]+)s\s+(.+)$", linea.strip())
        if not m:
            continue
        segundos = float(m.group(1))
        unidad = m.group(2).strip()
        if not unidad:
            continue
        servicios.append({"segundos": segundos, "unidad": unidad})
    servicios.sort(key=lambda s: s["segundos"], reverse=True)
    return servicios[:limite]


def _explicacion_servicio(unidad):
    nombre = (unidad or "").lower()
    for clave, texto in _EXPLICACIONES:
        if clave.lower() in nombre:
            return texto
    return _EXPLICACION_GENERICA


def analizar_arranque():
    if shutil.which("systemd-analyze") is None:
        return {
            "ok": False,
            "error": "systemd-analyze no esta instalado o no esta en el PATH.",
            "fases": [],
            "total": None,
            "target_info": "",
            "servicios_lentos": [],
            "linea": "",
        }
    salida_time = _comando_systemd_analyze()
    parsed = _parsear_tiempos(salida_time)
    if not parsed:
        return {
            "ok": False,
            "error": "No se pudo leer el tiempo de arranque. Salida inesperada de systemd-analyze.",
            "fases": [],
            "total": None,
            "target_info": "",
            "servicios_lentos": [],
            "linea": salida_time.splitlines()[0] if salida_time else "",
        }
    salida_blame = _comando_systemd_analyze("blame")
    servicios = _parsear_blame(salida_blame)
    return {
        "ok": True,
        "error": None,
        "fases": parsed["fases"],
        "total": parsed["total"],
        "target_info": parsed.get("target_info") or "",
        "servicios_lentos": servicios,
        "linea": parsed.get("linea") or "",
    }


def texto_tiempo_arranque_informacion():
    """Una linea para Informacion / barra lateral (compatible con la UI anterior)."""
    salida = _comando_systemd_analyze()
    if not salida.strip():
        return "No disponible"
    parsed = _parsear_tiempos(salida)
    if parsed and parsed.get("linea"):
        return parsed["linea"]
    primera = salida.strip().splitlines()[0].strip()
    return primera or "No disponible"


def _formato_segundos(valor):
    try:
        return f"{float(valor):.1f} s"
    except (TypeError, ValueError):
        return "N/D"


class AnalisisArranque:
    """Panel visual: tiempos de arranque y servicios que mas tardan."""

    def __init__(self, root):
        self.root = root
        self.root.title("Arranque")
        self.root.minsize(620, 520)
        self._centrar(640, 560)
        self._ocupado = False
        self._datos = None
        self._filas_fase = []
        self._servicios = []

        tk.Label(self.root, text="Arranque", font=("Arial", 14, "bold")).pack(pady=(12, 2))
        tk.Label(
            self.root,
            text="Por que tarda en arrancar? Tiempos del ultimo arranque segun systemd-analyze.",
            wraplength=600,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 6))

        self.lbl_estado = tk.Label(
            self.root, text="Analizando arranque...", anchor="w", font=("Arial", 10, "bold")
        )
        self.lbl_estado.pack(fill=tk.X, padx=14)
        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(2, 6))

        self.lbl_total = tk.Label(
            self.root, text="Tiempo total: --", font=("Arial", 12, "bold"), anchor="w"
        )
        self.lbl_total.pack(fill=tk.X, padx=14, pady=(4, 2))

        self.marco_fases = tk.LabelFrame(self.root, text="Fases del arranque", padx=10, pady=8)
        self.marco_fases.pack(fill=tk.X, padx=14, pady=(4, 8))

        self.lbl_target = tk.Label(
            self.root, text="", anchor="w", wraplength=600, justify=tk.LEFT, font=("Arial", 9)
        )
        self.lbl_target.pack(fill=tk.X, padx=14)

        cuerpo = tk.Frame(self.root)
        cuerpo.pack(fill=tk.BOTH, expand=True, padx=14, pady=(4, 4))

        izq = tk.Frame(cuerpo)
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(izq, text="Servicios mas lentos", font=("Arial", 11, "bold"), anchor="w").pack(
            fill=tk.X
        )
        cols = ("tiempo", "servicio")
        self.tree = ttk.Treeview(izq, columns=cols, show="headings", selectmode="browse", height=10)
        self.tree.heading("tiempo", text="Tiempo")
        self.tree.heading("servicio", text="Servicio")
        self.tree.column("tiempo", width=72, stretch=False)
        self.tree.column("servicio", width=280, stretch=True)
        scroll = ttk.Scrollbar(izq, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(2, 0))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(2, 0))
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._mostrar_servicio())

        der = tk.Frame(cuerpo, width=240)
        der.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        der.pack_propagate(False)
        tk.Label(der, text="Detalle", font=("Arial", 11, "bold"), anchor="w").pack(fill=tk.X)
        self.lbl_detalle = tk.Label(
            der,
            text="Selecciona un servicio para ver que hace y por que puede tardar.",
            justify=tk.LEFT,
            anchor="nw",
            wraplength=220,
        )
        self.lbl_detalle.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        pie = tk.Frame(self.root)
        pie.pack(pady=(6, 12))
        self.btn_analizar = con_tooltip(
            tk.Button(pie, text="Analizar arranque", width=16, command=self.cargar),
            "Vuelve a leer systemd-analyze y blame del ultimo arranque",
        )
        self.btn_analizar.pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Abrir Servicios", width=14, command=self._abrir_servicios),
            "Lista servicios systemd (iniciar, parar, habilitar). No desactiva nada desde aqui.",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Cerrar", width=10, command=self.root.destroy),
            "Cierra esta ventana",
        ).pack(side=tk.LEFT, padx=4)

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)

        if shutil.which("systemd-analyze") is None:
            self.lbl_estado.config(
                text="systemd-analyze no esta disponible en este sistema.",
                fg="#c0392b",
            )
            self.btn_analizar.config(state=tk.DISABLED)
        else:
            self.cargar()

    def _centrar(self, ancho, alto):
        try:
            from bandeja import preparar_ventana_app

            preparar_ventana_app(self.root, tamano=64)
        except Exception:
            pass
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - ancho) // 2
        y = (self.root.winfo_screenheight() - alto) // 2
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        try:
            self.btn_analizar.config(state=tk.DISABLED if ocupado else tk.NORMAL)
        except tk.TclError:
            pass
        if ocupado:
            try:
                self.progreso.start(12)
            except tk.TclError:
                pass
        else:
            try:
                self.progreso.stop()
            except tk.TclError:
                pass
        if mensaje:
            self.lbl_estado.config(text=mensaje, fg="#2471a3")

    def cargar(self):
        if self._ocupado:
            return
        if shutil.which("systemd-analyze") is None:
            return
        self._set_ocupado(True, "Analizando arranque...")

        def al_terminar(datos):
            self._set_ocupado(False)
            self._pintar(datos)

        def al_error(error):
            self._set_ocupado(False)
            self.lbl_estado.config(text=f"Error: {error}", fg="#c0392b")

        en_hilo(self.root, analizar_arranque, al_terminar=al_terminar, al_error=al_error)

    def _limpiar_fases(self):
        for fila in self._filas_fase:
            try:
                fila["marco"].destroy()
            except tk.TclError:
                pass
        self._filas_fase = []

    def _dibujar_fases(self, fases):
        self._limpiar_fases()
        if not fases:
            tk.Label(
                self.marco_fases,
                text="No hay datos de fases.",
                anchor="w",
            ).pack(fill=tk.X)
            return
        maximo = max(f["segundos"] for f in fases) or 1.0
        ancho_barra = 320
        alto_barra = 14
        for fase in fases:
            fila = tk.Frame(self.marco_fases)
            fila.pack(fill=tk.X, pady=3)
            tk.Label(fila, text=fase["etiqueta"], width=12, anchor="w").pack(side=tk.LEFT)
            canvas = tk.Canvas(
                fila,
                width=ancho_barra,
                height=alto_barra,
                highlightthickness=0,
                bg=preferencias.color_fondo() if hasattr(preferencias, "color_fondo") else "#f0f0f0",
            )
            canvas.pack(side=tk.LEFT, padx=(4, 8))
            ancho_fill = max(2, int(ancho_barra * fase["segundos"] / maximo))
            canvas.create_rectangle(0, 2, ancho_fill, alto_barra - 2, fill="#2471a3", outline="")
            tk.Label(fila, text=_formato_segundos(fase["segundos"]), width=10, anchor="w").pack(
                side=tk.LEFT
            )
            self._filas_fase.append({"marco": fila, "canvas": canvas})

    def _pintar(self, datos):
        self._datos = datos
        self._servicios = datos.get("servicios_lentos") or []

        if not datos.get("ok"):
            self.lbl_total.config(text="Tiempo total: --")
            self.lbl_target.config(text="")
            self._dibujar_fases([])
            self.lbl_estado.config(text=datos.get("error") or "Error desconocido", fg="#c0392b")
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            return

        total = datos.get("total")
        self.lbl_total.config(
            text=f"Tiempo total: {_formato_segundos(total)}" if total is not None else "Tiempo total: --"
        )
        target = datos.get("target_info") or ""
        self.lbl_target.config(text=target)
        self._dibujar_fases(datos.get("fases") or [])

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for idx, srv in enumerate(self._servicios):
            nombre_corto = srv["unidad"].replace(".service", "")
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(_formato_segundos(srv["segundos"]), nombre_corto),
            )

        self.lbl_detalle.config(
            text="Selecciona un servicio para ver que hace y por que puede tardar."
        )
        n = len(self._servicios)
        if n:
            self.lbl_estado.config(
                text=f"Analisis listo. {n} servicio(s) mas lentos listados (solo informativo).",
                fg="#1e8449",
            )
        else:
            self.lbl_estado.config(text="Analisis listo.", fg="#1e8449")

    def _mostrar_servicio(self):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        if idx < 0 or idx >= len(self._servicios):
            return
        srv = self._servicios[idx]
        expl = _explicacion_servicio(srv["unidad"])
        texto = (
            f"{srv['unidad']}\n"
            f"Tiempo en el ultimo arranque: {_formato_segundos(srv['segundos'])}\n\n"
            f"{expl}"
        )
        self.lbl_detalle.config(text=texto)

    def _abrir_servicios(self):
        ServiciosSystemd(tk.Toplevel(self.root))
