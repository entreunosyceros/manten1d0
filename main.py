import sys
import subprocess
import os


def _ruta_python_venv():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")


def _relanzar_en_venv_si_procede():
    python_venv = _ruta_python_venv()
    if not os.path.exists(python_venv):
        return
    if os.path.realpath(sys.executable) == os.path.realpath(python_venv):
        return
    os.execv(python_venv, [python_venv, os.path.abspath(__file__), *sys.argv[1:]])


_relanzar_en_venv_si_procede()

try:
    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog
except ImportError:
    # Instalar python3-tk automáticamente sin mostrar mensaje al usuario
    proceso_instalacion = subprocess.Popen(
        ["sudo", "apt", "install", "-y", "python3-tk", "python3-pip"],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    proceso_instalacion.communicate(input="\n")

    if proceso_instalacion.returncode != 0:
        exit(1)

    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog

import threading
import time
import webbrowser
import requests
from about import mostrar_about
from documentacion import mostrar_documentacion
from cat_informacion import Informacion
from password import limpiar_archivos_configuracion, obtener_contrasena
from dependencias import instalar_dependencias, resumen_dependencias_faltantes
from menuCategorias import archivos_cat, diccionario_cat, informacion_cat, internet_cat, navegadores_cat, perfil_cat, red_local_cat, sistema_cat, notas_cat, inicio_cat
import preferencias  # Importar el módulo de preferencias para manejar el cambio de tema
from registro import mostrar_registro
from bandeja import BandejaSistema


def instalar_dependencias_con_progreso(parent):
    progress_window = tk.Toplevel(parent)
    progress_window.title("Instalando dependencias")
    progress_window.geometry("360x110")
    progress_window.resizable(False, False)
    progress_window.transient(parent)
    progress_window.grab_set()

    progress_label = tk.Label(progress_window, text="Instalando dependencias...")
    progress_label.pack(pady=5)

    progress_bar = ttk.Progressbar(progress_window, length=280, mode="determinate")
    progress_bar.pack(pady=5)
    progress_bar["value"] = 0
    progress_bar["maximum"] = 100

    resultado = {"ok": False, "error": None}

    def actualizar_progreso(valor, texto=""):
        if not progress_window.winfo_exists():
            return
        progress_bar["value"] = valor
        if texto:
            progress_label.config(text=texto)

    def finalizar():
        if progress_window.winfo_exists():
            progress_window.grab_release()
            progress_window.destroy()

    def trabajador():
        ok, error = instalar_dependencias(
            on_progress=lambda valor, texto="": parent.after(
                0, lambda v=valor, t=texto: actualizar_progreso(v, t)
            )
        )
        resultado["ok"] = ok
        resultado["error"] = error
        parent.after(0, finalizar)

    threading.Thread(target=trabajador, daemon=True).start()
    parent.wait_window(progress_window)
    return resultado["ok"], resultado["error"]


def main():
    print(f"Ejecutando programa con: {sys.executable}")

    obtener_contrasena()

    root = tk.Tk()
    root.title("Comprobando Dependencias")
    root.resizable(False, False)

    progress_bar = ttk.Progressbar(root, orient="horizontal", length=200, mode="indeterminate")
    progress_bar.pack(pady=20)
    progress_bar.start()

    label = tk.Label(root, text="Comprobando dependencias...")
    label.pack()

    root.after(200, lambda: verificar_dependencias_con_progreso(root, progress_bar, label))
    root.mainloop()


def verificar_dependencias_con_progreso(root, progress_bar, label):
    faltan_sistema, faltan_pip = resumen_dependencias_faltantes()
    if faltan_sistema or faltan_pip:
        bloques = []
        if faltan_sistema:
            bloques.append("Sistema:\n- " + "\n- ".join(faltan_sistema))
        if faltan_pip:
            bloques.append("Python:\n- " + "\n- ".join(faltan_pip))
        mensaje = (
            "Faltan dependencias imprescindibles:\n\n"
            + "\n\n".join(bloques)
            + "\n\n¿Quieres instalarlas ahora?"
        )
        if messagebox.askyesno("Instalación de dependencias", mensaje):
            ok, error = instalar_dependencias_con_progreso(root)
            if not ok:
                messagebox.showerror(
                    "Error de instalación",
                    error or "No se pudieron instalar las dependencias.",
                )
                root.destroy()
                return
            verificar_dependencias_con_progreso(root, progress_bar, label)
        else:
            messagebox.showinfo(
                "Información",
                "El programa no puede iniciar sin todas las dependencias instaladas.",
            )
            root.destroy()
    else:
        close_progress(root, progress_bar, label)

def close_progress(root, progress_bar, label):
    progress_bar.stop()
    progress_bar.destroy()
    label.destroy()

    # Mostrar mensaje de dependencias instaladas
    messagebox.showinfo(
        "Información",
        "¡Todas las dependencias están instaladas! Haz clic en OK para iniciar el programa...",
    )
    # Cerrar la ventana de progreso
    root.destroy()
    # Crear la ventana principal
    main_window = tk.Tk()
    VentanaPrincipal(main_window)
    main_window.mainloop()

##############################################################VENTANA PRINCIPAL##############################################################

class VentanaPrincipal:
    def __init__(self, root):
        from tooltip import ToolTip

        self.root = root
        self.root.title("Manten1-d0")
        self.root.geometry("800x700")
        self.root.minsize(800, 700)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._al_pulsar_cerrar)
        self._bandeja = None

        # Cambiar el color de fondo de la ventana
        self.root.config(bg="lightgrey")
        
