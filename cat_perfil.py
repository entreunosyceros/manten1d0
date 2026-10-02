"""
Este módulo proporciona una interfaz gráfica para modificar el perfil de usuario en un sistema operativo basado en Unix/Linux.

Módulos Importados:
- tkinter: Proporciona la funcionalidad para crear la interfaz gráfica de usuario.
- messagebox: Permite mostrar cuadros de mensaje.
- filedialog: Permite al usuario seleccionar archivos.
- simpledialog: Permite solicitar la entrada del usuario a través de cuadros de diálogo.
- PIL (Pillow): Proporciona herramientas para trabajar con imágenes.
- os: Proporciona una forma de usar funcionalidades dependientes del sistema operativo.
- subprocess: Permite ejecutar comandos del sistema operativo y capturar su salida.
- getpass: Proporciona una manera de manejar entradas sensibles como contraseñas.
- password: Contiene funciones para limpiar archivos de configuración y obtener contraseñas de sudo.
- tooltip: Proporciona una clase para mostrar tooltips en widgets de tkinter.
"""

import grp
import os
import pwd
import re
import shutil
import tkinter as tk
from datetime import date, datetime
from subprocess import Popen, PIPE
import subprocess
import getpass
from tkinter import messagebox, filedialog, ttk
from PIL import Image, ImageTk

from password import limpiar_archivos_configuracion, obtener_contrasena
from registro import confirmar, en_hilo, registrar
from tooltip import ToolTip
import preferencias

# Locales habituales (codigo canónico UTF-8 -> etiqueta visible)
_IDIOMAS_CONOCIDOS = (
    ("es_ES.UTF-8", "Español"),
    ("en_US.UTF-8", "English (US)"),
    ("en_GB.UTF-8", "English (UK)"),
    ("gl_ES.UTF-8", "Galego"),
    ("ca_ES.UTF-8", "Catala"),
    ("eu_ES.UTF-8", "Euskara"),
    ("pt_PT.UTF-8", "Portugues"),
    ("pt_BR.UTF-8", "Portugues (Brasil)"),
    ("fr_FR.UTF-8", "Francais"),
    ("de_DE.UTF-8", "Deutsch"),
    ("it_IT.UTF-8", "Italiano"),
)


def _normalizar_locale(codigo):
    """es_ES / es_ES.utf8 / es_ES.UTF-8 -> es_ES.UTF-8 si es posible."""
    if not codigo:
        return ""
    codigo = codigo.strip().strip('"').strip("'")
    if not codigo:
        return ""
    codigo = codigo.replace("-", ".")
    # Quitar variantes tipo LANGUAGE=es:en
    if ":" in codigo:
        codigo = codigo.split(":", 1)[0]
    base = codigo.split(".")[0]
    if "." in codigo:
        return f"{base}.UTF-8"
    return f"{base}.UTF-8" if "_" in base else codigo


def _clave_locale(codigo):
    """Clave comparable: es_es."""
    codigo = _normalizar_locale(codigo)
    if not codigo:
        return ""
    return codigo.split(".")[0].lower()


