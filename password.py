"""
Funciones y módulos relacionados con la gestión de contraseñas y seguridad.

Imports:
    - tkinter as tk: Para la interfaz gráfica.
    - messagebox desde tkinter: Para mostrar mensajes de alerta.
    - os: Para operaciones de sistema como manipulación de archivos.
    - Fernet desde cryptography.fernet: Para el cifrado de contraseñas.
    - sys: Para interactuar con el sistema.
    - subprocess: Para ejecutar comandos del sistema operativo.

Variables Globales:
    - CLAVE_ARCHIVO (str): Nombre del archivo que almacena la clave de cifrado.
    - CONFIG_FILE (str): Nombre del archivo que guarda la contraseña cifrada.

Funciones:
    - generar_clave(): Genera una clave de cifrado.
    - almacenar_clave(clave, nombre_archivo="clave.key"): Almacena la clave en un archivo.
    - cargar_clave(nombre_archivo="clave.key"): Carga la clave desde un archivo.
    - cifrar_contrasena(contrasena, clave): Cifra una contraseña utilizando una clave.
    - descifrar_contrasena(contra_cifrada, clave): Descifra una contraseña utilizando una clave.
    - obtener_contrasena(): Obtiene la contraseña del usuario, solicitándola si no está almacenada.
    - limpiar_archivos_configuracion(): Elimina los archivos de configuración.
    - almacenar_contrasena(contrasena): Almacena la contraseña cifrada en el archivo de configuración.
    - verificar_contrasena_sudo(contrasena): Verifica si la contraseña proporcionada es válida para utilizar sudo.

Raises:
    - Excepciones generales si ocurre algún error durante la ejecución.
"""

import tkinter as tk
from tkinter import messagebox
import os
from cryptography.fernet import Fernet
import sys
from tooltip import ToolTip
import subprocess
import dialogo_estilo as estilo

# Contraseña cifrada en la carpeta de datos del usuario (escribible también con el .deb)
_DIR_DATOS = os.path.join(os.path.expanduser("~"), ".local", "share", "Manten1d0")
try:
    os.makedirs(_DIR_DATOS, exist_ok=True)
except OSError:
    pass
CLAVE_ARCHIVO = os.path.join(_DIR_DATOS, "clave.key")
CONFIG_FILE = os.path.join(_DIR_DATOS, "config.txt")

# Función para generar una clave de cifrado
def generar_clave():
    return Fernet.generate_key()

# Función para almacenar la clave en un archivo
def almacenar_clave(clave, nombre_archivo="clave.key"):
    with open(nombre_archivo, "wb") as archivo_clave:
        archivo_clave.write(clave)

# Función para cargar la clave desde el archivo
def cargar_clave(nombre_archivo="clave.key"):
    if not os.path.exists(nombre_archivo):
        # Generar una nueva clave y almacenarla en un archivo si no existe
        nueva_clave = generar_clave()
        almacenar_clave(nueva_clave, nombre_archivo)
        return nueva_clave
    else:
        with open(nombre_archivo, "rb") as archivo_clave:
            return archivo_clave.read()

# Función para cifrar la contraseña
def cifrar_contrasena(contrasena, clave):
    cipher_suite = Fernet(clave)
    return cipher_suite.encrypt(contrasena.encode())

# Función para descifrar la contraseña
def descifrar_contrasena(contra_cifrada, clave):
    cipher_suite = Fernet(clave)
    return cipher_suite.decrypt(contra_cifrada).decode()


