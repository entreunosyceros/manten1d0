"""Descubrimiento de dispositivos en la red local, carpetas compartidas, router y encendido por red."""

import json
import webbrowser
import os
import re
import socket
import subprocess
import threading
from datetime import date

import psutil
import tkinter as tk
from tkinter import filedialog, messagebox

import preferencias
from cat_informacion import Informacion
from registro import confirmar, en_hilo, registrar, sudo_run
from tooltip import con_tooltip


def _cargar_nmap():
    import importlib

    importlib.invalidate_caches()
    import nmap
    return nmap


def obtener_red_local():
    for _interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                return f"{addr.address}/{netmask_to_cidr(addr.netmask)}"
    return None


def netmask_to_cidr(netmask):
    return sum(bin(int(x)).count("1") for x in netmask.split("."))


def _tabla_arp():
    tabla = {}
    try:
        with open("/proc/net/arp", encoding="utf-8") as archivo:
            next(archivo)
            for linea in archivo:
                partes = linea.split()
                if len(partes) >= 4 and partes[3] != "00:00:00:00:00:00":
                    tabla[partes[0]] = partes[3]
    except OSError:
        pass
    return tabla


def _resolver_nombre(ip):
    try:
        nombre = socket.getfqdn(ip)
        if nombre and nombre != ip:
            return nombre
    except OSError:
        pass
    return "—"


def _ordenar_ip(ip):
    try:
        return tuple(int(octeto) for octeto in ip.split("."))
    except ValueError:
        return (999, 999, 999, 999)


def encontrar_dispositivos_en_red():
    try:
        nmap = _cargar_nmap()
    except ImportError as error:
        raise RuntimeError(
            "Falta el módulo nmap en el Python que ejecuta Manten1d0."
        ) from error
    red = obtener_red_local()
    if not red:
        return []
    escaner = nmap.PortScanner()
    escaner.scan(hosts=red, arguments="-sn")
    hosts = list(escaner.all_hosts())
    if not hosts:
        return []

    samba = set()
    try:
        puertos = nmap.PortScanner()
        puertos.scan(
            hosts=" ".join(hosts),
            arguments="-p 139,445 --open --max-retries 1 --host-timeout 4s",
        )
        for host in puertos.all_hosts():
            tcp = puertos[host].get("tcp") or {}
            if any(tcp.get(puerto, {}).get("state") == "open" for puerto in (139, 445)):
                samba.add(host)
    except Exception:
        pass

    arp = _tabla_arp()
    dispositivos = []
    for host in hosts:
        info = escaner[host]
        nombre = info.hostname() or _resolver_nombre(host)
        mac = (info.get("addresses") or {}).get("mac") or arp.get(host) or "—"
        dispositivos.append({
            "ip": host,
            "nombre": nombre or "—",
            "mac": mac,
            "samba": host in samba,
        })
    dispositivos.sort(key=lambda item: _ordenar_ip(item["ip"]))
    return dispositivos


def formatear_dispositivo(item):
    samba = "Samba: sí" if item.get("samba") else "Samba: no"
    return f"{item['ip']:<16} {item.get('nombre') or '—':<22} {item.get('mac') or '—':<18} {samba}"


def ip_de_linea(texto, lista=None):
    if lista is not None:
        seleccion = lista.curselection()
        dispositivos = getattr(lista, "dispositivos", None)
        if dispositivos and seleccion:
            return dispositivos[seleccion[0]]["ip"]
    return (texto or "").split()[0]


def abrir_administrador_de_archivos(ip):
    try:
        subprocess.Popen(["nautilus", f"smb://{ip}"])
    except FileNotFoundError:
        messagebox.showerror("Error", "Administrador de archivos no encontrado.")
    except Exception as e:
        messagebox.showerror("Error", f"Error al abrir el administrador de archivos: {e}")


def doble_clic(_, lista_dispositivos):
    ip = ip_de_linea(lista_dispositivos.get(tk.ACTIVE), lista_dispositivos)
    if not ip:
        return
    threading.Thread(target=abrir_administrador_de_archivos, args=(ip,), daemon=True).start()


