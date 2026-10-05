## Manten1d0: Mantenimiento básico de Ubuntu
<p align="center">
<img width="1431" height="1099" alt="Manten1do" src="https://github.com/user-attachments/assets/d014f1ba-1fe3-438e-a31c-dc61c12798e0" />
</p>

------------------------------------------------------------------
* Manten1d0: sistema de mantenimiento básico y otras herramientas para Ubuntu.
* Creado con: Python 3.10.12
* Versión actual del programa: **0.8.1**
* Probado en: Ubuntu 24.04
------------------------------------------------------------------
Esto es un pequeño programa para realizar el mantenimiento básico de Ubuntu, y que así no me toquen las narices todos los días cuando quiere instalar un programa, llega una actualización del sistema y cosas por el estilo.

La contraseña de sudo se pide una vez al iniciar y se guarda cifrada. Las acciones sensibles piden confirmación y quedan en el registro **sin anotar la contraseña**. Las tareas largas se ejecutan en segundo plano para no bloquear la interfaz. Cada botón tiene un tooltip descriptivo que desaparece al salir el ratón.

Las versiones anteriores están en [CHANGELOG.md](CHANGELOG.md).

## Características de la versión 0.8.1

### Inicio

<p align="center">
<img width="1919" height="1010" alt="interfaz-inicio" src="https://github.com/user-attachments/assets/40e4f4b7-d232-4b1b-8c3a-1fc503a4b1fc" />
</p>

- **¿Qué problema tienes?**: asistente técnico por síntoma. Eliges Internet, sonido, impresora, pantalla, lentitud, espacio, instalación, actualizaciones, Bluetooth o arranque lento; Manten1d0 hace el diagnóstico concreto y propone la herramienta o reparación adecuada.
- Diagnóstico del equipo (checklist completa), **Reparar Ubuntu**, **Liberar espacio**, **Actualizar todo**, **Informe de asistencia** y registro de acciones.
- Diálogos de arranque (contraseña y dependencias) con el mismo estilo visible.

### Perfil de usuario

<p align="center">
<img width="1919" height="1010" alt="perfil-usuario" src="https://github.com/user-attachments/assets/46c1c86f-2287-434e-a3be-f323c843772d" /> 
</p>

- Carpeta personal con espacio utilizado y enlace a Liberar espacio; aplicaciones predeterminadas; carpetas XDG (solo consulta); contraseña con fuerza y estado; idioma y región.

### Información

<p align="center">
<img width="1922" height="1011" alt="informacion-SO" src="https://github.com/user-attachments/assets/8b1e7952-4d6f-445b-90c3-fb092c4e5051" />
  
</p>

- Informe del equipo: sistema, Ubuntu, escritorio, tiempo encendido, **tiempo de arranque (`systemd-analyze`)**, red, DNS, CPU, memoria y zona horaria.
- Gráfica **AMD, Intel y NVIDIA** (lspci/sysfs; `nvidia-smi` solo si hay NVIDIA).
- Copiar el informe al portapapeles, exportarlo a un `.txt` o abrir el **Informe de asistencia** (diagnóstico + equipo para enviarlo a quien ayude).

### Sistema
<p align="center">
<img width="1917" height="1009" alt="sistema" src="https://github.com/user-attachments/assets/ec2a42a7-03d3-44b7-bd32-f9f1fa320cef" />
</p>

