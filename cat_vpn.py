"""Panel de ExpressVPN: estado, conexión y ajustes del cliente instalado."""

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import preferencias
from registro import confirmar, en_hilo, registrar, registrar_comando
from tooltip import con_tooltip


RUTA_CTL = "/opt/expressvpn/bin/expressvpnctl"

PROTOCOLOS = (
    ("auto", "Automático"),
    ("lightwayudp", "Lightway UDP"),
    ("lightwaytcp", "Lightway TCP"),
    ("openvpnudp", "OpenVPN UDP"),
    ("openvpntcp", "OpenVPN TCP"),
)

_ESTADOS = {
    "Connected": "Conectada",
    "Disconnected": "Desconectada",
    "Connecting": "Conectando",
    "Interrupted": "Interrumpida",
    "Reconnecting": "Reconectando",
    "DisconnectingToReconnect": "Reconectando",
    "Disconnecting": "Desconectando",
}

_INTERRUPTORES = (
    ("networklock", "Bloqueo de red (Network Lock)", "Impide salir a Internet si la VPN se cae"),
    ("allowlan", "Permitir red local", "Deja acceder a impresoras y equipos de tu red mientras la VPN está activa"),
    ("autoconnect", "Conectar al arrancar", "Conecta la VPN al iniciar el sistema"),
    ("splittunnel", "Túnel dividido", "Permite que algunas aplicaciones no pasen por la VPN"),
)


def ruta_expressvpnctl():
    if os.path.isfile(RUTA_CTL) and os.access(RUTA_CTL, os.X_OK):
        return RUTA_CTL
    return shutil.which("expressvpnctl")


def expressvpn_disponible():
    return ruta_expressvpnctl() is not None


def _interfaces_tunel():
    """Nombres de interfaces típicas de VPN que están arriba y tienen IPv4."""
    encontradas = []
    try:
        proceso = subprocess.run(
            ["ip", "-o", "-4", "addr", "show", "up"],
            capture_output=True,
            text=True,
            timeout=3,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return encontradas
    for linea in proceso.stdout.splitlines():
        partes = linea.split()
        if len(partes) < 2:
            continue
        nombre = partes[1]
        bajo = nombre.lower()
        if bajo.startswith(("tun", "tap", "wg", "zt", "nordlynx", "ppp")) or "vpn" in bajo:
            encontradas.append(nombre)
    return encontradas


def vpn_en_uso():
    """
    Detecta si el equipo usa una VPN ahora mismo.

    Returns:
        tuple: (activa: bool, texto_corto: str, detalle_tooltip: str)
    """
    if expressvpn_disponible():
        resultado = _ctl(["get", "connectionstate"], timeout=4)
        if resultado.returncode == 0:
            estado = (resultado.stdout or "").strip()
            if estado == "Connected":
                return (
                    True,
                    "VPN: sí (ExpressVPN)",
                    "ExpressVPN está conectada. La IP pública suele ser la del túnel",
                )
            if estado in (
                "Connecting",
                "Reconnecting",
                "DisconnectingToReconnect",
                "Interrupted",
            ):
                etiqueta = _ESTADOS.get(estado, estado)
                return (
                    True,
                    f"VPN: {etiqueta.lower()}",
                    f"ExpressVPN está en estado «{etiqueta}»",
                )

    tuneles = _interfaces_tunel()
    if tuneles:
        lista = ", ".join(tuneles[:3])
        return (
            True,
            "VPN: sí",
            f"Hay un túnel de red activo ({lista}). Puede ser una VPN u otro programa similar",
        )

    return (
        False,
        "VPN: no",
        "No se detecta una VPN activa (ni ExpressVPN conectada ni túnel típico)",
    )


def _centrar(ventana, ancho, alto):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def _tema(ventana):
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)


