"""Confirmación, registro de acciones y ejecución en segundo plano."""

import json
import os
import queue
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


def vaciar_registro():
    """Borra el archivo de acciones. No toca el historial de comandos repetibles."""
    try:
        os.makedirs(RUTA_DATOS_USUARIO, exist_ok=True)
        with open(RUTA_REGISTRO, "w", encoding="utf-8") as archivo:
            archivo.write("")
        return True
    except OSError:
        return False


def confirmar(mensaje, parent=None, titulo="¿Seguro?"):
    try:
        import dialogo_estilo as estilo

        return estilo.dialogo_confirmar(mensaje, parent=parent, titulo=titulo)
    except Exception:
        return messagebox.askyesno(titulo, mensaje, parent=parent)


def mostrar_registro(parent=None):
    ventana = tk.Toplevel(parent)
    ventana.title("Registro De Acciones")
    ventana.geometry("720x420")
    texto = scrolledtext.ScrolledText(ventana, wrap=tk.WORD)
    texto.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def refrescar():
        texto.config(state=tk.NORMAL)
        texto.delete("1.0", tk.END)
        texto.insert(tk.END, leer_registro())
        texto.see(tk.END)
        texto.config(state=tk.DISABLED)

    def vaciar():
        if not confirmar(
            "Se va a borrar todo el registro de acciones.\n\n"
            "No afecta al historial de comandos que se pueden repetir.\n\n"
            "¿Quieres vaciarlo?",
            ventana,
            "Vaciar El Registro",
        ):
            return
        if not vaciar_registro():
            messagebox.showerror("Registro De Acciones", "No se pudo vaciar el registro.", parent=ventana)
            return
        refrescar()
        messagebox.showinfo("Registro De Acciones", "El registro se ha vaciado.", parent=ventana)

    refrescar()
    marco = tk.Frame(ventana)
    marco.pack(pady=(0, 8))
    con_tooltip(
        tk.Button(marco, text="Vaciar registro", command=vaciar),
        "Borra todas las entradas del registro de acciones",
    ).pack(side=tk.LEFT, padx=6)
    con_tooltip(
        tk.Button(marco, text="Cerrar", command=ventana.destroy),
        "Cierra el registro de acciones",
    ).pack(side=tk.LEFT, padx=6)


def mostrar_historial_comandos(parent=None):
    """Lista comandos repetibles (limpiezas, apt, etc.) y permite volver a lanzarlos."""
    ventana = tk.Toplevel(parent)
    ventana.title("Historial De Comandos")
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


_cola_ui = queue.Queue()
_pumps_ui = set()
_raiz_bombeo = None
_after_bombeo = None


def detener_bombeo_ui():
    """Cancela el bombeo periódico (llamar antes de destruir una raíz Tk)."""
    global _raiz_bombeo, _after_bombeo
    raiz = _raiz_bombeo
    after_id = _after_bombeo
    _raiz_bombeo = None
    _after_bombeo = None
    _pumps_ui.clear()
    if raiz is None or after_id is None:
        return
    try:
        raiz.after_cancel(after_id)
    except tk.TclError:
        pass


def vincular_bombeo_ui(raiz):
    """Arranca el bombeo periódico de la cola UI (una ventana Tk activa)."""
    global _raiz_bombeo, _after_bombeo
    if raiz is None:
        return
    if raiz is _raiz_bombeo and id(raiz) in _pumps_ui:
        return
    detener_bombeo_ui()
    _raiz_bombeo = raiz
    _after_bombeo = None
    _pumps_ui.add(id(raiz))
    _bombeo_ui(raiz)


