"""
Clases y funciones para realizar copias de seguridad y operaciones de cifrado y descifrado de archivos.

Dependencias:
    - subprocess: Para ejecutar comandos en el sistema operativo.
    - messagebox de tkinter: Para mostrar mensajes de error en ventanas emergentes.
    - os: Para interactuar con el sistema operativo.
    - tkinter: Para la interfaz gráfica de usuario.
    - filedialog de tkinter: Para seleccionar archivos y ubicaciones.
    - obtener_contrasena de password: Para obtener la contraseña del usuario.
    - cryptography.hazmat: Para realizar operaciones de cifrado y descifrado de archivos.

Clases:
    - CopiaSeguridad: Permite realizar una copia de seguridad de un directorio.
    - RestaurarCopiaSeguridad: Permite restaurar una copia de seguridad en un directorio.

Funciones:
    - generar_clave_maestra: Genera una clave maestra a partir de la contraseña del usuario y un salt.
    - cifrar_archivo: Permite cifrar un archivo seleccionado por el usuario usando ChaCha20.
    - descifrar_archivo: Permite descifrar un archivo cifrado seleccionado por el usuario.
"""
 
import subprocess
from tkinter import messagebox
from password import obtener_contrasena
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import fnmatch
from password import obtener_contrasena  
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from tooltip import ToolTip
from registro import registrar, confirmar, en_hilo, ventana_progreso

class CopiaSeguridad:
    def __init__(self, origen, destino):
        self.origen = origen
        self.destino = destino
    
    def realizar_copia_seguridad(self):
        try:
            contrasena = obtener_contrasena()
            entorno = os.environ.copy()
            entorno["LC_ALL"] = "C"
            if self.destino.startswith("/"):
                comando = ["sudo", "-S", "-p", "", "tar", "-czf", self.destino, "-C", self.origen, "."]
                resultado = subprocess.run(
                    comando,
                    input=contrasena + "\n",
                    capture_output=True,
                    text=True,
                    env=entorno,
                )
            else:
                comando = ["tar", "-czf", self.destino, "-C", self.origen, "."]
                resultado = subprocess.run(comando, capture_output=True, text=True, env=entorno)
            ok = resultado.returncode == 0
            registrar("Copia de seguridad", f"{self.origen} -> {self.destino}", ok)
            if not ok:
                raise RuntimeError(resultado.stderr or "tar devolvió un error")
            return True
        except Exception as e:
            registrar("Copia de seguridad", str(e), False)
            raise

class RestaurarCopiaSeguridad:
    def __init__(self, origen, destino):
        self.origen = origen
        self.destino = destino

    def restaurar_copia_seguridad(self):
        contrasena = obtener_contrasena()
        comando = ["sudo", "-S", "-p", "", "tar", "-xzf", self.origen, "-C", self.destino]
        resultado = subprocess.run(
            comando,
            input=contrasena + "\n",
            capture_output=True,
            text=True,
        )
        ok = resultado.returncode == 0
        registrar("Restaurar copia", f"{self.origen} -> {self.destino}", ok)
        if not ok:
            raise RuntimeError(resultado.stderr or "tar devolvió un error")
        return True


