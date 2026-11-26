# Backend: Asistente de Diagnóstico y Soporte de TI

Backend de una mesa de servicios de primer nivel alineada con ITIL. Registra incidentes, consulta un motor de inferencia en SWI-Prolog que determina las causas probables, la prioridad, el SLA, los pasos de solución y el escalamiento, y utiliza un modelo de lenguaje local (Ollama) para redactar una guía para el usuario y una nota técnica para el agente. La IA no puede proponer soluciones que no provengan del motor: su respuesta se valida contra el diagnóstico y, si falla, se reemplaza por una plantilla.

## Requisitos

| Herramienta | Versión probada | Instalación en Windows |
|---|---|---|
| Python | 3.12 | python.org |
| SWI-Prolog | 11.0.1 | `winget install --id SWI-Prolog.SWI-Prolog -e` |
| Ollama | 0.40.18 | `winget install --id Ollama.Ollama -e` |
| Modelo de IA | `qwen2.5:3b` (1,9 GB) | `ollama pull qwen2.5:3b` |

Después de instalar SWI-Prolog y Ollama se debe abrir una terminal nueva para que el sistema reconozca los comandos `swipl` y `ollama`. Ollama queda en ejecución en segundo plano después de instalarse.

## Instalación

Todos los comandos se ejecutan en PowerShell, desde la carpeta `backend`.

1. Crear el entorno virtual e instalar las dependencias:
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
2. Copiar la configuración de ejemplo:
   ```
   copy .env.example .env
   ```
3. Crear la base de datos con los datos de prueba (5 departamentos, 7 grupos resolutores, 10 usuarios, 4 agentes y 15 activos, todos ficticios). El script reinicia la base cada vez que se ejecuta:
   ```
   .venv\Scripts\python -m scripts.seed
   ```
4. Opcionalmente, crear 10 tiquetes de ejemplo con fechas pasadas para el panel de indicadores:
   ```
   .venv\Scripts\python -m scripts.seed_tiquetes
   ```
5. Levantar la API:
   ```
   .venv\Scripts\python -m uvicorn app.main:app
   ```
6. Verificar el estado en `http://localhost:8000/salud`, que debe responder `{"api":"ok","prolog":"ok","ia":"ok"}`. La documentación interactiva está en `http://localhost:8000/docs`.

Los comandos usan `.venv\Scripts\python` directamente, así que no es necesario activar el entorno virtual ni cambiar la política de ejecución de PowerShell.

## Configuración

Las opciones se definen en el archivo `.env`. Las más relevantes son:

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `PROLOG_ADAPTADOR` | `subprocess` | `subprocess` (proceso aparte por consulta) o `pyswip` (en el mismo proceso). |
| `PROLOG_KB` | `app/prolog/kb/motor_inferencia.pl` | Base de conocimiento. Se cambia sin modificar código. |
| `SWIPL_EJECUTABLE` | `swipl` | Ruta completa a `swipl.exe` si no está en el PATH. |
| `OLLAMA_MODELO` | `qwen2.5:3b` | Modelo de IA. |
| `OLLAMA_TIMEOUT_S` | `120` | Tiempo máximo por consulta a la IA, en segundos. |
| `IA_HABILITADA` | `true` | Con `false` se usa siempre la plantilla, sin llamar a la IA. |
| `CORRELACION_HORAS` | `24` | Ventana para buscar tiquetes abiertos similares. |
| `RECURRENCIA_MINIMO`, `RECURRENCIA_DIAS` | `3`, `30` | Un usuario o activo es recurrente con N tiquetes de la misma categoría en X días. |
| `JORNADA_INICIO_HORA`, `JORNADA_FIN_HORA` | `8`, `16` | Jornada laboral para medir el SLA en horas hábiles. |

## Pruebas

```
.venv\Scripts\python -m pytest -q
```

Las pruebas usan una base de datos en memoria y no modifican `mesa_servicios.db`. Las que requieren SWI-Prolog se omiten si no está instalado; ninguna prueba llama al modelo de IA real.

Las pruebas propias de la base de conocimiento se ejecutan en SWI-Prolog:

```
cd app\prolog\kb
swipl -q -g correr_pruebas -t halt pruebas_consultas.pl
```

## Demostración

El script `demo` recorre los 7 escenarios de validación del proyecto sobre una base temporal en memoria e indica si cada uno cumple lo esperado:

```
.venv\Scripts\python -m scripts.demo
.venv\Scripts\python -m scripts.demo --sin-ia
```

La opción `--sin-ia` usa solo las plantillas y es más rápida. Para ver con detalle la guía que genera la IA en un escenario se usa `probar_ia`:

```
.venv\Scripts\python -m scripts.probar_ia --escenario correo
```

Los escenarios disponibles son `red`, `correo`, `cuenta` e `impresora`.

## Otros scripts

| Comando | Uso |
|---|---|
| `python -m scripts.init_db` | Crea las tablas que falten (`--reiniciar` las borra antes). |
| `python -m scripts.consulta_sql "SELECT ..."` | Ejecuta una consulta de solo lectura y muestra el resultado en tabla. |

## Documentación

| Documento | Contenido |
|---|---|
| `docs/API.md` | Endpoints, códigos de respuesta y diferencias con el contrato acordado. |
| `docs/ESQUEMA_BD.md` | Diagrama entidad-relación y diccionario de datos. |
| `docs/ARQUITECTURA.md` | Componentes, secuencia del registro de un tiquete y decisiones de diseño. |
| `docs/IA_COSTO_Y_PRIVACIDAD.md` | Modelo, costo, protección de datos y control de la IA. |
| `app/prolog/kb/CAMBIOS.md` | Cambios hechos a la base de conocimiento para integrarla. |

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `swipl` u `ollama` no se reconocen | La terminal se abrió antes de instalarlos. Abrir una terminal nueva. Si persiste en SWI-Prolog, agregar `C:\Program Files\swipl\bin` al PATH o indicar la ruta en `SWIPL_EJECUTABLE`. |
| `/salud` muestra `prolog: caido` | El motivo exacto aparece en la consola de `uvicorn`, en la línea `WARNING app.services.salud`. |
| La API falla al crear tiquetes después de actualizar el código | El modelo de datos cambió. Ejecutar `scripts.seed` para recrear la base. |
| La primera guía tarda más de un minuto | Ollama está cargando el modelo. Las siguientes consultas toman unos 5 segundos. Para precargarlo: `ollama run qwen2.5:3b ""`. |
| `database is locked` | Otro programa (DB Browser o el visor de SQLite de VS Code) tiene la base abierta. Cerrarlo. |
| `The module '.venv' could not be loaded` | La terminal no está en la carpeta `backend`. Ejecutar `cd` a esa carpeta. |
