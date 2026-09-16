# Guía de contribución

¡Gracias por interesarte en **[Manten1d0](https://github.com/entreunosyceros/manten1d0)**! Es una aplicación de escritorio en **Python** y **Tkinter** para el mantenimiento básico de **Ubuntu**. Cualquier mejora bien planteada es bienvenida.

## Antes de empezar

- Lee el [README](README.md) para entender el alcance del programa (versión actual en `config.ini`).
- El historial de versiones anteriores está en [CHANGELOG.md](CHANGELOG.md).
- Revisa las [issues abiertas](https://github.com/entreunosyceros/manten1d0/issues) por si alguien ya trabaja en lo mismo.
- Para el comportamiento en la comunidad, consulta el [Código de conducta](CODE_OF_CONDUCT.md).
- Para vulnerabilidades, sigue [SECURITY.md](SECURITY.md) (no abras issues públicas con detalles de explotación).

## Cómo puedes ayudar

- **Reportar errores** con pasos claros (versión de Ubuntu, si usas código fuente o el `.deb`).
- **Proponer mejoras** explicando el problema que resuelven.
- **Enviar pull requests** con cambios acotados y probados en Ubuntu.
- **Mejorar documentación** (README, CHANGELOG, comentarios en el código).

## Entorno de desarrollo

Requisitos: **Ubuntu** (probado en 22.04), **Python 3.10+** y `python3-pip`. El programa instala el resto de dependencias al arrancar si faltan (`dependencias.py` y `requirements.txt`).

```bash
git clone https://github.com/entreunosyceros/manten1d0.git
cd manten1d0
python3 index.py
```

`index.py` crea el entorno virtual (`venv/`), instala las dependencias de `requirements.txt` y lanza `main.py`.

### Arranque manual (opcional)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Hace falta `python3-tk`. Si no está, el propio `main.py` intenta instalarlo.

### Comprobar sintaxis

```bash
python3 -m compileall -q .
```

## Estructura del código

| Ruta | Contenido |
|------|-----------|
| `index.py` | Crea `venv`, instala dependencias y arranca la app |
| `main.py` | Ventana principal, menús, bandeja del sistema, categorías |
| `menuCategorias.py` | Pantallas de cada categoría del menú lateral |
| `dependencias.py` | Comprobación e instalación de paquetes APT y pip |
| `password.py` | Contraseña de sudo cifrada (no se escribe en el registro) |
| `registro.py` | Confirmaciones, `acciones.log` e historial de comandos |
| `tooltip.py` | Tooltips (desaparecen al salir el ratón) |
| `bandeja.py` | Icono de bandeja (proceso Qt aparte) |
| `preferencias.py` | Tema claro/oscuro y tamaño de texto |
| `avisos.py` | Avisos de Inicio (disco, APT, SMART, Internet) |
| `documentacion.py` / `about.py` | Ayuda y Acerca de |
| `actualizaciones.py` | Búsqueda de versiones en GitHub Releases |
| `cat_sistema.py`, `cat_sistema_extra.py` | Sistema: limpiezas, SMART, servicios, impresoras… |
| `cat_archivos.py`, `cat_archivos_extra.py` | Copias, cifrado, permisos, USB, hash… |
| `cat_internet.py`, `cat_red_extra.py`, `cat_redLocal.py` | Red, Wi-Fi, DNS, hosts, ruido de enlace |
| `cat_navegadores.py` | Navegadores, caché, perfiles y marcadores |
| `cat_informacion.py` | Informe del equipo |
| `cat_perfil.py` | Datos editables del usuario |
| `cat_editorTexto.py` | Notas |
| `cat_diccionario.py` | Diccionario GNU/Linux |
| `config.ini` | Versión del programa |
| `requirements.txt` | Dependencias pip |

## Estilo de código

- Sigue el estilo del código existente (nombres, imports, nivel de comentarios).
- Cambios **mínimos y enfocados**: no mezcles varias funcionalidades en un mismo PR.
- Los textos visibles para el usuario van en **español**.
- Cada botón nuevo debe tener un **tooltip** descriptivo (`ToolTip` / `con_tooltip`).
- Las tareas largas van en segundo plano (`en_hilo`); no bloquees la interfaz.
- Las acciones sensibles piden **confirmación**.
- **Nunca** registres la contraseña de sudo ni claves Wi-Fi en `acciones.log`, issues o PRs.
- No subas `*.key`, `config.txt`, `acciones.log`, `venv/` ni paquetes `.deb` generados en local.
- No mezcles Qt/`QApplication` en el mismo proceso que Tkinter (la bandeja ya corre aparte).

## Pull requests

1. Crea una rama descriptiva desde `main` (por ejemplo `fix/instalar-deb-cancelar` o `feat/impresoras`).
2. Describe **qué** cambias y **por qué**.
3. Indica cómo lo has probado en Ubuntu (pasos manuales, categoría afectada).
4. Actualiza el README o el CHANGELOG solo si el cambio lo requiere.

Usa la [plantilla de pull request](.github/pull_request_template.md) al abrir el PR.

## Reportar problemas de seguridad

No abras issues públicas para vulnerabilidades. Sigue la [política de seguridad](SECURITY.md).

## Licencia

Al contribuir, aceptas que tu aportación se publique bajo la misma licencia del proyecto.
