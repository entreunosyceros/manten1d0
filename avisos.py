"""Avisos del panel de inicio: actualizaciones, disco, SMART y conexión."""

import os
import re
import shutil
import subprocess

import requests


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


def recoger_avisos():
    avisos = []
    avisos.extend(_aviso_conexion())
    avisos.extend(_aviso_disco())
    avisos.extend(_aviso_actualizaciones())
    avisos.extend(_aviso_smart())
    if not avisos:
        avisos.append({
            "nivel": "ok",
            "titulo": "Todo en orden",
            "detalle": "No hay avisos de disco, actualizaciones, SMART ni conexión.",
            "destino": None,
        })
    return avisos


def _aviso_conexion():
    try:
        requests.get("https://www.google.com", timeout=3)
        return []
    except requests.RequestException:
        return [{
            "nivel": "error",
            "titulo": "Sin conexión a Internet",
            "detalle": "No se pudo contactar con la red. Revisa la categoría Internet.",
            "destino": "Internet",
        }]


def _aviso_disco():
    avisos = []
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
        elif porcentaje >= 80:
            nivel = "aviso"
        else:
            continue
        avisos.append({
            "nivel": nivel,
            "titulo": f"{etiqueta} al {porcentaje:.0f}%",
            "detalle": f"Libre: {_tamano(uso.free)} de {_tamano(uso.total)}. Conviene limpiar espacio.",
            "destino": "Sistema",
        })
    return avisos


def _aviso_actualizaciones():
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
                    "detalle": "Abre Sistema → Actualizar Sistema para instalarlas.",
                    "destino": "Sistema",
                }]
            return []
    proceso = _comando(["apt", "list", "--upgradable"], timeout=40)
    lineas = [l for l in (proceso.stdout or "").splitlines() if l and not l.startswith("Listing")]
    if lineas:
        return [{
            "nivel": "aviso",
            "titulo": f"{len(lineas)} actualizaciones pendientes",
            "detalle": "Abre Sistema → Actualizar Sistema para instalarlas.",
            "destino": "Sistema",
        }]
    return []


def _aviso_smart():
    if shutil.which("smartctl") is None:
        return []
    proceso = _comando(["lsblk", "-dn", "-o", "NAME,TYPE"], timeout=10)
    discos = []
    for linea in proceso.stdout.splitlines():
        partes = linea.split()
        if len(partes) >= 2 and partes[-1] == "disk":
            discos.append(partes[0])
    if not discos:
        return []

    contrasena = None
    try:
        from password import CONFIG_FILE, obtener_contrasena
        if os.path.exists(CONFIG_FILE):
            contrasena = obtener_contrasena()
    except Exception:
        contrasena = None

    fallos = []
    ilegibles = 0
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
            continue
        if re.search(
            r"self-assessment test result:\s*FAILED|SMART Health Status:\s*(?!OK)|DISK FAILING",
            texto,
            re.I,
        ) or (resultado.returncode and resultado.returncode & 8):
            fallos.append(disco)
        elif "Permission denied" in texto or "unable to" in texto.lower():
            ilegibles += 1

    avisos = []
    if fallos:
        avisos.append({
            "nivel": "error",
            "titulo": "SMART en fallo: " + ", ".join(fallos),
            "detalle": "Hay discos que no superan el autoinforme SMART. Ábrelos en Salud discos.",
            "destino": "Sistema",
        })
    elif ilegibles == len(discos) and discos:
        avisos.append({
            "nivel": "aviso",
            "titulo": "No se pudo leer el estado SMART",
            "detalle": "Abre Sistema → Salud discos para consultarlo con permisos sudo.",
            "destino": "Sistema",
        })
    return avisos


def _tamano(nbytes):
    valor = float(nbytes)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024:
            return f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{valor:.1f} PB"
