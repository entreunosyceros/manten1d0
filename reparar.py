"""Reparaciones guiadas de Ubuntu: continuación del diagnóstico con tarjetas por problema."""

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import preferencias
import requests
from diagnostico import listar_unidades_fallidas
from registro import confirmar, en_hilo, registrar, sudo_run
from tooltip import ToolTip


def _comando(args, timeout=30):
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


def _hay_internet():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except requests.RequestException:
        return False


def _cups_instalado():
    return bool(
        shutil.which("cupsd")
        or os.path.exists("/lib/systemd/system/cups.service")
        or os.path.exists("/usr/lib/systemd/system/cups.service")
    )


def _cups_activo():
    proceso = _comando(["systemctl", "is-active", "cups.service"], timeout=15)
    return (proceso.stdout or "").strip() == "active"


def _resultado_sudo(proceso, ok_msg, fail_default):
    if proceso is None:
        return False, "Cancelado o sin contraseña."
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout or fail_default).strip()
        return False, detalle[:500]
    return True, ok_msg


# --- Acciones de reparación (una responsabilidad cada una) ---


def repair_dpkg():
    """Termina configuraciones a medias: dpkg --configure -a."""
    return _resultado_sudo(
        sudo_run(["dpkg", "--configure", "-a"], "Reparar dpkg (configure -a)", timeout=300),
        "dpkg --configure -a completado.",
        "No se pudo ejecutar dpkg --configure -a.",
    )


def repair_apt():
    """Corrige dependencias rotas: apt-get -f install -y."""
    return _resultado_sudo(
        sudo_run(
            ["apt-get", "-f", "install", "-y"],
            "Reparar dependencias APT (-f install)",
            timeout=600,
        ),
        "Dependencias APT reparadas (apt-get -f install).",
        "No se pudo ejecutar apt-get -f install.",
    )


def restart_failed_service(unidad):
    """Reinicia una unidad systemd concreta."""
    return _resultado_sudo(
        sudo_run(
            ["systemctl", "restart", unidad],
            f"Reiniciar servicio {unidad}",
            timeout=120,
        ),
        f"Servicio reiniciado: {unidad}.",
        f"No se pudo reiniciar {unidad}.",
    )


def restart_failed_services(unidades):
    """Reinicia una lista de unidades. Devuelve (ok, mensaje)."""
    if not unidades:
        unidades_list, err = listar_unidades_fallidas()
        if err:
            return False, err
        unidades = [u["unidad"] for u in unidades_list]
    if not unidades:
        return True, "Ya no hay unidades en fallo."
    fallos = []
    for nombre in unidades:
        ok, msg = restart_failed_service(nombre)
        if not ok:
            fallos.append(f"{nombre}: {msg}")
    if fallos:
        return False, "Algunos servicios no se recuperaron:\n" + "\n".join(fallos[:8])
    return True, f"Se reiniciaron {len(unidades)} servicio(s)."


def repair_network():
    """Reinicia NetworkManager (o networking como respaldo)."""
    if not shutil.which("systemctl"):
        return False, "systemctl no está disponible."
    resultado = sudo_run(
        ["systemctl", "restart", "NetworkManager"],
        "Reiniciar NetworkManager",
        timeout=90,
    )
    if resultado is None:
        return False, "Cancelado o sin contraseña."
    if resultado.returncode == 0:
        return True, "Gestor de red reiniciado. Espera unos segundos y comprueba Internet."
    resultado = sudo_run(
        ["systemctl", "restart", "networking"],
        "Reiniciar networking",
        timeout=90,
    )
    return _resultado_sudo(
        resultado,
        "Servicio networking reiniciado.",
        "No se pudo reiniciar la red.",
    )


def restart_audio():
    """Reinicia PipeWire o PulseAudio."""
    from cat_sistema_extra import _reiniciar_audio
    _resultado, error = _reiniciar_audio()
    if error:
        return False, error
    return True, "Servicio de sonido reiniciado."


