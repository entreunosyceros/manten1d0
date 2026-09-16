## Manten1d0: Mantenimiento básico de Ubuntu
![Manten1d0](https://github.com/sapoclay/manten1d0/assets/6242827/358bb3c2-d0af-4f07-a592-dcee7b1ed1a0)
------------------------------------------------------------------
* Manten1d0: sistema de mantenimiento básico y otras herramientas para Ubuntu.
* Creado con: Python 3.10.12
* Versión actual del programa: **0.6.0**
* Probado en: Ubuntu 22.04
------------------------------------------------------------------
Esto es un pequeño programa para realizar el mantenimiento básico de Ubuntu, y que así no me toquen las narices todos los días cuando quiere instalar un programa, llega una actualización del sistema y cosas por el estilo.

La contraseña de sudo se pide una vez al iniciar y se guarda cifrada. Las acciones sensibles piden confirmación y quedan en el registro **sin anotar la contraseña**. Las tareas largas se ejecutan en segundo plano para no bloquear la interfaz. Cada botón tiene un tooltip descriptivo que desaparece al salir el ratón.

Las versiones anteriores están en [CHANGELOG.md](CHANGELOG.md).

## Características de la versión 0.6.0

### Inicio
- Logo `Manten1do.png` a tamaño del área disponible.
- Avisos de estado: Internet, disco raíz o carpeta personal (>80 % / >90 %), actualizaciones APT (incluidas las de seguridad) y problemas SMART si `smartctl` está disponible.
- Pulsar un aviso abre la categoría relacionada. Se puede actualizar la lista o abrir el registro de acciones.

### Perfil de usuario
- Muestra los datos actuales que se pueden modificar: foto, usuario, nombre visible, carpeta personal, intérprete y grupos.
- El formulario de edición llega ya rellenado. Se puede cambiar nombre visible, imagen y contraseña (el login no se altera desde aquí).

### Información
- Informe del equipo: sistema, Ubuntu, escritorio, tiempo encendido, **tiempo de arranque (`systemd-analyze`)**, red, DNS, CPU, memoria y zona horaria.
- Gráfica **AMD, Intel y NVIDIA** (lspci/sysfs; `nvidia-smi` solo si hay NVIDIA).
- Copiar el informe al portapapeles o exportarlo a un `.txt`.

### Sistema
- Actualizar, limpiar caché APT, gestor de software, autostart, borrar archivos, vaciar papelera, procesos, duplicados, repositorios/PPA, monitorización, instalar `.deb`, desinstalar paquetes, logs, limpieza de disco, SMART y servicios systemd.
- **Historial de comandos**: vuelve a lanzar limpiezas y acciones ya ejecutadas, con confirmación.
- **Impresoras**: busca equipos USB o de la red local, lista las colas de CUPS, página de prueba y abre la configuración del sistema.

### Archivos
- Copia y restauración `.gz`, cifrado/descifrado, búsqueda y renombrado masivo.
- **Permisos y propietario** (chmod/chown, también recursivo).
- **USB / discos**: listar, montar y desmontar (udisksctl).
- **Archivos grandes**: ISO, ficheros pesados y descargas antiguas; enviar a la papelera.
- **Hash MD5 / SHA-1 / SHA-256** para comprobar descargas.

### Internet
- Reiniciar interfaz, ping, escaneo de puertos, test de velocidad, diagnóstico (traceroute/netstat) y **nivel de ruido** (SNR Wi-Fi, jitter y pérdida de paquetes).
- **Wi-Fi** con nmcli (listar, conectar, desconectar; la clave no se guarda en el registro).
- **DNS**: router (DHCP), Cloudflare `1.1.1.1` o Google `8.8.8.8`.
- **Editor de `/etc/hosts`** con validación y copia `.bak` al guardar.

### Red local
- Listado de equipos con **IP, nombre, MAC** y si comparte **Samba**.
- Doble clic abre `smb://` en el administrador de archivos si está disponible.

### Navegadores
- Chrome, Firefox, Edge, **Brave, Chromium y Vivaldi**: abrir (también privado), instalar y limpiar caché/historial.
- **Perfiles y marcadores**: lista perfiles locales y exporta marcadores a HTML.

### Diccionario y notas
- Diccionario GNU/Linux en línea (hace falta Internet).
- **Notas** en una carpeta fija del usuario (`Documentos/Manten1d0/Notas` o `Documents/Manten1d0/Notas`), con listado de las últimas y editor `.md` / `.txt`.

### Ayuda y menús
- Menú **Ayuda**: documentación de todas las opciones y ventana Acerca de (versión 0.6.0).
- Archivo: terminal, abrir URL, salir.
- Preferencias: tema claro/oscuro, tamaño de texto, actualizaciones, repositorio GitHub, registro de acciones y atajos **Alt+1 … Alt+0**.

## Dependencias imprescindibles

Hay que instalarlas a mano si no están en el sistema:

- Python 3 → `sudo apt install python3.10`
- pip3 → `sudo apt install python3-pip`

## Dependencias instalables

El programa las comprueba al iniciar e intenta instalar las que falten.

**APT** (`dependencias.py`): samba, nmap, net-tools, ethtool, iw, gnome-terminal, smartmontools, traceroute, python3-dbus, python3-tk, pciutils, lshw, arp-scan, cups-client, avahi-utils; y los módulos Python `python3-pil`, `python3-pil.imagetk`, `python3-cryptography`, `python3-psutil`, `python3-matplotlib`, `python3-requests`, `python3-pyqt5`, `python3-netifaces`, `python3-markdown2`, `python3-nmap`, `speedtest-cli`.

**pip** (`requirements.txt`, solo si ejecutas desde código fuente con `index.py`): matplotlib, pillow, cryptography, psutil, markdown2, PyQt5, speedtest-cli, netifaces, python-nmap, requests.

## Instalación del paquete .DEB

Generar el paquete desde el código fuente:

```
bash packaging/build-deb.sh
```

En una terminal (`Ctrl+Alt+T`):

```
sudo apt install -f ./manten1d0_0.6.0_all.deb
```

o, como indica el nombre corto:

```
sudo dpkg -i Manten1d0.deb
sudo apt-get install -f
```

Tras la instalación deberías ver el lanzador en Actividades.

![lanzador](https://github.com/sapoclay/mantenimiento-sistema-basico/assets/6242827/1b0a026c-5cd9-4bc1-aca0-f9e2787d9d27)

## Desinstalación

```
sudo apt remove manten1d0
```

Para no dejar rastro:

```
sudo rm -rf /usr/share/Manten1d0/
```
