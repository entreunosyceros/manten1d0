"""Centro de seguridad: resumen claro de firewall, actualizaciones, usuario y puertos."""

import getpass
import os
import re
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import preferencias
from actualizar_todo import ActualizarTodo, contar_apt
from cat_sistema_extra import Cortafuegos
from diagnostico import estado_ufw
from registro import confirmar, en_hilo, registrar, sudo_run
from tooltip import ToolTip, con_tooltip

# Colores de nivel (texto ASCII OK / AVISO / ERROR)
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

# Puerto -> (nombre corto, explicacion, unidad systemd opcional)
_CATALOGO = {
    22: (
        "SSH",
        "Permite conexiones remotas a este ordenador.\n"
        "Si no utilizas SSH, puedes desactivarlo.",
        "ssh",
    ),
    80: (
        "HTTP",
        "Sirve paginas web sin cifrado (puerto habitual de un servidor web).",
        None,
    ),
    443: (
        "HTTPS",
        "Sirve paginas web cifradas (HTTPS).",
        None,
    ),
    137: (
        "NetBIOS (nombres)",
        "Parte de Samba: anuncia el nombre del equipo en la red.\n"
        "Si no compartes carpetas, puedes desactivar Samba.",
        "smbd",
    ),
    138: (
        "NetBIOS (datagramas)",
        "Parte de Samba en la red local.\n"
        "Si no compartes carpetas, puedes desactivar Samba.",
        "smbd",
    ),
    139: (
        "Samba (NetBIOS)",
        "Parte de las carpetas compartidas en Windows/Linux (Samba).\n"
        "Si no compartes carpetas, puedes desactivar Samba.",
        "smbd",
    ),
    445: (
        "Samba",
        "Carpetas compartidas en la red (Samba).\n"
        "Si no compartes carpetas, puedes desactivar Samba.",
        "smbd",
    ),
    631: (
        "CUPS",
        "Servicio de impresion de Ubuntu (CUPS).\n"
        "Normal en casa si usas impresoras. Puedes pararlo si no imprimes.",
        "cups",
    ),
    3389: (
        "Escritorio remoto (RDP)",
        "Permite controlar este PC en remoto (escritorio remoto).\n"
        "Si no lo usas, conviene desactivarlo.",
        None,
    ),
    5353: (
        "Avahi",
        "Anuncia este equipo en la red local (impresoras, compartir nombre).\n"
        "Es habitual en Ubuntu. Puedes pararlo si no lo necesitas.",
        "avahi-daemon",
    ),
    5900: (
        "VNC",
        "Escritorio remoto VNC. Si no lo usas, conviene desactivarlo.",
        None,
    ),
    8080: (
        "HTTP alternativo",
        "A menudo lo usan paneles web o aplicaciones locales.",
        None,
    ),
}

_UNIDADES_ALT = {
    "ssh": ("ssh.service", "sshd.service"),
    "smbd": ("smbd.service", "nmbd.service"),
    "cups": ("cups.service",),
    "avahi-daemon": ("avahi-daemon.service",),
}


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


def _es_localhost(addr):
    a = (addr or "").strip().lower()
    if a in ("127.0.0.1", "::1", "[::1]", "localhost"):
        return True
    if a.startswith("127."):
        return True
    return False


def _es_bind_red(addr):
    """True si el bind es alcanzable desde la red (no solo este PC)."""
    a = (addr or "").strip().lower()
    if not a or a in ("*", "0.0.0.0", "::", "[::]"):
        return True
    if _es_localhost(a):
        return False
    # Direccion concreta de interfaz = visible en esa red
    return True


def _parsear_local_addr(campo):
    """Devuelve (addr, puerto) desde el Local Address de ss."""
    campo = (campo or "").strip()
    if not campo:
        return "", None
    # IPv6: [::]:22 o *:5353 o 127.0.0.1:631
    if campo.startswith("["):
        m = re.match(r"^\[([^\]]+)\]:(\d+)$", campo)
        if m:
            return m.group(1), int(m.group(2))
    if ":" in campo:
        addr, puerto_txt = campo.rsplit(":", 1)
        if puerto_txt.isdigit():
            return addr, int(puerto_txt)
    return campo, None


