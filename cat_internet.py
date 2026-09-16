"""
Este módulo contiene funciones para gestionar el reinicio de las tarjetas de red en un sistema Linux (Ubuntu). 
Utiliza varios módulos de Python para interactuar con el sistema operativo, obtener contraseñas, gestionar la interfaz gráfica de usuario 
y mostrar mensajes.

Clases:
    RedTools:
        Clase que proporciona herramientas para el manejo de la red.

        Args:
            root: El widget raíz de Tkinter.

        Attributes:
            root: El widget raíz de Tkinter.
            area_central: El área central donde se muestran las herramientas relacionadas con la red.

Funciones:
    reiniciar_servicio_red():
        Detecta y reinicia el servicio de red en uso (NetworkManager o systemd-networkd).

    reiniciar_networkmanager():
        Reinicia el servicio NetworkManager utilizando el comando systemctl.

    reiniciar_systemd_networkd():
        Reinicia el servicio systemd-networkd utilizando el comando systemctl.

    reiniciar_tarjeta_red(interfaz, etiqueta_ip_local_info, etiqueta_ip_publica_info, callback=None):
        Reinicia una interfaz de red específica desactivándola y activándola nuevamente. Actualiza las etiquetas de la interfaz gráfica con las nuevas direcciones IP.

    mostrar_resultado_ping(resultado_ping):
        Muestra el resultado de un comando ping en una nueva ventana de Tkinter.

    hacer_ping(entry_url):
        Realiza un comando ping a una URL especificada por el usuario y muestra el resultado.
"""
import subprocess
from password import obtener_contrasena
import time
from tkinter import messagebox, scrolledtext
import shutil
from cat_informacion import Informacion
import tkinter as tk
import preferencias
import socket
import os
import re
import speedtest
from tooltip import ToolTip
from placeholder import entradaConPlaceHolder
from registro import confirmar, registrar, en_hilo, ventana_progreso

""" 

Funciones relacionadas con el reinicio de las tarjetas de red

"""
def reiniciar_servicio_red():
    """
    Detecta y reinicia el servicio de red en uso (NetworkManager o systemd-networkd).

    Si no se encuentra ningún servicio de red conocido, imprime un mensaje indicando la situación.
    """
    try:
        resultado = subprocess.run(['systemctl', 'list-units', '--type=service'], capture_output=True, text=True)
        servicios_red = resultado.stdout
        # Comprobar qué servicio de red está en uso
        if 'NetworkManager.service' in servicios_red:
            reiniciar_networkmanager()
        elif 'systemd-networkd.service' in servicios_red:
            reiniciar_systemd_networkd()
        else:
            print("No se encontró ningún servicio de red conocido en uso.")
    except Exception as e:
            print(f"Error al obtener los servicios de red: {e}")

def reiniciar_networkmanager():
    """
    Reinicia el servicio NetworkManager utilizando el comando systemctl.

    Si ocurre un error durante el reinicio, imprime un mensaje indicando la situación.
    """
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'NetworkManager'], check=True)
        print("Se reinició el servicio NetworkManager.")
    except subprocess.CalledProcessError as e:
        print(f"Error al reiniciar NetworkManager: {e}")

def reiniciar_systemd_networkd():
    """
    Reinicia el servicio systemd-networkd utilizando el comando systemctl.

    Si ocurre un error durante el reinicio, imprime un mensaje indicando la situación.
    """
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-networkd'], check=True)
        print("Se reinició el servicio systemd-networkd.")
    except subprocess.CalledProcessError as e:
        print(f"Error al reiniciar systemd-networkd: {e}")

