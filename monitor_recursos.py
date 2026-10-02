"""Monitor del sistema simplificado: CPU, RAM, disco, procesos y acciones."""

import os
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import messagebox, ttk

import psutil

import preferencias
from cat_sistema import MonitorizarSistema
from cat_sistema_extra import _formato_tamano
from diagnostico import _leer_temperatura_cpu
from registro import confirmar, en_hilo, registrar
from tooltip import ToolTip, con_tooltip

_INTERVALO_MS = 2500
_TOP_PROCESOS = 30
_ANCHO_BARRA = 10

# PID bajos del sistema (no recomendar matar)
_PIDS_SISTEMA = {1, 2}


def _barra_ascii(porcentaje, ancho=_ANCHO_BARRA):
    try:
        pct = max(0.0, min(100.0, float(porcentaje)))
    except (TypeError, ValueError):
        pct = 0.0
    lleno = int(round(ancho * pct / 100.0))
    lleno = max(0, min(ancho, lleno))
    return "#" * lleno + "-" * (ancho - lleno)


def _formato_memoria(nbytes):
    return _formato_tamano(nbytes)


def _formato_cpu(pct):
    try:
        return f"{float(pct):.0f} %"
    except (TypeError, ValueError):
        return "N/D"


def _metrica_orden(proc, criterio):
    if criterio == "cpu":
        return proc.get("cpu", 0.0) or 0.0
    if criterio == "ram":
        return proc.get("rss", 0) or 0
    if criterio == "disco":
        return proc.get("io_bytes", 0) or 0
    if criterio == "red":
        return proc.get("conexiones", 0) or 0
    return 0


def _texto_consumo(proc, criterio):
    if criterio == "cpu":
        return _formato_cpu(proc.get("cpu"))
    if criterio == "ram":
        return _formato_memoria(proc.get("rss"))
    if criterio == "disco":
        return _formato_memoria(proc.get("io_bytes"))
    if criterio == "red":
        n = proc.get("conexiones", 0)
        return f"{n} conex."
    return "N/D"


