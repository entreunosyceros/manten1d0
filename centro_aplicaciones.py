"""Centro de aplicaciones: APT (escritorio), Snap y Flatpak en una sola vista."""

import configparser
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import preferencias
from cat_sistema import DebInstalador, abrir_gestor_software
from cat_sistema_extra import (
    _formato_tamano,
    _listar_flatpaks,
    _listar_snaps,
)
from registro import confirmar, en_hilo, registrar, sudo_run
from tooltip import ToolTip, con_tooltip


def _comando(args, timeout=60):
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


def _directorios_desktop():
    rutas = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]
    return [r for r in rutas if os.path.isdir(r)]


def _leer_desktop(ruta):
    """Devuelve dict Name/Exec/NoDisplay/Hidden o None si no es app usable."""
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ruta, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        return None
    if "Desktop Entry" not in parser:
        return None
    seccion = parser["Desktop Entry"]
    tipo = (seccion.get("Type") or "Application").strip()
    if tipo != "Application":
        return None
    if seccion.getboolean("NoDisplay", fallback=False):
        return None
    if seccion.getboolean("Hidden", fallback=False):
        return None
    nombre = (seccion.get("Name") or "").strip()
    if not nombre:
        nombre = os.path.splitext(os.path.basename(ruta))[0]
    exec_line = (seccion.get("Exec") or "").strip()
    return {
        "nombre": nombre,
        "exec": exec_line,
        "ruta": ruta,
        "id_desktop": os.path.splitext(os.path.basename(ruta))[0],
    }


def _paquete_de_archivo(ruta, cache):
    """Resuelve el paquete APT dueño de un archivo (caché por ruta)."""
    if ruta in cache:
        return cache[ruta]
    proceso = _comando(["dpkg", "-S", "--", ruta], timeout=20)
    paquete = None
    if proceso.returncode == 0 and proceso.stdout:
        # formato: paquete: ruta
        primera = proceso.stdout.splitlines()[0]
        if ":" in primera:
            paquete = primera.split(":", 1)[0].strip().split(",")[0].strip()
    cache[ruta] = paquete
    return paquete


def _tamanos_paquetes(paquetes):
    """Installed-Size de dpkg en KB → bytes."""
    if not paquetes:
        return {}
    # Consulta por lotes
    resultado = {}
    lista = sorted(set(paquetes))
    for i in range(0, len(lista), 80):
        lote = lista[i : i + 80]
        proceso = _comando(
            ["dpkg-query", "-W", "-f=${Package}\\t${Installed-Size}\\n", *lote],
            timeout=60,
        )
        for linea in (proceso.stdout or "").splitlines():
            if "\t" not in linea:
                continue
            nombre, tam = linea.split("\t", 1)
            try:
                kb = int(tam.strip() or "0")
            except ValueError:
                kb = 0
            resultado[nombre] = kb * 1024
    return resultado


def _apt_actualizables():
    proceso = _comando(["apt", "list", "--upgradable"], timeout=60)
    nombres = set()
    for linea in (proceso.stdout or "").splitlines():
        if not linea or linea.startswith("Listing"):
            continue
        # nombre/arch ...
        nombre = linea.split("/", 1)[0].strip()
        if nombre:
            nombres.add(nombre)
    return nombres


def _snap_actualizables():
    if not shutil.which("snap"):
        return set()
    proceso = _comando(["snap", "refresh", "--list"], timeout=60)
    if proceso.returncode not in (0, 1):
        return set()
    nombres = set()
    for linea in (proceso.stdout or "").splitlines():
        if not linea.strip() or linea.lower().startswith("name"):
            continue
        if "up to date" in linea.lower():
            continue
        partes = linea.split()
        if partes:
            nombres.add(partes[0])
    return nombres


def _flatpak_actualizables():
    if not shutil.which("flatpak"):
        return set()
    proceso = _comando(
        ["flatpak", "remote-ls", "--updates", "--app", "--columns=application"],
        timeout=90,
    )
    if proceso.returncode != 0:
        return set()
    return {linea.strip() for linea in (proceso.stdout or "").splitlines() if linea.strip()}


