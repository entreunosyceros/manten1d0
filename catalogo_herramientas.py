"""Catalogo buscable de herramientas de Manten1d0 (barra lateral)."""

import os
import subprocess
import tkinter as tk

from actualizar_todo import ActualizarTodo
from analisis_arranque import AnalisisArranque
from asistente_internet import AsistenteInternet
from asistente_problemas import AsistenteProblemas
from cat_archivos import BulkRenameApp, FileSearchApp, cifrar_archivo, descifrar_archivo
from cat_archivos_extra import (
    ArchivosGrandes,
    CopiaUSB,
    DispositivosBloque,
    HashArchivo,
    PermisosArchivos,
)
from cat_internet import RedTools
from cat_navegadores import (
    InstalarNavegadores,
    InstalarNavegadoresExtra,
    PerfilesNavegadores,
    abrir_navegador,
)
from cat_red_extra import EditorHosts, PuertoDesdeInternet, RedesWifi, SelectorDns
from cat_redLocal import CompartirCarpeta, EncenderPC, RouterCasa
from cat_sistema import (
    AdministrarProcesos,
    AplicacionBuscadorDuplicados,
    AplicacionesAutostart,
    DebInstalador,
    DesinstalarPaquetes,
    Limpieza,
    Repositorios,
    actualizar_sistema,
    consultaLogs,
    limpiar_cache,
    abrir_gestor_software,
)
from cat_sistema_extra import (
    Bluetooth,
    EspacioDiscos,
    Impresoras,
    LimpiezaEspacio,
    Pantallas,
    SaludDiscos,
    ServiciosFallidos,
    ServiciosSystemd,
    SnapFlatpak,
    Sonido,
)
from cat_vpn import PanelExpressVPN, expressvpn_disponible
from centro_aplicaciones import CentroAplicaciones
from centro_seguridad import CentroSeguridad
from informe_asistencia import InformeAsistencia
from monitor_recursos import MonitorRecursos
from registro import mostrar_historial_comandos, mostrar_registro
from reparar import RepararUbuntu


def _toplevel(app):
    return tk.Toplevel(getattr(app, "area_central", app.root))