def reiniciar_tarjeta_red(interfaz, parent=None, callback=None):
    if not interfaz:
        messagebox.showwarning("Tarjeta de red no seleccionada", "Por favor, seleccione una tarjeta de red.", parent=parent)
        return
    if not confirmar(
        f"¿Reiniciar la interfaz {interfaz}?\nLa conexión se cortará unos segundos.",
        parent,
    ):
        registrar("Reiniciar tarjeta de red", f"{interfaz} cancelado", False)
        return

    contrasena = obtener_contrasena()
    if isinstance(contrasena, bytes):
        contrasena = contrasena.decode("utf-8")
    widget = parent or tk._default_root
    progreso, etiqueta = ventana_progreso(widget, "Reiniciar red", f"Reiniciando {interfaz}...")

    def trabajador():
        if not shutil.which("ifconfig"):
            instalacion = subprocess.run(
                ["sudo", "-S", "-p", "", "apt", "install", "-y", "net-tools"],
                input=contrasena + "\n",
                capture_output=True,
                text=True,
            )
            if instalacion.returncode != 0:
                raise RuntimeError("No se pudo instalar net-tools/ifconfig.")
        for estado in ("down", "up"):
            resultado = subprocess.run(
                ["sudo", "-S", "-p", "", "ifconfig", interfaz, estado],
                input=contrasena + "\n",
                capture_output=True,
                text=True,
            )
            if resultado.returncode != 0:
                raise RuntimeError(resultado.stderr or f"ifconfig {estado} falló")
            time.sleep(3)
        registrar("Reiniciar tarjeta de red", interfaz, True)
        return interfaz

    def terminar(_interfaz):
        if progreso.winfo_exists():
            progreso.destroy()
        messagebox.showinfo("Reinicio de red", f"La interfaz {_interfaz} se reinició correctamente.", parent=widget)
        if callback:
            callback("La tarjeta de red se reinició correctamente.")

    en_hilo(widget, trabajador, al_terminar=terminar)

def mostrar_resultado_ping(resultado_ping):
    """
    Muestra el resultado de un comando ping en una nueva ventana de Tkinter.

    Args:
        resultado_ping (str): Resultado del comando ping a mostrar.
    """
    ventana_resultado_ping = tk.Toplevel()
    ventana_resultado_ping.title("Resultado del Ping")

    # Etiqueta para mostrar el resultado del ping
    resultado_label = tk.Label(ventana_resultado_ping, text=resultado_ping, font=("Arial", 12))
    resultado_label.pack(padx=10, pady=10)
    # Aplicar el tema seleccionado a la nueva ventana
    preferencias.cambiar_tema(ventana_resultado_ping, preferencias.tema_seleccionado)
    preferencias.cambiar_tema(resultado_label, preferencias.tema_seleccionado)

def hacer_ping(entry_url):
    url = entry_url.get()
    if not url:
        messagebox.showerror("Error", "Por favor, ingrese una URL para hacer ping.")
        return

    def eliminar_protocolo(destino):
        protocolos = ['http://', 'https://', 'ftp://', 'ftps://', 'sftp://', 'ssh://', 'telnet://', 'smtp://', 'imap://', 'pop3://']
        for protocolo in protocolos:
            if destino.startswith(protocolo):
                return destino[len(protocolo):]
        return destino

    destino = eliminar_protocolo(url)
    progreso, _et = ventana_progreso(entry_url.winfo_toplevel(), "Ping", f"Haciendo ping a {destino}...")

    def trabajador():
        resultado = subprocess.run(
            ["/bin/ping", "-c", "4", destino],
            capture_output=True,
            text=True,
            timeout=12,
        )
        return resultado.stdout or resultado.stderr or "Sin respuesta"

    def terminar(texto):
        if progreso.winfo_exists():
            progreso.destroy()
        mostrar_resultado_ping(texto)

    en_hilo(entry_url, trabajador, al_terminar=terminar)


def _cmd_red(args, timeout=12):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, env=entorno
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def _es_wifi(interfaz):
    return bool(interfaz) and os.path.isdir(f"/sys/class/net/{interfaz}/wireless")


def _primera_wifi():
    try:
        for nombre in os.listdir("/sys/class/net"):
            if _es_wifi(nombre):
                return nombre
    except OSError:
        return ""
    return ""


def _valorar_snr(snr):
    if snr is None:
        return "No disponible"
    if snr >= 40:
        return "excelente"
    if snr >= 25:
        return "buena"
    if snr >= 15:
        return "regular"
    return "mala"


def _valorar_senal(dbm):
    if dbm is None:
        return "No disponible"
    if dbm >= -50:
        return "excelente"
    if dbm >= -60:
        return "buena"
    if dbm >= -70:
        return "aceptable"
    if dbm >= -80:
        return "débil"
    return "muy débil"


