"""Asistente de problemas de Internet: checklist y soluciones aplicables."""

import os
import re
import socket
import subprocess
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import preferencias
from cat_internet import _ping_internet, medir_nivel_ruido
from cat_red_extra import RedesWifi, SelectorDns, aplicar_dns_preajuste
from cat_redLocal import _gateway_casa, _ping_host
from registro import confirmar, en_hilo, registrar
from reparar import repair_network
from tooltip import ToolTip, con_tooltip

try:
    import requests
except ImportError:
    requests = None

_COLORES = {
    "ok": "#1e8449",
    "aviso": "#e67e22",
    "error": "#c0392b",
    "info": "#2471a3",
}

_MARCAS = {
    "ok": "OK",
    "aviso": "AVISO",
    "error": "ERROR",
    "info": "INFO",
}

# Prioridad de cascada para elegir el resultado principal
_ORDEN_IDS = ("adaptador", "router", "dns", "internet", "latencia", "perdida")


def _comando(args, timeout=15):
    entorno = os.environ.copy()
    entorno["LC_ALL"] = "C"
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=entorno,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def _iface_default():
    """Devuelve (iface, gateway) de la ruta por defecto IPv4, o (None, None)."""
    proceso = _comando(["ip", "-4", "route", "show", "default"], timeout=10)
    texto = proceso.stdout or ""
    gw = None
    iface = None
    m_gw = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", texto)
    if m_gw:
        gw = m_gw.group(1)
    m_dev = re.search(r"\bdev\s+(\S+)", texto)
    if m_dev:
        iface = m_dev.group(1)
    return iface, gw


def _ipv4_de_iface(iface):
    if not iface:
        return None
    proceso = _comando(["ip", "-4", "-o", "addr", "show", "dev", iface], timeout=10)
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", proceso.stdout or "")
    return m.group(1) if m else None


def _check_adaptador():
    iface, _gw = _iface_default()
    if not iface:
        return {
            "id": "adaptador",
            "nivel": "error",
            "titulo": "Adaptador de red",
            "detalle": "No hay ruta por defecto. Revisa el cable o el Wi-Fi.",
        }
    ip = _ipv4_de_iface(iface)
    if not ip:
        return {
            "id": "adaptador",
            "nivel": "error",
            "titulo": "Adaptador de red",
            "detalle": f"La interfaz {iface} no tiene direccion IPv4.",
        }
    return {
        "id": "adaptador",
        "nivel": "ok",
        "titulo": "Adaptador de red",
        "detalle": f"Interfaz {iface} con IP {ip}.",
    }


def _check_router():
    gateway = _gateway_casa()
    if not gateway:
        return {
            "id": "router",
            "nivel": "error",
            "titulo": "Conexion con router",
            "detalle": "No se detecto la puerta de enlace (router).",
        }
    ok, latencia, detalle = _ping_host(gateway, veces=3)
    if ok:
        extra = f" Latencia {latencia:.0f} ms." if latencia is not None else ""
        return {
            "id": "router",
            "nivel": "ok",
            "titulo": "Conexion con router",
            "detalle": f"El router {gateway} responde.{extra}",
        }
    return {
        "id": "router",
        "nivel": "error",
        "titulo": "Conexion con router",
        "detalle": f"El router {gateway} no responde. {detalle}",
    }


def _check_dns():
    host = "www.google.com"
    inicio = time.monotonic()
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        duracion = time.monotonic() - inicio
    except socket.gaierror as error:
        return {
            "id": "dns",
            "nivel": "error",
            "titulo": "DNS",
            "detalle": f"No se pudo resolver {host}: {error}",
        }
    except OSError as error:
        return {
            "id": "dns",
            "nivel": "error",
            "titulo": "DNS",
            "detalle": f"Error al consultar DNS: {error}",
        }
    if not infos:
        return {
            "id": "dns",
            "nivel": "error",
            "titulo": "DNS",
            "detalle": f"Sin direccion para {host}.",
        }
    if duracion > 1.0:
        return {
            "id": "dns",
            "nivel": "aviso",
            "titulo": "DNS",
            "detalle": f"DNS lento: {duracion:.1f} s al resolver {host}.",
        }
    return {
        "id": "dns",
        "nivel": "ok",
        "titulo": "DNS",
        "detalle": f"Resolvio {host} en {duracion:.2f} s.",
    }