def repair_cups():
    """Reinicia cups.service."""
    return _resultado_sudo(
        sudo_run(
            ["systemctl", "restart", "cups.service"],
            "Reiniciar CUPS",
            timeout=90,
        ),
        "Servicio de impresión (CUPS) reiniciado.",
        "No se pudo reiniciar CUPS.",
    )


def clean_package_cache():
    """Vacía la caché de paquetes APT."""
    return _resultado_sudo(
        sudo_run(["apt-get", "clean"], "Limpiar caché APT", timeout=120),
        "Caché APT vaciada (apt-get clean).",
        "No se pudo limpiar la caché APT.",
    )


def _detectar_estado_paquetes():
    """
    Devuelve dict:
      audit: texto de dpkg --audit o ""
      a_medias: lista de nombres de paquetes
      updates_pendientes: bool (operaciones dpkg sin terminar)
    """
    auditoria = _comando(["dpkg", "--audit"], timeout=40)
    texto_audit = (auditoria.stdout or "").strip()

    updates = "/var/lib/dpkg/updates"
    try:
        pendientes = [n for n in os.listdir(updates) if not n.startswith(".")]
    except OSError:
        pendientes = []

    consulta = _comando(
        ["dpkg-query", "-W", "-f=${db:Status-Abbrev} ${Package}\n"],
        timeout=40,
    )
    a_medias = []
    for linea in (consulta.stdout or "").splitlines():
        if not linea or len(linea) < 3:
            continue
        estado = linea[:3].strip()
        if len(estado) >= 2 and estado[1] in "HUFWt":
            partes = linea.split(None, 1)
            if len(partes) > 1 and partes[1].strip():
                a_medias.append(partes[1].strip())

    return {
        "audit": texto_audit,
        "a_medias": a_medias,
        "updates_pendientes": bool(pendientes),
        "n_updates": len(pendientes),
    }