def _ctl(args, timeout=30):
    ruta = ruta_expressvpnctl()
    if not ruta:
        return subprocess.CompletedProcess(
            ["expressvpnctl", *args], 127, "", "expressvpnctl no está instalado"
        )
    try:
        return subprocess.run(
            [ruta, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            [ruta, *args], 1, "", "Tiempo de espera agotado."
        )


def _detalle(proceso):
    texto = ((proceso.stderr or "") + "\n" + (proceso.stdout or "")).strip()
    return texto[:400] or "El cliente no respondió."


def _nombre_protocolo(codigo):
    for clave, etiqueta in PROTOCOLOS:
        if clave == codigo:
            return etiqueta
    return codigo or "-"


class PanelExpressVPN:
    """Consulta y cambia la VPN de ExpressVPN si el cliente está instalado."""

    def __init__(self, root):
        self.root = root
        self.root.title("ExpressVPN")
        _centrar(self.root, 560, 640)
        self._cargando = False
        self._ocupado = False
        self._datos = {}
        self._regiones = []
        self._vars = {}
        self._botones = []
        self._casillas = []

        tk.Label(self.root, text="ExpressVPN", font=("Arial", 14, "bold")).pack(pady=(10, 4))
        self.estado = tk.Label(self.root, text="Leyendo el cliente...", wraplength=500, justify=tk.CENTER)
        self.estado.pack(pady=4)
        self.detalle = tk.Label(self.root, text="", wraplength=500, justify=tk.CENTER)
        self.detalle.pack(pady=(0, 8))

        marco_listas = tk.Frame(self.root)
        marco_listas.pack(fill=tk.X, padx=16, pady=4)
        tk.Label(marco_listas, text="Región").grid(row=0, column=0, sticky="w")
        self.combo_region = ttk.Combobox(marco_listas, state="readonly", width=36)
        self.combo_region.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)
        self.combo_region.bind("<<ComboboxSelected>>", self._al_cambiar_region)
        tk.Label(marco_listas, text="Protocolo").grid(row=1, column=0, sticky="w")
        self.combo_protocolo = ttk.Combobox(marco_listas, state="readonly", width=36)
        self.combo_protocolo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)
        self.combo_protocolo["values"] = [etiqueta for _codigo, etiqueta in PROTOCOLOS]
        self.combo_protocolo.bind("<<ComboboxSelected>>", self._al_cambiar_protocolo)
        marco_listas.columnconfigure(1, weight=1)

        marco_checks = tk.Frame(self.root)
        marco_checks.pack(fill=tk.X, padx=16, pady=8)
        for clave, titulo, ayuda in _INTERRUPTORES:
            variable = tk.BooleanVar(value=False)
            self._vars[clave] = variable
            casilla = tk.Checkbutton(
                marco_checks,
                text=titulo,
                variable=variable,
                command=lambda c=clave, t=titulo: self._al_interruptor(c, t),
                anchor="w",
            )
            casilla.pack(fill=tk.X, pady=2)
            con_tooltip(casilla, ayuda)
            self._casillas.append(casilla)

        aviso = tk.Label(
            self.root,
            text="La sesión se inicia y se cierra en la aplicación de ExpressVPN.",
            wraplength=500,
            justify=tk.CENTER,
            font=("Arial", 9),
        )
        aviso.pack(pady=(4, 8))

        marco = tk.Frame(self.root)
        marco.pack(pady=8)
        self._botones.append(con_tooltip(
            tk.Button(marco, text="Conectar", width=14, command=self.conectar),
            "Conecta a la región elegida. Si ya está conectada, vuelve a conectar para aplicar los cambios",
        ))
        self._botones.append(con_tooltip(
            tk.Button(marco, text="Desconectar", width=14, command=self.desconectar),
            "Cierra el túnel de ExpressVPN",
        ))
        self._botones.append(con_tooltip(
            tk.Button(marco, text="Actualizar", width=14, command=self.actualizar),
            "Vuelve a leer el estado y los ajustes del cliente",
        ))
        for boton in self._botones:
            boton.pack(side=tk.LEFT, padx=6)

        _tema(self.root)
        self.actualizar()

    def _conectado(self):
        return self._datos.get("connectionstate") == "Connected"

    def _bloquear(self, ocupado):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for boton in self._botones:
            boton.config(state=estado)
        combo = "disabled" if ocupado else "readonly"
        self.combo_region.config(state=combo)
        self.combo_protocolo.config(state=combo)
        for casilla in self._casillas:
            casilla.config(state=estado)

    def actualizar(self):
        if self._ocupado:
            return
        self._bloquear(True)
        self.estado.config(text="Leyendo el cliente...")

        def trabajo():
            datos = {}
            claves = (
                "connectionstate", "region", "protocol", "vpnip", "pubip",
                "networklock", "allowlan", "autoconnect", "splittunnel",
            )
            for clave in claves:
                resultado = _ctl(["get", clave], timeout=15)
                if resultado.returncode != 0:
                    return {"error": _detalle(resultado)}
                datos[clave] = (resultado.stdout or "").strip()
            if not self._regiones:
                regiones = _ctl(["get", "regions"], timeout=30)
                if regiones.returncode != 0:
                    return {"error": _detalle(regiones)}
                datos["regiones"] = [linea.strip() for linea in regiones.stdout.splitlines() if linea.strip()]
            return datos

        def pintar(datos):
            self._bloquear(False)
            if not self.root.winfo_exists():
                return
            if datos.get("error"):
                self._datos = {}
                self.estado.config(
                    text="No se pudo hablar con ExpressVPN.\n"
                    "Abre el cliente o activa el modo en segundo plano."
                )
                self.detalle.config(text=datos["error"])
                return
            if datos.get("regiones"):
                self._regiones = datos["regiones"]
            self._datos = datos
            self._pintar()

        en_hilo(self.root, trabajo, al_terminar=pintar, al_error=self._error_hilo)

    def _error_hilo(self, error):
        self._bloquear(False)
        if self.root.winfo_exists():
            self.estado.config(text="No se pudo hablar con ExpressVPN.")
            messagebox.showerror("ExpressVPN", str(error), parent=self.root)

    def _pintar(self):
        self._cargando = True
        try:
            estado = _ESTADOS.get(self._datos.get("connectionstate"), self._datos.get("connectionstate") or "-")
            self.estado.config(text=f"Estado: {estado}")
            protocolo = _nombre_protocolo(self._datos.get("protocol"))
            self.detalle.config(
                text=(
                    f"Región: {self._datos.get('region') or '-'}"
                    f" | Protocolo: {protocolo}\n"
                    f"IP de la VPN: {self._datos.get('vpnip') or '-'}"
                    f" | IP pública: {self._datos.get('pubip') or '-'}"
                )
            )
            regiones = list(self._regiones)
            actual = self._datos.get("region")
            if actual and actual not in regiones:
                regiones.insert(0, actual)
            self.combo_region["values"] = regiones
            if actual in regiones:
                self.combo_region.current(regiones.index(actual))
            etiquetas = [etiqueta for _codigo, etiqueta in PROTOCOLOS]
            codigo = self._datos.get("protocol")
            if codigo and codigo not in {c for c, _e in PROTOCOLOS}:
                etiquetas.append(codigo)
            self.combo_protocolo["values"] = etiquetas
            nombre = _nombre_protocolo(codigo)
            if nombre in etiquetas:
                self.combo_protocolo.current(etiquetas.index(nombre))
            for clave, _titulo, _ayuda in _INTERRUPTORES:
                self._vars[clave].set(self._datos.get(clave, "").lower() == "true")
        finally:
            self._cargando = False

    def _codigo_protocolo(self, etiqueta):
        for codigo, nombre in PROTOCOLOS:
            if nombre == etiqueta or codigo == etiqueta:
                return codigo
        return etiqueta

    def _restaurar_region(self):
        self._cargando = True
        try:
            actual = self._datos.get("region")
            valores = list(self.combo_region["values"])
            if actual in valores:
                self.combo_region.current(valores.index(actual))
        finally:
            self._cargando = False

    def _restaurar_protocolo(self):
        self._cargando = True
        try:
            nombre = _nombre_protocolo(self._datos.get("protocol"))
            valores = list(self.combo_protocolo["values"])
            if nombre in valores:
                self.combo_protocolo.current(valores.index(nombre))
        finally:
            self._cargando = False

    def _al_cambiar_region(self, _event=None):
        if self._cargando or self._ocupado:
            return
        region = self.combo_region.get().strip()
        if not region or region == self._datos.get("region"):
            return
        if not confirmar(f"¿Usar la región «{region}»?", self.root, "ExpressVPN"):
            self._restaurar_region()
            return
        self._aplicar_region_o_protocolo("region", region, region)

    def _al_cambiar_protocolo(self, _event=None):
        if self._cargando or self._ocupado:
            return
        etiqueta = self.combo_protocolo.get().strip()
        codigo = self._codigo_protocolo(etiqueta)
        if not codigo or codigo == self._datos.get("protocol"):
            return
        if not confirmar(f"¿Usar el protocolo {etiqueta}?", self.root, "ExpressVPN"):
            self._restaurar_protocolo()
            return
        self._aplicar_region_o_protocolo("protocol", codigo, etiqueta)

    def _aplicar_region_o_protocolo(self, clave, valor, visible):
        conectada = self._conectado()
        if conectada and not confirmar(
            "La VPN está conectada. ¿Reconectar para aplicar el cambio?",
            self.root,
            "ExpressVPN",
        ):
            if clave == "region":
                self._restaurar_region()
            else:
                self._restaurar_protocolo()
            return

        def trabajo():
            cambio = _ctl(["set", clave, valor], timeout=30)
            if cambio.returncode != 0 or not conectada:
                return cambio
            if clave == "region":
                return _ctl(["connect", valor], timeout=90)
            return _ctl(["connect"], timeout=90)

        def terminar(resultado):
            self._bloquear(False)
            ok = resultado.returncode == 0
            registrar(f"ExpressVPN {clave}", visible, ok)
            if ok:
                registrar_comando(
                    f"ExpressVPN {clave}",
                    ["expressvpnctl", "set", clave, valor],
                    sudo=False,
                    tipo="args",
                )
            else:
                messagebox.showerror("ExpressVPN", _detalle(resultado), parent=self.root)
            self.actualizar()

        self._bloquear(True)
        en_hilo(self.root, trabajo, al_terminar=terminar, al_error=self._error_hilo)

    def _al_interruptor(self, clave, titulo):
        if self._cargando or self._ocupado:
            return
        nuevo = self._vars[clave].get()
        previo = self._datos.get(clave, "").lower() == "true"
        if nuevo == previo:
            return
        accion = "activar" if nuevo else "desactivar"
        if not confirmar(f"¿{accion.capitalize()} «{titulo}»?", self.root, "ExpressVPN"):
            self._cargando = True
            self._vars[clave].set(previo)
            self._cargando = False
            return
        valor = "true" if nuevo else "false"

        def trabajo():
            return _ctl(["set", clave, valor], timeout=30)

        def terminar(resultado):
            self._bloquear(False)
            ok = resultado.returncode == 0
            registrar(f"ExpressVPN {titulo}", valor, ok)
            if ok:
                registrar_comando(
                    f"ExpressVPN {titulo}",
                    ["expressvpnctl", "set", clave, valor],
                    sudo=False,
                    tipo="args",
                )
            else:
                messagebox.showerror("ExpressVPN", _detalle(resultado), parent=self.root)
            self.actualizar()

        self._bloquear(True)
        en_hilo(self.root, trabajo, al_terminar=terminar, al_error=self._error_hilo)

    def conectar(self):
        if self._ocupado:
            return
        region = self.combo_region.get().strip() or self._datos.get("region") or "smart"
        verbo = "Reconectar" if self._conectado() else "Conectar"
        if not confirmar(f"¿{verbo} ExpressVPN a «{region}»?", self.root, "ExpressVPN"):
            return

        def trabajo():
            return _ctl(["connect", region], timeout=90)

        def terminar(resultado):
            self._bloquear(False)
            ok = resultado.returncode == 0
            registrar("ExpressVPN conectar", region, ok)
            if ok:
                registrar_comando(
                    "Conectar ExpressVPN",
                    ["expressvpnctl", "connect", region],
                    sudo=False,
                    tipo="args",
                )
                messagebox.showinfo("ExpressVPN", f"Conectada a {region}.", parent=self.root)
            else:
                messagebox.showerror("ExpressVPN", _detalle(resultado), parent=self.root)
            self.actualizar()

        self._bloquear(True)
        en_hilo(self.root, trabajo, al_terminar=terminar, al_error=self._error_hilo)

    def desconectar(self):
        if self._ocupado:
            return
        if not confirmar("¿Desconectar ExpressVPN?", self.root, "ExpressVPN"):
            return

        def trabajo():
            return _ctl(["disconnect"], timeout=60)

        def terminar(resultado):
            self._bloquear(False)
            ok = resultado.returncode == 0
            registrar("ExpressVPN desconectar", "", ok)
            if ok:
                registrar_comando(
                    "Desconectar ExpressVPN",
                    ["expressvpnctl", "disconnect"],
                    sudo=False,
                    tipo="args",
                )
                messagebox.showinfo("ExpressVPN", "VPN desconectada.", parent=self.root)
            else:
                messagebox.showerror("ExpressVPN", _detalle(resultado), parent=self.root)
            self.actualizar()

        self._bloquear(True)
        en_hilo(self.root, trabajo, al_terminar=terminar, al_error=self._error_hilo)
