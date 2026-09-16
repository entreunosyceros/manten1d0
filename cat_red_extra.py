"""Wi-Fi (nmcli), DNS y edición cuidadosa de /etc/hosts."""

import os
import re
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import preferencias
from password import obtener_contrasena
from registro import confirmar, en_hilo, registrar, registrar_comando, sudo_run
from tooltip import con_tooltip

DNS_PREAJUSTES = (
    ("Router (DHCP)", "router", None),
    ("Cloudflare (1.1.1.1)", "cloudflare", "1.1.1.1 1.0.0.1"),
    ("Google (8.8.8.8)", "google", "8.8.8.8 8.8.4.4"),
)


def _centrar(ventana, ancho, alto):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def _tema(ventana):
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)


def _partir_nmcli(linea):
    partes = []
    actual = []
    escape = False
    for caracter in linea:
        if escape:
            actual.append(caracter)
            escape = False
        elif caracter == "\\":
            escape = True
        elif caracter == ":":
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(caracter)
    partes.append("".join(actual))
    return partes


def _nmcli(args, timeout=30):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(
            ["nmcli", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except FileNotFoundError:
        resultado = subprocess.CompletedProcess(["nmcli", *args], 127, "", "nmcli no está instalado")
        return resultado
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(["nmcli", *args], 1, "", str(error))


class RedesWifi:
    """Lista y conecta redes Wi-Fi con nmcli."""

    def __init__(self, root):
        self.root = root
        self.root.title("Redes Wi-Fi")
        _centrar(self.root, 640, 480)
        self.redes = []

        tk.Label(self.root, text="Redes Wi-Fi (nmcli)", font=("Arial", 14, "bold")).pack(pady=8)
        self.estado = tk.Label(self.root, text="Pulsa Actualizar para buscar redes.")
        self.estado.pack()

        self.lista = tk.Listbox(self.root, font=("monospace", 10), height=14)
        self.lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.lista.bind("<Double-Button-1>", lambda _e: self.conectar())

        marco = tk.Frame(self.root)
        marco.pack(pady=8)
        con_tooltip(
            tk.Button(marco, text="Actualizar", command=self.actualizar),
            "Busca redes Wi-Fi visibles con nmcli",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(marco, text="Conectar", command=self.conectar),
            "Conecta a la red seleccionada. La contraseña no se guarda en el registro",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(marco, text="Desconectar", command=self.desconectar),
            "Desconecta el adaptador Wi-Fi de la red actual",
        ).pack(side=tk.LEFT, padx=6)
        _tema(self.root)
        self.actualizar()

    def actualizar(self):
        self.estado.config(text="Buscando redes...")
        self.lista.delete(0, tk.END)

        def trabajo():
            _nmcli(["device", "wifi", "rescan"])
            return _nmcli(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,BSSID", "device", "wifi", "list"])

        def pintar(resultado):
            if resultado.returncode == 127:
                self.estado.config(text="nmcli no está disponible. Instala NetworkManager.")
                return
            redes = []
            vistos = set()
            for linea in resultado.stdout.splitlines():
                partes = _partir_nmcli(linea)
                if len(partes) < 5:
                    continue
                en_uso, ssid, senal, seguridad, bssid = partes[0], partes[1], partes[2], partes[3], partes[4]
                clave = ssid or bssid
                if clave in vistos:
                    continue
                vistos.add(clave)
                redes.append({
                    "ssid": ssid,
                    "senal": senal,
                    "seguridad": seguridad or "Abierta",
                    "bssid": bssid,
                    "activa": en_uso.strip() == "*",
                })
            def clave_orden(red):
                try:
                    senal = int(str(red["senal"]).strip() or 0)
                except ValueError:
                    senal = 0
                return (not red["activa"], -senal)

            redes.sort(key=clave_orden)
            self.redes = redes
            if not redes:
                self.lista.insert(tk.END, "No se encontraron redes Wi-Fi.")
                self.estado.config(text="Sin redes.")
                return
            for red in redes:
                marca = "* " if red["activa"] else "  "
                nombre = red["ssid"] or "(oculta)"
                self.lista.insert(
                    tk.END,
                    f"{marca}{nombre:<24}  {red['senal']:>3}%  {red['seguridad']:<12}  {red['bssid']}",
                )
            self.estado.config(text=f"{len(redes)} redes. Doble clic o Conectar.")

        en_hilo(self.root, trabajo, al_terminar=pintar)

    def _seleccion(self):
        indice = self.lista.curselection()
        if not indice or not self.redes:
            messagebox.showinfo("Wi-Fi", "Selecciona una red.", parent=self.root)
            return None
        return self.redes[indice[0]]

    def conectar(self):
        red = self._seleccion()
        if not red:
            return
        ssid = red["ssid"]
        if not ssid:
            messagebox.showwarning("Wi-Fi", "No se puede conectar a una red oculta desde aquí.", parent=self.root)
            return
        if not confirmar(f"¿Conectar a «{ssid}»?", self.root, "Wi-Fi"):
            return
        seguridad = (red["seguridad"] or "").upper()
        clave = None
        if seguridad and "OPEN" not in seguridad and seguridad not in ("--", "ABIERTA"):
            clave = simpledialog.askstring(
                "Wi-Fi",
                f"Contraseña para «{ssid}»:",
                show="*",
                parent=self.root,
            )
            if not clave:
                return
        args = ["device", "wifi", "connect", ssid]
        if clave:
            args.extend(["password", clave])

        def trabajo():
            resultado = _nmcli(args, timeout=45)
            if resultado.returncode == 0:
                return resultado
            contrasena = obtener_contrasena()
            entorno = os.environ.copy()
            entorno["LC_ALL"] = "C"
            return subprocess.run(
                ["sudo", "-S", "-p", "", "nmcli", "device", "wifi", "connect", ssid]
                + (["password", clave] if clave else []),
                input=f"{contrasena}\n",
                capture_output=True,
                text=True,
                timeout=45,
                env=entorno,
            )

        def terminar(resultado):
            ok = resultado is not None and resultado.returncode == 0
            if ok:
                registrar("Conectar Wi-Fi", ssid, True)
                registrar_comando("Conectar Wi-Fi", ["nmcli", "device", "wifi", "connect", ssid], sudo=False, tipo="args")
                messagebox.showinfo("Wi-Fi", f"Conectado a {ssid}.", parent=self.root)
            else:
                detalle = (resultado.stderr if resultado is not None else "error")[:300]
                registrar("Conectar Wi-Fi", f"{ssid} {detalle}", False)
                messagebox.showerror("Wi-Fi", f"No se pudo conectar:\n{detalle}", parent=self.root)
            self.actualizar()

        en_hilo(self.root, trabajo, al_terminar=terminar)

    def desconectar(self):
        def trabajo():
            activo = _nmcli(["-t", "-f", "DEVICE,TYPE", "device", "status"])
            wifi = None
            for linea in activo.stdout.splitlines():
                if ":wifi" in linea:
                    wifi = linea.split(":")[0]
                    break
            if not wifi:
                return None
            return _nmcli(["device", "disconnect", wifi])

        def terminar(resultado):
            if resultado is None:
                messagebox.showinfo("Wi-Fi", "No hay una interfaz Wi-Fi activa.", parent=self.root)
                return
            ok = resultado.returncode == 0
            registrar("Desconectar Wi-Fi", resultado.stdout or resultado.stderr, ok)
            if ok:
                messagebox.showinfo("Wi-Fi", "Wi-Fi desconectado.", parent=self.root)
            else:
                messagebox.showerror("Wi-Fi", resultado.stderr or "No se pudo desconectar.", parent=self.root)
            self.actualizar()

        if confirmar("¿Desconectar la Wi-Fi activa?", self.root, "Wi-Fi"):
            en_hilo(self.root, trabajo, al_terminar=terminar)


class EditorHosts:
    """Edita /etc/hosts con copia de seguridad y confirmación."""

    def __init__(self, root):
        self.root = root
        self.root.title("Hosts locales")
        _centrar(self.root, 700, 520)

        tk.Label(self.root, text="Archivo /etc/hosts", font=("Arial", 14, "bold")).pack(pady=8)
        tk.Label(
            self.root,
            text="Edita con cuidado. Se crea una copia en /etc/hosts.manten1d0.bak al guardar.",
            wraplength=640,
            justify=tk.CENTER,
        ).pack(padx=12)

        marco_texto = tk.Frame(self.root)
        marco_texto.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.texto = tk.Text(marco_texto, wrap=tk.NONE, font=("monospace", 11))
        barra_y = ttk.Scrollbar(marco_texto, orient="vertical", command=self.texto.yview)
        barra_x = ttk.Scrollbar(marco_texto, orient="horizontal", command=self.texto.xview)
        self.texto.configure(yscrollcommand=barra_y.set, xscrollcommand=barra_x.set)
        self.texto.grid(row=0, column=0, sticky="nsew")
        barra_y.grid(row=0, column=1, sticky="ns")
        barra_x.grid(row=1, column=0, sticky="ew")
        marco_texto.grid_rowconfigure(0, weight=1)
        marco_texto.grid_columnconfigure(0, weight=1)

        marco = tk.Frame(self.root)
        marco.pack(fill=tk.X, pady=(0, 10))
        con_tooltip(
            tk.Button(marco, text="Recargar", command=self.cargar),
            "Vuelve a leer /etc/hosts y descarta cambios no guardados",
        ).pack(side=tk.LEFT, padx=8)
        con_tooltip(
            tk.Button(marco, text="Guardar", command=self.guardar),
            "Guarda /etc/hosts con sudo y crea una copia .bak",
        ).pack(side=tk.LEFT, padx=8)
        _tema(self.root)
        self.cargar()

    def cargar(self):
        try:
            with open("/etc/hosts", encoding="utf-8") as archivo:
                contenido = archivo.read()
        except OSError as error:
            messagebox.showerror("Hosts", f"No se pudo leer /etc/hosts:\n{error}", parent=self.root)
            return
        self.texto.delete("1.0", tk.END)
        self.texto.insert("1.0", contenido)

    def _validar(self, contenido):
        if not contenido.strip():
            return "El archivo no puede quedar vacío."
        problemas = []
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            trozo = linea.strip()
            if not trozo or trozo.startswith("#"):
                continue
            partes = trozo.split()
            if len(partes) < 2:
                problemas.append(f"Línea {numero}: falta el nombre de host.")
                continue
            if not re.match(r"^[0-9a-fA-F:.]+$", partes[0]):
                problemas.append(f"Línea {numero}: «{partes[0]}» no parece una IP.")
        if problemas:
            return "Revisa estas líneas antes de guardar:\n" + "\n".join(problemas[:8])
        return None

    def guardar(self):
        contenido = self.texto.get("1.0", "end-1c")
        if not contenido.endswith("\n"):
            contenido += "\n"
        aviso = self._validar(contenido)
        if aviso:
            messagebox.showerror("Hosts", aviso, parent=self.root)
            return
        if not confirmar(
            "Se va a reemplazar /etc/hosts.\nSe guardará una copia en /etc/hosts.manten1d0.bak.\n\n¿Continuar?",
            self.root,
            "Hosts locales",
        ):
            return

        def trabajo():
            contrasena = obtener_contrasena()
            entorno = os.environ.copy()
            entorno["LC_ALL"] = "C"
            copia = subprocess.run(
                ["sudo", "-S", "-p", "", "cp", "/etc/hosts", "/etc/hosts.manten1d0.bak"],
                input=f"{contrasena}\n",
                capture_output=True,
                text=True,
                timeout=20,
                env=entorno,
            )
            if copia.returncode != 0:
                return copia
            return subprocess.run(
                ["sudo", "-S", "-p", "", "tee", "/etc/hosts"],
                input=f"{contrasena}\n{contenido}",
                capture_output=True,
                text=True,
                timeout=20,
                env=entorno,
            )

        def terminar(resultado):
            ok = resultado.returncode == 0
            registrar("Editar /etc/hosts", "tee /etc/hosts", ok)
            if ok:
                registrar_comando("Restaurar hosts (backup)", ["cp", "/etc/hosts.manten1d0.bak", "/etc/hosts"], sudo=True, tipo="args")
                messagebox.showinfo("Hosts", "Archivo /etc/hosts actualizado.", parent=self.root)
            else:
                messagebox.showerror("Hosts", resultado.stderr or "No se pudo guardar.", parent=self.root)

        en_hilo(self.root, trabajo, al_terminar=terminar)


class SelectorDns:
    """Cambia el DNS de la conexión NetworkManager activa."""

    def __init__(self, root):
        self.root = root
        self.root.title("DNS")
        _centrar(self.root, 520, 360)
        self.conexiones = []

        tk.Label(self.root, text="Servidor DNS", font=("Arial", 14, "bold")).pack(pady=8)
        self.actual = tk.Label(self.root, text="Cargando...", wraplength=480, justify=tk.CENTER)
        self.actual.pack(pady=4)

        tk.Label(self.root, text="Conexión activa:").pack()
        self.combo = ttk.Combobox(self.root, state="readonly", width=42)
        self.combo.pack(pady=6)
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_dns())

        marco = tk.Frame(self.root)
        marco.pack(pady=12)
        tips_dns = {
            "Router (DHCP)": "Vuelve al DNS automático que asigna el router",
            "Cloudflare (1.1.1.1)": "Usa los servidores DNS de Cloudflare (1.1.1.1 y 1.0.0.1)",
            "Google (8.8.8.8)": "Usa los servidores DNS de Google (8.8.8.8 y 8.8.4.4)",
        }
        for etiqueta, _clave, _dns in DNS_PREAJUSTES:
            con_tooltip(
                tk.Button(marco, text=etiqueta, width=22, command=lambda e=etiqueta: self.aplicar(e)),
                tips_dns.get(etiqueta, "Aplica este servidor DNS a la conexión activa"),
            ).pack(pady=4)

        con_tooltip(
            tk.Button(self.root, text="Actualizar", command=self.cargar),
            "Vuelve a leer la conexión activa y el DNS actual",
        ).pack(pady=8)
        _tema(self.root)
        self.cargar()

    def cargar(self):
        resultado = _nmcli(["-t", "-f", "NAME,UUID,TYPE,DEVICE", "connection", "show", "--active"])
        conexiones = []
        for linea in resultado.stdout.splitlines():
            partes = linea.split(":")
            if len(partes) < 4:
                continue
            nombre, uuid, tipo, dispositivo = partes[0], partes[1], partes[2], partes[3]
            if tipo in ("loopback", "bridge"):
                continue
            conexiones.append({"nombre": nombre, "uuid": uuid, "tipo": tipo, "dispositivo": dispositivo})
        self.conexiones = conexiones
        self.combo["values"] = [f"{c['nombre']} ({c['dispositivo'] or c['tipo']})" for c in conexiones]
        if conexiones:
            self.combo.current(0)
        self._mostrar_dns()

    def _seleccion(self):
        indice = self.combo.current()
        if indice < 0 or indice >= len(self.conexiones):
            return None
        return self.conexiones[indice]

    def _mostrar_dns(self):
        conexion = self._seleccion()
        if not conexion:
            self.actual.config(text="No hay una conexión NetworkManager activa.")
            return
        dns = _nmcli(["-g", "IP4.DNS", "connection", "show", conexion["uuid"]])
        valores = ", ".join(x for x in dns.stdout.strip().split("\n") if x) or "automático (router / DHCP)"
        self.actual.config(text=f"DNS actual: {valores}")

    def aplicar(self, etiqueta):
        conexion = self._seleccion()
        if not conexion:
            messagebox.showinfo("DNS", "No hay conexión activa para cambiar el DNS.", parent=self.root)
            return
        preajuste = next((item for item in DNS_PREAJUSTES if item[0] == etiqueta), None)
        if not preajuste:
            return
        _nombre, clave, servidores = preajuste
        if clave == "router":
            mensaje = f"¿Usar el DNS automático del router en «{conexion['nombre']}»?"
            args = ["connection", "modify", conexion["uuid"], "ipv4.ignore-auto-dns", "no", "ipv4.dns", ""]
        else:
            mensaje = f"¿Cambiar el DNS de «{conexion['nombre']}» a {servidores}?"
            args = ["connection", "modify", conexion["uuid"], "ipv4.ignore-auto-dns", "yes", "ipv4.dns", servidores]
        if not confirmar(mensaje, self.root, "DNS"):
            return

        def trabajo():
            modificado = sudo_run(["nmcli", *args], f"DNS {etiqueta}", parent=None, confirmar_accion=False)
            if modificado is None or modificado.returncode != 0:
                return modificado
            return sudo_run(
                ["nmcli", "connection", "up", conexion["uuid"]],
                f"Reactivar {conexion['nombre']}",
                parent=None,
                confirmar_accion=False,
            )

        def terminar(resultado):
            ok = resultado is not None and resultado.returncode == 0
            if ok:
                messagebox.showinfo("DNS", f"DNS cambiado: {etiqueta}.", parent=self.root)
            else:
                detalle = (resultado.stderr if resultado is not None else "cancelado")[:300]
                messagebox.showerror("DNS", f"No se pudo cambiar el DNS:\n{detalle}", parent=self.root)
            self.cargar()

        en_hilo(self.root, trabajo, al_terminar=terminar)