def _listar_apt_escritorio():
    """Apps APT asociadas a archivos .desktop visibles."""
    cache_pkg = {}
    vistas = {}  # paquete -> app (dedupe por paquete, preferir primer nombre)
    sin_paquete = []
    for carpeta in _directorios_desktop():
        try:
            nombres = os.listdir(carpeta)
        except OSError:
            continue
        for archivo in nombres:
            if not archivo.endswith(".desktop"):
                continue
            ruta = os.path.join(carpeta, archivo)
            datos = _leer_desktop(ruta)
            if not datos:
                continue
            paquete = _paquete_de_archivo(ruta, cache_pkg)
            app = {
                "id": paquete or datos["id_desktop"],
                "nombre": datos["nombre"],
                "origen": "APT",
                "version": "",
                "tamano": 0,
                "escritorio": ruta,
                "desktop_id": datos["id_desktop"],
                "actualizable": False,
                "raw": paquete or datos["id_desktop"],
                "instalacion": "system",
            }
            if paquete:
                if paquete not in vistas:
                    vistas[paquete] = app
            else:
                sin_paquete.append(app)

    paquetes = list(vistas.keys())
    tamanos = _tamanos_paquetes(paquetes)
    # Versiones
    if paquetes:
        for i in range(0, len(paquetes), 80):
            lote = paquetes[i : i + 80]
            proceso = _comando(
                ["dpkg-query", "-W", "-f=${Package}\\t${Version}\\n", *lote],
                timeout=60,
            )
            for linea in (proceso.stdout or "").splitlines():
                if "\t" not in linea:
                    continue
                nombre, version = linea.split("\t", 1)
                if nombre in vistas:
                    vistas[nombre]["version"] = version.strip()
                    vistas[nombre]["tamano"] = tamanos.get(nombre, 0)

    apps = list(vistas.values()) + sin_paquete
    return apps


def cargar_aplicaciones():
    """Lista unificada APT + Snap + Flatpak con flags de actualización."""
    apps = []
    avisos = []

    try:
        apps.extend(_listar_apt_escritorio())
    except Exception as error:
        avisos.append(f"APT: {error}")

    snaps, err_snap = _listar_snaps()
    if err_snap == "no_instalado":
        pass
    elif err_snap:
        avisos.append(f"Snap: {err_snap}")
    else:
        for s in snaps:
            apps.append({
                "id": s["id"],
                "nombre": s["nombre"],
                "origen": "Snap",
                "version": s.get("version") or "",
                "tamano": s.get("tamano") or 0,
                "escritorio": None,
                "desktop_id": None,
                "actualizable": False,
                "raw": s["id"],
                "instalacion": s.get("instalacion") or "system",
            })

    flats, err_flat = _listar_flatpaks()
    if err_flat == "no_instalado":
        pass
    elif err_flat:
        avisos.append(f"Flatpak: {err_flat}")
    else:
        for f in flats:
            apps.append({
                "id": f["id"],
                "nombre": f["nombre"],
                "origen": "Flatpak",
                "version": (f.get("version") or "").replace("—", "").replace("–", "").strip() or "",
                "tamano": f.get("tamano") or 0,
                "escritorio": None,
                "desktop_id": None,
                "actualizable": False,
                "raw": f["id"],
                "instalacion": f.get("instalacion") or "system",
            })

    apt_up = _apt_actualizables()
    snap_up = _snap_actualizables()
    flat_up = _flatpak_actualizables()
    for app in apps:
        if app["origen"] == "APT" and app["raw"] in apt_up:
            app["actualizable"] = True
        elif app["origen"] == "Snap" and app["raw"] in snap_up:
            app["actualizable"] = True
        elif app["origen"] == "Flatpak" and app["raw"] in flat_up:
            app["actualizable"] = True

    apps.sort(key=lambda a: (a["nombre"] or "").lower())
    return apps, avisos


