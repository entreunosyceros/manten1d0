import subprocess
from password import obtener_contrasena
import threading
import time
from tkinter import messagebox, scrolledtext, Listbox, Scrollbar, END, simpledialog, Menu
import tkinter as tk
from tkinter import ttk
import os
from tkinter import filedialog
import psutil
from tkinter import font
#import tkinter.messagebox as messagebox
import hashlib
from datetime import datetime, timezone
import platform
from tooltip import ToolTip
import subprocess
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from placeholder import entradaConPlaceHolder
from registro import registrar, registrar_comando, sudo_shell

# Clase para generar la ventana de barra de progreso
class ProgresoVentana(tk.Toplevel):
    """
Clase 'ProgresoVentana'.

Class:
    - ProgresoVentana(tk.Toplevel): Clase para generar la ventana de barra de progreso.

Attributes:
    - master: El widget principal al que pertenece la ventana.
    - accion: La acción que se está realizando y se muestra en la ventana.

Methods:
    - __init__(self, master, accion): Constructor de la clase. Inicializa la ventana de progreso con una barra de progreso indeterminada y un mensaje indicando la acción en curso.
        - master: El widget principal al que pertenece la ventana.
        - accion: La acción que se está realizando y se muestra en la ventana.

Raises:
    - No hay excepciones especificadas en la clase.
"""
    def __init__(self, master, accion):
        super().__init__(master)
        self.title("Progreso")
        self.geometry("400x100")
        self.progressbar = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
        self.progressbar.pack(pady=20)
        self.label = tk.Label(self, text=f"Ejecutando {accion}...", font=("Arial", 12))
        self.label.pack()
        self.progressbar.start()
        self.grab_set()
        self.resizable(False, False)  # Hacer que la ventana no sea redimensionable

'''
Función para ejecutar cualquier comando que necesite sudo y la contraseña
'''
def ejecutar_comando_con_sudo(comando, accion, master, callback=None):
    def _done(ok):
        if callback:
            callback(ok)

    sudo_shell(
        comando,
        accion,
        master,
        confirmar_accion=True,
        on_done=_done,
    )

def actualizar_sistema(master):
    comando = "apt-get update && apt-get upgrade -y"
    ejecutar_comando_con_sudo(
        comando,
        "actualizar el sistema",
        master,
        lambda ok: messagebox.showinfo("Información", "Actualización completada")
        if ok
        else messagebox.showerror("Error", "La actualización no se completó. Revisa Preferencias → Registro de acciones."),
    )

def limpiar_cache(master):
    comando = "apt-get clean && apt-get autoremove -y"
    ejecutar_comando_con_sudo(
        comando,
        "limpiar la caché del sistema",
        master,
        lambda ok: messagebox.showinfo("Información", "Limpieza de caché completada")
        if ok
        else messagebox.showerror("Error", "La limpieza no se completó. Revisa Preferencias → Registro de acciones."),
    )

def abrir_gestor_software():
        try:
            # Verificar si Snap Store está instalado
            snap_store_instalado = subprocess.run(["which", "snap-store"], stdout=subprocess.PIPE).returncode == 0

            # Si Snap Store no está instalado, mostrar un mensaje de advertencia en una ventana emergente
            if not snap_store_instalado:
                messagebox.showwarning("Snap Store no está instalado", "Snap Store no está instalado en el sistema.")
                return

            # Abrir Snap Store
            subprocess.Popen("snap-store", shell=True)
        except Exception as e:
            # Mostrar el mensaje de error en una ventana emergente
            messagebox.showerror("Error al abrir Snap Store", f"Error: {e}")

""" 
Clase para realizar tareas de limpieza:
    - Vaciar la papelera
    - Eliminar archivos y carpetas sin pasar por la papelera
"""

class Limpieza:
    @staticmethod
    def vaciar_papelera():
        try:
            confirmacion = messagebox.askyesno("Confirmar vaciado", "¿Estás seguro de que quieres vaciar la papelera de reciclaje?")
            if confirmacion:
                os.system("gio trash --empty")
                registrar("Vaciar papelera", "gio trash --empty", True)
                registrar_comando("Vaciar papelera", "gio trash --empty", sudo=False, tipo="plain")
                messagebox.showinfo("Éxito", "La papelera de reciclaje se ha vaciado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo vaciar la papelera de reciclaje. Error: {e}")

    @staticmethod
    def eliminar_elemento():
        try:
            elemento = filedialog.askdirectory(title="Seleccionar elemento para eliminar")
            
            if elemento:
                confirmacion = messagebox.askyesno("Confirmar eliminación", f"¿Estás seguro de que quieres eliminar el elemento seleccionado:\n{elemento}?")
                if confirmacion:
                    if os.path.isfile(elemento):
                        os.remove(elemento)
                    elif os.path.isdir(elemento):
                        os.rmdir(elemento)
                    registrar("Eliminar elemento", elemento, True)
                    messagebox.showinfo("Éxito", "El elemento seleccionado se ha eliminado correctamente.")
            else:
                messagebox.showwarning("Advertencia", "No se seleccionó ningún elemento para eliminar.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar el elemento seleccionado. Error: {e}")