def _listar_escuchas():
    """Lista sockets en escucha. Sin sudo. Devuelve lista de dicts."""
    if shutil.which("ss") is None:
        return [], "No se encontro el comando ss."
    proceso = _comando(["ss", "-ltnu"], timeout=20)
    if proceso.returncode != 0:
        error = (proceso.stderr or proceso.stdout or "No se pudo listar puertos.").strip()
        return [], error

    # Agrupar por (proto, puerto): una fila por servicio, no por cada IP
    por_clave = {}
    for linea in (proceso.stdout or "").splitlines():
        linea = linea.strip()
        if not linea or linea.lower().startswith("netid") or linea.lower().startswith("state"):
            continue
        partes = linea.split()
        if len(partes) < 5:
            continue
        # Formato tipico: Netid State Recv-Q Send-Q LocalAddress:Port PeerAddress:Port
        netid = partes[0].lower()
        if netid not in ("tcp", "udp"):
            continue
        local = partes[4]
        addr, puerto = _parsear_local_addr(local)
        if puerto is None:
            continue
        solo_local = _es_localhost(addr)
        en_red = _es_bind_red(addr) and not solo_local
        clave = (netid, puerto)
        actual = por_clave.get(clave)
        addr_norm = addr or "*"
        if actual is None:
            nombre, explicacion, servicio = _explicacion_puerto(puerto, netid)
            por_clave[clave] = {
                "proto": netid,
                "puerto": puerto,
                "addr": addr_norm,
                "en_red": en_red,
                "solo_local": solo_local,
                "nombre": nombre,
                "explicacion": explicacion,
                "servicio": servicio,
            }
            continue
        # Preferir bind abierto a toda la red frente a IP concreta o localhost
        if en_red and not actual["en_red"]:
            actual["en_red"] = True
            actual["solo_local"] = False
            actual["addr"] = addr_norm
        elif en_red and actual["en_red"] and addr_norm in ("*", "0.0.0.0", "::"):
            actual["addr"] = addr_norm

    escuchas = list(por_clave.values())
    escuchas.sort(key=lambda e: (0 if e["en_red"] else 1, e["puerto"], e["proto"]))
    return escuchas, None


def _explicacion_puerto(puerto, proto="tcp"):
    if puerto in _CATALOGO:
        nombre, texto, servicio = _CATALOGO[puerto]
        return nombre, texto, servicio
    proto = (proto or "tcp").upper()
    return (
        f"Puerto {puerto}",
        f"Hay un servicio escuchando el puerto {puerto}/{proto}.\n"
        "Si no reconoces para que sirve, conviene revisar el cortafuegos "
        "o preguntar antes de abrirlo hacia Internet.",
        None,
    )


def _servicio_para_puerto(puerto):
    info = _CATALOGO.get(puerto)
    if not info:
        return None
    return info[2]


def _unidades_servicio(clave):
    return _UNIDADES_ALT.get(clave, ())


def _unidad_activa(unidad):
    proceso = _comando(["systemctl", "is-active", "--", unidad], timeout=10)
    return (proceso.stdout or "").strip() == "active"


def _resolver_unidad(clave):
    for unidad in _unidades_servicio(clave):
        if _unidad_activa(unidad):
            return unidad
    unidades = _unidades_servicio(clave)
    return unidades[0] if unidades else None


