"""Permisos, dispositivos de bloque, archivos grandes y hash."""

import grp
import hashlib
import os
import pwd
import re
import stat
import subprocess
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import preferencias
from registro import confirmar, en_hilo, registrar, registrar_comando, sudo_run
from tooltip import con_tooltip


def _centrar(ventana, ancho, alto):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def _tema(ventana):
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)


def _formato_tamano(nbytes):
    try:
        nbytes = float(nbytes)
    except (TypeError, ValueError):
        return "N/D"
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.0f} {unidad}" if unidad == "B" else f"{nbytes:.1f} {unidad}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def _comando(args, timeout=30):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=entorno)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", "comando no encontrado")
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


class PermisosArchivos:
    """chmod y chown con interfaz."""

    def __init__(self, root):
        self.root = root
        self.root.title("Permisos y propietario")
        _centrar(self.root, 560, 480)
        self.ruta = tk.StringVar()
        self.owner = tk.StringVar()
        self.group = tk.StringVar()
        self.octal = tk.StringVar(value="644")
        self.recursivo = tk.BooleanVar(value=False)
        self.checks = {}

        tk.Label(self.root, text="Permisos y propietario", font=("Arial", 14, "bold")).pack(pady=8)
        marco_ruta = tk.Frame(self.root)
        marco_ruta.pack(fill=tk.X, padx=12)
        tk.Entry(marco_ruta, textvariable=self.ruta).pack(side=tk.LEFT, fill=tk.X, expand=True)
        con_tooltip(
            tk.Button(marco_ruta, text="Archivo", command=self._elegir_archivo),
            "Elige un archivo para ver y cambiar sus permisos",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(marco_ruta, text="Carpeta", command=self._elegir_carpeta),
            "Elige una carpeta para ver y cambiar permisos (incluye opción recursiva)",
        ).pack(side=tk.LEFT)

        self.info = tk.Label(self.root, text="Elige un archivo o carpeta.", wraplength=500, justify=tk.LEFT)
        self.info.pack(padx=12, pady=8, anchor="w")

        tabla = tk.Frame(self.root)
        tabla.pack(pady=4)
        tk.Label(tabla, text="").grid(row=0, column=0)
        for col, titulo in enumerate(("Lectura", "Escritura", "Ejecución"), start=1):
            tk.Label(tabla, text=titulo).grid(row=0, column=col, padx=6)
        for fila, quien in enumerate(("Usuario", "Grupo", "Otros"), start=1):
            tk.Label(tabla, text=quien).grid(row=fila, column=0, sticky="e", padx=6)
            for col, letra in enumerate("rwx", start=1):
                var = tk.BooleanVar()
                self.checks[f"{quien[0].lower()}{letra}"] = var
                tk.Checkbutton(tabla, variable=var, command=self._checks_a_octal).grid(row=fila, column=col)

        marco_oct = tk.Frame(self.root)
        marco_oct.pack(pady=6)
        tk.Label(marco_oct, text="Octal:").pack(side=tk.LEFT)
        tk.Entry(marco_oct, textvariable=self.octal, width=6).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(marco_oct, text="Aplicar a casillas", command=self._octal_a_checks),
            "Traduce el valor octal a las casillas de lectura, escritura y ejecución",
        ).pack(side=tk.LEFT)

        marco_own = tk.Frame(self.root)
        marco_own.pack(pady=6)
        tk.Label(marco_own, text="Propietario:").pack(side=tk.LEFT)
        tk.Entry(marco_own, textvariable=self.owner, width=14).pack(side=tk.LEFT, padx=4)
        tk.Label(marco_own, text="Grupo:").pack(side=tk.LEFT)
        tk.Entry(marco_own, textvariable=self.group, width=14).pack(side=tk.LEFT, padx=4)

        tk.Checkbutton(self.root, text="Aplicar también a subcarpetas (recursivo)", variable=self.recursivo).pack()
        marco_btn = tk.Frame(self.root)
        marco_btn.pack(pady=12)
        con_tooltip(
            tk.Button(marco_btn, text="Aplicar chmod", command=self.aplicar_chmod),
            "Aplica los permisos. Pide sudo si el archivo no es tuyo",
        ).pack(side=tk.LEFT, padx=8)
        con_tooltip(
            tk.Button(marco_btn, text="Aplicar chown", command=self.aplicar_chown),
            "Cambia propietario y grupo. Pide sudo si el archivo no es tuyo",
        ).pack(side=tk.LEFT, padx=8)
        _tema(self.root)

    def _elegir_archivo(self):
        ruta = filedialog.askopenfilename(parent=self.root, initialdir=os.path.expanduser("~"))
        if ruta:
            self.ruta.set(ruta)
            self.cargar()

    def _elegir_carpeta(self):
        ruta = filedialog.askdirectory(parent=self.root, initialdir=os.path.expanduser("~"))
        if ruta:
            self.ruta.set(ruta)
            self.cargar()

    def cargar(self):
        ruta = self.ruta.get().strip()
        if not ruta or not os.path.exists(ruta):
            self.info.config(text="La ruta no existe.")
            return
        datos = os.stat(ruta)
        modo = stat.S_IMODE(datos.st_mode)
        self.octal.set(f"{modo:o}")
        self._octal_a_checks()
        try:
            dueno = pwd.getpwuid(datos.st_uid).pw_name
        except KeyError:
            dueno = str(datos.st_uid)
        try:
            grupo = grp.getgrgid(datos.st_gid).gr_name
        except KeyError:
            grupo = str(datos.st_gid)
        self.owner.set(dueno)
        self.group.set(grupo)
        tipo = "carpeta" if os.path.isdir(ruta) else "archivo"
        self.info.config(
            text=f"{tipo}: {ruta}\nPermisos {modo:o} ({stat.filemode(datos.st_mode)})  ·  {dueno}:{grupo}"
        )

    def _octal_a_checks(self):
        try:
            valor = int(self.octal.get().strip() or "0", 8)
        except ValueError:
            return
        bits = (
            ("ur", stat.S_IRUSR), ("uw", stat.S_IWUSR), ("ux", stat.S_IXUSR),
            ("gr", stat.S_IRGRP), ("gw", stat.S_IWGRP), ("gx", stat.S_IXGRP),
            ("or", stat.S_IROTH), ("ow", stat.S_IWOTH), ("ox", stat.S_IXOTH),
        )
        for clave, mascara in bits:
            self.checks[clave].set(bool(valor & mascara))

    def _checks_a_octal(self):
        valor = 0
        bits = (
            ("ur", stat.S_IRUSR), ("uw", stat.S_IWUSR), ("ux", stat.S_IXUSR),
            ("gr", stat.S_IRGRP), ("gw", stat.S_IWGRP), ("gx", stat.S_IXGRP),
            ("or", stat.S_IROTH), ("ow", stat.S_IWOTH), ("ox", stat.S_IXOTH),
        )
        for clave, mascara in bits:
            if self.checks[clave].get():
                valor |= mascara
        self.octal.set(f"{valor:o}")

    def aplicar_chmod(self):
        ruta = self.ruta.get().strip()
        if not ruta or not os.path.exists(ruta):
            messagebox.showinfo("Permisos", "Elige un archivo o carpeta.", parent=self.root)
            return
        self._checks_a_octal()
        modo = self.octal.get().strip()
        try:
            int(modo, 8)
        except ValueError:
            messagebox.showerror("Permisos", "El modo octal no es válido.", parent=self.root)
            return
        extra = " de forma recursiva" if self.recursivo.get() else ""
        if not confirmar(f"¿Aplicar chmod {modo}{extra} a\n{ruta}?", self.root, "chmod"):
            return
        args = ["chmod"]
        if self.recursivo.get():
            args.append("-R")
        args.extend([modo, ruta])

        def trabajo():
            try:
                if not self.recursivo.get():
                    os.chmod(ruta, int(modo, 8))
                    return True, ""
            except OSError:
                pass
            resultado = _comando(args)
            if resultado.returncode == 0:
                return True, ""
            resultado = sudo_run(args, f"chmod {modo}", parent=None, confirmar_accion=False)
            if resultado is None:
                return False, "cancelado"
            return resultado.returncode == 0, resultado.stderr

        def fin(par):
            ok, detalle = par
            registrar("chmod", f"{modo} {ruta}", ok)
            if ok:
                registrar_comando("chmod", args, sudo=False, tipo="args")
                messagebox.showinfo("Permisos", "Permisos actualizados.", parent=self.root)
                self.cargar()
            else:
                messagebox.showerror("Permisos", detalle or "No se pudo cambiar.", parent=self.root)

        en_hilo(self.root, trabajo, al_terminar=fin)

    def aplicar_chown(self):
        ruta = self.ruta.get().strip()
        if not ruta or not os.path.exists(ruta):
            messagebox.showinfo("Propietario", "Elige un archivo o carpeta.", parent=self.root)
            return
        destino = f"{self.owner.get().strip()}:{self.group.get().strip()}"
        if not self.owner.get().strip() or not self.group.get().strip():
            messagebox.showerror("Propietario", "Indica usuario y grupo.", parent=self.root)
            return
        extra = " de forma recursiva" if self.recursivo.get() else ""
        if not confirmar(f"¿Aplicar chown {destino}{extra} a\n{ruta}?", self.root, "chown"):
            return
        args = ["chown"]
        if self.recursivo.get():
            args.append("-R")
        args.extend([destino, ruta])

        def trabajo():
            resultado = sudo_run(args, f"chown {destino}", parent=None, confirmar_accion=False)
            return resultado

        def fin(resultado):
            ok = resultado is not None and resultado.returncode == 0
            if ok:
                messagebox.showinfo("Propietario", "Propietario actualizado.", parent=self.root)
                self.cargar()
            else:
                detalle = (resultado.stderr if resultado is not None else "cancelado")[:300]
                messagebox.showerror("Propietario", detalle or "No se pudo cambiar.", parent=self.root)

        en_hilo(self.root, trabajo, al_terminar=fin)