def detectar_reparaciones():
    """
    Lista problemas reparables y acciones útiles.
    Campos: id, nivel, titulo, detalle, que, por_que, riesgos, automatico,
            boton (texto), unidad (opcional), unidades (opcional).
    """
    items = []
    pkg = _detectar_estado_paquetes()

    # APT: dependencias / audit
    if pkg["audit"]:
        items.append({
            "id": "apt",
            "nivel": "error",
            "titulo": "Problema detectado: dependencias APT",
            "detalle": (
                "APT tiene paquetes con dependencias pendientes.\n"
                + pkg["audit"].splitlines()[0][:160]
            ),
            "que": (
                "Se ejecutará `apt-get -f install -y` para corregir dependencias rotas. "
                "Si hace falta, antes se intentará `dpkg --configure -a`."
            ),
            "por_que": "Hay paquetes que APT no puede dejar en un estado coherente.",
            "riesgos": (
                "Puede descargar e instalar (o, en casos raros, quitar) paquetes. "
                "No borra tus documentos."
            ),
            "automatico": True,
            "boton": "Reparar",
            "antes_dpkg": bool(pkg["a_medias"] or pkg["updates_pendientes"]),
        })

    # dpkg: paquetes a medias / updates
    if pkg["a_medias"] or pkg["updates_pendientes"]:
        if pkg["a_medias"]:
            muestra = ", ".join(pkg["a_medias"][:4])
            if len(pkg["a_medias"]) > 4:
                muestra += "..."
            detalle = f"Se detectaron paquetes parcialmente instalados: {muestra}."
        else:
            detalle = (
                f"Hay {pkg['n_updates']} operación(es) de dpkg sin terminar "
                "en /var/lib/dpkg/updates."
            )
        items.append({
            "id": "dpkg",
            "nivel": "error",
            "titulo": "Problema detectado: paquetes a medias",
            "detalle": detalle,
            "que": "Se ejecutará `dpkg --configure -a` para terminar instalaciones a medias.",
            "por_que": "Una instalación o actualización se interrumpió o quedó incompleta.",
            "riesgos": (
                "Bajo-medio. Puede pedir configurar paquetes de forma interactiva "
                "en casos raros; normalmente termina solo."
            ),
            "automatico": True,
            "boton": "Reparar paquetes",
        })

    unidades, error_svc = listar_unidades_fallidas()
    if error_svc:
        items.append({
            "id": "servicios_info",
            "nivel": "aviso",
            "titulo": "No se pudieron listar servicios fallidos",
            "detalle": error_svc,
            "que": None,
            "por_que": None,
            "riesgos": None,
            "automatico": True,
            "solo_info": True,
        })
    elif unidades:
        for u in unidades:
            nombre = u["unidad"]
            desc = (u.get("descripcion") or "").strip()
            detalle = desc or f"Estado: {u.get('estado', '?')} / {u.get('subestado', '?')}"
            items.append({
                "id": "servicio",
                "nivel": "error",
                "titulo": f"Servicio con errores: {nombre}",
                "detalle": f"{nombre} ha fallado. {detalle}",
                "que": f"Se reiniciará la unidad con `systemctl restart {nombre}`.",
                "por_que": "systemd la marca como failed; a veces un reinicio la recupera.",
                "riesgos": (
                    "Si el fallo es de configuración, volverá a caer. "
                    "Reiniciar corta un momento lo que ese servicio hace."
                ),
                "automatico": True,
                "boton": "Reiniciar servicio",
                "unidad": nombre,
            })
        if len(unidades) > 1:
            nombres = [u["unidad"] for u in unidades]
            items.append({
                "id": "servicios_todos",
                "nivel": "aviso",
                "titulo": f"Reiniciar los {len(nombres)} servicios fallidos",
                "detalle": ", ".join(nombres[:6]) + ("..." if len(nombres) > 6 else ""),
                "que": (
                    "Se reiniciará cada unidad en fallo con `systemctl restart`:\n"
                    + ", ".join(nombres)
                ),
                "por_que": "Atajo cuando hay varios fallos a la vez.",
                "riesgos": "Misma advertencia que al reiniciar uno: pueden volver a fallar.",
                "automatico": True,
                "boton": "Reiniciar todos",
                "unidades": nombres,
            })

    if not _hay_internet():
        items.append({
            "id": "red",
            "nivel": "error",
            "titulo": "Problema detectado: sin Internet",
            "detalle": "No se pudo contactar con la red. Se puede reiniciar NetworkManager.",
            "que": "Se reiniciará el servicio NetworkManager (la red se corta unos segundos).",
            "por_que": "Muchos cortes de Wi-Fi o cable se resuelven reiniciando el gestor de red.",
            "riesgos": "Perderás la conexión unos segundos. Las descargas activas se interrumpirán.",
            "automatico": True,
            "boton": "Reparar",
        })

    if _cups_instalado() and not _cups_activo():
        items.append({
            "id": "cups",
            "nivel": "aviso",
            "titulo": "Problema detectado: impresión (CUPS)",
            "detalle": "cups.service no está activo. Sin él no se puede imprimir.",
            "que": "Se arrancará/reiniciará `cups.service`.",
            "por_que": "El demonio de impresión está parado o ha fallado.",
            "riesgos": "Bajo. Si CUPS está mal configurado, puede volver a pararse.",
            "automatico": True,
            "boton": "Reparar",
        })

    # Acciones útiles (no son “problema detectado”)
    ids_auto = {i["id"] for i in items if i.get("automatico")}
    if "apt" not in ids_auto and "dpkg" not in ids_auto:
        items.append({
            "id": "apt_dpkg_manual",
            "nivel": "info",
            "titulo": "Reparar paquetes APT/dpkg",
            "detalle": "Útil si una instalación se quedó a medias y el análisis no lo marcó.",
            "que": "Se ejecutará `dpkg --configure -a` y después `apt-get -f install -y`.",
            "por_que": "Corrige dependencias rotas y paquetes a medio instalar.",
            "riesgos": "Puede instalar o quitar paquetes para resolver dependencias.",
            "automatico": False,
            "boton": "Reparar",
        })
    if "red" not in ids_auto:
        items.append({
            "id": "red",
            "nivel": "info",
            "titulo": "Reiniciar el gestor de red",
            "detalle": "NetworkManager: útil si el Wi-Fi o el cable fallan a ratos.",
            "que": "Se reiniciará NetworkManager. La conexión se cortará unos segundos.",
            "por_que": "Reinicia la pila de red sin reiniciar el equipo.",
            "riesgos": "Cortarás Internet unos segundos.",
            "automatico": False,
            "boton": "Reparar",
        })
    items.append({
        "id": "audio",
        "nivel": "info",
        "titulo": "Reiniciar el sonido",
        "detalle": "PipeWire o PulseAudio: útil cuando no hay audio tras auriculares o HDMI.",
        "que": "Se reiniciará el servicio de sonido del usuario (PipeWire o PulseAudio).",
        "por_que": "A veces el demonio de audio se queda en un estado raro.",
        "riesgos": "Muy bajo. Puede haber un silencio breve.",
        "automatico": False,
        "boton": "Reparar",
    })
    if "cups" not in ids_auto and _cups_instalado():
        items.append({
            "id": "cups",
            "nivel": "info",
            "titulo": "Reiniciar el servicio de impresión",
            "detalle": "Reinicia CUPS si la impresora no responde.",
            "que": "Se reiniciará `cups.service`.",
            "por_que": "La cola de impresión a veces se queda bloqueada.",
            "riesgos": "Bajo. Los trabajos en cola pueden reintentarse.",
            "automatico": False,
            "boton": "Reparar",
        })
    items.append({
        "id": "cache_apt",
        "nivel": "info",
        "titulo": "Limpiar caché de paquetes APT",
        "detalle": "Borra .deb descargados en /var/cache/apt/archives (libera espacio).",
        "que": "Se ejecutará `apt-get clean`.",
        "por_que": "Esos paquetes ya no hacen falta para instalar lo que ya está instalado.",
        "riesgos": "Ninguno relevante. La próxima instalación volverá a descargar lo necesario.",
        "automatico": False,
        "boton": "Limpiar",
    })
    return items