def _check_usuario_protegido():
    usuario = getpass.getuser()
    if usuario == "root" or os.geteuid() == 0:
        return {
            "nivel": "error",
            "titulo": "Sesion como root",
            "detalle": "Estas usando el equipo como administrador root. No es recomendable para el dia a dia.",
            "accion": None,
        }
    proceso = _comando(["passwd", "-S", "--", usuario], timeout=10)
    texto = (proceso.stdout or "").strip()
    # Formato: usuario Estado Fecha ...  Estado: P=password, L=locked, NP=no password
    estado = ""
    if texto:
        partes = texto.split()
        if len(partes) >= 2:
            estado = partes[1].upper()
    if estado == "NP":
        return {
            "nivel": "error",
            "titulo": "Usuario sin contrasena",
            "detalle": f"La cuenta {usuario} no tiene contrasena. Cualquiera con acceso fisico podria usarla.",
            "accion": None,
        }
    if estado == "L":
        return {
            "nivel": "aviso",
            "titulo": "Cuenta bloqueada",
            "detalle": f"La cuenta {usuario} esta bloqueada (L). Revisa el perfil de usuario si no puedes entrar.",
            "accion": None,
        }
    if estado == "P" or estado.startswith("P"):
        return {
            "nivel": "ok",
            "titulo": "Usuario protegido",
            "detalle": f"La cuenta {usuario} tiene contrasena.",
            "accion": None,
        }
    return {
        "nivel": "info",
        "titulo": "Usuario: no se pudo comprobar",
        "detalle": "No se pudo leer el estado de la contrasena con passwd -S.",
        "accion": None,
    }


def analizar_seguridad():
    """Devuelve dict con items de checklist y lista de escuchas."""
    items = []
    escuchas, error_ss = _listar_escuchas()
    en_red = [e for e in escuchas if e["en_red"]]

    # Firewall
    estado = estado_ufw()
    if estado == "activo":
        items.append({
            "nivel": "ok",
            "titulo": "Firewall activo",
            "detalle": "El cortafuegos (ufw) esta activado.",
            "accion": "cortafuegos",
        })
    elif estado == "inactivo":
        items.append({
            "nivel": "aviso",
            "titulo": "Firewall desactivado",
            "detalle": "ufw esta instalado pero inactivo. Otros equipos de la red pueden intentar conectar.",
            "accion": "cortafuegos",
        })
    elif estado == "no_instalado":
        items.append({
            "nivel": "aviso",
            "titulo": "Firewall no instalado",
            "detalle": "ufw no esta en el sistema. Puedes instalarlo desde el cortafuegos.",
            "accion": "cortafuegos",
        })
    else:
        items.append({
            "nivel": "info",
            "titulo": "Estado del firewall desconocido",
            "detalle": "No se pudo leer ufw sin privilegios. Abre el cortafuegos para consultarlo.",
            "accion": "cortafuegos",
        })

    # Actualizaciones
    total, seguridad = contar_apt()
    if total is None:
        items.append({
            "nivel": "info",
            "titulo": "No se pudo consultar actualizaciones",
            "detalle": "Abre Actualizar todo para comprobarlo.",
            "accion": "actualizar",
        })
    else:
        if total == 0:
            items.append({
                "nivel": "ok",
                "titulo": "Sistema actualizado",
                "detalle": "No hay actualizaciones APT pendientes.",
                "accion": "actualizar",
            })
        else:
            items.append({
                "nivel": "aviso",
                "titulo": f"{total} actualizacion(es) pendiente(s)",
                "detalle": "Hay paquetes por actualizar. Conviene instalarlos.",
                "accion": "actualizar",
            })
        if seguridad and seguridad > 0:
            items.append({
                "nivel": "aviso",
                "titulo": f"{seguridad} actualizacion(es) de seguridad",
                "detalle": "Hay actualizaciones marcadas como de seguridad. Instalarlas reduce riesgos.",
                "accion": "actualizar",
            })

    # Puertos externos
    if error_ss:
        items.append({
            "nivel": "info",
            "titulo": "No se pudieron listar puertos",
            "detalle": error_ss,
            "accion": None,
        })
    elif not en_red:
        items.append({
            "nivel": "ok",
            "titulo": "Sin puertos externos detectados",
            "detalle": "No hay servicios escuchando fuera de este equipo (solo localhost o ninguno).",
            "accion": None,
        })
    else:
        items.append({
            "nivel": "aviso",
            "titulo": f"{len(en_red)} puerto(s) accesible(s) en red",
            "detalle": "Hay servicios escuchando en direcciones visibles desde la red local.",
            "accion": None,
        })

    # Usuario
    items.append(_check_usuario_protegido())

    # Servicios escuchando en red (conteo)
    if not error_ss:
        if len(en_red) == 0:
            items.append({
                "nivel": "ok",
                "titulo": "Ningun servicio escuchando en red",
                "detalle": "No hay sockets TCP/UDP abiertos hacia la red.",
                "accion": None,
            })
        else:
            items.append({
                "nivel": "aviso",
                "titulo": f"{len(en_red)} servicio(s) escuchando en red",
                "detalle": "Revisa la lista de abajo. Algunos (CUPS, Avahi) son normales en casa.",
                "accion": None,
            })

    return {"items": items, "escuchas": escuchas, "error_ss": error_ss}


