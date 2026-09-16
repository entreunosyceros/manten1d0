"""
Este módulo proporciona una interfaz gráfica para modificar el perfil de usuario en un sistema operativo basado en Unix/Linux.

Módulos Importados:
- tkinter: Proporciona la funcionalidad para crear la interfaz gráfica de usuario.
- messagebox: Permite mostrar cuadros de mensaje.
- filedialog: Permite al usuario seleccionar archivos.
- simpledialog: Permite solicitar la entrada del usuario a través de cuadros de diálogo.
- PIL (Pillow): Proporciona herramientas para trabajar con imágenes.
- os: Proporciona una forma de usar funcionalidades dependientes del sistema operativo.
- subprocess: Permite ejecutar comandos del sistema operativo y capturar su salida.
- getpass: Proporciona una manera de manejar entradas sensibles como contraseñas.
- password: Contiene funciones para limpiar archivos de configuración y obtener contraseñas de sudo.
- tooltip: Proporciona una clase para mostrar tooltips en widgets de tkinter.
"""

import grp
import os
import pwd
import shutil
import tkinter as tk
from subprocess import Popen, PIPE
import subprocess
import getpass
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk

from password import limpiar_archivos_configuracion, obtener_contrasena
from tooltip import ToolTip


def datos_perfil_actual():
    """Obtiene los datos visibles del usuario actual sin pedir sudo."""
    usuario = getpass.getuser()
    datos = {
        "usuario": usuario,
        "nombre": usuario,
        "uid": "",
        "home": os.path.expanduser("~"),
        "shell": "",
        "grupos": "",
        "imagen": None,
    }
    try:
        cuenta = pwd.getpwnam(usuario)
    except KeyError:
        return datos

    nombre = (cuenta.pw_gecos.split(",")[0] or "").strip()
    datos["nombre"] = nombre or usuario
    datos["uid"] = str(cuenta.pw_uid)
    datos["home"] = cuenta.pw_dir
    datos["shell"] = cuenta.pw_shell

    grupos = set()
    try:
        grupos.add(grp.getgrgid(cuenta.pw_gid).gr_name)
    except KeyError:
        pass
    for grupo in grp.getgrall():
        if usuario in grupo.gr_mem:
            grupos.add(grupo.gr_name)
    datos["grupos"] = ", ".join(sorted(grupos))

    candidatos = [
        os.path.join(cuenta.pw_dir, ".face"),
        os.path.join(cuenta.pw_dir, ".face.icon"),
        f"/var/lib/AccountsService/icons/{usuario}",
    ]
    accounts = f"/var/lib/AccountsService/users/{usuario}"
    if os.access(accounts, os.R_OK):
        try:
            with open(accounts, encoding="utf-8") as archivo:
                for linea in archivo:
                    if linea.startswith("Icon="):
                        ruta_icono = linea.split("=", 1)[1].strip()
                        if ruta_icono:
                            candidatos.insert(0, ruta_icono)
                        break
        except OSError:
            pass

    for ruta in candidatos:
        if ruta and os.path.isfile(ruta) and os.access(ruta, os.R_OK):
            datos["imagen"] = ruta
            break
    return datos


def _foto_perfil(ruta, tamano=(120, 120)):
    imagen = Image.open(ruta)
    imagen.thumbnail(tamano)
    return ImageTk.PhotoImage(imagen)


def crear_panel_perfil(parent, fondo="lightgrey"):
    """Muestra en un marco los datos actuales del perfil que se pueden consultar o cambiar."""
    datos = datos_perfil_actual()
    marco = tk.Frame(parent, bg=fondo)
    tarjeta = tk.Frame(marco, bg=fondo)
    tarjeta.pack(pady=8)

    columna_foto = tk.Frame(tarjeta, bg=fondo)
    columna_foto.pack(side=tk.LEFT, padx=(0, 16), anchor="n")
    etiqueta_foto = tk.Label(columna_foto, bg=fondo)
    etiqueta_foto.pack()
    foto = None
    if datos["imagen"]:
        try:
            foto = _foto_perfil(datos["imagen"])
            etiqueta_foto.configure(image=foto)
            etiqueta_foto.image = foto
        except OSError:
            etiqueta_foto.configure(text="Sin imagen")
    else:
        etiqueta_foto.configure(text="Sin imagen de perfil", font=("Arial", 9))

    columna_datos = tk.Frame(tarjeta, bg=fondo)
    columna_datos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    filas = (
        ("Usuario", datos["usuario"]),
        ("Nombre", datos["nombre"]),
        ("Carpeta personal", datos["home"]),
        ("Intérprete", datos["shell"]),
        ("Grupos", datos["grupos"] or "—"),
    )
    for etiqueta, valor in filas:
        fila = tk.Frame(columna_datos, bg=fondo)
        fila.pack(fill=tk.X, pady=2)
        tk.Label(
            fila,
            text=f"{etiqueta}:",
            width=16,
            anchor="e",
            bg=fondo,
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            fila,
            text=valor or "—",
            anchor="w",
            bg=fondo,
            wraplength=360,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, padx=8)

    tk.Label(
        marco,
        text="Se puede modificar el nombre, la imagen de perfil y la contraseña.",
        bg=fondo,
        font=("Arial", 9),
        justify=tk.CENTER,
    ).pack(pady=(8, 0))
    return marco, foto


