"""Icono y menú contextual en la bandeja del sistema.

Qt se ejecuta en un proceso aparte: mezclar QApplication con Tkinter
en el mismo proceso provoca SIGSEGV.
"""

import os
import subprocess
import sys
import threading

RUTA_ICONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manten1do.png")
RUTA_ESTE = os.path.abspath(__file__)

CATEGORIAS = (
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
)


def _emitir(comando):
    sys.stdout.write(comando + "\n")
    sys.stdout.flush()


def _crear_icono_qt():
    import io
    from PyQt5.QtGui import QIcon, QPixmap
    from PyQt5.QtCore import Qt

    try:
        from PIL import Image
    except ImportError:
        pixmap = QPixmap(RUTA_ICONO)
        if pixmap.isNull():
            return None
        return QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    try:
        imagen = Image.open(RUTA_ICONO).convert("RGBA")
    except OSError:
        return None
    lado = max(imagen.size)
    fondo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    fondo.paste(imagen, ((lado - imagen.width) // 2, (lado - imagen.height) // 2), imagen)
    fondo = fondo.resize((64, 64), Image.LANCZOS)
    buffer = io.BytesIO()
    fondo.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    return QIcon(pixmap)


def _ejecutar_hijo():
    from PyQt5.QtWidgets import (
        QApplication,
        QMenu,
        QSystemTrayIcon,
        QWidget,
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return 1

    icono = _crear_icono_qt()
    if icono is None or icono.isNull():
        return 1

    titular = QWidget()
    bandeja = QSystemTrayIcon(icono, titular)
    bandeja.setToolTip("Manten1d0")

    menu = QMenu(titular)

    def accion(menu_padre, texto, comando):
        item = menu_padre.addAction(texto)
        item.triggered.connect(lambda _c=False, cmd=comando: _emitir(cmd))
        return item

    accion(menu, "Mostrar ventana", "mostrar")
    accion(menu, "Ocultar a la bandeja", "ocultar")
    menu.addSeparator()
    ir_a = menu.addMenu("Ir a")
    for categoria in CATEGORIAS:
        accion(ir_a, categoria, "ir_a:" + categoria)
    menu.addSeparator()
    accion(menu, "Abrir terminal", "terminal")
    accion(menu, "Opciones", "opciones")
    accion(menu, "Registro de acciones", "registro")
    accion(menu, "Buscar actualizaciones", "actualizaciones")
    menu.addSeparator()
    accion(menu, "Documentación", "documentacion")
    accion(menu, "Acerca de", "about")
    menu.addSeparator()
    accion(menu, "Salir", "salir")

    def al_activar(razon):
        if razon in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            _emitir("alternar")

    bandeja.setContextMenu(menu)
    bandeja.activated.connect(al_activar)
    bandeja.show()
    bandeja.showMessage(
        "Manten1d0",
        "El programa está en la bandeja del sistema. Clic derecho para más opciones.",
        QSystemTrayIcon.Information,
        2500,
    )
    return app.exec_()


class BandejaSistema:
    """Lanza el icono de bandeja en un proceso Qt independiente."""

    def __init__(self, ventana_principal, acciones):
        self.ventana = ventana_principal
        self.root = ventana_principal.root
        self.acciones = acciones
        self.disponible = False
        self._proceso = None
        self._aviso_ocultar = False
        self._icono_ventana = None

    def iniciar(self):
        self._poner_icono_ventana()
        try:
            self._proceso = subprocess.Popen(
                [sys.executable, "-u", RUTA_ESTE, "--hijo"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                cwd=os.path.dirname(RUTA_ESTE),
            )
        except OSError:
            return False
        hilo = threading.Thread(target=self._leer_comandos, daemon=True)
        hilo.start()
        self.disponible = True
        try:
            self.root.after(1000, self._comprobar_hijo)
        except Exception:
            pass
        return True

    def _comprobar_hijo(self):
        if self._proceso is not None and self._proceso.poll() is not None:
            self.disponible = False

    def _poner_icono_ventana(self):
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return
        try:
            imagen = Image.open(RUTA_ICONO)
            imagen.thumbnail((64, 64), Image.LANCZOS)
            self._icono_ventana = ImageTk.PhotoImage(imagen)
            self.root.iconphoto(True, self._icono_ventana)
        except Exception:
            return

    def _leer_comandos(self):
        proceso = self._proceso
        if proceso is None or proceso.stdout is None:
            return
        for linea in proceso.stdout:
            comando = linea.strip()
            if comando:
                self._en_tk(lambda c=comando: self._aplicar(c))

    def _en_tk(self, comando):
        try:
            self.root.after(0, comando)
        except Exception:
            pass

    def _aplicar(self, comando):
        if comando == "mostrar":
            self.mostrar()
        elif comando == "ocultar":
            self.ocultar()
        elif comando == "alternar":
            self.alternar()
        elif comando.startswith("ir_a:"):
            self._ir_a(comando[5:])
        else:
            accion = self.acciones.get(comando)
            if accion:
                accion()

    def mostrar(self):
        try:
            if not self.root.winfo_exists():
                return
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            return

    def ocultar(self):
        try:
            if not self.root.winfo_exists():
                return
            self.root.withdraw()
        except Exception:
            return
        self._aviso_ocultar = True

    def alternar(self):
        try:
            oculta = not self.root.winfo_viewable() or self.root.state() == "withdrawn"
        except Exception:
            return
        if oculta:
            self.mostrar()
        else:
            self.ocultar()

    def _ir_a(self, categoria):
        self.mostrar()
        ir_a = self.acciones.get("ir_a")
        if ir_a:
            ir_a(categoria)

    def detener(self):
        proceso = self._proceso
        self._proceso = None
        self.disponible = False
        if proceso is None:
            return
        try:
            proceso.terminate()
            proceso.wait(timeout=2)
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass


if __name__ == "__main__":
    if "--hijo" in sys.argv:
        sys.exit(_ejecutar_hijo() or 0)
    sys.exit("Este módulo lanza el icono de bandeja; no se ejecuta solo.")
