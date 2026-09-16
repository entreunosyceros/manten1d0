"""Confirmación, registro de acciones y ejecución en segundo plano."""

import json
import os
import shlex
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

from password import obtener_contrasena
from tooltip import con_tooltip

RUTA_DATOS_USUARIO = os.path.join(os.path.expanduser("~"), ".local", "share", "Manten1d0")
RUTA_REGISTRO = os.path.join(RUTA_DATOS_USUARIO, "acciones.log")
RUTA_HISTORIAL = os.path.join(RUTA_DATOS_USUARIO, "historial_comandos.json")
MAX_HISTORIAL = 40


def registrar(accion, detalle="", exito=True):
    estado = "OK" if exito else "ERROR"
    marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{marca}] [{estado}] {accion}"
    if detalle:
        linea += f" — {detalle}"
    try:
        os.makedirs(RUTA_DATOS_USUARIO, exist_ok=True)
        with open(RUTA_REGISTRO, "a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")
    except OSError:
        print(linea)


def _carpeta_datos():
    os.makedirs(RUTA_DATOS_USUARIO, exist_ok=True)
    return RUTA_DATOS_USUARIO


def registrar_comando(descripcion, comando, sudo=True, tipo=None):
    """Guarda un comando repetible. No almacena contraseñas."""
    if isinstance(comando, (list, tuple)):
        args = [str(parte) for parte in comando]
        texto = " ".join(args)
        tipo_final = tipo or "args"
    else:
        args = None
        texto = str(comando).strip()
        tipo_final = tipo or ("shell" if sudo else "plain")
    if not texto:
        return
    entrada = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "descripcion": descripcion,
        "comando": texto,
        "args": args,
        "sudo": bool(sudo),
        "tipo": tipo_final,
    }
    historial = leer_historial_comandos()
    historial.append(entrada)
    historial = historial[-MAX_HISTORIAL:]
    try:
        _carpeta_datos()
        with open(RUTA_HISTORIAL, "w", encoding="utf-8") as archivo:
            json.dump(historial, archivo, ensure_ascii=False, indent=2)
    except OSError:
        pass