def _ruta_equipos():
    carpeta = os.path.join(os.path.expanduser("~"), ".config", "manten1d0")
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, "equipos-red.json")


def _leer_equipos():
    try:
        with open(_ruta_equipos(), encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return datos


def recordar_equipos(dispositivos):
    """Guarda nombre y MAC de los equipos vistos, para poder encenderlos después."""
    if not dispositivos:
        return
    guardados = _leer_equipos()
    hoy = date.today().isoformat()
    for item in dispositivos:
        if not isinstance(item, dict):
            continue
        mac = (item.get("mac") or "").strip().lower().replace("-", ":")
        if not re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
            continue
        if mac == "00:00:00:00:00:00":
            continue
        previo = guardados.get(mac) or {}
        guardados[mac] = {
            "nombre": item.get("nombre") or previo.get("nombre") or "PC",
            "ip": item.get("ip") or previo.get("ip") or "",
            "visto": hoy,
        }
    with open(_ruta_equipos(), "w", encoding="utf-8") as archivo:
        json.dump(guardados, archivo, ensure_ascii=False, indent=2)


def _normalizar_mac(texto):
    mac = (texto or "").strip().lower().replace("-", ":")
    if not re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
        return ""
    return mac


def _paquete_encendido(mac):
    octetos = bytes.fromhex(mac.replace(":", ""))
    return b"\xff" * 6 + octetos * 16


def _destinos_encendido():
    destinos = ["255.255.255.255"]
    for interfaz, direcciones in psutil.net_if_addrs().items():
        if interfaz == "lo" or interfaz.startswith(("docker", "br-", "virbr", "veth", "tun", "tap", "wg", "zt")):
            continue
        ip = mascara = None
        for direccion in direcciones:
            if direccion.family == socket.AF_INET and not direccion.address.startswith("127."):
                ip = direccion.address
                mascara = direccion.netmask
        if not ip or not mascara:
            continue
        try:
            import ipaddress
            red = ipaddress.IPv4Interface(f"{ip}/{mascara}").network
            destinos.append(str(red.broadcast_address))
        except ValueError:
            continue
    unicos = []
    for destino in destinos:
        if destino not in unicos:
            unicos.append(destino)
    return unicos


def enviar_encendido(mac):
    paquete = _paquete_encendido(mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for destino in _destinos_encendido():
            for puerto in (9, 7):
                sock.sendto(paquete, (destino, puerto))
    finally:
        sock.close()


def _centrar(ventana, ancho, alto):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def _tema(ventana):
    if preferencias.tema_seleccionado != "Claro":
        preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)


def _ufw_activo():
    try:
        with open("/etc/ufw/ufw.conf", encoding="utf-8", errors="replace") as archivo:
            for linea in archivo:
                if linea.strip().startswith("ENABLED="):
                    return linea.split("=", 1)[1].strip().strip('"').lower() == "yes"
    except OSError:
        return False
    return False


def _nombre_recurso(texto):
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "-", (texto or "").strip()).strip("-")
    return (limpio or "carpeta")[:40]


def _listar_recursos():
    proceso = subprocess.run(["net", "usershare", "info"], capture_output=True, text=True, timeout=15)
    recursos = []
    actual = None
    for linea in (proceso.stdout or "").splitlines():
        if linea.startswith("[") and linea.endswith("]"):
            if actual:
                recursos.append(actual)
            actual = {"nombre": linea[1:-1], "ruta": "", "acceso": ""}
            continue
        if actual is None or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        if clave.strip() == "path":
            actual["ruta"] = valor.strip()
        elif clave.strip() == "usershare_acl":
            actual["acceso"] = "puede cambiar archivos" if ":F" in valor.upper() else "solo ver"
    if actual:
        recursos.append(actual)
    return recursos


