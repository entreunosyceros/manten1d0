"""
Herramientas extra de la categoría Sistema:
limpieza de espacio en disco, salud SMART y servicios systemd.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import preferencias
from password import obtener_contrasena
from tooltip import ToolTip
from registro import registrar, registrar_comando, en_hilo


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
        self.root.title("Limpieza de espacio en disco")
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
            var = tk.BooleanVar(value=elemento["tamano"] > 0)
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
            if elemento["tamano"] <= 0:
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
        self.root.title("Salud de discos (SMART)")
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
        self.root.title("Servicios systemd")
        _centrar_ventana(self.root, 860, 580)
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

        scroll = ttk.Scrollbar(cuerpo, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)

        marco_botones = tk.Frame(cuerpo)
        marco_botones.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
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
            boton.pack(pady=4)
            ToolTip(boton, tip)

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

