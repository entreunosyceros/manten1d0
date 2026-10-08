"""Diagnóstico del equipo para el panel de Inicio (checklist ok / aviso / error)."""

import os
import re
import shutil
import subprocess

import requests

try:
    import psutil
except ImportError:
    psutil = None

_CHIPS_CPU = ("coretemp", "k10temp", "cpu_thermal", "cpu-thermal", "zenpower", "atk0110")


def _comando(args, timeout=20):
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


def analizar_equipo():
    """Devuelve la checklist completa del equipo (siempre un ítem por comprobación)."""
    items = []
    items.extend(_check_conexion())
    items.extend(_check_disco())
    items.extend(_check_reinicio())
    items.extend(_check_actualizaciones())
    items.extend(_check_smart())
    items.extend(_check_temperatura())
    items.extend(_check_servicios_fallidos())
    items.extend(_check_ufw())
    return items


def listar_unidades_fallidas():
    """Lista unidades systemd en estado failed. Devuelve (unidades, error_o_None)."""
    proceso = _comando(
        ["systemctl", "--failed", "--no-pager", "--plain", "--no-legend"],
        timeout=40,
    )
    if proceso.returncode not in (0, 1):
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


def estado_ufw():
    """Estado del cortafuegos sin pedir sudo: activo, inactivo, no_instalado o desconocido."""
    if shutil.which("ufw") is None:
        return "no_instalado"
    proceso = _comando(["ufw", "status"], timeout=10)
    if proceso.returncode == 0:
        texto = (proceso.stdout or "").lower()
        if "inactive" in texto:
            return "inactivo"
        if "active" in texto:
            return "activo"
    try:
        with open("/etc/ufw/ufw.conf", encoding="utf-8", errors="replace") as archivo:
            for linea in archivo:
                if linea.strip().upper().startswith("ENABLED="):
                    valor = linea.split("=", 1)[1].strip().lower()
                    return "activo" if valor == "yes" else "inactivo"
    except OSError:
        pass
    return "desconocido"


def _check_conexion():
    try:
        requests.get("https://www.google.com", timeout=3)
        return [{
            "nivel": "ok",
            "titulo": "Internet funcionando",
            "detalle": "Hay conexión con la red. Pulsa para abrir el asistente de Internet.",
            "destino": "Internet",
            "panel": "AsistenteInternet",
        }]
    except requests.RequestException:
        return [{
            "nivel": "error",
            "titulo": "Sin conexión a Internet",
            "detalle": "No se pudo contactar con la red. Pulsa para el asistente de problemas de Internet.",
            "destino": "Internet",
            "panel": "AsistenteInternet",
        }]


def _check_disco():
    items = []
    puntos = [("/", "Disco raíz (/)")]
    home = os.path.expanduser("~")
    if os.path.ismount(home) or home != "/":
        puntos.append((home, "Carpeta personal"))
    vistos = set()
    for ruta, etiqueta in puntos:
        try:
            uso = shutil.disk_usage(ruta)
        except OSError:
            continue
        clave = (uso.total, uso.used)
        if clave in vistos:
            continue
        vistos.add(clave)
        porcentaje = (uso.used / uso.total) * 100 if uso.total else 0
        if porcentaje >= 90:
            nivel = "error"
            detalle = _detalle_disco(ruta, uso)
            panel = "LimpiezaEspacio"
        elif porcentaje >= 80:
            nivel = "aviso"
            detalle = _detalle_disco(ruta, uso)
            panel = "LimpiezaEspacio"
        else:
            nivel = "ok"
            detalle = (
                f"Libre: {_tamano(uso.free)} de {_tamano(uso.total)}. "
                "Pulsa para abrir la limpieza de disco."
            )
            panel = "LimpiezaEspacio"
        items.append({
            "nivel": nivel,
            "titulo": f"{etiqueta} al {porcentaje:.0f}%",
            "detalle": detalle,
            "destino": "Sistema",
            "panel": panel,
        })
    if not items:
        items.append({
            "nivel": "info",
            "titulo": "Espacio en disco",
            "detalle": "No se pudo consultar el uso del disco.",
            "destino": "Sistema",
            "panel": "EspacioDiscos",
        })
    return items