class CompartirCarpeta:
    """Comparte una carpeta de tu usuario para que otro equipo de casa la vea."""

    def __init__(self, root):
        self.root = root
        self.root.title("Compartir Una Carpeta")
        self.root.minsize(560, 460)
        _centrar(self.root, 620, 520)
        self.ruta = tk.StringVar()
        self.nombre = tk.StringVar()
        self.acceso = tk.StringVar(value="ver")
        self._ocupado = False

        tk.Label(self.root, text="Compartir Una Carpeta", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Otro equipo de tu red podrá ver esta carpeta. "
                "No hace falta contraseña: cualquiera en casa puede abrirla."
            ),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(padx=16, pady=(0, 8))

        marco_ruta = tk.Frame(self.root)
        marco_ruta.pack(fill=tk.X, padx=16, pady=4)
        tk.Entry(marco_ruta, textvariable=self.ruta).pack(side=tk.LEFT, fill=tk.X, expand=True)
        boton_elegir = tk.Button(marco_ruta, text="Elegir", command=self._elegir)
        boton_elegir.pack(side=tk.LEFT, padx=(6, 0))
        con_tooltip(boton_elegir, "Elige la carpeta que verá el otro equipo")

        marco_nombre = tk.Frame(self.root)
        marco_nombre.pack(fill=tk.X, padx=16, pady=4)
        tk.Label(marco_nombre, text="Nombre").pack(side=tk.LEFT)
        tk.Entry(marco_nombre, textvariable=self.nombre, width=28).pack(side=tk.LEFT, padx=8)
        tk.Radiobutton(self.root, text="Solo ver", variable=self.acceso, value="ver").pack(anchor="w", padx=16)
        tk.Radiobutton(
            self.root, text="Ver y cambiar archivos", variable=self.acceso, value="cambiar",
        ).pack(anchor="w", padx=16)

        marco = tk.Frame(self.root)
        marco.pack(pady=8)
        self.btn_compartir = tk.Button(marco, text="Compartir", command=self.compartir)
        self.btn_compartir.pack(side=tk.LEFT, padx=6)
        con_tooltip(self.btn_compartir, "Hace visible la carpeta para los otros equipos de casa")
        self.btn_quitar = tk.Button(marco, text="Dejar de compartir", command=self.quitar)
        self.btn_quitar.pack(side=tk.LEFT, padx=6)
        con_tooltip(self.btn_quitar, "El otro equipo dejará de ver la carpeta seleccionada")

        self.lista = tk.Listbox(self.root, height=8)
        self.lista.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 8))
        self.lbl_estado = tk.Label(self.root, text="", wraplength=560, justify=tk.LEFT)
        self.lbl_estado.pack(fill=tk.X, padx=16, pady=(0, 10))
        self.recursos = []
        _tema(self.root)
        self._pintar_lista()

    def _elegir(self):
        ruta = filedialog.askdirectory(
            title="Carpeta para compartir",
            initialdir=os.path.expanduser("~"),
            parent=self.root,
        )
        if not ruta:
            return
        self.ruta.set(ruta)
        if not self.nombre.get().strip():
            self.nombre.set(_nombre_recurso(os.path.basename(ruta)))

    def _pintar_lista(self):
        self.recursos = _listar_recursos()
        self.lista.delete(0, tk.END)
        if not self.recursos:
            self.lista.insert(tk.END, "Todavía no compartes ninguna carpeta.")
            return
        for recurso in self.recursos:
            self.lista.insert(tk.END, f"{recurso['nombre']}  —  {recurso['acceso']}  —  {recurso['ruta']}")

    def compartir(self):
        if self._ocupado:
            return
        ruta = os.path.realpath(self.ruta.get().strip())
        home = os.path.realpath(os.path.expanduser("~"))
        if not ruta or not os.path.isdir(ruta):
            messagebox.showinfo("Compartir Una Carpeta", "Elige una carpeta.", parent=self.root)
            return
        if ruta != home and not ruta.startswith(home + os.sep):
            messagebox.showinfo(
                "Compartir Una Carpeta",
                "Elige una carpeta de tu usuario, no una del sistema.",
                parent=self.root,
            )
            return
        nombre = _nombre_recurso(self.nombre.get() or os.path.basename(ruta))
        self.nombre.set(nombre)
        grupos = subprocess.run(["id", "-nG"], capture_output=True, text=True)
        if "sambashare" not in (grupos.stdout or "").split():
            if confirmar(
                "Tu usuario todavía no puede compartir carpetas.\n\n"
                "¿Añadirlo ahora? Después hay que cerrar la sesión para que funcione.",
                self.root,
                "Compartir Una Carpeta",
            ):
                usuario = os.environ.get("USER") or os.path.basename(home)

                def fin_grupo(resultado):
                    if resultado is not None and resultado.returncode == 0:
                        messagebox.showinfo(
                            "Compartir Una Carpeta",
                            "Listo. Cierra la sesión y vuelve a entrar para poder compartir.",
                            parent=self.root,
                        )

                en_hilo(
                    self.root,
                    lambda: sudo_run(
                        ["usermod", "-aG", "sambashare", usuario],
                        "Permitir compartir carpetas",
                        timeout=40,
                    ),
                    al_terminar=fin_grupo,
                )
            return
        cambiar = self.acceso.get() == "cambiar"
        permiso = "ver y cambiar" if cambiar else "solo ver"
        if not confirmar(
            f"La carpeta\n{ruta}\nse verá en la red con el nombre {nombre}.\n\n"
            f"Cualquier equipo de casa podrá {permiso}. "
            "Para eso se permite leer esa carpeta.\n\n"
            "¿Quieres compartirla?",
            self.root,
            "Compartir Una Carpeta",
        ):
            return
        self._ocupado = True
        self.btn_compartir.config(state=tk.DISABLED)

        def trabajo():
            if subprocess.run(["systemctl", "is-active", "--quiet", "smbd"]).returncode != 0:
                arranque = sudo_run(["systemctl", "start", "smbd"], "Arrancar el uso compartido", timeout=40)
                if arranque is None or arranque.returncode != 0:
                    raise RuntimeError("No se pudo preparar el uso compartido de carpetas.")
            modo = "a+rwX" if cambiar else "a+rX"
            permiso_local = subprocess.run(["chmod", "-R", modo, ruta], capture_output=True, text=True)
            if permiso_local.returncode != 0:
                raise RuntimeError((permiso_local.stderr or "No se pudo permitir el acceso a la carpeta.").strip())
            acl = "Everyone:f" if cambiar else "Everyone:r"
            alta = subprocess.run(
                ["net", "usershare", "add", nombre, ruta, "Compartida desde Manten1d0", acl, "guest_ok=y"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if alta.returncode != 0:
                raise RuntimeError((alta.stderr or alta.stdout or "No se pudo compartir la carpeta.").strip())
            return nombre

        def fin(nombre_recurso):
            self._ocupado = False
            if not self.root.winfo_exists():
                return
            self.btn_compartir.config(state=tk.NORMAL)
            ip = Informacion.obtener_direccion_ip_local() or "la IP de este equipo"
            registrar("Compartir carpeta", f"{nombre_recurso} -> {ruta}", True)
            self._pintar_lista()
            self.lbl_estado.config(text=f"En el otro equipo, abre smb://{ip}/{nombre_recurso}")
            if _ufw_activo() and confirmar(
                "El cortafuegos está activado. Para que el otro equipo vea la carpeta, "
                "hay que permitir Samba.\n\n¿Quieres permitirlo?",
                self.root,
                "Permitir Samba",
            ):
                def abrir_samba():
                    return sudo_run(["ufw", "allow", "samba"], "Permitir carpetas compartidas", timeout=40)

                def tras_ufw(resultado):
                    if resultado is not None and resultado.returncode == 0:
                        self.lbl_estado.config(text=self.lbl_estado.cget("text") + "  ·  Samba permitido en el cortafuegos.")

                en_hilo(self.root, abrir_samba, al_terminar=tras_ufw)
            messagebox.showinfo(
                "Compartir Una Carpeta",
                f"Listo. En el otro equipo abre:\nsmb://{ip}/{nombre_recurso}",
                parent=self.root,
            )

        def error(exc):
            self._ocupado = False
            if self.root.winfo_exists():
                self.btn_compartir.config(state=tk.NORMAL)
            registrar("Compartir carpeta", str(exc), False)
            messagebox.showerror("Compartir Una Carpeta", str(exc), parent=self.root)

        en_hilo(self.root, trabajo, al_terminar=fin, al_error=error)

    def quitar(self):
        indice = self.lista.curselection()
        if not self.recursos or not indice or indice[0] >= len(self.recursos):
            messagebox.showinfo("Compartir Una Carpeta", "Elige una carpeta de la lista.", parent=self.root)
            return
        recurso = self.recursos[indice[0]]
        if not confirmar(
            f"El otro equipo dejará de ver {recurso['nombre']}.\n\n¿Quieres dejar de compartirla?",
            self.root,
            "Dejar De Compartir",
        ):
            return
        proceso = subprocess.run(
            ["net", "usershare", "delete", recurso["nombre"]],
            capture_output=True,
            text=True,
            timeout=15,
        )
        ok = proceso.returncode == 0
        registrar("Dejar de compartir", recurso["nombre"], ok)
        if not ok:
            messagebox.showerror(
                "Compartir Una Carpeta",
                (proceso.stderr or proceso.stdout or "No se pudo quitar.").strip(),
                parent=self.root,
            )
            return
        self._pintar_lista()
        self.lbl_estado.config(text=f"{recurso['nombre']} ya no se comparte.")


class EncenderPC:
    """Envía la señal de encendido a un PC de la red que ya se haya visto antes."""

    def __init__(self, root):
        self.root = root
        self.root.title("Encender Un PC")
        self.root.minsize(520, 420)
        _centrar(self.root, 560, 460)
        self.equipos = []
        self.nombre = tk.StringVar()
        self.mac = tk.StringVar()

        tk.Label(self.root, text="Encender Un PC", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Enciende un ordenador apagado de tu red. Tiene que estar enchufado, "
                "y su placa debe permitir el encendido por red. "
                "Si no despierta, activa Wake-on-LAN en la BIOS de ese equipo. "
                "Los equipos aparecen aquí después de buscarlos en la red, o puedes anotar su MAC a mano."
            ),
            wraplength=510,
            justify=tk.LEFT,
        ).pack(padx=16, pady=(0, 8))

        self.lista = tk.Listbox(self.root, height=8)
        self.lista.pack(fill=tk.BOTH, expand=True, padx=16, pady=6)
        self.lista.bind("<<ListboxSelect>>", self._al_elegir)

        marco = tk.Frame(self.root)
        marco.pack(pady=6)
        boton_encender = tk.Button(marco, text="Encender", command=self.encender)
        boton_encender.pack(side=tk.LEFT, padx=6)
        con_tooltip(boton_encender, "Envía la señal de encendido al equipo seleccionado")
        boton_quitar = tk.Button(marco, text="Quitar de la lista", command=self.quitar)
        boton_quitar.pack(side=tk.LEFT, padx=6)
        con_tooltip(boton_quitar, "Olvida este equipo. No lo apaga ni lo enciende")

        marco_alta = tk.Frame(self.root)
        marco_alta.pack(fill=tk.X, padx=16, pady=(4, 12))
        tk.Label(marco_alta, text="Nombre").pack(side=tk.LEFT)
        tk.Entry(marco_alta, textvariable=self.nombre, width=16).pack(side=tk.LEFT, padx=4)
        tk.Label(marco_alta, text="MAC").pack(side=tk.LEFT)
        tk.Entry(marco_alta, textvariable=self.mac, width=20).pack(side=tk.LEFT, padx=4)
        boton_guardar = tk.Button(marco_alta, text="Añadir", command=self.anadir)
        boton_guardar.pack(side=tk.LEFT, padx=4)
        con_tooltip(boton_guardar, "Guarda un equipo que ahora está apagado, si conoces su dirección MAC")
        _tema(self.root)
        self._pintar()

    def _pintar(self):
        datos = _leer_equipos()
        self.equipos = []
        self.lista.delete(0, tk.END)
        for mac, info in sorted(datos.items(), key=lambda par: (par[1].get("nombre") or "").lower()):
            self.equipos.append({"mac": mac, **info})
        if not self.equipos:
            self.lista.insert(tk.END, "Todavía no hay equipos. Busca en la red o añade una MAC.")
            return
        for equipo in self.equipos:
            ip = equipo.get("ip") or "sin IP"
            self.lista.insert(tk.END, f"{equipo.get('nombre') or 'PC'}  —  {equipo['mac']}  —  {ip}")

    def _al_elegir(self, _evento):
        indice = self.lista.curselection()
        if not self.equipos or not indice or indice[0] >= len(self.equipos):
            return
        equipo = self.equipos[indice[0]]
        self.nombre.set(equipo.get("nombre") or "")
        self.mac.set(equipo["mac"])

    def _guardar(self, mac, nombre, ip=""):
        datos = _leer_equipos()
        previo = datos.get(mac) or {}
        datos[mac] = {
            "nombre": nombre or previo.get("nombre") or "PC",
            "ip": ip or previo.get("ip") or "",
            "visto": previo.get("visto") or date.today().isoformat(),
        }
        with open(_ruta_equipos(), "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)

    def anadir(self):
        mac = _normalizar_mac(self.mac.get())
        if not mac:
            messagebox.showinfo("Encender Un PC", "La MAC tiene que ser como aa:bb:cc:dd:ee:ff.", parent=self.root)
            return
        nombre = self.nombre.get().strip() or "PC"
        self._guardar(mac, nombre)
        self._pintar()

    def quitar(self):
        indice = self.lista.curselection()
        if not self.equipos or not indice or indice[0] >= len(self.equipos):
            messagebox.showinfo("Encender Un PC", "Elige un equipo de la lista.", parent=self.root)
            return
        mac = self.equipos[indice[0]]["mac"]
        datos = _leer_equipos()
        datos.pop(mac, None)
        with open(_ruta_equipos(), "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
        self._pintar()

    def encender(self):
        mac = _normalizar_mac(self.mac.get())
        if not mac:
            indice = self.lista.curselection()
            if self.equipos and indice and indice[0] < len(self.equipos):
                mac = self.equipos[indice[0]]["mac"]
        if not mac:
            messagebox.showinfo("Encender Un PC", "Elige un equipo o escribe su MAC.", parent=self.root)
            return
        nombre = self.nombre.get().strip() or mac
        if not confirmar(
            f"Se va a enviar la señal de encendido a {nombre}.\n\n"
            "Solo funcionará si ese equipo está apagado, enchufado, "
            "y su placa permite encenderlo por la red.\n\n"
            "¿Quieres enviarla?",
            self.root,
            "Encender Un PC",
        ):
            return
        try:
            enviar_encendido(mac)
        except OSError as error:
            registrar("Encender un PC", str(error), False)
            messagebox.showerror("Encender Un PC", str(error), parent=self.root)
            return
        registrar("Encender un PC", mac, True)
        messagebox.showinfo(
            "Encender Un PC",
            f"Se ha enviado la señal a {nombre}.\n\n"
            "Si la placa lo permite, el equipo debería encenderse en unos segundos. "
            "Si no lo hace, activa Wake-on-LAN en su BIOS.",
            parent=self.root,
        )



def _gateway_casa():
    """IP del router (gateway de la ruta por defecto) o None."""
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        proceso = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=10,
            env=entorno,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proceso.returncode != 0 or not proceso.stdout.strip():
        return None
    coincidencia = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", proceso.stdout)
    return coincidencia.group(1) if coincidencia else None


def _ping_host(ip, veces=3):
    """Devuelve (ok, latencia_ms_o_None, detalle)."""
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        proceso = subprocess.run(
            ["ping", "-c", str(veces), "-W", "2", ip],
            capture_output=True,
            text=True,
            timeout=20,
            env=entorno,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return False, None, str(error)
    salida = (proceso.stdout or "") + (proceso.stderr or "")
    latencia = None
    media = re.search(r"rtt min/avg/max/[^\s]+\s*=\s*[\d.]+/([\d.]+)/", salida)
    if not media:
        media = re.search(r"min/avg/max/[^\s]+\s*=\s*[\d.]+/([\d.]+)/", salida)
    if media:
        try:
            latencia = float(media.group(1))
        except ValueError:
            latencia = None
    return proceso.returncode == 0, latencia, salida.strip()


class RouterCasa:
    """Comprueba si el router de casa responde al ping."""

    def __init__(self, root):
        self.root = root
        self.root.title("¿Responde El Router?")
        self.root.minsize(480, 280)
        _centrar(self.root, 520, 320)
        self._gateway = None

        tk.Label(self.root, text="¿Responde el router?", font=("Arial", 14, "bold")).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Comprueba si el aparato de tu red (el router) contesta. "
                "Si no responde, casi nada de la red de casa funcionará bien."
            ),
            wraplength=480,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 8))

        self.lbl_estado = tk.Label(
            self.root,
            text="Pulsa Comprobar para hacer un ping al router.",
            font=("Arial", 11, "bold"),
            wraplength=480,
            justify=tk.LEFT,
        )
        self.lbl_estado.pack(fill=tk.X, padx=14, pady=4)

        self.lbl_detalle = tk.Label(self.root, text="", wraplength=480, justify=tk.LEFT)
        self.lbl_detalle.pack(fill=tk.X, padx=14, pady=(0, 8))

        marco = tk.Frame(self.root)
        marco.pack(pady=8)
        self.btn_comprobar = tk.Button(marco, text="Comprobar", width=14, command=self.comprobar)
        self.btn_comprobar.pack(side=tk.LEFT, padx=6)
        con_tooltip(self.btn_comprobar, "Hace tres pings al router (la puerta de enlace de tu red)")
        self.btn_abrir = tk.Button(
            marco, text="Abrir página del router", width=20, command=self.abrir_pagina, state=tk.DISABLED
        )
        self.btn_abrir.pack(side=tk.LEFT, padx=6)
        con_tooltip(
            self.btn_abrir,
            "Abre en el navegador la dirección del router (suele pedir usuario y contraseña del aparato)",
        )
        btn_cerrar = tk.Button(marco, text="Cerrar", width=10, command=self.root.destroy)
        btn_cerrar.pack(side=tk.LEFT, padx=6)
        con_tooltip(btn_cerrar, "Cierra esta ventana")

        _tema(self.root)
        self.comprobar()

    def comprobar(self):
        self.btn_comprobar.config(state=tk.DISABLED)
        self.lbl_estado.config(text="Comprobando…", fg="#2471a3")
        self.lbl_detalle.config(text="")

        def trabajo():
            gateway = _gateway_casa()
            if not gateway:
                return {"gateway": None, "ok": False, "latencia": None, "detalle": "Sin ruta por defecto"}
            ok, latencia, detalle = _ping_host(gateway)
            return {"gateway": gateway, "ok": ok, "latencia": latencia, "detalle": detalle}

        def al_terminar(datos):
            if not self.root.winfo_exists():
                return
            self.btn_comprobar.config(state=tk.NORMAL)
            self._gateway = datos.get("gateway")
            if not self._gateway:
                self.lbl_estado.config(text="No se encontró el router.", fg="#c0392b")
                self.lbl_detalle.config(
                    text="Este equipo no tiene una ruta por defecto. Revisa el cable o el Wi-Fi."
                )
                self.btn_abrir.config(state=tk.DISABLED)
                return
            if datos["ok"]:
                lat = datos["latencia"]
                extra = f" Latencia media: {lat:.1f} ms." if lat is not None else ""
                self.lbl_estado.config(
                    text=f"Sí: el router {self._gateway} responde.{extra}",
                    fg="#1e8449",
                )
                self.lbl_detalle.config(
                    text="Si quieres cambiar Wi-Fi o contraseña del router, abre su página (botón de abajo)."
                )
                self.btn_abrir.config(state=tk.NORMAL)
            else:
                self.lbl_estado.config(
                    text=f"No responde: {self._gateway}",
                    fg="#c0392b",
                )
                self.lbl_detalle.config(
                    text="Prueba otro cable, reinicia el router o revisa la Wi-Fi. "
                    "Aun así puedes intentar abrir su página por si el ping está bloqueado."
                )
                self.btn_abrir.config(state=tk.NORMAL)

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self.btn_comprobar.config(state=tk.NORMAL)
            messagebox.showerror("¿Responde El Router?", str(error), parent=self.root)

        en_hilo(self.root, trabajo, al_terminar=al_terminar, al_error=al_error)

    def abrir_pagina(self):
        if not self._gateway:
            messagebox.showinfo("¿Responde El Router?", "Primero comprueba el router.", parent=self.root)
            return
        webbrowser.open(f"http://{self._gateway}")