# Clase para crear la ventana y gestionar la aplicaciones al Inicio
class AplicacionesAutostart:
    
    """
Clase 'AplicacionesAutostart'.

Class:
    - AplicacionesAutostart: Clase para crear la ventana y gestionar las aplicaciones al Inicio.

Attributes:
    - master: El widget principal al que pertenece la ventana.

Methods:
    - __init__(self, master): Constructor de la clase. Inicializa la ventana y sus componentes.
        - master: El widget principal al que pertenece la ventana.
    - actualizar_lista_aplicaciones(self): Actualiza la lista de aplicaciones de autostart en el Treeview.
    - obtener_aplicaciones_autostart(self): Obtiene la lista de aplicaciones de autostart.
    - agregar_aplicacion(self): Permite al usuario seleccionar y agregar una aplicación al autostart.
    - eliminar_aplicacion(self): Elimina una aplicación seleccionada del autostart.
    - abrir_ventana_aplicaciones_autostart(self): Abre una nueva ventana para la configuración de aplicaciones de autostart.

Raises:
    - No hay excepciones especificadas en la clase.
"""

    def __init__(self, master):
        self.master = master
        self.master.title("Configuración de Aplicaciones de Autostart")

        # Crear un Treeview para mostrar las aplicaciones de autostart
        self.treeview = ttk.Treeview(master, columns=("Aplicación"))
        self.treeview.heading("#0", text="ID")
        self.treeview.heading("#1", text="Aplicación")
        self.treeview.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        # Obtener la lista de aplicaciones de autostart
        self.actualizar_lista_aplicaciones()

        # Botones para agregar y eliminar aplicaciones
        self.btn_agregar = tk.Button(master, text="Agregar", command=self.agregar_aplicacion)
        self.btn_agregar.grid(row=1, column=0, padx=5, pady=5)
        ToolTip(self.btn_agregar, "Añade un programa al inicio de sesión")

        self.btn_eliminar = tk.Button(master, text="Eliminar", command=self.eliminar_aplicacion)
        self.btn_eliminar.grid(row=1, column=1, padx=5, pady=5)
        ToolTip(self.btn_eliminar, "Quita el programa seleccionado del inicio de sesión")

    def actualizar_lista_aplicaciones(self):
        # Limpiar el Treeview antes de actualizar
        for i in self.treeview.get_children():
            self.treeview.delete(i)

        # Obtener la lista de aplicaciones de autostart
        aplicaciones_autostart = self.obtener_aplicaciones_autostart()

        # Agregar las aplicaciones al Treeview
        for i, app in enumerate(aplicaciones_autostart, start=1):
            self.treeview.insert("", "end", text=str(i), values=(app,))

    def obtener_aplicaciones_autostart(self):
        aplicaciones_autostart = []

        # Leer el contenido del directorio autostart
        autostart_dir = os.path.expanduser("~/.config/autostart/")
        if os.path.exists(autostart_dir):
            for filename in os.listdir(autostart_dir):
                if filename.endswith(".desktop"):
                    aplicaciones_autostart.append(filename[:-8])  # Eliminar la extensión .desktop

        return aplicaciones_autostart

    def agregar_aplicacion(self):
        # Permitir al usuario seleccionar un archivo .desktop para agregarlo al autostart
        archivo_desktop = tk.filedialog.askopenfilename(title="Seleccionar Aplicación",
                                                        filetypes=[("Archivos Desktop", "*.desktop")])
        if archivo_desktop:
            nombre_aplicacion = os.path.basename(archivo_desktop)
            destino = os.path.expanduser("~/.config/autostart/") + nombre_aplicacion
            os.system(f"cp {archivo_desktop} {destino}")
            self.actualizar_lista_aplicaciones()

    def eliminar_aplicacion(self):
        # Obtener el ID de la fila seleccionada en el Treeview
        seleccion = self.treeview.selection()
        if seleccion:
            id_fila = self.treeview.index(seleccion)
            aplicacion = self.treeview.item(seleccion)["values"][0]

            # Eliminar la aplicación del autostart
            ruta_aplicacion = os.path.expanduser(f"~/.config/autostart/{aplicacion}.desktop")
            os.remove(ruta_aplicacion)
            self.actualizar_lista_aplicaciones()

    def abrir_ventana_aplicaciones_autostart(self):
        # Crear una nueva ventana de tkinter
        ventana_aplicaciones_autostart = tk.Toplevel(self.master)
        # Instanciar la clase AplicacionesAutostart en la nueva ventana
        aplicaciones_autostart = AplicacionesAutostart(ventana_aplicaciones_autostart)



class AdministrarProcesos:    
    def __init__(self, root):
        self.root = root
        self.root.title("Administrar Procesos")
        self.column_sort_order = {}  # Diccionario para guardar el orden de clasificación de las columnas
        
        self.tree = ttk.Treeview(self.root, columns=("PID", "Nombre", "Uso de CPU"))
        self.tree.heading("#0", text="", anchor=tk.W)
        self.tree.heading("#1", text="PID", anchor=tk.W, command=lambda: self.sort_column("#1"))
        self.tree.heading("#2", text="Nombre", anchor=tk.W, command=lambda: self.sort_column("#2"))
        self.tree.heading("#3", text="Uso de CPU", anchor=tk.W, command=lambda: self.sort_column("#3"))
        self.tree.column("#0", stretch=tk.NO, width=0)
        self.tree.column("#1", stretch=tk.YES, width=100)
        self.tree.column("#2", stretch=tk.YES, width=200)
        self.tree.column("#3", stretch=tk.YES, width=100)
        self.tree.pack(expand=True, fill=tk.BOTH)
        
        self.scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)  # Mover el árbol a la izquierda
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)  # Colocar la barra de desplazamiento a la derecha

        # Crear una fuente en negrita
        bold_font = font.Font(weight="bold")

        # Crear la etiqueta con el texto "Opciones" en negrita
        label = tk.Label(self.root, text="Opciones", font=bold_font)
        label.pack(side=tk.TOP, pady=(0, 5))  # Ajustar el relleno superior según sea necesario

        
        self.search_entry_var = tk.StringVar()
        self.search_entry_var.set("Buscar por nombre o PID")
        self.search_entry = tk.Entry(self.root, textvariable=self.search_entry_var, fg="grey")
        self.search_entry.pack(side=tk.TOP, fill=tk.X)
        self.search_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_entry_focus_out)
        self.search_entry.bind("<KeyRelease>", self.filter_processes)
        
        self.close_button = tk.Button(self.root, text="Cerrar Proceso", command=self.close_process)
        self.close_button.pack(side=tk.TOP)
        ToolTip(self.close_button, "Termina el proceso seleccionado. Úsalo con precaución")
        
        self.load_processes()

        # Iniciar la actualización periódica de los procesos
        self.update_processes()

    def on_entry_focus_in(self, event):
        if self.search_entry_var.get() == "Buscar por nombre o PID":
            self.search_entry_var.set("")
            self.search_entry.config(fg="black")

    def on_entry_focus_out(self, event):
        if not self.search_entry_var.get():
            self.search_entry_var.set("Buscar por nombre o PID")
            self.search_entry.config(fg="grey")
            
    def load_processes(self):
        self.tree.delete(*self.tree.get_children())
        for proc in psutil.process_iter(['pid', 'name']):
            proc_info = proc.info
            try:
                self.tree.insert("", "end", text="", values=(proc_info['pid'], proc_info['name'], "Calculando..."))
                threading.Thread(target=self.update_cpu_usage_single, args=(proc_info['pid'],)).start()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.tree.insert("", "end", text="", values=(proc_info['pid'], proc_info['name'], "N/A"))

    def close_process(self):
        selected_item = self.tree.selection()
        if selected_item:
            pid = self.tree.item(selected_item)["values"][0]
            name = self.tree.item(selected_item)["values"][1]
            confirm = messagebox.askyesno("Confirmar cierre", f"¿Estás seguro de que quieres cerrar el proceso {name} (PID: {pid})?")
            if confirm:
                try:
                    process = psutil.Process(pid)
                    process.terminate()
                except psutil.NoSuchProcess:
                    pass
                self.load_processes()
            
    def filter_processes(self, event):
        query = self.search_entry_var.get().lower()
        for item in self.tree.get_children():
            pid = str(self.tree.item(item)["values"][0])  # Convertir el PID a cadena
            name = self.tree.item(item)["values"][1].lower()
            if query in pid or query in name:
                self.tree.selection_set(item)
                self.tree.see(item)
            else:
                self.tree.selection_remove(item)
                
    def sort_column(self, column):
        column_index = int(column[1:]) - 1
        current_sort_order = self.column_sort_order.get(column, "asc")  # Obtener el orden actual de clasificación de la columna
        items = [(self.tree.set(child, column_index), child) for child in self.tree.get_children('')]

        if column_index == 0:  # Verificar si la columna es PID
            items.sort(key=lambda x: int(x[0]), reverse=current_sort_order == "desc")  # Convertir a entero antes de ordenar
        elif column_index == 1:  # Verificar si la columna es Nombre
            items.sort(key=lambda x: x[0].lower(), reverse=current_sort_order == "desc")
        elif column_index == 2:  # Verificar si la columna es Uso de CPU
            items.sort(key=lambda x: float(x[0].rstrip("%")) if x[0].replace('.', '', 1).isdigit() else float('inf'), reverse=current_sort_order == "desc")  # Convertir a float antes de ordenar

        for index, (value, child) in enumerate(items):
            self.tree.move(child, '', index)

        self.column_sort_order[column] = "desc" if current_sort_order == "asc" else "asc"
    
    def update_cpu_usage_single(self, pid):
        try:
            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=0.5)
            self.root.after(100, self.update_tree, pid, f"{cpu_percent:.2f}%")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"No se pudo calcular el uso de CPU para el proceso {pid}: {e}")

    def update_tree(self, pid, cpu_percent):
        if not self.tree.winfo_exists():
            return  # Salir si el widget Treeview no existe
        for child in self.tree.get_children():
            if self.tree.item(child)["values"][0] == pid:
                # Actualiza solo el valor de la CPU
                current_values = self.tree.item(child)["values"]
                new_values = (current_values[0], current_values[1], cpu_percent)
                self.tree.item(child, values=new_values)

    def update_processes(self):
        for proc in psutil.process_iter(['pid', 'name']):
            proc_info = proc.info
            try:
                pid = proc_info['pid']
                # Si el proceso ya está en la lista, actualiza el uso de CPU
                if any(self.tree.item(child)["values"][0] == pid for child in self.tree.get_children()):
                    threading.Thread(target=self.update_cpu_usage_single, args=(pid,)).start()
                else:
                    self.tree.insert("", "end", text="", values=(pid, proc_info['name'], "Calculando..."))
                    threading.Thread(target=self.update_cpu_usage_single, args=(pid,)).start()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Llama a update_processes nuevamente después de 5 segundos
        self.root.after(5000, self.update_processes)  # Actualiza cada 5 segundos


        
