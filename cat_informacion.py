"""
Clase Informacion

Esta clase proporciona métodos estáticos para obtener información detallada sobre el sistema, incluyendo interfaces de red, direcciones IP, 
información del sistema operativo, monitorización de recursos del sistema y más. Los métodos se implementan utilizando diversas bibliotecas y 
herramientas de Python.

Métodos:
    obtener_interfaces_red():
        Obtiene una lista de interfaces de red que están activas.
        Retorna:
            list: Lista de nombres de interfaces de red activas.

    obtener_direccion_ip_local():
        Obtiene la dirección IP local del dispositivo.
        Retorna:
            str: Dirección IP local, o 'No disponible' si no se puede determinar.

    obtener_direccion_ip_publica():
        Obtiene la dirección IP pública del dispositivo.
        Retorna:
            str: Dirección IP pública, o 'No disponible' si no se puede determinar.

    obtener_info_sistema():
        Obtiene información básica del sistema operativo y del usuario.
        Retorna:
            dict: Diccionario con información del sistema operativo y del usuario.

    obtener_version_ubuntu():
        Obtiene la versión de Ubuntu si el sistema operativo es Linux.
        Retorna:
            str: Versión de Ubuntu, o 'No disponible' si no se puede determinar.

    obtener_tipo_escritorio():
        Determina el tipo de entorno de escritorio en uso.
        Retorna:
            str: Nombre del entorno de escritorio y tipo de gestor de ventanas, o 'Desconocido' si no se puede determinar.

    monitorizar_sistema():
        Muestra una ventana de gráfico que monitoriza el uso de CPU, memoria, disco, red, temperatura del CPU y carga del sistema en tiempo real.
        No retorna nada. Abre una ventana de Tkinter con un gráfico de barras.

    obtener_servidores_dns():
        Obtiene los servidores DNS locales y públicos configurados.
        Retorna:
            dict: Diccionario con listas de servidores DNS locales y públicos.

    get_tiempo_actividad():
        Obtiene el tiempo de actividad del sistema.
        Retorna:
            str: Tiempo de actividad en formato legible, o 'No disponible' si no se puede determinar.

    get_zona_horaria():
        Obtiene la zona horaria del sistema.
        Retorna:
            str: Zona horaria del sistema, o 'No disponible' si no se puede determinar.

    obtener_informacion_procesador():
        Obtiene información detallada del procesador.
        Retorna:
            list: Lista de listas con información del procesador en formato de tabla.

    obtener_informacion_memoria():
        Obtiene información detallada sobre la memoria RAM y la memoria swap.
        Retorna:
            dict: Diccionario con información de memoria RAM y memoria swap.

    obtener_informacion_completa():
        Obtiene toda la información recopilada por los métodos anteriores en un solo diccionario.
        Retorna:
            dict: Diccionario con toda la información recopilada sobre el sistema.
"""
import subprocess
import netifaces
import platform
import getpass
import os
import urllib.request
import psutil
import re
import matplotlib.pyplot as plt
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class Informacion:
    @staticmethod
    def obtener_interfaces_red():
        interfaces = []
        try:
            # Cambiamos 'ip link show' por 'ip addr show' para obtener las interfaces de red sin sudo
            resultado = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            lineas = resultado.stdout.split('\n')
            for linea in lineas:
                if 'state UP' in linea:
                    partes = linea.split(': ')
                    if len(partes) > 1:
                        interfaz = partes[1].split(':')[0]
                        interfaces.append(interfaz)
        except Exception as e:
            print(f"Error al obtener interfaces de red: {e}")
        return interfaces
    
    @staticmethod
    def obtener_direccion_ip_local():
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            try:
                # Utilizamos netifaces para obtener la dirección IP local sin necesidad de sudo
                address = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
                if not address.startswith('127.'):
                    return address
            except (KeyError, IndexError):
                pass
        return 'No disponible'

    @staticmethod
    def obtener_direccion_ip_publica():
        try:
            ip = urllib.request.urlopen('https://ifconfig.me/ip').read().decode('utf8')
            return ip.strip()
        except Exception as e:
            print(f"No se pudo obtener la dirección IP pública: {e}")
            return 'No disponible'
        
    @staticmethod
    def obtener_info_sistema():
        nombre_sistema = platform.system()
        version_sistema = platform.release()

        if nombre_sistema == 'Linux':
            nombre_sistema = 'Ubuntu'
            version_ubuntu = Informacion.obtener_version_ubuntu()
        else:
            version_ubuntu = 'No disponible'

        usuario = getpass.getuser()

        return {
            "Usuario": usuario,
            "Sistema Operativo": nombre_sistema,
            "Versión de Sistema": version_sistema,
            "Versión de Ubuntu": version_ubuntu
        }

    @staticmethod
    def obtener_version_ubuntu():
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('VERSION_ID='):
                        return line.strip().split('=')[1].strip('"')
        except Exception as e:
            print(f"Error al obtener la versión de Ubuntu: {e}")
        return 'No disponible'
    
    @staticmethod
    def obtener_tipo_escritorio():
        archivos_configuracion = {
            "GNOME": "/usr/share/glib-2.0/schemas/org.gnome.desktop.interface.gschema.xml",
            "KDE": "/usr/share/plasma/plasmoids/org.kde.plasma.desktop/contents/config/main.xml",
            "LXDE": "/etc/xdg/openbox/rc.xml",
            "MATE": "/usr/share/mate-control-center/ui/",
            "Cinnamon": "/usr/share/cinnamon/cinnamon-settings/cinnamon-settings.py",
            "XFCE": "/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-session.xml"
        }

        gestor_ventanas = os.environ.get('XDG_SESSION_TYPE', 'Desconocido')
        
        for escritorio, archivo in archivos_configuracion.items():
            if os.path.isfile(archivo):
                return f"{escritorio} - gestor de ventanas {gestor_ventanas}"

        return "Desconocido"
    

    @staticmethod
    def _comando_texto(args, timeout=8):
        entorno = os.environ.copy()
        entorno["LC_ALL"] = "C"
        try:
            resultado = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=entorno,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return ""
        return resultado.stdout if resultado.returncode == 0 else resultado.stdout or ""

    @staticmethod
    def _leer_sysfs(ruta):
        try:
            with open(ruta, encoding="utf-8") as archivo:
                return archivo.read().strip()
        except OSError:
            return None

    @staticmethod
    def _formato_bytes(nbytes):
        try:
            nbytes = float(nbytes)
        except (TypeError, ValueError):
            return None
        for unidad in ("B", "KiB", "MiB", "GiB", "TiB"):
            if nbytes < 1024:
                return f"{nbytes:.0f} {unidad}" if unidad == "B" else f"{nbytes:.1f} {unidad}"
            nbytes /= 1024
        return f"{nbytes:.1f} PiB"

    @staticmethod
    def _fabricante_pci(vendor_id):
        tabla = {
            "10de": "NVIDIA",
            "1002": "AMD",
            "1022": "AMD",
            "8086": "Intel",
            "1414": "Microsoft",
        }
        return tabla.get((vendor_id or "").lower(), None)

    @staticmethod
    def _gpus_lspci():
        salida = Informacion._comando_texto(["lspci", "-nnk"])
        gpus = []
        actual = None
        for linea in salida.splitlines():
            if re.search(r"VGA compatible controller|3D controller|Display controller", linea):
                if actual:
                    gpus.append(actual)
                vendor_id = ""
                ids = re.search(r"\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]", linea)
                if ids:
                    vendor_id = ids.group(1).lower()
                nombre = linea.split(": ", 1)[-1].strip() if ": " in linea else linea.strip()
                actual = {
                    "Nombre": Informacion._fabricante_pci(vendor_id) or "GPU",
                    "Modelo": nombre,
                    "Memoria": "No disponible",
                    "Controlador": "No disponible",
                    "Temperatura": "No disponible",
                    "Descripción": "No disponible",
                    "Fabricante": Informacion._fabricante_pci(vendor_id) or "Desconocido",
                    "_vendor": vendor_id,
                }
            elif actual and "Kernel driver in use:" in linea:
                actual["Controlador"] = linea.split(":", 1)[-1].strip()
        if actual:
            gpus.append(actual)
        return gpus

    @staticmethod
    def _enriquecer_nvidia(gpus):
        salida = Informacion._comando_texto(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,temperature.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ]
        )
        if not salida.strip():
            return
        lineas = [l.strip() for l in salida.splitlines() if l.strip()]
        nvidia = [g for g in gpus if g.get("_vendor") == "10de"]
        for indice, linea in enumerate(lineas):
            partes = [p.strip() for p in linea.split(",")]
            if len(partes) < 4:
                continue
            destino = nvidia[indice] if indice < len(nvidia) else None
            if destino is None:
                destino = {
                    "Nombre": "NVIDIA",
                    "Modelo": partes[0],
                    "Memoria": "No disponible",
                    "Controlador": "No disponible",
                    "Temperatura": "No disponible",
                    "Descripción": "No disponible",
                    "Fabricante": "NVIDIA",
                    "_vendor": "10de",
                }
                gpus.append(destino)
            destino["Fabricante"] = "NVIDIA"
            destino["Nombre"] = "NVIDIA"
            destino["Modelo"] = partes[0] or destino["Modelo"]
            if partes[1]:
                destino["Memoria"] = f"{partes[1]} MiB"
            if partes[2]:
                destino["Temperatura"] = f"{partes[2]} °C"
            if partes[3]:
                destino["Controlador"] = f"nvidia {partes[3]}"

    @staticmethod
    def _enriquecer_sysfs(gpus):
        drm = "/sys/class/drm"
        if not os.path.isdir(drm):
            return
        tarjetas = []
        for nombre in sorted(os.listdir(drm)):
            if not re.fullmatch(r"card\d+", nombre):
                continue
            base = os.path.join(drm, nombre, "device")
            vendor = (Informacion._leer_sysfs(os.path.join(base, "vendor")) or "").lower().replace("0x", "")
            if not vendor:
                continue
            tarjetas.append((vendor, base))

        usados = set()
        for gpu in gpus:
            vendor = gpu.get("_vendor")
            for indice, (vendor_sys, base) in enumerate(tarjetas):
                if indice in usados or vendor_sys != vendor:
                    continue
                usados.add(indice)
                gpu["Fabricante"] = Informacion._fabricante_pci(vendor_sys) or gpu.get("Fabricante")
                gpu["Nombre"] = gpu["Fabricante"]
                vram = Informacion._leer_sysfs(os.path.join(base, "mem_info_vram_total"))
                if vram and vram.isdigit() and gpu.get("Memoria") == "No disponible":
                    gpu["Memoria"] = Informacion._formato_bytes(vram) or gpu["Memoria"]
                hwmon = os.path.join(base, "hwmon")
                if os.path.isdir(hwmon) and gpu.get("Temperatura") == "No disponible":
                    for carpeta in os.listdir(hwmon):
                        for sensor in ("temp1_input", "temp2_input"):
                            bruto = Informacion._leer_sysfs(os.path.join(hwmon, carpeta, sensor))
                            if bruto and bruto.lstrip("-").isdigit():
                                gpu["Temperatura"] = f"{int(bruto) / 1000:.0f} °C"
                                break
                        if gpu.get("Temperatura") != "No disponible":
                            break
                break

    @staticmethod
    def _enriquecer_glxinfo(gpus):
        salida = Informacion._comando_texto(["glxinfo", "-B"])
        if not salida:
            return
        renderer = None
        memoria = None
        for linea in salida.splitlines():
            baja = linea.lower()
            if "opengl renderer" in baja and ":" in linea:
                renderer = linea.split(":", 1)[1].strip()
            elif baja.startswith("video memory:") or "dedicated video memory" in baja:
                memoria = linea.split(":", 1)[-1].strip()
        if not gpus:
            return
        principal = gpus[0]
        if renderer and principal.get("Descripción") in (None, "No disponible"):
            principal["Descripción"] = renderer
        if memoria and principal.get("Memoria") == "No disponible":
            principal["Memoria"] = memoria

    @staticmethod
    def obtener_informacion_tarjeta_grafica():
        """Lista de GPUs (Intel, AMD o NVIDIA) sin depender solo de nvidia-smi."""
        try:
            gpus = Informacion._gpus_lspci()
            Informacion._enriquecer_nvidia(gpus)
            Informacion._enriquecer_sysfs(gpus)
            Informacion._enriquecer_glxinfo(gpus)
            for gpu in gpus:
                gpu.pop("_vendor", None)
                if gpu.get("Descripción") == "No disponible":
                    gpu["Descripción"] = gpu.get("Fabricante") or "Adaptador gráfico"
            if not gpus:
                return [{
                    "Nombre": "No disponible",
                    "Modelo": "No disponible",
                    "Memoria": "No disponible",
                    "Controlador": "No disponible",
                    "Temperatura": "No disponible",
                    "Descripción": "No se detectó un adaptador gráfico",
                    "Fabricante": "Desconocido",
                }]
            return gpus
        except Exception:
            return [{
                "Nombre": "No disponible",
                "Modelo": "No disponible",
                "Memoria": "No disponible",
                "Controlador": "No disponible",
                "Temperatura": "No disponible",
                "Descripción": "No se pudo leer la GPU",
                "Fabricante": "Desconocido",
            }]

    @staticmethod
    def obtener_tiempo_arranque():
        """Tiempo de arranque según systemd-analyze (kernel + userspace)."""
        salida = Informacion._comando_texto(["systemd-analyze"], timeout=10)
        if not salida.strip():
            return "No disponible"
        primera = salida.strip().splitlines()[0].strip()
        return primera or "No disponible"



    @staticmethod
    def monitorizar_sistema():
        cpu_percent = psutil.cpu_percent()
        mem_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        red_info = psutil.net_io_counters(pernic=False)
        red_envio = red_info.bytes_sent
        red_recepcion = red_info.bytes_recv
        temperatura_cpu = psutil.sensors_temperatures().get('cpu_thermal', [None])[0].current if 'cpu_thermal' in psutil.sensors_temperatures() else None
        carga_sistema = psutil.getloadavg()[0]

        nombres = ['CPU', 'Memoria', 'Disco', 'Red (enviado)', 'Red (recibido)', 'Temperatura CPU', 'Carga del sistema']
        valores = [cpu_percent, mem_percent, disk_percent, red_envio / 1024 / 1024, red_recepcion / 1024 / 1024, temperatura_cpu, carga_sistema]
        colores = ['blue', 'green', 'red', 'orange', 'purple', 'cyan', 'magenta']

        nombres = [n for n, v in zip(nombres, valores) if v is not None]
        valores = [v for v in valores if v is not None]
        colores = colores[:len(valores)]

        ventana_grafico = tk.Toplevel()
        ventana_grafico.title("Estadísticas")

        fig, ax = plt.subplots(figsize=(12, 8))

        ax.bar(nombres, valores, color=colores)
        ax.set_xlabel('Recursos del Sistema')
        ax.set_ylabel('Porcentaje de Uso / Valor')
        ax.set_title('Monitorización del Sistema')
        ax.grid(True)

        canvas = FigureCanvasTkAgg(fig, master=ventana_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack()

        ventana_grafico.mainloop()
    
    @staticmethod
    def obtener_servidores_dns():
        dns_local = []
        dns_publico = []

        try:
            # Obtener DNS locales del archivo /etc/resolv.conf
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    match = re.match(r'\s*nameserver\s+(\S+)', line)
                    if match:
                        dns_local.append(match.group(1))

            # Obtener DNS públicos utilizando el comando nmcli
            output = subprocess.check_output(["nmcli", "dev", "show"])
            output = output.decode('utf-8').split('\n')
            for line in output:
                match = re.match(r'\s*IP4\.DNS\[[0-9]+\]:\s+(\S+)', line)
                if match:
                    dns_publico.append(match.group(1))

            return {"dns_local": dns_local, "dns_publico": dns_publico}

        except Exception as e:
            error_message = f"Error al obtener los servidores DNS: {e}"
            return {"dns_local": error_message, "dns_publico": error_message}


    
    @staticmethod
    def get_tiempo_actividad():
        try:
            tiempo_actividad_raw = subprocess.check_output(['uptime'], universal_newlines=True)
            tiempo_actividad_match = re.search(r'up\s+(.*?),', tiempo_actividad_raw)
            if tiempo_actividad_match:
                tiempo_actividad = tiempo_actividad_match.group(1)
                tiempo_parts = tiempo_actividad.split(':')
                if len(tiempo_parts) == 2:
                    horas = tiempo_parts[0]
                    minutos = tiempo_parts[1]
                    if int(horas) == 0:
                        return f"{minutos} minutos"
                    else:
                        return f"{horas} horas, {minutos} minutos"
                else:
                    return tiempo_actividad.strip()
            else:
                return "No disponible"
        except Exception as e:
            print(f"Error al obtener el tiempo de actividad: {e}")
            return "No disponible"

    @staticmethod
    def get_zona_horaria():
        try:
            # Eliminamos el uso de sudo y la función obtener_contrasena
            zona_horaria_raw = subprocess.check_output(['timedatectl', 'show', '-p', 'Timezone'], universal_newlines=True)
            zona_horaria_match = re.search(r'Timezone=(.*)', zona_horaria_raw)
            if zona_horaria_match:
                zona_horaria = zona_horaria_match.group(1)
                return zona_horaria.strip()
            else:
                return "No disponible"
        except Exception as e:
            print(f"Error al obtener la zona horaria: {e}")
            return "No disponible"
    
    @staticmethod    
    def obtener_informacion_procesador():
        info_procesador = {
            "Procesador": platform.processor(),
            "Frecuencia del Procesador (MHz)": psutil.cpu_freq().current
        }

        info_procesador["Número de núcleos y hilos"] = psutil.cpu_count(logical=True)

        info_procesador["Arquitectura del procesador"] = platform.architecture()[0]

        info_procesador["Utilización actual de la CPU"] = psutil.cpu_percent()

        info_cpu = {}
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if ':' in line:
                        parts = line.split(':')
                        key = parts[0].strip()
                        value = parts[1].strip()
                        info_cpu[key] = value
        except FileNotFoundError:
            info_cpu["Error"] = "No se pudo acceder a la información detallada de la CPU"

        info_procesador["Información detallada sobre la CPU"] = info_cpu

        table_data = []
        for key, value in info_procesador.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    table_data.append([sub_key, sub_value])
            else:
                table_data.append([key, value])
        return table_data

    @staticmethod    
    def obtener_informacion_memoria():
        mem = psutil.virtual_memory()

        swap = psutil.swap_memory()

        info_memoria = {
            "Memoria RAM Total (MB)": mem.total,
            "Memoria RAM Disponible (MB)": mem.available,
            "Uso de Memoria RAM (%)": mem.percent,
            "Memoria Swap Total (MB)": swap.total,
            "Memoria Swap Disponible (MB)": swap.free,
            "Uso de Memoria Swap (%)": swap.percent
        }

        return info_memoria

    @staticmethod
    def obtener_informacion_completa():
        info = {}
        # Obtener la información del sistema
        info_sistema = Informacion.obtener_info_sistema()
        info["Usuario"] = info_sistema["Usuario"]
        info["Sistema Operativo"] = info_sistema["Sistema Operativo"]
        info["Versión de Sistema"] = info_sistema["Versión de Sistema"]
        info["Versión de Ubuntu"] = info_sistema["Versión de Ubuntu"]
        # Info tarjeta gráfica
        info["Información de la Tarjeta Gráfica"] = Informacion.obtener_informacion_tarjeta_grafica()
        # Obtener la información de los dns
        info_dns = Informacion.obtener_servidores_dns()
        dns_local = ", ".join(info_dns["dns_local"])
        dns_local = dns_local.replace("[", "").replace("]", "").replace("'", "")
        info["dns local"] = dns_local
        dns_publico = ", ".join(info_dns["dns_publico"])
        dns_publico = dns_publico.replace("[", "").replace("]", "").replace("'", "")
        info["dns publico"] = dns_publico
        # Obtener el resto de la información
        info["Tipo de Escritorio"] = Informacion.obtener_tipo_escritorio()
        info["Interfaces de Red"] = Informacion.obtener_interfaces_red()
        info["Dirección IP Local"] = Informacion.obtener_direccion_ip_local()
        info["Dirección IP Pública"] = Informacion.obtener_direccion_ip_publica()
        info["Tiempo de Actividad"] = Informacion.get_tiempo_actividad()
        info["Tiempo de Arranque"] = Informacion.obtener_tiempo_arranque()
        #info["Fabricante del Equipo"] = Informacion.get_fabricante_equipo()
        info["Zona Horaria"] = Informacion.get_zona_horaria()
        info["Información del Procesador"] = Informacion.obtener_informacion_procesador()
        info["Información de la Memoria"] = Informacion.obtener_informacion_memoria()
        return info

