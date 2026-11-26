"""Cliente HTTP de Ollama (IA local, sin costo).

API usada: POST {OLLAMA_URL}/api/chat con stream=false y un esquema JSON en
"format" (salida estructurada). La respuesta trae el texto en message.content.
Ante una falla de red o un timeout se reintenta una vez; si vuelve a fallar
se lanza ErrorIA y el llamador usa la plantilla de respaldo.
"""

import logging
from typing import Annotated

import httpx
from fastapi import Depends

from app.config import Configuracion, obtener_configuracion

log = logging.getLogger(__name__)
INTENTOS_RED = 2  # el primero y un reintento


class ErrorIA(Exception):
    """Ollama no respondio o respondio algo inutilizable."""


class ClienteOllama:
    def __init__(self, config: Configuracion, transporte: httpx.BaseTransport | None = None):
        self.config = config
        self.transporte = transporte

    def generar(self, mensajes: list[dict], esquema: dict) -> str:
        cuerpo = {
            "model": self.config.ollama_modelo,
            "messages": mensajes,
            "stream": False,
            "format": esquema,
            "options": {"temperature": self.config.ollama_temperatura},
            "keep_alive": self.config.ollama_keep_alive,
        }
        ultimo_error: Exception | None = None
        for intento in range(1, INTENTOS_RED + 1):
            try:
                return self._enviar(cuerpo)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as error:
                ultimo_error = error
                log.warning("Ollama fallo (intento %s de %s): %s", intento, INTENTOS_RED, error)
        raise ErrorIA(f"Ollama no respondio: {ultimo_error}")

    def precargar(self) -> None:
        """Carga el modelo en memoria con una consulta vacia (sin mensajes), para que
        el primer tiquete no espere la carga. Si falla, solo se registra."""
        cuerpo = {"model": self.config.ollama_modelo, "keep_alive": self.config.ollama_keep_alive}
        try:
            with httpx.Client(timeout=self.config.ollama_timeout_s,
                              transport=self.transporte) as cliente:
                cliente.post(f"{self.config.ollama_url}/api/chat", json=cuerpo).raise_for_status()
            log.info("Modelo %s precargado en Ollama", self.config.ollama_modelo)
        except httpx.HTTPError as error:
            log.warning("No se pudo precargar el modelo: %s", error)

    def _enviar(self, cuerpo: dict) -> str:
        with httpx.Client(timeout=self.config.ollama_timeout_s,
                          transport=self.transporte) as cliente:
            respuesta = cliente.post(f"{self.config.ollama_url}/api/chat", json=cuerpo)
            respuesta.raise_for_status()
        try:
            return respuesta.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as error:
            raise ErrorIA(f"Respuesta de Ollama con formato inesperado: {error}") from error


def obtener_cliente_ia(
        config: Annotated[Configuracion, Depends(obtener_configuracion)]) -> ClienteOllama | None:
    """Dependencia de FastAPI. None si la IA esta deshabilitada (se usa la plantilla)."""
    return ClienteOllama(config) if config.ia_habilitada else None
