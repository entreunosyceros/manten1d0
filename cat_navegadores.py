"""
Clase `LimpiadorNavegadores` y los módulos asociados para la limpieza de caché y historial de navegadores.
 
Imports:
    - subprocess: Para ejecutar procesos del sistema.
    - os: Para realizar operaciones relacionadas con el sistema operativo.
    - threading: Para ejecutar operaciones en segundo plano.
    - messagebox desde tkinter: Para mostrar mensajes de alerta.

Clase:
    - LimpiadorNavegadores: Clase estática que proporciona métodos para limpiar la caché y el historial de navegadores web.

Métodos Estáticos:
    - limpiar_cache_chrome(window, boton, callback=None): Limpia la caché de Google Chrome.
    - limpiar_cache_firefox(window, boton, callback=None): Limpia la caché de Mozilla Firefox.
    - limpiar_cache_edge(window, boton, callback=None): Limpia la caché de Microsoft Edge.
    - _limpiar_cache(window, boton, executable, argument, callback=None): Método privado para realizar la limpieza de caché.
    - limpiar_historial_chrome(): Limpia el historial de Google Chrome.
    - limpiar_historial_firefox(): Limpia el historial de Mozilla Firefox.
    - limpiar_historial_edge(): Limpia el historial de Microsoft Edge.

Raises:
    - FileNotFoundError: Si el ejecutable del navegador no se encuentra en la ruta por defecto.
    - subprocess.CalledProcessError: Si ocurre un error al ejecutar el comando para limpiar la caché o el historial.
"""

import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from registro import sudo_shell
from tooltip import con_tooltip

# Clase para realizar la limpieza de la caché de los navegadores
class LimpiadorNavegadores:
    @staticmethod
    def limpiar_cache_chrome(window, boton, callback=None):
        # Deshabilitar el botón para evitar múltiples clics
        boton.config(state="disabled")
        chrome_path = '/usr/bin/google-chrome'
        if not os.path.exists(chrome_path):
            return "Google Chrome no está instalado o no se encuentra en la ruta por defecto."

        try:
            mensaje = "Limpiando caché de Google Chrome..."
            if callback:
                callback(mensaje)

            # Eliminar el directorio de caché de Google Chrome
            chrome_cache_path = os.path.expanduser("~/.cache/google-chrome")
            if os.path.exists(chrome_cache_path):
                os.system(f"rm -rf {chrome_cache_path}")

            # Limpiar la caché de Google Chrome
            threading.Thread(
                target=LimpiadorNavegadores._limpiar_cache,
                args=(window, boton, chrome_path, '--clear-browser-data', callback),
            ).start()

        except Exception as e:
            return f"Error al limpiar la caché de Google Chrome: {e}"

    @staticmethod
    def limpiar_cache_firefox(window, boton, callback=None):
        # Deshabilitar el botón para evitar múltiples clics
        boton.config(state="disabled")
        firefox_path = '/usr/bin/firefox'
        if not os.path.exists(firefox_path):
            return "Mozilla Firefox no está instalado o no se encuentra en la ruta por defecto."

        try:
            mensaje = "Limpiando caché de Mozilla Firefox..."
            if callback:
                callback(mensaje)

            # Eliminar el directorio de caché de Mozilla Firefox
            firefox_cache_path = os.path.expanduser("~/.cache/mozilla")
            if os.path.exists(firefox_cache_path):
                os.system(f"rm -rf {firefox_cache_path}")

            # Limpiar la caché de Mozilla Firefox
            threading.Thread(
                target=LimpiadorNavegadores._limpiar_cache,
                args=(window, boton, firefox_path, '--clear-cache', callback),
            ).start()

        except Exception as e:
            return f"Error al limpiar la caché de Mozilla Firefox: {e}"

    @staticmethod
    def limpiar_cache_edge(window, boton, callback=None):
        # Deshabilitar el botón para evitar múltiples clics
        boton.config(state="disabled")
        edge_path = '/usr/bin/microsoft-edge'
        if not os.path.exists(edge_path):
            return "Microsoft Edge no está instalado o no se encuentra en la ruta por defecto."

        try:
            mensaje = "Limpiando caché de Microsoft Edge..."
            if callback:
                callback(mensaje)

            # Eliminar el directorio de caché de Microsoft Edge
            edge_cache_path = os.path.expanduser("~/.cache/microsoft-edge")
            if os.path.exists(edge_cache_path):
                os.system(f"rm -rf {edge_cache_path}")

            # Limpiar la caché de Microsoft Edge
            threading.Thread(
                target=LimpiadorNavegadores._limpiar_cache,
                args=(window, boton, edge_path, '--clear-browser-data', callback),
            ).start()

        except Exception as e:
            return f"Error al limpiar la caché de Microsoft Edge: {e}"

    @staticmethod
    def _limpiar_cache(window, boton, executable, argument, callback=None):
        try:
            subprocess.run([executable, argument], check=True)
            mensaje = "Caché limpiada correctamente."
            if callback:
                callback(mensaje)
                boton.config(state="normal")
        except subprocess.CalledProcessError as e:
            mensaje = f"Error al limpiar la caché: {e}"
            if callback:
                callback(mensaje)

    @staticmethod
    def limpiar_historial_chrome():
        try:
            # Comando para limpiar el historial de Chrome en Linux
            subprocess.run(["google-chrome", "--delete-history"], check=True)
            messagebox.showinfo("Éxito", "Historial de Chrome limpiado con éxito.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            messagebox.showerror(
                "Error",
                "No se pudo limpiar el historial de Chrome. Asegúrate de tener Google Chrome instalado.",
            )

    @staticmethod
    def limpiar_historial_firefox():
        try:
            # Comando para limpiar el historial de Firefox en Linux
            subprocess.run(["firefox", "--delete-history"], check=True)
            messagebox.showinfo("Éxito", "Historial de Firefox limpiado con éxito.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            messagebox.showerror(
                "Error",
                "No se pudo limpiar el historial de Firefox. Asegúrate de tener Mozilla Firefox instalado.",
            )

    @staticmethod
    def limpiar_historial_edge():
        try:
            # Comando para limpiar el historial de Edge en Linux
            subprocess.run(["microsoft-edge", "--delete-history"], check=True)
            messagebox.showinfo("Éxito", "Historial de Edge limpiado con éxito.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            messagebox.showerror(
                "Error",
                "No se pudo limpiar el historial de Edge. Asegúrate de tener Microsoft Edge instalado.",
            )