def _wifi_proc(interfaz):
    try:
        with open("/proc/net/wireless", encoding="utf-8") as archivo:
            for linea in archivo:
                if not linea.strip().startswith(interfaz):
                    continue
                partes = linea.replace(":", " ").split()
                if len(partes) < 5:
                    return None, None
                try:
                    nivel = float(partes[3].rstrip("."))
                    ruido = float(partes[4].rstrip("."))
                except ValueError:
                    return None, None
                if ruido <= -200:
                    ruido = None
                return int(nivel), int(ruido) if ruido is not None else None
    except OSError:
        pass
    return None, None


def _wifi_iw(interfaz):
    ssid = None
    senal = None
    ruido = None
    enlace = _cmd_red(["iw", "dev", interfaz, "link"], timeout=8)
    if enlace.returncode == 0:
        for linea in enlace.stdout.splitlines():
            texto = linea.strip()
            if texto.startswith("SSID:"):
                ssid = texto.split(":", 1)[1].strip()
            elif texto.startswith("signal:"):
                coinc = re.search(r"(-?\d+)", texto)
                if coinc:
                    senal = int(coinc.group(1))
    encuesta = _cmd_red(["iw", "dev", interfaz, "survey", "dump"], timeout=8)
    if encuesta.returncode == 0:
        en_uso = False
        actual = None
        for linea in encuesta.stdout.splitlines():
            texto = linea.strip()
            if texto.startswith("frequency:"):
                en_uso = "[in use]" in texto
            elif texto.startswith("noise:"):
                coinc = re.search(r"(-?\d+)", texto)
                if coinc:
                    actual = int(coinc.group(1))
                    if en_uso:
                        ruido = actual
        if ruido is None and actual is not None:
            ruido = actual
    return ssid, senal, ruido


def _estadisticas_iface(interfaz):
    base = f"/sys/class/net/{interfaz}/statistics"
    valores = {}
    for clave in ("rx_errors", "rx_dropped", "rx_crc_errors", "collisions", "tx_errors"):
        try:
            with open(os.path.join(base, clave), encoding="utf-8") as archivo:
                valores[clave] = archivo.read().strip()
        except OSError:
            valores[clave] = "N/D"
    return valores


def _ping_internet():
    for destino in ("1.1.1.1", "8.8.8.8"):
        resultado = _cmd_red(["/bin/ping", "-c", "8", "-i", "0.3", "-W", "2", destino], timeout=20)
        texto = resultado.stdout or ""
        if "transmitted" not in texto and "transmitted" not in (resultado.stderr or ""):
            continue
        perdido = None
        media = None
        jitter = None
        coinc_loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", texto)
        if coinc_loss:
            perdido = float(coinc_loss.group(1))
        coinc_rtt = re.search(
            r"rtt [^=]+=\s*[\d.]+/([\d.]+)/[\d.]+/([\d.]+)",
            texto,
        )
        if coinc_rtt:
            media = float(coinc_rtt.group(1))
            jitter = float(coinc_rtt.group(2))
        return destino, perdido, media, jitter, resultado.returncode == 0
    return None, None, None, None, False