def abrir_aplicacion(app):
    """Lanza la aplicación. Devuelve (ok, mensaje)."""
    origen = app["origen"]
    if origen == "Snap":
        try:
            subprocess.Popen(["snap", "run", app["raw"]], start_new_session=True)
            return True, f"Abriendo {app['nombre']}..."
        except OSError as error:
            return False, str(error)
    if origen == "Flatpak":
        args = ["flatpak", "run", app["raw"]]
        try:
            subprocess.Popen(args, start_new_session=True)
            return True, f"Abriendo {app['nombre']}..."
        except OSError as error:
            return False, str(error)
    # APT / desktop
    desktop_id = app.get("desktop_id")
    escritorio = app.get("escritorio")
    if desktop_id and shutil.which("gtk-launch"):
        try:
            subprocess.Popen(["gtk-launch", desktop_id], start_new_session=True)
            return True, f"Abriendo {app['nombre']}..."
        except OSError:
            pass
    if escritorio and shutil.which("gio"):
        try:
            subprocess.Popen(["gio", "launch", escritorio], start_new_session=True)
            return True, f"Abriendo {app['nombre']}..."
        except OSError:
            pass
    if escritorio:
        try:
            subprocess.Popen(["xdg-open", escritorio], start_new_session=True)
            return True, f"Abriendo {app['nombre']}..."
        except OSError as error:
            return False, str(error)
    return False, "No se encontró forma de abrir esta aplicación."


def actualizar_aplicacion(app):
    """Actualiza una app. Devuelve (ok, mensaje)."""
    if app["origen"] == "APT":
        pkg = app["raw"]
        r = sudo_run(
            ["apt-get", "install", "--only-upgrade", "-y", pkg],
            f"Actualizar APT {pkg}",
            timeout=600,
        )
        if r is None:
            return False, "Cancelado."
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "Error al actualizar.").strip()[:400]
        return True, f"{app['nombre']} actualizado (APT)."
    if app["origen"] == "Snap":
        r = sudo_run(["snap", "refresh", app["raw"]], f"Actualizar Snap {app['raw']}", timeout=600)
        if r is None:
            return False, "Cancelado."
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "Error al actualizar Snap.").strip()[:400]
        return True, f"{app['nombre']} actualizado (Snap)."
    if app["origen"] == "Flatpak":
        args = ["flatpak", "update", "-y", app["raw"]]
        if app.get("instalacion") == "user":
            args = ["flatpak", "update", "-y", "--user", app["raw"]]
            r = _comando(args, timeout=600)
            registrar(f"Actualizar Flatpak {app['raw']}", " ".join(args), r.returncode == 0)
        else:
            r = sudo_run(args, f"Actualizar Flatpak {app['raw']}", timeout=600)
            if r is None:
                return False, "Cancelado."
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "Error al actualizar Flatpak.").strip()[:400]
        return True, f"{app['nombre']} actualizado (Flatpak)."
    return False, "Origen desconocido."


def desinstalar_aplicacion(app):
    """Desinstala una app. Devuelve (ok, mensaje)."""
    if app["origen"] == "APT":
        pkg = app["raw"]
        r = sudo_run(
            ["apt-get", "remove", "--purge", "-y", pkg],
            f"Desinstalar APT {pkg}",
            timeout=600,
        )
        if r is None:
            return False, "Cancelado."
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "Error al desinstalar.").strip()[:400]
        return True, f"{app['nombre']} desinstalado (APT)."
    if app["origen"] == "Snap":
        r = sudo_run(["snap", "remove", app["raw"]], f"Desinstalar Snap {app['raw']}", timeout=600)
        if r is None:
            return False, "Cancelado."
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "Error al quitar Snap.").strip()[:400]
        return True, f"{app['nombre']} desinstalado (Snap)."
    if app["origen"] == "Flatpak":
        if app.get("instalacion") == "user":
            args = ["flatpak", "uninstall", "-y", "--user", app["raw"]]
            r = _comando(args, timeout=600)
            registrar(f"Desinstalar Flatpak {app['raw']}", " ".join(args), r.returncode == 0)
        else:
            r = sudo_run(
                ["flatpak", "uninstall", "-y", app["raw"]],
                f"Desinstalar Flatpak {app['raw']}",
                timeout=600,
            )
            if r is None:
                return False, "Cancelado."
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "Error al quitar Flatpak.").strip()[:400]
        return True, f"{app['nombre']} desinstalado (Flatpak)."
    return False, "Origen desconocido."


