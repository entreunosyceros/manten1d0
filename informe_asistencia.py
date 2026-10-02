"""Informe de asistencia: diagnóstico + datos del equipo para enviar a quien ayude."""

import platform
import socket
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

import preferencias
from cat_informacion import Informacion
from diagnostico import analizar_equipo
from registro import en_hilo
from tooltip import ToolTip


def _nivel_marca(nivel):
    return {
        "ok": "[OK]",
        "aviso": "[AVISO]",
        "error": "[ERROR]",
        "info": "[INFO]",
    }.get(nivel, "[?]")


def generar_informe_asistencia():
    """Genera el texto del informe (pensado para ejecutarse en hilo de fondo)."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = "desconocido"

    lineas = [
        "INFORME DE ASISTENCIA — Manten1d0",
        f"Fecha: {ahora}",
        f"Equipo: {hostname}",
        "",
        "=== Diagnóstico ===",
        "",
    ]

    items = analizar_equipo()
    errores = sum(1 for i in items if i.get("nivel") == "error")
    avisos = sum(1 for i in items if i.get("nivel") == "aviso")
    if errores or avisos:
        lineas.append(f"Resumen: {errores} problema(s), {avisos} aviso(s).")
    else:
        lineas.append("Resumen: sin problemas detectados.")
    lineas.append("")

    for item in items:
        marca = _nivel_marca(item.get("nivel"))
        lineas.append(f"{marca} {item.get('titulo', '')}")
        detalle = (item.get("detalle") or "").strip()
        if detalle:
            lineas.append(f"    {detalle}")
        lineas.append("")

    lineas.extend(["=== Equipo ===", ""])
    try:
        info = Informacion.obtener_informacion_completa()
    except Exception as error:
        lineas.append(f"(No se pudo leer la información del equipo: {error})")
        info = {}

    orden = (
        "Usuario",
        "Sistema Operativo",
        "Versión de Sistema",
        "Versión de Ubuntu",
        "Tipo de Escritorio",
        "Tiempo de Actividad",
        "Tiempo de Arranque",
        "Zona Horaria",
        "Dirección IP Local",
        "Dirección IP Pública",
        "dns local",
        "dns publico",
        "Interfaces de Red",
        "Información de la Tarjeta Gráfica",
    )
    for clave in orden:
        if clave not in info:
            continue
        valor = info[clave]
        if isinstance(valor, (list, tuple)):
            valor = ", ".join(str(v) for v in valor)
        lineas.append(f"{clave}: {valor}")

    if "Información del Procesador" in info:
        lineas.append("")
        lineas.append("Procesador:")
        proc = info["Información del Procesador"]
        if isinstance(proc, list):
            for fila in proc[:12]:
                if isinstance(fila, (list, tuple)):
                    lineas.append("  " + " | ".join(str(c) for c in fila))
                else:
                    lineas.append(f"  {fila}")
        else:
            lineas.append(f"  {proc}")

    if "Información de la Memoria" in info:
        lineas.append("")
        lineas.append("Memoria:")
        mem = info["Información de la Memoria"]
        if isinstance(mem, dict):
            for k, v in mem.items():
                lineas.append(f"  {k}: {v}")
        else:
            lineas.append(f"  {mem}")

    lineas.extend([
        "",
        "=== Notas ===",
        f"Plataforma Python: {platform.platform()}",
        "Generado automáticamente para compartir con quien te ayude.",
        "No incluye contraseñas ni claves.",
        "",
    ])
    return "\n".join(lineas)


class InformeAsistencia:
    """Ventana para generar, copiar y guardar el informe de asistencia."""

    def __init__(self, root):
        self.root = root
        self.root.title("Informe De Asistencia")
        self.root.minsize(560, 480)
        self._centrar(680, 560)
        self._ocupado = False
        self._texto = ""

        tk.Label(
            self.root,
            text="Informe de asistencia",
            font=("Arial", 14, "bold"),
        ).pack(pady=(12, 4))
        tk.Label(
            self.root,
            text=(
                "Genera un resumen del diagnóstico y del equipo para enviárselo "
                "a quien te ayude (correo, chat, etc.). No incluye contraseñas."
            ),
            wraplength=640,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 8))

        self.lbl_estado = tk.Label(self.root, text="Generando informe…", anchor="w")
        self.lbl_estado.pack(fill=tk.X, padx=14)

        self.texto = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=22)
        self.texto.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        botones = tk.Frame(self.root)
        botones.pack(pady=(0, 12))
        self.btn_generar = tk.Button(botones, text="Generar de nuevo", width=16, command=self.generar)
        self.btn_generar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_generar, "Vuelve a ejecutar el diagnóstico y armar el informe")
        self.btn_copiar = tk.Button(botones, text="Copiar", width=12, command=self.copiar)
        self.btn_copiar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_copiar, "Copia el informe al portapapeles")
        self.btn_guardar = tk.Button(botones, text="Guardar .txt", width=12, command=self.guardar)
        self.btn_guardar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_guardar, "Guarda el informe en un archivo de texto para enviarlo")
        btn_cerrar = tk.Button(botones, text="Cerrar", width=10, command=self.root.destroy)
        btn_cerrar.pack(side=tk.LEFT, padx=6)
        ToolTip(btn_cerrar, "Cierra esta ventana")

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)
        self.generar()

    def _centrar(self, ancho, alto):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - ancho) // 2
        y = (self.root.winfo_screenheight() - alto) // 2
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _set_ocupado(self, ocupado):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for btn in (self.btn_generar, self.btn_copiar, self.btn_guardar):
            try:
                btn.config(state=estado)
            except tk.TclError:
                pass

    def generar(self):
        if self._ocupado:
            return
        self._set_ocupado(True)
        self.lbl_estado.config(text="Generando informe…")
        self.texto.delete("1.0", tk.END)
        self.texto.insert(tk.END, "Analizando el equipo, espera un momento...")

        def trabajador():
            return generar_informe_asistencia()

        def al_terminar(contenido):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._texto = contenido
            self.texto.delete("1.0", tk.END)
            self.texto.insert(tk.END, contenido)
            self.lbl_estado.config(text="Informe listo. Puedes copiarlo o guardarlo.")

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self.lbl_estado.config(text=str(error))
            messagebox.showerror("Informe de asistencia", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def copiar(self):
        contenido = self.texto.get("1.0", "end-1c").strip()
        if not contenido:
            messagebox.showwarning("Informe de asistencia", "No hay informe que copiar.", parent=self.root)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(contenido)
        self.root.update_idletasks()
        messagebox.showinfo("Informe de asistencia", "Informe copiado al portapapeles.", parent=self.root)

    def guardar(self):
        contenido = self.texto.get("1.0", "end-1c").strip()
        if not contenido:
            messagebox.showwarning("Informe de asistencia", "No hay informe que guardar.", parent=self.root)
            return
        nombre = f"Manten1d0-informe-{datetime.now().strftime('%Y-%m-%d')}.txt"
        destino = filedialog.asksaveasfilename(
            parent=self.root,
            title="Guardar informe de asistencia",
            defaultextension=".txt",
            initialfile=nombre,
            filetypes=(("Texto", "*.txt"), ("Todos los archivos", "*.*")),
        )
        if not destino:
            return
        try:
            with open(destino, "w", encoding="utf-8") as archivo:
                archivo.write(contenido.rstrip() + "\n")
        except OSError as error:
            messagebox.showerror(
                "Informe de asistencia",
                f"No se pudo guardar el archivo:\n{error}",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "Informe de asistencia",
            f"Informe guardado en:\n{destino}",
            parent=self.root,
        )