def construir_catalogo(app):
    """Lista de herramientas: nombre, categoria, ayuda y accion abrir()."""
    root = app.root
    area = getattr(app, "area_central", root)

    def ir(categoria):
        app.mostrar_subcategorias(categoria)

    def panel(clase):
        return lambda: clase(_toplevel(app))

    entradas = [
        # Categorias
        ("Inicio", "Inicio", "Diagnostico y resumen del equipo", lambda: ir("Inicio")),
        ("Perfil Usuario", "Perfil Usuario", "Datos del usuario y carpeta personal", lambda: ir("Perfil Usuario")),
        ("Información", "Información", "Informe del sistema operativo", lambda: ir("Información")),
        ("Sistema", "Sistema", "Actualizaciones, espacio, servicios y hardware", lambda: ir("Sistema")),
        ("Archivos", "Archivos", "Copias, cifrado, busqueda y utilidades", lambda: ir("Archivos")),
        ("Internet", "Internet", "Red, DNS, Wi-Fi y diagnostico", lambda: ir("Internet")),
        ("Red Local", "Red Local", "Equipos de casa, compartir y Wake-on-LAN", lambda: ir("Red Local")),
        ("Navegadores", "Navegadores", "Abrir, instalar y limpiar navegadores", lambda: ir("Navegadores")),
        ("Diccionario", "Diccionario", "Comandos Gnu/Linux", lambda: ir("Diccionario")),
        ("Notas", "Notas", "Apuntes rapidos", lambda: ir("Notas")),
        # Inicio / diagnostico
        ("Que problema tienes?", "Inicio", "Asistente por sintomas", panel(AsistenteProblemas)),
        ("Reparar Ubuntu", "Sistema", "Reparaciones guiadas por problema", panel(RepararUbuntu)),
        ("Informe de asistencia", "Inicio", "Diagnostico + datos del equipo para enviar", panel(InformeAsistencia)),
        ("Actualizar todo", "Sistema", "APT, Snap y Flatpak juntos", panel(ActualizarTodo)),
        ("Liberar espacio", "Sistema", "Limpieza rapida o profunda del disco", panel(LimpiezaEspacio)),
        ("Registro de acciones", "Inicio", "Historial de acciones de la aplicacion", lambda: mostrar_registro(root)),
        # Sistema
        ("Actualizar Sistema", "Sistema", "Instala actualizaciones APT", lambda: actualizar_sistema(root)),
        ("Centro de aplicaciones", "Sistema", "APT, Snap y Flatpak", panel(CentroAplicaciones)),
        ("Limpiar Caché", "Sistema", "Limpia la cache del sistema", lambda: limpiar_cache(root)),
        ("Abrir Gestor Software", "Sistema", "Snap Store / software Ubuntu", abrir_gestor_software),
        ("Instalar .deb", "Sistema", "Instala un paquete .deb", lambda: DebInstalador().ejecutar(root)),
        ("Desinstalar Paquetes", "Sistema", "Quita paquetes del usuario", panel(DesinstalarPaquetes)),
        ("Gestiona Repositorios", "Sistema", "Repositorios APT", panel(Repositorios)),
        ("Snap y Flatpak", "Sistema", "Apps Snap/Flatpak y espacio", panel(SnapFlatpak)),
        ("Espacio discos", "Sistema", "Uso de disco por particion y carpetas", panel(EspacioDiscos)),
        ("Vaciar Papelera", "Sistema", "Vacia la papelera", Limpieza.vaciar_papelera),
        ("Eliminar Archivo/s", "Sistema", "Borra archivos o carpetas", Limpieza.eliminar_elemento),
        ("Buscar Archivos Duplicados", "Sistema", "Encuentra duplicados", panel(AplicacionBuscadorDuplicados)),
        ("Administrar Procesos", "Sistema", "Lista y cierra procesos", panel(AdministrarProcesos)),
        ("Monitorizar", "Sistema", "CPU, RAM, disco y temperatura", panel(MonitorRecursos)),
        ("Servicios", "Sistema", "Control de servicios systemd", panel(ServiciosSystemd)),
        ("Servicios que fallan", "Sistema", "Unidades systemd en fallo", panel(ServiciosFallidos)),
        ("Ver logs", "Sistema", "Registros del sistema", panel(consultaLogs)),
        ("Salud discos", "Sistema", "SMART y temperatura", panel(SaludDiscos)),
        ("Centro de seguridad", "Sistema", "Firewall, updates y puertos", panel(CentroSeguridad)),
        ("Bluetooth", "Sistema", "Dispositivos y reinicio Bluetooth", panel(Bluetooth)),
        ("Sonido", "Sistema", "Salida de audio y reinicio", panel(Sonido)),
        ("Pantallas", "Sistema", "Monitores: espejo o extender", panel(Pantallas)),
        ("Impresoras", "Sistema", "USB, red y colas CUPS", panel(Impresoras)),
        ("Aplicaciones Inicio", "Sistema", "Autostart al iniciar sesion", panel(AplicacionesAutostart)),
        ("Por que tarda en arrancar?", "Sistema", "Analisis de arranque", panel(AnalisisArranque)),
        ("Historial comandos", "Sistema", "Repite acciones ya ejecutadas", lambda: mostrar_historial_comandos(root)),
        # Archivos
        ("Copiar A Un USB", "Archivos", "Copia Documentos/escritorio a USB", panel(CopiaUSB)),
        ("Cifrar Archivos", "Archivos", "Cifra un archivo", cifrar_archivo),
        ("Descifrar Archivos", "Archivos", "Descifra un archivo", descifrar_archivo),
        ("Busca archivos", "Archivos", "Buscador de archivos", lambda: FileSearchApp(tk.Toplevel())),
        ("Renombrar archivos", "Archivos", "Renombrado masivo", lambda: BulkRenameApp(tk.Toplevel())),
        ("Permisos / propietario", "Archivos", "chmod y chown", panel(PermisosArchivos)),
        ("USB / discos", "Archivos", "Montar o desmontar discos", panel(DispositivosBloque)),
        ("Archivos grandes", "Archivos", "ISO y ficheros pesados", panel(ArchivosGrandes)),
        ("Hash MD5/SHA", "Archivos", "Comprobar integridad", panel(HashArchivo)),
        # Internet
        ("Tengo problemas con Internet", "Internet", "Asistente de conexion", panel(AsistenteInternet)),
        ("Redes Wi-Fi", "Internet", "Conectar o desconectar Wi-Fi", panel(RedesWifi)),
        ("DNS", "Internet", "Cambiar DNS de la conexion", panel(SelectorDns)),
        ("Hosts locales", "Internet", "Editar /etc/hosts", panel(EditorHosts)),
        ("Puerto desde Internet", "Internet", "Comprobar puerto desde fuera", panel(PuertoDesdeInternet)),
        ("Escanear Puertos", "Internet", "Escaneo de puertos de una IP", lambda: RedTools(root).escanear_puertos()),
        ("Test Velocidad", "Internet", "Velocidad de descarga y carga", lambda: RedTools(root).test_velocidad()),
        ("Diagnóstico Red", "Internet", "traceroute y netstat", lambda: RedTools(root).diagnostico_red()),
        ("Hacer Ping", "Internet", "Ping a una URL o host", lambda: ir("Internet")),
        # Red local
        ("Quién hay en la red", "Red Local", "Lista equipos en la red local", lambda: ir("Red Local")),
        ("¿Responde el router?", "Red Local", "Ping al router de casa", panel(RouterCasa)),
        ("Compartir carpeta", "Red Local", "Compartir carpeta en la red", panel(CompartirCarpeta)),
        ("Encender un PC", "Red Local", "Wake-on-LAN", panel(EncenderPC)),
        # Navegadores
        ("Chrome", "Navegadores", "Abrir Google Chrome", lambda: subprocess.Popen(["google-chrome"])),
        ("Firefox", "Navegadores", "Abrir Mozilla Firefox", lambda: subprocess.Popen(["firefox"])),
        ("Edge", "Navegadores", "Abrir Microsoft Edge", lambda: subprocess.Popen(["microsoft-edge"])),
        ("Brave", "Navegadores", "Abrir Brave", lambda: abrir_navegador(["brave-browser"], "Brave")),
        ("Instalar Chrome", "Navegadores", "Instalar Google Chrome", InstalarNavegadores.instalar_chrome),
        ("Instalar Firefox", "Navegadores", "Instalar Mozilla Firefox", InstalarNavegadores.instalar_firefox),
        ("Instalar Edge", "Navegadores", "Instalar Microsoft Edge", InstalarNavegadores.instalar_edge),
        ("Instalar Brave", "Navegadores", "Instalar Brave", lambda: InstalarNavegadoresExtra.instalar_brave(root)),
        ("Instalar Chromium", "Navegadores", "Instalar Chromium", lambda: InstalarNavegadoresExtra.instalar_chromium(root)),
        ("Instalar Vivaldi", "Navegadores", "Instalar Vivaldi", lambda: InstalarNavegadoresExtra.instalar_vivaldi(root)),
        ("Perfiles y marcadores", "Navegadores", "Exportar marcadores", panel(PerfilesNavegadores)),
        ("Limpiar navegadores", "Navegadores", "Borrar cache e historial", lambda: ir("Navegadores")),
    ]

    if expressvpn_disponible():
        entradas.append(
            ("VPN", "Internet", "Panel ExpressVPN", panel(PanelExpressVPN))
        )

    catalogo = []
    for nombre, categoria, ayuda, abrir in entradas:
        catalogo.append(
            {
                "nombre": nombre,
                "categoria": categoria,
                "ayuda": ayuda,
                "abrir": abrir,
                "busqueda": f"{nombre} {categoria} {ayuda}".lower(),
            }
        )
    catalogo.sort(key=lambda e: e["nombre"].lower())
    return catalogo


def filtrar_catalogo(catalogo, consulta):
    """Devuelve entradas cuyo nombre/categoria/ayuda contienen la consulta."""
    texto = (consulta or "").strip().lower()
    if not texto:
        return []
    partes = [p for p in texto.split() if p]
    resultados = []
    for item in catalogo:
        hay = item["busqueda"]
        if all(p in hay for p in partes):
            resultados.append(item)
    return resultados