class DispositivosBloque:
    """Lista dispositivos de bloque y monta o desmonta USB."""

    def __init__(self, root):
        self.root = root
        self.root.title("Dispositivos USB / bloque")
        _centrar(self.root, 780, 460)
        self.filas = []

        tk.Label(self.root, text="Dispositivos de bloque", font=("Arial", 14, "bold")).pack(pady=8)
        self.lista = tk.Listbox(self.root, font=("monospace", 10), height=14)
        self.lista.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        marco = tk.Frame(self.root)
        marco.pack(pady=8)
        con_tooltip(
            tk.Button(marco, text="Actualizar", command=self.cargar),
            "Vuelve a listar discos y particiones detectados",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(marco, text="Montar", command=self.montar),
            "Monta el dispositivo seleccionado (udisksctl si está disponible)",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(marco, text="Desmontar", command=self.desmontar),
            "Desmonta el dispositivo seleccionado de forma segura",
        ).pack(side=tk.LEFT, padx=6)
        _tema(self.root)
        self.cargar()

    def cargar(self):
        resultado = _comando([
            "lsblk", "-lnp", "--pairs", "-o",
            "NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT,TRAN,RM,MODEL",
        ])
        self.lista.delete(0, tk.END)
        self.filas = []
        if resultado.returncode != 0:
            self.lista.insert(tk.END, resultado.stderr or "No se pudo ejecutar lsblk.")
            return
        for linea in resultado.stdout.splitlines():
            campos = dict(re.findall(r'(\w+)="([^"]*)"', linea))
            if not campos.get("NAME"):
                continue
            extraible = campos.get("RM", "")
            tran = campos.get("TRAN", "")
            tipo = campos.get("TYPE", "")
            self.filas.append({
                "name": campos.get("NAME", ""),
                "size": campos.get("SIZE", ""),
                "type": tipo,
                "fstype": campos.get("FSTYPE", ""),
                "label": campos.get("LABEL", ""),
                "mount": campos.get("MOUNTPOINT", ""),
                "tran": tran,
                "rm": extraible,
                "model": campos.get("MODEL", ""),
            })
            marca = "USB" if extraible in ("1", "yes") or tran == "usb" else tipo
            montaje = campos.get("MOUNTPOINT") or "—"
            self.lista.insert(
                tk.END,
                f"{campos.get('NAME', ''):<14} {campos.get('SIZE', ''):>7}  {marca:<6} "
                f"{campos.get('FSTYPE', ''):<6} {campos.get('LABEL', ''):<12} {montaje:<18} {campos.get('MODEL', '')}",
            )

    def _seleccion(self):
        indice = self.lista.curselection()
        if not indice or not self.filas:
            messagebox.showinfo("Dispositivos", "Selecciona una partición.", parent=self.root)
            return None
        return self.filas[indice[0]]

    def montar(self):
        item = self._seleccion()
        if not item:
            return
        if item["type"] == "disk" and not item.get("fstype"):
            messagebox.showwarning("Montar", "Selecciona una partición, no el disco entero.", parent=self.root)
            return
        if item["mount"] not in ("", "—"):
            messagebox.showinfo("Montar", f"Ya está montado en {item['mount']}.", parent=self.root)
            return
        if not confirmar(f"¿Montar {item['name']}?", self.root, "Montar"):
            return

        def trabajo():
            udisks = _comando(["udisksctl", "mount", "-b", item["name"]])
            if udisks.returncode == 0:
                return udisks
            return sudo_run(["mount", item["name"]], f"Montar {item['name']}", parent=None, confirmar_accion=False)

        def fin(resultado):
            ok = resultado is not None and resultado.returncode == 0
            registrar("Montar dispositivo", item["name"], ok)
            if ok:
                messagebox.showinfo("Montar", resultado.stdout or f"{item['name']} montado.", parent=self.root)
            else:
                messagebox.showerror("Montar", (resultado.stderr if resultado else "error")[:300], parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajo, al_terminar=fin)

    def desmontar(self):
        item = self._seleccion()
        if not item:
            return
        if not item["mount"]:
            messagebox.showinfo("Desmontar", "Ese dispositivo no está montado.", parent=self.root)
            return
        if not confirmar(f"¿Desmontar {item['name']} ({item['mount']})?", self.root, "Desmontar"):
            return

        def trabajo():
            udisks = _comando(["udisksctl", "unmount", "-b", item["name"]])
            if udisks.returncode == 0:
                return udisks
            return sudo_run(["umount", item["name"]], f"Desmontar {item['name']}", parent=None, confirmar_accion=False)

        def fin(resultado):
            ok = resultado is not None and resultado.returncode == 0
            registrar("Desmontar dispositivo", item["name"], ok)
            if ok:
                messagebox.showinfo("Desmontar", f"{item['name']} desmontado.", parent=self.root)
            else:
                messagebox.showerror("Desmontar", (resultado.stderr if resultado else "error")[:300], parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajo, al_terminar=fin)