- Las acciones están agrupadas en **poner al día**, **espacio**, **el equipo** y **al arrancar**: actualizar, **Actualizar todo** (APT + Snap + Flatpak), **Centro de aplicaciones** (lista unificada APT de escritorio + Snap + Flatpak: buscar, abrir, actualizar o desinstalar; ranking por espacio; atajos a Instalar .deb y la tienda), limpiar caché APT, gestor de software, autostart, **analisis de arranque** (systemd-analyze: tiempos por fase y servicios mas lentos con explicaciones), borrar archivos, vaciar papelera, procesos, duplicados, repositorios/PPA, **monitorización simplificada** (barras CPU/RAM/disco, procesos ordenables, Abrir/Finalizar), instalar `.deb`, desinstalar paquetes, logs, **Liberar espacio** (qué ocupa el disco, limpieza rápida o profunda: caché APT, journal, miniaturas, papelera, Snap antiguos y kernels viejos; atajos a Ver carpetas, Snap/Flatpak y Archivos grandes), **Snap y Flatpak** (listar con el espacio que ocupan, actualizar o desinstalar; van aparte de APT; si falta Flatpak se puede instalar desde ahí), SMART, servicios systemd, **servicios que fallan** (listar, reiniciar o ver un log corto), **Reparar Ubuntu** (evolución del diagnóstico: tarjeta por problema APT/dpkg/servicio/red/CUPS con confirmación qué/por qué/riesgos), **espacio de cada disco** (carpetas que más ocupan), **Bluetooth**, **Sonido** (reiniciar PipeWire/PulseAudio o cambiar de salida), **Pantallas** (espejo / extendido / una sola con xrandr o ajustes GNOME) y **Centro de seguridad** (checklist de firewall, actualizaciones, usuario y puertos en escucha con explicaciones; desde ahí se abre el cortafuegos ufw con reglas SSH/Samba/red local, Actualizar todo, o desactivar servicios conocidos).
- **Historial de comandos**: vuelve a lanzar limpiezas y acciones ya ejecutadas, con confirmación.
- **Impresoras**: busca equipos USB o de la red local, lista las colas de CUPS, página de prueba y abre la configuración del sistema.

### Archivos

<p align="center">
<img width="1919" height="1007" alt="archivos" src="https://github.com/user-attachments/assets/aa974275-d1b8-4c89-86d1-ecabb9ac5010" />  
</p>
- Las acciones están agrupadas en **copias**, **proteger**, **organizar** y **comprobar y liberar**.
- **Copiar a un USB**: Documentos o el escritorio, en una carpeta con la fecha en el nombre. Si el USB no está abierto, se monta; si no cabe, avisa y no copia. La restauración de un `.gz` antiguo sigue disponible. Cifrado/descifrado, búsqueda y renombrado masivo.
- **Permisos y propietario** (chmod/chown, también recursivo).
- **USB / discos**: listar, montar y desmontar (udisksctl).
- **Archivos grandes**: ISO, ficheros pesados y descargas antiguas; enviar a la papelera.
- **Hash MD5 / SHA-1 / SHA-256** para comprobar descargas.

### Internet
<p align="center">
<img width="1919" height="1009" alt="internet" src="https://github.com/user-attachments/assets/994a3d13-eb91-4b29-9dbc-82e8c9af6691" />


</p>

- Acciones agrupadas en **conexión**, **ajustes de red** y **herramientas**.
- Reiniciar interfaz, ping, escaneo de puertos, **puerto desde Internet** (aviso de riesgos; escucha local + comprobación en el navegador), test de velocidad, diagnóstico (traceroute/netstat) y **nivel de ruido** (SNR Wi-Fi, jitter y pérdida de paquetes).
- **Tengo problemas con Internet**: checklist automática (adaptador, router, DNS, Internet, latencia, pérdida) con solución recomendada aplicable (p. ej. DNS Cloudflare o reiniciar NetworkManager).
- **Wi-Fi** con nmcli (listar, conectar, desconectar; la clave no se guarda en el registro).
- **DNS**: router (DHCP), Cloudflare `1.1.1.1` o Google `8.8.8.8`.
- **Editor de `/etc/hosts`** con validación y copia `.bak` al guardar.
- **VPN**: solo **ExpressVPN** (si `expressvpnctl` está instalado). Estado, conectar o desconectar, región, protocolo, bloqueo de red, red local, arranque automático y túnel dividido. La sesión sigue en la aplicación oficial. NordVPN, Surfshark, Proton VPN, CyberGhost, Mullvad y el resto no se gestionan aquí.
- El indicador del menú lateral muestra si hay Internet y, debajo, la IP privada (la de la red de casa, no la del túnel VPN), la IP pública y si hay **VPN** activa (ExpressVPN o túnel típico).

### Red local
<p align="center">
<img width="1920" height="1010" alt="redlocal" src="https://github.com/user-attachments/assets/9f5df260-e6bb-4282-8abb-9fda990d1aa5" />

  
</p>

