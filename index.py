import sys
import subprocess
import os


def ruta_python_venv():
    return os.path.join(os.getcwd(), "venv", "bin", "python")


def verificar_instalacion_venv():
    try:
        import venv
        return True
    except ImportError:
        return False


def instalar_python3_venv():
    proceso_instalacion = subprocess.Popen(
        ["sudo", "apt-get", "install", "-y", "python3-venv"],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    proceso_instalacion.communicate(input="\n")
    return proceso_instalacion.returncode == 0


def crear_entorno_virtual():
    python_venv = ruta_python_venv()
    if os.path.exists(python_venv):
        return python_venv

    if not verificar_instalacion_venv():
        print("Instalando python3-venv...")
        if not instalar_python3_venv():
            print("No se pudo instalar python3-venv. Saliendo.")
            sys.exit(1)
        print("python3-venv instalado correctamente.")

    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    except Exception as e:
        print(f"No se pudo crear el entorno virtual: {e}")
        sys.exit(1)

    python_venv = ruta_python_venv()
    if not os.path.exists(python_venv):
        print(f"No se encontró el intérprete del entorno virtual en {python_venv}")
        sys.exit(1)
    return python_venv


def instalar_dependencias(python_venv):
    requirements_path = os.path.join(os.getcwd(), "requirements.txt")
    if os.path.exists(requirements_path):
        subprocess.check_call([python_venv, "-m", "pip", "install", "-r", requirements_path])
    else:
        print(f"No se pudo encontrar el archivo {requirements_path}. Saliendo.")
        sys.exit(1)


def main():
    python_venv = crear_entorno_virtual()
    print(f"Usando el entorno virtual: {python_venv}")
    instalar_dependencias(python_venv)
    subprocess.check_call([python_venv, "main.py"])


if __name__ == "__main__":
    main()
