"""
Función 'mostrar_about'.

Imports:
    - tkinter as tk: Para la creación de interfaces gráficas.
    - os: Para realizar operaciones relacionadas con el sistema operativo.
    - preferencias: Para ajustar las preferencias de la interfaz.

Function:
    - mostrar_about(): Abre una ventana que muestra información sobre el programa. La ventana incluye un logotipo, la versión del programa y un 
    mensaje informativo. Además, si se ha seleccionado un tema oscuro en las preferencias, aplica el tema oscuro a las ventanas del proyecto.

"""
 
import tkinter as tk
import os
import configparser

import preferencias


def obtener_version_actual():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_config = os.path.join(directorio_actual, 'config.ini')
    config = configparser.ConfigParser()
    config.read(ruta_config)
    return config['Version']['actual']


def mostrar_about():
    version_actual = obtener_version_actual()

    about_window = tk.Toplevel()
    about_window.title("Acerca De")
    # Altura mayor: franja + logo + texto completo sin recortar
    about_window.geometry("420x480")
    about_window.resizable(False, False)
    about_window.minsize(420, 480)

    dir_actual = os.path.dirname(os.path.realpath(__file__))
    ruta_imagen = os.path.join(dir_actual, "logo.png")
    img = tk.PhotoImage(file=ruta_imagen)

    img_label = tk.Label(about_window, image=img)
    img_label.image = img
    img_label.pack(pady=(16, 8))

    about_label = tk.Label(
        about_window,
        text=(
            f"Manten1-d0 de Sistema Ubuntu\n"
            f"Versión: {version_actual}\n\n"
            "Este programa realiza tareas de mantenimiento básico\n"
            "en sistemas Ubuntu.\n"
            "No se dan garantías de ningún tipo.\n\n"
            "Repositorio:\n"
            "https://github.com/sapoclay/manten1d0"
        ),
        justify=tk.CENTER,
    )
    about_label.pack(padx=24, pady=(8, 24))

    preferencias.cambiar_tema(about_window, preferencias.tema_seleccionado)

    about_window.update_idletasks()
    ancho = about_window.winfo_width()
    alto = about_window.winfo_height()
    x = max(0, (about_window.winfo_screenwidth() - ancho) // 2)
    y = max(0, (about_window.winfo_screenheight() - alto) // 3)
    about_window.geometry(f"+{x}+{y}")
    about_window.lift()
    about_window.focus_force()