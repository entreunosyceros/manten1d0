import importlib
import importlib.util
import subprocess
import sys

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

# Módulos, paquete APT y paquete pip. APT instala en el Python del sistema;
# si el programa corre con otro intérprete (conda, venv) ese paquete no se ve
# y hay que instalar el equivalente pip en el intérprete que está en marcha.
DEPENDENCIAS_PYTHON = (
    (("PIL",), "python3-pil", "pillow"),
    (("PIL.ImageTk",), "python3-pil.imagetk", "pillow"),
    (("cryptography",), "python3-cryptography", "cryptography"),
    (("psutil",), "python3-psutil", "psutil"),
    (("matplotlib",), "python3-matplotlib", "matplotlib"),
    (("requests",), "python3-requests", "requests"),
    (("PyQt5",), "python3-pyqt5", "PyQt5"),
    (("netifaces",), "python3-netifaces", "netifaces"),
    (("markdown2",), "python3-markdown2", "markdown2"),
    (("speedtest", "speedtest_cli"), "speedtest-cli", "speedtest-cli"),
    (("nmap",), "python3-nmap", "python-nmap"),
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


def _modulos_de_paquete(paquete):
    for modulos, paquete_apt, _pip in DEPENDENCIAS_PYTHON:
        if paquete_apt == paquete:
            return modulos
    return None


def _paquete_pip(paquete_apt):
    for _modulos, paquete, pip in DEPENDENCIAS_PYTHON:
        if paquete == paquete_apt:
            return pip
    return None


def paquetes_python_faltantes():
    importlib.invalidate_caches()
    faltantes = []
    vistos = set()
    for modulos, paquete, _pip in DEPENDENCIAS_PYTHON:
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


def _detalle_salida(proceso):
    texto = (proceso.stderr or proceso.stdout or "sin detalle").strip()
    if len(texto) > 1500:
        texto = texto[-1500:]
    return texto


def _instalar_apt(paquete, contrasena):
    try:
        proceso = subprocess.run(
            ["sudo", "-S", "-p", "", "apt", "install", "-y", paquete],
            input=contrasena + "\n",
            capture_output=True,
            text=True,
        )
    except Exception as error:
        return False, str(error)
    if proceso.returncode != 0:
        return False, _detalle_salida(proceso)
    return True, None


def _instalar_pip(paquete):
    try:
        proceso = subprocess.run(
            [sys.executable, "-m", "pip", "install", paquete],
            capture_output=True,
            text=True,
        )
    except Exception as error:
        return False, str(error)
    if proceso.returncode != 0:
        return False, _detalle_salida(proceso)
    return True, None


def _asegurar_modulo(paquete_apt, contrasena, reportar):
    """Deja el módulo importable en el intérprete que ejecuta el programa."""
    modulos = _modulos_de_paquete(paquete_apt)
    pip_name = _paquete_pip(paquete_apt)
    if modulos and _modulo_disponible(modulos):
        return True, None

    errores = []
    if not _paquete_apt_instalado(paquete_apt):
        ok, error = _instalar_apt(paquete_apt, contrasena)
        importlib.invalidate_caches()
        if modulos and _modulo_disponible(modulos):
            return True, None
        if not ok and error:
            errores.append(error)
    elif modulos and not _modulo_disponible(modulos) and pip_name:
        reportar(
            None,
            f"{paquete_apt} está en el sistema, pero este Python no lo ve. Instalando {pip_name}...",
        )

    if modulos and pip_name and not _modulo_disponible(modulos):
        ok, error = _instalar_pip(pip_name)
        importlib.invalidate_caches()
        if _modulo_disponible(modulos):
            return True, None
        if not ok and error:
            errores.append(error)

    if modulos and _modulo_disponible(modulos):
        return True, None
    detalle = "\n".join(errores) or "el módulo sigue sin poder importarse"
    return False, f"No se pudo instalar {paquete_apt}:\n{detalle}"


def instalar_dependencias(on_progress=None):
    """Instala con APT las herramientas y, si hace falta, con pip los módulos Python."""

    def reportar(valor, texto=""):
        if on_progress and valor is not None:
            on_progress(valor, texto)
        elif on_progress and texto:
            on_progress(0, texto)

    sistema = paquetes_sistema_faltantes()
    python = paquetes_python_faltantes()
    pendientes = []
    for paquete in sistema + python:
        if paquete not in pendientes:
            pendientes.append(paquete)

    if not pendientes:
        reportar(100, "Nada pendiente de instalar")
        return True, None

    necesita_apt = list(sistema)
    for paquete in python:
        if not _paquete_apt_instalado(paquete):
            necesita_apt.append(paquete)
    contrasena = obtener_contrasena() if necesita_apt else ""

    total = len(pendientes)
    python_set = set(python)
    for indice, dependencia in enumerate(pendientes, start=1):
        avance = int(((indice - 1) / total) * 100)
        reportar(avance, f"Instalando {dependencia}...")
        if dependencia in python_set:
            ok, error = _asegurar_modulo(dependencia, contrasena, lambda _v, texto: reportar(avance, texto))
            if not ok:
                return False, error
        else:
            ok, error = _instalar_apt(dependencia, contrasena)
            if not ok:
                return False, f"No se pudo instalar {dependencia}:\n{error}"
        reportar(int((indice / total) * 100), f"{dependencia} instalado")

    importlib.invalidate_caches()
    if paquetes_python_faltantes() or paquetes_sistema_faltantes():
        siguen = paquetes_sistema_faltantes() + paquetes_python_faltantes()
        return False, "Siguen sin estar disponibles:\n- " + "\n- ".join(siguen)
    reportar(100, "Instalación completada")
    return True, None