_PISTAS_CARPETA = {
    ".cache": "caché",
    ".thumbnails": "miniaturas",
    ".config": "configuración de programas",
    ".local": "datos de programas",
    ".var": "Flatpak",
    "snap": "aplicaciones Snap",
    "VirtualBox": "máquinas virtuales",
    "VirtualBox VMs": "máquinas virtuales",
    "Descargas": "descargas",
    "Downloads": "descargas",
    "Documentos": "documentos",
    "Documents": "documentos",
    "Imágenes": "imágenes",
    "Pictures": "imágenes",
    "Vídeos": "vídeos",
    "Videos": "vídeos",
    ".thunderbird": "correo",
    ".mozilla": "Firefox",
}


def _carpetas_mayores(ruta, limite=3):
    """Las carpetas de primer nivel que más ocupan, sin cruzar a otro disco."""
    proceso = _comando(["du", "-x", "-B1", "--max-depth=1", "--", ruta], timeout=45)
    if not proceso.stdout:
        return []
    base = os.path.abspath(ruta)
    filas = []
    for linea in proceso.stdout.splitlines():
        partes = linea.split("\t", 1)
        if len(partes) != 2:
            continue
        try:
            tam = int(partes[0])
        except ValueError:
            continue
        camino = partes[1].rstrip("/")
        if os.path.abspath(camino) == base:
            continue
        filas.append((tam, os.path.basename(camino) or camino))
    filas.sort(reverse=True)
    return filas[:limite]


def _detalle_disco(ruta, uso):
    libre = f"Libre: {_tamano(uso.free)} de {_tamano(uso.total)}."
    mayores = _carpetas_mayores(ruta)
    if not mayores:
        return libre + " Conviene limpiar espacio."
    trozos = []
    for tam, nombre in mayores:
        pista = _PISTAS_CARPETA.get(nombre)
        if pista:
            trozos.append(f"{nombre} ({_tamano(tam)}, {pista})")
        else:
            trozos.append(f"{nombre} ({_tamano(tam)})")
    return (
        libre
        + " Lo que más ocupa: "
        + ", ".join(trozos)
        + ". Se puede borrar sin miedo: caché, miniaturas y papelera. "
        "No borres máquinas virtuales ni documentos."
    )


def _check_reinicio():
    if not os.path.isfile("/var/run/reboot-required"):
        return [{
            "nivel": "ok",
            "titulo": "No hace falta reiniciar",
            "detalle": "No hay reinicio pendiente tras actualizaciones.",
            "destino": None,
        }]
    detalle = "Una actualización no termina de aplicarse hasta reiniciar."
    paquetes = _paquetes_reinicio()
    if paquetes:
        detalle += f" Afecta a: {paquetes}."
    detalle += " Pulsa aquí para reiniciar."
    return [{
        "nivel": "aviso",
        "titulo": "Hay que reiniciar el equipo",
        "detalle": detalle,
        "destino": None,
        "accion": "reiniciar",
    }]


def _paquetes_reinicio():
    ruta = "/var/run/reboot-required.pkgs"
    if not os.path.isfile(ruta):
        return ""
    try:
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            nombres = [linea.strip() for linea in archivo if linea.strip()]
    except OSError:
        return ""
    if not nombres:
        return ""
    texto = ", ".join(nombres[:4])
    if len(nombres) > 4:
        texto += "..."
    return texto