class InstalarNavegadores:
    """
    Clase para instalar navegadores web en Ubuntu.

    Métodos estáticos disponibles:
        - instalar_chrome(): Instala Google Chrome.
        - instalar_firefox(): Instala Mozilla Firefox.
        - instalar_edge(): Instala Microsoft Edge.

    Ejemplo de uso:
        Para instalar Google Chrome:
            InstalarNavegadores.instalar_chrome()

        Para instalar Mozilla Firefox:
            InstalarNavegadores.instalar_firefox()

        Para instalar Microsoft Edge:
            InstalarNavegadores.instalar_edge()
    """
    @staticmethod
    def instalar_chrome():
        progress_window = tk.Toplevel()
        progress_window.title("Instalando Google Chrome")
        progress_bar = ttk.Progressbar(progress_window, length=300, mode="indeterminate")
        progress_bar.pack(pady=10)
        progress_bar.start()

        # Función para ejecutar los comandos en un hilo separado
        def instalar():
            try:
                subprocess.run([
                    "wget",
                    "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
                ], check=True)

                subprocess.run(
                    ["sudo", "dpkg", "-i", "google-chrome-stable_current_amd64.deb"],
                    check=True
                )

                subprocess.run(["sudo", "apt-get", "-f", "install", "-y"], check=True)

                os.remove("google-chrome-stable_current_amd64.deb")

                messagebox.showinfo("Éxito", "Google Chrome se ha instalado correctamente.")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Error al instalar Google Chrome: {e}")
            except FileNotFoundError as e:
                messagebox.showerror("Error", f"Error al eliminar el archivo: {e}")
            finally:
                progress_bar.stop()
                progress_window.destroy()

        # Ejecutar la función en un hilo separado
        threading.Thread(target=instalar).start()
            
    @staticmethod
    def instalar_firefox():
        progress_window = tk.Toplevel()
        progress_window.title("Instalando Mozilla Firefox")
        progress_bar = ttk.Progressbar(progress_window, length=300, mode="indeterminate")
        progress_bar.pack(pady=10)
        progress_bar.start()

        # Función para ejecutar los comandos en un hilo separado
        def instalar():
            try:
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "firefox"], check=True)
                messagebox.showinfo("Éxito", "Mozilla Firefox se ha instalado correctamente.")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Error al instalar Mozilla Firefox: {e}")
            finally:
                progress_bar.stop()
                progress_window.destroy()

        # Ejecutar la función en un hilo separado
        threading.Thread(target=instalar).start()

    @staticmethod
    def instalar_edge():
        progress_window = tk.Toplevel()
        progress_window.title("Instalando Microsoft Edge")
        progress_bar = ttk.Progressbar(progress_window, length=300, mode="indeterminate")
        progress_bar.pack(pady=10)
        progress_bar.start()

        # Función para ejecutar los comandos en un hilo separado
        def instalar():
            try:
                # Descargar la clave GPG de Microsoft
                key_url = "https://packages.microsoft.com/keys/microsoft.asc"
                key_file = "/tmp/microsoft.asc"
                subprocess.run(["wget", "-qO", key_file, key_url], check=True)
                # Agregar la clave GPG al directorio trusted.gpg.d
                subprocess.run(["sudo", "mkdir", "-p", "/etc/apt/trusted.gpg.d"], check=True)
                subprocess.run(["sudo", "apt-key", "add", key_file], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Añadir el repositorio de Microsoft Edge
                subprocess.run([
                    "sudo",
                    "sh",
                    "-c",
                    'echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list',
                    ],
                    check=True,
                )
                # Actualizar el índice de paquetes
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "microsoft-edge-stable"], check=True)
                messagebox.showinfo("Éxito", "Microsoft Edge se ha instalado correctamente.")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Error al instalar Microsoft Edge: {e}")
            finally:
                progress_bar.stop()
                progress_window.destroy()

        threading.Thread(target=instalar).start()


