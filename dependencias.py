import subprocess
import sys
from password import obtener_contrasena
from tkinter import messagebox
import os

# Paquetes APT necesarios para las funciones del programa
DEPENDENCIAS_SISTEMA = [
    "samba",
    "nmap",
    "net-tools",
    "ethtool",
    "iw",
    "gnome-terminal",
    "python3-psutil",
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


def obtener_ruta_requirements():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "requirements.txt")


def _normalizar_nombre_pip(nombre):
    return nombre.lower().replace("_", "-")


def _leer_requirements():
    required_packages = {}
    requirements_path = obtener_ruta_requirements()
    with open(requirements_path, "r") as req_file:
        for line in req_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line:
                pkg, version = line.split("==", 1)
                required_packages[pkg.strip()] = version.strip()
            else:
                required_packages[line] = None
    return required_packages


def _paquetes_pip_instalados():
    installed_packages = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"],
        universal_newlines=True,
    )
    instalados = {}
    for pkg in installed_packages.splitlines():
        if "==" in pkg:
            nombre, version = pkg.split("==", 1)
        else:
            nombre, version = pkg, None
        instalados[_normalizar_nombre_pip(nombre)] = version
    return instalados


def paquetes_sistema_faltantes():
    faltantes = []
    for dependencia in DEPENDENCIAS_SISTEMA:
        proceso = subprocess.run(
            ["dpkg", "-s", dependencia],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proceso.returncode != 0:
            faltantes.append(dependencia)
    return faltantes


def paquetes_pip_faltantes():
    required_packages = _leer_requirements()
    instalados = _paquetes_pip_instalados()
    faltantes = []
    for pkg, version in required_packages.items():
        instalada = instalados.get(_normalizar_nombre_pip(pkg))
        if instalada is None:
            faltantes.append(pkg if version is None else f"{pkg}=={version}")
        elif version is not None and instalada != version:
            faltantes.append(f"{pkg}=={version}")
    return faltantes


def resumen_dependencias_faltantes():
    return paquetes_sistema_faltantes(), paquetes_pip_faltantes()


def verificar_dependencias_sistema():
    faltantes = paquetes_sistema_faltantes()
    if faltantes:
        mensaje = "Las siguientes dependencias del sistema no están instaladas:\n\n"
        mensaje += "\n".join(faltantes)
        messagebox.showinfo("Dependencias faltantes", mensaje)
        return False
    return True


def verificar_dependencias_pip():
    try:
        faltantes = paquetes_pip_faltantes()
        if faltantes:
            mensaje = "Las siguientes dependencias de Python no están instaladas o tienen versiones incorrectas:\n\n"
            mensaje += "\n".join(faltantes)
            messagebox.showinfo("Dependencias de Python faltantes", mensaje)
            return False
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Error al verificar dependencias de Python: {e}")
        return False


def verificar_dependencias():
    sistema_ok = not paquetes_sistema_faltantes()
    pip_ok = not paquetes_pip_faltantes()
    return sistema_ok and pip_ok


def instalar_dependencias(on_progress=None):
    """
    Instala solo las dependencias de sistema y de Python que faltan.

    Args:
        on_progress: callback opcional (porcentaje, texto) para actualizar la UI
                     desde el hilo principal.

    Returns:
        tuple[bool, str | None]: (éxito, mensaje de error)
    """
    def reportar(valor, texto=""):
        if on_progress:
            on_progress(valor, texto)

    faltan_sistema = paquetes_sistema_faltantes()
    try:
        faltan_pip = paquetes_pip_faltantes()
    except Exception as e:
        return False, f"Error al comprobar dependencias de Python: {e}"

    total = len(faltan_sistema) + (1 if faltan_pip else 0)
    if total == 0:
        reportar(100, "Nada pendiente de instalar")
        return True, None

    progreso_actual = 0
    contrasena = obtener_contrasena()

    for dependencia in faltan_sistema:
        reportar(
            int((progreso_actual / total) * 100),
            f"Instalando {dependencia}...",
        )
        try:
            proceso_instalacion = subprocess.Popen(
                ["sudo", "-S", "apt", "install", "-y", dependencia],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            _salida, error = proceso_instalacion.communicate(input=contrasena + "\n")
            if proceso_instalacion.returncode != 0:
                return False, f"No se pudo instalar {dependencia}: {error}"
            progreso_actual += 1
            reportar(int((progreso_actual / total) * 100), f"{dependencia} instalado")
        except Exception as e:
            return False, f"No se pudo instalar {dependencia}: {e}"

    if faltan_pip:
        reportar(int((progreso_actual / total) * 100), "Instalando paquetes de Python...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + faltan_pip)
            progreso_actual += 1
            reportar(int((progreso_actual / total) * 100), "Paquetes de Python instalados")
        except subprocess.CalledProcessError as e:
            return False, f"No se pudieron instalar las dependencias de Python: {e}"
        except Exception as e:
            return False, f"Error general al instalar dependencias de Python: {e}"

    reportar(100, "Instalación completada")
    return True, None