def _check_actualizaciones():
    comprobador = "/usr/lib/update-notifier/apt-check"
    if os.path.exists(comprobador):
        proceso = _comando([comprobador], timeout=30)
        texto = (proceso.stderr or proceso.stdout or "").strip()
        if ";" in texto:
            try:
                pendientes, seguridad = texto.split(";", 1)
                total = int(pendientes)
                sec = int(seguridad)
            except ValueError:
                total, sec = 0, 0
            if total > 0:
                extra = f" ({sec} de seguridad)" if sec else ""
                return [{
                    "nivel": "aviso" if sec == 0 else "error",
                    "titulo": f"{total} actualizaciones pendientes{extra}",
                    "detalle": "Abre Actualizar todo o Sistema -> Actualizar Sistema para instalarlas.",
                    "destino": "Sistema",
                    "panel": "ActualizarTodo",
                }]
            return [{
                "nivel": "ok",
                "titulo": "Sistema actualizado",
                "detalle": "No hay actualizaciones APT pendientes.",
                "destino": "Sistema",
                "panel": "ActualizarTodo",
            }]
    proceso = _comando(["apt", "list", "--upgradable"], timeout=40)
    lineas = [l for l in (proceso.stdout or "").splitlines() if l and not l.startswith("Listing")]
    if lineas:
        return [{
            "nivel": "aviso",
            "titulo": f"{len(lineas)} actualizaciones pendientes",
            "detalle": "Abre Actualizar todo o Sistema -> Actualizar Sistema para instalarlas.",
            "destino": "Sistema",
            "panel": "ActualizarTodo",
        }]
    return [{
        "nivel": "ok",
        "titulo": "Sistema actualizado",
        "detalle": "No hay actualizaciones APT pendientes.",
        "destino": "Sistema",
        "panel": "ActualizarTodo",
    }]


def _check_smart():
    if shutil.which("smartctl") is None:
        return [{
            "nivel": "info",
            "titulo": "SMART no disponible",
            "detalle": "Instala smartmontools o abre Salud discos para más detalle.",
            "destino": "Sistema",
            "panel": "SaludDiscos",
        }]
    proceso = _comando(["lsblk", "-dn", "-o", "NAME,TYPE"], timeout=10)
    discos = []
    for linea in proceso.stdout.splitlines():
        partes = linea.split()
        if len(partes) >= 2 and partes[-1] == "disk":
            discos.append(partes[0])
    if not discos:
        return [{
            "nivel": "info",
            "titulo": "SMART: sin discos detectados",
            "detalle": "No se encontraron discos para consultar.",
            "destino": "Sistema",
            "panel": "SaludDiscos",
        }]

    contrasena = None
    try:
        from password import CONFIG_FILE, obtener_contrasena
        if os.path.exists(CONFIG_FILE):
            contrasena = obtener_contrasena()
    except Exception:
        contrasena = None

    fallos = []
    ilegibles = 0
    ok = 0
    for disco in discos:
        args = ["smartctl", "-H", f"/dev/{disco}"]
        if contrasena:
            resultado = subprocess.run(
                ["sudo", "-S", "-p", "", *args],
                input=f"{contrasena}\n",
                capture_output=True,
                text=True,
                timeout=25,
            )
        else:
            resultado = _comando(args, timeout=25)
        texto = (resultado.stdout or "") + (resultado.stderr or "")
        if re.search(r"PASSED|Health Status:\s*OK", texto, re.I):
            ok += 1
            continue
        if re.search(
            r"self-assessment test result:\s*FAILED|SMART Health Status:\s*(?!OK)|DISK FAILING",
            texto,
            re.I,
        ) or (resultado.returncode and resultado.returncode & 8):
            fallos.append(disco)
        elif "Permission denied" in texto or "unable to" in texto.lower():
            ilegibles += 1

    if fallos:
        return [{
            "nivel": "error",
            "titulo": "SMART en fallo: " + ", ".join(fallos),
            "detalle": "Hay discos que no superan el autoinforme SMART. Ábrelos en Salud discos.",
            "destino": "Sistema",
            "panel": "SaludDiscos",
        }]
    if ilegibles == len(discos):
        return [{
            "nivel": "aviso",
            "titulo": "No se pudo leer el estado SMART",
            "detalle": "Abre Salud discos para consultarlo con permisos de administrador.",
            "destino": "Sistema",
            "panel": "SaludDiscos",
        }]
    return [{
        "nivel": "ok",
        "titulo": "Discos en buen estado (SMART)",
        "detalle": f"{ok} disco(s) superan el autoinforme. Pulsa para ver el detalle.",
        "destino": "Sistema",
        "panel": "SaludDiscos",
    }]