##############################################################FUNCIONES PARA MENÚ SUPERIOR##########################################################

        # Función para abrir la ventana de Opciones/Personalización
        def abrir_ventana_personalizacion():
            preferencias.abrir_ventana_configuracion(root)
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        # Función para abrir la ventana de actualizaciones
        def abrir_ventana_actualizaciones():
            # Importar el módulo actualizaciones.py
            import actualizaciones
            # Llamar a la función para mostrar la ventana de actualizaciones
            actualizaciones.mostrar_ventana_actualizaciones()
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        def abrir_url():

            url = tk.simpledialog.askstring("Abrir URL", "Ingrese la URL que desea abrir:")
            if url:
                webbrowser.open_new(url)

        def abrir_url_github():

            webbrowser.open("https://github.com/sapoclay/manten1d0")
            
        def abrir_terminal():
            try:
                # Comando para abrir la terminal predeterminada en Ubuntu
                subprocess.Popen(["gnome-terminal"])
            except Exception as e:
                # Manejar cualquier excepción que pueda ocurrir al intentar abrir la terminal
                print(f"No se pudo abrir la terminal: {e}")

#################################################### MENÚ SUPERIOR ##############################################################
        def menu():
            # Crear el menú superior
            self.menu_superior = tk.Menu(self.root)
            self.menu_archivo = tk.Menu(self.menu_superior, tearoff=0)
            self.menu_archivo.add_command(label="Abrir Terminal (Ctrl+Alt+T)", command=abrir_terminal)
            self.menu_archivo.add_separator()
            self.menu_archivo.add_command(label="Abrir URL en Navegador", command=abrir_url)
            self.menu_archivo.add_separator()
            self.menu_archivo.add_command(label="Salir", command=self.cerrar_ventana_principal)
            self.menu_superior.add_cascade(label="Archivo", menu=self.menu_archivo)
            # Crear el menú Preferencias
            preferencias_menu = tk.Menu(self.root, tearoff=0)
            preferencias_menu.add_command(label="Repositorio GitHub", command=abrir_url_github)
            preferencias_menu.add_separator()
            preferencias_menu.add_command(
                label="Buscar Actualizaciones", command=abrir_ventana_actualizaciones
            )
            preferencias_menu.add_separator()
            preferencias_menu.add_command(label="Opciones", command=abrir_ventana_personalizacion)
            preferencias_menu.add_separator()
            preferencias_menu.add_command(label="Registro de acciones", command=lambda: mostrar_registro(self.root))
            preferencias_menu.add_command(
                label="Atajos de teclado",
                command=lambda: messagebox.showinfo(
                    "Atajos",
                    "Alt+1 Inicio\nAlt+2 Perfil Usuario\nAlt+3 Información\nAlt+4 Sistema\n"
                    "Alt+5 Archivos\nAlt+6 Internet\nAlt+7 Red Local\nAlt+8 Navegadores\n"
                    "Alt+9 Diccionario\nAlt+0 Notas",
                ),
            )
            self.menu_superior.add_cascade(label="Preferencias", menu=preferencias_menu)
            menu_ayuda = tk.Menu(self.menu_superior, tearoff=0)
            menu_ayuda.add_command(
                label="Documentación",
                command=lambda: mostrar_documentacion(self.root),
            )
            menu_ayuda.add_separator()
            menu_ayuda.add_command(label="Acerca de", command=mostrar_about)
            self.menu_superior.add_cascade(label="Ayuda", menu=menu_ayuda)
            self.root.config(menu=self.menu_superior)

        # Llamamos al menú superior creado con la función menú
        menu()
        
