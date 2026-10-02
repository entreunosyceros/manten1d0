"""Actualizar APT, Snap y Flatpak en un solo flujo."""

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import preferencias
from registro import confirmar, en_hilo, registrar, sudo_run
from tooltip import ToolTip


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


def _binario(nombre):
    return shutil.which(nombre) is not None


def listar_apt_upgradable():
    """Lista nombres de paquetes APT actualizables."""
    proceso = _comando(["apt", "list", "--upgradable"], timeout=40)
    nombres = []
    for linea in (proceso.stdout or "").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("Listing"):
            continue
        # formato: paquete/origen version [upgradable from: ...]
        nombre = linea.split("/", 1)[0].strip()
        if nombre:
            nombres.append(nombre)
    return nombres


def listar_snap_refresh():
    if not _binario("snap"):
        return None
    proceso = _comando(["snap", "refresh", "--list"], timeout=60)
    if proceso.returncode not in (0, 1):
        return []
    nombres = []
    for linea in (proceso.stdout or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        primera = linea.split()[0].lower()
        if primera in ("name", "nombre"):
            continue
        if "up to date" in linea.lower() or "al dia" in linea.lower() or "al día" in linea.lower():
            return []
        nombres.append(linea.split()[0])
    return nombres


def listar_flatpak_updates():
    if not _binario("flatpak"):
        return None
    proceso = _comando(
        ["flatpak", "remote-ls", "--updates", "--app", "--columns=application,name"],
        timeout=90,
    )
    if proceso.returncode != 0:
        return []
    nombres = []
    for linea in (proceso.stdout or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        partes = linea.split("\t") if "\t" in linea else linea.split(None, 1)
        if len(partes) >= 2 and partes[1].strip():
            nombres.append(partes[1].strip())
        else:
            nombres.append(partes[0].strip())
    return nombres


def contar_apt():
    """Devuelve (total, seguridad) o (None, None) si no se pudo consultar."""
    comprobador = "/usr/lib/update-notifier/apt-check"
    if os.path.exists(comprobador):
        proceso = _comando([comprobador], timeout=30)
        texto = (proceso.stderr or proceso.stdout or "").strip()
        if ";" in texto:
            try:
                pendientes, seguridad = texto.split(";", 1)
                return int(pendientes), int(seguridad)
            except ValueError:
                pass
    return len(listar_apt_upgradable()), 0


def contar_snap():
    lista = listar_snap_refresh()
    if lista is None:
        return None
    return len(lista)


def contar_flatpak():
    lista = listar_flatpak_updates()
    if lista is None:
        return None
    return len(lista)


def resumen_pendientes():
    """Dict con conteos, listas de paquetes y texto para la UI."""
    apt_lista = listar_apt_upgradable()
    snap_lista = listar_snap_refresh()
    flat_lista = listar_flatpak_updates()

    comprobador = "/usr/lib/update-notifier/apt-check"
    apt_sec = 0
    if os.path.exists(comprobador):
        proceso = _comando([comprobador], timeout=30)
        texto = (proceso.stderr or proceso.stdout or "").strip()
        if ";" in texto:
            try:
                _pendientes, seguridad = texto.split(";", 1)
                apt_sec = int(seguridad)
            except ValueError:
                pass

    return {
        "apt": len(apt_lista),
        "apt_seguridad": apt_sec,
        "apt_paquetes": apt_lista,
        "snap": None if snap_lista is None else len(snap_lista),
        "snap_paquetes": snap_lista or [],
        "flatpak": None if flat_lista is None else len(flat_lista),
        "flatpak_paquetes": flat_lista or [],
        "snap_disponible": snap_lista is not None,
        "flatpak_disponible": flat_lista is not None,
    }


def ejecutar_actualizacion(on_progreso=None):
    """
    Actualiza APT, luego Snap, luego Flatpak.
    on_progreso(texto) opcional.
    Devuelve lista de (paso, ok, detalle).
    """
    resultados = []

    def aviso(texto):
        if on_progreso:
            on_progreso(texto)

    aviso("APT: actualizando indices...")
    r_update = sudo_run(["apt-get", "update"], "APT update (Actualizar todo)", timeout=300)
    if r_update is None:
        resultados.append(("APT update", False, "Cancelado o sin contraseña."))
        return resultados
    if r_update.returncode != 0:
        detalle = (r_update.stderr or r_update.stdout or "Error en apt-get update").strip()[:400]
        resultados.append(("APT update", False, detalle))
        # Seguimos con upgrade por si el índice aún sirve
    else:
        resultados.append(("APT update", True, "Indices actualizados."))

    aviso("APT: instalando actualizaciones...")
    r_upgrade = sudo_run(
        ["apt-get", "upgrade", "-y"],
        "APT upgrade (Actualizar todo)",
        timeout=900,
    )
    if r_upgrade is None:
        resultados.append(("APT upgrade", False, "Cancelado."))
    elif r_upgrade.returncode != 0:
        detalle = (r_upgrade.stderr or r_upgrade.stdout or "Error en apt-get upgrade").strip()[:400]
        resultados.append(("APT upgrade", False, detalle))
    else:
        resultados.append(("APT upgrade", True, "Paquetes APT al dia."))

    if _binario("snap"):
        aviso("Snap: actualizando...")
        r_snap = sudo_run(["snap", "refresh"], "Snap refresh (Actualizar todo)", timeout=900)
        if r_snap is None:
            resultados.append(("Snap", False, "Cancelado."))
        elif r_snap.returncode != 0:
            detalle = (r_snap.stderr or r_snap.stdout or "Error en snap refresh").strip()[:400]
            resultados.append(("Snap", False, detalle))
        else:
            resultados.append(("Snap", True, "Snaps actualizados."))
    else:
        resultados.append(("Snap", True, "Snap no esta instalado (omitido)."))

    if _binario("flatpak"):
        aviso("Flatpak (sistema): actualizando...")
        r_flat = sudo_run(
            ["flatpak", "update", "-y"],
            "Flatpak update system (Actualizar todo)",
            timeout=900,
        )
        if r_flat is None:
            resultados.append(("Flatpak system", False, "Cancelado."))
        elif r_flat.returncode != 0:
            detalle = (r_flat.stderr or r_flat.stdout or "Error en flatpak update").strip()[:400]
            resultados.append(("Flatpak system", False, detalle))
        else:
            resultados.append(("Flatpak system", True, "Flatpak (sistema) al dia."))

        aviso("Flatpak (usuario): actualizando...")
        r_user = _comando(["flatpak", "update", "-y", "--user"], timeout=900)
        registrar(
            "Flatpak update user (Actualizar todo)",
            "flatpak update -y --user",
            r_user.returncode == 0,
        )
        if r_user.returncode != 0:
            detalle = (r_user.stderr or r_user.stdout or "Error en flatpak --user").strip()[:400]
            resultados.append(("Flatpak user", False, detalle))
        else:
            resultados.append(("Flatpak user", True, "Flatpak (usuario) al dia."))
    else:
        resultados.append(("Flatpak", True, "Flatpak no esta instalado (omitido)."))

    return resultados


class ActualizarTodo:
    """Panel: cuenta pendientes APT/Snap/Flatpak y actualiza todo en un flujo."""

    def __init__(self, root):
        self.root = root
        self.root.title("Actualizar Todo")
        self.root.minsize(520, 420)
        self._centrar(600, 480)
        self._ocupado = False
        self._resumen = None

        tk.Label(self.root, text="Actualizar todo", font=("Arial", 14, "bold")).pack(
            pady=(12, 4)
        )
        tk.Label(
            self.root,
            text=(
                "Comprueba e instala actualizaciones de APT, Snap y Flatpak "
                "en un solo paso, con progreso visible."
            ),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 8))

        self.lbl_estado = tk.Label(
            self.root,
            text="Comprobando pendientes...",
            font=("Arial", 11, "bold"),
            justify=tk.LEFT,
            anchor="w",
        )
        self.lbl_estado.pack(fill=tk.X, padx=14)

        self.lbl_detalle = tk.Label(
            self.root,
            text="",
            justify=tk.LEFT,
            anchor="w",
            wraplength=560,
        )
        self.lbl_detalle.pack(fill=tk.X, padx=14, pady=(4, 8))

        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(0, 8))

        self.log = scrolledtext.ScrolledText(self.root, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))

        botones = tk.Frame(self.root)
        botones.pack(pady=(0, 12))
        self.btn_comprobar = tk.Button(botones, text="Comprobar", width=14, command=self.comprobar)
        self.btn_comprobar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_comprobar, "Vuelve a contar actualizaciones pendientes")
        self.btn_actualizar = tk.Button(
            botones,
            text="Actualizar todo",
            width=14,
            command=self.actualizar,
        )
        self.btn_actualizar.pack(side=tk.LEFT, padx=6)
        ToolTip(
            self.btn_actualizar,
            "Ejecuta apt update/upgrade, snap refresh y flatpak update (sistema y usuario)",
        )
        btn_cerrar = tk.Button(botones, text="Cerrar", width=10, command=self.root.destroy)
        btn_cerrar.pack(side=tk.LEFT, padx=6)
        ToolTip(btn_cerrar, "Cierra esta ventana")

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)
        self.comprobar()

    def _centrar(self, ancho, alto):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - ancho) // 2
        y = (self.root.winfo_screenheight() - alto) // 2
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _log(self, texto):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, texto.rstrip() + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        try:
            self.btn_comprobar.config(state=estado)
            self.btn_actualizar.config(state=estado)
        except tk.TclError:
            pass
        if ocupado:
            self.progreso.start(12)
            if mensaje:
                self.lbl_estado.config(text=mensaje)
        else:
            self.progreso.stop()

    def comprobar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Comprobando pendientes...")

        def trabajador():
            return resumen_pendientes()

        def al_terminar(datos):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._resumen = datos
            self._mostrar_resumen(datos)

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self.lbl_estado.config(text=str(error))

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _mostrar_resumen(self, datos):
        apt = datos["apt"]
        sec = datos["apt_seguridad"]
        snap = datos["snap"]
        flat = datos["flatpak"]
        apt_paquetes = datos.get("apt_paquetes") or []
        snap_paquetes = datos.get("snap_paquetes") or []
        flat_paquetes = datos.get("flatpak_paquetes") or []
        total = apt
        if snap is not None:
            total += snap
        if flat is not None:
            total += flat

        if total == 0:
            self.lbl_estado.config(text="No hay actualizaciones pendientes")
        else:
            self.lbl_estado.config(text=f"{total} actualizacion(es) pendiente(s)")

        lineas = []
        extra_apt = f" ({sec} de seguridad)" if sec else ""
        lineas.append(f"APT: {apt}{extra_apt}")
        if snap is None:
            lineas.append("Snap: no instalado")
        else:
            lineas.append(f"Snap: {snap}")
        if flat is None:
            lineas.append("Flatpak: no instalado")
        else:
            lineas.append(f"Flatpak: {flat}")
        self.lbl_detalle.config(text="\n".join(lineas))

        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)

        if total == 0:
            self._log("No hay paquetes pendientes.")
            return

        self._log("Paquetes que se van a actualizar:")
        if apt_paquetes:
            self._log("")
            self._log("APT:")
            for nombre in apt_paquetes:
                self._log(f"  - {nombre}")
        elif apt:
            self._log("")
            self._log("APT: hay pendientes, pero no se pudo listar el nombre.")

        if snap is not None:
            if snap_paquetes:
                self._log("")
                self._log("Snap:")
                for nombre in snap_paquetes:
                    self._log(f"  - {nombre}")
            elif snap:
                self._log("")
                self._log("Snap: hay pendientes, pero no se pudo listar el nombre.")

        if flat is not None:
            if flat_paquetes:
                self._log("")
                self._log("Flatpak:")
                for nombre in flat_paquetes:
                    self._log(f"  - {nombre}")
            elif flat:
                self._log("")
                self._log("Flatpak: hay pendientes, pero no se pudo listar el nombre.")

    def actualizar(self):
        if self._ocupado:
            return
        datos = self._resumen or {}
        apt = datos.get("apt", "?")
        snap = datos.get("snap")
        flat = datos.get("flatpak")
        texto_snap = "no instalado" if snap is None else str(snap)
        texto_flat = "no instalado" if flat is None else str(flat)
        if not confirmar(
            "Se van a actualizar APT, Snap y Flatpak (si estan disponibles).\n\n"
            f"Pendientes aproximados:\n"
            f"- APT: {apt}\n"
            f"- Snap: {texto_snap}\n"
            f"- Flatpak: {texto_flat}\n\n"
            "Puede tardar varios minutos y pedira la contrasena de administrador.\n\n"
            "Continuar?",
            self.root,
            "Actualizar todo",
        ):
            return

        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)
        self._set_ocupado(True, "Actualizando...")

        def on_progreso(texto):
            if self.root.winfo_exists():
                self.root.after(0, lambda t=texto: self._avance(t))

        def trabajador():
            return ejecutar_actualizacion(on_progreso=on_progreso)

        def al_terminar(resultados):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            ok_total = all(ok for _paso, ok, _det in resultados)
            for paso, ok, detalle in resultados:
                marca = "OK" if ok else "ERROR"
                self._log(f"[{marca}] {paso}: {detalle}")
            registrar(
                "Actualizar todo",
                " | ".join(f"{p}:{'ok' if o else 'fail'}" for p, o, _d in resultados),
                ok_total,
            )
            if ok_total:
                self.lbl_estado.config(text="Actualizacion completada")
                messagebox.showinfo(
                    "Actualizar todo",
                    "APT, Snap y Flatpak se han actualizado correctamente.",
                    parent=self.root,
                )
            else:
                self.lbl_estado.config(text="Completado con avisos")
                messagebox.showwarning(
                    "Actualizar todo",
                    "Algunos pasos fallaron. Revisa el registro de la ventana "
                    "o Preferencias -> Registro de acciones.",
                    parent=self.root,
                )
            self.comprobar()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._log(f"[ERROR] {error}")
            messagebox.showerror("Actualizar todo", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _avance(self, texto):
        if not self.root.winfo_exists():
            return
        self.lbl_estado.config(text=texto)
        self._log(texto)
