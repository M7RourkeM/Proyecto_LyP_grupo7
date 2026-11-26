# Backend: Asistente de Diagnóstico y Soporte de TI

API en FastAPI que registra tiquetes, consulta el motor de inferencia en Prolog y genera, con IA generativa local, una guía para el usuario y una nota técnica para el agente.

## Requisitos

| Herramienta | Versión probada | Instalación en Windows |
|---|---|---|
| Python | 3.12 | python.org |
| SWI-Prolog | 11.0.1 | `winget install --id SWI-Prolog.SWI-Prolog -e` |
| Ollama | 0.40.18 | `winget install --id Ollama.Ollama -e` |
| Modelo de IA | qwen2.5:3b (1,9 GB) | `ollama pull qwen2.5:3b` |

## Instalación (PowerShell, desde la carpeta `backend`)

1. Crear el entorno virtual e instalar las dependencias:
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
2. Copiar la configuración de ejemplo:
   ```
   copy .env.example .env
   ```
3. Crear la base de datos y cargar los datos de prueba (5 departamentos, 7 grupos resolutores, 10 usuarios, 4 agentes y 15 activos, todos ficticios). El script reinicia la base cada vez que se ejecuta:
   ```
   .venv\Scripts\python -m scripts.seed
   ```
   Opcionalmente, para tener datos en el panel de indicadores, crear 10 tiquetes de ejemplo con fechas pasadas (requiere SWI-Prolog):
   ```
   .venv\Scripts\python -m scripts.seed_tiquetes
   ```
4. Levantar la API:
   ```
   .venv\Scripts\python -m uvicorn app.main:app --reload
   ```
5. Verificar el estado en `http://localhost:8000/salud` y la documentación en `http://localhost:8000/docs`.

Los comandos usan `.venv\Scripts\python` directamente, así que no hace falta activar el entorno ni cambiar la política de ejecución de PowerShell.

## Pruebas

```
.venv\Scripts\python -m pytest -q
```

## Base de conocimiento

Los archivos Prolog están en `app/prolog/kb/`. Para usar otra versión de la base basta con cambiar `PROLOG_KB` en `.env`, sin tocar código.

El backend se comunica con el motor por medio de `app/prolog/puente.pl`, que recibe el tiquete en JSON, llama a `diagnostico_completo/4` y devuelve el diagnóstico en JSON. Hay dos adaptadores, que se eligen con `PROLOG_ADAPTADOR` en `.env`:

- `subprocess` (por defecto): ejecuta `swipl` como proceso aparte en cada consulta. Es más lento, pero aislado: un error en Prolog no afecta a la API.
- `pyswip`: carga la base una sola vez dentro del proceso de la API. Es más rápido, pero requiere reiniciar la API si cambia la base.

Para probar el motor sin crear tiquetes se puede usar `POST /prolog/diagnostico` desde `/docs`.
