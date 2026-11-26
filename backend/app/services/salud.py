"""Verificacion del estado de las dependencias externas: Prolog y Ollama.

Ninguna verificacion lanza excepciones: si una dependencia falla, se
reporta como "caido" y la API sigue respondiendo.
"""

import asyncio
import logging
import subprocess

import httpx

from app.config import Configuracion

log = logging.getLogger(__name__)

# Carga la base de conocimiento recibida como argumento y termina con
# codigo 0 solo si la carga no produjo errores. Se toma el ULTIMO
# elemento de argv porque, segun la version y el sistema operativo,
# SWI-Prolog puede incluir antes la ruta del ejecutable. Si ocurre una
# excepcion, se imprime en stderr para que quede en el log.
# halt(0) va FUERA del catch: desde SWI-Prolog 9.3, halt/1 termina
# lanzando la excepcion unwind(halt(_)); dentro de un catch que
# atrapa todo, la salida normal se confundiria con un error.
_OBJETIVO_CARGA_KB = (
    "current_prolog_flag(argv, Argv), last(Argv, Ruta),"
    "catch(load_files(Ruta, [silent(true)]),"
    " E, (print_message(error, E), halt(2))),"
    "halt(0)"
)


def verificar_prolog(config: Configuracion) -> str:
    """Devuelve "ok" si swipl existe y carga la base de conocimiento sin errores."""
    ruta_kb = config.ruta_kb()
    if not ruta_kb.is_file():
        log.warning("Base de conocimiento no encontrada: %s", ruta_kb)
        return "caido"
    comando = [
        config.swipl_ejecutable, "-q",
        "-g", _OBJETIVO_CARGA_KB,
        "-t", "halt(1)",
        "--", str(ruta_kb),
    ]
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=config.salud_timeout_s,
            cwd=ruta_kb.parent,
        )
    except FileNotFoundError:
        log.warning("No se encontro el ejecutable de Prolog: %s", config.swipl_ejecutable)
        return "caido"
    except subprocess.TimeoutExpired:
        log.warning("Prolog excedio el tiempo de espera al cargar la base")
        return "caido"
    # SWI escribe en stderr las advertencias y errores de carga.
    if resultado.returncode != 0 or "error" in resultado.stderr.lower():
        log.warning("Prolog no cargo la base (codigo %s): %s",
                    resultado.returncode, resultado.stderr.strip())
        return "caido"
    return "ok"


async def verificar_ia(config: Configuracion,
                      transporte: httpx.AsyncBaseTransport | None = None) -> str:
    """Devuelve "ok" si Ollama responde y tiene descargado el modelo configurado.

    `transporte` permite simular Ollama en las pruebas.
    """
    try:
        async with httpx.AsyncClient(timeout=config.salud_timeout_s,
                                     transport=transporte) as cliente:
            respuesta = await cliente.get(f"{config.ollama_url}/api/tags")
            respuesta.raise_for_status()
            modelos = {m.get("name") for m in respuesta.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as error:
        log.warning("Ollama no disponible: %s", error)
        return "caido"
    if config.ollama_modelo not in modelos:
        log.warning("Ollama responde, pero no tiene el modelo %s", config.ollama_modelo)
        return "caido"
    return "ok"


async def estado_general(config: Configuracion) -> dict[str, str]:
    """Consulta Prolog e IA en paralelo."""
    prolog, ia = await asyncio.gather(
        asyncio.to_thread(verificar_prolog, config),
        verificar_ia(config),
    )
    return {"api": "ok", "prolog": prolog, "ia": ia}