def medir_nivel_ruido(interfaz=""):
    """
    Combina ruido de radio (Wi-Fi) y estabilidad de la ruta a Internet (pérdida/jitter).
    El ruido RF solo existe en inalámbrico; en cable se muestran errores de la NIC.
    """
    interfaz = (interfaz or "").strip() or _primera_wifi()
    lineas = []

    if interfaz and _es_wifi(interfaz):
        ssid, senal_iw, ruido_iw = _wifi_iw(interfaz)
        senal_proc, ruido_proc = _wifi_proc(interfaz)
        senal = senal_iw if senal_iw is not None else senal_proc
        ruido = ruido_iw if ruido_iw is not None else ruido_proc
        snr = (senal - ruido) if senal is not None and ruido is not None else None
        lineas.append(f"Enlace Wi-Fi ({interfaz})")
        lineas.append(f"Red: {ssid or 'no asociada'}")
        if senal is not None:
            lineas.append(f"Señal: {senal} dBm ({_valorar_senal(senal)})")
        else:
            lineas.append("Señal: no disponible")
        if ruido is not None:
            lineas.append(f"Ruido de radio: {ruido} dBm")
        else:
            lineas.append(
                "Ruido de radio: el adaptador no lo informa (habitual en muchos chips)."
            )
        if snr is not None:
            lineas.append(f"Relación señal/ruido (SNR): {snr} dB ({_valorar_snr(snr)})")
            lineas.append(
                "El SNR es señal menos ruido. Cuanto más alto, menos interferencia "
                "(microondas, vecinos, Bluetooth)."
            )
        else:
            lineas.append("SNR: no se puede calcular sin ruido de radio.")
        lineas.append("")
    elif interfaz:
        stats = _estadisticas_iface(interfaz)
        lineas.append(f"Enlace por cable ({interfaz})")
        lineas.append("En Ethernet no hay ruido de radio. Se muestran errores del adaptador:")
        lineas.append(f"Errores de recepción: {stats['rx_errors']}")
        lineas.append(f"CRC: {stats['rx_crc_errors']}")
        lineas.append(f"Descartes: {stats['rx_dropped']}")
        lineas.append(f"Errores de envío: {stats['tx_errors']}")
        lineas.append(f"Colisiones: {stats['collisions']}")
        lineas.append("")
    else:
        lineas.append("No hay una interfaz seleccionada ni un Wi-Fi activo.")
        lineas.append("")

    destino, perdido, media, jitter, ok = _ping_internet()
    lineas.append("Ruta a Internet")
    if not ok and destino is None:
        lineas.append("No se pudo hacer ping a 1.1.1.1 ni a 8.8.8.8.")
        return "\n".join(lineas)
    lineas.append(f"Destino: {destino}")
    if perdido is not None:
        lineas.append(f"Pérdida de paquetes: {perdido:.1f} %")
    if media is not None:
        lineas.append(f"Latencia media: {media:.1f} ms")
    if jitter is not None:
        lineas.append(f"Jitter (variación): {jitter:.1f} ms")
        if perdido == 0 and jitter < 10:
            valoracion = "estable (poco ruido en la ruta)"
        elif perdido is not None and perdido < 2 and jitter < 30:
            valoracion = "aceptable"
        else:
            valoracion = "inestable (mucho ruido o pérdida en la ruta)"
        lineas.append(f"Valoración: {valoracion}")
    lineas.append(
        "El jitter y la pérdida de paquetes miden el «ruido» de la conexión a Internet, "
        "distinto del ruido de radio del Wi-Fi."
    )
    return "\n".join(lineas)