def abrir_navegador(comando, nombre):
    try:
        subprocess.Popen(comando if isinstance(comando, list) else [comando])
    except FileNotFoundError:
        messagebox.showerror("Navegadores", f"{nombre} no está instalado.")
    except Exception as error:
        messagebox.showerror("Navegadores", f"No se pudo abrir {nombre}: {error}")


def _limpiar_directorio(ruta, nombre):
    expandida = os.path.expanduser(ruta)
    if not os.path.isdir(expandida):
        messagebox.showinfo("Navegadores", f"No hay caché de {nombre} o no está instalado.")
        return
    shutil.rmtree(expandida, ignore_errors=True)
    messagebox.showinfo("Navegadores", f"Caché de {nombre} eliminada.")


class InstalarNavegadoresExtra:
    @staticmethod
    def instalar_chromium(parent=None):
        sudo_shell(
            "apt-get update && (apt-get install -y chromium-browser || apt-get install -y chromium)",
            "instalar Chromium",
            parent,
            on_done=lambda ok: messagebox.showinfo(
                "Navegadores",
                "Chromium instalado." if ok else "No se pudo instalar Chromium.",
                parent=parent,
            ),
        )

    @staticmethod
    def instalar_brave(parent=None):
        comando = (
            "curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg "
            "https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg && "
            'echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] '
            'https://brave-browser-apt-release.s3.brave.com/ stable main" '
            "> /etc/apt/sources.list.d/brave-browser-release.list && "
            "apt-get update && apt-get install -y brave-browser"
        )
        sudo_shell(
            comando,
            "instalar Brave",
            parent,
            on_done=lambda ok: messagebox.showinfo(
                "Navegadores",
                "Brave instalado." if ok else "No se pudo instalar Brave.",
                parent=parent,
            ),
        )

    @staticmethod
    def instalar_vivaldi(parent=None):
        sudo_shell(
            "wget -O /tmp/vivaldi-stable.deb https://downloads.vivaldi.com/stable/vivaldi-stable_amd64.deb "
            "&& dpkg -i /tmp/vivaldi-stable.deb || apt-get -f install -y; rm -f /tmp/vivaldi-stable.deb",
            "instalar Vivaldi",
            parent,
            on_done=lambda ok: messagebox.showinfo(
                "Navegadores",
                "Vivaldi instalado." if ok else "No se pudo instalar Vivaldi.",
                parent=parent,
            ),
        )


