"""
Herramientas extra de la categoría Sistema:
limpieza de espacio en disco, salud SMART, uso por carpetas, cortafuegos,
servicios systemd (incluidos los que fallan), Snap/Flatpak y Bluetooth.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import preferencias
from password import obtener_contrasena
from tooltip import ToolTip
from registro import registrar, registrar_comando, confirmar, en_hilo, sudo_run


def _centrar_ventana(ventana, ancho, alto):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def _aplicar_tema(ventana):
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)


def _formato_tamano(nbytes):
    try:
        nbytes = float(nbytes)
    except (TypeError, ValueError):
        return "N/D"
    if nbytes < 0:
        return "N/D"
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unidad}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def _comando(args, timeout=60, env=None):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    if env:
        entorno.update(env)
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        resultado = subprocess.CompletedProcess(args, 1, "", str(error))
        return resultado


_RE_KERNEL = re.compile(
    r"^linux-(?:image|image-unsigned|modules|modules-extra|headers)-(\d+\.\d+\.\d+-\d+)(?:-generic)?$"
)


def _clave_kernel(version):
    coincidencia = re.match(r"(\d+)\.(\d+)\.(\d+)-(\d+)", version)
    if not coincidencia:
        return (0, 0, 0, 0)
    return tuple(int(parte) for parte in coincidencia.groups())


def _versiones_viejas():
    """Paquetes de kernels que no son el que está en marcha ni el anterior."""
    actual = os.uname().release
    coincidencia = re.match(r"(\d+\.\d+\.\d+-\d+)", actual)
    version_actual = coincidencia.group(1) if coincidencia else ""
    proceso = _comando(
        [
            "dpkg-query", "-W", "-f", "${db:Status-Status}\t${Package}\t${Installed-Size}\n",
            "linux-image-*", "linux-modules-*", "linux-headers-*",
        ],
        timeout=30,
    )
    versiones = {}
    for linea in (proceso.stdout or "").splitlines():
        partes = linea.split("\t")
        if len(partes) < 3:
            continue
        estado, nombre, tamano = partes[0], partes[1], partes[2]
        if estado not in ("installed", "config-files"):
            continue
        encontrada = _RE_KERNEL.match(nombre)
        if not encontrada:
            continue
        versiones.setdefault(encontrada.group(1), []).append((nombre, int(tamano or 0) * 1024))
    if not versiones:
        return {
            "paquetes": [],
            "tamano": 0,
            "texto": "No hay versiones viejas que quitar.",
        }
    orden = sorted(versiones, key=_clave_kernel)
    conservar = set()
    if version_actual:
        conservar.add(version_actual)
    conservar.add(orden[-1])
    anteriores = [version for version in orden if _clave_kernel(version) < _clave_kernel(version_actual or orden[-1])]
    if anteriores:
        conservar.add(anteriores[-1])
    paquetes = []
    tamano = 0
    for version, entradas in versiones.items():
        if version in conservar:
            continue
        for nombre, peso in entradas:
            paquetes.append(nombre)
            tamano += peso
    if not paquetes:
        return {
            "paquetes": [],
            "tamano": 0,
            "texto": f"No hay versiones viejas. Se conserva la que está en marcha ({version_actual or actual}).",
        }
    return {
        "paquetes": paquetes,
        "tamano": tamano,
        "texto": (
            f"Se deja la que está en marcha ({version_actual or actual}) y la anterior, "
            f"por si hay que arrancar con ella. Hay {len({_RE_KERNEL.match(p).group(1) for p in paquetes if _RE_KERNEL.match(p)})} versiones que se pueden quitar."
        ),
    }


def _quitar_kernels_viejos(paquetes, contrasena):
    actual = os.uname().release
    coincidencia = re.match(r"(\d+\.\d+\.\d+-\d+)", actual)
    version_actual = coincidencia.group(1) if coincidencia else actual
    seguros = []
    for nombre in paquetes:
        encontrada = _RE_KERNEL.match(nombre)
        if not encontrada or encontrada.group(1) == version_actual:
            continue
        seguros.append(nombre)
    if not seguros:
        return "Versiones viejas: no había nada que quitar."
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    entorno["DEBIAN_FRONTEND"] = "noninteractive"
    try:
        resultado = subprocess.run(
            ["sudo", "-S", "-p", "", "apt-get", "purge", "-y", *seguros],
            input=f"{contrasena}\n",
            capture_output=True,
            text=True,
            timeout=900,
            env=entorno,
        )
    except subprocess.TimeoutExpired:
        return "Versiones viejas: tardó demasiado y se interrumpió."
    ok = resultado.returncode == 0
    registrar(
        "Versiones viejas del sistema",
        f"apt-get purge de {len(seguros)} paquetes; se conservó {version_actual}",
        ok,
    )
    if ok:
        return f"Versiones viejas: OK ({len(seguros)} paquetes)."
    detalle = (resultado.stderr or resultado.stdout or "error").strip().splitlines()
    return "Versiones viejas: " + (detalle[-1] if detalle else "error")


def _comando_sudo(args, contrasena, timeout=180):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(
            ["sudo", "-S", "-p", "", *args],
            input=f"{contrasena}\n",
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def _tamano_ruta(ruta):
    if not os.path.exists(ruta):
        return 0
    proceso = _comando(["du", "-sb", ruta], timeout=90)
    if proceso.returncode == 0 and proceso.stdout.strip():
        try:
            return int(proceso.stdout.split()[0])
        except (ValueError, IndexError):
            pass
    total = 0
    if os.path.isfile(ruta):
        try:
            return os.path.getsize(ruta)
        except OSError:
            return 0
    for raiz, _dirs, archivos in os.walk(ruta):
        for archivo in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, archivo))
            except OSError:
                continue
    return total


class LimpiezaEspacio:
    """Analiza y limpia cachés, logs, papelera y revisiones antiguas de snap."""

    def __init__(self, root):
        self.root = root
        self.root.title("Limpieza De Espacio En Disco")
        _centrar_ventana(self.root, 740, 560)
        self.items = []
        self.vars = {}
        self._analizando = False

        self.lbl_resumen = tk.Label(
            self.root,
            text="Calculando uso de disco...",
            font=("Arial", 11, "bold"),
            justify=tk.LEFT,
        )
        self.lbl_resumen.pack(anchor="w", padx=12, pady=(12, 6))

        marco_lista = tk.Frame(self.root)
        marco_lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        canvas = tk.Canvas(marco_lista, highlightthickness=0)
        scroll = ttk.Scrollbar(marco_lista, orient="vertical", command=canvas.yview)
        self.frame_items = tk.Frame(canvas)
        self.frame_items.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        ventana_items = canvas.create_window((0, 0), window=self.frame_items, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(ventana_items, width=e.width))
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.lbl_estado = tk.Label(self.root, text="", anchor="w")
        self.lbl_estado.pack(fill=tk.X, padx=12)

        marco_botones = tk.Frame(self.root)
        marco_botones.pack(pady=10)

        self.btn_analizar = tk.Button(marco_botones, text="Volver a analizar", command=self.analizar)
        self.btn_analizar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_analizar, "Vuelve a calcular el espacio recuperable")

        self.btn_limpiar = tk.Button(marco_botones, text="Limpiar seleccionados", command=self.limpiar)
        self.btn_limpiar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_limpiar, "Elimina solo las categorías marcadas")

        _aplicar_tema(self.root)
        self.analizar()

    def _uso_discos(self):
        lineas = []
        for punto in ("/", os.path.expanduser("~")):
            try:
                uso = shutil.disk_usage(punto)
                porcentaje = (uso.used / uso.total) * 100 if uso.total else 0
                lineas.append(
                    f"{punto}: {_formato_tamano(uso.used)} / {_formato_tamano(uso.total)} "
                    f"({porcentaje:.0f}% usado, {_formato_tamano(uso.free)} libres)"
                )
            except OSError:
                continue
        return "\n".join(lineas) if lineas else "No se pudo leer el uso de disco."

    def _recoger_elementos(self):
        home = os.path.expanduser("~")
        elementos = []

        apt = 0
        apt_dir = "/var/cache/apt/archives"
        if os.path.isdir(apt_dir):
            try:
                for nombre in os.listdir(apt_dir):
                    if nombre.endswith(".deb"):
                        try:
                            apt += os.path.getsize(os.path.join(apt_dir, nombre))
                        except OSError:
                            continue
            except OSError:
                apt = _tamano_ruta(apt_dir)
        elementos.append({
            "id": "apt_cache",
            "nombre": "Caché de APT",
            "descripcion": "Paquetes .deb descargados que ya no hacen falta para instalar.",
            "tamano": apt,
            "sudo": True,
        })

        proceso_auto = _comando(["apt-get", "--dry-run", "autoremove"], timeout=90)
        texto_auto = (proceso_auto.stdout or "") + (proceso_auto.stderr or "")
        coincidencia = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(kB|KB|MB|GB|B)",
            texto_auto,
            re.IGNORECASE,
        )
        tamano_auto = 0
        if coincidencia:
            cantidad = float(coincidencia.group(1).replace(",", "."))
            unidad = coincidencia.group(2).upper().replace("KB", "KB")
            factores = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}
            tamano_auto = int(cantidad * factores.get(unidad, 1))
        elementos.append({
            "id": "autoremove",
            "nombre": "Paquetes huérfanos (autoremove)",
            "descripcion": "Paquetes que ya no son dependencia de ninguno instalado.",
            "tamano": tamano_auto,
            "sudo": True,
        })

        proceso_journal = _comando(["journalctl", "--disk-usage"], timeout=30)
        texto_journal = (proceso_journal.stdout or "") + (proceso_journal.stderr or "")
        coincidencia_j = re.search(
            r"(\d+(?:[.,]\d+)?)\s*([KMGT])i?B?",
            texto_journal,
            re.IGNORECASE,
        )
        tamano_journal = 0
        if coincidencia_j:
            cantidad = float(coincidencia_j.group(1).replace(",", "."))
            prefijo = (coincidencia_j.group(2) or "").upper()
            factores = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}
            tamano_journal = int(cantidad * factores.get(prefijo, 1))
        elementos.append({
            "id": "journal",
            "nombre": "Logs de journald",
            "descripcion": "Se conservarán los registros de los últimos 7 días.",
            "tamano": tamano_journal,
            "sudo": True,
        })

        elementos.append({
            "id": "thumbnails",
            "nombre": "Miniaturas de imágenes",
            "descripcion": "Caché de previsualizaciones en ~/.cache/thumbnails.",
            "tamano": _tamano_ruta(os.path.join(home, ".cache", "thumbnails")),
            "sudo": False,
        })

        elementos.append({
            "id": "pip",
            "nombre": "Caché de pip",
            "descripcion": "Ruedas y archivos temporales de pip en ~/.cache/pip.",
            "tamano": _tamano_ruta(os.path.join(home, ".cache", "pip")),
            "sudo": False,
        })

        elementos.append({
            "id": "trash",
            "nombre": "Papelera de reciclaje",
            "descripcion": "Archivos enviados a la papelera del usuario.",
            "tamano": _tamano_ruta(os.path.join(home, ".local", "share", "Trash")),
            "sudo": False,
        })

        snaps_antiguos = []
        proceso_snap = _comando(["snap", "list", "--all"], timeout=30)
        if proceso_snap.returncode == 0:
            for linea in proceso_snap.stdout.splitlines()[1:]:
                partes = linea.split()
                if len(partes) < 6:
                    continue
                if "disabled" not in linea.lower():
                    continue
                nombre, _version, revision = partes[0], partes[1], partes[2]
                archivo = f"/var/lib/snapd/snaps/{nombre}_{revision}.snap"
                snaps_antiguos.append((nombre, revision, _tamano_ruta(archivo)))
        elementos.append({
            "id": "snaps",
            "nombre": "Revisiones antiguas de Snap",
            "descripcion": f"{len(snaps_antiguos)} revisión(es) desactivada(s) que se pueden eliminar.",
            "tamano": sum(item[2] for item in snaps_antiguos),
            "sudo": True,
            "extra": snaps_antiguos,
        })

        viejas = _versiones_viejas()
        elementos.append({
            "id": "kernels",
            "nombre": "Versiones viejas del sistema que ya no se usan",
            "descripcion": viejas["texto"],
            "tamano": viejas["tamano"],
            "sudo": True,
            "marcado": False,
            "extra": viejas["paquetes"],
        })

        return elementos

    def analizar(self):
        if self._analizando:
            return
        self._analizando = True
        self.btn_analizar.config(state=tk.DISABLED)
        self.btn_limpiar.config(state=tk.DISABLED)
        self.lbl_estado.config(text="Analizando espacio recuperable...")

        def trabajador():
            try:
                resumen = self._uso_discos()
                elementos = self._recoger_elementos()
            except Exception as error:
                self.root.after(0, lambda e=str(error): self._error_analisis(e))
                return
            self.root.after(0, lambda r=resumen, el=elementos: self._mostrar_analisis(r, el))

        threading.Thread(target=trabajador, daemon=True).start()

    def _error_analisis(self, error):
        self._analizando = False
        self.btn_analizar.config(state=tk.NORMAL)
        self.btn_limpiar.config(state=tk.NORMAL)
        messagebox.showerror("Error", f"No se pudo analizar el disco:\n{error}", parent=self.root)

    def _mostrar_analisis(self, resumen, elementos):
        if not self.root.winfo_exists():
            return
        self._analizando = False
        self.items = elementos
        self.lbl_resumen.config(text=resumen)
        for hijo in self.frame_items.winfo_children():
            hijo.destroy()
        self.vars = {}
        recuperable = 0
        for elemento in elementos:
            recuperable += elemento["tamano"]
            activo = elemento["tamano"] > 0 or bool(elemento.get("extra"))
            var = tk.BooleanVar(value=bool(elemento.get("marcado", True)) and activo)
            self.vars[elemento["id"]] = var
            texto = (
                f"{elemento['nombre']}  —  {_formato_tamano(elemento['tamano'])}\n"
                f"{elemento['descripcion']}"
            )
            casilla = tk.Checkbutton(
                self.frame_items,
                text=texto,
                variable=var,
                justify=tk.LEFT,
                anchor="w",
                wraplength=640,
            )
            if not activo:
                casilla.config(state=tk.DISABLED)
                var.set(False)
            casilla.pack(fill=tk.X, pady=4, anchor="w")
        self.lbl_estado.config(text=f"Espacio potencialmente recuperable: {_formato_tamano(recuperable)}")
        self.btn_analizar.config(state=tk.NORMAL)
        self.btn_limpiar.config(state=tk.NORMAL)
        _aplicar_tema(self.root)

    def limpiar(self):
        seleccionados = [item for item in self.items if self.vars.get(item["id"]) and self.vars[item["id"]].get()]
        if not seleccionados:
            messagebox.showinfo("Limpieza", "No hay categorías seleccionadas.", parent=self.root)
            return
        total = sum(item["tamano"] for item in seleccionados)
        nombres = "\n".join(f"- {item['nombre']}" for item in seleccionados)
        if not messagebox.askyesno(
            "Confirmar limpieza",
            f"Se van a limpiar:\n{nombres}\n\nEstimado: {_formato_tamano(total)}\n\n¿Continuar?",
            parent=self.root,
        ):
            return

        necesita_sudo = any(item["sudo"] for item in seleccionados)
        contrasena = obtener_contrasena() if necesita_sudo else None
        self.btn_analizar.config(state=tk.DISABLED)
        self.btn_limpiar.config(state=tk.DISABLED)
        self.lbl_estado.config(text="Limpiando...")

        def trabajador():
            mensajes = []
            home = os.path.expanduser("~")
            for item in seleccionados:
                try:
                    if item["id"] == "apt_cache":
                        r = _comando_sudo(["apt-get", "clean"], contrasena)
                        ok = r.returncode == 0
                        mensajes.append("Caché APT: " + ("OK" if ok else r.stderr.strip() or "error"))
                        if ok:
                            registrar_comando("Caché APT", ["apt-get", "clean"], sudo=True, tipo="args")
                    elif item["id"] == "autoremove":
                        r = _comando_sudo(["apt-get", "autoremove", "-y"], contrasena)
                        ok = r.returncode == 0
                        mensajes.append("Autoremove: " + ("OK" if ok else r.stderr.strip() or "error"))
                        if ok:
                            registrar_comando("Autoremove APT", ["apt-get", "autoremove", "-y"], sudo=True, tipo="args")
                    elif item["id"] == "journal":
                        r = _comando_sudo(["journalctl", "--vacuum-time=7d"], contrasena)
                        ok = r.returncode == 0
                        mensajes.append("Journal: " + ("OK" if ok else r.stderr.strip() or "error"))
                        if ok:
                            registrar_comando("Vaciar journal (7d)", ["journalctl", "--vacuum-time=7d"], sudo=True, tipo="args")
                    elif item["id"] == "thumbnails":
                        ruta_miniaturas = os.path.join(home, ".cache", "thumbnails")
                        shutil.rmtree(ruta_miniaturas, ignore_errors=True)
                        os.makedirs(ruta_miniaturas, exist_ok=True)
                        mensajes.append("Miniaturas: OK")
                        registrar_comando("Miniaturas", f"rm -rf {ruta_miniaturas}", sudo=False, tipo="plain")
                    elif item["id"] == "pip":
                        ruta_pip = os.path.join(home, ".cache", "pip")
                        shutil.rmtree(ruta_pip, ignore_errors=True)
                        mensajes.append("Caché de pip: OK")
                        registrar_comando("Caché de pip", f"rm -rf {ruta_pip}", sudo=False, tipo="plain")
                    elif item["id"] == "trash":
                        _comando(["gio", "trash", "--empty"], timeout=30)
                        mensajes.append("Papelera: OK")
                        registrar_comando("Vaciar papelera", "gio trash --empty", sudo=False, tipo="plain")
                    elif item["id"] == "snaps":
                        errores = []
                        for nombre, revision, _tam in item.get("extra") or []:
                            r = _comando_sudo(["snap", "remove", nombre, f"--revision={revision}"], contrasena)
                            if r.returncode != 0:
                                errores.append(f"{nombre} r{revision}")
                            else:
                                registrar_comando(
                                    f"Snap antiguo {nombre} r{revision}",
                                    ["snap", "remove", nombre, f"--revision={revision}"],
                                    sudo=True,
                                    tipo="args",
                                )
                        mensajes.append("Snaps: " + ("OK" if not errores else "falló " + ", ".join(errores)))
                    elif item["id"] == "kernels":
                        mensajes.append(_quitar_kernels_viejos(item.get("extra") or [], contrasena))
                except Exception as error:
                    mensajes.append(f"{item['nombre']}: {error}")
            self.root.after(0, lambda m=mensajes: self._fin_limpieza(m))

        threading.Thread(target=trabajador, daemon=True).start()

    def _fin_limpieza(self, mensajes):
        if not self.root.winfo_exists():
            return
        registrar("Limpieza de disco", " | ".join(mensajes), True)
        messagebox.showinfo("Limpieza", "\n".join(mensajes), parent=self.root)
        self.analizar()


class SaludDiscos:
    """Muestra el estado SMART de los discos del equipo."""

    def __init__(self, root):
        self.root = root
        self.root.title("Salud De Discos (SMART)")
        _centrar_ventana(self.root, 780, 560)
        self.discos = []

        tk.Label(
            self.root,
            text="Selecciona un disco para ver el informe SMART.",
            font=("Arial", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 4))

        self.lbl_salud = tk.Label(self.root, text="Analizando discos...", font=("Arial", 12))
        self.lbl_salud.pack(anchor="w", padx=12, pady=(0, 8))

        self.tree = ttk.Treeview(
            self.root,
            columns=("disco", "tamano", "modelo", "salud", "temp"),
            show="headings",
            height=6,
        )
        self.tree.heading("disco", text="Disco")
        self.tree.heading("tamano", text="Tamaño")
        self.tree.heading("modelo", text="Modelo")
        self.tree.heading("salud", text="Salud")
        self.tree.heading("temp", text="Temp.")
        self.tree.column("disco", width=110)
        self.tree.column("tamano", width=90)
        self.tree.column("modelo", width=260)
        self.tree.column("salud", width=90)
        self.tree.column("temp", width=80)
        self.tree.pack(fill=tk.X, padx=12)
        self.tree.bind("<<TreeviewSelect>>", self._mostrar_detalle)
        self.tree.tag_configure("ok", foreground="green")
        self.tree.tag_configure("fail", foreground="red")
        self.tree.tag_configure("warn", foreground="#b36b00")

        self.detalle = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=16)
        self.detalle.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        marco = tk.Frame(self.root)
        marco.pack(pady=(0, 10))
        btn = tk.Button(marco, text="Volver a analizar", command=self.analizar)
        btn.pack()
        ToolTip(btn, "Vuelve a consultar smartctl en todos los discos")

        _aplicar_tema(self.root)
        self.analizar()

    def _listar_discos(self):
        proceso = _comando(["lsblk", "-dn", "-b", "-J", "-o", "NAME,SIZE,MODEL,TRAN,TYPE"])
        discos = []
        if proceso.returncode == 0 and proceso.stdout.strip():
            try:
                datos = json.loads(proceso.stdout)
                for dispositivo in datos.get("blockdevices", []):
                    if dispositivo.get("type") != "disk":
                        continue
                    discos.append({
                        "name": dispositivo.get("name", ""),
                        "size": int(dispositivo.get("size") or 0),
                        "model": (dispositivo.get("model") or "Desconocido").strip(),
                        "tran": dispositivo.get("tran") or "",
                    })
            except (json.JSONDecodeError, TypeError, ValueError):
                discos = []
        if discos:
            return discos
        proceso = _comando(["lsblk", "-dn", "-b", "-o", "NAME,SIZE,TYPE"])
        for linea in proceso.stdout.splitlines():
            partes = linea.split()
            if len(partes) >= 3 and partes[-1] == "disk":
                discos.append({
                    "name": partes[0],
                    "size": int(partes[1]) if partes[1].isdigit() else 0,
                    "model": "Desconocido",
                    "tran": "",
                })
        return discos

    def _informe_smart(self, nombre, contrasena):
        dispositivo = f"/dev/{nombre}"
        if shutil.which("smartctl") is None:
            return {
                "salud": "N/D",
                "temp": "N/D",
                "texto": "smartctl no está instalado. Instala smartmontools.",
            }
        proceso = _comando_sudo(["smartctl", "-H", "-A", "-i", dispositivo], contrasena, timeout=40)
        texto = (proceso.stdout or "") + (proceso.stderr or "")
        salud = "N/D"
        if re.search(r"SMART Health Status:\s*OK", texto, re.I) or re.search(
            r"self-assessment test result:\s*PASSED", texto, re.I
        ):
            salud = "PASSED"
        elif re.search(r"FAILED", texto, re.I) or re.search(r"SMART Health Status:\s*(?!OK)", texto, re.I):
            if "Permission denied" not in texto and "unable to" not in texto.lower():
                salud = "FAILED"
        temp = "N/D"
        coincidencia = re.search(r"Temperature:\s+(\d+)\s+Celsius", texto, re.I)
        if not coincidencia:
            coincidencia = re.search(r"Temperature_Celsius.*?(\d+)(?:\s+\(|$)", texto)
        if coincidencia:
            temp = f"{coincidencia.group(1)} °C"
        if proceso.returncode is not None and proceso.returncode & 8:
            salud = "FAILED"
        if proceso.returncode not in (0, 4) and "Permission denied" in texto:
            texto = "No se pudo leer SMART. Comprueba que smartmontools está instalado y que hay permisos sudo.\n\n" + texto
        return {"salud": salud, "temp": temp, "texto": texto.strip() or "Sin datos SMART."}

    def analizar(self):
        self.lbl_salud.config(text="Analizando discos...", fg="black")
        self.tree.delete(*self.tree.get_children())
        self.detalle.delete("1.0", tk.END)
        contrasena = obtener_contrasena()

        def trabajador():
            try:
                discos = self._listar_discos()
                informes = []
                for disco in discos:
                    info = self._informe_smart(disco["name"], contrasena)
                    informes.append({**disco, **info})
            except Exception as error:
                self.root.after(0, lambda e=str(error): messagebox.showerror("Error", e, parent=self.root))
                return
            self.root.after(0, lambda inf=informes: self._mostrar(inf))

        threading.Thread(target=trabajador, daemon=True).start()

    def _mostrar(self, informes):
        if not self.root.winfo_exists():
            return
        self.discos = informes
        self.tree.delete(*self.tree.get_children())
        peores = [d["salud"] for d in informes]
        if not informes:
            self.lbl_salud.config(text="No se encontraron discos.", fg="black")
            return
        if "FAILED" in peores:
            self.lbl_salud.config(text="Atención: hay discos con SMART en fallo.", fg="red")
        elif all(s == "PASSED" for s in peores):
            self.lbl_salud.config(text="Todos los discos superan el autoinforme SMART.", fg="green")
        else:
            self.lbl_salud.config(text="Hay discos sin datos SMART completos.", fg="#b36b00")
        for disco in informes:
            etiqueta = "ok" if disco["salud"] == "PASSED" else "fail" if disco["salud"] == "FAILED" else "warn"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    disco["name"],
                    _formato_tamano(disco["size"]),
                    disco["model"],
                    disco["salud"],
                    disco["temp"],
                ),
                tags=(etiqueta,),
            )
        if self.tree.get_children():
            primero = self.tree.get_children()[0]
            self.tree.selection_set(primero)
            self.tree.focus(primero)
            self._mostrar_detalle()

    def _mostrar_detalle(self, _event=None):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        nombre = self.tree.item(seleccion[0])["values"][0]
        disco = next((d for d in self.discos if d["name"] == nombre), None)
        self.detalle.delete("1.0", tk.END)
        if disco:
            cabecera = f"Disco /dev/{disco['name']}  |  {disco['model']}  |  {disco.get('tran') or 'bus desconocido'}\n"
            cabecera += f"Salud: {disco['salud']}   Temperatura: {disco['temp']}\n"
            cabecera += "-" * 72 + "\n"
            self.detalle.insert(tk.END, cabecera + disco.get("texto", ""))


class ServiciosSystemd:
    """Lista servicios systemd y permite iniciarlos, detenerlos o habilitarlos."""

    def __init__(self, root):
        self.root = root
        self.root.title("Servicios Systemd")
        _centrar_ventana(self.root, 1120, 580)
        self.root.minsize(1120, 580)
        self.servicios = []

        marco_buscar = tk.Frame(self.root)
        marco_buscar.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(12, 4))
        tk.Label(marco_buscar, text="Buscar:").pack(side=tk.LEFT)
        self.busqueda = tk.StringVar()
        entrada = tk.Entry(marco_buscar, textvariable=self.busqueda)
        entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        entrada.bind("<KeyRelease>", lambda _e: self._filtrar())
        self.solo_activos = tk.BooleanVar(value=False)
        tk.Checkbutton(
            marco_buscar,
            text="Solo en ejecución",
            variable=self.solo_activos,
            command=self._filtrar,
        ).pack(side=tk.LEFT)

        self.lbl_estado = tk.Label(self.root, text="Cargando servicios...", anchor="w")
        self.lbl_estado.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8))

        cuerpo = tk.Frame(self.root)
        cuerpo.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=6)

        self.tree = ttk.Treeview(
            cuerpo,
            columns=("servicio", "estado", "subestado", "habilitado", "descripcion"),
            show="headings",
            height=14,
        )
        self.tree.heading("servicio", text="Servicio")
        self.tree.heading("estado", text="Estado")
        self.tree.heading("subestado", text="Subestado")
        self.tree.heading("habilitado", text="Al arranque")
        self.tree.heading("descripcion", text="Descripción")
        self.tree.column("servicio", width=220)
        self.tree.column("estado", width=90)
        self.tree.column("subestado", width=100)
        self.tree.column("habilitado", width=110)
        self.tree.column("descripcion", width=280)
        self.tree.tag_configure("active", foreground="green")
        self.tree.tag_configure("failed", foreground="red")
        self.tree.tag_configure("inactive", foreground="gray")

        marco_botones = tk.Frame(cuerpo)
        marco_botones.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        acciones = [
            ("Iniciar", "start", "Inicia el servicio seleccionado"),
            ("Detener", "stop", "Detiene el servicio seleccionado"),
            ("Reiniciar", "restart", "Reinicia el servicio seleccionado"),
            ("Habilitar", "enable", "El servicio arrancará con el sistema"),
            ("Deshabilitar", "disable", "El servicio no arrancará con el sistema"),
            ("Actualizar lista", "reload", "Vuelve a leer los servicios"),
        ]
        for texto, accion, tip in acciones:
            boton = tk.Button(
                marco_botones,
                text=texto,
                width=16,
                command=lambda a=accion: self._accion(a),
            )
            boton.pack(pady=4, fill=tk.X)
            ToolTip(boton, tip)

        scroll = ttk.Scrollbar(cuerpo, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        _aplicar_tema(self.root)
        self.cargar()

    def cargar(self):
        self.lbl_estado.config(text="Cargando servicios...")

        def trabajador():
            try:
                servicios = self._listar()
            except Exception as error:
                self.root.after(0, lambda e=str(error): messagebox.showerror("Error", e, parent=self.root))
                return
            self.root.after(0, lambda s=servicios: self._mostrar(s))

        threading.Thread(target=trabajador, daemon=True).start()

    def _listar(self):
        habilitados = {}
        archivos = _comando(["systemctl", "list-unit-files", "--type=service", "--no-pager", "--plain", "--no-legend"])
        for linea in archivos.stdout.splitlines():
            partes = linea.split()
            if len(partes) >= 2:
                habilitados[partes[0]] = partes[1]

        unidades = _comando(["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain", "--no-legend"])
        servicios = []
        for linea in unidades.stdout.splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("●"):
                continue
            partes = linea.split(None, 4)
            if len(partes) < 4:
                continue
            unidad, _load, activo, sub = partes[0], partes[1], partes[2], partes[3]
            descripcion = partes[4] if len(partes) > 4 else ""
            if _load == "not-found":
                continue
            servicios.append({
                "unidad": unidad,
                "estado": activo,
                "subestado": sub,
                "habilitado": habilitados.get(unidad, "n/d"),
                "descripcion": descripcion,
            })
        servicios.sort(key=lambda s: (0 if s["estado"] == "active" else 1, s["unidad"]))
        return servicios

    def _mostrar(self, servicios):
        if not self.root.winfo_exists():
            return
        self.servicios = servicios
        self.lbl_estado.config(text=f"{len(servicios)} servicios encontrados")
        self._filtrar()

    def _filtrar(self):
        consulta = self.busqueda.get().strip().lower()
        solo = self.solo_activos.get()
        self.tree.delete(*self.tree.get_children())
        for servicio in self.servicios:
            if solo and servicio["estado"] != "active":
                continue
            blob = f"{servicio['unidad']} {servicio['descripcion']} {servicio['estado']}".lower()
            if consulta and consulta not in blob:
                continue
            if servicio["estado"] == "failed":
                tag = "failed"
            elif servicio["estado"] == "active":
                tag = "active"
            else:
                tag = "inactive"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    servicio["unidad"],
                    servicio["estado"],
                    servicio["subestado"],
                    servicio["habilitado"],
                    servicio["descripcion"],
                ),
                tags=(tag,),
            )

    def _servicio_seleccionado(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Servicios", "Selecciona un servicio de la lista.", parent=self.root)
            return None
        return self.tree.item(seleccion[0])["values"][0]

    def _accion(self, accion):
        if accion == "reload":
            self.cargar()
            return
        unidad = self._servicio_seleccionado()
        if not unidad:
            return
        if accion in ("stop", "disable", "restart") and not messagebox.askyesno(
            "¿Seguro?",
            f"¿Seguro que quieres ejecutar «{accion}» sobre {unidad}?",
            parent=self.root,
        ):
            registrar(f"Servicio {accion}", f"{unidad} cancelado", False)
            return
        contrasena = obtener_contrasena()
        self.lbl_estado.config(text=f"Ejecutando {accion} en {unidad}...")

        def trabajador():
            resultado = _comando_sudo(["systemctl", accion, unidad], contrasena, timeout=60)
            self.root.after(0, lambda u=unidad, a=accion, r=resultado: self._fin_accion(u, a, r))

        threading.Thread(target=trabajador, daemon=True).start()

    def _fin_accion(self, unidad, accion, resultado):
        if not self.root.winfo_exists():
            return
        if resultado.returncode != 0:
            error = (resultado.stderr or resultado.stdout or "Error desconocido").strip()
            registrar(f"Servicio {accion}", unidad, False)
            messagebox.showerror("Servicios", f"No se pudo completar {accion} en {unidad}:\n{error}", parent=self.root)
        else:
            registrar(f"Servicio {accion}", unidad, True)
            self.lbl_estado.config(text=f"{accion} completado en {unidad}")
        self.cargar()


def _leer_sys(ruta):
    try:
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            return archivo.read().strip()
    except OSError:
        return ""


def _impresoras_usb():
    """Detecta impresoras USB por la clase de interfaz 0x07."""
    halladas = []
    vistos = set()
    base = "/sys/bus/usb/devices"
    try:
        entradas = os.listdir(base)
    except OSError:
        entradas = []
    for entrada in entradas:
        ruta = os.path.join(base, entrada)
        if _leer_sys(os.path.join(ruta, "bInterfaceClass")).lower() != "07":
            continue
        padre = os.path.join(base, entrada.split(":")[0]) if ":" in entrada else ruta
        vid = _leer_sys(os.path.join(padre, "idVendor"))
        pid = _leer_sys(os.path.join(padre, "idProduct"))
        clave = (vid, pid, _leer_sys(os.path.join(padre, "serial")))
        if clave in vistos:
            continue
        vistos.add(clave)
        producto = _leer_sys(os.path.join(padre, "product")) or "Impresora USB"
        fabricante = _leer_sys(os.path.join(padre, "manufacturer"))
        nombre = f"{fabricante} {producto}".strip()
        detalle = f"{vid}:{pid}" if vid and pid else entrada
        halladas.append(
            {
                "nombre": nombre,
                "tipo": "USB",
                "detalle": f"USB {detalle}",
                "estado": "Conectada",
                "cola": "",
            }
        )
    for nodo in ("/dev/usb/lp0", "/dev/usb/lp1", "/dev/usb/lp2"):
        if os.path.exists(nodo) and not any(nodo in item["detalle"] for item in halladas):
            halladas.append(
                {
                    "nombre": os.path.basename(nodo),
                    "tipo": "USB",
                    "detalle": nodo,
                    "estado": "Dispositivo",
                    "cola": "",
                }
            )
    return halladas


def _impresoras_cups():
    """Impresoras ya dadas de alta en CUPS."""
    halladas = []
    predeterminada = ""
    destino = _comando(["lpstat", "-d"], timeout=10)
    if destino.returncode == 0:
        for linea in destino.stdout.splitlines():
            if ":" in linea:
                predeterminada = linea.split(":", 1)[1].strip()
    dispositivos = {}
    listado_v = _comando(["lpstat", "-v"], timeout=15)
    if listado_v.returncode == 0:
        for linea in listado_v.stdout.splitlines():
            if ":" not in linea:
                continue
            izquierda, uri = linea.split(":", 1)
            nombre = izquierda.replace("device for", "").strip()
            dispositivos[nombre] = uri.strip()
    listado_p = _comando(["lpstat", "-p"], timeout=15)
    if listado_p.returncode == 0:
        for linea in listado_p.stdout.splitlines():
            if not linea.startswith("printer "):
                continue
            partes = linea.split()
            if len(partes) < 2:
                continue
            nombre = partes[1]
            estado = "Instalada"
            if "idle" in linea:
                estado = "En espera"
            elif "printing" in linea:
                estado = "Imprimiendo"
            if "disabled" in linea:
                estado = "Deshabilitada"
            if nombre == predeterminada:
                estado = f"{estado} (predeterminada)"
            halladas.append(
                {
                    "nombre": nombre,
                    "tipo": "CUPS",
                    "detalle": dispositivos.get(nombre, ""),
                    "estado": estado,
                    "cola": nombre,
                }
            )
    return halladas


def _impresoras_lpinfo():
    """Backends que anuncia CUPS (USB, IPP, socket, Bonjour…)."""
    halladas = []
    resultado = _comando(["lpinfo", "-v"], timeout=40)
    if resultado.returncode != 0:
        return halladas
    for linea in resultado.stdout.splitlines():
        linea = linea.strip()
        if not linea or " " not in linea:
            continue
        _esquema, uri = linea.split(" ", 1)
        uri = uri.strip()
        if uri.startswith(("file:", "hal:", "beh:")):
            continue
        if "localhost" in uri or "127.0.0.1" in uri:
            continue
        tipo = "USB" if ("usb" in uri.lower() or uri.startswith("hp:/usb")) else "Red"
        nombre = uri.split("://", 1)[-1].split("?")[0]
        nombre = nombre.replace("%20", " ").rstrip("/")
        halladas.append(
            {
                "nombre": nombre or uri,
                "tipo": tipo,
                "detalle": uri,
                "estado": "Detectada",
                "cola": "",
            }
        )
    return halladas


def _impresoras_avahi():
    """Impresoras anunciadas por mDNS/Bonjour en la red local."""
    halladas = []
    servicios = ("_ipp._tcp", "_ipps._tcp", "_printer._tcp", "_pdl-datastream._tcp")
    vistos = set()
    for servicio in servicios:
        resultado = _comando(["avahi-browse", "-prt", servicio], timeout=20)
        if resultado.returncode != 0:
            continue
        for linea in resultado.stdout.splitlines():
            if not linea.startswith("="):
                continue
            partes = linea.split(";")
            if len(partes) < 9:
                continue
            nombre, host, direccion, puerto = partes[3], partes[6], partes[7], partes[8]
            clave = (nombre, direccion, puerto)
            if clave in vistos:
                continue
            vistos.add(clave)
            halladas.append(
                {
                    "nombre": nombre.replace("\\032", " "),
                    "tipo": "Red",
                    "detalle": f"{host} ({direccion}:{puerto})",
                    "estado": "Anunciada",
                    "cola": "",
                }
            )
    return halladas


class Impresoras:
    """Busca impresoras USB, de red y las ya instaladas en CUPS."""

    def __init__(self, root):
        self.root = root
        self.root.title("Impresoras")
        _centrar_ventana(self.root, 820, 520)
        self.filas = []

        tk.Label(
            self.root,
            text="Impresoras USB, de red local e instaladas en CUPS",
            font=("Arial", 13, "bold"),
        ).pack(pady=(12, 4))
        self.lbl_estado = tk.Label(self.root, text="Pulsa Buscar para explorar USB y la red local.")
        self.lbl_estado.pack(pady=(0, 6))

        marco = tk.Frame(self.root)
        marco.pack(fill=tk.X, padx=12, pady=(0, 8))
        botones = (
            ("Buscar todas", self.buscar_todas, "Explora USB, red local (mDNS/CUPS) e impresoras instaladas"),
            ("Solo USB", self.buscar_usb, "Busca impresoras enchufadas por USB"),
            ("Solo red", self.buscar_red, "Busca impresoras anunciadas en la red local"),
            ("Instaladas", self.buscar_cups, "Lista las colas ya configuradas en CUPS"),
            ("Página de prueba", self.pagina_prueba, "Imprime una página de prueba en la cola CUPS seleccionada"),
            ("Configuración", self.abrir_configuracion, "Abre la configuración de impresoras del sistema"),
        )
        for texto, comando, tip in botones:
            boton = tk.Button(marco, text=texto, command=comando)
            boton.pack(side=tk.LEFT, padx=4)
            ToolTip(boton, tip)

        marco_lista = tk.Frame(self.root)
        marco_lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.tree = ttk.Treeview(
            marco_lista,
            columns=("nombre", "tipo", "detalle", "estado"),
            show="headings",
            height=14,
        )
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("detalle", text="Dispositivo / URI")
        self.tree.heading("estado", text="Estado")
        self.tree.column("nombre", width=220)
        self.tree.column("tipo", width=70)
        self.tree.column("detalle", width=360)
        self.tree.column("estado", width=140)
        self.tree.tag_configure("USB", foreground="#1a5276")
        self.tree.tag_configure("Red", foreground="#196f3d")
        self.tree.tag_configure("CUPS", foreground="#6c3483")
        scroll = ttk.Scrollbar(marco_lista, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        _aplicar_tema(self.root)
        self.buscar_todas()

    def _mostrar(self, filas, mensaje):
        if not self.root.winfo_exists():
            return
        self.filas = filas
        self.tree.delete(*self.tree.get_children())
        vistos = set()
        for fila in filas:
            clave = (fila["nombre"], fila["tipo"], fila["detalle"])
            if clave in vistos:
                continue
            vistos.add(clave)
            self.tree.insert(
                "",
                tk.END,
                values=(fila["nombre"], fila["tipo"], fila["detalle"], fila["estado"]),
                tags=(fila["tipo"],),
            )
        self.lbl_estado.config(text=mensaje)

    def _buscar(self, mensaje, trabajador):
        self.lbl_estado.config(text=mensaje)

        def al_terminar(resultado):
            filas, texto = resultado
            self._mostrar(filas, texto)

        en_hilo(self.root, trabajador, al_terminar=al_terminar)

    def buscar_todas(self):
        def trabajador():
            filas = _impresoras_cups() + _impresoras_usb() + _impresoras_avahi() + _impresoras_lpinfo()
            return filas, f"{len(filas)} resultado(s). USB, red e instaladas."

        self._buscar("Buscando impresoras USB y de red…", trabajador)

    def buscar_usb(self):
        def trabajador():
            filas = _impresoras_usb() + [f for f in _impresoras_lpinfo() if f["tipo"] == "USB"]
            return filas, f"{len(filas)} impresora(s) USB."

        self._buscar("Buscando impresoras USB…", trabajador)

    def buscar_red(self):
        def trabajador():
            filas = _impresoras_avahi() + [f for f in _impresoras_lpinfo() if f["tipo"] == "Red"]
            return filas, f"{len(filas)} impresora(s) de red."

        self._buscar("Buscando impresoras en la red local…", trabajador)

    def buscar_cups(self):
        def trabajador():
            filas = _impresoras_cups()
            if not filas and _comando(["lpstat", "-r"], timeout=8).returncode != 0:
                return filas, "CUPS no está disponible. Instala el paquete cups-client."
            return filas, f"{len(filas)} cola(s) instalada(s) en CUPS."

        self._buscar("Leyendo impresoras de CUPS…", trabajador)

    def _seleccion(self):
        item = self.tree.focus()
        if not item:
            return None
        valores = self.tree.item(item, "values")
        if not valores:
            return None
        for fila in self.filas:
            if (fila["nombre"], fila["tipo"], fila["detalle"], fila["estado"]) == tuple(valores):
                return fila
        return None

    def pagina_prueba(self):
        fila = self._seleccion()
        if not fila or not fila.get("cola"):
            messagebox.showinfo(
                "Impresoras",
                "Selecciona una impresora instalada en CUPS (tipo CUPS) para la página de prueba.",
                parent=self.root,
            )
            return
        cola = fila["cola"]
        if not messagebox.askyesno(
            "¿Seguro?",
            f"¿Enviar una página de prueba a «{cola}»?",
            parent=self.root,
        ):
            return

        def trabajador():
            prueba = "/usr/share/cups/data/testprint"
            if os.path.exists(prueba):
                return _comando(["lp", "-d", cola, prueba], timeout=30)
            entorno = os.environ.copy()
            entorno["LC_ALL"] = "C"
            try:
                return subprocess.run(
                    ["lp", "-d", cola],
                    input="Pagina de prueba Manten1d0\n",
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=entorno,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as error:
                return subprocess.CompletedProcess(["lp", "-d", cola], 1, "", str(error))

        def terminar(resultado):
            if resultado.returncode == 0:
                registrar("Página de prueba", cola, True)
                registrar_comando("Página de prueba", ["lp", "-d", cola], sudo=False, tipo="args")
                messagebox.showinfo("Impresoras", f"Trabajo enviado a {cola}.", parent=self.root)
            else:
                detalle = (resultado.stderr or resultado.stdout or "No se pudo imprimir").strip()
                registrar("Página de prueba", f"{cola}: {detalle}", False)
                messagebox.showerror("Impresoras", detalle, parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=terminar)

    def abrir_configuracion(self):
        for comando in (
            ["gnome-control-center", "printers"],
            ["system-config-printer"],
            ["xdg-open", "http://localhost:631"],
        ):
            try:
                subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
        messagebox.showinfo(
            "Impresoras",
            "No se encontró el configurador. Abre http://localhost:631 en el navegador.",
            parent=self.root,
        )


_TIPOS_DISCO = {
    "ext2", "ext3", "ext4", "btrfs", "xfs", "ntfs", "ntfs3", "vfat", "exfat",
    "f2fs", "bcachefs", "zfs", "jfs", "reiserfs", "udf",
}
_LIMITE_CARPETAS = 300


def _es_disco_real(origen, tipo, montaje):
    if tipo not in _TIPOS_DISCO:
        return False
    if origen.startswith("/dev/loop"):
        return False
    if montaje.startswith(("/snap/", "/run/", "/sys/", "/proc/", "/dev/")):
        return False
    return True


def parsear_df(salida):
    """Interpreta la salida de df --output=source,fstype,size,used,avail,pcent,target."""
    discos = []
    for linea in (salida or "").splitlines()[1:]:
        partes = linea.split(None, 6)
        if len(partes) < 7:
            continue
        origen, tipo, total, usado, libre, porcentaje, montaje = partes
        montaje = os.path.normpath(montaje.strip())
        if not _es_disco_real(origen, tipo, montaje):
            continue
        try:
            total_n = int(total)
            usado_n = int(usado)
            libre_n = int(libre)
        except ValueError:
            continue
        try:
            pct = int(str(porcentaje).strip().rstrip("%"))
        except ValueError:
            pct = int((usado_n / total_n) * 100) if total_n else 0
        discos.append({
            "origen": origen,
            "tipo": tipo,
            "total": total_n,
            "usado": usado_n,
            "libre": libre_n,
            "porcentaje": pct,
            "montaje": montaje,
        })
    discos.sort(key=lambda disco: (disco["porcentaje"], disco["usado"]), reverse=True)
    return discos


def listar_uso_discos():
    proceso = _comando([
        "df", "-B1",
        "--output=source,fstype,size,used,avail,pcent,target",
        "--local",
    ])
    discos = parsear_df(proceso.stdout) if proceso.returncode == 0 else []
    if discos:
        return discos
    respaldo = []
    vistos = set()
    for punto in ("/", os.path.expanduser("~")):
        punto = os.path.normpath(punto)
        if punto in vistos:
            continue
        vistos.add(punto)
        try:
            uso = shutil.disk_usage(punto)
        except OSError:
            continue
        pct = int((uso.used / uso.total) * 100) if uso.total else 0
        respaldo.append({
            "origen": punto,
            "tipo": "",
            "total": uso.total,
            "usado": uso.used,
            "libre": uso.free,
            "porcentaje": pct,
            "montaje": punto,
        })
    return respaldo


def parsear_du(salida, ruta):
    """Tamaños de las carpetas hijas. La línea de la propia ruta es el total."""
    ruta_norm = os.path.normpath(ruta)
    carpetas = []
    total = 0
    for linea in (salida or "").splitlines():
        if "\t" not in linea:
            continue
        tam_txt, path = linea.split("\t", 1)
        path = os.path.normpath(path.strip())
        try:
            tam = int(tam_txt)
        except ValueError:
            continue
        if path == ruta_norm:
            total = tam
            continue
        carpetas.append({
            "ruta": path,
            "nombre": os.path.basename(path) or path,
            "tamano": tam,
            "es_dir": True,
        })
    return carpetas, total


def parsear_archivos(salida):
    archivos = []
    for linea in (salida or "").splitlines():
        if "\t" not in linea:
            continue
        tam_txt, path = linea.split("\t", 1)
        path = os.path.normpath(path.strip())
        try:
            tam = int(tam_txt)
        except ValueError:
            continue
        archivos.append({
            "ruta": path,
            "nombre": os.path.basename(path) or path,
            "tamano": tam,
            "es_dir": False,
        })
    return archivos


def _texto_porcentaje(valor):
    if valor >= 10:
        return f"{valor:.0f} %"
    if valor >= 0.1:
        return f"{valor:.1f} %"
    if valor > 0:
        return "<0,1 %"
    return "0 %"


def _barra_uso(tamano, maximo, ancho=16):
    if tamano <= 0 or maximo <= 0:
        return ""
    bloques = max(1, round(ancho * tamano / maximo))
    return "█" * min(ancho, bloques)


class EspacioDiscos:
    """Muestra el espacio de cada disco y las carpetas que más ocupan."""

    def __init__(self, root):
        self.root = root
        self.root.title("Espacio Ocupado En Disco")
        _centrar_ventana(self.root, 920, 680)
        self.discos = []
        self.entradas = []
        self.montaje = ""
        self.ruta = ""
        self._token = 0
        self._proceso = None
        self._lock = threading.Lock()
        self._silencio = False
        self._contrasena = None
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)

        tk.Label(
            self.root,
            text="Espacio de cada disco. Elige uno para ver las carpetas que más ocupan.",
            font=("Arial", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        marco_discos = tk.Frame(self.root)
        marco_discos.pack(fill=tk.X, padx=12)

        self.tree_discos = ttk.Treeview(
            marco_discos,
            columns=("disco", "montaje", "tipo", "ocupado", "total", "libre", "uso"),
            show="headings",
            height=5,
        )
        self.tree_discos.heading("disco", text="Disco")
        self.tree_discos.heading("montaje", text="Montaje")
        self.tree_discos.heading("tipo", text="Tipo")
        self.tree_discos.heading("ocupado", text="Ocupado")
        self.tree_discos.heading("total", text="Total")
        self.tree_discos.heading("libre", text="Libre")
        self.tree_discos.heading("uso", text="Uso")
        self.tree_discos.column("disco", width=150)
        self.tree_discos.column("montaje", width=220)
        self.tree_discos.column("tipo", width=70)
        self.tree_discos.column("ocupado", width=100, anchor="e")
        self.tree_discos.column("total", width=100, anchor="e")
        self.tree_discos.column("libre", width=100, anchor="e")
        self.tree_discos.column("uso", width=60, anchor="e")
        self.tree_discos.tag_configure("ok", foreground="#1e8449")
        self.tree_discos.tag_configure("warn", foreground="#b36b00")
        self.tree_discos.tag_configure("fail", foreground="#c0392b")
        scroll_discos = ttk.Scrollbar(marco_discos, orient="vertical", command=self.tree_discos.yview)
        self.tree_discos.configure(yscrollcommand=scroll_discos.set)
        self.tree_discos.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scroll_discos.pack(side=tk.LEFT, fill=tk.Y)
        self.tree_discos.bind("<<TreeviewSelect>>", self._al_elegir_disco)

        self.lbl_ruta = tk.Label(self.root, text="", anchor="w", justify=tk.LEFT, font=("Arial", 10))
        self.lbl_ruta.pack(fill=tk.X, padx=12, pady=(8, 2))

        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=12, pady=(0, 6))

        marco_carpetas = tk.Frame(self.root)
        marco_carpetas.pack(fill=tk.BOTH, expand=True, padx=12)

        self.tree_carpetas = ttk.Treeview(
            marco_carpetas,
            columns=("nombre", "tipo", "tamano", "porcentaje", "barra"),
            show="headings",
        )
        self.tree_carpetas.heading("nombre", text="Nombre")
        self.tree_carpetas.heading("tipo", text="Tipo")
        self.tree_carpetas.heading("tamano", text="Tamaño")
        self.tree_carpetas.heading("porcentaje", text="% del disco")
        self.tree_carpetas.heading("barra", text="")
        self.tree_carpetas.column("nombre", width=280)
        self.tree_carpetas.column("tipo", width=100)
        self.tree_carpetas.column("tamano", width=110, anchor="e")
        self.tree_carpetas.column("porcentaje", width=90, anchor="e")
        self.tree_carpetas.column("barra", width=180)
        self.tree_carpetas.tag_configure("otro", foreground="#2471a3")
        scroll_carpetas = ttk.Scrollbar(marco_carpetas, orient="vertical", command=self.tree_carpetas.yview)
        self.tree_carpetas.configure(yscrollcommand=scroll_carpetas.set)
        self.tree_carpetas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_carpetas.pack(side=tk.LEFT, fill=tk.Y)
        self.tree_carpetas.bind("<Double-1>", self._entrar_click)
        self.tree_carpetas.bind("<Return>", self._entrar)

        marco_botones = tk.Frame(self.root)
        marco_botones.pack(fill=tk.X, padx=12, pady=8)

        self.btn_subir = tk.Button(marco_botones, text="Subir", command=self._subir, state=tk.DISABLED)
        self.btn_subir.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.btn_subir, "Vuelve a la carpeta anterior, sin salir de este disco")

        self.btn_actualizar = tk.Button(marco_botones, text="Actualizar", command=self._actualizar)
        self.btn_actualizar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_actualizar, "Vuelve a medir el disco seleccionado y la carpeta actual")

        self.con_sudo = tk.BooleanVar(value=False)
        self.chk_sudo = tk.Checkbutton(
            marco_botones,
            text="Incluir carpetas protegidas",
            variable=self.con_sudo,
            command=self._cambiar_sudo,
        )
        self.chk_sudo.pack(side=tk.LEFT, padx=6)
        ToolTip(
            self.chk_sudo,
            "Mide también carpetas que tu usuario no puede leer, como /root o partes de /var",
        )

        self.btn_abrir = tk.Button(marco_botones, text="Abrir carpeta", command=self._abrir)
        self.btn_abrir.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_abrir, "Abre la carpeta seleccionada en el administrador de archivos")

        self.lbl_estado = tk.Label(self.root, text="Leyendo discos...", anchor="w")
        self.lbl_estado.pack(fill=tk.X, padx=12, pady=(0, 10))

        _aplicar_tema(self.root)
        self._cargar_discos()

    def _disco_actual(self):
        return next((disco for disco in self.discos if disco["montaje"] == self.montaje), None)

    def _dentro_del_disco(self, ruta):
        montaje = os.path.normpath(self.montaje or "/")
        ruta = os.path.normpath(ruta)
        if montaje == "/":
            return ruta.startswith("/")
        return ruta == montaje or ruta.startswith(montaje + os.sep)

    def _cargar_discos(self):
        self.lbl_estado.config(text="Leyendo discos...")

        def pintar(discos):
            if not self.root.winfo_exists():
                return
            self.discos = discos
            self.tree_discos.delete(*self.tree_discos.get_children())
            if not discos:
                self.lbl_estado.config(text="No se encontraron discos locales.")
                return
            for disco in discos:
                if disco["porcentaje"] >= 90:
                    etiqueta = "fail"
                elif disco["porcentaje"] >= 80:
                    etiqueta = "warn"
                else:
                    etiqueta = "ok"
                self.tree_discos.insert(
                    "",
                    tk.END,
                    iid=disco["montaje"],
                    tags=(etiqueta,),
                    values=(
                        disco["origen"],
                        disco["montaje"],
                        disco["tipo"] or "N/D",
                        _formato_tamano(disco["usado"]),
                        _formato_tamano(disco["total"]),
                        _formato_tamano(disco["libre"]),
                        f"{disco['porcentaje']} %",
                    ),
                )
            self.tree_discos.selection_set(discos[0]["montaje"])
            self.tree_discos.focus(discos[0]["montaje"])

        en_hilo(self.root, listar_uso_discos, al_terminar=pintar)

    def _al_elegir_disco(self, _event=None):
        if self._silencio:
            return
        seleccion = self.tree_discos.selection()
        if not seleccion:
            return
        montaje = seleccion[0]
        if montaje == self.montaje and self.ruta == montaje:
            return
        self.montaje = montaje
        self._analizar(montaje)

    def _cambiar_sudo(self):
        if self.con_sudo.get():
            self._contrasena = obtener_contrasena()
        else:
            self._contrasena = None
        if self.ruta:
            self._analizar(self.ruta)

    def _actualizar(self):
        def pintar(discos):
            if not self.root.winfo_exists():
                return
            self.discos = discos or self.discos
            seleccionado = self.montaje
            self._silencio = True
            try:
                self._rellenar_discos(seleccionado)
            finally:
                self._silencio = False
            if self.ruta:
                self._analizar(self.ruta)

        en_hilo(self.root, listar_uso_discos, al_terminar=pintar)

    def _rellenar_discos(self, seleccionado):
        self.tree_discos.delete(*self.tree_discos.get_children())
        for disco in self.discos:
            if disco["porcentaje"] >= 90:
                etiqueta = "fail"
            elif disco["porcentaje"] >= 80:
                etiqueta = "warn"
            else:
                etiqueta = "ok"
            self.tree_discos.insert(
                "",
                tk.END,
                iid=disco["montaje"],
                tags=(etiqueta,),
                values=(
                    disco["origen"],
                    disco["montaje"],
                    disco["tipo"] or "N/D",
                    _formato_tamano(disco["usado"]),
                    _formato_tamano(disco["total"]),
                    _formato_tamano(disco["libre"]),
                    f"{disco['porcentaje']} %",
                ),
            )
        if seleccionado in self.tree_discos.get_children():
            self.tree_discos.selection_set(seleccionado)
            self.tree_discos.focus(seleccionado)
        elif self.discos:
            self.tree_discos.selection_set(self.discos[0]["montaje"])
            self.montaje = self.discos[0]["montaje"]
            self.ruta = self.montaje

    def _subir(self):
        if not self.ruta or not self.montaje:
            return
        padre = os.path.dirname(os.path.normpath(self.ruta))
        if not padre or not self._dentro_del_disco(padre) or padre == os.path.normpath(self.ruta):
            return
        self._analizar(padre)

    def _entrar_click(self, event):
        if self.tree_carpetas.identify("region", event.x, event.y) != "cell":
            return
        self._entrar()

    def _entrar(self, _event=None):
        seleccion = self.tree_carpetas.selection()
        if not seleccion:
            return
        ruta = seleccion[0]
        entrada = next((item for item in self.entradas if item["ruta"] == ruta), None)
        if not entrada:
            return
        if entrada.get("otro_disco"):
            if ruta in self.tree_discos.get_children():
                self.tree_discos.selection_set(ruta)
                self.tree_discos.focus(ruta)
                self.tree_discos.see(ruta)
                self.montaje = ruta
                self._analizar(ruta)
            return
        if entrada["es_dir"]:
            self._analizar(ruta)

    def _abrir(self):
        seleccion = self.tree_carpetas.selection()
        ruta = seleccion[0] if seleccion else self.ruta
        if not ruta:
            return
        if os.path.isfile(ruta):
            ruta = os.path.dirname(ruta)
        for comando in (["nautilus", ruta], ["xdg-open", ruta]):
            try:
                subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
        messagebox.showinfo("Espacio", "No se pudo abrir el administrador de archivos.", parent=self.root)

    def _cerrar(self):
        self._token += 1
        self._cancelar_proceso()
        self.root.destroy()

    def _matar_proceso(self, proceso):
        if proceso is None or proceso.poll() is not None:
            return
        try:
            os.killpg(proceso.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proceso.kill()
            except OSError:
                return
        try:
            proceso.wait(timeout=2)
        except Exception:
            pass

    def _cancelar_proceso(self):
        with self._lock:
            proceso = self._proceso
            self._proceso = None
        self._matar_proceso(proceso)

    def _lanzar(self, args, contrasena, timeout, token):
        entorno = os.environ.copy()
        entorno["LC_ALL"] = "C"
        if contrasena:
            comando = ["sudo", "-S", "-p", "", *args]
            entrada = f"{contrasena}\n"
        else:
            comando = list(args)
            entrada = None
        try:
            proceso = subprocess.Popen(
                comando,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=entorno,
                start_new_session=True,
            )
        except FileNotFoundError as error:
            return subprocess.CompletedProcess(comando, 1, "", str(error))
        descartado = None
        anterior = None
        with self._lock:
            if token != self._token:
                descartado = proceso
            else:
                anterior = self._proceso
                self._proceso = proceso
        if descartado is not None:
            self._matar_proceso(descartado)
            return subprocess.CompletedProcess(comando, 1, "", "")
        if anterior is not None and anterior is not proceso:
            self._matar_proceso(anterior)
        try:
            salida, error = proceso.communicate(entrada, timeout=timeout)
        except subprocess.TimeoutExpired:
            self._matar_proceso(proceso)
            return subprocess.CompletedProcess(comando, 1, "", "Tiempo de espera agotado.")
        return subprocess.CompletedProcess(comando, proceso.returncode, salida or "", error or "")

    def _medir(self, ruta, contrasena, token):
        du = self._lanzar(
            ["du", "-x", "-B1", "--max-depth=1", "--", ruta],
            contrasena,
            600,
            token,
        )
        if token != self._token:
            return [], 0
        if du.returncode not in (0, 1) and not (du.stdout or "").strip():
            detalle = (du.stderr or du.stdout or "No se pudo medir la carpeta.").strip()
            raise RuntimeError(detalle)
        archivos = self._lanzar(
            ["find", ruta, "-maxdepth", "1", "-type", "f", "-printf", "%s\\t%p\\n"],
            contrasena,
            120,
            token,
        )
        if token != self._token:
            return [], 0
        carpetas, _total = parsear_du(du.stdout, ruta)
        entradas = carpetas + parsear_archivos(archivos.stdout if archivos.returncode in (0, 1) else "")
        avisos = (du.stderr or "").lower().count("permission denied")
        avisos += (archivos.stderr or "").lower().count("permission denied")
        return entradas, avisos

    def _analizar(self, ruta):
        ruta = os.path.normpath(ruta)
        if not self._dentro_del_disco(ruta):
            return
        self._token += 1
        token = self._token
        self._cancelar_proceso()
        self.ruta = ruta
        self.entradas = []
        self.tree_carpetas.delete(*self.tree_carpetas.get_children())
        disco = self._disco_actual()
        texto_disco = ""
        if disco:
            texto_disco = (
                f"{disco['montaje']} · {_formato_tamano(disco['usado'])} de "
                f"{_formato_tamano(disco['total'])} ({disco['porcentaje']} % ocupado, "
                f"{_formato_tamano(disco['libre'])} libres)\n"
            )
        self.lbl_ruta.config(text=texto_disco + ruta)
        self.lbl_estado.config(text="Calculando carpetas… en discos grandes puede tardar.")
        self.progreso.start(12)
        self.btn_subir.config(state=tk.DISABLED)
        contrasena = self._contrasena if self.con_sudo.get() else None

        def trabajador():
            return self._medir(ruta, contrasena, token)

        def pintar(resultado):
            if token != self._token or not self.root.winfo_exists():
                return
            entradas, avisos = resultado
            self._mostrar_carpetas(entradas, avisos)

        def fallo(error):
            if token != self._token or not self.root.winfo_exists():
                return
            self.progreso.stop()
            en_raiz = os.path.normpath(self.ruta) == os.path.normpath(self.montaje or self.ruta)
            self.btn_subir.config(state=tk.DISABLED if en_raiz else tk.NORMAL)
            self.lbl_estado.config(text="No se pudo calcular el espacio.")
            messagebox.showerror("Espacio", str(error), parent=self.root)

        threading.Thread(
            target=lambda: self._hilo_analisis(trabajador, pintar, fallo),
            daemon=True,
        ).start()

    def _hilo_analisis(self, trabajador, pintar, fallo):
        try:
            resultado = trabajador()
        except Exception as error:
            if self.root.winfo_exists():
                self.root.after(0, lambda e=error: fallo(e))
            return
        if self.root.winfo_exists():
            self.root.after(0, lambda r=resultado: pintar(r))

    def _mostrar_carpetas(self, entradas, avisos):
        self.progreso.stop()
        montajes = {disco["montaje"] for disco in self.discos}
        unicos = {}
        for entrada in entradas:
            previa = unicos.get(entrada["ruta"])
            if previa is None or entrada["tamano"] > previa["tamano"]:
                unicos[entrada["ruta"]] = entrada
        entradas = list(unicos.values())
        for entrada in entradas:
            entrada["otro_disco"] = entrada["es_dir"] and entrada["ruta"] in montajes and entrada["ruta"] != self.montaje
        entradas.sort(key=lambda item: item["tamano"], reverse=True)
        self.entradas = entradas
        self.tree_carpetas.delete(*self.tree_carpetas.get_children())
        disco = self._disco_actual()
        usado = disco["usado"] if disco else 0
        maximo = entradas[0]["tamano"] if entradas else 0
        visibles = entradas[:_LIMITE_CARPETAS]
        for entrada in visibles:
            if entrada["otro_disco"]:
                tipo = "Otro disco"
                etiqueta = ("otro",)
            elif entrada["es_dir"]:
                tipo = "Carpeta"
                etiqueta = ()
            else:
                tipo = "Archivo"
                etiqueta = ()
            porcentaje = (entrada["tamano"] / usado) * 100 if usado else 0
            self.tree_carpetas.insert(
                "",
                tk.END,
                iid=entrada["ruta"],
                tags=etiqueta,
                values=(
                    entrada["nombre"],
                    tipo,
                    _formato_tamano(entrada["tamano"]),
                    _texto_porcentaje(porcentaje),
                    _barra_uso(entrada["tamano"], maximo),
                ),
            )
        en_raiz = os.path.normpath(self.ruta) == os.path.normpath(self.montaje or self.ruta)
        self.btn_subir.config(state=tk.DISABLED if en_raiz else tk.NORMAL)
        if not entradas:
            self.lbl_estado.config(text="Esta carpeta no tiene elementos medibles.")
            return
        mayor = entradas[0]
        porcentaje = (mayor["tamano"] / usado) * 100 if usado else 0
        texto = (
            f"{len(entradas)} elementos · lo que más ocupa es {mayor['nombre']} "
            f"({_formato_tamano(mayor['tamano'])}, {_texto_porcentaje(porcentaje)} del disco)"
        )
        if len(entradas) > _LIMITE_CARPETAS:
            texto += f". Mostrando las {_LIMITE_CARPETAS} mayores"
        if avisos:
            texto += ". Hay carpetas sin permiso: marca «Incluir carpetas protegidas»"
        self.lbl_estado.config(text=texto + ".")


def _ufw_instalado():
    return os.path.isfile("/usr/sbin/ufw") or shutil.which("ufw") is not None


def _ufw_activado():
    """Lee ENABLED de ufw.conf. No hace falta ser administrador para saber si está encendido."""
    try:
        with open("/etc/ufw/ufw.conf", encoding="utf-8", errors="replace") as archivo:
            for linea in archivo:
                linea = linea.strip()
                if linea.startswith("ENABLED="):
                    return linea.split("=", 1)[1].strip().strip('"').lower() == "yes"
    except OSError:
        return None
    return None


def _cidr_lan():
    """Detecta la red local de la interfaz con ruta por defecto (p. ej. 192.168.1.0/24)."""
    ruta = _comando(["ip", "-4", "route", "show", "default"], timeout=10)
    if ruta.returncode != 0 or not ruta.stdout.strip():
        return None
    coincidencia = re.search(r"\bdev\s+(\S+)", ruta.stdout)
    if not coincidencia:
        return None
    interfaz = coincidencia.group(1)
    addrs = _comando(["ip", "-4", "-o", "addr", "show", "dev", interfaz], timeout=10)
    if addrs.returncode != 0:
        return None
    match_ip = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", addrs.stdout)
    if not match_ip:
        return None
    ip_txt, prefijo_txt = match_ip.group(1), match_ip.group(2)
    try:
        prefijo = int(prefijo_txt)
    except ValueError:
        return None
    if prefijo < 0 or prefijo > 32:
        return None
    partes = [int(p) for p in ip_txt.split(".")]
    ip_int = (partes[0] << 24) | (partes[1] << 16) | (partes[2] << 8) | partes[3]
    mascara = (0xFFFFFFFF << (32 - prefijo)) & 0xFFFFFFFF if prefijo else 0
    red = ip_int & mascara
    return (
        f"{(red >> 24) & 255}.{(red >> 16) & 255}.{(red >> 8) & 255}.{red & 255}/{prefijo}"
    )


def _ufw_status_texto():
    """Devuelve la salida de `ufw status` o None si falla."""
    resultado = sudo_run(["ufw", "status"], "Consultar estado del cortafuegos", timeout=40)
    if resultado is None or resultado.returncode != 0:
        return None
    return resultado.stdout or ""


def _reglas_desde_status(texto, cidr=None):
    """Interpreta si SSH, Samba y la regla de LAN aparecen en ufw status."""
    bajo = (texto or "").lower()
    ssh = (
        "openssh" in bajo
        or "22/tcp" in bajo
        or re.search(r"(^|\s)22(\s|/)", bajo) is not None
    )
    samba = (
        "samba" in bajo
        or "137" in bajo
        or "138" in bajo
        or "139" in bajo
        or "445" in bajo
    )
    lan = False
    if cidr:
        lan = cidr.lower() in bajo and "allow" in bajo
    return {"ssh": ssh, "samba": samba, "lan": lan}


class Cortafuegos:
    """Activa o desactiva ufw y gestiona reglas frecuentes (SSH, Samba, red local)."""

    def __init__(self, root):
        self.root = root
        self.root.title("Cortafuegos")
        self.root.minsize(560, 480)
        _centrar_ventana(self.root, 640, 520)
        self._ocupado = False
        self._cidr = _cidr_lan()
        self._reglas = {"ssh": False, "samba": False, "lan": False}

        tk.Label(self.root, text="Cortafuegos", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        self.lbl_estado = tk.Label(self.root, text="Comprobando…", font=("Arial", 12, "bold"))
        self.lbl_estado.pack(pady=(0, 6))
        tk.Label(
            self.root,
            text=(
                "Activado: solo entran las conexiones que tú permites. "
                "El equipo sigue pudiendo salir a Internet.\n"
                "Desactivado: otros equipos de la red pueden intentar conectar con este.\n\n"
                "Las reglas de abajo solo sirven si el cortafuegos está activado."
            ),
            wraplength=600,
            justify=tk.LEFT,
        ).pack(padx=16, pady=(0, 8))

        marco = tk.Frame(self.root)
        marco.pack(pady=(0, 8))
        self.btn_cambiar = tk.Button(marco, text="Activar", width=16, command=self._activar)
        self.btn_cambiar.pack(side=tk.LEFT, padx=6)
        self.tip_cambiar = ToolTip(
            self.btn_cambiar,
            "Enciende o apaga el cortafuegos del equipo. Pide confirmación y la contraseña de administrador",
        )
        self.btn_refrescar = tk.Button(marco, text="Actualizar estado", width=16, command=self._refrescar)
        self.btn_refrescar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_refrescar, "Vuelve a leer si el cortafuegos está activo y qué reglas hay")
        boton_cerrar = tk.Button(marco, text="Cerrar", width=12, command=self.root.destroy)
        boton_cerrar.pack(side=tk.LEFT, padx=6)
        ToolTip(boton_cerrar, "Cierra esta ventana")

        self.marco_reglas = tk.LabelFrame(self.root, text="Reglas frecuentes", padx=10, pady=8)
        self.marco_reglas.pack(fill=tk.X, padx=16, pady=(4, 10))

        self.lbl_aviso_reglas = tk.Label(
            self.marco_reglas,
            text="",
            anchor="w",
            justify=tk.LEFT,
            wraplength=580,
        )
        self.lbl_aviso_reglas.pack(fill=tk.X, pady=(0, 6))

        self._filas = {}
        self._filas["ssh"] = self._crear_fila_regla(
            self.marco_reglas,
            "Permitir SSH",
            "Deja entrar por SSH (acceso remoto seguro, puerto 22).",
            self._toggle_ssh,
        )
        self._filas["samba"] = self._crear_fila_regla(
            self.marco_reglas,
            "Permitir Samba",
            "Deja ver carpetas compartidas desde otros equipos de la red.",
            self._toggle_samba,
        )
        texto_lan = (
            f"Solo esta red ({self._cidr})"
            if self._cidr
            else "Solo esta red (no detectada)"
        )
        self._filas["lan"] = self._crear_fila_regla(
            self.marco_reglas,
            texto_lan,
            "Permite conexiones desde tu red de casa, no desde Internet.",
            self._toggle_lan,
        )

        _aplicar_tema(self.root)
        self._mostrar_estado()
        if _ufw_instalado():
            self._refrescar()

    def _crear_fila_regla(self, padre, titulo, tooltip, comando):
        fila = tk.Frame(padre)
        fila.pack(fill=tk.X, pady=4)
        lbl_titulo = tk.Label(fila, text=titulo, width=28, anchor="w")
        lbl_titulo.pack(side=tk.LEFT)
        ToolTip(lbl_titulo, tooltip)
        lbl_estado = tk.Label(fila, text="…", width=12, anchor="w")
        lbl_estado.pack(side=tk.LEFT, padx=6)
        boton = tk.Button(fila, text="Permitir", width=10, command=comando)
        boton.pack(side=tk.RIGHT)
        ToolTip(boton, tooltip)
        return {"titulo": lbl_titulo, "estado": lbl_estado, "boton": boton}

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        try:
            self.btn_cambiar.config(state=estado)
            self.btn_refrescar.config(state=estado)
        except tk.TclError:
            pass
        for fila in self._filas.values():
            try:
                fila["boton"].config(state=estado)
            except tk.TclError:
                pass
        if mensaje:
            self.lbl_estado.config(text=mensaje, fg="#2471a3")

    def _mostrar_estado(self):
        if not _ufw_instalado():
            self.lbl_estado.config(text="No está instalado.", fg="#c0392b")
            self.btn_cambiar.config(text="Instalar", command=self._instalar, state=tk.NORMAL)
            self.tip_cambiar.text = "Instala el cortafuegos ufw"
            self.lbl_aviso_reglas.config(
                text="Instala el cortafuegos para poder usar las reglas frecuentes."
            )
            for fila in self._filas.values():
                fila["boton"].config(state=tk.DISABLED)
                fila["estado"].config(text="—")
            return
        activo = _ufw_activado()
        if activo is None:
            self.lbl_estado.config(text="No se pudo leer el estado.", fg="#c0392b")
            self.btn_cambiar.config(state=tk.DISABLED)
            return
        if activo:
            self.lbl_estado.config(
                text="Activado. Solo entran las conexiones que tú permites.",
                fg="#1e8449",
            )
            self.btn_cambiar.config(text="Desactivar", command=self._desactivar, state=tk.NORMAL)
            self.tip_cambiar.text = "Apaga el cortafuegos. Las conexiones de otros equipos dejarán de filtrarse"
            self.lbl_aviso_reglas.config(
                text="Puedes permitir o quitar reglas frecuentes sin editar ufw a mano."
            )
        else:
            self.lbl_estado.config(
                text="Desactivado. Las conexiones de fuera pueden entrar.",
                fg="#c0392b",
            )
            self.btn_cambiar.config(text="Activar", command=self._activar, state=tk.NORMAL)
            self.tip_cambiar.text = "Enciende el cortafuegos. Solo entrarán las conexiones permitidas"
            self.lbl_aviso_reglas.config(
                text="El cortafuegos está apagado: las reglas no filtran hasta que lo actives."
            )
        self._pintar_reglas()

    def _pintar_reglas(self):
        for clave, etiqueta_si in (
            ("ssh", "Permitido"),
            ("samba", "Permitido"),
            ("lan", "Permitido"),
        ):
            fila = self._filas[clave]
            activo_regla = self._reglas.get(clave, False)
            fila["estado"].config(text=etiqueta_si if activo_regla else "No")
            fila["boton"].config(text="Quitar" if activo_regla else "Permitir")
        if not self._cidr:
            self._filas["lan"]["boton"].config(state=tk.DISABLED)
            self._filas["lan"]["estado"].config(text="N/D")
            self._filas["lan"]["titulo"].config(text="Solo esta red (no detectada)")
        else:
            self._filas["lan"]["titulo"].config(text=f"Solo esta red ({self._cidr})")
            if not self._ocupado and _ufw_instalado():
                self._filas["lan"]["boton"].config(state=tk.NORMAL)

    def _refrescar(self):
        if self._ocupado:
            return
        if not _ufw_instalado():
            self._mostrar_estado()
            return
        self._set_ocupado(True, "Leyendo reglas…")

        def trabajo():
            self._cidr = _cidr_lan()
            texto = _ufw_status_texto()
            return texto

        def al_terminar(texto):
            if not self.root.winfo_exists():
                return
            self._ocupado = False
            if texto is None:
                self._reglas = {"ssh": False, "samba": False, "lan": False}
                self.lbl_aviso_reglas.config(
                    text="No se pudieron leer las reglas (hace falta contraseña de administrador)."
                )
            else:
                self._reglas = _reglas_desde_status(texto, self._cidr)
            self._mostrar_estado()
            self.btn_refrescar.config(state=tk.NORMAL)
            if _ufw_instalado():
                for fila in self._filas.values():
                    fila["boton"].config(state=tk.NORMAL)
                self._pintar_reglas()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._ocupado = False
            self.btn_refrescar.config(state=tk.NORMAL)
            messagebox.showerror("Cortafuegos", str(error), parent=self.root)
            self._mostrar_estado()

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)

    def _activar(self):
        if not confirmar(
            "Se va a activar el cortafuegos.\n\n"
            "Solo entrarán las conexiones que ya estén permitidas. "
            "La salida a Internet no se corta.\n\n"
            "¿Quieres activarlo?",
            self.root,
            "Activar El Cortafuegos",
        ):
            return
        self._aplicar(["ufw", "--force", "enable"], "Activar el cortafuegos")

    def _desactivar(self):
        if not confirmar(
            "Se va a desactivar el cortafuegos.\n\n"
            "Otros equipos podrán intentar conectar con este sin ese filtro.\n\n"
            "¿Quieres desactivarlo?",
            self.root,
            "Desactivar El Cortafuegos",
        ):
            return
        self._aplicar(["ufw", "disable"], "Desactivar el cortafuegos")

    def _instalar(self):
        if not confirmar(
            "Se va a instalar el cortafuegos (ufw). Después podrás activarlo.\n\n¿Quieres instalarlo?",
            self.root,
            "Instalar El Cortafuegos",
        ):
            return
        self._aplicar(["apt-get", "install", "-y", "ufw"], "Instalar el cortafuegos")

    def _toggle_ssh(self):
        if self._ocupado:
            return
        if self._reglas.get("ssh"):
            if not confirmar(
                "Se va a quitar el permiso de SSH.\n\n"
                "Ya no se podrá entrar a este equipo por SSH desde fuera "
                "(salvo otras reglas que tengas).\n\n¿Quieres quitarlo?",
                self.root,
                "Quitar SSH",
            ):
                return

            def trabajo():
                r = sudo_run(["ufw", "delete", "allow", "OpenSSH"], "Quitar permiso SSH", timeout=40)
                if r is not None and r.returncode != 0:
                    r = sudo_run(["ufw", "delete", "allow", "22/tcp"], "Quitar permiso SSH 22/tcp", timeout=40)
                return r

            self._aplicar_fn(trabajo, "Quitando permiso SSH…")
            return
        if not confirmar(
            "Se va a permitir SSH (acceso remoto seguro, puerto 22).\n\n"
            "Otros equipos podrán intentar conectar por SSH a este.\n\n¿Quieres permitirlo?",
            self.root,
            "Permitir SSH",
        ):
            return

        def trabajo():
            r = sudo_run(["ufw", "allow", "OpenSSH"], "Permitir SSH", timeout=40)
            if r is not None and r.returncode != 0:
                r = sudo_run(["ufw", "allow", "22/tcp"], "Permitir SSH 22/tcp", timeout=40)
            return r

        self._aplicar_fn(trabajo, "Permitiendo SSH…")

    def _toggle_samba(self):
        if self._ocupado:
            return
        if self._reglas.get("samba"):
            if not confirmar(
                "Se va a quitar el permiso de Samba.\n\n"
                "Otros equipos dejarán de ver las carpetas compartidas "
                "si el cortafuegos está activado.\n\n¿Quieres quitarlo?",
                self.root,
                "Quitar Samba",
            ):
                return
            self._aplicar(["ufw", "delete", "allow", "samba"], "Quitar permiso Samba")
            return
        if not confirmar(
            "Se va a permitir Samba (carpetas compartidas en la red).\n\n"
            "Otros equipos de la red podrán ver las carpetas que compartas.\n\n¿Quieres permitirlo?",
            self.root,
            "Permitir Samba",
        ):
            return
        self._aplicar(["ufw", "allow", "samba"], "Permitir Samba")

    def _toggle_lan(self):
        if self._ocupado:
            return
        cidr = self._cidr or _cidr_lan()
        if not cidr:
            messagebox.showinfo(
                "Cortafuegos",
                "No se pudo detectar la red local de este equipo.",
                parent=self.root,
            )
            return
        self._cidr = cidr
        if self._reglas.get("lan"):
            if not confirmar(
                f"Se va a quitar el permiso para la red local {cidr}.\n\n"
                "Los equipos de casa dejarán de poder conectar por esa regla.\n\n¿Quieres quitarlo?",
                self.root,
                "Quitar Solo Esta Red",
            ):
                return
            self._aplicar(["ufw", "delete", "allow", "from", cidr], f"Quitar acceso desde {cidr}")
            return
        if not confirmar(
            f"Se va a permitir conexiones desde tu red local ({cidr}).\n\n"
            "Los equipos de casa podrán conectar; no se abre el acceso a todo Internet.\n\n"
            "¿Quieres permitirlo?",
            self.root,
            "Permitir Solo Esta Red",
        ):
            return
        self._aplicar(["ufw", "allow", "from", cidr], f"Permitir acceso desde {cidr}")

    def _aplicar(self, args, descripcion):
        self._aplicar_fn(lambda: sudo_run(args, descripcion, timeout=180), "Espera un momento…")

    def _aplicar_fn(self, trabajo, mensaje):
        if self._ocupado:
            return
        self._set_ocupado(True, mensaje)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._ocupado = False
            if resultado is not None and getattr(resultado, "returncode", 0) != 0:
                texto = (resultado.stderr or resultado.stdout or "No se pudo completar la acción.").strip()
                messagebox.showerror("Cortafuegos", texto, parent=self.root)
            self._refrescar()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._ocupado = False
            messagebox.showerror("Cortafuegos", str(error), parent=self.root)
            self._refrescar()

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)


def _binario_disponible(nombre):
    return shutil.which(nombre) is not None


def _parsear_tamano_humano(texto):
    """Convierte tamaños tipo '129,5 MB', '129.5 MB' o '1.2 GiB' a bytes."""
    if texto is None:
        return 0
    limpio = (
        str(texto)
        .strip()
        .replace("\xa0", " ")
        .replace("\u202f", " ")
        .replace(",", ".")
    )
    if not limpio or limpio in ("-", "n/a", "N/A"):
        return 0
    try:
        return int(float(limpio))
    except ValueError:
        pass
    coincidencia = re.match(
        r"^\s*([0-9]+(?:\.[0-9]+)?)[^\dA-Za-z]*([A-Za-z]+)\s*$",
        limpio,
    )
    if not coincidencia:
        return 0
    cantidad = float(coincidencia.group(1))
    unidad = coincidencia.group(2).upper().rstrip("S")
    factores = {
        "B": 1,
        "BYTE": 1,
        "K": 1024,
        "KB": 1024,
        "KIB": 1024,
        "M": 1024 ** 2,
        "MB": 1024 ** 2,
        "MIB": 1024 ** 2,
        "G": 1024 ** 3,
        "GB": 1024 ** 3,
        "GIB": 1024 ** 3,
        "T": 1024 ** 4,
        "TB": 1024 ** 4,
        "TIB": 1024 ** 4,
    }
    return int(cantidad * factores.get(unidad, 0))


def _tamano_snap(nombre, revision):
    archivo = f"/var/lib/snapd/snaps/{nombre}_{revision}.snap"
    return _tamano_ruta(archivo)


def _listar_snaps():
    """Lista snaps instalados con tamaño de la revisión activa."""
    if not _binario_disponible("snap"):
        return [], "no_instalado"
    proceso = _comando(["snap", "list"], timeout=60)
    if proceso.returncode != 0:
        return [], (proceso.stderr or proceso.stdout or "No se pudo listar Snap.").strip()
    apps = []
    for linea in proceso.stdout.splitlines()[1:]:
        partes = linea.split()
        if len(partes) < 3:
            continue
        nombre, version, revision = partes[0], partes[1], partes[2]
        apps.append({
            "tipo": "Snap",
            "id": nombre,
            "nombre": nombre,
            "version": version,
            "revision": revision,
            "instalacion": "system",
            "tamano": _tamano_snap(nombre, revision),
        })
    return apps, None


def _listar_flatpaks():
    """Lista aplicaciones Flatpak (user y system) con tamaño."""
    if not _binario_disponible("flatpak"):
        return [], "no_instalado"
    proceso = _comando(
        [
            "flatpak",
            "list",
            "--app",
            "--columns=application,name,version,installation,size",
        ],
        timeout=90,
    )
    if proceso.returncode != 0:
        return [], (proceso.stderr or proceso.stdout or "No se pudo listar Flatpak.").strip()
    apps = []
    for linea in proceso.stdout.splitlines():
        partes = linea.split("\t")
        if len(partes) < 5:
            continue
        app_id, nombre, version, instalacion, tamano_txt = (p.strip() for p in partes[:5])
        if not app_id:
            continue
        apps.append({
            "tipo": "Flatpak",
            "id": app_id,
            "nombre": nombre or app_id,
            "version": version or "—",
            "revision": "",
            "instalacion": (instalacion or "system").lower(),
            "tamano": _parsear_tamano_humano(tamano_txt),
        })
    return apps, None


class SnapFlatpak:
    """Lista, actualiza y desinstala aplicaciones Snap y Flatpak con el espacio que ocupan."""

    def __init__(self, root):
        self.root = root
        self.root.title("Snap Y Flatpak")
        self.root.minsize(720, 480)
        _centrar_ventana(self.root, 820, 560)
        self._ocupado = False
        self._apps = []
        self._por_iid = {}
        self.filtro = tk.StringVar(value="todos")

        tk.Label(self.root, text="Snap y Flatpak", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Estas aplicaciones van aparte de APT: no salen en la lista de paquetes .deb "
                "y suelen ocupar bastante espacio en el disco."
            ),
            wraplength=760,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 8))

        self.lbl_resumen = tk.Label(
            self.root,
            text="Cargando lista…",
            font=("Arial", 11, "bold"),
            anchor="w",
            justify=tk.LEFT,
        )
        self.lbl_resumen.pack(fill=tk.X, padx=14, pady=(0, 4))

        self.lbl_aviso = tk.Label(self.root, text="", anchor="w", justify=tk.LEFT, wraplength=760)
        self.lbl_aviso.pack(fill=tk.X, padx=14)

        marco_filtro = tk.Frame(self.root)
        marco_filtro.pack(fill=tk.X, padx=14, pady=(4, 2))
        tk.Label(marco_filtro, text="Mostrar:").pack(side=tk.LEFT, padx=(0, 8))
        for valor, texto in (("todos", "Todos"), ("snap", "Snap"), ("flatpak", "Flatpak")):
            tk.Radiobutton(
                marco_filtro,
                text=texto,
                variable=self.filtro,
                value=valor,
                command=self._aplicar_filtro,
            ).pack(side=tk.LEFT, padx=4)

        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(2, 4))

        marco_tabla = tk.Frame(self.root)
        marco_tabla.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)
        self.tree = ttk.Treeview(
            marco_tabla,
            columns=("tipo", "nombre", "version", "tamano"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("version", text="Versión")
        self.tree.heading("tamano", text="Tamaño")
        self.tree.column("tipo", width=80, anchor="w")
        self.tree.column("nombre", width=360, anchor="w")
        self.tree.column("version", width=160, anchor="w")
        self.tree.column("tamano", width=100, anchor="e")
        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)

        marco_botones = tk.Frame(self.root)
        marco_botones.pack(fill=tk.X, padx=14, pady=10)

        self.btn_refrescar = tk.Button(marco_botones, text="Actualizar lista", command=self.cargar)
        self.btn_refrescar.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_refrescar, "Vuelve a leer las aplicaciones Snap y Flatpak instaladas")

        self.btn_act_sel = tk.Button(
            marco_botones, text="Actualizar seleccionada", command=self._actualizar_seleccionada
        )
        self.btn_act_sel.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_act_sel, "Busca una versión nueva de la aplicación seleccionada")

        self.btn_act_todas = tk.Button(
            marco_botones, text="Actualizar todas", command=self._actualizar_todas
        )
        self.btn_act_todas.pack(side=tk.LEFT, padx=4)
        ToolTip(
            self.btn_act_todas,
            "Actualiza todas las aplicaciones visibles según el filtro (Snap, Flatpak o ambas)",
        )

        self.btn_desinstalar = tk.Button(marco_botones, text="Desinstalar", command=self._desinstalar)
        self.btn_desinstalar.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_desinstalar, "Quita la aplicación seleccionada del equipo")

        self.btn_instalar_fp = tk.Button(
            marco_botones, text="Instalar Flatpak", command=self._instalar_flatpak
        )
        ToolTip(self.btn_instalar_fp, "Instala Flatpak con APT para poder usar aplicaciones Flatpak")

        btn_cerrar = tk.Button(marco_botones, text="Cerrar", command=self.root.destroy)
        btn_cerrar.pack(side=tk.RIGHT, padx=4)
        ToolTip(btn_cerrar, "Cierra esta ventana")

        _aplicar_tema(self.root)
        self.cargar()

    def _apps_filtradas(self):
        filtro = self.filtro.get()
        if filtro == "snap":
            return [a for a in self._apps if a["tipo"] == "Snap"]
        if filtro == "flatpak":
            return [a for a in self._apps if a["tipo"] == "Flatpak"]
        return list(self._apps)

    def _seleccion(self):
        seleccion = self.tree.selection()
        if not seleccion:
            return None
        return self._por_iid.get(seleccion[0])

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for boton in (
            self.btn_refrescar,
            self.btn_act_sel,
            self.btn_act_todas,
            self.btn_desinstalar,
            self.btn_instalar_fp,
        ):
            try:
                boton.config(state=estado)
            except tk.TclError:
                pass
        if ocupado:
            self.progreso.start(12)
            if mensaje:
                self.lbl_aviso.config(text=mensaje)
        else:
            self.progreso.stop()

    def cargar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Leyendo aplicaciones instaladas…")
        self.lbl_resumen.config(text="Cargando lista…")

        def trabajador():
            snaps, err_snap = _listar_snaps()
            flats, err_flat = _listar_flatpaks()
            return {
                "snaps": snaps,
                "err_snap": err_snap,
                "flats": flats,
                "err_flat": err_flat,
            }

        def al_terminar(datos):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._mostrar(datos)

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror("Snap Y Flatpak", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _mostrar(self, datos):
        avisos = []
        self._apps = []
        if datos["err_snap"] == "no_instalado":
            avisos.append("Snap no está disponible en este equipo.")
        elif datos["err_snap"]:
            avisos.append(f"Snap: {datos['err_snap']}")
        else:
            self._apps.extend(datos["snaps"])

        flatpak_ok = True
        if datos["err_flat"] == "no_instalado":
            flatpak_ok = False
            avisos.append("Flatpak no está instalado. Puedes instalarlo desde aquí.")
            self.btn_instalar_fp.pack(side=tk.LEFT, padx=4, before=self.btn_desinstalar)
        elif datos["err_flat"]:
            avisos.append(f"Flatpak: {datos['err_flat']}")
            self.btn_instalar_fp.pack_forget()
        else:
            self._apps.extend(datos["flats"])
            self.btn_instalar_fp.pack_forget()

        total_snap = sum(a["tamano"] for a in self._apps if a["tipo"] == "Snap")
        total_flat = sum(a["tamano"] for a in self._apps if a["tipo"] == "Flatpak")
        n_snap = sum(1 for a in self._apps if a["tipo"] == "Snap")
        n_flat = sum(1 for a in self._apps if a["tipo"] == "Flatpak")
        partes = [
            f"Snap: {n_snap} app(s), {_formato_tamano(total_snap)}",
            (
                f"Flatpak: {n_flat} app(s), {_formato_tamano(total_flat)}"
                if flatpak_ok and not datos["err_flat"]
                else "Flatpak: no instalado" if not flatpak_ok else f"Flatpak: error al listar"
            ),
            f"Total listado: {_formato_tamano(total_snap + total_flat)}",
        ]
        self.lbl_resumen.config(text="  ·  ".join(partes))
        self.lbl_aviso.config(text="\n".join(avisos))
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._por_iid.clear()
        visibles = sorted(self._apps_filtradas(), key=lambda a: a["tamano"], reverse=True)
        for app in visibles:
            etiqueta_nombre = app["nombre"]
            if app["tipo"] == "Flatpak" and app["id"] != app["nombre"]:
                etiqueta_nombre = f"{app['nombre']} ({app['id']})"
            iid = self.tree.insert(
                "",
                tk.END,
                values=(
                    app["tipo"],
                    etiqueta_nombre,
                    app["version"],
                    _formato_tamano(app["tamano"]),
                ),
            )
            self._por_iid[iid] = app

    def _actualizar_seleccionada(self):
        if self._ocupado:
            return
        app = self._seleccion()
        if not app:
            messagebox.showinfo(
                "Snap Y Flatpak",
                "Selecciona una aplicación de la lista.",
                parent=self.root,
            )
            return
        if not confirmar(
            f"Se va a buscar una actualización de:\n\n{app['nombre']} ({app['tipo']})\n\n¿Quieres continuar?",
            self.root,
            "Actualizar Aplicación",
        ):
            return
        self._ejecutar_accion(
            lambda: self._hacer_actualizar_una(app),
            f"Actualizando {app['nombre']}…",
            "Actualizar aplicación",
        )

    def _actualizar_todas(self):
        if self._ocupado:
            return
        filtro = self.filtro.get()
        if filtro == "snap":
            que = "todas las aplicaciones Snap"
        elif filtro == "flatpak":
            que = "todas las aplicaciones Flatpak"
        else:
            que = "todas las aplicaciones Snap y Flatpak visibles"
        if not confirmar(
            f"Se van a actualizar {que}.\n\nPuede tardar varios minutos.\n\n¿Quieres continuar?",
            self.root,
            "Actualizar Todas",
        ):
            return
        self._ejecutar_accion(
            lambda: self._hacer_actualizar_todas(filtro),
            "Actualizando aplicaciones…",
            "Actualizar todas",
        )

    def _desinstalar(self):
        if self._ocupado:
            return
        app = self._seleccion()
        if not app:
            messagebox.showinfo(
                "Snap Y Flatpak",
                "Selecciona una aplicación de la lista.",
                parent=self.root,
            )
            return
        if not confirmar(
            f"Se va a desinstalar:\n\n{app['nombre']} ({app['tipo']})\n"
            f"Espacio aproximado: {_formato_tamano(app['tamano'])}\n\n"
            "¿Quieres quitarla?",
            self.root,
            "Desinstalar Aplicación",
        ):
            registrar("Desinstalar Snap/Flatpak", f"{app['tipo']}:{app['id']} cancelado", False)
            return
        self._ejecutar_accion(
            lambda: self._hacer_desinstalar(app),
            f"Desinstalando {app['nombre']}…",
            "Desinstalar Snap/Flatpak",
        )

    def _instalar_flatpak(self):
        if self._ocupado:
            return
        if not confirmar(
            "Se va a instalar Flatpak con APT.\n\n"
            "Después podrás instalar aplicaciones Flatpak desde otras fuentes.\n\n"
            "¿Quieres instalarlo?",
            self.root,
            "Instalar Flatpak",
        ):
            return

        def trabajo():
            return sudo_run(["apt-get", "install", "-y", "flatpak"], "Instalar Flatpak", timeout=600)

        self._ejecutar_accion(trabajo, "Instalando Flatpak…", "Instalar Flatpak", recargar=True)

    def _hacer_actualizar_una(self, app):
        if app["tipo"] == "Snap":
            return sudo_run(["snap", "refresh", app["id"]], f"Actualizar Snap {app['id']}", timeout=600)
        args = ["flatpak", "update", "-y", app["id"]]
        if app.get("instalacion") == "user":
            args = ["flatpak", "update", "-y", "--user", app["id"]]
            proceso = _comando(args, timeout=600)
            registrar(f"Actualizar Flatpak {app['id']}", " ".join(args), proceso.returncode == 0)
            return proceso
        return sudo_run(args, f"Actualizar Flatpak {app['id']}", timeout=600)

    def _hacer_actualizar_todas(self, filtro):
        ultimo = None
        if filtro in ("todos", "snap") and _binario_disponible("snap"):
            ultimo = sudo_run(["snap", "refresh"], "Actualizar todos los Snap", timeout=900)
            if ultimo is not None and ultimo.returncode != 0:
                return ultimo
        if filtro in ("todos", "flatpak") and _binario_disponible("flatpak"):
            # Actualiza instalaciones de sistema y de usuario.
            ultimo = sudo_run(["flatpak", "update", "-y"], "Actualizar Flatpak (system)", timeout=900)
            if ultimo is not None and ultimo.returncode != 0:
                return ultimo
            user = _comando(["flatpak", "update", "-y", "--user"], timeout=900)
            registrar("Actualizar Flatpak (user)", "flatpak update -y --user", user.returncode == 0)
            if user.returncode != 0:
                return user
            ultimo = user if ultimo is None else ultimo
        return ultimo

    def _hacer_desinstalar(self, app):
        if app["tipo"] == "Snap":
            return sudo_run(["snap", "remove", app["id"]], f"Desinstalar Snap {app['id']}", timeout=600)
        if app.get("instalacion") == "user":
            args = ["flatpak", "uninstall", "-y", "--user", app["id"]]
            proceso = _comando(args, timeout=600)
            registrar(f"Desinstalar Flatpak {app['id']}", " ".join(args), proceso.returncode == 0)
            return proceso
        return sudo_run(
            ["flatpak", "uninstall", "-y", app["id"]],
            f"Desinstalar Flatpak {app['id']}",
            timeout=600,
        )

    def _ejecutar_accion(self, trabajo, mensaje, titulo, recargar=True):
        self._set_ocupado(True, mensaje)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            if resultado is not None and getattr(resultado, "returncode", 0) != 0:
                texto = (resultado.stderr or resultado.stdout or "No se pudo completar la acción.").strip()
                messagebox.showerror(titulo, texto, parent=self.root)
            elif resultado is None:
                self.lbl_aviso.config(text="Acción cancelada.")
            else:
                self.lbl_aviso.config(text="Listo.")
            if recargar:
                self.cargar()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror(titulo, str(error), parent=self.root)
            if recargar:
                self.cargar()

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)



def _bluetoothctl(args, timeout=30):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(
            ["bluetoothctl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(["bluetoothctl", *args], 127, "", "bluetoothctl no está instalado")
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(["bluetoothctl", *args], 1, "", str(error))


def _estado_adaptador_bluetooth():
    """Devuelve (texto_estado, powered_bool_o_None, error_o_None)."""
    if not shutil.which("bluetoothctl"):
        return "Bluetooth no disponible (falta bluez / bluetoothctl).", None, "no_instalado"
    proceso = _bluetoothctl(["show"])
    if proceso.returncode != 0:
        texto = (proceso.stderr or proceso.stdout or "No se pudo leer el adaptador.").strip()
        return texto, None, texto
    powered = None
    for linea in proceso.stdout.splitlines():
        if "Powered:" in linea:
            powered = "yes" in linea.lower()
            break
    if powered is True:
        return "Adaptador encendido.", True, None
    if powered is False:
        return "Adaptador apagado.", False, None
    return "No se pudo saber si el adaptador está encendido.", None, None


def _listar_dispositivos_bluetooth():
    """Lista dispositivos emparejados con estado conectado/emparejado."""
    if not shutil.which("bluetoothctl"):
        return [], "no_instalado"
    proceso = _bluetoothctl(["devices", "Paired"])
    if proceso.returncode != 0:
        # Versiones antiguas pueden no aceptar "Paired": caer a devices.
        proceso = _bluetoothctl(["devices"])
        if proceso.returncode != 0:
            return [], (proceso.stderr or proceso.stdout or "No se pudo listar dispositivos.").strip()

    dispositivos = []
    for linea in proceso.stdout.splitlines():
        linea = linea.strip()
        if not linea.lower().startswith("device "):
            continue
        partes = linea.split(None, 2)
        if len(partes) < 2:
            continue
        mac = partes[1]
        nombre = partes[2] if len(partes) > 2 else mac
        conectado = False
        info = _bluetoothctl(["info", mac], timeout=20)
        if info.returncode == 0:
            for fila in info.stdout.splitlines():
                if "Connected:" in fila and "yes" in fila.lower():
                    conectado = True
                    break
        dispositivos.append({
            "mac": mac,
            "nombre": nombre,
            "conectado": conectado,
        })
    dispositivos.sort(key=lambda d: (not d["conectado"], d["nombre"].lower()))
    return dispositivos, None


class Bluetooth:
    """Lista dispositivos Bluetooth, olvida uno o reinicia el servicio."""

    def __init__(self, root):
        self.root = root
        self.root.title("Bluetooth")
        self.root.minsize(620, 420)
        _centrar_ventana(self.root, 700, 480)
        self._ocupado = False
        self._por_iid = {}

        tk.Label(self.root, text="Bluetooth", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Dispositivos guardados en este equipo. Si uno no conecta, "
                "olvidarlo o reiniciar Bluetooth suele bastar (como apagar y encender)."
            ),
            wraplength=660,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 6))

        self.lbl_adaptador = tk.Label(
            self.root,
            text="Comprobando adaptador…",
            font=("Arial", 11, "bold"),
            anchor="w",
        )
        self.lbl_adaptador.pack(fill=tk.X, padx=14, pady=(0, 2))

        self.lbl_aviso = tk.Label(self.root, text="", anchor="w", justify=tk.LEFT, wraplength=660)
        self.lbl_aviso.pack(fill=tk.X, padx=14)

        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(2, 4))

        marco_tabla = tk.Frame(self.root)
        marco_tabla.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)
        self.tree = ttk.Treeview(
            marco_tabla,
            columns=("nombre", "mac", "estado"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("mac", text="Dirección")
        self.tree.heading("estado", text="Estado")
        self.tree.column("nombre", width=280, anchor="w")
        self.tree.column("mac", width=180, anchor="w")
        self.tree.column("estado", width=120, anchor="w")
        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)

        marco_botones = tk.Frame(self.root)
        marco_botones.pack(fill=tk.X, padx=14, pady=10)

        self.btn_actualizar = tk.Button(marco_botones, text="Actualizar lista", command=self.cargar)
        self.btn_actualizar.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_actualizar, "Vuelve a leer el adaptador y los dispositivos emparejados")

        self.btn_olvidar = tk.Button(marco_botones, text="Olvidar seleccionado", command=self._olvidar)
        self.btn_olvidar.pack(side=tk.LEFT, padx=4)
        ToolTip(
            self.btn_olvidar,
            "Quita el vínculo con el dispositivo elegido. Después habrá que emparejarlo otra vez desde los ajustes de Ubuntu",
        )

        self.btn_reiniciar = tk.Button(
            marco_botones, text="Reiniciar Bluetooth", command=self._reiniciar
        )
        self.btn_reiniciar.pack(side=tk.LEFT, padx=4)
        ToolTip(
            self.btn_reiniciar,
            "Apaga y vuelve a arrancar el servicio Bluetooth del sistema. Útil cuando los auriculares o el ratón no responden",
        )

        btn_cerrar = tk.Button(marco_botones, text="Cerrar", command=self.root.destroy)
        btn_cerrar.pack(side=tk.RIGHT, padx=4)
        ToolTip(btn_cerrar, "Cierra esta ventana")

        _aplicar_tema(self.root)
        self.cargar()

    def _seleccion(self):
        seleccion = self.tree.selection()
        if not seleccion:
            return None
        return self._por_iid.get(seleccion[0])

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for boton in (self.btn_actualizar, self.btn_olvidar, self.btn_reiniciar):
            try:
                boton.config(state=estado)
            except tk.TclError:
                pass
        if ocupado:
            self.progreso.start(12)
            if mensaje:
                self.lbl_aviso.config(text=mensaje)
        else:
            self.progreso.stop()

    def cargar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Leyendo dispositivos Bluetooth…")

        def trabajador():
            adaptador, powered, err_ad = _estado_adaptador_bluetooth()
            dispositivos, err_list = _listar_dispositivos_bluetooth()
            return {
                "adaptador": adaptador,
                "powered": powered,
                "err_ad": err_ad,
                "dispositivos": dispositivos,
                "err_list": err_list,
            }

        def al_terminar(datos):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._mostrar(datos)

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror("Bluetooth", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _mostrar(self, datos):
        self.lbl_adaptador.config(text=datos["adaptador"])
        avisos = []
        if datos["err_ad"] == "no_instalado" or datos["err_list"] == "no_instalado":
            avisos.append(
                "No está instalado bluetoothctl (paquete bluez). "
                "En Ubuntu de escritorio suele venir de serie."
            )
            self.btn_olvidar.config(state=tk.DISABLED)
            self.btn_reiniciar.config(state=tk.DISABLED)
        elif datos["err_list"]:
            avisos.append(datos["err_list"])
        elif not datos["dispositivos"]:
            avisos.append("No hay dispositivos emparejados. Emparéjalos desde los ajustes de Ubuntu.")
        else:
            avisos.append(f"{len(datos['dispositivos'])} dispositivo(s) emparejado(s).")
        self.lbl_aviso.config(text="\n".join(avisos))

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._por_iid.clear()
        for dispositivo in datos["dispositivos"]:
            estado = "conectado" if dispositivo["conectado"] else "emparejado"
            iid = self.tree.insert(
                "",
                tk.END,
                values=(dispositivo["nombre"], dispositivo["mac"], estado),
            )
            self._por_iid[iid] = dispositivo

    def _olvidar(self):
        if self._ocupado:
            return
        dispositivo = self._seleccion()
        if not dispositivo:
            messagebox.showinfo(
                "Bluetooth",
                "Selecciona un dispositivo de la lista.",
                parent=self.root,
            )
            return
        if not confirmar(
            f"Se va a olvidar este dispositivo:\n\n"
            f"{dispositivo['nombre']}\n{dispositivo['mac']}\n\n"
            "Después habrá que emparejarlo otra vez desde los ajustes de Ubuntu.\n\n"
            "¿Quieres olvidarlo?",
            self.root,
            "Olvidar Dispositivo",
        ):
            registrar("Olvidar Bluetooth", f"{dispositivo['mac']} cancelado", False)
            return

        def trabajo():
            resultado = _bluetoothctl(["remove", dispositivo["mac"]], timeout=45)
            registrar(
                "Olvidar Bluetooth",
                f"{dispositivo['nombre']} {dispositivo['mac']}",
                resultado.returncode == 0,
            )
            return resultado

        self._ejecutar(trabajo, f"Olvidando {dispositivo['nombre']}…", "Olvidar Bluetooth")

    def _reiniciar(self):
        if self._ocupado:
            return
        if not confirmar(
            "Se va a reiniciar el servicio Bluetooth del sistema.\n\n"
            "Equivale a apagar y encender el Bluetooth. "
            "Los dispositivos conectados se desconectarán un momento.\n\n"
            "¿Quieres reiniciarlo?",
            self.root,
            "Reiniciar Bluetooth",
        ):
            return

        def trabajo():
            return sudo_run(
                ["systemctl", "restart", "bluetooth"],
                "Reiniciar Bluetooth",
                timeout=120,
            )

        self._ejecutar(trabajo, "Reiniciando Bluetooth…", "Reiniciar Bluetooth")

    def _ejecutar(self, trabajo, mensaje, titulo):
        self._set_ocupado(True, mensaje)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            if resultado is not None and getattr(resultado, "returncode", 0) != 0:
                texto = (resultado.stderr or resultado.stdout or "No se pudo completar la acción.").strip()
                messagebox.showerror(titulo, texto, parent=self.root)
            elif resultado is None:
                self.lbl_aviso.config(text="Acción cancelada.")
            else:
                self.lbl_aviso.config(text="Listo.")
            self.cargar()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror(titulo, str(error), parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)



def _listar_unidades_fallidas():
    """Lista unidades systemd en estado failed."""
    proceso = _comando(
        ["systemctl", "--failed", "--no-pager", "--plain", "--no-legend"],
        timeout=40,
    )
    if proceso.returncode not in (0, 1):
        # systemctl --failed puede devolver 0 con lista vacía
        error = (proceso.stderr or proceso.stdout or "No se pudo listar unidades fallidas.").strip()
        return [], error
    unidades = []
    for linea in proceso.stdout.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("●"):
            continue
        partes = linea.split(None, 4)
        if len(partes) < 4:
            continue
        nombre, _load, activo, sub = partes[0], partes[1], partes[2], partes[3]
        descripcion = partes[4] if len(partes) > 4 else ""
        unidades.append({
            "unidad": nombre,
            "estado": activo,
            "subestado": sub,
            "descripcion": descripcion,
        })
    unidades.sort(key=lambda u: u["unidad"].lower())
    return unidades, None


def _log_corto_unidad(unidad):
    """Últimas líneas del journal de una unidad. Prueba sin sudo y con sudo."""
    args = ["journalctl", "-u", unidad, "-n", "40", "--no-pager", "-o", "short-iso"]
    proceso = _comando(args, timeout=40)
    if proceso.returncode == 0 and (proceso.stdout or "").strip():
        return proceso.stdout.strip(), None
    # Algunos journals necesitan privilegios
    con_sudo = sudo_run(args, f"Log de {unidad}", timeout=40)
    if con_sudo is None:
        return None, "cancelado"
    if con_sudo.returncode != 0:
        texto = (con_sudo.stderr or con_sudo.stdout or proceso.stderr or "No se pudo leer el log.").strip()
        return None, texto
    return (con_sudo.stdout or "").strip() or "(Sin entradas recientes en el registro.)", None


class ServiciosFallidos:
    """Lista unidades systemd en failed y permite reiniciarlas o ver un log corto."""

    def __init__(self, root):
        self.root = root
        self.root.title("Servicios Que Fallan")
        self.root.minsize(700, 480)
        _centrar_ventana(self.root, 820, 560)
        self._ocupado = False
        self._por_iid = {}

        tk.Label(self.root, text="Servicios que fallan", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Unidades que systemd marca como fallidas. "
                "Puedes reiniciarlas o ver las últimas líneas del registro."
            ),
            wraplength=780,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 6))

        self.lbl_estado = tk.Label(self.root, text="Cargando…", font=("Arial", 11, "bold"), anchor="w")
        self.lbl_estado.pack(fill=tk.X, padx=14, pady=(0, 2))

        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(0, 4))

        marco_tabla = tk.Frame(self.root)
        marco_tabla.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)
        self.tree = ttk.Treeview(
            marco_tabla,
            columns=("unidad", "estado", "descripcion"),
            show="headings",
            selectmode="browse",
            height=8,
        )
        self.tree.heading("unidad", text="Unidad")
        self.tree.heading("estado", text="Estado")
        self.tree.heading("descripcion", text="Descripción")
        self.tree.column("unidad", width=320, anchor="w")
        self.tree.column("estado", width=100, anchor="w")
        self.tree.column("descripcion", width=320, anchor="w")
        self.tree.tag_configure("failed", foreground="#c0392b")
        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)

        marco_botones = tk.Frame(self.root)
        marco_botones.pack(fill=tk.X, padx=14, pady=6)

        self.btn_actualizar = tk.Button(marco_botones, text="Actualizar lista", command=self.cargar)
        self.btn_actualizar.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_actualizar, "Vuelve a leer las unidades en fallo")

        self.btn_reiniciar = tk.Button(
            marco_botones, text="Reiniciar seleccionada", command=self._reiniciar
        )
        self.btn_reiniciar.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_reiniciar, "Reinicia la unidad fallida seleccionada")

        self.btn_log = tk.Button(marco_botones, text="Ver log corto", command=self._ver_log)
        self.btn_log.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_log, "Muestra las últimas 40 líneas del registro de esa unidad")

        btn_cerrar = tk.Button(marco_botones, text="Cerrar", command=self.root.destroy)
        btn_cerrar.pack(side=tk.RIGHT, padx=4)
        ToolTip(btn_cerrar, "Cierra esta ventana")

        tk.Label(self.root, text="Log corto", anchor="w").pack(fill=tk.X, padx=14)
        self.log = scrolledtext.ScrolledText(self.root, height=10, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        self.log.insert(tk.END, "Selecciona una unidad y pulsa «Ver log corto».")
        self.log.config(state=tk.DISABLED)

        _aplicar_tema(self.root)
        self.cargar()

    def _seleccion(self):
        seleccion = self.tree.selection()
        if not seleccion:
            return None
        return self._por_iid.get(seleccion[0])

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for boton in (self.btn_actualizar, self.btn_reiniciar, self.btn_log):
            try:
                boton.config(state=estado)
            except tk.TclError:
                pass
        if ocupado:
            self.progreso.start(12)
            if mensaje:
                self.lbl_estado.config(text=mensaje, fg="#2471a3")
        else:
            self.progreso.stop()

    def _poner_log(self, texto):
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.insert(tk.END, texto)
        self.log.config(state=tk.DISABLED)

    def cargar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Buscando unidades en fallo…")

        def trabajador():
            return _listar_unidades_fallidas()

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            unidades, error = resultado
            self._mostrar(unidades, error)

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror("Servicios Que Fallan", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _mostrar(self, unidades, error):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._por_iid.clear()
        if error:
            self.lbl_estado.config(text=error, fg="#c0392b")
            return
        if not unidades:
            self.lbl_estado.config(text="No hay unidades en fallo.", fg="#1e8449")
            self._poner_log("No hay unidades fallidas ahora mismo.")
            return
        self.lbl_estado.config(
            text=f"{len(unidades)} unidad(es) en fallo.",
            fg="#c0392b",
        )
        for item in unidades:
            estado = f"{item['estado']} / {item['subestado']}"
            iid = self.tree.insert(
                "",
                tk.END,
                values=(item["unidad"], estado, item["descripcion"]),
                tags=("failed",),
            )
            self._por_iid[iid] = item

    def _reiniciar(self):
        if self._ocupado:
            return
        unidad = self._seleccion()
        if not unidad:
            messagebox.showinfo(
                "Servicios Que Fallan",
                "Selecciona una unidad de la lista.",
                parent=self.root,
            )
            return
        nombre = unidad["unidad"]
        if not confirmar(
            f"Se va a reiniciar:\n\n{nombre}\n\n"
            "Si sigue fallando, mira el log corto para ver el motivo.\n\n¿Quieres reiniciarla?",
            self.root,
            "Reiniciar Unidad",
        ):
            return

        def trabajo():
            return sudo_run(["systemctl", "restart", nombre], f"Reiniciar {nombre}", timeout=120)

        self._set_ocupado(True, f"Reiniciando {nombre}…")

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            if resultado is not None and resultado.returncode != 0:
                texto = (resultado.stderr or resultado.stdout or "No se pudo reiniciar.").strip()
                messagebox.showerror("Servicios Que Fallan", texto, parent=self.root)
            elif resultado is None:
                self.lbl_estado.config(text="Reinicio cancelado.", fg="#2471a3")
            else:
                self.lbl_estado.config(text=f"Reinicio de {nombre} pedido.", fg="#1e8449")
            self.cargar()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror("Servicios Que Fallan", str(error), parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)

    def _ver_log(self):
        if self._ocupado:
            return
        unidad = self._seleccion()
        if not unidad:
            messagebox.showinfo(
                "Servicios Que Fallan",
                "Selecciona una unidad de la lista.",
                parent=self.root,
            )
            return
        nombre = unidad["unidad"]
        self._set_ocupado(True, f"Leyendo log de {nombre}…")

        def trabajo():
            return _log_corto_unidad(nombre)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            texto, error = resultado
            if error == "cancelado":
                self.lbl_estado.config(text="Lectura del log cancelada.", fg="#2471a3")
                return
            if error:
                messagebox.showerror("Servicios Que Fallan", error, parent=self.root)
                self._poner_log(error)
                return
            self._poner_log(texto or "(Vacío)")
            self.lbl_estado.config(text=f"Log de {nombre} (últimas 40 líneas).", fg="#2471a3")

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            messagebox.showerror("Servicios Que Fallan", str(error), parent=self.root)

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)
