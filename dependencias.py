import importlib.util
import subprocess

from password import obtener_contrasena

# Paquetes APT de herramientas (no módulos Python)
DEPENDENCIAS_SISTEMA = [
    "samba",
    "nmap",
    "net-tools",
    "ethtool",
    "iw",
    "gnome-terminal",
    "smartmontools",
    "traceroute",
    "python3-dbus",
    "python3-tk",
    "pciutils",
    "lshw",
    "arp-scan",
    "cups-client",
    "avahi-utils",
]

# Módulo Python → paquete APT. Se comprueba con import, no con pip freeze
# (los paquetes de Ubuntu no aparecen en pip y no hay que reinstalarlos).
DEPENDENCIAS_PYTHON = (
    (("PIL",), "python3-pil"),
    (("PIL.ImageTk",), "python3-pil.imagetk"),
    (("cryptography",), "python3-cryptography"),
    (("psutil",), "python3-psutil"),
    (("matplotlib",), "python3-matplotlib"),
    (("requests",), "python3-requests"),
    (("PyQt5",), "python3-pyqt5"),
    (("netifaces",), "python3-netifaces"),
    (("markdown2",), "python3-markdown2"),
    (("speedtest", "speedtest_cli"), "speedtest-cli"),
    (("nmap",), "python3-nmap"),
)


def _modulo_disponible(nombres):
    for nombre in nombres:
        try:
            if importlib.util.find_spec(nombre) is not None:
                return True
        except (ImportError, ValueError, ModuleNotFoundError):
            continue
    return False


def _paquete_apt_instalado(paquete):
    proceso = subprocess.run(
        ["dpkg", "-s", paquete],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proceso.returncode == 0


def paquetes_sistema_faltantes():
    return [paquete for paquete in DEPENDENCIAS_SISTEMA if not _paquete_apt_instalado(paquete)]


def paquetes_python_faltantes():
    faltantes = []
    vistos = set()
    for modulos, paquete in DEPENDENCIAS_PYTHON:
        if _modulo_disponible(modulos):
            continue
        if paquete not in vistos:
            vistos.add(paquete)
            faltantes.append(paquete)
    return faltantes


def paquetes_pip_faltantes():
    """Compatibilidad: ahora son paquetes APT de Python, no nombres de PyPI."""
    return paquetes_python_faltantes()


def resumen_dependencias_faltantes():
    return paquetes_sistema_faltantes(), paquetes_python_faltantes()


def verificar_dependencias():
    return not paquetes_sistema_faltantes() and not paquetes_python_faltantes()


def instalar_dependencias(on_progress=None):
    """Instala con APT las herramientas y módulos Python que faltan."""

    def reportar(valor, texto=""):
        if on_progress:
            on_progress(valor, texto)

    pendientes = []
    for paquete in paquetes_sistema_faltantes() + paquetes_python_faltantes():
        if paquete not in pendientes:
            pendientes.append(paquete)

    if not pendientes:
        reportar(100, "Nada pendiente de instalar")
        return True, None

    contrasena = obtener_contrasena()
    total = len(pendientes)
    for indice, dependencia in enumerate(pendientes, start=1):
        reportar(int(((indice - 1) / total) * 100), f"Instalando {dependencia}...")
        try:
            proceso = subprocess.run(
                ["sudo", "-S", "-p", "", "apt", "install", "-y", dependencia],
                input=contrasena + "\n",
                capture_output=True,
                text=True,
            )
            if proceso.returncode != 0:
                detalle = (proceso.stderr or proceso.stdout or "error de apt").strip()
                return False, f"No se pudo instalar {dependencia}:\n{detalle}"
        except Exception as error:
            return False, f"No se pudo instalar {dependencia}: {error}"
        reportar(int((indice / total) * 100), f"{dependencia} instalado")

    reportar(100, "Instalación completada")
    return True, None