##################################################################################################################################
##############################################MENÚ LATERAL########################################################################
        def menu_lateral():
            # Crear el menú lateral con categorías
            self.menu_lateral = tk.Frame(self.root, width=210, bg="lightgrey")
            self.menu_lateral.pack(side="left", fill="y")
            self.menu_lateral.pack_propagate(False)

            # Categorías para el menú lateral
            self.categorias = [
                "Inicio",
                "Perfil Usuario",
                "Información",
                "Sistema",
                "Archivos",
                "Internet",
                "Red Local",
                "Navegadores",
                "Diccionario",
                "Notas",
            ]
            self.botones_categorias = []
            for indice, categoria in enumerate(self.categorias, start=1):
                tecla = "0" if indice == 10 else str(indice)
                boton = tk.Button(
                    self.menu_lateral,
                    text=categoria,
                    width=20,
                    command=lambda c=categoria: self.mostrar_subcategorias(c),
                )
                boton.pack(pady=5)
                ToolTip(boton, f"Categoría {categoria} (Alt+{tecla})")
                self.botones_categorias.append(boton)
                self.root.bind_all(
                    f"<Alt-Key-{tecla}>",
                    lambda event, c=categoria: self.mostrar_subcategorias(c),
                )
            # Dibujar una línea horizontal
            self.canvas = tk.Canvas(self.menu_lateral, width=50, height=2, bg="lightgrey", highlightthickness=0)
            self.canvas.create_line(0, 1, 50, 1, fill="black")
            self.canvas.pack(pady=10)        
            # Crear indicador de conexión a Internet
            self.indicador_internet = tk.Label(
                self.menu_lateral,
                text="Estado de la conexión",
                bg="red",
                fg="white",
                width=20,
                height=1,
            )
            
            self.indicador_internet.pack(pady=20)
            ToolTip(self.indicador_internet, "Estado de la conexión a internet del equipo")
            # Iniciar la verificación de conexión a Internet
            self.check_connection()

        menu_lateral()