def _mensaje_confirmacion(item):
    return (
        f"¿Qué voy a hacer?\n{item['que']}\n\n"
        f"¿Por qué?\n{item['por_que']}\n\n"
        f"¿Qué riesgos tiene?\n{item['riesgos']}\n\n"
        "¿Quieres continuar?"
    )


def ejecutar_reparacion(item):
    """Despacha a repair_* / restart_*. Devuelve (ok, mensaje)."""
    ident = item["id"]

    if ident == "dpkg":
        return repair_dpkg()

    if ident == "apt":
        if item.get("antes_dpkg"):
            ok_d, msg_d = repair_dpkg()
            if not ok_d:
                return False, f"Antes de APT falló dpkg: {msg_d}"
        return repair_apt()

    if ident == "apt_dpkg_manual":
        ok_d, msg_d = repair_dpkg()
        if not ok_d:
            return False, msg_d
        ok_a, msg_a = repair_apt()
        if not ok_a:
            return False, f"dpkg OK; APT falló: {msg_a}"
        return True, "Paquetes reparados (dpkg --configure -a y apt-get -f install)."

    if ident == "servicio":
        unidad = item.get("unidad")
        if not unidad:
            return False, "No se indicó la unidad a reiniciar."
        return restart_failed_service(unidad)

    if ident == "servicios_todos":
        return restart_failed_services(item.get("unidades") or [])

    if ident == "red":
        return repair_network()

    if ident == "audio":
        return restart_audio()

    if ident == "cups":
        return repair_cups()

    if ident == "cache_apt":
        return clean_package_cache()

    return False, f"Reparación desconocida: {ident}"