PERFILES_CHROMIUM = (
    ("Chrome", os.path.expanduser("~/.config/google-chrome")),
    ("Chromium", os.path.expanduser("~/.config/chromium")),
    ("Brave", os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")),
    ("Vivaldi", os.path.expanduser("~/.config/vivaldi")),
    ("Edge", os.path.expanduser("~/.config/microsoft-edge")),
)


def _perfiles_chromium(base):
    encontrados = []
    if not os.path.isdir(base):
        return encontrados
    for nombre in sorted(os.listdir(base)):
        ruta = os.path.join(base, nombre)
        if os.path.isdir(ruta) and os.path.isfile(os.path.join(ruta, "Bookmarks")):
            encontrados.append((nombre, ruta, os.path.join(ruta, "Bookmarks")))
    return encontrados


def _perfiles_firefox():
    ini = os.path.expanduser("~/.mozilla/firefox/profiles.ini")
    if not os.path.isfile(ini):
        return []
    perfiles = []
    actual = {}
    with open(ini, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if linea.startswith("[") and linea.endswith("]"):
                if actual.get("path"):
                    perfiles.append(actual)
                actual = {"nombre": linea.strip("[]")}
            elif "=" in linea:
                clave, valor = linea.split("=", 1)
                actual[clave.lower()] = valor
        if actual.get("path"):
            perfiles.append(actual)
    resultado = []
    raiz = os.path.expanduser("~/.mozilla/firefox")
    for perfil in perfiles:
        ruta = perfil["path"]
        if not os.path.isabs(ruta):
            ruta = os.path.join(raiz, ruta)
        html = os.path.join(ruta, "bookmarks.html")
        json_backup = os.path.join(ruta, "bookmarkbackups")
        resultado.append((
            perfil.get("name") or perfil.get("nombre") or os.path.basename(ruta),
            ruta,
            html if os.path.isfile(html) else json_backup,
        ))
    return resultado


class PerfilesNavegadores:
    """Lista perfiles y exporta marcadores (archivo Bookmarks / bookmarks.html)."""

    def __init__(self, root):
        self.root = root
        self.root.title("Perfiles y marcadores")
        self.root.geometry("720x420")
        self.filas = []

        tk.Label(self.root, text="Perfiles de navegador", font=("Arial", 14, "bold")).pack(pady=8)
        self.lista = tk.Listbox(self.root, font=("monospace", 10))
        self.lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        marco = tk.Frame(self.root)
        marco.pack(pady=8)
        con_tooltip(
            tk.Button(marco, text="Actualizar", command=self.cargar),
            "Vuelve a detectar perfiles de Brave, Chrome, Chromium, Edge, Firefox y Vivaldi",
        ).pack(side=tk.LEFT, padx=6)
        con_tooltip(
            tk.Button(marco, text="Exportar marcadores", command=self.exportar),
            "Exporta los marcadores del perfil seleccionado a un archivo HTML",
        ).pack(side=tk.LEFT, padx=6)
        self.cargar()

    def cargar(self):
        self.lista.delete(0, tk.END)
        self.filas = []
        for nombre, base in PERFILES_CHROMIUM:
            for perfil, ruta, marcadores in _perfiles_chromium(base):
                self.filas.append({
                    "navegador": nombre,
                    "perfil": perfil,
                    "ruta": ruta,
                    "marcadores": marcadores,
                })
                self.lista.insert(tk.END, f"{nombre:<10}  {perfil:<16}  {ruta}")
        for nombre, ruta, marcadores in _perfiles_firefox():
            self.filas.append({
                "navegador": "Firefox",
                "perfil": nombre,
                "ruta": ruta,
                "marcadores": marcadores,
            })
            self.lista.insert(tk.END, f"{'Firefox':<10}  {nombre:<16}  {ruta}")
        if not self.filas:
            self.lista.insert(tk.END, "No se encontraron perfiles locales.")

    def exportar(self):
        seleccion = self.lista.curselection()
        if not self.filas or not seleccion:
            messagebox.showinfo("Marcadores", "Selecciona un perfil.", parent=self.root)
            return
        fila = self.filas[seleccion[0]]
        origen = fila["marcadores"]
        if os.path.isdir(origen):
            archivos = [
                os.path.join(origen, nombre)
                for nombre in os.listdir(origen)
                if nombre.endswith(".json")
            ]
            archivos.sort(key=os.path.getmtime, reverse=True)
            origen = archivos[0] if archivos else None
        if not origen or not os.path.isfile(origen):
            messagebox.showwarning(
                "Marcadores",
                "Este perfil no tiene un archivo de marcadores exportable.",
                parent=self.root,
            )
            return
        extension = ".json" if origen.endswith(".json") or os.path.basename(origen) == "Bookmarks" else ".html"
        destino = filedialog.asksaveasfilename(
            parent=self.root,
            title="Exportar marcadores",
            defaultextension=extension,
            initialfile=f"marcadores-{fila['navegador']}-{fila['perfil']}{extension}",
            filetypes=(("Marcadores", f"*{extension}"), ("Todos", "*.*")),
        )
        if not destino:
            return
        try:
            shutil.copy2(origen, destino)
        except OSError as error:
            messagebox.showerror("Marcadores", str(error), parent=self.root)
            return
        messagebox.showinfo("Marcadores", f"Marcadores copiados a:\n{destino}", parent=self.root)