def _pedir_contrasena_interactiva():
    """Dialogo llamativo para pedir la contraseña de usuario (sudo)."""
    resultado = {"valor": None}
    raiz_propia = False
    padre = getattr(tk, "_default_root", None)
    if padre is None:
        padre = tk.Tk()
        padre.withdraw()
        raiz_propia = True

    win = tk.Toplevel(padre)
    cuerpo = estilo.preparar_dialogo(
        win,
        "Manten1d0 - Contrasena requerida",
        "CONTRASENA REQUERIDA",
        460,
        340,
        topmost=True,
    )

    estilo.etiqueta_titulo(cuerpo, "Escribe aqui la contraseña de tu usuario").pack(anchor="w")
    estilo.etiqueta_texto(
        cuerpo,
        "Manten1d0 la necesita para tareas de administrador "
        "(actualizar, reparar, limpiar, etc.). "
        "Se guarda cifrada solo en esta sesion.",
    ).pack(anchor="w", pady=(6, 12))

    marco_entrada = tk.LabelFrame(
        cuerpo,
        text=" Contraseña de usuario ",
        bg=estilo.BG,
        fg=estilo.TITULO,
        font=("Arial", 10, "bold"),
        padx=10,
        pady=8,
    )
    marco_entrada.pack(fill=tk.X)

    var_clave = tk.StringVar()
    entrada = tk.Entry(
        marco_entrada,
        textvariable=var_clave,
        show="*",
        font=("Arial", 14),
        width=28,
        relief=tk.SOLID,
        borderwidth=2,
        highlightthickness=2,
        highlightbackground=estilo.FRANJA,
        highlightcolor=estilo.BOTON_BG_ACTIVO,
    )
    entrada.pack(fill=tk.X, pady=(2, 6))

    visible = {"si": False}

    def alternar_ver():
        visible["si"] = not visible["si"]
        entrada.config(show="" if visible["si"] else "*")
        btn_ver.config(
            text="Ocultar contraseña" if visible["si"] else "Mostrar contraseña"
        )

    btn_ver = tk.Button(
        marco_entrada,
        text="Mostrar contraseña",
        command=alternar_ver,
        width=18,
    )
    btn_ver.pack(anchor="w")
    ToolTip(btn_ver, "Muestra u oculta lo escrito para evitar errores")

    def aceptar(_evento=None):
        resultado["valor"] = var_clave.get()
        win.destroy()

    def cancelar():
        resultado["valor"] = None
        win.destroy()

    fila = tk.Frame(cuerpo, bg=estilo.BG)
    fila.pack(fill=tk.X, pady=(16, 4))
    estilo.boton_primario(fila, "Continuar", aceptar).pack(side=tk.LEFT, padx=(0, 8))
    estilo.boton_secundario(fila, "Cancelar", cancelar).pack(side=tk.LEFT)

    entrada.bind("<Return>", aceptar)
    win.protocol("WM_DELETE_WINDOW", cancelar)

    try:
        win.grab_set()
    except tk.TclError:
        pass
    win.after(50, entrada.focus_set)
    win.wait_window()

    # Si creamos la raiz solo para este dialogo, la dejamos retirada
    # para que messagebox pueda usarla; se destruye al salir de obtener_contrasena.
    if raiz_propia:
        try:
            padre.withdraw()
            padre._manten1d0_temp = True
        except tk.TclError:
            pass

    return resultado["valor"]


def _cerrar_raiz_temporal():
    raiz = getattr(tk, "_default_root", None)
    if raiz is not None and getattr(raiz, "_manten1d0_temp", False):
        try:
            raiz.destroy()
        except tk.TclError:
            pass


def obtener_contrasena():
    contrasena_verificada = False

    while True:
        # Verificar si la contraseña está guardada en el archivo CONFIG_FILE
        if not contrasena_verificada and os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "rb") as file:
                contrasena_cifrada = file.read()
            contrasena = descifrar_contrasena(contrasena_cifrada, cargar_clave(CLAVE_ARCHIVO))
            if verificar_contrasena_sudo(contrasena):
                contrasena_verificada = True
                _cerrar_raiz_temporal()
                return contrasena

        # Solicitar la contraseña al usuario (dialogo propio, mas visible)
        contrasena = _pedir_contrasena_interactiva()
        if contrasena is None:
            limpiar_archivos_configuracion()
            _cerrar_raiz_temporal()
            sys.exit()
        elif contrasena.strip() == "":
            limpiar_archivos_configuracion()
            messagebox.showwarning(
                "Contrasena requerida",
                "Debes escribir tu contraseña de usuario para continuar.",
            )
        else:
            if verificar_contrasena_sudo(contrasena):
                contrasena_verificada = True
                almacenar_contrasena(contrasena)
                _cerrar_raiz_temporal()
                return contrasena
            else:
                limpiar_archivos_configuracion()
                messagebox.showerror(
                    "Contrasena no valida",
                    "La contraseña no es correcta o no permite usar sudo.\n"
                    "Vuelve a intentarlo.",
                )

# Función para eliminar los archivos de configuración
def limpiar_archivos_configuracion():
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    if os.path.exists(CLAVE_ARCHIVO):
        os.remove(CLAVE_ARCHIVO)

def almacenar_contrasena(contrasena):
    if contrasena is not None:  # Verificar si se ha ingresado una contraseña
        contrasena_cifrada = cifrar_contrasena(contrasena, cargar_clave(CLAVE_ARCHIVO))
        with open(CONFIG_FILE, "wb") as file:
            file.write(contrasena_cifrada)

def verificar_contrasena_sudo(contrasena):
    try:
        # Intentamos listar el directorio de root. Si la contraseña permite sudo devolverá 0
        proceso = subprocess.run(['sudo', '-k', '-S', 'ls', '/root'], input=contrasena, capture_output=True, text=True, timeout=5)
        if proceso.returncode == 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error al verificar la contraseña: {e}")
        return False

