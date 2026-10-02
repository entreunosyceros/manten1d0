## Manten1d0: Mantenimiento básico de Ubuntu
<img width="798" height="766" alt="inicio" src="https://github.com/user-attachments/assets/09b50f34-0c50-40df-b053-d955fa474287" />

------------------------------------------------------------------
* Manten1d0: sistema de mantenimiento básico y otras herramientas para Ubuntu.
* Creado con: Python 3.10.12
* Versión actual del programa: **0.8.0**
* Probado en: Ubuntu 22.04
------------------------------------------------------------------
Esto es un pequeño programa para realizar el mantenimiento básico de Ubuntu, y que así no me toquen las narices todos los días cuando quiere instalar un programa, llega una actualización del sistema y cosas por el estilo.

La contraseña de sudo se pide una vez al iniciar y se guarda cifrada. Las acciones sensibles piden confirmación y quedan en el registro **sin anotar la contraseña**. Las tareas largas se ejecutan en segundo plano para no bloquear la interfaz. Cada botón tiene un tooltip descriptivo que desaparece al salir el ratón.

Las versiones anteriores están en [CHANGELOG.md](CHANGELOG.md).

## Características de la versión 0.8.0

### Inicio

- Barra lateral plana: la categoría activa queda marcada; los botones responden al pasar el ratón (también en tema oscuro).
- Logo `Manten1do.png` a tamaño del área disponible.
- **Diagnóstico del equipo**: checklist completa (ok / aviso / error) con Internet, espacio en disco, reinicio pendiente, actualizaciones APT, SMART, temperatura, servicios systemd fallidos y cortafuegos (ufw). Resumen arriba: problemas y avisos, o «Sin problemas detectados».
- Pulsar un resultado abre la herramienta concreta (limpieza de disco, Salud discos, servicios que fallan, cortafuegos…) o la categoría relacionada. El de reinicio pide confirmación y reinicia el equipo.
- **Analizar mi equipo** vuelve a ejecutar el diagnóstico. **Reparar Ubuntu** continúa el diagnóstico con **tarjetas por problema** (dependencias APT, paquetes a medias, cada servicio fallido, red, CUPS): cada reparación explica qué hará, por qué y los riesgos; también hay otras reparaciones útiles (audio, caché APT…). **Liberar espacio** muestra qué ocupa la carpeta personal, el espacio recuperable y perfiles de limpieza rápida o profunda. **Actualizar todo** cuenta e instala pendientes de APT, Snap y Flatpak. **Informe de asistencia** genera un texto del diagnóstico y del equipo para enviarlo a quien ayude. Se puede abrir el registro de acciones.

### Perfil de usuario

<img width="799" height="765" alt="perfil-usuario" src="https://github.com/user-attachments/assets/2f672cdc-e862-41e7-b748-4f8aa8179e6b" />

- Muestra lo esencial: foto, usuario, nombre visible, **configuración regional** (país, formatos, moneda, zona horaria) e **idioma de la interfaz**. La pestaña tiene desplazamiento vertical si hace falta.
- **Mi carpeta personal**: ruta del home, abrir en el explorador, ver espacio utilizado (Documentos, Descargas, Vídeos…) o ir a **Liberar espacio**.
- **Aplicaciones predeterminadas**: navegador, correo, visor de imágenes, vídeo y editor de texto; se puede restaurar lo del sistema.
- **Carpetas personales**: Documentos, Descargas, Música, Imágenes, Vídeos y Escritorio (solo consulta; Abrir en el explorador).
- **Contraseña**: último cambio y estado; **Cambiar contraseña** con indicador de fuerza, checklist, mostrar/ocultar y aviso de no reutilizar claves. Caducidad solo si el sistema la tiene configurada.
- **Idioma de la interfaz**: elige entre los idiomas instalados; se aplica al iniciar la próxima sesión.
- **Configuración regional**: resumen de formatos; para cambiarlos se abre el panel de Ubuntu.
- El formulario de edición permite cambiar nombre visible e imagen (el login no se altera desde aquí).