def _lectura_valida(sensor):
    """Descarta lecturas absurdas (p. ej. high/critical absurdos de algunos NVMe)."""
    try:
        actual = float(sensor.current)
    except (TypeError, ValueError, AttributeError):
        return False
    if actual < -20 or actual > 125:
        return False
    high = getattr(sensor, "high", None)
    critical = getattr(sensor, "critical", None)
    for limite in (high, critical):
        if limite is None:
            continue
        try:
            if float(limite) > 200:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _elegir_sensor_cpu(temperaturas):
    """Elige el sensor de CPU más representativo entre los chips conocidos."""
    preferidos = []
    for chip in _CHIPS_CPU:
        if chip not in temperaturas:
            continue
        for sensor in temperaturas[chip]:
            if not _lectura_valida(sensor):
                continue
            etiqueta = (getattr(sensor, "label", None) or "").strip().lower()
            preferidos.append((chip, sensor, etiqueta))
    if preferidos:
        for chip, sensor, etiqueta in preferidos:
            if etiqueta == "package id 0" or etiqueta.startswith("tctl"):
                return chip, sensor
        return preferidos[0][0], preferidos[0][1]

    candidatos = []
    for chip, sensores in temperaturas.items():
        chip_l = chip.lower()
        if chip_l.startswith("nvme") or "amdgpu" in chip_l:
            continue
        for sensor in sensores:
            if not _lectura_valida(sensor):
                continue
            candidatos.append((chip, sensor))
    if not candidatos:
        return None, None
    return max(candidatos, key=lambda par: float(par[1].current))