def _https_ok():
    if requests is None:
        return False
    try:
        requests.get("https://www.google.com", timeout=4)
        return True
    except Exception:
        return False


def _checks_internet_latencia_perdida():
    destino, perdido, media, jitter, ok_ping = _ping_internet()
    https = _https_ok()

    if ok_ping or https:
        detalle_net = []
        if ok_ping and destino:
            detalle_net.append(f"Ping a {destino} OK.")
        if https:
            detalle_net.append("HTTPS funciona.")
        item_internet = {
            "id": "internet",
            "nivel": "ok",
            "titulo": "Conexion a Internet",
            "detalle": " ".join(detalle_net) or "Hay salida a Internet.",
        }
    else:
        item_internet = {
            "id": "internet",
            "nivel": "error",
            "titulo": "Conexion a Internet",
            "detalle": "No hay respuesta a 1.1.1.1/8.8.8.8 ni HTTPS.",
        }

    if media is None and not ok_ping:
        item_latencia = {
            "id": "latencia",
            "nivel": "info",
            "titulo": "Latencia",
            "detalle": "No se pudo medir la latencia (sin ping).",
        }
    elif media is None:
        item_latencia = {
            "id": "latencia",
            "nivel": "info",
            "titulo": "Latencia",
            "detalle": "Ping OK pero sin RTT en la salida.",
        }
    elif media < 100:
        item_latencia = {
            "id": "latencia",
            "nivel": "ok",
            "titulo": "Latencia",
            "detalle": f"Latencia media {media:.0f} ms"
            + (f" (jitter {jitter:.1f} ms)." if jitter is not None else "."),
        }
    elif media <= 200:
        item_latencia = {
            "id": "latencia",
            "nivel": "aviso",
            "titulo": "Latencia",
            "detalle": f"Latencia alta: {media:.0f} ms.",
        }
    else:
        item_latencia = {
            "id": "latencia",
            "nivel": "error",
            "titulo": "Latencia",
            "detalle": f"Latencia muy alta: {media:.0f} ms.",
        }

    if perdido is None and not ok_ping:
        item_perdida = {
            "id": "perdida",
            "nivel": "info",
            "titulo": "Perdida de paquetes",
            "detalle": "No se pudo medir la perdida de paquetes.",
        }
    elif perdido is None:
        item_perdida = {
            "id": "perdida",
            "nivel": "info",
            "titulo": "Perdida de paquetes",
            "detalle": "Sin dato de perdida en el ping.",
        }
    elif perdido <= 0:
        item_perdida = {
            "id": "perdida",
            "nivel": "ok",
            "titulo": "Perdida de paquetes",
            "detalle": "Sin perdida de paquetes.",
        }
    elif perdido < 25:
        item_perdida = {
            "id": "perdida",
            "nivel": "aviso",
            "titulo": "Perdida de paquetes",
            "detalle": f"Perdida {perdido:.0f} %.",
        }
    else:
        item_perdida = {
            "id": "perdida",
            "nivel": "error",
            "titulo": "Perdida de paquetes",
            "detalle": f"Perdida alta: {perdido:.0f} %.",
        }

    return item_internet, item_latencia, item_perdida


def _elegir_solucion(items):
    """Elige el primer fallo grave (error luego aviso) segun _ORDEN_IDS."""
    por_id = {item["id"]: item for item in items}
    for nivel_buscado in ("error", "aviso"):
        for id_check in _ORDEN_IDS:
            item = por_id.get(id_check)
            if not item or item["nivel"] != nivel_buscado:
                continue
            return _solucion_para(item)
    return {
        "titulo": "Internet parece estable",
        "texto": "No se detectaron problemas en las comprobaciones basicas.",
        "accion": None,
        "etiqueta_boton": None,
    }