# Función para generar una clave derivada de la contraseña
def generar_clave_maestra(contrasena, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(contrasena.encode())

def cifrar_archivo():
    dir_usuario = os.path.expanduser('~')
        
    # Seleccionar el archivo a cifrar
    archivo_a_cifrar = filedialog.askopenfilename(
        title="Seleccionar archivo a cifrar",
        initialdir=dir_usuario
    )
        
    if not archivo_a_cifrar:
        return

    # Obtener la contraseña del usuario
    contrasena = obtener_contrasena()
    if not contrasena:
        return

    # Generar un salt aleatorio
    salt = os.urandom(16)

    # Generar la clave maestra a partir de la contraseña y el salt
    clave_maestra = generar_clave_maestra(contrasena, salt)

    # Generar un nonce aleatorio para el cifrado
    nonce = os.urandom(16)

    # Leer los datos del archivo a cifrar
    with open(archivo_a_cifrar, 'rb') as f:
        datos = f.read()

    # Inicializar el cifrador ChaCha20
    cipher = Cipher(algorithms.ChaCha20(clave_maestra, nonce), mode=None, backend=default_backend())
    encryptor = cipher.encryptor()

    # Cifrar los datos
    datos_cifrados = encryptor.update(datos) + encryptor.finalize()

    # Seleccionar la ubicación y el nombre del archivo cifrado
    archivo_salida = filedialog.asksaveasfilename(
        title="Guardar archivo cifrado",
        initialdir=dir_usuario,
        filetypes=(("Archivos cifrados", "*.cifrado"),),
        defaultextension=".cifrado",
        initialfile=archivo_a_cifrar.split('/')[-1] + ".cifrado"  # Nombre por defecto
    )
        
    if not archivo_salida:
        return

    # Escribir los datos cifrados y el salt en el archivo cifrado
    with open(archivo_salida, 'wb') as f:
        f.write(salt + nonce + datos_cifrados)

    messagebox.showinfo("Cifrado completado", f"El archivo {archivo_salida} ha sido cifrado con éxito.")


def descifrar_archivo():
    # Obtener el directorio de inicio del usuario
    dir_usuario = os.path.expanduser('~')

    # Definir los tipos de archivo a mostrar
    tipos_archivo = [("Archivos encriptados", "*.cifrado")]

    # Seleccionar el archivo cifrado a descifrar
    archivo_cifrado = filedialog.askopenfilename(
        title="Seleccionar archivo cifrado a descifrar",
        initialdir=dir_usuario,
        filetypes=tipos_archivo
    )
    if not archivo_cifrado:
        return

    # Obtener la contraseña del usuario
    contrasena = obtener_contrasena()
    if not contrasena:
        return

    # Leer el salt y el nonce del archivo cifrado
    with open(archivo_cifrado, 'rb') as file:
        salt = file.read(16)  # Leer el salt del archivo
        nonce = file.read(16)  # Leer el nonce del archivo
        datos_cifrados = file.read()  # Leer los datos cifrados

    # Generar la clave maestra a partir de la contraseña y el salt
    clave_maestra = generar_clave_maestra(contrasena, salt)

    # Inicializar el descifrador ChaCha20
    cipher = Cipher(algorithms.ChaCha20(clave_maestra, nonce), mode=None, backend=default_backend())
    decryptor = cipher.decryptor()

    try:
        # Descifrar los datos
        datos_descifrados = decryptor.update(datos_cifrados) + decryptor.finalize()

        # Seleccionar la ubicación y el nombre del archivo descifrado
        archivo_descifrado = filedialog.asksaveasfilename(
            title="Guardar archivo descifrado",
            initialdir=dir_usuario,
            initialfile=os.path.basename(archivo_cifrado).replace('.cifrado', ''),
            filetypes=(("Todos los archivos", "*.*"),)
        )
        if not archivo_descifrado:
            # El usuario canceló la selección del archivo
            messagebox.showinfo("Operación cancelada por el usuario.")
            return

        # Escribir los datos descifrados en el archivo descifrado
        with open(archivo_descifrado, 'wb') as file:
            file.write(datos_descifrados)

        messagebox.showinfo("Descifrado completado", f"El archivo {archivo_cifrado} ha sido descifrado con éxito.")
    except Exception as e:
        messagebox.showerror("Error", f"Error al descifrar el archivo: {e}")
        
        
# Clase para buscar archivos        
    
class FileSearchApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Buscador de archivos en el sistema")
       # self.master.geometry("800x600")  # Tamaño fijo de la ventana
        self.master.resizable(False, False)  # La ventana no se puede redimensionar
        
        self.create_widgets()
    
    def create_widgets(self):
        self.label_folder = tk.Label(self.master, text="Carpeta de búsqueda:")
        self.label_folder.grid(row=0, column=0, padx=5, pady=5)
        
        self.folder_entry = tk.Entry(self.master, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=5)
        
        self.folder_button = tk.Button(self.master, text="Seleccionar Carpeta", command=self.select_folder)
        self.folder_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.folder_button, "Seleccionar carpeta de búsqueda")  # Agregar tooltip al botón

        self.label_query = tk.Label(self.master, text="Nombre del archivo:")
        self.label_query.grid(row=1, column=0, padx=5, pady=5)
        
        self.entry = tk.Entry(self.master, width=50)
        self.entry.grid(row=1, column=1, padx=5, pady=5)
        
        self.search_button = tk.Button(self.master, text="Buscar", command=self.search_files)
        self.search_button.grid(row=1, column=2, padx=1, pady=5)
        ToolTip(self.search_button, "Iniciar búsqueda")  # Agregar tooltip al botón

        self.results_text = tk.Text(self.master, height=20, width=80)
        self.results_text.grid(row=2, column=0, columnspan=4, padx=5, pady=5)
        self.results_text.bind("<Double-Button-1>", self.open_file_folder)
        
    def select_folder(self):
        folder_path = filedialog.askdirectory(initialdir=os.path.expanduser("~"))
        if folder_path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_path)
        
    def search_files(self):
        folder_path = self.folder_entry.get()
        query = self.entry.get().lower()  # Convertir la consulta del usuario a minúsculas
        
        if not folder_path:
            messagebox.showerror("Error", "Por favor, selecciona una carpeta de búsqueda.")
            return
        
        if not query:
            messagebox.showerror("Error", "Por favor, escribe el nombre del archivo a buscar.")
            return
        
        self.results_text.delete(1.0, tk.END)
        files_found = False
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # Convertir el nombre del archivo a minúsculas antes de compararlo
                if fnmatch.fnmatch(file.lower(), f"*{query}*"):  
                    file_path = os.path.join(root, file)
                    self.results_text.insert(tk.END, file_path + "\n")
                    files_found = True
        
        if not files_found:
            messagebox.showinfo("Información", "No se encontraron archivos que coincidan con la búsqueda.")

    
    def open_file_folder(self, event):
        selection_indices = self.results_text.tag_ranges(tk.SEL)
        if selection_indices:
            selection = self.results_text.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            if os.path.isfile(selection):
                folder_path = os.path.dirname(selection)
                subprocess.Popen(["nautilus", folder_path])
            elif os.path.isdir(selection):
                subprocess.Popen(["nautilus", selection])