class RedTools:
    def __init__(self, root):
        self.root = root
        self.area_central = None

    def set_area_central(self, area_central):
        self.area_central = area_central

    def escanear_puertos(self):
        self.limpiar_area_central()
        tk.Label(self.area_central, text="Escaneo de Puertos", font=("Arial", 14, "bold")).pack(pady=10)
        tk.Label(self.area_central, text="Introduce la IP a escanear:", font=("Arial", 12)).pack(pady=5)
        entry_ip = entradaConPlaceHolder(self.area_central, placeholder="Ejemplo de IP: 8.8.8.8", width=30)
        entry_ip.pack(pady=5)
        resultado_text = tk.Text(self.area_central, height=20, width=80)
        resultado_text.pack(pady=10)

        def iniciar_escaneo():
            ip = entry_ip.get().strip()
            if not ip:
                messagebox.showwarning("Escaneo", "Indica una dirección IP.")
                return
            progreso, _et = ventana_progreso(self.root, "Escaneo de puertos", f"Escaneando {ip}...")

            def trabajador():
                abiertos = []
                for puerto in range(1, 1025):
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.2)
                    if s.connect_ex((ip, puerto)) == 0:
                        abiertos.append(puerto)
                    s.close()
                return abiertos

            def terminar(abiertos):
                if progreso.winfo_exists():
                    progreso.destroy()
                resultado_text.delete("1.0", tk.END)
                if abiertos:
                    for puerto in abiertos:
                        resultado_text.insert(tk.END, f"Puerto {puerto}: Abierto\n")
                else:
                    resultado_text.insert(tk.END, "No se encontraron puertos abiertos en 1-1024.\n")

            en_hilo(self.root, trabajador, al_terminar=terminar)

        boton_escanear = tk.Button(self.area_central, text="Escanear Puertos", width=20, command=iniciar_escaneo)
        boton_escanear.pack(pady=10)
        ToolTip(boton_escanear, "Inicia el escaneo de puertos de la IP indicada")

    def test_velocidad(self):
        self.limpiar_area_central()
        tk.Label(self.area_central, text="Test de Velocidad de Internet", font=("Arial", 14, "bold")).pack(pady=10)
        resultado_text = tk.Text(self.area_central, height=20, width=80)
        resultado_text.pack(pady=10)

        def realizar_test():
            progreso, _et = ventana_progreso(self.root, "Test de velocidad", "Midiendo descarga y subida...")

            def trabajador():
                st = speedtest.Speedtest()
                st.download()
                st.upload()
                return st.results.dict()

            def terminar(resultados):
                if progreso.winfo_exists():
                    progreso.destroy()
                resultado_text.delete("1.0", tk.END)
                resultado_text.insert(tk.END, f"Velocidad de descarga: {resultados['download'] / 1_000_000:.2f} Mbps\n")
                resultado_text.insert(tk.END, f"Velocidad de carga: {resultados['upload'] / 1_000_000:.2f} Mbps\n")
                resultado_text.insert(tk.END, f"Ping: {resultados['ping']} ms\n")

            en_hilo(self.root, trabajador, al_terminar=terminar)

        boton_iniciar_test = tk.Button(self.area_central, text="Iniciar Test", command=realizar_test)
        boton_iniciar_test.pack(pady=10)
        ToolTip(boton_iniciar_test, "Inicia el Test de Velocidad")

    def diagnostico_red(self):
        for widget in self.area_central.winfo_children():
            widget.destroy()
        tk.Label(self.area_central, text="Diagnóstico de Red", font=("Arial", 14, "bold")).pack(pady=10)
        resultado_text_frame = tk.Frame(self.area_central)
        resultado_text_frame.pack(pady=10)
        resultado_text = scrolledtext.ScrolledText(resultado_text_frame, height=20, width=80, wrap=tk.NONE)
        resultado_text.pack(expand=True, fill=tk.BOTH)

        def realizar_diagnostico():
            progreso, _et = ventana_progreso(self.root, "Diagnóstico de red", "Ejecutando traceroute y netstat...")

            def trabajador():
                if not shutil.which("traceroute"):
                    raise RuntimeError("El comando traceroute no está instalado.")
                if not shutil.which("netstat"):
                    raise RuntimeError("El comando netstat no está instalado.")
                tr = subprocess.run(["traceroute", "www.google.com"], capture_output=True, text=True, timeout=90)
                ns = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True, timeout=20)
                return f"Traceroute:\n{tr.stdout or tr.stderr}\n\nNetstat:\n{ns.stdout or ns.stderr}"

            def terminar(texto):
                if progreso.winfo_exists():
                    progreso.destroy()
                resultado_text.delete("1.0", tk.END)
                resultado_text.insert(tk.END, texto)

            en_hilo(self.root, trabajador, al_terminar=terminar)

        boton_iniciar_diagnostico = tk.Button(self.area_central, text="Iniciar Diagnóstico", command=realizar_diagnostico)
        boton_iniciar_diagnostico.pack(pady=10)
        ToolTip(boton_iniciar_diagnostico, "Haz clic para iniciar el diagnóstico de la red")

    def nivel_ruido(self, interfaz=""):
        self.limpiar_area_central()
        tk.Label(
            self.area_central,
            text="Nivel de ruido de la conexión",
            font=("Arial", 14, "bold"),
        ).pack(pady=10)
        tk.Label(
            self.area_central,
            text="Wi-Fi: ruido de radio y SNR. Internet: pérdida de paquetes y jitter.",
            wraplength=520,
        ).pack(pady=(0, 6))
        resultado = scrolledtext.ScrolledText(self.area_central, height=18, width=80, wrap=tk.WORD)
        resultado.pack(pady=8, padx=10, fill=tk.BOTH, expand=True)

        def medir():
            progreso, _et = ventana_progreso(
                self.root, "Nivel de ruido", "Midiendo señal, ruido y latencia..."
            )

            def trabajador():
                return medir_nivel_ruido(interfaz)

            def terminar(texto):
                if progreso.winfo_exists():
                    progreso.destroy()
                resultado.delete("1.0", tk.END)
                resultado.insert(tk.END, texto)

            en_hilo(self.root, trabajador, al_terminar=terminar)

        boton = tk.Button(self.area_central, text="Medir ahora", command=medir)
        boton.pack(pady=8)
        ToolTip(boton, "Mide el ruido de radio (Wi-Fi) y la estabilidad de la ruta a Internet")
        medir()

    def limpiar_area_central(self):
        for widget in self.area_central.winfo_children():
            widget.destroy()
            
