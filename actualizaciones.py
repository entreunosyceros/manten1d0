"""
Script de actualización de programas a través de GitHub.

Imports:
    - tkinter as tk: Para la creación de interfaces gráficas.
    - requests: Para realizar solicitudes HTTP.
    - wget: Para descargar archivos de la web.
    - subprocess: Para ejecutar procesos del sistema.
    - obtener_contrasena desde password: Para obtener la contraseña de sudo.
    - messagebox desde tkinter: Para mostrar mensajes de alerta.
    - os: Para realizar operaciones relacionadas con el sistema operativo.
    - sys: Para interactuar con el intérprete de Python.
    - preferencias: Para ajustar las preferencias de la interfaz.

Functions:
    - instalar_paquete_deb(archivo_deb): Instala un paquete .deb en el sistema.
    - mostrar_ventana_actualizaciones(): Muestra una ventana para buscar actualizaciones del programa.

Raises:
    - Exception: Captura errores generales y los muestra en una ventana emergente.
"""

import tkinter as tk
import requests
import wget
import subprocess
from password import obtener_contrasena
from tkinter import messagebox
import os
import sys
import preferencias
import configparser
from tooltip import ToolTip

def obtener_version_actual():
    # Obtener el directorio del archivo que llama a la función
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    # Combinar el directorio con el nombre del archivo config.ini
    ruta_config = os.path.join(directorio_actual, 'config.ini')
    
    config = configparser.ConfigParser()
    config.read(ruta_config)
    return config['Version']['actual']


def instalar_paquete_deb(archivo_deb):
    """
    Instala un paquete .deb en el sistema utilizando el comando 'apt install'. Sobreescibe una instalación anterior si la hubiese.

    Parameters:
        archivo_deb (str): La ruta al archivo .deb que se va a instalar.

    """
    contrasena_sudo = obtener_contrasena()  # Obtener la contraseña de sudo

    # Obtener la ruta absoluta del archivo .deb
    ruta_absoluta = os.path.abspath(archivo_deb)

    # Comando para instalar el paquete .deb usando sudo
    comando_instalacion = ['sudo', '-S', 'apt', 'install', ruta_absoluta]

    # Ejecutar el proceso de instalación con sudo y la contraseña obtenida
    proceso_instalacion = subprocess.Popen(comando_instalacion, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    _, error = proceso_instalacion.communicate(input=contrasena_sudo + "\n")

    if proceso_instalacion.returncode == 0:
        messagebox.showinfo("Instalación exitosa", "Se ha instalado correctamente la última versión del programa.")
        # Eliminar el archivo .deb después de la instalación
        os.remove(archivo_deb)
        # Solicitar al usuario que reinicie el programa
        if messagebox.askyesno("Reiniciar programa", "Se requiere reiniciar el programa para aplicar los cambios. ¿Deseas reiniciar ahora?"):
            # Reiniciar el programa
            python = sys.executable
            os.execl(python, python, *sys.argv)
    else:
        messagebox.showerror("Error de instalación", f"Error durante la actualización del programa:\n{error}")

def mostrar_ventana_actualizaciones():
    
    # Obtener la versión actual del programa desde el archivo de configuración
    version_actual = obtener_version_actual()


    # Crear la ventana de actualizaciones con un tamaño más grande
    ventana_actualizaciones = tk.Toplevel()
    ventana_actualizaciones.title("Buscar Actualizaciones")
    ventana_actualizaciones.geometry("500x200")  # Tamaño personalizado
    ventana_actualizaciones.resizable(False, False)

    # Etiqueta para mostrar la versión instalada
    version_instalada_label = tk.Label(ventana_actualizaciones, text="Versión instalada:")
    version_instalada_label.pack()

    # Etiqueta para mostrar la versión disponible
    version_disponible_label = tk.Label(ventana_actualizaciones, text="Versión disponible:")
    version_disponible_label.pack()

    # Etiqueta para mostrar el estado de la búsqueda con una fuente más grande
    etiqueta_estado = tk.Label(ventana_actualizaciones, text="\n------ Actualizaciones ------\n", font=("Arial", 12))
    etiqueta_estado.pack()

    # Mostrar la versión actual instalada
    version_instalada_label.config(text=f"Versión instalada: {version_actual}")
    
    # Función para comprobar actualizaciones y descargar / instalar si es necesario
    def comprobar_actualizaciones():
        try:
            # 'usuario' y 'repositorio' del repositorio en GitHub
            usuario = 'sapoclay'
            repositorio = 'manten1d0'
            url_repositorio = f'https://api.github.com/repos/{usuario}/{repositorio}/releases/latest'
            
            # Realizar la solicitud a la API de GitHub
            respuesta = requests.get(url_repositorio)
            respuesta_json = respuesta.json()

            # Obtener la versión más reciente del repositorio
            version_mas_reciente = respuesta_json['tag_name']
            version_actual = obtener_version_actual()

            mensaje_resultado = f"Versión actual instalada: {version_actual}\nLa versión más reciente disponible es: {version_mas_reciente}"

            if version_mas_reciente != version_actual:
                # Habilitar el botón de comprobar actualizaciones si las versiones son diferentes
                boton_comprobar.config(state=tk.NORMAL)

                # Obtener la URL de descarga
                url_descarga = respuesta_json['assets'][0]['browser_download_url']  # URL de descarga del archivo

                # Obtener la ruta de la carpeta home del usuario
                ruta_home = os.path.expanduser("~")

                # Combinar la ruta de la carpeta home con el nombre del archivo .deb
                archivo_descargado = os.path.join(ruta_home, "nombre_del_archivo.deb")

                # Descargar el paquete .deb 
                wget.download(url_descarga, archivo_descargado)
                instalar_paquete_deb(archivo_descargado)
            else:
                # Deshabilitar el botón de comprobar actualizaciones si las versiones son iguales
                boton_comprobar.config(state=tk.DISABLED)

                # Antes de actualizar la etiqueta
                mensaje_resultado = "Ya tienes instalada la última versión disponible de este programa."
                messagebox.showinfo("Sin actualizaciones", mensaje_resultado)
            
            # Convertir mensaje_resultado a una cadena de texto
            mensaje_resultado = str(mensaje_resultado)
            # Configurar el mensaje después de un breve retraso
            ventana_actualizaciones.after(100, lambda: etiqueta_estado.config(text=mensaje_resultado))
            # Actualizar las etiquetas de versiones
            version_instalada_label.config(text=f"Versión instalada: {version_actual}")
            version_disponible_label.config(text=f"Versión disponible: {version_mas_reciente}")

        except Exception as e:
            # Convertir el mensaje de error a una cadena de texto si es necesario
            mensaje_error = str(e, 'utf-8') if isinstance(e, bytes) else str(e)
            # Mostrar el mensaje de error en una ventana emergente
            messagebox.showerror("Error", mensaje_error)

    # Botón para iniciar la comprobación de actualizaciones
    boton_comprobar = tk.Button(ventana_actualizaciones, text="Buscar e Instalar Actualizaciones", command=comprobar_actualizaciones)
    boton_comprobar.pack()
    ToolTip(boton_comprobar, "Descarga e instala la versión más reciente de Manten1d0 desde GitHub")

    # Aplicar el tema seleccionado a la nueva ventana
    preferencias.cambiar_tema(ventana_actualizaciones, preferencias.tema_seleccionado)
    preferencias.cambiar_tema(version_instalada_label, preferencias.tema_seleccionado)
    preferencias.cambiar_tema(version_disponible_label, preferencias.tema_seleccionado)
    preferencias.cambiar_tema(etiqueta_estado, preferencias.tema_seleccionado)