def _solucion_para(item):
    id_check = item["id"]
    if id_check == "adaptador":
        return {
            "titulo": "Adaptador sin conexion correcta",
            "texto": (
                "Reiniciar NetworkManager suele recuperar la interfaz "
                "(la red se corta unos segundos)."
            ),
            "accion": "reiniciar_nm",
            "etiqueta_boton": "Aplicar solucion",
        }
    if id_check == "router":
        return {
            "titulo": "El router no responde",
            "texto": (
                "Comprueba el cable o el Wi-Fi. Puedes abrir Redes Wi-Fi "
                "para ver si estas conectado a la red de casa."
            ),
            "accion": "abrir_wifi",
            "etiqueta_boton": "Abrir Wi-Fi",
        }
    if id_check == "dns":
        return {
            "titulo": "DNS lento" if item["nivel"] == "aviso" else "DNS no funciona",
            "texto": "Cambiar DNS a Cloudflare (1.1.1.1) suele mejorar la resolucion de nombres.",
            "accion": "dns_cloudflare",
            "etiqueta_boton": "Aplicar solucion",
        }
    if id_check == "internet":
        return {
            "titulo": "Sin conexion a Internet",
            "texto": (
                "El router responde pero no hay salida a Internet. "
                "Reiniciar NetworkManager puede ayudar; si sigue fallando, "
                "revisa el operador o el router."
            ),
            "accion": "reiniciar_nm",
            "etiqueta_boton": "Aplicar solucion",
        }
    if id_check in ("latencia", "perdida"):
        return {
            "titulo": "Conexion inestable" if id_check == "perdida" else "Latencia alta",
            "texto": (
                "En Wi-Fi suele deberse a interferencias o distancia al router. "
                "Mide el nivel de ruido (SNR y perdida) para ver mas detalle."
            ),
            "accion": "medir_ruido",
            "etiqueta_boton": "Medir ruido",
        }
    return {
        "titulo": item["titulo"],
        "texto": item["detalle"],
        "accion": None,
        "etiqueta_boton": None,
    }


def diagnosticar_internet():
    """Ejecuta la checklist completa. Pensado para llamar desde un hilo."""
    items = []
    items.append(_check_adaptador())
    items.append(_check_router())
    items.append(_check_dns())
    internet, latencia, perdida = _checks_internet_latencia_perdida()
    items.extend([internet, latencia, perdida])
    solucion = _elegir_solucion(items)
    return {"items": items, "solucion": solucion}


