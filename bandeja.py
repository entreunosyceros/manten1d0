"""Icono y menú contextual en la bandeja del sistema.

Qt se ejecuta en un proceso aparte: mezclar QApplication con Tkinter
en el mismo proceso provoca SIGSEGV.
"""

import os
import subprocess
import sys
import threading

RUTA_ICONO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manten1do.png")
RUTA_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
RUTA_ESTE = os.path.abspath(__file__)
CLASE_VENTANA = "Manten1d0"

# Referencias vivas a PhotoImage (Tk las pierde si no se guardan).
_ICONOS_FOTO = []
_ICONO_PARCHE_TOPLEVEL = False


def _imagen_cuadrada_desde_archivo(ruta, lado=128):
    """Carga un PNG y lo centra en un lienzo cuadrado transparente."""
    from PIL import Image

    imagen = Image.open(ruta).convert("RGBA")
    ancho, alto = imagen.size
    lienzo = max(ancho, alto)
    salida = Image.new("RGBA", (lienzo, lienzo), (0, 0, 0, 0))
    salida.paste(imagen, ((lienzo - ancho) // 2, (lienzo - alto) // 2), imagen)
    if lado and lienzo != lado:
        salida = salida.resize((lado, lado), Image.LANCZOS)
    return salida


def _imagen_icono_ventana():
    """
    Preferir el logo del programa; si no existe, engranaje + llave dibujado.
    """
    for ruta in (RUTA_ICONO, RUTA_LOGO):
        if os.path.isfile(ruta):
            try:
                return _imagen_cuadrada_desde_archivo(ruta, 128)
            except OSError:
                continue
    return _imagen_icono_procedural()


def _imagen_icono_procedural():
    """Engranaje + llave de respaldo si faltan los PNG del proyecto."""
    import math
    from PIL import Image, ImageDraw

    lado = 128
    imagen = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    draw = ImageDraw.Draw(imagen)

    # Fondo redondeado azul
    margen = 6
    draw.rounded_rectangle(
        (margen, margen, lado - margen, lado - margen),
        radius=28,
        fill=(30, 80, 140, 255),
    )

    cx = cy = lado // 2
    # Anillo tipo engranaje (sin espiral)
    r_ext, r_int = 46, 30
    draw.ellipse(
        (cx - r_ext, cy - r_ext, cx + r_ext, cy + r_ext),
        outline=(220, 235, 255, 255),
        width=7,
    )
    # Dientes simples del engranaje
    for angulo in range(0, 360, 45):
        rad = math.radians(angulo)
        x1 = cx + int((r_ext - 2) * math.cos(rad))
        y1 = cy + int((r_ext - 2) * math.sin(rad))
        x2 = cx + int((r_ext + 10) * math.cos(rad))
        y2 = cy + int((r_ext + 10) * math.sin(rad))
        draw.line((x1, y1, x2, y2), fill=(220, 235, 255, 255), width=8)

    draw.ellipse(
        (cx - r_int, cy - r_int, cx + r_int, cy + r_int),
        fill=(30, 80, 140, 255),
    )

    # Llave inglesa simplificada (blanco)
    draw.rectangle((cx - 5, cy - 28, cx + 5, cy + 22), fill=(255, 255, 255, 255))
    draw.ellipse((cx - 14, cy - 36, cx + 14, cy - 8), outline=(255, 255, 255, 255), width=5)
    draw.ellipse((cx - 7, cy - 29, cx + 7, cy - 15), fill=(30, 80, 140, 255))
    draw.polygon(
        [(cx - 12, cy + 18), (cx + 12, cy + 18), (cx + 8, cy + 32), (cx - 8, cy + 32)],
        fill=(255, 255, 255, 255),
    )
    return imagen


def preparar_ventana_app(ventana, tamano=128, estilo_dialogo=None):
    """Clase WM, icono y (en Toplevel) chrome con franja al estilo Manten1d0."""
    try:
        ventana.tk.call("wm", "class", ".", CLASE_VENTANA, CLASE_VENTANA)
    except Exception:
        try:
            ventana.wm_class(CLASE_VENTANA)
        except Exception:
            pass
    try:
        from PIL import Image, ImageTk
    except ImportError:
        emblema = None
    else:
        emblema = None
        try:
            emblema = _imagen_icono_ventana()
            fotos = []
            for lado in (16, 32, 48, 64, max(64, int(tamano))):
                copia = emblema.copy()
                copia.thumbnail((lado, lado), Image.LANCZOS)
                foto = ImageTk.PhotoImage(copia, master=ventana)
                fotos.append(foto)
            ventana.iconphoto(True, *fotos)
            ventana._icono_manten1d0 = fotos
            _ICONOS_FOTO.extend(fotos)
        except Exception:
            pass

    if estilo_dialogo is None:
        # Tras el parche, tk.Toplevel es una funcion: detectar por nombre de clase
        estilo_dialogo = type(ventana).__name__ == "Toplevel"
    if estilo_dialogo:
        try:
            import dialogo_estilo as estilo

            estilo.aplicar_chrome_toplevel(ventana)
        except Exception:
            pass
    else:
        try:
            import preferencias

            preferencias.aplicar_defaults_tema(ventana)
        except Exception:
            pass


def instalar_icono_en_toplevels():
    """Icono + estilo de franja en todo Toplevel nuevo; dialogos messagebox unificados."""
    global _ICONO_PARCHE_TOPLEVEL
    if _ICONO_PARCHE_TOPLEVEL:
        return
    import tkinter as tk

    original = tk.Toplevel
    estilo_mod = None
    try:
        import dialogo_estilo as estilo_mod

        estilo_mod.instalar_messagebox_estilo()
    except Exception:
        estilo_mod = None

    def toplevel_con_icono(*args, **kwargs):
        # chrome=False: ventanas sin franja (tooltips, popups ligeros)
        con_chrome = kwargs.pop("chrome", True)
        ventana = original(*args, **kwargs)
        if not con_chrome:
            return ventana
        try:
            preparar_ventana_app(ventana, tamano=64, estilo_dialogo=True)
        except Exception:
            pass
        # Devolver el panel de contenido (expandible) para que pack/grid
        # de las apps rellene la ventana bajo la franja.
        if estilo_mod is not None:
            try:
                contenedor = getattr(ventana, "_contenedor_estilo", None)
                if contenedor is not None:
                    return estilo_mod.enganchar_cuerpo_toplevel(contenedor, ventana)
            except Exception:
                pass
        return ventana

    tk.Toplevel = toplevel_con_icono
    _ICONO_PARCHE_TOPLEVEL = True


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


def _ruta_icono_cache_bandeja():
    """PNG cuadrado en cache/tema local: AppIndicator/GNOME lo cargan mejor desde archivo."""
    rutas_destino = []
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "Manten1d0")
    tema_dir = os.path.join(
        os.path.expanduser("~"), ".local", "share", "icons", "hicolor", "48x48", "apps"
    )
    for carpeta in (cache_dir, tema_dir):
        try:
            os.makedirs(carpeta, exist_ok=True)
            rutas_destino.append(carpeta)
        except OSError:
            continue
    if not rutas_destino:
        rutas_destino.append(os.path.dirname(RUTA_ESTE))

    try:
        from PIL import Image

        emblema = _imagen_icono_ventana()
    except (OSError, ImportError):
        emblema = None

    cache_png = os.path.join(rutas_destino[0], "bandeja-icono.png")
    tema_png = os.path.join(
        os.path.expanduser("~"),
        ".local",
        "share",
        "icons",
        "hicolor",
        "48x48",
        "apps",
        "manten1d0.png",
    )
    if emblema is not None:
        try:
            emblema.save(cache_png, format="PNG")
        except OSError:
            cache_png = RUTA_ICONO if os.path.isfile(RUTA_ICONO) else None
        try:
            emblema.resize((48, 48), Image.LANCZOS).save(tema_png, format="PNG")
        except OSError:
            pass
        return cache_png or (RUTA_ICONO if os.path.isfile(RUTA_ICONO) else RUTA_LOGO)

    if os.path.isfile(RUTA_ICONO):
        return RUTA_ICONO
    if os.path.isfile(RUTA_LOGO):
        return RUTA_LOGO
    return None


def _crear_icono_qt():
    import io
    from PyQt5.QtGui import QIcon, QPixmap
    from PyQt5.QtCore import Qt

    try:
        from PIL import Image
    except ImportError:
        Image = None

    ruta_cache = _ruta_icono_cache_bandeja()
    icono = QIcon.fromTheme("manten1d0")

    # Preferir archivo en disco (StatusNotifier / AppIndicator)
    if ruta_cache and os.path.isfile(ruta_cache):
        if icono.isNull():
            icono = QIcon()
        icono.addFile(ruta_cache)
        pixmap = QPixmap(ruta_cache)
        if not pixmap.isNull():
            for lado in (16, 22, 24, 32, 48, 64):
                icono.addPixmap(
                    pixmap.scaled(lado, lado, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

    if (icono.isNull() or not icono.availableSizes()) and Image is not None:
        try:
            emblema = _imagen_icono_ventana()
            if icono.isNull():
                icono = QIcon()
            for lado in (16, 22, 24, 32, 48, 64, 128):
                copia = emblema.copy()
                copia.thumbnail((lado, lado), Image.LANCZOS)
                buffer = io.BytesIO()
                copia.save(buffer, format="PNG")
                pix = QPixmap()
                pix.loadFromData(buffer.getvalue())
                if not pix.isNull():
                    icono.addPixmap(pix)
        except OSError:
            pass

    if icono.isNull():
        for ruta in (RUTA_ICONO, RUTA_LOGO):
            if os.path.isfile(ruta):
                pixmap = QPixmap(ruta)
                if not pixmap.isNull():
                    return QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return None
    return icono


def _ejecutar_hijo():
    from PyQt5.QtWidgets import (
        QApplication,
        QMenu,
        QSystemTrayIcon,
        QWidget,
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Manten1d0")
    app.setOrganizationName("Manten1d0")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return 1

    icono = _crear_icono_qt()
    if icono is None or icono.isNull():
        return 1
    app.setWindowIcon(icono)

    titular = QWidget()
    titular.setWindowIcon(icono)
    bandeja = QSystemTrayIcon(icono, titular)
    bandeja.setIcon(icono)
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
        preparar_ventana_app(self.root, tamano=64)

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
            from registro import programar_ui

            programar_ui(self.root, comando)
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