class PerfilUsuario:
    """Clase para la interfaz de modificación del perfil de usuario."""
    def __init__(self, root):
        """Inicializa la interfaz gráfica de usuario.

        Args:
            root (tk.Tk): La ventana principal de tkinter.
        """
        self.root = root
        self.root.title("Modificar Perfil de Usuario en el Sistema Operativo")
        self.root.geometry("400x600")

        datos = datos_perfil_actual()
        tk.Label(root, text=f"Usuario: {datos['usuario']}").pack()
        tk.Label(root, text="* Nombre:").pack()
        self.entry_nombre = tk.Entry(root, width=36)
        self.entry_nombre.pack()
        ToolTip(self.entry_nombre, "Nombre visible del usuario (se puede modificar)")

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        tk.Label(root, text="Contraseña (vacío = no cambiar):").pack()
        self.entry_password = tk.Entry(root, show="*", width=36)
        self.entry_password.pack()
        ToolTip(self.entry_password, "Déjala vacía para conservar la contraseña actual")

        tk.Label(root, text="Confirmar contraseña:").pack()
        self.entry_confirm_password = tk.Entry(root, show="*", width=36)
        self.entry_confirm_password.pack()
        ToolTip(self.entry_confirm_password, "Repite la contraseña solo si quieres cambiarla")

        # Botón para mostrar/ocultar contraseña
        self.boton_mostrar_contrasena = tk.Button(root, text="Mostrar", command=self.mostrar_ocultar_contrasena)
        self.boton_mostrar_contrasena.pack()
        ToolTip(self.boton_mostrar_contrasena, "Mostrar/Ocultar Contraseña")

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        # Botón para elegir una imagen de perfil
        self.seleccion_imagen = tk.Button(root, text="Seleccionar Imagen de Perfil", command=self.seleccionar_imagen)
        self.seleccion_imagen.pack(pady=5)
        ToolTip(self.seleccion_imagen, "Elige una imagen para el perfil de usuario")

        self.label_imagen = tk.Label(root, text="Sin imagen de perfil")
        self.label_imagen.pack(pady=10)
        ToolTip(self.label_imagen, "Imagen actual del perfil de usuario")

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        # Contenedor para los botones
        self.frame_botones = tk.Frame(root)
        self.frame_botones.pack(pady=10)

        # Botón para guardar los cambios
        self.boton_guardar_perfil = tk.Button(self.frame_botones, text="Guardar Perfil", command=self.guardar_perfil)
        self.boton_guardar_perfil.pack(side=tk.LEFT, padx=5)
        ToolTip(self.boton_guardar_perfil, "Guardar Perfil de Usuario con los Datos Introducidos")

        # Botón para cancelar
        self.boton_cancelar = tk.Button(self.frame_botones, text="Cancelar", command=root.destroy)
        self.boton_cancelar.pack(side=tk.LEFT, padx=5)
        ToolTip(self.boton_cancelar, "Cancelar el guardado del Perfil de Usuario")


        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        # Ruta de la imagen de perfil seleccionada
        self.imagen_perfil = None
        self.imagen_tk = None  # Retener la referencia a la imagen

        # Cargar los datos actuales del usuario
        self.cargar_datos_usuario()

    def mostrar_ocultar_contrasena(self):
        """Muestra u oculta la contraseña en los campos de entrada."""
        if self.entry_password.cget('show') == '*':
            self.entry_password.config(show='')
            self.entry_confirm_password.config(show='')
            self.boton_mostrar_contrasena.config(text="Ocultar")
        else:
            self.entry_password.config(show='*')
            self.entry_confirm_password.config(show='*')
            self.boton_mostrar_contrasena.config(text="Mostrar")

    def seleccionar_imagen(self):
        """Abre un cuadro de diálogo para seleccionar una imagen de perfil."""
        self.imagen_perfil = filedialog.askopenfilename(
            initialdir=os.path.expanduser("~"),
            title="Seleccionar Imagen de Perfil",
            filetypes=(("Archivos de imagen", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*"))
        )
        if self.imagen_perfil:
            # Mostrar la previsualización de la imagen seleccionada
            self.mostrar_previsualizacion_imagen(self.imagen_perfil)
            messagebox.showinfo("Imagen seleccionada", f"Imagen seleccionada: {self.imagen_perfil}")

    def mostrar_previsualizacion_imagen(self, ruta_imagen):
        """Muestra una previsualización de la imagen de perfil seleccionada.

        Args:
            ruta_imagen (str): La ruta del archivo de imagen seleccionado.
        """
        try:
            self.imagen_tk = _foto_perfil(ruta_imagen, (100, 100))
            self.label_imagen.config(image=self.imagen_tk, text="")
            self.label_imagen.image = self.imagen_tk
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la imagen de perfil: {e}")

    def cargar_datos_usuario(self):
        """Rellena el formulario con el nombre e imagen actuales, sin pedir sudo."""
        datos = datos_perfil_actual()
        self.entry_nombre.delete(0, tk.END)
        self.entry_nombre.insert(0, datos["nombre"])
        if datos["imagen"]:
            self.mostrar_previsualizacion_imagen(datos["imagen"])

    def _guardar_imagen_perfil(self, usuario, contrasena_sudo):
        if not self.imagen_perfil:
            return
        destino_home = os.path.join(os.path.expanduser("~"), ".face")
        shutil.copy2(self.imagen_perfil, destino_home)
        destino_cuenta = f"/var/lib/AccountsService/icons/{usuario}"
        subprocess.run(
            ["sudo", "-S", "cp", self.imagen_perfil, destino_cuenta],
            input=f"{contrasena_sudo}\n",
            text=True,
            check=False,
        )
        subprocess.run(
            ["sudo", "-S", "chmod", "644", destino_cuenta],
            input=f"{contrasena_sudo}\n",
            text=True,
            check=False,
        )

    def guardar_perfil(self):
        """Guarda los cambios en el perfil del usuario, incluyendo el nombre y la contraseña."""
        nombre = self.entry_nombre.get().strip()
        password = self.entry_password.get()
        confirm_password = self.entry_confirm_password.get()
        usuario = getpass.getuser()

        if not nombre:
            messagebox.showerror("Error", "El nombre es obligatorio.")
            return

        if password or confirm_password:
            if password != confirm_password:
                messagebox.showerror("Error", "Las contraseñas no coinciden.")
                return
            if not password:
                messagebox.showerror("Error", "La contraseña no puede estar vacía si quieres cambiarla.")
                return

        contrasena_sudo = obtener_contrasena()
        if not contrasena_sudo:
            return

        try:
            subprocess.run(
                ["sudo", "-S", "usermod", "-c", nombre, usuario],
                input=f"{contrasena_sudo}\n",
                text=True,
                check=True,
                capture_output=True,
            )
            self._guardar_imagen_perfil(usuario, contrasena_sudo)

            if password:
                process = Popen(
                    ["sudo", "-S", "chpasswd"],
                    stdin=PIPE,
                    stdout=PIPE,
                    stderr=PIPE,
                    text=True,
                )
                stdout, stderr = process.communicate(input=f"{contrasena_sudo}\n{usuario}:{password}\n")
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, "chpasswd", output=stdout, stderr=stderr)

            messagebox.showinfo("Perfil", "Los datos del perfil se han actualizado.")
            reiniciar_sesion = messagebox.askyesno(
                "Reiniciar sesión",
                "¿Quieres reiniciar la sesión para aplicar los cambios?",
            )
            if reiniciar_sesion:
                limpiar_archivos_configuracion()
                subprocess.run(["pkill", "-HUP", "-u", usuario])
            else:
                try:
                    self.root.destroy()
                except tk.TclError:
                    pass
        except subprocess.CalledProcessError as e:
            detalle = e.stderr if getattr(e, "stderr", None) else e
            messagebox.showerror("Error", f"No se pudo actualizar el perfil: {detalle}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar el perfil: {e}")