class CentroSeguridad:
    """Panel: checklist de seguridad + puertos con explicaciones humanas."""

    def __init__(self, root):
        self.root = root
        self.root.title("Centro De Seguridad")
        self.root.minsize(680, 560)
        self._centrar(720, 600)
        self._ocupado = False
        self._items = []
        self._escuchas = []
        self._por_iid = {}

        tk.Label(self.root, text="Centro de seguridad", font=("Arial", 14, "bold")).pack(
            pady=(12, 2)
        )
        tk.Label(
            self.root,
            text=(
                "Resumen claro del cortafuegos, actualizaciones, tu usuario "
                "y los servicios que escuchan en la red. Sin ss ni iptables."
            ),
            wraplength=680,
            justify=tk.LEFT,
        ).pack(padx=14, pady=(0, 6))

        self.lbl_estado = tk.Label(
            self.root, text="Analizando seguridad...", anchor="w", font=("Arial", 10, "bold")
        )
        self.lbl_estado.pack(fill=tk.X, padx=14)
        self.progreso = ttk.Progressbar(self.root, mode="indeterminate")
        self.progreso.pack(fill=tk.X, padx=14, pady=(2, 6))

        cuerpo = tk.Frame(self.root)
        cuerpo.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 4))

        izq = tk.Frame(cuerpo)
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(izq, text="Seguridad", font=("Arial", 11, "bold"), anchor="w").pack(fill=tk.X)
        self.lista_items = tk.Listbox(izq, height=10, exportselection=False, font=("Arial", 10))
        self.lista_items.pack(fill=tk.BOTH, expand=True, pady=(2, 8))
        self.lista_items.bind("<<ListboxSelect>>", self._al_seleccionar_item)
        ToolTip(self.lista_items, "Pulsa un resultado para ver el detalle y acciones")

        tk.Label(izq, text="Puertos abiertos", font=("Arial", 11, "bold"), anchor="w").pack(
            fill=tk.X
        )
        cols = ("puerto", "nombre", "alcance")
        self.tree = ttk.Treeview(izq, columns=cols, show="headings", selectmode="browse", height=8)
        self.tree.heading("puerto", text="Puerto")
        self.tree.heading("nombre", text="Servicio")
        self.tree.heading("alcance", text="Alcance")
        self.tree.column("puerto", width=90, stretch=False)
        self.tree.column("nombre", width=160, stretch=True)
        self.tree.column("alcance", width=100, stretch=False)
        scroll = ttk.Scrollbar(izq, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._mostrar_puerto())

        der = tk.Frame(cuerpo, width=260)
        der.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        der.pack_propagate(False)

        tk.Label(der, text="Detalle", font=("Arial", 11, "bold"), anchor="w").pack(fill=tk.X)
        self.lbl_detalle = tk.Label(
            der,
            text="Selecciona un resultado o un puerto.",
            justify=tk.LEFT,
            anchor="nw",
            wraplength=240,
        )
        self.lbl_detalle.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        self.btn_accion = tk.Button(der, text="Accion", width=20, command=self._accion_principal)
        self.btn_accion.pack(pady=2)
        self.tip_accion = ToolTip(self.btn_accion, "Depende de lo seleccionado")
        self.btn_desactivar = tk.Button(
            der, text="Desactivar servicio", width=20, command=self._desactivar_servicio
        )
        self.btn_desactivar.pack(pady=2)
        ToolTip(
            self.btn_desactivar,
            "Para el servicio asociado al puerto (SSH, Samba, CUPS, Avahi) con confirmacion",
        )
        self.btn_cortafuegos = tk.Button(
            der, text="Abrir cortafuegos", width=20, command=self._abrir_cortafuegos
        )
        self.btn_cortafuegos.pack(pady=2)
        ToolTip(self.btn_cortafuegos, "Activa o desactiva ufw y reglas frecuentes")

        pie = tk.Frame(self.root)
        pie.pack(pady=(4, 12))
        con_tooltip(
            tk.Button(pie, text="Actualizar estado", width=16, command=self.cargar),
            "Vuelve a leer firewall, actualizaciones y puertos",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Actualizar todo", width=14, command=self._abrir_actualizar),
            "Abre el panel para instalar actualizaciones APT, Snap y Flatpak",
        ).pack(side=tk.LEFT, padx=4)
        con_tooltip(
            tk.Button(pie, text="Cerrar", width=10, command=self.root.destroy),
            "Cierra esta ventana",
        ).pack(side=tk.LEFT, padx=4)

        self._seleccion = None  # ("item", idx) o ("puerto", iid)

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
        for btn in (self.btn_accion, self.btn_desactivar, self.btn_cortafuegos):
            try:
                btn.config(state=estado)
            except tk.TclError:
                pass
        if ocupado:
            try:
                self.progreso.start(12)
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
        self._set_ocupado(True, "Analizando seguridad...")

        def al_terminar(datos):
            self._set_ocupado(False)
            self._pintar(datos)
            avisos = sum(1 for i in datos["items"] if i["nivel"] in ("aviso", "error"))
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

        def al_error(error):
            self._set_ocupado(False)
            self.lbl_estado.config(text=f"Error: {error}", fg=_COLORES["error"])

        en_hilo(self.root, analizar_seguridad, al_terminar=al_terminar, al_error=al_error)

    def _pintar(self, datos):
        self._items = datos.get("items") or []
        self._escuchas = datos.get("escuchas") or []
        self._por_iid = {}
        self._seleccion = None

        self.lista_items.delete(0, tk.END)
        for item in self._items:
            marca = _MARCAS.get(item["nivel"], "INFO")
            self.lista_items.insert(tk.END, f"[{marca}] {item['titulo']}")

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        visibles = [e for e in self._escuchas if e["en_red"]] or self._escuchas
        for esc in visibles:
            alcance = "Red" if esc["en_red"] else "Solo local"
            etiqueta = f"{esc['puerto']}/{esc['proto']}"
            iid = self.tree.insert(
                "",
                tk.END,
                values=(etiqueta, esc["nombre"], alcance),
            )
            self._por_iid[iid] = esc

        self.lbl_detalle.config(text="Selecciona un resultado o un puerto.")
        self.btn_accion.config(text="Accion", state=tk.DISABLED)
        self.btn_desactivar.config(state=tk.DISABLED)

    def _al_seleccionar_item(self, _event=None):
        sel = self.lista_items.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._items):
            return
        self.tree.selection_remove(self.tree.selection())
        self._seleccion = ("item", idx)
        item = self._items[idx]
        self.lbl_detalle.config(text=f"{item['titulo']}\n\n{item['detalle']}")
        accion = item.get("accion")
        if accion == "cortafuegos":
            self.btn_accion.config(text="Abrir cortafuegos", state=tk.NORMAL)
            self.tip_accion.text = "Abre el panel del cortafuegos (ufw)"
        elif accion == "actualizar":
            self.btn_accion.config(text="Actualizar todo", state=tk.NORMAL)
            self.tip_accion.text = "Abre el panel de actualizaciones"
        else:
            self.btn_accion.config(text="Accion", state=tk.DISABLED)
        self.btn_desactivar.config(state=tk.DISABLED)

    def _mostrar_puerto(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        esc = self._por_iid.get(iid)
        if not esc:
            return
        self.lista_items.selection_clear(0, tk.END)
        self._seleccion = ("puerto", iid)
        alcance = (
            "Visible desde la red local (y desde Internet si el router reenvia el puerto)."
            if esc["en_red"]
            else "Solo en este ordenador (localhost)."
        )
        texto = (
            f"{esc['nombre']} ({esc['puerto']}/{esc['proto']})\n\n"
            f"{esc['explicacion']}\n\n"
            f"Escucha en: {esc['addr']}\n"
            f"{alcance}"
        )
        self.lbl_detalle.config(text=texto)
        self.btn_accion.config(text="Abrir cortafuegos", state=tk.NORMAL)
        self.tip_accion.text = "Gestiona reglas ufw para este tipo de acceso"
        if esc.get("servicio"):
            self.btn_desactivar.config(state=tk.NORMAL)
        else:
            self.btn_desactivar.config(state=tk.DISABLED)

    def _accion_principal(self):
        if self._ocupado or not self._seleccion:
            return
        tipo, valor = self._seleccion
        if tipo == "item":
            item = self._items[valor]
            if item.get("accion") == "cortafuegos":
                self._abrir_cortafuegos()
            elif item.get("accion") == "actualizar":
                self._abrir_actualizar()
        elif tipo == "puerto":
            self._abrir_cortafuegos()

    def _abrir_cortafuegos(self):
        Cortafuegos(tk.Toplevel(self.root))

    def _abrir_actualizar(self):
        ActualizarTodo(tk.Toplevel(self.root))

    def _desactivar_servicio(self):
        if self._ocupado or not self._seleccion or self._seleccion[0] != "puerto":
            return
        esc = self._por_iid.get(self._seleccion[1])
        if not esc or not esc.get("servicio"):
            messagebox.showinfo(
                "Centro De Seguridad",
                "No hay un servicio conocido asociado a este puerto.",
                parent=self.root,
            )
            return
        clave = esc["servicio"]
        unidad = _resolver_unidad(clave)
        if not unidad:
            messagebox.showinfo(
                "Centro De Seguridad",
                "No se encontro la unidad systemd de este servicio.",
                parent=self.root,
            )
            return

        mensaje = (
            f"Que se va a hacer?\n"
            f"Se parara y deshabilitara el servicio {unidad}.\n\n"
            f"Por que?\n"
            f"El puerto {esc['puerto']} ({esc['nombre']}) esta escuchando y no lo necesitas.\n\n"
            f"Que riesgos tiene?\n"
            f"Dejara de funcionar lo que dependa de ese servicio "
            f"(por ejemplo, acceso SSH, impresoras o carpetas compartidas).\n\n"
            f"Continuar?"
        )
        if not confirmar(mensaje, self.root, "Desactivar servicio"):
            return

        self._set_ocupado(True, f"Desactivando {unidad}...")

        def trabajo():
            r1 = sudo_run(
                ["systemctl", "stop", "--", unidad],
                f"Parar {unidad}",
                parent=self.root,
                timeout=60,
            )
            if r1 is None:
                return False, "Cancelado"
            if r1.returncode != 0:
                return False, (r1.stderr or r1.stdout or "Error al parar").strip()
            r2 = sudo_run(
                ["systemctl", "disable", "--", unidad],
                f"Deshabilitar {unidad}",
                parent=self.root,
                timeout=60,
            )
            if r2 is None:
                return False, "Cancelado tras parar"
            if r2.returncode != 0:
                return False, (r2.stderr or r2.stdout or "Error al deshabilitar").strip()
            # Samba: tambien nmbd si paramos smbd
            if clave == "smbd":
                for extra in ("nmbd.service",):
                    if _unidad_activa(extra):
                        sudo_run(
                            ["systemctl", "stop", "--", extra],
                            f"Parar {extra}",
                            parent=self.root,
                            timeout=40,
                        )
                        sudo_run(
                            ["systemctl", "disable", "--", extra],
                            f"Deshabilitar {extra}",
                            parent=self.root,
                            timeout=40,
                        )
            registrar(f"Desactivar {unidad}", "ok", True)
            return True, f"{unidad} parado y deshabilitado."

        def al_terminar(resultado):
            self._set_ocupado(False)
            ok, mensaje = resultado
            if ok:
                messagebox.showinfo("Centro De Seguridad", mensaje, parent=self.root)
                self.cargar()
            else:
                messagebox.showerror("Centro De Seguridad", mensaje, parent=self.root)
                self.lbl_estado.config(text=mensaje, fg=_COLORES["error"])

        en_hilo(self.root, trabajo, al_terminar=al_terminar)