### Información

<img width="800" height="765" alt="info-sistema" src="https://github.com/user-attachments/assets/7a648d60-306e-42d4-9fb6-bc292403bb20" />

- Informe del equipo: sistema, Ubuntu, escritorio, tiempo encendido, **tiempo de arranque (`systemd-analyze`)**, red, DNS, CPU, memoria y zona horaria.
- Gráfica **AMD, Intel y NVIDIA** (lspci/sysfs; `nvidia-smi` solo si hay NVIDIA).
- Copiar el informe al portapapeles, exportarlo a un `.txt` o abrir el **Informe de asistencia** (diagnóstico + equipo para enviarlo a quien ayude).

### Sistema

<img width="796" height="771" alt="sisetma" src="https://github.com/user-attachments/assets/c20c5012-dfce-44f4-a327-807bcd7a06ca" />

- Las acciones están agrupadas en **poner al día**, **espacio**, **el equipo** y **al arrancar**: actualizar, **Actualizar todo** (APT + Snap + Flatpak), **Centro de aplicaciones** (lista unificada APT de escritorio + Snap + Flatpak: buscar, abrir, actualizar o desinstalar; ranking por espacio; atajos a Instalar .deb y la tienda), limpiar caché APT, gestor de software, autostart, **analisis de arranque** (systemd-analyze: tiempos por fase y servicios mas lentos con explicaciones), borrar archivos, vaciar papelera, procesos, duplicados, repositorios/PPA, **monitorización simplificada** (barras CPU/RAM/disco, procesos ordenables, Abrir/Finalizar), instalar `.deb`, desinstalar paquetes, logs, **Liberar espacio** (qué ocupa el disco, limpieza rápida o profunda: caché APT, journal, miniaturas, papelera, Snap antiguos y kernels viejos; atajos a Ver carpetas, Snap/Flatpak y Archivos grandes), **Snap y Flatpak** (listar con el espacio que ocupan, actualizar o desinstalar; van aparte de APT; si falta Flatpak se puede instalar desde ahí), SMART, servicios systemd, **servicios que fallan** (listar, reiniciar o ver un log corto), **Reparar Ubuntu** (evolución del diagnóstico: tarjeta por problema APT/dpkg/servicio/red/CUPS con confirmación qué/por qué/riesgos), **espacio de cada disco** (carpetas que más ocupan), **Bluetooth**, **Sonido** (reiniciar PipeWire/PulseAudio o cambiar de salida), **Pantallas** (espejo / extendido / una sola con xrandr o ajustes GNOME) y **Centro de seguridad** (checklist de firewall, actualizaciones, usuario y puertos en escucha con explicaciones; desde ahí se abre el cortafuegos ufw con reglas SSH/Samba/red local, Actualizar todo, o desactivar servicios conocidos).
- **Historial de comandos**: vuelve a lanzar limpiezas y acciones ya ejecutadas, con confirmación.
- **Impresoras**: busca equipos USB o de la red local, lista las colas de CUPS, página de prueba y abre la configuración del sistema.

### Archivos

<img width="799" height="766" alt="archivo" src="https://github.com/user-attachments/assets/03f7587a-ed85-42f1-b42a-0ccc29b46452" />

- Las acciones están agrupadas en **copias**, **proteger**, **organizar** y **comprobar y liberar**.
- **Copiar a un USB**: Documentos o el escritorio, en una carpeta con la fecha en el nombre. Si el USB no está abierto, se monta; si no cabe, avisa y no copia. La restauración de un `.gz` antiguo sigue disponible. Cifrado/descifrado, búsqueda y renombrado masivo.
- **Permisos y propietario** (chmod/chown, también recursivo).
- **USB / discos**: listar, montar y desmontar (udisksctl).
- **Archivos grandes**: ISO, ficheros pesados y descargas antiguas; enviar a la papelera.
- **Hash MD5 / SHA-1 / SHA-256** para comprobar descargas.