def _temperatura_sysfs():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", encoding="utf-8") as archivo:
            return int(archivo.read().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def _leer_temperatura_cpu():
    """Devuelve dict con current/high/critical o None si no hay sensores."""
    if psutil is not None:
        try:
            temperaturas = psutil.sensors_temperatures() or {}
        except Exception:
            temperaturas = {}
        if temperaturas:
            _chip, sensor = _elegir_sensor_cpu(temperaturas)
            if sensor is not None:
                high = getattr(sensor, "high", None)
                critical = getattr(sensor, "critical", None)
                try:
                    high = float(high) if high is not None and float(high) <= 200 else None
                except (TypeError, ValueError):
                    high = None
                try:
                    critical = (
                        float(critical) if critical is not None and float(critical) <= 200 else None
                    )
                except (TypeError, ValueError):
                    critical = None
                _cores = []
                for _s in (temperaturas.get("coretemp") or []) + (
                    temperaturas.get("k10temp") or []
                ):
                    _lab = (getattr(_s, "label", None) or "").strip().lower()
                    if _lab.startswith("core") or _lab.startswith("tdie"):
                        try:
                            _cores.append(float(_s.current))
                        except (TypeError, ValueError):
                            pass
                return {
                    "current": float(sensor.current),
                    "high": high,
                    "critical": critical,
                    "chip": _chip,
                    "label": getattr(sensor, "label", None),
                    "core_min": min(_cores) if _cores else None,
                    "core_max": max(_cores) if _cores else None,
                    "core_avg": (sum(_cores) / len(_cores)) if _cores else None,
                }
    valor = _temperatura_sysfs()
    if valor is None:
        return None
    return {"current": valor, "high": None, "critical": None}


def _leer_ventiladores():
    """Lista de (nombre, rpm). Vacía si no hay sensores de ventilador."""
    if psutil is None or not hasattr(psutil, "sensors_fans"):
        return []
    try:
        fans = psutil.sensors_fans() or {}
    except Exception:
        return []
    resultado = []
    for chip, entradas in fans.items():
        for entrada in entradas:
            try:
                rpm = int(entrada.current)
            except (TypeError, ValueError, AttributeError):
                continue
            etiqueta = (getattr(entrada, "label", None) or "").strip() or chip
            resultado.append((etiqueta, rpm))
    return resultado


def _check_temperatura():
    datos = _leer_temperatura_cpu()
    if datos is None:
        return [{
            "nivel": "info",
            "titulo": "Temperatura no disponible",
            "detalle": "No hay sensores de temperatura legibles en este equipo.",
            "destino": "Información",
        }]

    actual = datos["current"]
    high = datos["high"]
    critical = datos["critical"]
    umbral_aviso = high if high is not None else 75.0
    umbral_error = critical if critical is not None else 90.0

    if actual >= umbral_error:
        nivel = "error"
        titulo = "El equipo está muy caliente"
    elif actual >= umbral_aviso:
        nivel = "aviso"
        titulo = "El equipo va caliente"
    else:
        nivel = "ok"
        titulo = f"Temperatura normal ({actual:.0f} °C)"

    partes = [f"CPU (paquete) {actual:.0f} °C"]
    cmin, cmax = datos.get("core_min"), datos.get("core_max")
    if cmin is not None and cmax is not None:
        partes.append(f"núcleos {cmin:.0f}-{cmax:.0f} °C")
    if high is not None:
        partes.append(f"aviso del sensor a {high:.0f} °C")
    elif critical is not None:
        partes.append(f"crítico del sensor a {critical:.0f} °C")

    fans = _leer_ventiladores()
    fan_parado = False
    if fans:
        textos_fan = []
        for nombre, rpm in fans[:3]:
            textos_fan.append(f"{nombre} {rpm} rpm")
            if rpm == 0 and nivel in ("aviso", "error"):
                fan_parado = True
        partes.append("Ventilador: " + ", ".join(textos_fan))
        if len(fans) > 3:
            partes.append(f"y {len(fans) - 3} más")

    if fan_parado:
        if nivel == "aviso":
            nivel = "error"
            titulo = "El equipo está muy caliente"
        partes.append("hay un ventilador a 0 rpm")

    if len(partes) == 1:
        detalle = partes[0] + ". Pulsa para ver la información del equipo."
    else:
        detalle = partes[0] + " (" + "; ".join(partes[1:]) + "). Pulsa para ver la información del equipo."
    return [{
        "nivel": nivel,
        "titulo": titulo,
        "detalle": detalle,
        "destino": "Información",
    }]


def _check_servicios_fallidos():
    unidades, error = listar_unidades_fallidas()
    if error:
        return [{
            "nivel": "aviso",
            "titulo": "No se pudieron listar servicios fallidos",
            "detalle": error,
            "destino": "Sistema",
            "panel": "RepararUbuntu",
        }]
    if not unidades:
        return [{
            "nivel": "ok",
            "titulo": "Ningún servicio ha fallado",
            "detalle": "systemd no marca unidades en fallo. Pulsa para abrir servicios que fallan.",
            "destino": "Sistema",
            "panel": "ServiciosFallidos",
        }]
    nombres = ", ".join(u["unidad"] for u in unidades[:4])
    if len(unidades) > 4:
        nombres += "..."
    return [{
        "nivel": "error",
        "titulo": f"{len(unidades)} servicio(s) han fallado",
        "detalle": f"{nombres}. Pulsa para reparaciones guiadas (reiniciar por servicio).",
        "destino": "Sistema",
        "panel": "RepararUbuntu",
    }]


def _check_ufw():
    estado = estado_ufw()
    if estado == "no_instalado":
        return [{
            "nivel": "aviso",
            "titulo": "Cortafuegos no instalado",
            "detalle": "ufw no está en el sistema. Puedes instalarlo desde Centro de seguridad.",
            "destino": "Sistema",
            "panel": "CentroSeguridad",
        }]
    if estado == "activo":
        return [{
            "nivel": "ok",
            "titulo": "Firewall activo",
            "detalle": "ufw está activado. Pulsa para abrir el Centro de seguridad.",
            "destino": "Sistema",
            "panel": "CentroSeguridad",
        }]
    if estado == "inactivo":
        return [{
            "nivel": "aviso",
            "titulo": "Firewall desactivado",
            "detalle": "ufw está instalado pero inactivo. Pulsa para activarlo si lo necesitas.",
            "destino": "Sistema",
            "panel": "CentroSeguridad",
        }]
    return [{
        "nivel": "info",
        "titulo": "Estado del firewall desconocido",
        "detalle": "No se pudo leer ufw sin privilegios. Abre Centro de seguridad para consultarlo.",
        "destino": "Sistema",
        "panel": "CentroSeguridad",
    }]


def _tamano(nbytes):
    valor = float(nbytes)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024:
            return f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{valor:.1f} PB"