# Categoría para buscar archivos duplicados en el sistema
class AplicacionBuscadorDuplicados:
    
    """
Clase 'AplicacionBuscadorDuplicados'.

Class:
    - AplicacionBuscadorDuplicados: Clase para buscar archivos duplicados en el sistema.

Attributes:
    - root: El widget principal al que pertenece la ventana.
    - carpeta_seleccionada: La carpeta seleccionada por el usuario para buscar archivos duplicados.
    - archivos_duplicados: Un diccionario que contiene los archivos duplicados encontrados.

Methods:
    - __init__(self, root): Constructor de la clase. Inicializa la ventana y sus componentes.
        - root: El widget principal al que pertenece la ventana.
    - abrir_ventana_carpeta(self): Abre una ventana para que el usuario seleccione una carpeta para buscar archivos duplicados.
    - mostrar_progreso(self): Muestra la barra de progreso y el mensaje de progreso.
    - buscar_archivos_duplicados(self, carpeta): Busca archivos duplicados en la carpeta especificada.
        - carpeta: La carpeta en la que se buscarán archivos duplicados.
    - mostrar_duplicados(self): Muestra los archivos duplicados encontrados en el Treeview.
    - calcular_hash(self, ruta_archivo): Calcula el hash SHA256 de un archivo dado.
        - ruta_archivo: La ruta completa del archivo.
    - obtener_fecha_creacion(self, archivo): Obtiene la fecha de creación de un archivo.
        - archivo: El archivo del que se obtendrá la fecha de creación.
    - seleccionar_todo(self): Selecciona o deselecciona todos los archivos en el Treeview.
    - confirmar_eliminar_seleccionados(self): Muestra un cuadro de diálogo de confirmación antes de eliminar los archivos seleccionados.
    - eliminar_seleccionados(self): Elimina los archivos seleccionados del sistema y del Treeview.
    - configurar_tamano_filas(self, event=None): Ajusta el ancho de las columnas del Treeview para que se adapten al tamaño de la ventana.
        - event: El evento que desencadena la función (por defecto es None).
    - abrir_ubicacion_archivo(self, event): Abre la ubicación del archivo seleccionado en el gestor de archivos por defecto.
        - event: El evento que desencadena la función.

Raises:
    - No se especifican excepciones en la clase.
"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Buscar Archivos Duplicados")
        self.root.geometry("800x600")  # Establecer un tamaño predeterminado para la ventana

        self.carpeta_seleccionada = None
        self.archivos_duplicados = {}

        # Marco para selección de carpeta
        self.marco_carpeta = tk.Frame(self.root)
        self.marco_carpeta.pack(pady=10)

        # Botón para buscar archivos
        self.boton_buscar = tk.Button(self.marco_carpeta, text="Buscar Archivos", command=self.abrir_ventana_carpeta)
        self.boton_buscar.pack(side="left")
        ToolTip(self.boton_buscar, "Selecciona una carpeta para buscar los archivos duplicados")

        # Marco para barra de progreso
        self.marco_progreso = tk.Frame(self.root)

        self.etiqueta_progreso = tk.Label(self.marco_progreso, text="Buscando archivos duplicados ...")
        self.barra_progreso = ttk.Progressbar(self.marco_progreso, orient="horizontal", length=300, mode="determinate")

        # Marco para mostrar archivos duplicados
        self.marco_duplicados = tk.Frame(self.root)
        self.marco_duplicados.pack(pady=10, fill="both", expand=True)

        self.treeview = ttk.Treeview(self.marco_duplicados, columns=("Nombre", "Ubicacion", "Hash", "Fecha"), show="headings", selectmode="extended")

        self.treeview.pack(side="left", fill="both", expand=True)
        self.treeview.heading("Nombre", text="Nombre del Archivo")
        self.treeview.heading("Ubicacion", text="Ubicacion")
        self.treeview.heading("Hash", text="Hash")
        self.treeview.heading("Fecha", text="Fecha de Creación")
        self.treeview.column("#0", width=0, stretch=tk.NO)  # Eliminar espacio para el checkbox

        # Configurar el scroll
        scroll_y = tk.Scrollbar(self.marco_duplicados, orient="vertical", command=self.treeview.yview)
        scroll_y.pack(side="right", fill="y")
        self.treeview.configure(yscrollcommand=scroll_y.set)

        # Checkbox para seleccionar todos los archivos
        self.var_seleccionar_todo = tk.IntVar()
        self.checkbox_seleccionar_todo = tk.Checkbutton(self.root, text="Seleccionar Todos", variable=self.var_seleccionar_todo, command=self.seleccionar_todo)
        self.checkbox_seleccionar_todo.pack(pady=5)
        ToolTip(self.checkbox_seleccionar_todo, "Seleccionar todos los archivos mostrados")


        # Botón para eliminar archivos seleccionados
        self.boton_eliminar = tk.Button(self.root, text="Eliminar Seleccionados", command=self.confirmar_eliminar_seleccionados)
        self.boton_eliminar.pack(pady=5)        
        ToolTip(self.boton_eliminar, "Elimina los archivos seleccionados. Cuidado!! esta acción no se puede deshacer.")


        # Configurar el tamaño de las filas después de que la ventana se haya mostrado completamente
        self.root.update_idletasks()
        self.configurar_tamano_filas()

        # Configurar el evento <Configure> para ajustar el tamaño de las filas si la ventana se redimensiona
        self.root.bind("<Configure>", self.configurar_tamano_filas)

        # Enlazar el evento de doble clic en el treeview
        self.treeview.bind("<Double-1>", self.abrir_ubicacion_archivo)

    def abrir_ventana_carpeta(self):
        carpeta_seleccionada = filedialog.askdirectory()
        if carpeta_seleccionada:
            self.carpeta_seleccionada = os.path.abspath(carpeta_seleccionada)
            self.mostrar_progreso()  # Mostrar el mensaje de progreso y la barra
            self.barra_progreso.start()
            self.root.update()

            self.buscar_archivos_duplicados(self.carpeta_seleccionada)

            self.barra_progreso.stop()
            self.barra_progreso["value"] = 100  # Asegurar que la barra de progreso esté al 100%
            self.etiqueta_progreso.config(text="Búsqueda completada.")
            self.mostrar_duplicados()
        else:
            messagebox.showinfo("Información", "No se seleccionó ninguna carpeta.")

    def mostrar_progreso(self):
        self.marco_progreso.pack(pady=10)
        self.etiqueta_progreso.pack()
        self.barra_progreso.pack(padx=10, pady=10, fill="x")

    def buscar_archivos_duplicados(self, carpeta):
        total_archivos = sum(len(files) for _, _, files in os.walk(carpeta))
        progreso = 0
        for carpeta_raiz, _, archivos in os.walk(carpeta):
            for nombre_archivo in archivos:
                ruta_archivo = os.path.join(carpeta_raiz, nombre_archivo)
                hash_archivo = self.calcular_hash(ruta_archivo)
                if hash_archivo in self.archivos_duplicados:
                    self.archivos_duplicados[hash_archivo].append(ruta_archivo)
                else:
                    self.archivos_duplicados[hash_archivo] = [ruta_archivo]
                progreso += 1
                self.barra_progreso["value"] = (progreso / total_archivos) * 100
                self.root.update_idletasks()
        # Verificar si no se encontraron archivos duplicados
        if not self.archivos_duplicados:
            messagebox.showinfo("Información", "No se encontraron archivos duplicados en la carpeta seleccionada.")

    def mostrar_duplicados(self):
        # Eliminar las filas existentes en el treeview
        for item in self.treeview.get_children():
            self.treeview.delete(item)

        # Insertar archivos duplicados en el treeview
        for hash_archivo, archivos in self.archivos_duplicados.items():
            if len(archivos) > 1:
                for archivo in archivos:
                    ubicacion = os.path.dirname(archivo)  # Obtener la ubicación del archivo
                    self.treeview.insert("", "end", values=(os.path.basename(archivo), ubicacion, hash_archivo, self.obtener_fecha_creacion(archivo)))

    def calcular_hash(self, ruta_archivo):
        try:
            sha256_hash = hashlib.sha256()
            with open(ruta_archivo, "rb") as f:
                for fragmento in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(fragmento)
            return sha256_hash.digest()
        except FileNotFoundError:
            messagebox.showinfo("Error", "El archivo no se encuentra en la ruta especificada:\n{}".format(ruta_archivo))
            return None

    def obtener_fecha_creacion(self, archivo):
        fecha_creacion = datetime.fromtimestamp(os.path.getctime(archivo), tz=timezone.utc)
        return fecha_creacion.strftime('%d-%m-%Y %H:%M:%S')

    def seleccionar_todo(self):
        if self.var_seleccionar_todo.get() == 1:
            self.treeview.selection_set(*self.treeview.get_children())
        else:
            self.treeview.selection_remove(self.treeview.get_children())

    def confirmar_eliminar_seleccionados(self):
        confirmacion = messagebox.askokcancel("Confirmar", "¿Está seguro de que desea eliminar el/los archivo/s seleccionado/s?")
        if confirmacion:
            self.eliminar_seleccionados()

    def eliminar_seleccionados(self):
        seleccionados = self.treeview.selection()
        
        # Verificar si no hay archivos seleccionados para eliminar
        if not seleccionados:
            messagebox.showinfo("Información", "No hay archivos seleccionados para eliminar.")
            return
        
        for seleccionado in seleccionados:
            archivo = self.treeview.item(seleccionado)["values"][0]  # Obtener el nombre del archivo
            ubicacion = self.treeview.item(seleccionado)["values"][1]  # Obtener la ubicación del archivo
            ruta_archivo = os.path.join(ubicacion, archivo)
            try:
                os.remove(ruta_archivo)  # Eliminar el archivo del sistema
                self.treeview.delete(seleccionado)  # Eliminar el archivo del treeview
                messagebox.showinfo("Información", "Archivo eliminado: {}".format(ruta_archivo))
            except Exception as e:
                messagebox.showerror("Error", "Error al eliminar el archivo: {}".format(e))

    def configurar_tamano_filas(self, event=None):
        # Ajustar el ancho de las columnas al ancho de la ventana
        ancho_ventana = self.root.winfo_width()
        if ancho_ventana > 0:
            ancho_columna = ancho_ventana // 4  # Dividir en 4 columnas
            for col in self.treeview["columns"]:
                self.treeview.column(col, width=ancho_columna)
            # Ajustar el ancho de la primera columna para que ocupe el espacio restante
            self.treeview.column("#0", width=0, stretch=tk.YES)  # Eliminar espacio para el checkbox

    def abrir_ubicacion_archivo(self, event):
        seleccionado = self.treeview.selection()
        if seleccionado:
            archivo = self.treeview.item(seleccionado[0])["values"][0]  # Obtener el nombre del archivo
            ubicacion = self.treeview.item(seleccionado[0])["values"][1]  # Obtener la ubicación del archivo
            ruta_archivo = os.path.join(ubicacion, archivo)
            if os.path.exists(ruta_archivo):
                # Obtener el comando para abrir la ubicación del archivo en el gestor de archivos por defecto
                if platform.system() == "Linux":
                    comando = ['nautilus', os.path.dirname(ruta_archivo)]
                elif platform.system() == "Windows":
                    comando = ['explorer', '/select,', ruta_archivo.replace('/', '\\')]
                else:
                    comando = ['open', '-R', ruta_archivo]  # En macOS, abre la ubicación del archivo en el Finder
                
                try:
                    # Ejecutar el comando del sistema para abrir la ubicación del archivo de manera asíncrona
                    subprocess.Popen(comando)
                except Exception as e:
                    messagebox.showerror("Error", "Error al abrir la ubicación del archivo: {}".format(e))
            else:
                messagebox.showerror("Error", "El archivo ya no existe en la ubicación: {}".format(ruta_archivo))
                
class Repositorios:
    def __init__(self, master):
        self.master = master
        master.title("Administrador de Repositorios")

        # Crear un marco para la lista de repositorios
        self.frame_repositorios = tk.Frame(master)
        self.frame_repositorios.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Botón para actualizar la lista de repositorios
        self.btn_actualizar = tk.Button(master, text="Actualizar Repositorios", command=self.actualizar_repositorios)
        self.btn_actualizar.pack(side=tk.LEFT, padx=10, pady=10)
        ToolTip(self.btn_actualizar, "Actualizar el listado de repositorios")


        # Botón para eliminar el repositorio seleccionado
        self.btn_eliminar = tk.Button(master, text="Eliminar Repositorio", command=self.eliminar_repositorios_seleccionados)
        self.btn_eliminar.pack(side=tk.LEFT, padx=10, pady=10)
        ToolTip(self.btn_eliminar, "Eliminar el repositorio seleccionado del sistema")

        # Botón para añadir un PPA
        self.btn_anadir = tk.Button(master, text="Añadir PPA", command=self.abrir_ventana_anadir_ppa)
        self.btn_anadir.pack(side=tk.LEFT, padx=10, pady=10)
        ToolTip(self.btn_anadir, "Añadir un PPA al sistema")

        # Variable para los checkboxes
        self.repositorios_seleccionados = []

        # Mostrar la lista de repositorios
        self.mostrar_repositorios()

    def mostrar_repositorios(self):
        # Limpiar el contenido del marco antes de mostrar la lista de repositorios
        for widget in self.frame_repositorios.winfo_children():
            widget.destroy()

        # Obtener la lista de repositorios instalados
        lista_repositorios = self.obtener_repositorios_instalados()

        # Crear un scrollbar
        scrollbar = tk.Scrollbar(self.frame_repositorios)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Crear un canvas para contener los checkboxes
        canvas = tk.Canvas(self.frame_repositorios, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Crear un frame dentro del canvas para los checkboxes
        frame_checkboxes = tk.Frame(canvas)
        canvas.create_window((0, 0), window=frame_checkboxes, anchor='nw')

        # Configurar el scrollbar
        scrollbar.config(command=canvas.yview)
        frame_checkboxes.bind("<Configure>", lambda e: canvas.config(scrollregion=canvas.bbox("all")))

        # Mostrar la lista de repositorios con checkboxes
        self.repositorios_seleccionados = []
        for repo in lista_repositorios:
            var = tk.BooleanVar()
            checkbox = tk.Checkbutton(frame_checkboxes, text=repo, variable=var, command=lambda var=var: self.on_checkbox_click(var))
            checkbox.pack(anchor='w')
            self.repositorios_seleccionados.append((repo, var))

    def obtener_repositorios_instalados(self):
        repositorios = []

        # Leer los archivos en /etc/apt/sources.list.d/
        archivos = os.listdir("/etc/apt/sources.list.d/")
        for archivo in archivos:
            if archivo.endswith(".list"):
                with open(os.path.join("/etc/apt/sources.list.d/", archivo), "r") as f:
                    contenido = f.readlines()
                    for linea in contenido:
                        if linea.startswith("deb"):
                            repositorios.append(linea.strip())

        # Leer el archivo /etc/apt/sources.list
        with open("/etc/apt/sources.list", "r") as f:
            contenido = f.readlines()
            for linea in contenido:
                if linea.startswith("deb"):
                    repositorios.append(linea.strip())

        return repositorios

    def actualizar_repositorios(self):
        try:
            subprocess.check_call(['sudo', 'apt-get', 'update'])
            self.mostrar_repositorios()
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"No se pudo actualizar la lista de repositorios: {e}")

    def eliminar_repositorios_seleccionados(self):
        seleccionados = [repo for repo, var in self.repositorios_seleccionados if var.get()]
        if not seleccionados:
            messagebox.showwarning("Advertencia", "Seleccione al menos un repositorio para eliminar.")
            return

        repo = seleccionados[0]  # Solo un repositorio debe estar seleccionado
        confirmar = messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar el repositorio: {repo}?")
        if confirmar:
            self.eliminar_repo_confirmado(repo)

    def eliminar_repo_confirmado(self, repo):
        from password import obtener_contrasena  # Importar la función para obtener la contraseña
        contrasena = obtener_contrasena()  # Obtener la contraseña

        # Determinar si el repositorio es un PPA o un repositorio regular
        if "ppa.launchpad.net" in repo:
            ppa_name = self.obtener_nombre_ppa(repo)
            if ppa_name:
                proceso = subprocess.Popen(['sudo', '-S', 'add-apt-repository', '--remove', ppa_name], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                salida, error = proceso.communicate(input=(contrasena + '\n').encode() + b'\n')
                if proceso.returncode == 0:
                    messagebox.showinfo("Éxito", f"Repositorio {repo} eliminado correctamente con APT.")
                else:
                    messagebox.showerror("Error", f"No se pudo eliminar el repositorio {repo}: {error.decode()}")
        else:
            # Eliminar los archivos en /etc/apt/sources.list.d/ con sudo
            self.eliminar_archivos_repositorio(repo, contrasena)

        # Actualizar la lista de repositorios después de eliminar uno
        self.actualizar_repositorios()

    def obtener_nombre_ppa(self, repo):
        # Extraer el nombre del PPA desde la URL del repositorio
        for line in repo.split():
            if line.startswith("ppa:"):
                return line
        return None

    def eliminar_archivos_repositorio(self, repo, contrasena):
        # Obtener la lista de archivos en el directorio /etc/apt/sources.list.d/
        archivos = os.listdir("/etc/apt/sources.list.d/")

        # Iterar sobre los archivos y eliminar los que contienen la URL del repositorio
        for archivo in archivos:
            archivo_path = os.path.join("/etc/apt/sources.list.d/", archivo)
            with open(archivo_path, "r") as f:
                contenido = f.read()
                if repo in contenido:
                    try:
                        # Eliminar el archivo .list con sudo
                        proceso = subprocess.Popen(['sudo', '-S', 'rm', archivo_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        salida, error = proceso.communicate(input=(contrasena + '\n').encode())
                        
                        # Eliminar el archivo .list.save si existe con sudo
                        archivo_save_path = archivo_path + ".save"
                        if os.path.exists(archivo_save_path):
                            proceso = subprocess.Popen(['sudo', '-S', 'rm', archivo_save_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            salida, error = proceso.communicate(input=(contrasena + '\n').encode())
                    except FileNotFoundError:
                        pass  # Si el archivo no existe, continuamos sin error

        # Mostrar mensaje de éxito
        messagebox.showinfo("Éxito", f"Repositorio {repo} eliminado correctamente del directorio /etc/apt/sources.list.d/")

    def on_checkbox_click(self, checkbox_var):
        # Deshabilitar todos los demás checkboxes si el checkbox actual está marcado
        if checkbox_var.get():
            for repo, var in self.repositorios_seleccionados:
                if var != checkbox_var:
                    var.set(False)

    def abrir_ventana_anadir_ppa(self):
        # Crear una nueva ventana para ingresar la URL del PPA
        ventana_ppa = tk.Toplevel(self.master)
        ventana_ppa.title("Añadir PPA")

        # Crear una entrada con marcador de posición para la URL del PPA
        entrada_ppa = entradaConPlaceHolder(ventana_ppa, placeholder="PPA:nombredelppa", width=50)
        entrada_ppa.pack(pady=10, padx=10)

        # Funcionalidad de clic derecho para pegar
        menu = Menu(entrada_ppa, tearoff=0)
        menu.add_command(label="Pegar", command=lambda: entrada_ppa.event_generate("<<Paste>>"))

        def mostrar_menu(event):
            menu.post(event.x_root, event.y_root)

        entrada_ppa.bind("<Button-3>", mostrar_menu)

        # Botón para añadir el PPA
        btn_anadir = tk.Button(ventana_ppa, text="Añadir", command=lambda: self.anadir_ppa(entrada_ppa.get(), ventana_ppa))
        btn_anadir.pack(pady=10)
        ToolTip(btn_anadir, "Añade el PPA indicado con add-apt-repository")

    def anadir_ppa(self, ppa_url, ventana_ppa):
        from password import obtener_contrasena  # Importar la función para obtener la contraseña
        contrasena = obtener_contrasena()  # Obtener la contraseña

        if ppa_url:
            proceso = subprocess.Popen(['sudo', '-S', 'add-apt-repository', ppa_url], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            salida, error = proceso.communicate(input=(contrasena + '\n').encode() + b'\n')
            if proceso.returncode == 0:
                messagebox.showinfo("Éxito", f"Repositorio {ppa_url} añadido correctamente.")
                self.actualizar_repositorios()
            else:
                messagebox.showerror("Error", f"No se pudo añadir el repositorio {ppa_url}: {error.decode()}")
        ventana_ppa.destroy()
    
class MonitorizarSistema:
    """
    Clase 'MonitorizarSistema'.

    Class:
        - MonitorizarSistema: Clase para monitorizar el sistema y visualizar estadísticas en una ventana emergente.

    Attributes:
        - master: El widget principal al que pertenece la ventana.

    Methods:
        - __init__(self, master): Constructor de la clase. Inicializa el widget principal al que pertenece la ventana.
            - master: El widget principal al que pertenece la ventana.
        - monitorizar_sistema(self): Método para monitorizar el sistema y visualizar estadísticas en una ventana emergente.

    Raises:
        - No se especifican excepciones en la clase.
    """

    def __init__(self, master):
        self.master = master

    def monitorizar_sistema(self):
        # Ocultar la ventana principal temporalmente
        self.master.withdraw()

        # Obtener los datos del sistema
        cpu_percent = psutil.cpu_percent()
        mem_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        # Obtener los datos de red
        red_info = psutil.net_io_counters(pernic=False)
        red_envio = red_info.bytes_sent
        red_recepcion = red_info.bytes_recv
        temperatura_cpu = psutil.sensors_temperatures().get('cpu-thermal', [None])[0]
        temperatura_cpu = temperatura_cpu.current if temperatura_cpu else None
        carga_sistema = psutil.getloadavg()[0]

        # Crear listas de nombres, valores y colores para los datos
        nombres = ['CPU', 'Memoria', 'Disco', 'Red (enviado)', 'Red (recibido)', 'Temperatura CPU', 'Carga del sistema']
        valores = [cpu_percent, mem_percent, disk_percent, red_envio / 1024 / 1024, red_recepcion / 1024 / 1024, temperatura_cpu, carga_sistema]
        colores = ['blue', 'green', 'red', 'orange', 'purple', 'cyan', 'magenta']
        unidades = ['%', '%', '%', 'MB', 'MB', '%', '']

        # Filtrar los datos que no están disponibles y actualizar las listas
        nombres = [n for n, v in zip(nombres, valores) if v is not None]
        valores = [v for v in valores if v is not None]
        colores = colores[:len(valores)]
        unidades = [u for u, v in zip(unidades, valores) if v is not None]

        # Crear una nueva ventana de Tkinter
        ventana_grafico = tk.Toplevel(self.master)
        ventana_grafico.title("Estadísticas")

        # Crear un frame para contener todo
        frame_contenedor = ttk.Frame(ventana_grafico)
        frame_contenedor.pack(fill=tk.BOTH, expand=True)

        # Crear un frame para el gráfico
        frame_grafico = ttk.Frame(frame_contenedor)
        frame_grafico.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Crear una figura de Matplotlib
        fig, ax = plt.subplots(figsize=(12, 8))

        # Visualizar los datos en un gráfico de barras
        ax.bar(nombres, valores, color=colores)
        ax.set_xlabel('Recursos del Sistema')
        ax.set_ylabel('Porcentaje de Uso / Valor')
        ax.set_title('Monitorización del Sistema')
        ax.grid(True)

        # Crear un lienzo de Matplotlib para integrarlo en la ventana de Tkinter
        canvas = FigureCanvasTkAgg(fig, master=frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Crear un frame para los datos numéricos
        frame_datos = ttk.Frame(frame_contenedor)
        frame_datos.pack(side=tk.TOP, fill=tk.X, expand=False)

        # Mostrar los datos numéricos en labels
        for nombre, valor, unidad, color in zip(nombres, valores, unidades, colores):
            label = ttk.Label(frame_datos, text=f"{nombre}: {valor:.2f} {unidad}", foreground=color)
            label.pack(anchor=tk.W, padx=10, pady=5)

        def cerrar_ventana():
            ventana_grafico.destroy()

        # Vincular el evento de cierre de la ventana a una función que solo destruya la ventana de gráficos
        ventana_grafico.protocol("WM_DELETE_WINDOW", cerrar_ventana)
        ventana_grafico.mainloop()

        
class DebInstalador:
    """
    Clase para gestionar la instalación de paquetes .deb en un sistema Ubuntu utilizando dpkg.

    Métodos:
    --------
    seleccionar_archivo()
        Abre un cuadro de diálogo para seleccionar un archivo .deb.
    instalar_deb()
        Instala el archivo .deb seleccionado utilizando dpkg y corrige dependencias si es necesario.
    """

    def __init__(self):
        """
        Inicializa la clase DebInstalador.

        Atributos:
        ----------
        file_path : str or None
            Ruta del archivo .deb seleccionado para la instalación.
        """
        self.file_path = None

    def seleccionar_archivo(self, parent=None):
        """
        Abre un cuadro de diálogo para seleccionar un archivo .deb y guarda la ruta del archivo seleccionado.

        Utiliza tkinter para mostrar un cuadro de diálogo de selección de archivo que se abre en la carpeta home del usuario.
        Si no se selecciona ningún archivo, muestra un mensaje informativo. Si se selecciona un archivo, guarda la ruta
        del archivo en self.file_path y muestra un mensaje informativo con la ruta del archivo seleccionado.
        """
        home_dir = os.path.expanduser("~")
        self.file_path = filedialog.askopenfilename(
            parent=parent,
            initialdir=home_dir,
            filetypes=[("Debian packages", "*.deb")],
        )
        if not self.file_path:
            return False
        messagebox.showinfo(
            "Información",
            f"Archivo seleccionado: {self.file_path}",
            parent=parent,
        )
        return True

    def ejecutar(self, parent=None):
        """Selecciona un .deb e instala solo si el usuario no canceló."""
        if self.seleccionar_archivo(parent):
            self.instalar_deb()

    def instalar_deb(self):
        """
        Instala el archivo .deb seleccionado utilizando dpkg y corrige dependencias si es necesario.

        Si no se ha seleccionado ningún archivo, muestra un mensaje informativo. Si se ha seleccionado un archivo,
        intenta instalarlo utilizando dpkg. Si la instalación falla debido a dependencias no satisfechas, intenta
        corregirlas utilizando apt-get.

        Muestra mensajes informativos y de error según corresponda.
        """
        # Verificar si se ha seleccionado un archivo .deb
        if not self.file_path:
            messagebox.showinfo("Información", "No se ha seleccionado ningún archivo.")
            return

        if not messagebox.askyesno(
            "¿Seguro?",
            f"¿Instalar el paquete {self.file_path} con dpkg?",
        ):
            registrar("Instalar .deb", "cancelado por el usuario", False)
            return

        contrasena = obtener_contrasena()

        def trabajador():
            comando = ["sudo", "-S", "-p", "", "dpkg", "-i", self.file_path]
            entorno = os.environ.copy()
            entorno["LC_ALL"] = "C"
            resultado = subprocess.run(
                comando,
                input=contrasena + "\n",
                capture_output=True,
                text=True,
                env=entorno,
            )
            if resultado.returncode != 0:
                fix = subprocess.run(
                    ["sudo", "-S", "-p", "", "apt-get", "-f", "install", "-y"],
                    input=contrasena + "\n",
                    capture_output=True,
                    text=True,
                    env=entorno,
                )
                ok = fix.returncode == 0
                registrar("Instalar .deb", self.file_path, ok)
                return ok, "Dependencias corregidas y paquete instalado." if ok else (
                    resultado.stderr or fix.stderr or "Error al instalar el paquete."
                )
            registrar("Instalar .deb", self.file_path, True)
            return True, "Instalación completada."

        def terminar(resultado):
            ok, mensaje = resultado
            if ok:
                messagebox.showinfo("Información", mensaje)
            else:
                messagebox.showerror("Error", mensaje)

        from registro import en_hilo, ventana_progreso
        parent = tk._default_root
        progreso, _etiqueta = ventana_progreso(parent, "Instalar .deb", f"Instalando {os.path.basename(self.file_path)}...")

        def al_terminar(resultado):
            if progreso.winfo_exists():
                progreso.destroy()
            terminar(resultado)

        en_hilo(parent, trabajador, al_terminar=al_terminar)

                
class DesinstalarPaquetes:
    """
    Una clase para gestionar la desinstalación de paquetes deb y snap en un sistema Ubuntu usando una interfaz gráfica.

    Atributos:
    root (tk.Tk): La ventana principal de la interfaz gráfica.
    search_var (tk.StringVar): Variable de texto para el campo de búsqueda.
    search_entry (tk.Entry): Campo de entrada para la búsqueda de paquetes.
    packages_listbox (Listbox): Lista que muestra los paquetes instalados.
    uninstall_button (tk.Button): Botón para desinstalar el paquete seleccionado.
    placeholder (str): Texto del placeholder del campo de búsqueda.
    installed_packages (list): Lista de paquetes instalados en el sistema.

    Métodos:
    __init__(self, root):
        Inicializa la ventana principal y los elementos de la interfaz gráfica.
    set_placeholder(self, event=None):
        Establece el placeholder en el campo de búsqueda.
    clear_placeholder(self, event=None):
        Limpia el placeholder del campo de búsqueda.
    cargar_paquetes_instalados(self):
        Carga y muestra los paquetes deb y snap instalados por el usuario en el sistema.
    actualizar_lista_paquetes(self):
        Actualiza la lista de paquetes mostrados según el término de búsqueda.
    buscar_paquete(self, event=None):
        Busca paquetes en la lista según la entrada del usuario.
    desinstalar_paquetes(self):
        Desinstala el paquete seleccionado según su tipo (deb o snap).
    """

    def __init__(self, root):
        """
        Inicializa la ventana principal y los elementos de la interfaz gráfica.
        
        Args:
        root (tk.Tk): La ventana principal de la interfaz gráfica.
        """
        self.root = root
        self.root.title("Gestor de Paquetes")
        
        # Crear campo de búsqueda con placeholder
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.root, textvariable=self.search_var, fg='grey')
        self.search_entry.pack(side=tk.TOP, padx=10, pady=10, fill=tk.X)
        self.search_entry.bind("<KeyRelease>", self.buscar_paquete)
        self.search_entry.bind("<FocusIn>", self.clear_placeholder)
        self.search_entry.bind("<FocusOut>", self.set_placeholder)
        
        self.placeholder = "Buscar"
        self.set_placeholder()

        # Crear lista de paquetes
        self.packages_listbox = Listbox(self.root, selectmode=tk.SINGLE, width=50)
        self.packages_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Agregar scroll a la lista de paquetes
        scrollbar = Scrollbar(self.root)
        scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.packages_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.packages_listbox.yview)

        # Botón para desinstalar paquete seleccionado
        self.uninstall_button = tk.Button(self.root, text="Desinstalar", command=self.desinstalar_paquetes)
        self.uninstall_button.pack(pady=10)
        ToolTip(self.uninstall_button, "Desinstalar el Paquete Seleccionado")

        # Lista de paquetes instalados
        self.installed_packages = []
        # Cargar los paquetes instalados
        self.cargar_paquetes_instalados()
        self.actualizar_lista_paquetes()  # Asegura que los paquetes se muestran al inicio

    def set_placeholder(self, event=None):
        """
        Establece el placeholder en el campo de búsqueda si está vacío.
        
        Args:
        event: Evento opcional que desencadena la función.
        """
        if not self.search_var.get():
            self.search_entry.insert(0, self.placeholder)
            self.search_entry.config(fg='grey')

    def clear_placeholder(self, event=None):
        """
        Limpia el placeholder del campo de búsqueda si está presente.
        
        Args:
        event: Evento opcional que desencadena la función.
        """
        if self.search_var.get() == self.placeholder:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg='black')

    def cargar_paquetes_instalados(self):
        """
        Carga y muestra los paquetes deb y snap instalados por el usuario en el sistema.
        """
        self.installed_packages = []  # Reinicia la lista de paquetes instalados

        # Listar paquetes deb instalados por el usuario
        deb_packages = subprocess.check_output("dpkg --get-selections | grep -v deinstall", shell=True, text=True)
        for package in deb_packages.splitlines():
            package_name = package.split()[0]
            self.installed_packages.append(f"deb: {package_name}")

        # Listar paquetes snap instalados
        snap_packages = subprocess.check_output("snap list", shell=True, text=True)
        for line in snap_packages.splitlines()[1:]:  # Omitir la primera línea de encabezado
            package_name = line.split()[0]
            self.installed_packages.append(f"snap: {package_name}")

        self.actualizar_lista_paquetes()  # Llamar aquí para mostrar los paquetes inicialmente

    def actualizar_lista_paquetes(self):
        """
        Actualiza la lista de paquetes mostrados según el término de búsqueda.
        """
        self.packages_listbox.delete(0, END)
        search_term = self.search_var.get().lower()
        for package in self.installed_packages:
            if search_term in package.lower() or search_term == self.placeholder.lower():
                self.packages_listbox.insert(END, package)

    def buscar_paquete(self, event=None):
        """
        Función para buscar paquetes según la entrada del usuario.
        
        Args:
        event: Evento opcional que desencadena la función.
        """
        self.actualizar_lista_paquetes()

    def desinstalar_paquetes(self):
        """
        Desinstala el paquete seleccionado según su tipo (deb o snap).
        """
        selected = self.packages_listbox.curselection()
        if not selected:
            messagebox.showinfo("Información", "Por favor, selecciona un paquete para desinstalar.")
            return
        
        package = self.packages_listbox.get(selected[0])
        package_type, package_name = package.split(": ")

        if not messagebox.askyesno(
            "¿Seguro?",
            f"¿Desinstalar el paquete {package_name} ({package_type})?",
            parent=self.root,
        ):
            registrar("Desinstalar paquete", f"{package_type}:{package_name} cancelado", False)
            return

        contrasena = obtener_contrasena()

        def trabajador():
            if package_type == "deb":
                args = ["apt-get", "remove", "--purge", "-y", package_name]
            elif package_type == "snap":
                args = ["snap", "remove", package_name]
            else:
                raise ValueError("Tipo de paquete desconocido.")
            resultado = subprocess.run(
                ["sudo", "-S", "-p", "", *args],
                input=contrasena + "\n",
                capture_output=True,
                text=True,
            )
            registrar("Desinstalar paquete", f"{package_type}: {package_name}", resultado.returncode == 0)
            if resultado.returncode != 0:
                raise RuntimeError(resultado.stderr or "No se pudo desinstalar el paquete.")
            return package_name

        def al_terminar(nombre):
            if progreso.winfo_exists():
                progreso.destroy()
            messagebox.showinfo("Información", f"Paquete {nombre} desinstalado correctamente.", parent=self.root)
            self.cargar_paquetes_instalados()
            self.actualizar_lista_paquetes()

        from registro import en_hilo, ventana_progreso
        progreso, _etiqueta = ventana_progreso(self.root, "Desinstalar", f"Desinstalando {package_name}...")
        en_hilo(self.root, trabajador, al_terminar=al_terminar) 
# Clase para consultar los logs del sistema

import tkinter as tk
from tkinter import scrolledtext, messagebox
import os

class consultaLogs:
    def __init__(self, master):
        self.master = master
        self.mostrar_logs()
        self.current_tooltip = None  # Añadimos un atributo para rastrear el tooltip actual

    def mostrar_logs(self):
        self.master.title("Logs del Sistema")
        
        logs_frame = tk.Frame(self.master)
        logs_frame.pack(side=tk.LEFT, fill=tk.Y)

        logs_text_frame = tk.Frame(self.master)
        logs_text_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        logs_list = tk.Listbox(logs_frame)
        logs_list.pack(side=tk.LEFT, fill=tk.Y)
        
        scrollbar = tk.Scrollbar(logs_frame, orient="vertical")
        scrollbar.config(command=logs_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        logs_list.config(yscrollcommand=scrollbar.set)
        
        log_files = {
            "syslog": "/var/log/syslog",
            "auth.log": "/var/log/auth.log",
            "kern.log": "/var/log/kern.log",
            "dmesg": "/var/log/dmesg",
            "boot.log": "/var/log/boot.log",
            "dpkg.log": "/var/log/dpkg.log",
            "faillog": "/var/log/faillog",
            "btmp": "/var/log/btmp",
            "lastlog": "/var/log/lastlog",
            "apt history.log": "/var/log/apt/history.log",
            "apt term.log": "/var/log/apt/term.log",
            "Xorg.0.log": "/var/log/Xorg.0.log",
            "ufw.log": "/var/log/ufw.log",
            "access.log": "/var/log/apache2/access.log",
            "error.log": "/var/log/apache2/error.log"
        }

        log_tooltips = {
            "syslog": "Registra los mensajes del sistema y las aplicaciones.",
            "auth.log": "Registra los eventos de autenticación.",
            "kern.log": "Registra los mensajes del núcleo.",
            "dmesg": "Muestra los mensajes del anillo de buffer del kernel.",
            "boot.log": "Registra los eventos del sistema durante el arranque.",
            "dpkg.log": "Registra todas las acciones realizadas por el gestor de paquetes dpkg.",
            "faillog": "Muestra los intentos de inicio de sesión fallidos.",
            "btmp": "Registra los intentos de inicio de sesión fallidos.",
            "lastlog": "Muestra la última vez que cada usuario se conectó.",
            "apt history.log": "Registra las acciones realizadas por el gestor de paquetes APT.",
            "apt term.log": "Contiene los registros detallados de las acciones de APT.",
            "Xorg.0.log": "Contiene los registros del servidor gráfico X.Org.",
            "ufw.log": "Registra las acciones del cortafuegos UFW.",
            "access.log": "Registra solicitudes de acceso de un servidor Apache (si está instalado)",
            "error.log": "Registro de errores producidos en un servidor Apache (si está instalado)"
        }

        for log in log_files:
            logs_list.insert(tk.END, log)

        logs_text = scrolledtext.ScrolledText(logs_text_frame, wrap=tk.WORD)
        logs_text.pack(fill=tk.BOTH, expand=True)

        def mostrar_contenido_log(event):
            seleccion = logs_list.curselection()
            if seleccion:
                log_seleccionado = logs_list.get(seleccion[0])
                ruta_log = log_files.get(log_seleccionado)
                if ruta_log:
                    try:
                        with open(ruta_log, 'r') as file:
                            contenido = file.read()
                            logs_text.delete(1.0, tk.END)
                            logs_text.insert(tk.INSERT, contenido)
                    except PermissionError:
                        messagebox.showerror("Error", f"No se pudo abrir el archivo de log seleccionado: {log_seleccionado}. Permiso denegado.")
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo abrir el archivo de log seleccionado: {log_seleccionado}. Error: {str(e)}")

        def mostrar_tooltip(event):
            if self.current_tooltip:  # Si hay un tooltip activo, destrúyelo
                self.current_tooltip.hide_tooltip()
            seleccion = logs_list.nearest(event.y)
            if seleccion >= 0:
                log_seleccionado = logs_list.get(seleccion)
                tooltip_text = log_tooltips.get(log_seleccionado, "")
                self.current_tooltip = ToolTip(logs_list, tooltip_text)
                self.current_tooltip.show_tooltip(event)

        def ocultar_tooltip(event):
            if self.current_tooltip:
                self.current_tooltip.hide_tooltip()
                self.current_tooltip = None

        logs_list.bind('<<ListboxSelect>>', mostrar_contenido_log)
        logs_list.bind("<Motion>", mostrar_tooltip)
        logs_list.bind("<Leave>", ocultar_tooltip)