class RepararUbuntu:
    """Tarjetas de problema detectado + reparaciones útiles (evolución del diagnóstico)."""

    def __init__(self, root):
        self.root = root
        self.root.title("Reparar Ubuntu")
        self.root.minsize(640, 540)
        self._centrar(720, 600)
        self._ocupado = False
        self._items = []
        self._utiles_visibles = False

        tk.Label(self.root, text="Reparar Ubuntu", font=("Arial", 14, "bold")).pack(
            pady=(12, 4)
        )
        tk.Label(
            self.root,
            text=(
                "Continúa el diagnóstico: muestra cada problema detectado y una "
                "reparación guiada (qué, por qué y riesgos) antes de actuar."
            ),
            wraplength=680,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 8))

        self.lbl_estado = tk.Label(self.root, text="Comprobando...", anchor="w", justify=tk.LEFT)
        self.lbl_estado.pack(fill=tk.X, padx=14)
        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(4, 8))

        marco_lista = tk.Frame(self.root)
        marco_lista.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        self.lienzo = tk.Canvas(marco_lista, highlightthickness=0)
        scroll = ttk.Scrollbar(marco_lista, orient=tk.VERTICAL, command=self.lienzo.yview)
        self.interior = tk.Frame(self.lienzo)
        self.interior.bind(
            "<Configure>",
            lambda e: self.lienzo.configure(scrollregion=self.lienzo.bbox("all")),
        )
        self._ventana_id = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        self.lienzo.bind("<Configure>", self._ajustar_ancho)
        self.lienzo.configure(yscrollcommand=scroll.set)
        self.lienzo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log = scrolledtext.ScrolledText(self.root, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self.log.pack(fill=tk.X, padx=14, pady=(0, 8))

        botones = tk.Frame(self.root)
        botones.pack(pady=(0, 12))
        self.btn_buscar = tk.Button(botones, text="Buscar problemas", width=16, command=self.cargar)
        self.btn_buscar.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_buscar, "Vuelve a detectar problemas reparables")
        self.btn_utiles = tk.Button(
            botones,
            text="Otras reparaciones",
            width=16,
            command=self._toggle_utiles,
        )
        self.btn_utiles.pack(side=tk.LEFT, padx=6)
        ToolTip(
            self.btn_utiles,
            "Muestra u oculta acciones útiles (audio, red, caché APT...) aunque no haya fallo",
        )
        btn_cerrar = tk.Button(botones, text="Cerrar", width=12, command=self.root.destroy)
        btn_cerrar.pack(side=tk.LEFT, padx=6)
        ToolTip(btn_cerrar, "Cierra esta ventana")

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)
        self.cargar()

    def _centrar(self, ancho, alto):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - ancho) // 2
        y = (self.root.winfo_screenheight() - alto) // 2
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _ajustar_ancho(self, event):
        self.lienzo.itemconfigure(self._ventana_id, width=event.width)

    def _set_ocupado(self, ocupado, mensaje=None):
        self._ocupado = ocupado
        estado = tk.DISABLED if ocupado else tk.NORMAL
        for btn in (self.btn_buscar, self.btn_utiles):
            try:
                btn.config(state=estado)
            except tk.TclError:
                pass
        for hijo in self.interior.winfo_children():
            for widget in hijo.winfo_children():
                if isinstance(widget, tk.Button):
                    try:
                        widget.config(state=estado)
                    except tk.TclError:
                        pass
        if ocupado:
            self.progreso.start(12)
            if mensaje:
                self.lbl_estado.config(text=mensaje)
        else:
            self.progreso.stop()

    def _log(self, texto):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, texto.rstrip() + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _toggle_utiles(self):
        self._utiles_visibles = not self._utiles_visibles
        self._mostrar(self._items)

    def cargar(self):
        if self._ocupado:
            return
        self._set_ocupado(True, "Buscando problemas reparables...")
        for hijo in self.interior.winfo_children():
            hijo.destroy()

        def trabajador():
            return detectar_reparaciones()

        def al_terminar(items):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._items = items
            self._mostrar(items)

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self.lbl_estado.config(text=str(error))
            messagebox.showerror("Reparar Ubuntu", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)

    def _tarjeta(self, item, etiqueta_problema=False):
        marco = tk.Frame(self.interior, relief=tk.GROOVE, borderwidth=1, padx=10, pady=8)
        marco.pack(fill=tk.X, pady=6)
        if etiqueta_problema and item.get("automatico") and not item.get("solo_info"):
            tk.Label(
                marco,
                text="Problema detectado",
                font=("Arial", 9),
                fg="#c0392b",
                anchor="w",
            ).pack(anchor="w")
        tk.Label(
            marco,
            text=item["titulo"],
            font=("Arial", 10, "bold"),
            anchor="w",
            justify=tk.LEFT,
            wraplength=620,
        ).pack(anchor="w")
        tk.Label(
            marco,
            text=item["detalle"],
            anchor="w",
            justify=tk.LEFT,
            wraplength=620,
        ).pack(anchor="w", pady=(2, 8))
        if item.get("solo_info") or not item.get("que"):
            return
        texto_btn = item.get("boton") or "Reparar"
        btn = tk.Button(
            marco,
            text=texto_btn,
            width=max(14, len(texto_btn) + 2),
            command=lambda i=item: self._reparar(i),
        )
        btn.pack(anchor="e")
        ToolTip(
            btn,
            "Antes de actuar explica qué hará, por qué y los riesgos, y pide confirmación",
        )

    def _mostrar(self, items):
        for hijo in self.interior.winfo_children():
            hijo.destroy()

        detectados = [i for i in items if i.get("automatico") and not i.get("solo_info")]
        utiles = [i for i in items if not i.get("automatico")]
        infos = [i for i in items if i.get("solo_info")]

        if detectados:
            self.lbl_estado.config(
                text=f"{len(detectados)} reparación(es) disponible(s) por problemas detectados.",
            )
        else:
            self.lbl_estado.config(
                text="No se detectaron fallos graves. Usa «Otras reparaciones» si lo necesitas.",
            )

        tk.Label(
            self.interior,
            text="Reparaciones disponibles",
            font=("Arial", 11, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(4, 2))

        if not detectados and not infos:
            tk.Label(
                self.interior,
                text="Ningún problema reparable ahora mismo.",
                anchor="w",
                fg="#1e8449",
            ).pack(anchor="w", pady=4)

        for item in infos:
            self._tarjeta(item, etiqueta_problema=False)
        for item in detectados:
            self._tarjeta(item, etiqueta_problema=True)

        if self._utiles_visibles and utiles:
            tk.Label(
                self.interior,
                text="Otras reparaciones útiles",
                font=("Arial", 11, "bold"),
                anchor="w",
            ).pack(anchor="w", pady=(14, 2))
            for item in utiles:
                self._tarjeta(item, etiqueta_problema=False)

        self.btn_utiles.config(
            text="Ocultar otras" if self._utiles_visibles else "Otras reparaciones",
        )

        if preferencias.tema_seleccionado != "Claro":
            preferencias.cambiar_tema(self.root, preferencias.tema_seleccionado)

    def _reparar(self, item):
        if self._ocupado:
            return
        if not item.get("que"):
            return
        if not confirmar(_mensaje_confirmacion(item), self.root, "Confirmar reparación"):
            self._log(f"Cancelado: {item['titulo']}")
            registrar("Reparar Ubuntu", f"{item['id']} cancelado", False)
            return

        self._set_ocupado(True, f"Reparando: {item['titulo']}...")
        self._log(f"-> {item['titulo']}")

        def trabajador():
            return ejecutar_reparacion(item)

        def al_terminar(resultado):
            if not self.root.winfo_exists():
                return
            ok, mensaje = resultado
            self._set_ocupado(False)
            self._log(("[OK] " if ok else "[ERROR] ") + mensaje)
            registrar("Reparar Ubuntu", f"{item['id']}: {mensaje[:200]}", ok)
            if ok:
                messagebox.showinfo("Reparar Ubuntu", mensaje, parent=self.root)
            else:
                messagebox.showwarning("Reparar Ubuntu", mensaje, parent=self.root)
            self.cargar()

        def al_error(error):
            if not self.root.winfo_exists():
                return
            self._set_ocupado(False)
            self._log(f"[ERROR] {error}")
            messagebox.showerror("Reparar Ubuntu", str(error), parent=self.root)

        en_hilo(self.root, trabajador, al_terminar=al_terminar, al_error=al_error)
