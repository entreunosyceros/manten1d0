# Historial de versiones

Cambios de Manten1d0 anteriores a la [versión 0.6.0](README.md).

------------------------------------------------------------------

## Versión 0.5.7

![logs](https://github.com/sapoclay/manten1d0/assets/6242827/2e742038-8c1d-4de6-9aa8-c3639ba54f38)

- Añadida la consulta de logs del sistema a la opción Sistema.
- En Archivos, búsqueda recursiva en todo el sistema. Doble clic abre Nautilus en la carpeta del archivo. Acepta comodines `*` y `?`.

![renombrar-archivos](https://github.com/sapoclay/manten1d0/assets/6242827/49915632-ad65-4238-8d76-cf4ceb15a230)

- Renombrado masivo: se elige una carpeta, un prefijo y se aplica un número incremental a todos los archivos. También permite abrir la carpeta con Nautilus.

## Versión 0.5.6

![editor-texto](https://github.com/sapoclay/manten1d0/assets/6242827/a46abeb2-244f-434e-a1b9-ee8425507cd9)

- Editor de texto básico para tomar notas (`.md` y `.txt`). Menú contextual, recuento de palabras y caracteres, búsqueda con resaltado.
- Corrección de tooltips.
- Información de la tarjeta gráfica con `lspci` y `lshw`. Si hay NVIDIA se usa `nvidia-smi` para temperatura y memoria.
- Reparados errores al instalar paquetes `.deb` si no se selecciona archivo.
- Optimizados el test de velocidad, el diagnóstico de red y el escáner de puertos.
- Botones para abrir Firefox, Chrome o Edge, también en modo incógnito.
- En Red Local, detección automática de la red (ya no tiene que ser 192.168.x.x). La conexión se hace por Samba con Nautilus.
- Valores numéricos en la monitorización del sistema.
- Correcciones al cerrar la aplicación.

## Versión 0.5.5

- Corregido y optimizado el sistema de actualización del programa.
- Comprobación de dependencias simplificada: pip3 en `requirements.txt` y APT en `dependencias.py`.
- Permisos de `config.ini` ajustados para la lectura desde el paquete `.deb`.
- Modificar perfil de usuario (nombre visible, contraseña y fotografía; requiere sudo).
- Sistema: instalar un archivo `.deb` con `dpkg`.

![desinstalar](https://github.com/sapoclay/manten1d0/assets/6242827/06dfeed0-a1f2-428d-b461-a3b812392876)

- Desinstalar paquetes snap y deb del usuario, con búsqueda dinámica.
- Abrir el repositorio de GitHub desde Preferencias.

![conexion-internet](https://github.com/sapoclay/manten1d0/assets/6242827/2c714f02-b0e9-4106-9c61-2dc2e1a441c9)

- Indicador de conexión a Internet en el menú lateral (verde / rojo).
- Instalación de Firefox, Chrome y Edge en Navegadores.
- Reparados errores en la gestión de repositorios.
- Correcciones menores.

## Versión 0.5.4

- En Internet: Escanear puertos, Test de velocidad y Diagnóstico de red.

## Versión 0.5.3

- Menú lateral vertical por categorías; cada una muestra sus herramientas en el área central.
- Ping a URL en Internet.
- Tema claro u oscuro y tamaño de fuente.
- Abrir URL en el navegador desde el menú Archivo.
- Monitorización del sistema con un gráfico del momento.
- El tooltip desaparece al hacer clic en el botón.
- Limpiar historial de Chrome, Firefox y Edge.
- Si falta `python3-tk`, se instala al iniciar y el programa continúa.

![opciones-archivos](https://github.com/sapoclay/manten1d0/assets/6242827/f0d64f77-03b9-40d9-91bf-9c3c2a9c2c5d)

- Copias de seguridad de carpetas en `.gz` con `tar`, y restauración.
- Cifrado y descifrado de archivos con ChaCha20.

## Versión 0.5.2

- Búsqueda de archivos duplicados por hash SHA-256. Muestra original y copias, permite seleccionar y eliminar. Scroll con rueda o teclado.
- Doble clic sobre un duplicado abre su ubicación en Nautilus.
- Tooltips explicativos en los botones.

## Versión 0.5.1

- En el menú principal: eliminar archivos y carpetas, o vaciar la papelera.
- Buscar actualizaciones.

## Versión 0.5.0

Descripción inicial del programa (almacenar contraseña, comprobar dependencias, interfaz por categorías, información del sistema, Internet, navegadores, diccionario, tema y preferencias).

![password-manten1d0](https://github.com/sapoclay/manten1d0/assets/6242827/c45a7157-1cf4-42bc-86da-54db4e03c69e)

- Contraseña de sudo almacenada de forma cifrada; se pide una vez al iniciar.

![comprobando-dependencias](https://github.com/sapoclay/manten1d0/assets/6242827/f8f7487e-7973-4741-ac72-90734b35a9c4)

- Al arrancar se comprueban e instalan las dependencias que falten.

![interfaz](https://github.com/sapoclay/manten1d0/assets/6242827/80f57daf-97a6-4212-b1c0-da5c61a64000)

- Interfaz con menú lateral de categorías y menú superior.

![info-SO](https://github.com/sapoclay/manten1d0/assets/6242827/729081ad-5f20-4911-9fe7-cc1b31495942)

- Categoría Información: sistema, red, procesador y memoria.

![sistema](https://github.com/sapoclay/manten1d0/assets/6242827/d8a4cb09-9b22-4489-80f7-6a130af56b7b)

- Categoría Sistema: operaciones de mantenimiento. El tooltip explica cada botón.

![opcion-internet](https://github.com/sapoclay/manten1d0/assets/6242827/ba3f444c-ac31-4312-8409-23bc3cd18f15)

- Internet: reiniciar la tarjeta de red seleccionada y hacer ping.

![navegadores](https://github.com/sapoclay/manten1d0/assets/6242827/dc6c5b5b-dfc0-4979-8af9-0e5dab6f6a40)

- Navegadores: limpiar caché e instalar Chrome, Firefox o Edge.

![diccionario](https://github.com/sapoclay/manten1d0/assets/6242827/8f41ebb9-9250-49f9-807e-545cb1f86eda)

- Diccionario GNU/Linux desde una URL, búsqueda en Markdown y terminal para probar comandos.

![tema-oscuro](https://github.com/sapoclay/manten1d0/assets/6242827/9cf5c903-c237-4a53-a5ba-5203e0a02236)

- Tema claro u oscuro y tamaño de texto en Preferencias.
- Búsqueda automática de actualizaciones.
- Abrir una URL en el navegador del sistema desde el menú Archivo.