- Listado de equipos con **IP, nombre, MAC** y si comparte **Samba** (**quién hay en la red**, Wi‑Fi o cable; no hace falta entrar en el router).
- Doble clic abre `smb://` en el administrador de archivos si está disponible.
- **¿Responde el router?**: ping a la puerta de enlace y acceso a su página de configuración.
- **Compartir carpeta**: otro equipo de casa puede ver una carpeta tuya (solo lectura, o también modificar), sin contraseña. Si el cortafuegos está activado, pregunta si hay que permitir Samba.
- **Encender un PC**: señal de encendido por red a un equipo guardado al buscar la red, o a una MAC anotada, si su placa lo permite.

### Navegadores

<p align="center">
<img width="1920" height="1011" alt="navegadores" src="https://github.com/user-attachments/assets/308421ec-3889-45da-8da0-33c001044062" />

</p>

- Acciones agrupadas en **abrir**, **instalar**, **limpiar** y **perfiles**.
- Chrome, Firefox, Edge, **Brave, Chromium y Vivaldi**: abrir (también privado), instalar y limpiar caché/historial.
- **Perfiles y marcadores**: lista perfiles locales y exporta marcadores a HTML.

### Diccionario y notas

<p align="center">

<img width="1921" height="1010" alt="diccionario" src="https://github.com/user-attachments/assets/4bf646cf-85ff-4e7f-9b81-5b0f13ef390a" />

</p>

- Diccionario GNU/Linux en línea (hace falta Internet).
- **Notas** en una carpeta fija del usuario (`Documentos/Manten1d0/Notas` o `Documents/Manten1d0/Notas`), con listado de las últimas y editor `.md` / `.txt`.

### Ayuda y menús

- Menú **Ayuda**: documentación de todas las opciones y ventana Acerca de (versión 0.8.1).
- Archivo: terminal, abrir URL, salir.
- Preferencias: tema claro, o el tema oscuro del sistema (GTK), paleta más suave, tamaño de texto, actualizaciones, repositorio GitHub, registro de acciones (con opción de **vaciarlo** sin tocar el historial de comandos repetibles) y atajos **Alt+1 … Alt+0**.

## Dependencias imprescindibles

Hay que instalarlas a mano si no están en el sistema:

- Python 3 → `sudo apt install python3.10`
- pip3 → `sudo apt install python3-pip`

## Dependencias instalables

El programa las comprueba al iniciar e intenta instalar las que falten. Si se ejecuta con otro Python (por ejemplo Miniconda), un paquete APT puede estar instalado y aun así no verse: entonces instala el equivalente de pip en el intérprete que está en marcha.

**APT** (`dependencias.py`): samba, nmap, net-tools, ethtool, iw, gnome-terminal, smartmontools, traceroute, python3-dbus, python3-tk, pciutils, lshw, arp-scan, cups-client, avahi-utils; y los módulos Python `python3-pil`, `python3-pil.imagetk`, `python3-cryptography`, `python3-psutil`, `python3-matplotlib`, `python3-requests`, `python3-pyqt5`, `python3-netifaces`, `python3-markdown2`, `python3-nmap`, `speedtest-cli`.

**pip** (`requirements.txt`, solo si ejecutas desde código fuente con `index.py`): matplotlib, pillow, cryptography, psutil, markdown2, PyQt5, speedtest-cli, netifaces, python-nmap, requests.

## Instalación del paquete .DEB

Generar el paquete desde el código fuente:

```
bash packaging/build-deb.sh
```

En una terminal (`Ctrl+Alt+T`):

```
sudo apt install -f ./manten1d0_0.8.1_all.deb
```

o, como indica el nombre corto:

```
sudo dpkg -i Manten1d0.deb
sudo apt-get install -f
```

Tras la instalación deberías ver el lanzador en Actividades.

<img width="429" height="233" alt="lanzador-manten1d0" src="https://github.com/user-attachments/assets/71aab8d8-befb-43dc-a651-8ebb3b55160b" />

## Desinstalación

```
sudo apt remove manten1d0
```

Para no dejar rastro:

```
sudo rm -rf /usr/share/Manten1d0/
```