# Clase para renombrado masivo de archivos

class BulkRenameApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Renombrar archivos masivamente")
        self.create_widgets()

    def create_widgets(self):
        self.folder_label = tk.Label(self.master, text="Carpeta de archivos:")
        self.folder_label.grid(row=0, column=0, padx=5, pady=5)

        self.folder_entry = tk.Entry(self.master, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=5)

        self.folder_button = tk.Button(self.master, text="Seleccionar Carpeta", command=self.select_folder)
        self.folder_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.folder_button, "Elige la carpeta cuyos archivos se van a renombrar")

        self.prefix_label = tk.Label(self.master, text="Prefijo:")
        self.prefix_label.grid(row=1, column=0, padx=5, pady=5)
        ToolTip(self.prefix_label, "Prefijo a aplicar a los archivos renombrados")  # Agregar tooltip al botón


        self.prefix_entry = tk.Entry(self.master, width=50)
        self.prefix_entry.grid(row=1, column=1, padx=5, pady=5)

        self.rename_button = tk.Button(self.master, text="Renombrar", command=self.bulk_rename)
        self.rename_button.grid(row=1, column=2, padx=5, pady=5)
        ToolTip(self.rename_button, "Renombrar los archivo utilizando el prefijo indicado. Cuidado!! esta acción no se puede deshacer.")  # Agregar tooltip al botón
        
        self.open_folder_button = tk.Button(self.master, text="Abrir Carpeta", command=self.open_folder)
        self.open_folder_button.grid(row=2, column=1, padx=5, pady=5)
        ToolTip(self.open_folder_button, "Abrir la carpeta con los archivos renombrados")  # Agregar tooltip al botón
        
    def select_folder(self):
        # Seleccionamos por defecto la carpeta home del usuario
        folder_path = filedialog.askdirectory(initialdir=os.path.expanduser("~"))

        if folder_path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_path)

    def bulk_rename(self):
        folder_path = self.folder_entry.get()
        prefix = self.prefix_entry.get()
        if not folder_path:
            tk.messagebox.showerror("Error", "Por favor, selecciona una carpeta.")
            return
        if not prefix:
            tk.messagebox.showerror("Error", "Por favor, ingresa un prefijo para los archivos.")
            return

        try:
            for i, filename in enumerate(os.listdir(folder_path)):
                os.rename(os.path.join(folder_path, filename), os.path.join(folder_path, f"{prefix}_{i+1}.txt"))
            tk.messagebox.showinfo("Éxito", "Archivos renombrados exitosamente.")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Ocurrió un error: {str(e)}")

    def open_folder(self):
        folder_path = self.folder_entry.get()
        if not folder_path:
            tk.messagebox.showerror("Error", "Por favor, selecciona una carpeta.")
            return

        subprocess.Popen(["nautilus", folder_path])