def _locales_instalados():
    """Conjunto de claves instaladas (es_es, en_us, ...)."""
    proceso = subprocess.run(
        ["locale", "-a"],
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "LC_ALL": "C"},
    )
    claves = set()
    for linea in (proceso.stdout or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        clave = linea.split(".")[0].lower().replace("-", "_")
        if "_" in clave:
            claves.add(clave)
    return claves


def _etiqueta_idioma(codigo):
    clave = _clave_locale(codigo)
    for canon, etiqueta in _IDIOMAS_CONOCIDOS:
        if _clave_locale(canon) == clave:
            return etiqueta
    if not codigo:
        return "Desconocido"
    return codigo.split(".")[0]


def _leer_lang_archivo(ruta):
    try:
        with open(ruta, encoding="utf-8") as archivo:
            for linea in archivo:
                linea = linea.strip()
                if linea.startswith("LANG="):
                    return linea.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def _idioma_sesion():
    """Idioma de la sesion actual (LANG / AccountsService / entorno)."""
    for clave in ("LC_ALL", "LC_MESSAGES", "LANG"):
        valor = (os.environ.get(clave) or "").strip()
        if valor:
            return _normalizar_locale(valor)
    # AccountsService Language (sin .UTF-8 a veces)
    try:
        uid = os.getuid()
        entorno = os.environ.copy()
        if "DBUS_SYSTEM_BUS_ADDRESS" not in entorno and os.path.exists("/var/run/dbus/system_bus_socket"):
            entorno["DBUS_SYSTEM_BUS_ADDRESS"] = "unix:path=/var/run/dbus/system_bus_socket"
        proceso = subprocess.run(
            [
                "gdbus", "call", "--system",
                "--dest", "org.freedesktop.Accounts",
                "--object-path", f"/org/freedesktop/Accounts/User{uid}",
                "--method", "org.freedesktop.DBus.Properties.Get",
                "org.freedesktop.Accounts.User", "Language",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env=entorno,
        )
        m = re.search(r"<'([^']*)'>", proceso.stdout or "")
        if m and m.group(1):
            return _normalizar_locale(m.group(1))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _idioma_sistema():
    """Idioma por defecto del sistema (/etc/default/locale)."""
    for ruta in ("/etc/default/locale", "/etc/locale.conf"):
        valor = _leer_lang_archivo(ruta)
        if valor:
            return _normalizar_locale(valor)
    try:
        proceso = subprocess.run(
            ["localectl", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        )
        m = re.search(r"System Locale:\s*LANG=(\S+)", proceso.stdout or "")
        if m:
            return _normalizar_locale(m.group(1))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def idiomas_disponibles():
    """Lista (codigo UTF-8, etiqueta) de idiomas conocidos e instalados."""
    instalados = _locales_instalados()
    disponibles = []
    for codigo, etiqueta in _IDIOMAS_CONOCIDOS:
        if _clave_locale(codigo) in instalados:
            disponibles.append((codigo, etiqueta))
    return disponibles


def aplicar_idioma_sesion(codigo_utf8):
    """
    Configura el idioma de la proxima sesion del usuario.
    Devuelve (ok, mensaje). No cambia la sesion actual.
    """
    codigo = _normalizar_locale(codigo_utf8)
    if not codigo:
        return False, "Indica un idioma valido."
    if _clave_locale(codigo) not in _locales_instalados():
        return False, (
            f"El idioma {codigo} no esta instalado en el sistema. "
            "Instala el paquete de idioma correspondiente e intentalo de nuevo."
        )

    base = codigo.split(".")[0]  # es_ES
    errores = []

    # 1) AccountsService (GNOME / pantalla de login)
    try:
        uid = os.getuid()
        entorno = os.environ.copy()
        if "DBUS_SYSTEM_BUS_ADDRESS" not in entorno and os.path.exists("/var/run/dbus/system_bus_socket"):
            entorno["DBUS_SYSTEM_BUS_ADDRESS"] = "unix:path=/var/run/dbus/system_bus_socket"
        proceso = subprocess.run(
            [
                "gdbus", "call", "--system",
                "--dest", "org.freedesktop.Accounts",
                "--object-path", f"/org/freedesktop/Accounts/User{uid}",
                "--method", "org.freedesktop.Accounts.User.SetLanguage",
                base,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env=entorno,
        )
        if proceso.returncode != 0:
            errores.append((proceso.stderr or proceso.stdout or "AccountsService").strip()[:200])
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        errores.append(str(error))

    # 2) locale.conf de usuario (systemd / algunos escritorios)
    try:
        config_dir = os.path.expanduser("~/.config")
        os.makedirs(config_dir, exist_ok=True)
        ruta = os.path.join(config_dir, "locale.conf")
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(f"LANG={codigo}\n")
            archivo.write(f"LANGUAGE={base.split('_')[0]}\n")
    except OSError as error:
        errores.append(f"locale.conf: {error}")

    # 3) .pam_environment (sesiones clasicas)
    try:
        ruta_pam = os.path.expanduser("~/.pam_environment")
        lineas = []
        if os.path.isfile(ruta_pam):
            with open(ruta_pam, encoding="utf-8") as archivo:
                lineas = [linea for linea in archivo if not linea.startswith(("LANG=", "LANGUAGE=", "LC_MESSAGES="))]
        lineas.append(f"LANG={codigo}\n")
        lineas.append(f"LANGUAGE={base.split('_')[0]}\n")
        with open(ruta_pam, "w", encoding="utf-8") as archivo:
            archivo.writelines(lineas)
    except OSError as error:
        errores.append(f"pam_environment: {error}")

    registrar("Cambiar idioma de sesion", codigo, True)
    if errores and not os.path.isfile(os.path.expanduser("~/.config/locale.conf")):
        return False, "No se pudo guardar el idioma: " + "; ".join(errores)[:300]
    return True, (
        f"Idioma configurado: {_etiqueta_idioma(codigo)}.\n"
        "Se aplicara al iniciar la proxima sesion."
    )


_PAISES = {
    "ES": "España",
    "US": "Estados Unidos",
    "GB": "Reino Unido",
    "MX": "Mexico",
    "AR": "Argentina",
    "CO": "Colombia",
    "CL": "Chile",
    "PE": "Peru",
    "UY": "Uruguay",
    "VE": "Venezuela",
    "PT": "Portugal",
    "BR": "Brasil",
    "FR": "Francia",
    "DE": "Alemania",
    "IT": "Italia",
    "CA": "Canada",
}


def _gsettings_get(esquema, clave):
    try:
        proceso = subprocess.run(
            ["gsettings", "get", esquema, clave],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proceso.returncode != 0:
            return None
        return (proceso.stdout or "").strip().strip("'")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def datos_regionales():
    """Preferencias regionales del usuario (lectura; no modifica nada)."""
    import datetime
    import locale as locale_mod

    idioma = _idioma_sesion() or _idioma_sistema()
    region_gsettings = _gsettings_get("org.gnome.system.locale", "region") or ""
    locale_formatos = _normalizar_locale(region_gsettings) if region_gsettings else idioma

    pais = "-"
    clave = _clave_locale(locale_formatos or idioma)
    if "_" in clave:
        codigo_pais = clave.split("_", 1)[1].upper()
        pais = _PAISES.get(codigo_pais, codigo_pais)

    # Locale para formatos (no tocar el de la app entera si falla)
    loc_prev = None
    try:
        loc_prev = locale_mod.setlocale(locale_mod.LC_ALL)
    except locale_mod.Error:
        loc_prev = None
    conv = {}
    fecha = "-"
    try:
        for candidato in (locale_formatos, idioma, ""):
            if candidato is None:
                continue
            try:
                if candidato:
                    locale_mod.setlocale(locale_mod.LC_ALL, candidato)
                else:
                    locale_mod.setlocale(locale_mod.LC_ALL, "")
                break
            except locale_mod.Error:
                continue
        conv = locale_mod.localeconv() or {}
        hoy = datetime.date.today()
        # Preferir dia/mes/ano completo (mas claro que %x a 2 digitos)
        try:
            fecha = hoy.strftime("%d/%m/%Y")
            # Si el locale no es dia-mes, usar %x
            if locale_formatos and not _clave_locale(locale_formatos).startswith(("es_", "gl_", "ca_", "pt_", "eu_", "it_", "fr_", "de_")):
                if _clave_locale(locale_formatos).startswith(("en_us",)):
                    fecha = hoy.strftime("%m/%d/%Y")
                elif _clave_locale(locale_formatos).startswith("en_"):
                    fecha = hoy.strftime("%d/%m/%Y")
        except ValueError:
            fecha = hoy.isoformat()
    except Exception:
        conv = {}
        fecha = datetime.date.today().strftime("%d/%m/%Y")
    finally:
        if loc_prev is not None:
            try:
                locale_mod.setlocale(locale_mod.LC_ALL, loc_prev)
            except locale_mod.Error:
                pass

    decimal = conv.get("decimal_point") or ","
    moneda = (conv.get("currency_symbol") or "").strip()
    if not moneda:
        intl = (conv.get("int_curr_symbol") or "").strip()
        if intl.startswith("EUR"):
            moneda = "€"
        elif intl:
            moneda = intl
        else:
            moneda = "-"

    reloj = _gsettings_get("org.gnome.desktop.interface", "clock-format")
    if reloj == "12h":
        formato_horario = "12 horas"
    elif reloj == "24h":
        formato_horario = "24 horas"
    else:
        formato_horario = "24 horas"  # es_ES habitual

    zona = "-"
    try:
        proceso = subprocess.run(
            ["timedatectl", "show", "-p", "Timezone", "--value"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proceso.returncode == 0 and (proceso.stdout or "").strip():
            zona = proceso.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    if zona == "-":
        try:
            from cat_informacion import Informacion
            zona = Informacion.get_zona_horaria() or "-"
        except Exception:
            pass

    return {
        "pais": pais,
        "idioma": _etiqueta_idioma(idioma) if idioma else "Desconocido",
        "fecha": fecha,
        "horario": formato_horario,
        "decimal": decimal,
        "moneda": moneda,
        "zona": zona,
        "locale_formatos": locale_formatos or idioma or "",
    }


def abrir_ajustes_regionales():
    """Abre el panel de region/idioma de Ubuntu (GNOME) si esta disponible."""
    comandos = (
        ["gnome-control-center", "system", "region"],
        ["gnome-control-center", "region"],
        ["gnome-language-selector"],
    )
    for args in comandos:
        if not shutil.which(args[0]):
            continue
        try:
            subprocess.Popen(args, start_new_session=True)
            return True, None
        except OSError as error:
            ultimo = str(error)
            continue
    return False, "No se encontro la configuracion regional de Ubuntu (gnome-control-center)."


def datos_perfil_actual():
    """Obtiene los datos visibles del usuario actual sin pedir sudo."""
    usuario = getpass.getuser()
    datos = {
        "usuario": usuario,
        "nombre": usuario,
        "uid": "",
        "home": os.path.expanduser("~"),
        "shell": "",
        "grupos": "",
        "imagen": None,
    }
    try:
        cuenta = pwd.getpwnam(usuario)
    except KeyError:
        return datos

    nombre = (cuenta.pw_gecos.split(",")[0] or "").strip()
    datos["nombre"] = nombre or usuario
    datos["uid"] = str(cuenta.pw_uid)
    datos["home"] = cuenta.pw_dir
    datos["shell"] = cuenta.pw_shell

    grupos = set()
    try:
        grupos.add(grp.getgrgid(cuenta.pw_gid).gr_name)
    except KeyError:
        pass
    for grupo in grp.getgrall():
        if usuario in grupo.gr_mem:
            grupos.add(grupo.gr_name)
    datos["grupos"] = ", ".join(sorted(grupos))

    candidatos = [
        os.path.join(cuenta.pw_dir, ".face"),
        os.path.join(cuenta.pw_dir, ".face.icon"),
        f"/var/lib/AccountsService/icons/{usuario}",
    ]
    accounts = f"/var/lib/AccountsService/users/{usuario}"
    if os.access(accounts, os.R_OK):
        try:
            with open(accounts, encoding="utf-8") as archivo:
                for linea in archivo:
                    if linea.startswith("Icon="):
                        ruta_icono = linea.split("=", 1)[1].strip()
                        if ruta_icono:
                            candidatos.insert(0, ruta_icono)
                        break
        except OSError:
            pass

    for ruta in candidatos:
        if ruta and os.path.isfile(ruta) and os.access(ruta, os.R_OK):
            datos["imagen"] = ruta
            break
    return datos


def _foto_perfil(ruta, tamano=(120, 120)):
    imagen = Image.open(ruta)
    imagen.thumbnail(tamano)
    return ImageTk.PhotoImage(imagen)


def evaluar_fuerza_contrasena(clave):
    """Checklist y etiqueta de fuerza para una contraseña nueva (solo orientativo)."""
    clave = clave or ""
    checks = (
        ("8 caracteres", len(clave) >= 8),
        ("Mayusculas", any(c.isupper() for c in clave)),
        ("Minusculas", any(c.islower() for c in clave)),
        ("Numeros", any(c.isdigit() for c in clave)),
        ("Simbolo recomendado", any(not c.isalnum() for c in clave)),
    )
    puntos = sum(1 for _et, ok in checks if ok)
    if not clave:
        return {
            "checks": checks,
            "puntos": 0,
            "etiqueta": "",
            "color": "#7f8c8d",
            "relleno": 0.0,
        }
    if puntos <= 2:
        etiqueta, color = "Debil", "#c0392b"
    elif puntos == 3:
        etiqueta, color = "Aceptable", "#e67e22"
    elif puntos == 4:
        etiqueta, color = "Buena", "#27ae60"
    else:
        etiqueta, color = "Fuerte", "#1e8449"
    return {
        "checks": checks,
        "puntos": puntos,
        "etiqueta": etiqueta,
        "color": color,
        "relleno": puntos / 5.0,
    }


def estado_contrasena(usuario=None):
    """Estado de la contraseña de login (passwd -S) y caducidad si el sistema la usa."""
    usuario = usuario or getpass.getuser()
    datos = {
        "usuario": usuario,
        "codigo": "",
        "estado": "No se pudo comprobar",
        "ok": False,
        "ultimo_cambio": None,
        "ultimo_texto": "Desconocido",
        "caducidad": None,
        "detalle": "No se pudo leer passwd -S.",
    }
    try:
        proceso = subprocess.run(
            ["passwd", "-S", "--", usuario],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        datos["detalle"] = str(error)
        return datos

    texto = (proceso.stdout or "").strip()
    if not texto:
        return datos
    partes = texto.split()
    if len(partes) < 2:
        return datos

    codigo = partes[1].upper()
    datos["codigo"] = codigo
    if codigo == "NP":
        datos["estado"] = "Sin contraseña"
        datos["ok"] = False
        datos["detalle"] = "La cuenta no tiene contraseña."
    elif codigo == "L":
        datos["estado"] = "Bloqueada"
        datos["ok"] = False
        datos["detalle"] = "La cuenta esta bloqueada."
    elif codigo.startswith("P"):
        datos["estado"] = "Correcta"
        datos["ok"] = True
        datos["detalle"] = "La cuenta tiene contraseña."
    else:
        datos["estado"] = codigo
        datos["detalle"] = f"Estado del sistema: {codigo}."

    if len(partes) >= 3:
        try:
            ultimo = datetime.strptime(partes[2], "%Y-%m-%d").date()
            datos["ultimo_cambio"] = ultimo
            dias = (date.today() - ultimo).days
            if dias <= 0:
                datos["ultimo_texto"] = "hoy"
            elif dias == 1:
                datos["ultimo_texto"] = "hace 1 dia"
            else:
                datos["ultimo_texto"] = f"hace {dias} dias"
        except ValueError:
            datos["ultimo_texto"] = partes[2]

    # Caducidad solo si hay politica real (max distinto de 99999 / -1)
    max_dias = None
    if len(partes) >= 5:
        try:
            max_dias = int(partes[4])
        except ValueError:
            max_dias = None
    if max_dias is not None and 0 < max_dias < 99999 and datos["ultimo_cambio"]:
        try:
            caduca = datos["ultimo_cambio"].toordinal() + max_dias
            fecha_caduca = date.fromordinal(caduca)
            quedan = (fecha_caduca - date.today()).days
            if quedan < 0:
                datos["caducidad"] = f"Caduco el {fecha_caduca.isoformat()}"
            elif quedan == 0:
                datos["caducidad"] = "Caduca hoy"
            else:
                datos["caducidad"] = (
                    f"Caduca el {fecha_caduca.isoformat()} (en {quedan} dias)"
                )
        except (OverflowError, ValueError):
            pass
    return datos


_CATEGORIAS_APP = (
    {
        "clave": "navegador",
        "etiqueta": "Navegador web",
        "mimes": (
            "x-scheme-handler/http",
            "x-scheme-handler/https",
            "text/html",
        ),
        "xdg_settings": "default-web-browser",
        "cats_desktop": ("WebBrowser",),
    },
    {
        "clave": "correo",
        "etiqueta": "Cliente de correo",
        "mimes": ("x-scheme-handler/mailto",),
        "xdg_settings": None,
        "cats_desktop": ("Email", "EmailClient"),
    },
    {
        "clave": "imagenes",
        "etiqueta": "Visor de imagenes",
        "mimes": ("image/jpeg", "image/png", "image/webp"),
        "xdg_settings": None,
        "cats_desktop": ("Viewer", "Graphics", "Photography", "2DGraphics"),
    },
    {
        "clave": "video",
        "etiqueta": "Reproductor de video",
        "mimes": ("video/mp4", "video/x-matroska", "video/webm"),
        "xdg_settings": None,
        "cats_desktop": ("Player", "AudioVideo", "Video"),
    },
    {
        "clave": "texto",
        "etiqueta": "Editor de texto",
        "mimes": ("text/plain",),
        "xdg_settings": None,
        "cats_desktop": ("TextEditor",),
    },
)

_CARPETAS_XDG = (
    ("Documentos", "DOCUMENTS", "Documentos"),
    ("Descargas", "DOWNLOAD", "Descargas"),
    ("Musica", "MUSIC", "Música"),
    ("Imagenes", "PICTURES", "Imágenes"),
    ("Videos", "VIDEOS", "Vídeos"),
    ("Escritorio", "DESKTOP", "Escritorio"),
)

_MIMES_GESTIONADOS = tuple(
    mime for cat in _CATEGORIAS_APP for mime in cat["mimes"]
) + (
    "x-scheme-handler/about",
    "x-scheme-handler/unknown",
)


def _directorios_applications():
    vistos = []
    candidatos = [
        os.path.join(os.path.expanduser("~"), ".local", "share", "applications"),
        os.path.join(os.path.expanduser("~"), ".local", "share", "flatpak", "exports", "share", "applications"),
        "/var/lib/flatpak/exports/share/applications",
        "/var/lib/snapd/desktop/applications",
        "/usr/local/share/applications",
        "/usr/share/applications",
    ]
    for base in (os.environ.get("XDG_DATA_DIRS") or "").split(":"):
        if base:
            candidatos.append(os.path.join(base, "applications"))
    for ruta in candidatos:
        if ruta and os.path.isdir(ruta) and ruta not in vistos:
            vistos.append(ruta)
    return vistos


def _encontrar_desktop(desktop_id):
    if not desktop_id or not desktop_id.endswith(".desktop"):
        return None
    for carpeta in _directorios_applications():
        directa = os.path.join(carpeta, desktop_id)
        if os.path.isfile(directa):
            return directa
        for raiz, _dirs, archivos in os.walk(carpeta):
            if desktop_id in archivos:
                return os.path.join(raiz, desktop_id)
    return None


def _info_desktop(desktop_id):
    ruta = _encontrar_desktop(desktop_id)
    nombre = desktop_id.replace(".desktop", "") if desktop_id else ""
    oculto = False
    categorias = ()
    if not ruta:
        return {
            "id": desktop_id,
            "nombre": nombre,
            "oculto": True,
            "ruta": None,
            "categorias": categorias,
        }
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fichero:
            lineas = fichero.readlines()
    except OSError:
        return {
            "id": desktop_id,
            "nombre": nombre,
            "oculto": True,
            "ruta": ruta,
            "categorias": categorias,
        }
    nombre_es = None
    nombre_base = None
    en_entrada = False
    for linea in lineas:
        strip = linea.strip()
        if strip.startswith("[") and strip.endswith("]"):
            en_entrada = strip.lower() == "[desktop entry]"
            continue
        if not en_entrada:
            continue
        if strip.startswith("Name[es]=") or strip.startswith("Name[es_ES]="):
            nombre_es = strip.split("=", 1)[1].strip()
        elif strip.startswith("Name=") and nombre_base is None:
            nombre_base = strip.split("=", 1)[1].strip()
        elif strip.startswith("Categories="):
            categorias = tuple(
                c for c in strip.split("=", 1)[1].strip().split(";") if c
            )
        elif strip.startswith("NoDisplay="):
            oculto = strip.split("=", 1)[1].strip().lower() in ("true", "1", "yes")
        elif strip.startswith("Hidden="):
            if strip.split("=", 1)[1].strip().lower() in ("true", "1", "yes"):
                oculto = True
    return {
        "id": desktop_id,
        "nombre": nombre_es or nombre_base or nombre,
        "oculto": oculto,
        "ruta": ruta,
        "categorias": categorias,
    }


def _gio_apps_para_mime(mime):
    """Devuelve (actual, lista_ids) segun gio mime (LC_ALL=C)."""
    try:
        proceso = subprocess.run(
            ["gio", "mime", mime],
            capture_output=True,
            text=True,
            timeout=8,
            env={**os.environ, "LC_ALL": "C", "LANGUAGE": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return "", []
    actual = ""
    ids = []
    seccion = None
    for linea in (proceso.stdout or "").splitlines():
        baja = linea.strip()
        if not baja:
            continue
        baja_l = baja.lower()
        if baja_l.startswith("default application for"):
            if ":" in baja:
                actual = baja.rsplit(":", 1)[-1].strip()
            continue
        if baja_l.startswith("registered applications"):
            seccion = "reg"
            continue
        if baja_l.startswith("recommended applications"):
            seccion = "rec"
            continue
        if baja.endswith(".desktop") and " " not in baja.split()[-1]:
            desktop_id = baja.split()[-1] if " " in baja else baja
            desktop_id = desktop_id.lstrip("\t ")
            # Preferir recomendadas; si no hay, usar registradas
            ids.append((seccion or "reg", desktop_id))
    recomendadas = [d for s, d in ids if s == "rec"]
    registradas = [d for s, d in ids if s == "reg"]
    orden = recomendadas if recomendadas else registradas
    vistos = set()
    unicos = []
    for desktop_id in orden:
        if desktop_id not in vistos:
            vistos.add(desktop_id)
            unicos.append(desktop_id)
    # Si hay recomendadas, añadir registradas utiles que falten (p. ej. VLC)
    if recomendadas:
        for desktop_id in registradas:
            if desktop_id not in vistos:
                vistos.add(desktop_id)
                unicos.append(desktop_id)
    if not actual:
        try:
            proc = subprocess.run(
                ["xdg-mime", "query", "default", mime],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "LC_ALL": "C"},
            )
            actual = (proc.stdout or "").strip()
        except (OSError, subprocess.TimeoutExpired):
            actual = ""
    return actual, unicos


def _apps_descartables(desktop_id):
    baja = (desktop_id or "").lower()
    return any(
        trozo in baja
        for trozo in (
            "daemon",
            "oauth",
            "url-handler",
            "software-properties",
            "gnome-mime",
        )
    )


def listar_apps_categoria(categoria):
    """Apps candidatas y actual para una categoria de _CATEGORIAS_APP."""
    mime_principal = categoria["mimes"][0]
    actual, ids = _gio_apps_para_mime(mime_principal)
    if categoria.get("xdg_settings") == "default-web-browser":
        try:
            proc = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            obtenido = (proc.stdout or "").strip()
            if obtenido:
                actual = obtenido
        except (OSError, subprocess.TimeoutExpired):
            pass
    filtro = set(categoria.get("cats_desktop") or ())
    candidatas = []
    vistos = set()
    for desktop_id in ids:
        if desktop_id in vistos or _apps_descartables(desktop_id):
            continue
        info = _info_desktop(desktop_id)
        if info["oculto"] and desktop_id != actual:
            continue
        if not info["ruta"] and desktop_id != actual:
            continue
        if not info["nombre"]:
            continue
        vistos.add(desktop_id)
        candidatas.append(info)

    def _pasa_filtro(info):
        if not filtro:
            return True
        if info["id"] == actual:
            return True
        cats = set(info.get("categorias") or ())
        return bool(cats & filtro)

    apps = [a for a in candidatas if _pasa_filtro(a)]
    # Si el filtro deja la lista demasiado vacia, mostrar todas las candidatas
    if len(apps) < 1:
        apps = list(candidatas)
    if actual and actual not in {a["id"] for a in apps}:
        apps.insert(0, _info_desktop(actual))
    apps.sort(key=lambda a: a["nombre"].lower())
    return actual, apps


def aplicar_app_predeterminada(categoria, desktop_id):
    """Asigna la app como predeterminada para los MIME de la categoria."""
    if not desktop_id or not desktop_id.endswith(".desktop"):
        return False, "Aplicacion no valida."
    errores = []
    for mime in categoria["mimes"]:
        try:
            proc = subprocess.run(
                ["xdg-mime", "default", desktop_id, mime],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                errores.append((mime, (proc.stderr or proc.stdout or "").strip()))
        except (OSError, subprocess.TimeoutExpired) as error:
            errores.append((mime, str(error)))
    if categoria.get("xdg_settings"):
        try:
            proc = subprocess.run(
                ["xdg-settings", "set", categoria["xdg_settings"], desktop_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                errores.append(
                    (categoria["xdg_settings"], (proc.stderr or proc.stdout or "").strip())
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            errores.append((categoria["xdg_settings"], str(error)))
    if errores and len(errores) == len(categoria["mimes"]) + (
        1 if categoria.get("xdg_settings") else 0
    ):
        return False, "No se pudo aplicar:\n" + "\n".join(f"{k}: {v}" for k, v in errores)
    nombre = _info_desktop(desktop_id)["nombre"]
    registrar(
        "Aplicacion predeterminada",
        f"{categoria['etiqueta']}: {nombre}",
        True,
    )
    return True, f"{categoria['etiqueta']}: {nombre}"


def restaurar_apps_predeterminadas():
    """Quita personalizaciones de ~/.config/mimeapps.list para las categorias gestionadas."""
    ruta = os.path.join(os.path.expanduser("~"), ".config", "mimeapps.list")
    if not os.path.isfile(ruta):
        return True, "No habia aplicaciones personalizadas que restaurar."
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fichero:
            lineas = fichero.readlines()
    except OSError as error:
        return False, str(error)

    seccion = None
    nuevas = []
    quitadas = 0
    for linea in lineas:
        strip = linea.strip()
        if strip.startswith("[") and strip.endswith("]"):
            seccion = strip.lower()
            nuevas.append(linea)
            continue
        if seccion == "[default applications]" and "=" in strip and not strip.startswith("#"):
            mime = strip.split("=", 1)[0].strip()
            if mime in _MIMES_GESTIONADOS:
                quitadas += 1
                continue
        nuevas.append(linea)

    if quitadas == 0:
        return True, "No habia valores personalizados en esas categorias."

    try:
        with open(ruta, "w", encoding="utf-8") as fichero:
            fichero.writelines(nuevas)
    except OSError as error:
        return False, str(error)
    registrar("Restaurar apps predeterminadas", f"Quitadas {quitadas} entradas", True)
    return True, f"Restaurados {quitadas} valores del sistema."


def carpetas_personales_xdg():
    """Rutas XDG de Documentos, Descargas, etc. (solo lectura)."""
    filas = []
    for etiqueta, clave, respaldo in _CARPETAS_XDG:
        ruta = ""
        try:
            proc = subprocess.run(
                ["xdg-user-dir", clave],
                capture_output=True,
                text=True,
                timeout=5,
            )
            ruta = (proc.stdout or "").strip()
        except (OSError, subprocess.TimeoutExpired):
            ruta = ""
        if not ruta or not os.path.isdir(ruta):
            candidata = os.path.join(os.path.expanduser("~"), respaldo)
            if not os.path.isdir(candidata):
                candidata = os.path.join(os.path.expanduser("~"), etiqueta)
            ruta = candidata if os.path.isdir(candidata) else (ruta or candidata)
        filas.append({"etiqueta": etiqueta, "ruta": ruta, "existe": os.path.isdir(ruta)})
    return filas


def resumen_carpeta_personal(home=None):
    """Ocupacion de la carpeta personal: total, libre en disco y desglose tipico."""
    from cat_sistema_extra import _formato_tamano, _tamano_ruta

    home = home or os.path.expanduser("~")
    grupos = (
        ("Documentos", ("Documentos", "Documents")),
        ("Descargas", ("Descargas", "Downloads")),
        ("Videos", ("Videos", "Vídeos")),
        ("Imagenes", ("Imagenes", "Imágenes", "Pictures")),
        ("Musica", ("Musica", "Música", "Music")),
        ("Cache", (".cache",)),
        ("Papelera", (".local/share/Trash",)),
    )
    filas = []
    sumado = 0
    for etiqueta, nombres in grupos:
        tamano = 0
        for nombre in nombres:
            ruta = os.path.join(home, nombre)
            if os.path.exists(ruta):
                tamano += _tamano_ruta(ruta, solo_volumen=True)
        if tamano > 0:
            filas.append((etiqueta, tamano))
            sumado += tamano
    ocupado = _tamano_ruta(home, solo_volumen=True)
    otros = max(0, ocupado - sumado)
    if otros > 0:
        filas.append(("Otros", otros))
    filas.sort(key=lambda par: par[1], reverse=True)
    try:
        libre = shutil.disk_usage(home).free
    except OSError:
        libre = 0
    return {
        "home": home,
        "ocupado": ocupado,
        "libre": libre,
        "filas": filas,
        "texto_ocupado": _formato_tamano(ocupado),
        "texto_libre": _formato_tamano(libre),
        "filas_texto": [(et, _formato_tamano(n)) for et, n in filas],
    }


def crear_panel_perfil(parent, fondo=None):
    """Muestra datos utiles del perfil y el idioma de la sesion."""
    if fondo is None:
        fondo = preferencias.color_fondo()
    datos = datos_perfil_actual()
    marco = tk.Frame(parent, bg=fondo)
    raiz = parent.winfo_toplevel()

    tarjeta = tk.Frame(marco, bg=fondo)
    tarjeta.pack(pady=8)

    columna_foto = tk.Frame(tarjeta, bg=fondo)
    columna_foto.pack(side=tk.LEFT, padx=(0, 16), anchor="n")
    etiqueta_foto = tk.Label(columna_foto, bg=fondo)
    etiqueta_foto.pack()
    foto = None
    if datos["imagen"]:
        try:
            foto = _foto_perfil(datos["imagen"])
            etiqueta_foto.configure(image=foto)
            etiqueta_foto.image = foto
        except OSError:
            etiqueta_foto.configure(text="Sin imagen")
    else:
        etiqueta_foto.configure(text="Sin imagen de perfil", font=("Arial", 9))

    columna_datos = tk.Frame(tarjeta, bg=fondo)
    columna_datos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    idioma_sesion = _idioma_sesion()
    filas = (
        ("Usuario", datos["usuario"]),
        ("Nombre visible", datos["nombre"]),
    )
    for etiqueta, valor in filas:
        fila = tk.Frame(columna_datos, bg=fondo)
        fila.pack(fill=tk.X, pady=2)
        tk.Label(
            fila,
            text=f"{etiqueta}:",
            width=18,
            anchor="e",
            bg=fondo,
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            fila,
            text=valor or "-",
            anchor="w",
            bg=fondo,
            wraplength=360,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, padx=8)

    # --- Mi carpeta personal ---
    marco_home = tk.LabelFrame(
        marco,
        text="Mi carpeta personal",
        bg=fondo,
        padx=10,
        pady=8,
    )
    marco_home.pack(fill=tk.X, pady=(12, 4), padx=4)
    tk.Label(
        marco_home,
        text=datos["home"] or "-",
        bg=fondo,
        font=("Arial", 10, "bold"),
        anchor="w",
        justify=tk.LEFT,
        wraplength=520,
    ).pack(anchor="w")

    def abrir_carpeta_personal():
        ruta = datos["home"]
        if not ruta or not os.path.isdir(ruta):
            messagebox.showerror(
                "Carpeta personal",
                "No se encontro la carpeta personal.",
                parent=raiz,
            )
            return
        try:
            subprocess.Popen(["xdg-open", ruta])
        except OSError as error:
            messagebox.showerror(
                "Carpeta personal",
                f"No se pudo abrir la carpeta:\n{error}",
                parent=raiz,
            )

    def mostrar_resumen(resumen):
        lineas = [
            f"Ocupado: {resumen['texto_ocupado']}",
            f"Libre en disco: {resumen['texto_libre']}",
            "",
        ]
        ancho = max((len(et) for et, _t in resumen["filas_texto"]), default=8)
        for etiqueta, texto in resumen["filas_texto"]:
            lineas.append(f"{etiqueta.ljust(ancho)}  {texto}")
        lbl_resumen.config(text="\n".join(lineas))

    def ver_espacio():
        btn_espacio.config(state=tk.DISABLED)
        lbl_resumen.config(text="Calculando espacio... (puede tardar unos segundos)")

        def trabajo():
            return resumen_carpeta_personal(datos["home"])

        def terminar(resumen):
            btn_espacio.config(state=tk.NORMAL)
            mostrar_resumen(resumen)

        def fallar(error):
            btn_espacio.config(state=tk.NORMAL)
            lbl_resumen.config(text="No se pudo calcular el espacio.")
            messagebox.showerror(
                "Carpeta personal",
                f"No se pudo calcular el espacio:\n{error}",
                parent=raiz,
            )

        en_hilo(raiz, trabajo, al_terminar=terminar, al_error=fallar)

    def abrir_liberar_espacio():
        from cat_sistema_extra import LimpiezaEspacio

        LimpiezaEspacio(tk.Toplevel(raiz))

    fila_botones_home = tk.Frame(marco_home, bg=fondo)
    fila_botones_home.pack(anchor="w", pady=(8, 2))
    btn_abrir = tk.Button(
        fila_botones_home,
        text="Abrir carpeta",
        command=abrir_carpeta_personal,
        width=18,
    )
    btn_abrir.pack(side=tk.LEFT, padx=(0, 6))
    ToolTip(btn_abrir, "Abre tu carpeta personal en el explorador de archivos")
    btn_espacio = tk.Button(
        fila_botones_home,
        text="Ver espacio utilizado",
        command=ver_espacio,
        width=20,
    )
    btn_espacio.pack(side=tk.LEFT, padx=(0, 6))
    ToolTip(
        btn_espacio,
        "Calcula cuanto ocupan Documentos, Descargas, Videos y el resto",
    )
    btn_liberar = tk.Button(
        fila_botones_home,
        text="Liberar espacio",
        command=abrir_liberar_espacio,
        width=16,
    )
    btn_liberar.pack(side=tk.LEFT)
    ToolTip(
        btn_liberar,
        "Abre el analisis de disco y las limpiezas rapida o profunda",
    )

    resumen_frame = tk.Frame(marco_home, bg=fondo)
    resumen_frame.pack(fill=tk.X, pady=(8, 0))
    lbl_resumen = tk.Label(
        resumen_frame,
        text="Pulsa «Ver espacio utilizado» para ver cuanto ocupa cada carpeta.",
        bg=fondo,
        justify=tk.LEFT,
        wraplength=520,
        anchor="w",
    )
    lbl_resumen.pack(anchor="w")

    # --- Aplicaciones predeterminadas ---
    marco_apps = tk.LabelFrame(
        marco,
        text="Aplicaciones predeterminadas",
        bg=fondo,
        padx=10,
        pady=8,
    )
    marco_apps.pack(fill=tk.X, pady=(12, 4), padx=4)
    tk.Label(
        marco_apps,
        text="Elige con que programa se abren el navegador, el correo y otros archivos habituales.",
        bg=fondo,
        justify=tk.LEFT,
        wraplength=520,
    ).pack(anchor="w")

    combos_apps = {}
    mapas_apps = {}
    aplicando_app = {"activo": False}

    def refrescar_combos_apps():
        aplicando_app["activo"] = True
        try:
            for categoria in _CATEGORIAS_APP:
                clave = categoria["clave"]
                actual, apps = listar_apps_categoria(categoria)
                nombres = [a["nombre"] for a in apps]
                id_por_nombre = {a["nombre"]: a["id"] for a in apps}
                # Evitar colision de nombres duplicados
                if len(id_por_nombre) < len(apps):
                    nombres = []
                    id_por_nombre = {}
                    for app in apps:
                        etiqueta = app["nombre"]
                        if etiqueta in id_por_nombre:
                            etiqueta = f"{app['nombre']} ({app['id']})"
                        nombres.append(etiqueta)
                        id_por_nombre[etiqueta] = app["id"]
                mapas_apps[clave] = id_por_nombre
                combo = combos_apps[clave]
                combo["values"] = nombres
                elegido = ""
                for etiqueta, desktop_id in id_por_nombre.items():
                    if desktop_id == actual:
                        elegido = etiqueta
                        break
                if elegido:
                    combo.set(elegido)
                elif nombres:
                    combo.set(nombres[0])
                else:
                    combo.set("(ninguna detectada)")
                combo.config(state="readonly" if nombres else "disabled")
        finally:
            aplicando_app["activo"] = False

    def al_elegir_app(categoria):
        def _handler(_evento=None):
            if aplicando_app["activo"]:
                return
            clave = categoria["clave"]
            etiqueta = combos_apps[clave].get()
            desktop_id = mapas_apps.get(clave, {}).get(etiqueta)
            if not desktop_id:
                return
            ok, mensaje = aplicar_app_predeterminada(categoria, desktop_id)
            if ok:
                refrescar_combos_apps()
            else:
                messagebox.showerror("Aplicaciones", mensaje, parent=raiz)
                refrescar_combos_apps()

        return _handler

    for categoria in _CATEGORIAS_APP:
        fila = tk.Frame(marco_apps, bg=fondo)
        fila.pack(fill=tk.X, pady=3)
        tk.Label(
            fila,
            text=f"{categoria['etiqueta']}:",
            width=20,
            anchor="e",
            bg=fondo,
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT)
        combo = ttk.Combobox(fila, state="readonly", width=32)
        combo.pack(side=tk.LEFT, padx=8)
        combo.bind("<<ComboboxSelected>>", al_elegir_app(categoria))
        combos_apps[categoria["clave"]] = combo

    def restaurar_apps():
        if not confirmar(
            "Que se va a hacer?\n"
            "Se quitaran tus elecciones de navegador, correo, imagenes, "
            "video y texto en las aplicaciones predeterminadas.\n\n"
            "Por que?\n"
            "Para volver a lo que trae el sistema por defecto.\n\n"
            "Que riesgos tiene?\n"
            "Bajo: solo afecta a con que programa se abren esos tipos de archivo.\n\n"
            "Continuar?",
            raiz,
            "Restaurar aplicaciones",
        ):
            return
        ok, mensaje = restaurar_apps_predeterminadas()
        refrescar_combos_apps()
        if ok:
            messagebox.showinfo("Aplicaciones", mensaje, parent=raiz)
        else:
            messagebox.showerror("Aplicaciones", mensaje, parent=raiz)

    btn_rest_apps = tk.Button(
        marco_apps,
        text="Restaurar valores del sistema",
        command=restaurar_apps,
        width=28,
    )
    btn_rest_apps.pack(anchor="w", pady=(8, 2))
    ToolTip(
        btn_rest_apps,
        "Quita tus personalizaciones y vuelve a las apps por defecto del sistema",
    )
    refrescar_combos_apps()

    # --- Carpetas personales (solo lectura) ---
    marco_dirs = tk.LabelFrame(
        marco,
        text="Carpetas personales",
        bg=fondo,
        padx=10,
        pady=8,
    )
    marco_dirs.pack(fill=tk.X, pady=(12, 4), padx=4)
    tk.Label(
        marco_dirs,
        text="Rutas habituales de tu cuenta (solo consulta; no se cambian desde aqui).",
        bg=fondo,
        justify=tk.LEFT,
        wraplength=520,
    ).pack(anchor="w")

    lista_dirs = tk.Listbox(
        marco_dirs,
        height=6,
        activestyle="dotbox",
        exportselection=False,
        font=("DejaVu Sans Mono", 9),
    )
    lista_dirs.pack(fill=tk.X, pady=(6, 4))
    filas_dirs = carpetas_personales_xdg()
    ancho_et = max((len(f["etiqueta"]) for f in filas_dirs), default=10)
    for fila_dir in filas_dirs:
        marca = "" if fila_dir["existe"] else " (no existe)"
        lista_dirs.insert(
            tk.END,
            f"{fila_dir['etiqueta'].ljust(ancho_et)}  {fila_dir['ruta']}{marca}",
        )
    if filas_dirs:
        lista_dirs.selection_set(0)

    def abrir_carpeta_xdg():
        seleccion = lista_dirs.curselection()
        if not seleccion:
            messagebox.showinfo(
                "Carpetas personales",
                "Selecciona una carpeta de la lista.",
                parent=raiz,
            )
            return
        fila_dir = filas_dirs[seleccion[0]]
        ruta = fila_dir["ruta"]
        if not ruta or not os.path.isdir(ruta):
            messagebox.showerror(
                "Carpetas personales",
                f"No se encontro la carpeta:\n{ruta}",
                parent=raiz,
            )
            return
        try:
            subprocess.Popen(["xdg-open", ruta])
        except OSError as error:
            messagebox.showerror(
                "Carpetas personales",
                f"No se pudo abrir:\n{error}",
                parent=raiz,
            )

    lista_dirs.bind("<Double-Button-1>", lambda _e: abrir_carpeta_xdg())
    btn_abrir_dir = tk.Button(
        marco_dirs,
        text="Abrir",
        command=abrir_carpeta_xdg,
        width=12,
    )
    btn_abrir_dir.pack(anchor="w", pady=(2, 2))
    ToolTip(btn_abrir_dir, "Abre la carpeta seleccionada en el explorador")

    # --- Configuracion regional (lectura + enlace a Ubuntu) ---
    regional = datos_regionales()
    marco_region = tk.LabelFrame(
        marco,
        text="Configuracion regional",
        bg=fondo,
        padx=10,
        pady=8,
    )
    marco_region.pack(fill=tk.X, pady=(12, 4), padx=4)
    tk.Label(
        marco_region,
        text="Preferencias de formato de tu sesion. Para cambiarlas se abre la configuracion de Ubuntu.",
        bg=fondo,
        justify=tk.LEFT,
        wraplength=520,
    ).pack(anchor="w")

    filas_region = (
        ("Pais", regional["pais"]),
        ("Idioma", regional["idioma"]),
        ("Formato de fecha", regional["fecha"]),
        ("Formato horario", regional["horario"]),
        ("Separador decimal", regional["decimal"]),
        ("Moneda", regional["moneda"]),
        ("Zona horaria", regional["zona"]),
    )
    for etiqueta, valor in filas_region:
        fila = tk.Frame(marco_region, bg=fondo)
        fila.pack(fill=tk.X, pady=1)
        tk.Label(
            fila,
            text=f"{etiqueta}:",
            width=18,
            anchor="e",
            bg=fondo,
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(fila, text=valor or "-", anchor="w", bg=fondo).pack(side=tk.LEFT, padx=8)

    def abrir_region():
        ok, error = abrir_ajustes_regionales()
        if not ok:
            messagebox.showinfo(
                "Configuracion regional",
                error or "No se pudo abrir la configuracion.",
                parent=parent.winfo_toplevel(),
            )

    btn_region = tk.Button(
        marco_region,
        text="Abrir ajustes de Ubuntu",
        command=abrir_region,
        width=22,
    )
    btn_region.pack(anchor="w", pady=(8, 2))
    ToolTip(
        btn_region,
        "Abre Region e idioma de Ubuntu para cambiar formatos, zona horaria, etc.",
    )

    # --- Idioma de la interfaz ---
    marco_idioma = tk.LabelFrame(
        marco,
        text="Idioma de la interfaz",
        bg=fondo,
        padx=10,
        pady=8,
    )
    marco_idioma.pack(fill=tk.X, pady=(12, 4), padx=4)

    idioma_sistema = _idioma_sistema()
    tk.Label(
        marco_idioma,
        text=(
            f"Idioma actual: {_etiqueta_idioma(idioma_sesion) if idioma_sesion else 'Desconocido'}.  "
            f"Idioma del sistema: {_etiqueta_idioma(idioma_sistema) if idioma_sistema else 'Desconocido'}."
        ),
        bg=fondo,
        justify=tk.LEFT,
        wraplength=520,
    ).pack(anchor="w")

    disponibles = idiomas_disponibles()
    etiquetas = [et for _cod, et in disponibles]
    codigos = [cod for cod, _et in disponibles]
    var_idioma = tk.StringVar()

    fila_sel = tk.Frame(marco_idioma, bg=fondo)
    fila_sel.pack(fill=tk.X, pady=(8, 4))
    tk.Label(fila_sel, text="Idioma:", bg=fondo).pack(side=tk.LEFT)
    combo = ttk.Combobox(fila_sel, textvariable=var_idioma, values=etiquetas, state="readonly", width=28)
    combo.pack(side=tk.LEFT, padx=8)

    if disponibles:
        clave_actual = _clave_locale(idioma_sesion)
        indice = 0
        for i, codigo in enumerate(codigos):
            if _clave_locale(codigo) == clave_actual:
                indice = i
                break
        combo.current(indice)
    else:
        combo.config(state=tk.DISABLED)
        var_idioma.set("No hay idiomas instalados")

    lbl_aviso = tk.Label(
        marco_idioma,
        text="El idioma se aplicara al iniciar la proxima sesion.",
        bg=fondo,
        font=("Arial", 9),
        fg="#2471a3",
        anchor="w",
        justify=tk.LEFT,
    )
    lbl_aviso.pack(fill=tk.X, pady=(2, 6))

    def aplicar():
        if not disponibles:
            messagebox.showinfo(
                "Idioma",
                "No hay paquetes de idioma instalados para elegir.",
                parent=parent.winfo_toplevel(),
            )
            return
        indice = combo.current()
        if indice < 0 or indice >= len(codigos):
            return
        codigo = codigos[indice]
        etiqueta = etiquetas[indice]
        if not confirmar(
            "Que se va a hacer?\n"
            f"Se configurara el idioma de tu sesion a {etiqueta}.\n\n"
            "Por que?\n"
            "Para que menus y programas usen ese idioma.\n\n"
            "Que riesgos tiene?\n"
            "El cambio no es inmediato: se aplicara al cerrar sesion "
            "e iniciar de nuevo. La sesion actual sigue en el idioma de ahora.\n\n"
            "Continuar?",
            parent.winfo_toplevel(),
            "Cambiar idioma",
        ):
            return

        def trabajo():
            return aplicar_idioma_sesion(codigo)

        def terminar(resultado):
            ok, mensaje = resultado
            if ok:
                messagebox.showinfo("Idioma", mensaje, parent=parent.winfo_toplevel())
                lbl_aviso.config(
                    text=f"Pendiente: {etiqueta}. Cierra sesion para aplicarlo.",
                    fg="#1e8449",
                )
            else:
                messagebox.showerror("Idioma", mensaje, parent=parent.winfo_toplevel())

        en_hilo(parent.winfo_toplevel(), trabajo, al_terminar=terminar)

    btn = tk.Button(marco_idioma, text="Aplicar idioma", command=aplicar, width=16)
    btn.pack(anchor="w", pady=(0, 4))
    ToolTip(btn, "Guarda el idioma para la proxima sesion")
    if not disponibles:
        btn.config(state=tk.DISABLED)

    # --- Contraseña ---
    marco_pwd = tk.LabelFrame(
        marco,
        text="Contrasena",
        bg=fondo,
        padx=10,
        pady=8,
    )
    marco_pwd.pack(fill=tk.X, pady=(12, 4), padx=4)

    lbl_pwd_ultimo = tk.Label(marco_pwd, text="", bg=fondo, anchor="w", justify=tk.LEFT)
    lbl_pwd_ultimo.pack(anchor="w")
    lbl_pwd_estado = tk.Label(marco_pwd, text="", bg=fondo, anchor="w", justify=tk.LEFT)
    lbl_pwd_estado.pack(anchor="w")
    lbl_pwd_caduca = tk.Label(
        marco_pwd,
        text="",
        bg=fondo,
        anchor="w",
        justify=tk.LEFT,
        font=("Arial", 9),
        fg="#566573",
    )
    lbl_pwd_caduca.pack(anchor="w")

    def refrescar_estado_pwd():
        info = estado_contrasena(datos["usuario"])
        lbl_pwd_ultimo.config(text=f"Ultimo cambio: {info['ultimo_texto']}")
        marca = "OK" if info["ok"] else "AVISO"
        color = "#1e8449" if info["ok"] else "#c0392b"
        lbl_pwd_estado.config(
            text=f"Estado: [{marca}] {info['estado']}",
            fg=color,
        )
        if info.get("caducidad"):
            lbl_pwd_caduca.config(text=info["caducidad"])
        else:
            lbl_pwd_caduca.config(text="")

    def abrir_cambio_pwd():
        CambiarContrasena(tk.Toplevel(raiz), al_cerrar=refrescar_estado_pwd)

    btn_pwd = tk.Button(
        marco_pwd,
        text="Cambiar contrasena",
        command=abrir_cambio_pwd,
        width=20,
    )
    btn_pwd.pack(anchor="w", pady=(8, 2))
    ToolTip(
        btn_pwd,
        "Cambia la contraseña de inicio de sesion con indicador de seguridad",
    )
    refrescar_estado_pwd()

    tk.Label(
        marco,
        text="Tambien puedes modificar el nombre visible y la imagen de perfil.",
        bg=fondo,
        font=("Arial", 9),
        justify=tk.CENTER,
    ).pack(pady=(8, 0))
    return marco, foto


class CambiarContrasena:
    """Dialogo para cambiar la contraseña de login con indicador de fuerza."""

    def __init__(self, root, al_cerrar=None):
        self.root = root
        self.al_cerrar = al_cerrar
        self.root.title("Cambiar contrasena")
        self.root.geometry("440x520")
        self.root.minsize(400, 480)
        self.usuario = getpass.getuser()
        self._visible = False

        tk.Label(
            root,
            text=f"Usuario: {self.usuario}",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            root,
            text="Elige una contraseña nueva para iniciar sesion en este equipo.",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=16)

        tk.Label(root, text="Nueva contraseña:").pack(anchor="w", padx=16, pady=(12, 2))
        self.entry_password = tk.Entry(root, show="*", width=40)
        self.entry_password.pack(anchor="w", padx=16)
        self.entry_password.bind("<KeyRelease>", self._actualizar_fuerza)

        tk.Label(root, text="Confirmar contraseña:").pack(anchor="w", padx=16, pady=(8, 2))
        self.entry_confirm = tk.Entry(root, show="*", width=40)
        self.entry_confirm.pack(anchor="w", padx=16)

        self.btn_mostrar = tk.Button(
            root,
            text="Mostrar contraseña",
            command=self._mostrar_ocultar,
            width=18,
        )
        self.btn_mostrar.pack(anchor="w", padx=16, pady=(6, 4))
        ToolTip(self.btn_mostrar, "Muestra u oculta lo escrito para evitar errores")

        marco_fuerza = tk.LabelFrame(root, text="Seguridad de la contraseña", padx=10, pady=8)
        marco_fuerza.pack(fill=tk.X, padx=16, pady=(8, 4))

        fila_barra = tk.Frame(marco_fuerza)
        fila_barra.pack(fill=tk.X)
        self.canvas_barra = tk.Canvas(fila_barra, width=220, height=14, highlightthickness=1, highlightbackground="#bdc3c7")
        self.canvas_barra.pack(side=tk.LEFT)
        self.lbl_fuerza = tk.Label(fila_barra, text="", width=12, anchor="w")
        self.lbl_fuerza.pack(side=tk.LEFT, padx=8)

        self.lbls_checks = []
        for _i in range(5):
            lbl = tk.Label(marco_fuerza, text="", anchor="w", justify=tk.LEFT)
            lbl.pack(anchor="w")
            self.lbls_checks.append(lbl)

        tk.Label(
            root,
            text="No reutilices una contraseña que utilices en otros servicios.",
            wraplength=400,
            justify=tk.LEFT,
            fg="#2471a3",
            font=("Arial", 9),
        ).pack(anchor="w", padx=16, pady=(6, 4))

        fila_btns = tk.Frame(root)
        fila_btns.pack(pady=12)
        btn_guardar = tk.Button(
            fila_btns,
            text="Cambiar contraseña",
            command=self._guardar,
            width=18,
        )
        btn_guardar.pack(side=tk.LEFT, padx=6)
        ToolTip(btn_guardar, "Aplica la nueva contraseña (pide la de administrador)")
        tk.Button(fila_btns, text="Cancelar", command=self._cerrar, width=12).pack(
            side=tk.LEFT, padx=6
        )

        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)
        self._actualizar_fuerza()

    def _mostrar_ocultar(self):
        self._visible = not self._visible
        show = "" if self._visible else "*"
        self.entry_password.config(show=show)
        self.entry_confirm.config(show=show)
        self.btn_mostrar.config(
            text="Ocultar contraseña" if self._visible else "Mostrar contraseña"
        )

    def _actualizar_fuerza(self, _evento=None):
        info = evaluar_fuerza_contrasena(self.entry_password.get())
        self.canvas_barra.delete("all")
        ancho = 220
        alto = 14
        self.canvas_barra.create_rectangle(0, 0, ancho, alto, fill="#ecf0f1", outline="")
        relleno = max(0, min(1.0, info["relleno"]))
        if relleno > 0:
            self.canvas_barra.create_rectangle(
                0, 0, int(ancho * relleno), alto, fill=info["color"], outline=""
            )
        self.lbl_fuerza.config(text=info["etiqueta"] or "-", fg=info["color"])
        for lbl, (etiqueta, ok) in zip(self.lbls_checks, info["checks"]):
            marca = "[OK]" if ok else "[  ]"
            color = "#1e8449" if ok else "#7f8c8d"
            lbl.config(text=f"{marca}  {etiqueta}", fg=color)

    def _cerrar(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        if self.al_cerrar:
            try:
                self.al_cerrar()
            except Exception:
                pass

    def _guardar(self):
        password = self.entry_password.get()
        confirm = self.entry_confirm.get()
        if not password:
            messagebox.showerror("Contrasena", "Escribe una contraseña nueva.", parent=self.root)
            return
        if password != confirm:
            messagebox.showerror("Contrasena", "Las contraseñas no coinciden.", parent=self.root)
            return
        fuerza = evaluar_fuerza_contrasena(password)
        if fuerza["puntos"] < 3:
            if not messagebox.askyesno(
                "Contrasena debil",
                "La contraseña es debil segun las comprobaciones.\n"
                "¿Quieres usarla de todas formas?",
                parent=self.root,
            ):
                return
        if not confirmar(
            "Que se va a hacer?\n"
            "Se cambiara la contraseña de inicio de sesion de tu usuario.\n\n"
            "Por que?\n"
            "Para proteger la cuenta con una clave nueva.\n\n"
            "Que riesgos tiene?\n"
            "Si olvidas la nueva, no podras entrar hasta recuperarla.\n"
            "Haz falta la contraseña de administrador para aplicarlo.\n\n"
            "Continuar?",
            self.root,
            "Cambiar contraseña",
        ):
            return

        contrasena_sudo = obtener_contrasena()
        if not contrasena_sudo:
            return

        try:
            process = Popen(
                ["sudo", "-S", "chpasswd"],
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
            )
            _stdout, stderr = process.communicate(
                input=f"{contrasena_sudo}\n{self.usuario}:{password}\n"
            )
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, "chpasswd", stderr=stderr
                )
            registrar("Cambiar contraseña", f"Usuario {self.usuario}", True)
            messagebox.showinfo(
                "Contrasena",
                "La contraseña se ha cambiado correctamente.",
                parent=self.root,
            )
            self._cerrar()
        except subprocess.CalledProcessError as error:
            detalle = getattr(error, "stderr", None) or error
            messagebox.showerror(
                "Contrasena",
                f"No se pudo cambiar la contraseña:\n{detalle}",
                parent=self.root,
            )
        except Exception as error:
            messagebox.showerror(
                "Contrasena",
                f"No se pudo cambiar la contraseña:\n{error}",
                parent=self.root,
            )


class PerfilUsuario:
    """Clase para la interfaz de modificación del perfil de usuario."""
    def __init__(self, root):
        """Inicializa la interfaz gráfica de usuario.

        Args:
            root (tk.Tk): La ventana principal de tkinter.
        """
        self.root = root
        self.root.title("Modificar Perfil De Usuario En El Sistema Operativo")
        self.root.geometry("400x520")

        datos = datos_perfil_actual()
        tk.Label(root, text=f"Usuario: {datos['usuario']}").pack()
        tk.Label(root, text="* Nombre:").pack()
        self.entry_nombre = tk.Entry(root, width=36)
        self.entry_nombre.pack()
        ToolTip(self.entry_nombre, "Nombre visible del usuario (se puede modificar)")

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        # Botón para elegir una imagen de perfil
        self.seleccion_imagen = tk.Button(root, text="Seleccionar Imagen de Perfil", command=self.seleccionar_imagen)
        self.seleccion_imagen.pack(pady=5)
        ToolTip(self.seleccion_imagen, "Elige una imagen para el perfil de usuario")

        self.label_imagen = tk.Label(root, text="Sin imagen de perfil")
        self.label_imagen.pack(pady=10)
        ToolTip(self.label_imagen, "Imagen actual del perfil de usuario")

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        # Contenedor para los botones
        self.frame_botones = tk.Frame(root)
        self.frame_botones.pack(pady=10)

        # Botón para guardar los cambios
        self.boton_guardar_perfil = tk.Button(self.frame_botones, text="Guardar Perfil", command=self.guardar_perfil)
        self.boton_guardar_perfil.pack(side=tk.LEFT, padx=5)
        ToolTip(self.boton_guardar_perfil, "Guardar Perfil de Usuario con los Datos Introducidos")

        # Botón para cancelar
        self.boton_cancelar = tk.Button(self.frame_botones, text="Cancelar", command=root.destroy)
        self.boton_cancelar.pack(side=tk.LEFT, padx=5)
        ToolTip(self.boton_cancelar, "Cancelar el guardado del Perfil de Usuario")

        # Dibujar una línea horizontal
        self.canvas = tk.Canvas(root, width=200, height=2, bg="lightgrey", highlightthickness=0)
        self.canvas.create_line(0, 1, 500, 1, fill="silver")
        self.canvas.pack(pady=10)

        # Ruta de la imagen de perfil seleccionada
        self.imagen_perfil = None
        self.imagen_tk = None  # Retener la referencia a la imagen

        # Cargar los datos actuales del usuario
        self.cargar_datos_usuario()

    def seleccionar_imagen(self):
        """Abre un cuadro de diálogo para seleccionar una imagen de perfil."""
        self.imagen_perfil = filedialog.askopenfilename(
            initialdir=os.path.expanduser("~"),
            title="Seleccionar Imagen de Perfil",
            filetypes=(("Archivos de imagen", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*"))
        )
        if self.imagen_perfil:
            # Mostrar la previsualización de la imagen seleccionada
            self.mostrar_previsualizacion_imagen(self.imagen_perfil)
            messagebox.showinfo("Imagen seleccionada", f"Imagen seleccionada: {self.imagen_perfil}")

    def mostrar_previsualizacion_imagen(self, ruta_imagen):
        """Muestra una previsualización de la imagen de perfil seleccionada.

        Args:
            ruta_imagen (str): La ruta del archivo de imagen seleccionado.
        """
        try:
            self.imagen_tk = _foto_perfil(ruta_imagen, (100, 100))
            self.label_imagen.config(image=self.imagen_tk, text="")
            self.label_imagen.image = self.imagen_tk
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la imagen de perfil: {e}")

    def cargar_datos_usuario(self):
        """Rellena el formulario con el nombre e imagen actuales, sin pedir sudo."""
        datos = datos_perfil_actual()
        self.entry_nombre.delete(0, tk.END)
        self.entry_nombre.insert(0, datos["nombre"])
        if datos["imagen"]:
            self.mostrar_previsualizacion_imagen(datos["imagen"])

    def _guardar_imagen_perfil(self, usuario, contrasena_sudo):
        if not self.imagen_perfil:
            return
        destino_home = os.path.join(os.path.expanduser("~"), ".face")
        shutil.copy2(self.imagen_perfil, destino_home)
        destino_cuenta = f"/var/lib/AccountsService/icons/{usuario}"
        subprocess.run(
            ["sudo", "-S", "cp", self.imagen_perfil, destino_cuenta],
            input=f"{contrasena_sudo}\n",
            text=True,
            check=False,
        )
        subprocess.run(
            ["sudo", "-S", "chmod", "644", destino_cuenta],
            input=f"{contrasena_sudo}\n",
            text=True,
            check=False,
        )

    def guardar_perfil(self):
        """Guarda nombre visible e imagen de perfil (la contraseña se cambia aparte)."""
        nombre = self.entry_nombre.get().strip()
        usuario = getpass.getuser()

        if not nombre:
            messagebox.showerror("Error", "El nombre es obligatorio.")
            return

        contrasena_sudo = obtener_contrasena()
        if not contrasena_sudo:
            return

        try:
            subprocess.run(
                ["sudo", "-S", "usermod", "-c", nombre, usuario],
                input=f"{contrasena_sudo}\n",
                text=True,
                check=True,
                capture_output=True,
            )
            self._guardar_imagen_perfil(usuario, contrasena_sudo)

            messagebox.showinfo("Perfil", "Los datos del perfil se han actualizado.")
            reiniciar_sesion = messagebox.askyesno(
                "Reiniciar sesión",
                "¿Quieres reiniciar la sesión para aplicar los cambios?",
            )
            if reiniciar_sesion:
                limpiar_archivos_configuracion()
                subprocess.run(["pkill", "-HUP", "-u", usuario])
            else:
                try:
                    self.root.destroy()
                except tk.TclError:
                    pass
        except subprocess.CalledProcessError as e:
            detalle = e.stderr if getattr(e, "stderr", None) else e
            messagebox.showerror("Error", f"No se pudo actualizar el perfil: {detalle}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar el perfil: {e}")