def programar_ui(widget, func, *args, **kwargs):
    """Ejecuta func en el hilo de Tk (seguro llamarlo desde otros hilos)."""

    def tarea():
        if widget is not None and not _widget_vivo(widget):
            return
        try:
            func(*args, **kwargs)
        except tk.TclError:
            pass

    _cola_ui.put(tarea)

    # Desde un hilo secundario no se puede tocar Tk (ni winfo ni after).
    if threading.current_thread() is not threading.main_thread():
        return

    try:
        raiz = widget.winfo_toplevel() if widget is not None else _raiz_bombeo
    except tk.TclError:
        raiz = _raiz_bombeo
    if raiz is None:
        raiz = getattr(tk, "_default_root", None)
    if raiz is None:
        return
    if raiz is _raiz_bombeo and id(raiz) in _pumps_ui:
        return
    vincular_bombeo_ui(raiz)


def obtener_contrasena_segura(parent=None):
    """Pide la contraseña siempre en el hilo de Tk (válido desde en_hilo)."""
    if threading.current_thread() is threading.main_thread():
        return obtener_contrasena()
    listo = threading.Event()
    holder = []

    def pedir():
        try:
            holder.append(obtener_contrasena())
        finally:
            listo.set()

    ancla = parent if parent is not None else _raiz_bombeo
    programar_ui(ancla, pedir)
    listo.wait()
    return holder[0] if holder else None


def _bombeo_ui(raiz):
    global _after_bombeo
    # Si ya hay otra raíz activa (o se detuvo el bombeo), no reprogramar.
    if raiz is not _raiz_bombeo:
        _pumps_ui.discard(id(raiz))
        return
    try:
        if not raiz.winfo_exists():
            if raiz is _raiz_bombeo:
                detener_bombeo_ui()
            else:
                _pumps_ui.discard(id(raiz))
            return
    except tk.TclError:
        if raiz is _raiz_bombeo:
            detener_bombeo_ui()
        else:
            _pumps_ui.discard(id(raiz))
        return

    for _ in range(80):
        try:
            tarea = _cola_ui.get_nowait()
        except queue.Empty:
            break
        try:
            tarea()
        except Exception:
            pass

    if raiz is not _raiz_bombeo:
        return
    try:
        _after_bombeo = raiz.after(50, lambda r=raiz: _bombeo_ui(r))
    except tk.TclError:
        if raiz is _raiz_bombeo:
            detener_bombeo_ui()
        else:
            _pumps_ui.discard(id(raiz))


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
                programar_ui(widget, lambda e=error: _en_ui(al_error, e))
            else:
                programar_ui(
                    widget,
                    lambda e=error: _en_ui(
                        lambda err: messagebox.showerror("Error", str(err), parent=widget),
                        e,
                    ),
                )
            return
        if al_terminar:
            programar_ui(widget, lambda r=resultado: _en_ui(al_terminar, r))

    threading.Thread(target=trabajador, daemon=True).start()


def ventana_progreso(parent, titulo, mensaje="Trabajando..."):
    import dialogo_estilo as estilo

    ventana = tk.Toplevel(parent)
    cuerpo = estilo.preparar_dialogo(
        ventana,
        titulo,
        (titulo or "Progreso").upper()[:48],
        420,
        160,
        topmost=True,
    )
    try:
        ventana.transient(parent)
    except tk.TclError:
        pass
    etiqueta = estilo.etiqueta_texto(cuerpo, mensaje, wraplength=360)
    etiqueta.pack(anchor="w", pady=(0, 8))
    barra = ttk.Progressbar(cuerpo, mode="indeterminate", length=360)
    barra.pack(fill=tk.X, pady=4)
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
    contrasena = obtener_contrasena_segura(parent)
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
                    programar_ui(parent, actualizar, linea.strip())
            codigo = proceso.wait()
        except Exception as error:
            registrar(descripcion, str(error), False)
            if _widget_vivo(parent):
                programar_ui(parent, lambda: finalizar(1))
                programar_ui(
                    parent,
                    lambda e=error: messagebox.showerror("Error", str(e), parent=parent),
                )
            return
        if _widget_vivo(parent):
            programar_ui(parent, finalizar, codigo)

    threading.Thread(target=trabajador, daemon=True).start()