class CentroAplicaciones:
    """Panel unificado de aplicaciones instaladas."""

    def __init__(self, root):
        self.root = root
        self.root.title("Centro De Aplicaciones")
        self.root.minsize(780, 560)
        self._centrar(900, 640)
        self._ocupado = False
        self._apps = []
        self._por_iid = {}
        self._filtro_origen = tk.StringVar(value="todos")
        self._busqueda = tk.StringVar()

        tk.Label(self.root, text="Centro de aplicaciones", font=("Arial", 14, "bold")).pack(
            pady=(12, 4)
        )
        tk.Label(
            self.root,
            text=(
                "Lista las aplicaciones de escritorio (APT), Snap y Flatpak. "
                "Busca, abre, actualiza o desinstala desde un solo sitio."
            ),
            wraplength=860,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 6))

        barra = tk.Frame(self.root)
        barra.pack(fill=tk.X, padx=14, pady=(0, 4))
        tk.Label(barra, text="Buscar:").pack(side=tk.LEFT)
        entrada = tk.Entry(barra, textvariable=self._busqueda, width=36)
        entrada.pack(side=tk.LEFT, padx=6)
        entrada.bind("<KeyRelease>", lambda _e: self._aplicar_filtro())
        ToolTip(entrada, "Filtra por nombre, origen o identificador")
        tk.Label(barra, text="Origen:").pack(side=tk.LEFT, padx=(12, 4))
        for valor, texto in (
            ("todos", "Todos"),
            ("APT", "APT"),
            ("Snap", "Snap"),
            ("Flatpak", "Flatpak"),
        ):
            tk.Radiobutton(
                barra,
                text=texto,
                variable=self._filtro_origen,
                value=valor,
                command=self._aplicar_filtro,
            ).pack(side=tk.LEFT, padx=2)

        self.lbl_estado = tk.Label(self.root, text="Cargando...", anchor="w")
        self.lbl_estado.pack(fill=tk.X, padx=14)
        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(2, 6))

        cuerpo = tk.Frame(self.root)
        cuerpo.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 4))

        izquierda = tk.Frame(cuerpo)
        izquierda.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columnas = ("nombre", "origen", "version", "tamano", "act")
        self.tree = ttk.Treeview(
            izquierda,
            columns=columnas,
            show="headings",
            selectmode="browse",
            height=16,
        )
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("origen", text="Origen")
        self.tree.heading("version", text="Versión")
        self.tree.heading("tamano", text="Tamaño")
        self.tree.heading("act", text="Act.")
        self.tree.column("nombre", width=220, stretch=True)
        self.tree.column("origen", width=70, stretch=False)
        self.tree.column("version", width=120, stretch=False)
        self.tree.column("tamano", width=80, stretch=False)
        self.tree.column("act", width=50, stretch=False)
        scroll = ttk.Scrollbar(izquierda, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._mostrar_detalle())

        derecha = tk.Frame(cuerpo, width=280)
        derecha.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        derecha.pack_propagate(False)

        tk.Label(derecha, text="Detalle", font=("Arial", 11, "bold"), anchor="w").pack(
            fill=tk.X
        )
        self.lbl_detalle = tk.Label(
            derecha,
            text="Selecciona una aplicación.",
            justify=tk.LEFT,
            anchor="nw",
            wraplength=260,
        )
        self.lbl_detalle.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        self.btn_abrir = tk.Button(derecha, text="Abrir", width=18, command=self._abrir)
        self.btn_abrir.pack(pady=2)
        ToolTip(self.btn_abrir, "Abre la aplicación seleccionada")
        self.btn_actualizar = tk.Button(
            derecha, text="Actualizar", width=18, command=self._actualizar
        )
        self.btn_actualizar.pack(pady=2)
        ToolTip(self.btn_actualizar, "Actualiza solo esta aplicación si hay versión nueva")
        self.btn_desinstalar = tk.Button(
            derecha, text="Desinstalar", width=18, command=self._desinstalar
        )
        self.btn_desinstalar.pack(pady=2)
        ToolTip(self.btn_desinstalar, "Quita la aplicación del sistema (pide confirmación)")

        tk.Label(
            derecha,
            text="Más espacio",
            font=("Arial", 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(12, 2))
        self.lista_top = tk.Listbox(derecha, height=8, exportselection=False)
        self.lista_top.pack(fill=tk.X)
        self.lista_top.bind("<<ListboxSelect>>", self._seleccionar_top)
        ToolTip(self.lista_top, "Las que más ocupan; clic para seleccionarlas arriba")
        self._top_ids = []

        pie = tk.Frame(self.root)
        pie.pack(pady=(4, 12))
        con_tooltip(
            tk.Button(pie, text="Actualizar lista", width=14, command=self.cargar),
            "Vuelve a leer APT, Snap y Flatpak",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Instalar .deb", width=14, command=self._instalar_deb),
            "Elige un archivo .deb e instálalo",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Abrir tienda", width=14, command=self._abrir_tienda),
            "Abre el gestor de software de Ubuntu (Snap Store)",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Cerrar", width=10, command=self.root.destroy),
            "Cierra esta ventana",
        ).pack(side=tk.LEFT, padx=4)

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)
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
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for btn in (
            self.btn_abrir,
            self.btn_actualizar,
            self.btn_desinstalar,
        ):
            try:
                btn.config(state=estado)
            except tk.TclError:
                pass
        if ocupado:
            self.progreso.start(12)
            if mensaje:
                self.lbl_estado.config(text=mensaje)
        else:
            self.progreso.stop()

    def cargar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Cargando aplicaciones...")

        def trabajador():
            return cargar_aplicaciones()

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            apps, avisos = resultado
            self._apps = apps
            extra = ""
            if avisos:
                extra = " · " + "; ".join(avisos[:2])
            self.lbl_estado.config(
                text=f"{len(apps)} aplicación(es){extra}",
            )
            self._rellenar_top()
            self._aplicar_filtro()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self.lbl_estado.config(text=str(error))
            messagebox.showerror("Centro de aplicaciones", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _rellenar_top(self):
        self.lista_top.delete(0, tk.END)
        self._top_ids = []
        ordenadas = sorted(
            [a for a in self._apps if a.get("tamano")],
            key=lambda a: a["tamano"],
            reverse=True,
        )[:10]
        for app in ordenadas:
            texto = f"{app['nombre']} - {_formato_tamano(app['tamano'])} ({app['origen']})"
            self.lista_top.insert(tk.END, texto)
            self._top_ids.append((app["origen"], app["raw"]))

    def _apps_filtradas(self):
        texto = (self._busqueda.get() or "").strip().lower()
        origen = self._filtro_origen.get()
        resultado = []
        for app in self._apps:
            if origen != "todos" and app["origen"] != origen:
                continue
            if texto:
                hay = (
                    texto in (app["nombre"] or "").lower()
                    or texto in (app["origen"] or "").lower()
                    or texto in (app["raw"] or "").lower()
                    or texto in (app["version"] or "").lower()
                )
                if not hay:
                    continue
            resultado.append(app)
        return resultado

    def _aplicar_filtro(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._por_iid.clear()
        for app in self._apps_filtradas():
            act = "Si" if app.get("actualizable") else "No"
            version = (app.get("version") or "").strip() or "-"
            tamano = _formato_tamano(app["tamano"]) if app.get("tamano") else "-"
            iid = self.tree.insert(
                "",
                tk.END,
                values=(
                    app["nombre"],
                    app["origen"],
                    version,
                    tamano,
                    act,
                ),
            )
            self._por_iid[iid] = app
        self.lbl_detalle.config(text="Selecciona una aplicacion.")

    def _seleccion(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._por_iid.get(sel[0])

    def _mostrar_detalle(self):
        app = self._seleccion()
        if not app:
            self.lbl_detalle.config(text="Selecciona una aplicacion.")
            return
        act = "si" if app.get("actualizable") else "no"
        tam = _formato_tamano(app["tamano"]) if app.get("tamano") else "desconocido"
        version = (app.get("version") or "").strip() or "-"
        texto = (
            f"{app['nombre']}\n\n"
            f"Instalado mediante: {app['origen']}\n"
            f"Identificador: {app['raw']}\n"
            f"Version: {version}\n"
            f"Tamano: {tam}\n"
            f"Actualizacion disponible: {act}"
        )
        self.lbl_detalle.config(text=texto)

    def _seleccionar_top(self, _event=None):
        sel = self.lista_top.curselection()
        if not sel:
            return
        origen, raw = self._top_ids[sel[0]]
        for iid, app in self._por_iid.items():
            if app["origen"] == origen and app["raw"] == raw:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                self._mostrar_detalle()
                return
        # Puede estar filtrado: quitar filtro y buscar en _apps
        self._filtro_origen.set("todos")
        self._busqueda.set("")
        self._aplicar_filtro()
        for iid, app in self._por_iid.items():
            if app["origen"] == origen and app["raw"] == raw:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                self._mostrar_detalle()
                return

    def _abrir(self):
        app = self._seleccion()
        if not app:
            messagebox.showinfo(
                "Centro de aplicaciones",
                "Selecciona una aplicación.",
                parent=self.root,
            )
            return
        ok, msg = abrir_aplicacion(app)
        if not ok:
            messagebox.showwarning("Centro de aplicaciones", msg, parent=self.root)

    def _actualizar(self):
        if self._ocupado:
            return
        app = self._seleccion()
        if not app:
            messagebox.showinfo(
                "Centro de aplicaciones",
                "Selecciona una aplicación.",
                parent=self.root,
            )
            return
        if not app.get("actualizable"):
            if not confirmar(
                f"No se detectó actualización pendiente para {app['nombre']}.\n\n"
                "¿Quieres intentar actualizarla igual?",
                self.root,
                "Actualizar",
            ):
                return
        elif not confirmar(
            f"¿Qué voy a hacer?\nActualizar {app['nombre']} ({app['origen']}).\n\n"
            f"¿Por qué?\nHay una versión más nueva disponible.\n\n"
            f"¿Qué riesgos tiene?\nBajo. Puede pedir reiniciar la app si está abierta.\n\n"
            "¿Continuar?",
            self.root,
            "Actualizar",
        ):
            return

        self._set_ocupado(True, f"Actualizando {app['nombre']}...")

        def trabajador():
            return actualizar_aplicacion(app)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            ok, msg = resultado
            registrar("Centro aplicaciones", f"actualizar {app['origen']} {app['raw']}", ok)
            if ok:
                messagebox.showinfo("Centro de aplicaciones", msg, parent=self.root)
            else:
                messagebox.showwarning("Centro de aplicaciones", msg, parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajador, al_terminar=al_terminar)

    def _desinstalar(self):
        if self._ocupado:
            return
        app = self._seleccion()
        if not app:
            messagebox.showinfo(
                "Centro de aplicaciones",
                "Selecciona una aplicación.",
                parent=self.root,
            )
            return
        if not confirmar(
            f"¿Qué voy a hacer?\nDesinstalar {app['nombre']} ({app['origen']} / {app['raw']}).\n\n"
            f"¿Por qué?\nYa no la necesitas o quieres liberar espacio.\n\n"
            f"¿Qué riesgos tiene?\nPerderás la aplicación y, según el origen, "
            "datos de configuración asociados. Tus documentos no se borran.\n\n"
            "¿Continuar?",
            self.root,
            "Desinstalar",
        ):
            return

        self._set_ocupado(True, f"Desinstalando {app['nombre']}...")

        def trabajador():
            return desinstalar_aplicacion(app)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            ok, msg = resultado
            registrar("Centro aplicaciones", f"desinstalar {app['origen']} {app['raw']}", ok)
            if ok:
                messagebox.showinfo("Centro de aplicaciones", msg, parent=self.root)
            else:
                messagebox.showwarning("Centro de aplicaciones", msg, parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajador, al_terminar=al_terminar)

    def _instalar_deb(self):
        DebInstalador().ejecutar(self.root)

    def _abrir_tienda(self):
        abrir_gestor_software()