class ArchivosGrandes:
    """Localiza archivos grandes, ISO y descargas antiguas."""

    def __init__(self, root):
        self.root = root
        self.root.title("Liberar espacio")
        _centrar(self.root, 820, 520)
        self.carpeta = tk.StringVar(value=os.path.expanduser("~"))
        self.min_mb = tk.StringVar(value="100")
        self.dias = tk.StringVar(value="90")
        self.filas = []

        tk.Label(self.root, text="Archivos grandes, ISO y descargas antiguas", font=("Arial", 14, "bold")).pack(pady=8)
        marco = tk.Frame(self.root)
        marco.pack(fill=tk.X, padx=10)
        tk.Entry(marco, textvariable=self.carpeta).pack(side=tk.LEFT, fill=tk.X, expand=True)
        con_tooltip(
            tk.Button(marco, text="Carpeta", command=self._elegir),
            "Elige la carpeta donde buscar archivos grandes e ISO",
        ).pack(side=tk.LEFT, padx=4)
        tk.Label(marco, text="Mín. MB").pack(side=tk.LEFT)
        tk.Entry(marco, textvariable=self.min_mb, width=6).pack(side=tk.LEFT, padx=4)
        tk.Label(marco, text="Días").pack(side=tk.LEFT)
        tk.Entry(marco, textvariable=self.dias, width=5).pack(side=tk.LEFT, padx=4)

        self.estado = tk.Label(self.root, text="Pulsa Analizar. No recorre /proc ni sistemas de red.")
        self.estado.pack(pady=4)

        self.lista = tk.Listbox(self.root, font=("monospace", 9), height=16)
        self.lista.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        botones = tk.Frame(self.root)
        botones.pack(pady=8)
        con_tooltip(
            tk.Button(botones, text="Analizar", command=self.analizar),
            "Busca archivos grandes, ISO y descargas antiguas en la carpeta indicada",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(botones, text="Abrir carpeta", command=self.abrir),
            "Abre el gestor de archivos en la carpeta del elemento seleccionado",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(botones, text="Enviar a la papelera", command=self.borrar),
            "Envía el archivo seleccionado a la papelera (no lo borra de inmediato)",
        ).pack(side=tk.LEFT, padx=6)
        _tema(self.root)

    def _elegir(self):
        ruta = filedialog.askdirectory(parent=self.root, initialdir=self.carpeta.get())
        if ruta:
            self.carpeta.set(ruta)

    def analizar(self):
        raiz = self.carpeta.get().strip() or os.path.expanduser("~")
        try:
            minimo = int(self.min_mb.get() or 100) * 1024 * 1024
            dias = int(self.dias.get() or 90)
        except ValueError:
            messagebox.showerror("Espacio", "MB y días deben ser números.", parent=self.root)
            return
        self.estado.config(text="Analizando...")
        self.lista.delete(0, tk.END)

        def trabajo():
            return self._recorrer(raiz, minimo, dias)

        def pintar(filas):
            self.filas = filas
            if not filas:
                self.lista.insert(tk.END, "No se encontraron archivos con esos criterios.")
                self.estado.config(text="Nada que mostrar.")
                return
            for item in filas:
                self.lista.insert(
                    tk.END,
                    f"{item['motivo']:<10} {_formato_tamano(item['tamano']):>8}  {item['fecha']}  {item['ruta']}",
                )
            total = sum(i["tamano"] for i in filas)
            self.estado.config(text=f"{len(filas)} archivos · { _formato_tamano(total) }")

        en_hilo(self.root, trabajo, al_terminar=pintar)

    def _recorrer(self, raiz, minimo, dias):
        ahora = time.time()
        limite = ahora - dias * 86400
        descargas = os.path.join(os.path.expanduser("~"), "Descargas")
        if not os.path.isdir(descargas):
            descargas = os.path.join(os.path.expanduser("~"), "Downloads")
        encontrados = []
        omitir = {".git", "proc", "sys", "dev", "run", "snap"}
        for carpeta, dirs, archivos in os.walk(raiz):
            dirs[:] = [d for d in dirs if d not in omitir and not d.startswith(".")]
            for nombre in archivos:
                ruta = os.path.join(carpeta, nombre)
                try:
                    datos = os.stat(ruta, follow_symlinks=False)
                except OSError:
                    continue
                if not stat.S_ISREG(datos.st_mode):
                    continue
                motivo = None
                baja = nombre.lower()
                if baja.endswith(".iso") or baja.endswith(".img"):
                    motivo = "ISO"
                elif datos.st_size >= minimo:
                    motivo = "Grande"
                elif ruta.startswith(descargas) and datos.st_mtime < limite:
                    motivo = "Antiguo"
                if not motivo:
                    continue
                encontrados.append({
                    "ruta": ruta,
                    "tamano": datos.st_size,
                    "fecha": datetime.fromtimestamp(datos.st_mtime).strftime("%Y-%m-%d"),
                    "motivo": motivo,
                })
            if len(encontrados) > 400:
                break
        encontrados.sort(key=lambda i: i["tamano"], reverse=True)
        return encontrados[:200]

    def _seleccion(self):
        indice = self.lista.curselection()
        if not indice or not self.filas:
            messagebox.showinfo("Espacio", "Selecciona un archivo.", parent=self.root)
            return None
        return self.filas[indice[0]]

    def abrir(self):
        item = self._seleccion()
        if not item:
            return
        subprocess.Popen(["xdg-open", os.path.dirname(item["ruta"])])

    def borrar(self):
        item = self._seleccion()
        if not item:
            return
        if not confirmar(f"¿Enviar a la papelera?\n{item['ruta']}", self.root, "Papelera"):
            return
        resultado = _comando(["gio", "trash", item["ruta"]])
        ok = resultado.returncode == 0
        registrar("Papelera (archivo grande)", item["ruta"], ok)
        if ok:
            messagebox.showinfo("Espacio", "Enviado a la papelera.", parent=self.root)
            self.analizar()
        else:
            messagebox.showerror("Espacio", resultado.stderr or "No se pudo borrar.", parent=self.root)


