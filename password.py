"""
Funciones y módulos relacionados con la gestión de contraseñas y seguridad.

Imports:
    - tkinter as tk: Para la interfaz gráfica.
    - messagebox desde tkinter: Para mostrar mensajes de alerta.
    - os: Para operaciones de sistema como manipulación de archivos.
    - Fernet desde cryptography.fernet: Para el cifrado de contraseñas.
    - threading: Para ejecutar operaciones en segundo plano.
    - Popen, PIPE desde subprocess: Para ejecutar comandos en el sistema operativo.
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
    - solicitar_contrasena_y_ejecutar(funcion, mostrar_output=True): Solicita la contraseña al usuario y ejecuta una función con ella, mostrando el progreso.

Raises:
    - Excepciones generales si ocurre algún error durante la ejecución.
"""

import tkinter as tk
from tkinter import messagebox
import os
from cryptography.fernet import Fernet
import threading
from subprocess import Popen, PIPE
import sys
from tooltip import ToolTip
import subprocess
import base64

# Verificar y cargar la clave de cifrado
CLAVE_ARCHIVO = "clave.key" # clave de cifrado
CONFIG_FILE = "config.txt" # archivo en el que guardamos la clave de usuario

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
                return contrasena

        # Solicitar la contraseña al usuario
        contrasena = tk.simpledialog.askstring("Contraseña", "Por favor, escrite tu contraseña de usuario:", show='*')
        if contrasena is None:
            limpiar_archivos_configuracion()
            sys.exit()
        elif contrasena.strip() == "":
            limpiar_archivos_configuracion()
            messagebox.showwarning("Contraseña requerida", "Debes ingresar una contraseña.")
        else:
            if verificar_contrasena_sudo(contrasena):
                contrasena_verificada = True
                almacenar_contrasena(contrasena)
                return contrasena
            else:
                limpiar_archivos_configuracion()
                messagebox.showerror("Contraseña Inválida", "Se necesita una contraseña válida para utilizar sudo.")

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


# Función para solicitar la contraseña al usuario y ejecutar una función con ella
def solicitar_contrasena_y_ejecutar(funcion, mostrar_output=True):
    contrasena = obtener_contrasena()
    if contrasena is None:
        messagebox.showwarning("Contraseña requerida", "Debes ingresar una contraseña.")
        return
    elif not verificar_contrasena_sudo(contrasena):
        messagebox.showerror("Contraseña Inválida", "Se necesita una contraseña válida para utilizar sudo.")
        return
    else:
        if mostrar_output:
            ventana_resultado = tk.Toplevel()
            ventana_resultado.title("Resultado de la Operación")

            etiqueta_progreso = tk.Label(ventana_resultado, text="Progreso:")
            etiqueta_progreso.pack(pady=5)

            texto_output = tk.Text(ventana_resultado, height=10, width=60)
            texto_output.pack(padx=10, pady=5)

            boton_cerrar = tk.Button(ventana_resultado, text="Cerrar", command=ventana_resultado.destroy)
            boton_cerrar.pack(pady=5)
            ToolTip(boton_cerrar, "Cierra esta ventana cuando termine el comando")

            # Deshabilitar el botón de cerrar mientras se está ejecutando el comando
            boton_cerrar.config(state=tk.DISABLED)

            def actualizar_output(line):
                texto_output.config(state=tk.NORMAL)
                texto_output.insert(tk.END, line + "\n")
                texto_output.config(state=tk.DISABLED)
                texto_output.see(tk.END)  # Desplazar hacia abajo para mostrar el último texto
                ventana_resultado.update()  # Actualizar la ventana para mostrar los cambios

            def ejecucion_contrasena():
                returncode = funcion(contrasena, actualizar_output)
                boton_cerrar.config(state=tk.NORMAL)  # Habilitar el botón de cerrar después de la ejecución
                if returncode == 0:
                    etiqueta_progreso.config(text="Operación completada exitosamente", fg="green")
                else:
                    etiqueta_progreso.config(text=f"Error al ejecutar la operación. Código de salida: {returncode}", fg="red")

            etiqueta_progreso = tk.Label(ventana_resultado, text="Ejecutando...", fg="blue")
            etiqueta_progreso.pack(pady=10)

            # Ejecutar el comando en un hilo separado para que la interfaz no se bloquee
            threading.Thread(target=ejecucion_contrasena).start()
        else:
            return funcion(contrasena)
        

def cargar_clave_maestra(contrasena, salt):
    import base64

    # Combina la contraseña y el salt
    contrasena_salt = contrasena + salt

    # Codificar la contraseña y el salt con base64
    contrasena_salt_bytes = contrasena_salt.encode('utf-8')
    contrasena_salt_base64 = base64.urlsafe_b64encode(contrasena_salt_bytes)

    # Asegurar que la clave tenga 32 bytes llenando con '=' si es necesario
    clave_maestra = contrasena_salt_base64.ljust(32, b'=')

    return clave_maestra 