############################################################################################################################################        
        
        # Crear el área central para mostrar subcategorías
        self.area_central = tk.Frame(self.root, bg="lightgrey", borderwidth=0)  # Eliminar el borde
        self.area_central.pack(side="top", fill="both", expand=True)  # Ajustar el área central

        # Mensaje de bienvenida
        self.label_bienvenida = tk.Label(
            self.area_central,
            text="¡Bienvenid@!\n Comienza haciendo clic\n en una categoría del menú lateral.",
            font=("Arial", 18, "bold"),
            bg="lightgrey",
        )
        self.label_bienvenida.pack(pady=50)

        # Contenedor para el label de subcategorías
        self.frame_subcategorias = tk.Frame(
            self.area_central, bg="lightgrey", padx=10, pady=10
        )  # Ajustar el espaciado interno
        self.frame_subcategorias.pack(
            anchor="n", pady=(0, 20)
        )  # Espaciado en la parte superior y anclar al norte

        self.label_subcategorias = tk.Label(
            self.area_central, text="", font=("Arial", 12), bg="lightgrey", padx=10, pady=0
        )
        self.label_subcategorias.pack()

        # Crear el contenedor para el widget Text y la barra de desplazamiento para mostrar la categoría Información
        self.contenedor_texto = tk.Frame(self.root)
        # Contenedor Deshabilitado al inicio
        self.contenedor_texto.pack_forget()

        # Crear el widget Text para mostrar la información del sistema (inicialmente deshabilitado)
        self.texto_informacion = tk.Text(
            self.contenedor_texto, wrap=tk.WORD, font=("Arial", 12), state=tk.DISABLED
        )
        self.texto_informacion.pack(expand=True, fill="both", side="left")
        self.texto_informacion.pack_forget()  # Ocultar el widget Text

        # Agregar barra de desplazamiento vertical
        self.scrollbar_vertical = ttk.Scrollbar(
            self.contenedor_texto, orient="vertical", command=self.texto_informacion.yview
        )
        self.scrollbar_vertical.pack(side="right", fill="y")
        self.texto_informacion.config(yscrollcommand=self.scrollbar_vertical.set)

        # Mensajes personalizados para cada categoría
        self.mensajes_personalizados = {
            "Inicio": "Resumen del estado del equipo",
            "Información": "Información sobre el Sistema Operativo",
            "Perfil Usuario": "Modifica los datos de tu perfil de usuario en el sistema",
            "Sistema": "Configuraciones y detalles del Sistema Operativo.",
            "Archivos": "Opciones sobre archivos del Sistema Operativo",
            "Internet": "Configuraciones y detalles sobre la conexión a Internet.",
            "Red Local": "Configuraciones y acciones sobre la red local.",
            "Navegadores": "Acciones con los navegadores web.",
            "Diccionario": "Diccionario sobre comandos Gnu/Linux",
            "Notas": "Escribe tus apuntes y notas rápidas",
        }

        # Llenar el área de texto con la información inicial
        self.mostrar_informacion_sistema()
        self.root.after(200, lambda: self.mostrar_subcategorias("Inicio"))
        self.root.after(
            400,
            lambda: self._iniciar_bandeja(
                abrir_terminal,
                abrir_ventana_personalizacion,
                abrir_ventana_actualizaciones,
            ),
        )

    # Función para mostrar u ocultar elementos en el área principal según la categoría seleccionada. También se hacen las llamadas a funciones
    def mostrar_subcategorias(self, categoria):
        mensaje_personalizado = self.mensajes_personalizados.get(categoria, None)

        if categoria == "Inicio":

            inicio_cat(self, mensaje_personalizado)

        elif categoria == "Información":

            informacion_cat(self, mensaje_personalizado)

        elif categoria == "Diccionario":

            diccionario_cat(self, mensaje_personalizado)
            
        elif categoria == "Notas":

            notas_cat(self, mensaje_personalizado)

        elif categoria == "Perfil Usuario":

            perfil_cat(self, mensaje_personalizado)

        elif categoria == "Sistema":

            sistema_cat(self, mensaje_personalizado)
            if preferencias.tema_seleccionado == "Claro":
                return
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Archivos":

            archivos_cat(self, mensaje_personalizado)
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Internet":

            internet_cat(self, mensaje_personalizado)
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Red Local":

            red_local_cat(self, mensaje_personalizado)
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        elif categoria == "Navegadores":

            navegadores_cat(self, mensaje_personalizado)
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

        else:
            self.contenedor_texto.pack_forget()  # Deshabilitar contenedor categoría Información
            self.texto_informacion.pack_forget()  # Ocultar el widget Text
            self.texto_informacion.delete('1.0', tk.END)  # Borrar el contenido del widget Text
            self.label_bienvenida.pack_forget()  # Ocultar el mensaje de bienvenida
            if mensaje_personalizado:
                self.label_subcategorias.config(
                    text=mensaje_personalizado, font=("Arial", 14, "bold")
                )  # Ajustar el texto al mensaje personalizado
            else:
                self.label_subcategorias.config(
                    text=f"Subcategorías de {categoria}", font=("Arial", 12)
                )  # Restaurar el texto original
            self.label_subcategorias.pack()  # Mostrar la etiqueta de subcategorías
            # Aplicar el tema seleccionado a la nueva ventana
            preferencias.cambiar_tema(self.area_central, preferencias.tema_seleccionado)

    # Función para mostrar la información del sistema dentro de la categoría información. Toma los datos de información.py
    def mostrar_informacion_sistema(self):
        def obtener_temperatura_cpu():
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as file:
                    temperatura_miligrados = int(file.read().strip())
                    return temperatura_miligrados / 1000.0
            except FileNotFoundError:
                return None

        # Obtener la información del sistema utilizando la clase Informacion
        info_completa = Informacion.obtener_informacion_completa()
        usuario = info_completa["Usuario"]
        sistema_operativo = info_completa["Sistema Operativo"]
        version_sistema = info_completa["Versión de Sistema"]
        version_ubuntu = info_completa["Versión de Ubuntu"]
        tipo_escritorio = info_completa["Tipo de Escritorio"]
        tiempo_actividad = info_completa["Tiempo de Actividad"]
        tiempo_arranque = info_completa.get("Tiempo de Arranque", "No disponible")
        tarjeta_grafica = info_completa["Información de la Tarjeta Gráfica"]
        interfaces_red = ", ".join(
            info_completa["Interfaces de Red"]
        )  # Convertir la lista a cadena separada por comas
        ip_local = info_completa["Dirección IP Local"]
        ip_publica = info_completa["Dirección IP Pública"]
        dns_local = info_completa["dns local"]
        dns_publico = info_completa["dns publico"]
        zona_horaria = info_completa["Zona Horaria"]
        procesador = Informacion.obtener_informacion_procesador()
        memoria = Informacion.obtener_informacion_memoria()

        # Obtener la temperatura del procesador
        temperatura_cpu = obtener_temperatura_cpu()

        # Crear el texto con la información del sistema
        texto_info = [
            ("Usuario:", usuario),
            ("Sistema Operativo:", sistema_operativo),
            ("Versión del Sistema:", version_sistema),
            ("Versión de Ubuntu:", version_ubuntu),
            ("Tipo Escritorio:", tipo_escritorio),
            ("Tiempo de actividad:", tiempo_actividad),
            ("Tiempo de arranque:", tiempo_arranque),
            ("-" * 110, ""),
            ("Interfaces de Red:", interfaces_red),
            ("IP Local:", ip_local),
            ("IP Pública:", ip_publica),
            ("DNS Local:", dns_local),
            ("DNS Público:", dns_publico),
            ("Zona Horaria:", zona_horaria),
            (
                "Temperatura CPU:",
                f"{temperatura_cpu} °C" if temperatura_cpu is not None else "No disponible",
            ),
            ("-" * 110, ""),
        ]

        # Insertar el texto en el widget Text
        self.texto_informacion.config(state=tk.NORMAL)  # Habilitar la edición
        self.texto_informacion.delete(
            '1.0', tk.END
        ) 

        for label, value in texto_info:
            self.texto_informacion.insert(
                tk.END, f"{label} ", "bold"
            )  # Insertar texto estático con negrita
            self.texto_informacion.insert(tk.END, f"{value}\n")  # Insertar valor de la variable
            self.texto_informacion.tag_configure(
                "bold", font=("Arial", 12, "bold")
            )  # Aplicar estilo de texto negrita al texto estático

        self.texto_informacion.insert(
            tk.END, "\nInformación de la tarjeta gráfica:\n", "bold"
        )
        if isinstance(tarjeta_grafica, dict):
            tarjetas = [tarjeta_grafica]
        else:
            tarjetas = tarjeta_grafica or []
        for indice, gpu in enumerate(tarjetas, start=1):
            if len(tarjetas) > 1:
                self.texto_informacion.insert(tk.END, f"\nGPU {indice}\n", "bold")
            for key, value in gpu.items():
                if str(key).startswith("_"):
                    continue
                self.texto_informacion.insert(tk.END, f"{key}: {value}\n")

        self.texto_informacion.insert(tk.END, "-" * 110 + "\n")  # Línea horizontal

        self.texto_informacion.insert(
            tk.END, "\nInformación del Procesador:\n", "bold"
        )  # Texto "Información del Procesador" en negrita
        for item in procesador:
            self.texto_informacion.insert(tk.END, f"{item[0]}: {item[1]}\n")

        self.texto_informacion.insert(tk.END, "-" * 110 + "\n")  # Línea horizontal

        self.texto_informacion.insert(
            tk.END, "\nInformación de la Memoria:\n", "bold"
        )  # Texto "Información de la Memoria" en negrita
        for key, value in memoria.items():
            self.texto_informacion.insert(tk.END, f"{key}: {value}\n")

        self.texto_informacion.config(state=tk.DISABLED)  # Deshabilitar la edición
        self._informe_texto = self.texto_informacion.get("1.0", "end-1c")

    def copiar_informe_sistema(self):
        texto = getattr(self, "_informe_texto", "") or self.texto_informacion.get("1.0", "end-1c")
        if not texto.strip():
            messagebox.showwarning("Informe", "No hay informe para copiar.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.root.update()
        messagebox.showinfo("Informe", "El informe se ha copiado al portapapeles.")

    def exportar_informe_sistema(self):
        texto = getattr(self, "_informe_texto", "") or self.texto_informacion.get("1.0", "end-1c")
        if not texto.strip():
            messagebox.showwarning("Informe", "No hay informe para exportar.")
            return
        destino = filedialog.asksaveasfilename(
            parent=self.root,
            title="Exportar informe",
            defaultextension=".txt",
            initialfile="informe-manten1d0.txt",
            filetypes=(("Texto", "*.txt"), ("Todos los archivos", "*.*")),
        )
        if not destino:
            return
        try:
            with open(destino, "w", encoding="utf-8") as archivo:
                archivo.write(texto.rstrip() + "\n")
        except OSError as error:
            messagebox.showerror("Informe", f"No se pudo guardar el archivo:\n{error}")
            return
        messagebox.showinfo("Informe", f"Informe guardado en:\n{destino}")

    def _iniciar_bandeja(self, abrir_terminal, abrir_opciones, abrir_actualizaciones):
        bandeja = BandejaSistema(
            self,
            {
                "terminal": abrir_terminal,
                "opciones": abrir_opciones,
                "actualizaciones": abrir_actualizaciones,
                "registro": lambda: mostrar_registro(self.root),
                "documentacion": lambda: mostrar_documentacion(self.root),
                "about": mostrar_about,
                "salir": self.cerrar_ventana_principal,
                "ir_a": self.mostrar_subcategorias,
            },
        )
        try:
            if bandeja.iniciar():
                self._bandeja = bandeja
        except Exception:
            self._bandeja = None

    def _al_pulsar_cerrar(self):
        if self._bandeja and self._bandeja.disponible:
            self._bandeja.ocultar()
            return
        self.cerrar_ventana_principal()

    def cerrar_ventana_principal(self):
        after_id = getattr(self, "_internet_check_after_id", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        if self._bandeja is not None:
            self._bandeja.detener()
            self._bandeja = None
        limpiar_archivos_configuracion()
        self.root.destroy()

    def check_connection(self):
        # Programar la primera comprobación cuando el mainloop ya esté activo
        self._internet_check_after_id = self.root.after(200, self._comprobar_internet)

    def _comprobar_internet(self):
        def trabajador():
            try:
                requests.get("https://www.google.com", timeout=3)
                estado = ("green", "Conexión establecida")
            except requests.RequestException:
                estado = ("red", "Sin conexión")
            try:
                self.root.after(0, lambda e=estado: self._aplicar_estado_internet(*e))
            except RuntimeError:
                return

        threading.Thread(target=trabajador, daemon=True).start()

    def _aplicar_estado_internet(self, color, texto):
        if not self.root.winfo_exists():
            return
        self.indicador_internet.config(bg=color, text=texto)
        self._internet_check_after_id = self.root.after(10000, self._comprobar_internet)

if __name__ == "__main__":
    main()