class AsistenteInternet:
    """Panel: diagnostico guiado de Internet y solucion recomendada."""

    def __init__(self, root):
        self.root = root
        self.root.title("Problemas Con Internet")
        self.root.minsize(600, 520)
        self._centrar(640, 560)
        self._ocupado = False
        self._items = []
        self._solucion = None

        tk.Label(
            self.root, text="Tengo problemas con Internet", font=("Arial", 14, "bold")
        ).pack(pady=(12, 2))
        tk.Label(
            self.root,
            text=(
                "Comprueba adaptador, router, DNS, Internet, latencia y perdida "
                "de paquetes. Luego propone una solucion."
            ),
            wraplength=600,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 6))

        self.lbl_estado = tk.Label(
            self.root, text="Listo para analizar.", anchor="w", font=("Arial", 10, "bold")
        )
        self.lbl_estado.pack(fill=tk.X, padx=14)
        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(2, 6))

        tk.Label(self.root, text="Comprobaciones", font=("Arial", 11, "bold"), anchor="w").pack(
            fill=tk.X, padx=14
        )
        self.lista = tk.Listbox(self.root, height=8, exportselection=False, font=("Arial", 10))
        self.lista.pack(fill=tk.X, padx=14, pady=(2, 4))
        self.lista.bind("<<ListboxSelect>>", self._al_seleccionar)
        ToolTip(self.lista, "Pulsa un resultado para ver el detalle")

        self.lbl_detalle = tk.Label(
            self.root,
            text="",
            anchor="w",
            justify=tk.LEFT,
            wraplength=600,
        )
        self.lbl_detalle.pack(fill=tk.X, padx=14, pady=(0, 6))

        marco_res = tk.LabelFrame(self.root, text="Resultado", padx=10, pady=8)
        marco_res.pack(fill=tk.X, padx=14, pady=(4, 8))
        self.lbl_resultado = tk.Label(
            marco_res, text="Pulsa Analizar.", font=("Arial", 11, "bold"), anchor="w"
        )
        self.lbl_resultado.pack(fill=tk.X)
        self.lbl_solucion = tk.Label(
            marco_res,
            text="",
            anchor="w",
            justify=tk.LEFT,
            wraplength=580,
        )
        self.lbl_solucion.pack(fill=tk.X, pady=(4, 0))

        pie = tk.Frame(self.root)
        pie.pack(pady=(4, 12))
        self.btn_analizar = con_tooltip(
            tk.Button(pie, text="Analizar", width=12, command=self.cargar),
            "Ejecuta todas las comprobaciones",
        )
        self.btn_analizar.pack(side=tk.LEFT, padx=4)
        self.btn_aplicar = con_tooltip(
            tk.Button(pie, text="Aplicar solucion", width=16, command=self._aplicar),
            "Aplica la solucion recomendada (pide confirmacion)",
        )
        self.btn_aplicar.pack(side=tk.LEFT, padx=4)
        self.btn_aplicar.config(state=tk.DISABLED)
        con_tooltip(
            tk.Button(pie, text="Abrir DNS", width=12, command=self._abrir_dns),
            "Abre el selector de DNS (router, Cloudflare, Google)",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Cerrar", width=10, command=self.root.destroy),
            "Cierra esta ventana",
        ).pack(side=tk.LEFT, padx=4)

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)
        self.cargar()

    def _centrar(self, ancho, alto):
        try:
            from bandeja import preparar_ventana_app

            preparar_ventana_app(self.root, tamano=64)
        except Exception:
            pass
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - ancho) // 2
        y = (self.root.winfo_screenheight() - alto) // 2
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        try:
            self.btn_analizar.config(state=estado)
        except tk.TclError:
            pass
        if ocupado:
            try:
                self.progreso.start(12)
            except tk.TclError:
                pass
            try:
                self.btn_aplicar.config(state=tk.DISABLED)
            except tk.TclError:
                pass
        else:
            try:
                self.progreso.stop()
            except tk.TclError:
                pass
        if mensaje:
            self.lbl_estado.config(text=mensaje, fg=_COLORES["info"])

    def cargar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Analizando Internet...")

        def al_terminar(datos):
            self._set_ocupado(False)
            self._pintar(datos)

        def al_error(error):
            self._set_ocupado(False)
            self.lbl_estado.config(text=f"Error: {error}", fg=_COLORES["error"])

        en_hilo(self.root, diagnosticar_internet, al_terminar=al_terminar, al_error=al_error)

    def _pintar(self, datos):
        self._items = datos.get("items") or []
        self._solucion = datos.get("solucion") or {}

        self.lista.delete(0, tk.END)
        for item in self._items:
            marca = _MARCAS.get(item["nivel"], "INFO")
            self.lista.insert(tk.END, f"[{marca}] {item['titulo']}")

        sol = self._solucion
        self.lbl_resultado.config(text=sol.get("titulo") or "Sin resultado")
        self.lbl_solucion.config(
            text=f"Solucion recomendada:\n{sol.get('texto') or ''}"
        )
        etiqueta = sol.get("etiqueta_boton") or "Aplicar solucion"
        self.btn_aplicar.config(text=etiqueta)
        if sol.get("accion"):
            self.btn_aplicar.config(state=tk.NORMAL)
        else:
            self.btn_aplicar.config(state=tk.DISABLED)

        avisos = sum(1 for i in self._items if i["nivel"] in ("aviso", "error"))
        if avisos:
            self.lbl_estado.config(
                text=f"Analisis listo: {avisos} aviso(s) o problema(s).",
                fg=_COLORES["aviso"],
            )
        else:
            self.lbl_estado.config(
                text="Analisis listo: sin problemas destacados.",
                fg=_COLORES["ok"],
            )
        self.lbl_detalle.config(text="Selecciona una comprobacion para ver el detalle.")

    def _al_seleccionar(self, _event=None):
        sel = self.lista.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._items):
            return
        item = self._items[idx]
        self.lbl_detalle.config(text=f"{item['titulo']}\n{item['detalle']}")

    def _abrir_dns(self):
        SelectorDns(tk.Toplevel(self.root))

    def _mostrar_ruido(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Nivel De Ruido")
        ventana.minsize(520, 360)
        texto = scrolledtext.ScrolledText(ventana, wrap=tk.WORD, height=18)
        texto.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        texto.insert(tk.END, "Midiendo...")
        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(ventana, preferencias.tema_seleccionado)

        def trabajo():
            return medir_nivel_ruido()

        def terminar(resultado):
            texto.delete("1.0", tk.END)
            texto.insert(tk.END, resultado)

        en_hilo(ventana, trabajo, al_terminar=terminar)

    def _aplicar(self):
        if self._ocupado or not self._solucion or not self._solucion.get("accion"):
            return
        accion = self._solucion["accion"]

        if accion == "abrir_wifi":
            RedesWifi(tk.Toplevel(self.root))
            return

        if accion == "medir_ruido":
            self._mostrar_ruido()
            return

        if accion == "dns_cloudflare":
            etiqueta = "Cloudflare (1.1.1.1)"
            mensaje = (
                "Que se va a hacer?\n"
                "Se cambiara el DNS de la conexion activa a Cloudflare (1.1.1.1).\n\n"
                "Por que?\n"
                "El DNS actual es lento o no resuelve bien los nombres.\n\n"
                "Que riesgos tiene?\n"
                "La conexion se reinicia unos segundos. Puedes volver al DNS del router "
                "desde Abrir DNS.\n\n"
                "Continuar?"
            )
            if not confirmar(mensaje, self.root, "Cambiar DNS"):
                return
            self._set_ocupado(True, "Aplicando DNS Cloudflare...")

            def trabajo():
                return aplicar_dns_preajuste(etiqueta, parent=None, confirmar_antes=False)

            def terminar(resultado):
                self._set_ocupado(False)
                ok, msg = resultado
                if ok:
                    registrar("Asistente Internet: DNS Cloudflare", msg, True)
                    messagebox.showinfo("Problemas Con Internet", msg, parent=self.root)
                    self.cargar()
                else:
                    registrar("Asistente Internet: DNS Cloudflare", msg, False)
                    messagebox.showerror("Problemas Con Internet", msg, parent=self.root)

            en_hilo(self.root, trabajo, al_terminar=terminar)
            return

        if accion == "reiniciar_nm":
            mensaje = (
                "Que se va a hacer?\n"
                "Se reiniciara NetworkManager (gestor de red).\n\n"
                "Por que?\n"
                "El adaptador o la salida a Internet no responden bien.\n\n"
                "Que riesgos tiene?\n"
                "Perderas la conexion unos segundos. Las descargas activas se interrumpiran.\n\n"
                "Continuar?"
            )
            if not confirmar(mensaje, self.root, "Reiniciar red"):
                return
            self._set_ocupado(True, "Reiniciando NetworkManager...")

            def trabajo():
                return repair_network()

            def terminar(resultado):
                self._set_ocupado(False)
                ok, msg = resultado
                if ok:
                    registrar("Asistente Internet: reiniciar NM", msg, True)
                    messagebox.showinfo("Problemas Con Internet", msg, parent=self.root)
                    self.root.after(2000, self.cargar)
                else:
                    registrar("Asistente Internet: reiniciar NM", msg, False)
                    messagebox.showerror("Problemas Con Internet", msg, parent=self.root)

            en_hilo(self.root, trabajo, al_terminar=terminar)