def leer_historial_comandos():
    if not os.path.exists(RUTA_HISTORIAL):
        return []
    try:
        with open(RUTA_HISTORIAL, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if isinstance(datos, list):
            return datos
    except (OSError, json.JSONDecodeError):
        pass
    return []


def repetir_comando(entrada, parent=None, on_done=None):
    """Vuelve a ejecutar un comando del historial, pidiendo confirmación."""
    descripcion = entrada.get("descripcion") or "comando"
    comando = entrada.get("comando") or ""
    if not confirmar(
        f"¿Repetir esta acción?\n\n{descripcion}\n{comando}",
        parent,
        titulo="Repetir comando",
    ):
        return
    tipo = entrada.get("tipo") or "shell"
    args = entrada.get("args")
    usa_sudo = entrada.get("sudo", True)

    def avisar(ok):
        if parent is not None:
            if ok:
                messagebox.showinfo("Historial", f"Completado: {descripcion}", parent=parent)
            else:
                messagebox.showerror("Historial", f"Falló: {descripcion}", parent=parent)
        if on_done:
            on_done(ok)

    if tipo == "args" or args:
        lista = args or shlex.split(comando)

        def trabajo():
            return sudo_run(lista, descripcion, parent=None, confirmar_accion=False)

        def terminar(resultado):
            avisar(resultado is not None and resultado.returncode == 0)

        en_hilo(parent or tk._default_root, trabajo, al_terminar=terminar)
        return

    if usa_sudo or tipo == "shell":
        sudo_shell(comando, descripcion, parent, confirmar_accion=False, on_done=avisar)
        return

    def trabajo_plano():
        return subprocess.run(shlex.split(comando), capture_output=True, text=True, timeout=180)

    def terminar_plano(resultado):
        avisar(resultado.returncode == 0)

    en_hilo(parent or tk._default_root, trabajo_plano, al_terminar=terminar_plano)


def leer_registro():
    if not os.path.exists(RUTA_REGISTRO):
        return "Aún no hay acciones registradas."
    try:
        with open(RUTA_REGISTRO, "r", encoding="utf-8") as archivo:
            return archivo.read() or "Aún no hay acciones registradas."
    except OSError as error:
        return f"No se pudo leer el registro: {error}"


def confirmar(mensaje, parent=None, titulo="¿Seguro?"):
    return messagebox.askyesno(titulo, mensaje, parent=parent)


def mostrar_registro(parent=None):
    ventana = tk.Toplevel(parent)
    ventana.title("Registro de acciones")
    ventana.geometry("720x420")
    texto = scrolledtext.ScrolledText(ventana, wrap=tk.WORD)
    texto.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    texto.insert(tk.END, leer_registro())
    texto.see(tk.END)
    texto.config(state=tk.DISABLED)
    con_tooltip(
        tk.Button(ventana, text="Cerrar", command=ventana.destroy),
        "Cierra el registro de acciones",
    ).pack(pady=(0, 8))


def mostrar_historial_comandos(parent=None):
    """Lista comandos repetibles (limpiezas, apt, etc.) y permite volver a lanzarlos."""
    ventana = tk.Toplevel(parent)
    ventana.title("Historial de comandos")
    ventana.geometry("760x440")

    tk.Label(
        ventana,
        text="Comandos ejecutados desde la aplicación. Doble clic o Repetir para lanzarlos de nuevo.",
        wraplength=720,
        justify=tk.CENTER,
    ).pack(padx=8, pady=(8, 4))

    lista = tk.Listbox(ventana, font=("monospace", 10))
    lista.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    lista.entradas = []

    def rellenar():
        lista.delete(0, tk.END)
        entradas = list(reversed(leer_historial_comandos()))
        lista.entradas = entradas
        if not entradas:
            lista.insert(tk.END, "Aún no hay comandos. Las limpiezas y acciones sudo aparecerán aquí.")
            return
        for item in entradas:
            lista.insert(
                tk.END,
                f"{item.get('fecha', '')}  ·  {item.get('descripcion', '')}  ·  {item.get('comando', '')}",
            )

    def repetir_seleccion():
        entradas = getattr(lista, "entradas", [])
        seleccion = lista.curselection()
        if not entradas or not seleccion:
            messagebox.showinfo("Historial", "Selecciona un comando de la lista.", parent=ventana)
            return
        repetir_comando(entradas[seleccion[0]], parent=ventana, on_done=lambda _ok: rellenar())

    lista.bind("<Double-Button-1>", lambda _e: repetir_seleccion())
    marco = tk.Frame(ventana)
    marco.pack(pady=8)
    con_tooltip(
        tk.Button(marco, text="Repetir seleccionado", command=repetir_seleccion),
        "Vuelve a ejecutar el comando de limpieza o mantenimiento seleccionado",
    ).pack(side=tk.LEFT, padx=6)
    con_tooltip(
        tk.Button(marco, text="Actualizar lista", command=rellenar),
        "Vuelve a leer el historial de comandos",
    ).pack(side=tk.LEFT, padx=6)
    con_tooltip(
        tk.Button(marco, text="Cerrar", command=ventana.destroy),
        "Cierra el historial de comandos",
    ).pack(side=tk.LEFT, padx=6)
    rellenar()


def _widget_vivo(widget):
    try:
        return bool(widget) and widget.winfo_exists()
    except tk.TclError:
        return False


def en_hilo(widget, funcion, al_terminar=None, al_error=None):
    """Ejecuta funcion() en un hilo y devuelve el resultado al hilo de la UI."""

    def _en_ui(callback, valor):
        if not _widget_vivo(widget):
            return
        try:
            callback(valor)
        except tk.TclError:
            return

    def trabajador():
        try:
            resultado = funcion()
        except Exception as error:
            if al_error:
                if _widget_vivo(widget):
                    widget.after(0, lambda e=error: _en_ui(al_error, e))
            elif _widget_vivo(widget):
                widget.after(
                    0,
                    lambda e=error: _en_ui(
                        lambda err: messagebox.showerror("Error", str(err), parent=widget),
                        e,
                    ),
                )
            return
        if al_terminar and _widget_vivo(widget):
            widget.after(0, lambda r=resultado: _en_ui(al_terminar, r))

    threading.Thread(target=trabajador, daemon=True).start()


def ventana_progreso(parent, titulo, mensaje="Trabajando..."):
    ventana = tk.Toplevel(parent)
    ventana.title(titulo)
    ventana.geometry("420x110")
    ventana.transient(parent)
    etiqueta = tk.Label(ventana, text=mensaje, padx=10, pady=8)
    etiqueta.pack()
    barra = ttk.Progressbar(ventana, mode="indeterminate", length=320)
    barra.pack(pady=8)
    barra.start()
    return ventana, etiqueta


def sudo_run(args, descripcion, parent=None, confirmar_accion=False, timeout=300):
    """
    Ejecuta un comando con sudo en el hilo actual (llamarlo desde en_hilo).
    No escribe la contraseña en el registro. La confirmación debe hacerse antes, en la UI.
    """
    if confirmar_accion and parent is not None:
        comando = " ".join(args)
        if not confirmar(f"{descripcion}\n\nComando: {comando}\n\n¿Quieres continuar?", parent):
            registrar(descripcion, "cancelado por el usuario", False)
            return None
    contrasena = obtener_contrasena()
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        resultado = subprocess.run(
            ["sudo", "-S", "-p", "", *args],
            input=f"{contrasena}\n",
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except Exception as error:
        registrar(descripcion, str(error), False)
        raise
    detalle = " ".join(args)
    registrar(descripcion, detalle, resultado.returncode == 0)
    if resultado.returncode == 0:
        registrar_comando(descripcion, args, sudo=True, tipo="args")
    return resultado


def sudo_shell(comando, descripcion, parent, confirmar_accion=True, on_done=None):
    """Lanza un comando shell con sudo en segundo plano y actualiza una ventana de progreso."""
    if confirmar_accion and not confirmar(
        f"¿Seguro que quieres {descripcion}?\n\n{comando}",
        parent,
    ):
        registrar(descripcion, "cancelado por el usuario", False)
        return

    contrasena = obtener_contrasena()
    progreso, etiqueta = ventana_progreso(parent, descripcion, f"Ejecutando {descripcion}...")

    def actualizar(texto):
        if _widget_vivo(etiqueta) and texto:
            etiqueta.config(text=texto[:90])

    def finalizar(codigo):
        if _widget_vivo(progreso):
            progreso.destroy()
        ok = codigo == 0
        registrar(descripcion, comando, ok)
        if ok:
            registrar_comando(descripcion, comando, sudo=True, tipo="shell")
        if on_done:
            on_done(ok)

    def trabajador():
        try:
            proceso = subprocess.Popen(
                ["sudo", "-S", "-p", "", "bash", "-c", comando],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            proceso.stdin.write(contrasena + "\n")
            proceso.stdin.close()
            for linea in proceso.stdout:
                if _widget_vivo(parent):
                    parent.after(0, lambda t=linea.strip(): actualizar(t))
            codigo = proceso.wait()
        except Exception as error:
            registrar(descripcion, str(error), False)
            if _widget_vivo(parent):
                parent.after(0, lambda: finalizar(1))
                parent.after(0, lambda e=error: messagebox.showerror("Error", str(e), parent=parent))
            return
        if _widget_vivo(parent):
            parent.after(0, lambda c=codigo: finalizar(c))

    threading.Thread(target=trabajador, daemon=True).start()