def _recopilar_procesos():
    psutil.cpu_percent(interval=0.1)
    lista = []
    procesos = list(psutil.process_iter(["pid", "name"]))
    for proc in procesos:
        try:
            proc.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.12)
    for proc in procesos:
        try:
            info = proc.info
            pid = info.get("pid")
            nombre = info.get("name") or "?"
            cpu = proc.cpu_percent(None)
            mem = proc.memory_info()
            rss = mem.rss if mem else 0
            io_bytes = 0
            try:
                io = proc.io_counters()
                io_bytes = (io.read_bytes or 0) + (io.write_bytes or 0)
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                pass
            conexiones = 0
            try:
                conexiones = len(proc.connections(kind="inet"))
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            exe = ""
            try:
                exe = proc.exe() or ""
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                pass
            lista.append({
                "pid": pid,
                "name": nombre,
                "cpu": cpu,
                "rss": rss,
                "io_bytes": io_bytes,
                "conexiones": conexiones,
                "exe": exe,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return lista


def recopilar_estado(criterio_orden="ram", net_anterior=None):
    """Snapshot de sistema y top procesos. criterio: cpu, ram, disco, red."""
    criterio = (criterio_orden or "ram").lower()
    if criterio not in ("cpu", "ram", "disco", "red"):
        criterio = "ram"

    cpu_pct = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disco = psutil.disk_usage("/")
    temp = _leer_temperatura_cpu()
    temp_txt = f"{temp['current']:.0f} C" if temp and temp.get("current") is not None else "N/D"

    red_info = ""
    net_actual = None
    try:
        net = psutil.net_io_counters(pernic=False)
        net_actual = (net.bytes_sent, net.bytes_recv)
        if net_anterior and len(net_anterior) == 2:
            ds = max(0, net.bytes_sent - net_anterior[0])
            dr = max(0, net.bytes_recv - net_anterior[1])
            red_info = f"Red (desde ultima lectura): subida {_formato_memoria(ds)}, bajada {_formato_memoria(dr)}"
    except Exception:
        pass

    procesos = _recopilar_procesos()
    procesos.sort(key=lambda p: _metrica_orden(p, criterio), reverse=True)
    procesos = procesos[:_TOP_PROCESOS]

    return {
        "cpu_pct": cpu_pct,
        "ram_pct": mem.percent,
        "disco_pct": disco.percent,
        "temp_txt": temp_txt,
        "red_info": red_info,
        "net_actual": net_actual,
        "procesos": procesos,
        "criterio": criterio,
    }


def _intentar_activar_ventana(nombre):
    if not shutil.which("wmctrl"):
        return False, "wmctrl no esta instalado."
    try:
        resultado = subprocess.run(
            ["wmctrl", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    if resultado.returncode != 0:
        return False, (resultado.stderr or "No se pudo listar ventanas.").strip()
    busqueda = (nombre or "").lower()
    if not busqueda:
        return False, "Nombre de proceso vacio."
    for linea in (resultado.stdout or "").splitlines():
        partes = linea.split(None, 3)
        if len(partes) < 4:
            continue
        titulo = partes[3].lower()
        if busqueda in titulo or titulo in busqueda:
            ventana_id = partes[0]
            activar = subprocess.run(
                ["wmctrl", "-ia", ventana_id],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if activar.returncode == 0:
                return True, titulo
    return False, "No se encontro una ventana con ese nombre."


class MonitorRecursos:
    """Panel: uso de recursos y procesos que mas consumen."""

    def __init__(self, root):
        self.root = root
        self.root.title("Monitor Del Sistema")
        self.root.minsize(680, 580)
        self._centrar(720, 620)
        self._ocupado = False
        self._net_anterior = None
        self._after_id = None
        self._procesos = []
        self._criterio = tk.StringVar(value="ram")

        tk.Label(self.root, text="Monitor del sistema", font=("Arial", 14, "bold")).pack(
            pady=(12, 2)
        )
        tk.Label(
            self.root,
            text="Que esta consumiendo recursos? Se actualiza solo cada pocos segundos.",
            wraplength=680,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 8))

        self.marco_barras = tk.Frame(self.root)
        self.marco_barras.pack(fill=tk.X, padx=14, pady=(0, 6))
        self._lbl_barras = {}
        for clave, titulo in (
            ("cpu", "CPU"),
            ("ram", "RAM"),
            ("disco", "DISCO"),
            ("temp", "TEMPERATURA"),
        ):
            fila = tk.Frame(self.marco_barras)
            fila.pack(fill=tk.X, pady=2)
            tk.Label(fila, text=titulo, width=14, anchor="w", font=("Courier", 10)).pack(
                side=tk.LEFT
            )
            lbl = tk.Label(fila, text="----------  --", anchor="w", font=("Courier", 10))
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._lbl_barras[clave] = lbl

        self.lbl_red = tk.Label(self.root, text="", anchor="w", font=("Arial", 9))
        self.lbl_red.pack(fill=tk.X, padx=14, pady=(0, 4))

        marco_ord = tk.LabelFrame(
            self.root, text="Que esta consumiendo recursos?", padx=10, pady=6
        )
        marco_ord.pack(fill=tk.X, padx=14, pady=(4, 6))
        for valor, texto, tip in (
            ("cpu", "CPU", "Ordena por uso de procesador"),
            ("ram", "RAM", "Ordena por memoria (habitual para ver quien ocupa mas)"),
            ("disco", "Disco", "Ordena por lectura+escritura acumulada del proceso"),
            (
                "red",
                "Red",
                "Ordena por numero de conexiones de red activas (no es velocidad en MB/s)",
            ),
        ):
            rb = tk.Radiobutton(
                marco_ord,
                text=texto,
                variable=self._criterio,
                value=valor,
                command=self._al_cambiar_criterio,
            )
            rb.pack(side=tk.LEFT, padx=8)
            ToolTip(rb, tip)

        tk.Label(self.root, text="PROCESOS", font=("Arial", 11, "bold"), anchor="w").pack(
            fill=tk.X, padx=14
        )
        marco_tree = tk.Frame(self.root)
        marco_tree.pack(fill=tk.BOTH, expand=True, padx=14, pady=(2, 6))
        cols = ("nombre", "pid", "consumo")
        self.tree = ttk.Treeview(
            marco_tree, columns=cols, show="headings", selectmode="browse", height=12
        )
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("pid", text="PID")
        self.tree.heading("consumo", text="Memoria")
        self.tree.column("nombre", width=220, stretch=True)
        self.tree.column("pid", width=70, stretch=False)
        self.tree.column("consumo", width=120, stretch=False)
        scroll = ttk.Scrollbar(marco_tree, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.lbl_estado = tk.Label(self.root, text="Leyendo recursos...", anchor="w")
        self.lbl_estado.pack(fill=tk.X, padx=14)

        pie = tk.Frame(self.root)
        pie.pack(pady=(4, 12))
        con_tooltip(
            tk.Button(pie, text="Abrir", width=10, command=self._abrir),
            "Activa la ventana del proceso (wmctrl) o muestra su ruta",
        ).pack(side=tk.LEFT, padx=3)
        con_tooltip(
            tk.Button(pie, text="Finalizar", width=10, command=self._finalizar),
            "Cierra el proceso seleccionado (pide confirmacion)",
        ).pack(side=tk.LEFT, padx=3)
        con_tooltip(
            tk.Button(pie, text="Actualizar", width=10, command=self._refrescar_manual),
            "Vuelve a leer CPU, memoria y procesos",
        ).pack(side=tk.LEFT, padx=3)
        con_tooltip(
            tk.Button(pie, text="Ver grafico", width=11, command=self._ver_grafico),
            "Abre el grafico matplotlib del monitor antiguo",
        ).pack(side=tk.LEFT, padx=3)
        con_tooltip(
            tk.Button(pie, text="Cerrar", width=8, command=self._cerrar),
            "Cierra esta ventana",
        ).pack(side=tk.LEFT, padx=3)

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)

        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)
        self._programar_refresco()

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

    def _cerrar(self):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self.root.destroy()

    def _al_cambiar_criterio(self):
        crit = self._criterio.get()
        titulos = {
            "cpu": "CPU %",
            "ram": "Memoria",
            "disco": "Disco I/O",
            "red": "Conexiones",
        }
        self.tree.heading("consumo", text=titulos.get(crit, "Consumo"))
        self._refrescar_manual()

    def _programar_refresco(self):
        if not self.root.winfo_exists():
            return
        self._refrescar(en_auto=True)

    def _refrescar_manual(self):
        self._refrescar(en_auto=False)

    def _refrescar(self, en_auto=False):
        if self._ocupado:
            if en_auto:
                self._after_id = self.root.after(_INTERVALO_MS, self._programar_refresco)
            return
        self._ocupado = True
        criterio = self._criterio.get()
        net_prev = self._net_anterior

        def trabajo():
            return recopilar_estado(criterio, net_prev)

        def al_terminar(datos):
            self._ocupado = False
            if not self.root.winfo_exists():
                return
            self._pintar(datos)
            self.lbl_estado.config(text="Actualizado.", fg="#1e8449")
            self._after_id = self.root.after(_INTERVALO_MS, self._programar_refresco)

        def al_error(error):
            self._ocupado = False
            if not self.root.winfo_exists():
                return
            self.lbl_estado.config(text=f"Error: {error}", fg="#c0392b")
            self._after_id = self.root.after(_INTERVALO_MS, self._programar_refresco)

        if not en_auto:
            self.lbl_estado.config(text="Leyendo recursos...", fg="#2471a3")
        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)

    def _pintar(self, datos):
        self._procesos = datos.get("procesos") or []
        if datos.get("net_actual"):
            self._net_anterior = datos["net_actual"]

        cpu = datos.get("cpu_pct", 0)
        ram = datos.get("ram_pct", 0)
        disco = datos.get("disco_pct", 0)
        self._lbl_barras["cpu"].config(
            text=f"{_barra_ascii(cpu)}  {_formato_cpu(cpu)}"
        )
        self._lbl_barras["ram"].config(
            text=f"{_barra_ascii(ram)}  {_formato_cpu(ram)}"
        )
        self._lbl_barras["disco"].config(
            text=f"{_barra_ascii(disco)}  {_formato_cpu(disco)}"
        )
        self._lbl_barras["temp"].config(text=datos.get("temp_txt") or "N/D")
        self.lbl_red.config(text=datos.get("red_info") or "")

        criterio = datos.get("criterio") or self._criterio.get()
        sel_pid = None
        sel = self.tree.selection()
        if sel:
            try:
                sel_pid = int(self.tree.item(sel[0])["values"][1])
            except (ValueError, TypeError, tk.TclError):
                sel_pid = None

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        reselect = None
        for idx, proc in enumerate(self._procesos):
            iid = str(idx)
            vals = (proc["name"], proc["pid"], _texto_consumo(proc, criterio))
            self.tree.insert("", tk.END, iid=iid, values=vals)
            if sel_pid is not None and proc["pid"] == sel_pid:
                reselect = iid
        if reselect:
            self.tree.selection_set(reselect)
            self.tree.see(reselect)

    def _proceso_seleccionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(
                "Monitor Del Sistema",
                "Selecciona un proceso de la lista.",
                parent=self.root,
            )
            return None
        try:
            idx = int(sel[0])
        except ValueError:
            return None
        if idx < 0 or idx >= len(self._procesos):
            return None
        return self._procesos[idx]

    def _abrir(self):
        proc = self._proceso_seleccionado()
        if not proc:
            return
        ok, detalle = _intentar_activar_ventana(proc["name"])
        if ok:
            self.lbl_estado.config(text=f"Ventana activada: {detalle}", fg="#1e8449")
            return
        texto = (
            f"Proceso: {proc['name']}\n"
            f"PID: {proc['pid']}\n"
        )
        if proc.get("exe"):
            texto += f"Ejecutable: {proc['exe']}\n"
        texto += f"\nNo se pudo cambiar a la ventana ({detalle})."
        messagebox.showinfo("Monitor Del Sistema", texto, parent=self.root)

    def _finalizar(self):
        proc = self._proceso_seleccionado()
        if not proc:
            return
        pid = proc["pid"]
        nombre = proc["name"]
        if pid in _PIDS_SISTEMA or pid <= 2:
            messagebox.showwarning(
                "Monitor Del Sistema",
                "No conviene finalizar procesos basicos del sistema.",
                parent=self.root,
            )
            return
        mensaje = (
            f"Que se va a hacer?\n"
            f"Se enviara una senal de cierre al proceso {nombre} (PID {pid}).\n\n"
            f"Por que?\n"
            f"Has pedido liberar recursos cerrando ese programa.\n\n"
            f"Que riesgos tiene?\n"
            f"Se puede perder trabajo no guardado. "
            f"No cierres procesos que no reconozcas (systemd, kernel, etc.).\n\n"
            f"Continuar?"
        )
        if not confirmar(mensaje, self.root, "Finalizar proceso"):
            return
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                pass
            registrar(f"Finalizar proceso {nombre}", f"PID {pid} terminate", True)
            messagebox.showinfo(
                "Monitor Del Sistema",
                f"Senal de cierre enviada a {nombre} (PID {pid}).",
                parent=self.root,
            )
        except psutil.NoSuchProcess:
            messagebox.showinfo(
                "Monitor Del Sistema",
                "El proceso ya no existe.",
                parent=self.root,
            )
        except psutil.AccessDenied:
            messagebox.showerror(
                "Monitor Del Sistema",
                "Sin permiso para cerrar ese proceso.",
                parent=self.root,
            )
            registrar(f"Finalizar proceso {nombre}", "access denied", False)
        except Exception as error:
            messagebox.showerror("Monitor Del Sistema", str(error), parent=self.root)
            registrar(f"Finalizar proceso {nombre}", str(error), False)
        self._refrescar_manual()

    def _ver_grafico(self):
        MonitorizarSistema(tk.Toplevel(self.root)).monitorizar_sistema()