### Internet

<img width="906" height="771" alt="internet" src="https://github.com/user-attachments/assets/eb98713d-61bf-485f-81de-ed81493eac2f" />

- Acciones agrupadas en **conexión**, **ajustes de red** y **herramientas**.
- Reiniciar interfaz, ping, escaneo de puertos, **puerto desde Internet** (aviso de riesgos; escucha local + comprobación en el navegador), test de velocidad, diagnóstico (traceroute/netstat) y **nivel de ruido** (SNR Wi-Fi, jitter y pérdida de paquetes).
- **Tengo problemas con Internet**: checklist automática (adaptador, router, DNS, Internet, latencia, pérdida) con solución recomendada aplicable (p. ej. DNS Cloudflare o reiniciar NetworkManager).
- **Wi-Fi** con nmcli (listar, conectar, desconectar; la clave no se guarda en el registro).
- **DNS**: router (DHCP), Cloudflare `1.1.1.1` o Google `8.8.8.8`.
- **Editor de `/etc/hosts`** con validación y copia `.bak` al guardar.
- **VPN**: solo **ExpressVPN** (si `expressvpnctl` está instalado). Estado, conectar o desconectar, región, protocolo, bloqueo de red, red local, arranque automático y túnel dividido. La sesión sigue en la aplicación oficial. NordVPN, Surfshark, Proton VPN, CyberGhost, Mullvad y el resto no se gestionan aquí.
- El indicador del menú lateral muestra si hay Internet y, debajo, la IP privada (la de la red de casa, no la del túnel VPN), la IP pública y si hay **VPN** activa (ExpressVPN o túnel típico).

### Red local

<img width="907" height="770" alt="red-local" src="https://github.com/user-attachments/assets/9973bf20-5c61-41ec-acad-663b4487deb9" />

- Listado de equipos con **IP, nombre, MAC** y si comparte **Samba** (**quién hay en la red**, Wi‑Fi o cable; no hace falta entrar en el router).
- Doble clic abre `smb://` en el administrador de archivos si está disponible.
- **¿Responde el router?**: ping a la puerta de enlace y acceso a su página de configuración.
- **Compartir carpeta**: otro equipo de casa puede ver una carpeta tuya (solo lectura, o también modificar), sin contraseña. Si el cortafuegos está activado, pregunta si hay que permitir Samba.
- **Encender un PC**: señal de encendido por red a un equipo guardado al buscar la red, o a una MAC anotada, si su placa lo permite.

### Navegadores

<img width="904" height="826" alt="nevagadores" src="https://github.com/user-attachments/assets/def51d5e-947e-426e-bc6a-84c2e65801bf" />

- Acciones agrupadas en **abrir**, **instalar**, **limpiar** y **perfiles**.
- Chrome, Firefox, Edge, **Brave, Chromium y Vivaldi**: abrir (también privado), instalar y limpiar caché/historial.
- **Perfiles y marcadores**: lista perfiles locales y exporta marcadores a HTML.

### Diccionario y notas

<img width="904" height="831" alt="diccionario" src="https://github.com/user-attachments/assets/764a6ec2-056b-45d7-a03f-25c408133475" />

- Diccionario GNU/Linux en línea (hace falta Internet).

<img width="905" height="828" alt="notas" src="https://github.com/user-attachments/assets/beca1a2b-de5d-4f08-9d61-c36b4d41173a" />

- **Notas** en una carpeta fija del usuario (`Documentos/Manten1d0/Notas` o `Documents/Manten1d0/Notas`), con listado de las últimas y editor `.md` / `.txt`.

### Ayuda y menús

- Menú **Ayuda**: documentación de todas las opciones y ventana Acerca de (versión 0.8.0).
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
sudo apt install -f ./manten1d0_0.8.0_all.deb
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
