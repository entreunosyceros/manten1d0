# Política de seguridad

## Versiones con soporte

| Versión | Soportada |
| ------- | --------- |
| 0.6.x   | ✅        |
| < 0.6   | ❌        |

## Alcance

**Manten1d0** es una aplicación de **escritorio** (Python + Tkinter) para mantenimiento de Ubuntu. En el ámbito de seguridad nos interesa especialmente:

- **Contraseña de sudo**: se pide al iniciar, se cifra en local y **no** debe escribirse en `acciones.log` ni en la salida de comandos.
- **Claves Wi-Fi**: al conectar redes con `nmcli` la contraseña no se guarda en el registro.
- **Almacenamiento local**: `*.key`, `config.txt` (contraseña cifrada), `acciones.log`, historial de comandos en `~/.local/share/Manten1d0/` y notas del usuario.
- **Acciones con privilegios**: `sudo`, edición de `/etc/hosts`, DNS, chmod/chown, servicios systemd, instalación de `.deb`.
- **Dependencias**: vulnerabilidades en paquetes de `requirements.txt` o en herramientas del sistema que el programa invoca.

**Fuera de alcance habitual:**

- Fallos del propio APT, CUPS, NetworkManager, SMART o del kernel ajenos a este programa.
- Contenido de las notas o archivos que el usuario abre o cifra voluntariamente.
- Equipos o redes de terceros descubiertos en el escaneo de red local.

## Cómo reportar una vulnerabilidad

1. **No** abras un issue público con detalles del fallo ni pegues contraseñas, claves `.key` o capturas de `acciones.log`.
2. Usa [GitHub Security Advisories](https://github.com/entreunosyceros/manten1d0/security/advisories/new) (**Report a vulnerability**) si tienes acceso.
3. Si no puedes usar Advisories, abre un issue con título `SECURITY (sin detalles)` y pide un canal privado; no incluyas pasos de explotación en público.

Incluye, en la medida de lo posible:

- Descripción del problema y módulo afectado (`password.py`, `registro.py`, `cat_red_extra.py`, etc.).
- Pasos para reproducirlo (sin secretos reales).
- Impacto estimado (privilegios, datos locales, ejecución de comandos).
- Versión (`config.ini`, p. ej. 0.6.0) o commit afectado.
- Versión de Ubuntu y si usas código fuente o el paquete `.deb`.
- Sugerencia de mitigación, si la tienes.

## Qué esperar

- **Acuse de recibo** en un plazo razonable (habitualmente en pocos días).
- Evaluación del informe y, si procede, parche o mitigación en una versión posterior.
- Crédito al informante en las notas de la corrección, salvo que prefiera anonimato.

## Buenas prácticas para usuarios

- No subas `*.key`, `config.txt` ni `acciones.log` a issues, PRs o capturas.
- Clona y descarga el código solo desde el repositorio oficial: [github.com/entreunosyceros/manten1d0](https://github.com/entreunosyceros/manten1d0).
- En equipos compartidos, protege los archivos de clave y el registro local; al salir, el programa intenta limpiar la contraseña cifrada de la sesión.
- Recuerda que **Salir** (menú o bandeja) cierra el programa; ocultar a la bandeja no borra aún esa sesión.