class HashArchivo:
    """Calcula MD5, SHA-1 y SHA-256 para comprobar descargas."""

    def __init__(self, root):
        self.root = root
        self.root.title("Hash de archivo")
        _centrar(self.root, 640, 380)
        self.ruta = tk.StringVar()
        self.esperado = tk.StringVar()
        self.md5 = tk.StringVar(value="—")
        self.sha1 = tk.StringVar(value="—")
        self.sha256 = tk.StringVar(value="—")

        tk.Label(self.root, text="Comprobar hash de un archivo", font=("Arial", 14, "bold")).pack(pady=8)
        marco = tk.Frame(self.root)
        marco.pack(fill=tk.X, padx=12)
        tk.Entry(marco, textvariable=self.ruta).pack(side=tk.LEFT, fill=tk.X, expand=True)
        con_tooltip(
            tk.Button(marco, text="Elegir", command=self._elegir),
            "Selecciona el archivo cuyo hash quieres calcular",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(marco, text="Calcular", command=self.calcular),
            "Calcula MD5, SHA-1 y SHA-256 del archivo elegido",
        ).pack(side=tk.LEFT)

        for etiqueta, variable in (("MD5", self.md5), ("SHA-1", self.sha1), ("SHA-256", self.sha256)):
            fila = tk.Frame(self.root)
            fila.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(fila, text=f"{etiqueta}:", width=10, anchor="e").pack(side=tk.LEFT)
            tk.Entry(fila, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True)
            con_tooltip(
                tk.Button(fila, text="Copiar", command=lambda v=variable: self._copiar(v.get())),
                f"Copia el hash {etiqueta} al portapapeles",
            ).pack(side=tk.LEFT, padx=4)

        tk.Label(self.root, text="Hash esperado (opcional):").pack(pady=(10, 0))
        tk.Entry(self.root, textvariable=self.esperado, width=80).pack(padx=12)
        con_tooltip(
            tk.Button(self.root, text="Comparar", command=self.comparar),
            "Compara el hash esperado con MD5, SHA-1 o SHA-256 calculados",
        ).pack(pady=8)
        self.resultado = tk.Label(self.root, text="")
        self.resultado.pack()
        _tema(self.root)

    def _elegir(self):
        ruta = filedialog.askopenfilename(parent=self.root, initialdir=os.path.expanduser("~"))
        if ruta:
            self.ruta.set(ruta)

    def _copiar(self, texto):
        if not texto or texto == "—":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.root.update()

    def calcular(self):
        ruta = self.ruta.get().strip()
        if not ruta or not os.path.isfile(ruta):
            messagebox.showinfo("Hash", "Elige un archivo.", parent=self.root)
            return
        self.resultado.config(text="Calculando...")

        def trabajo():
            try:
                md5 = hashlib.md5(usedforsecurity=False)
                sha1 = hashlib.sha1(usedforsecurity=False)
            except TypeError:
                md5 = hashlib.md5()
                sha1 = hashlib.sha1()
            sha256 = hashlib.sha256()
            with open(ruta, "rb") as archivo:
                while True:
                    bloque = archivo.read(1024 * 1024)
                    if not bloque:
                        break
                    md5.update(bloque)
                    sha1.update(bloque)
                    sha256.update(bloque)
            return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()

        def pintar(valores):
            self.md5.set(valores[0])
            self.sha1.set(valores[1])
            self.sha256.set(valores[2])
            self.resultado.config(text="Listo. Puedes copiar o comparar con el hash publicado.")

        en_hilo(self.root, trabajo, al_terminar=pintar)

    def comparar(self):
        esperado = self.esperado.get().strip().lower().replace(" ", "")
        if not esperado:
            messagebox.showinfo("Hash", "Pega el hash que te dieron con la descarga.", parent=self.root)
            return
        candidatos = {
            "MD5": self.md5.get().lower(),
            "SHA-1": self.sha1.get().lower(),
            "SHA-256": self.sha256.get().lower(),
        }
        for nombre, valor in candidatos.items():
            if valor and valor != "—" and valor == esperado:
                self.resultado.config(text=f"Coincide con {nombre}. El archivo es el esperado.")
                return
        self.resultado.config(text="No coincide con MD5, SHA-1 ni SHA-256. Revisa la descarga.")
