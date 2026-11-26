"""Adaptador que consulta SWI-Prolog dentro del mismo proceso, con pyswip.

Es mas rapido que subprocess porque la base se carga una sola vez, pero
comparte el proceso con la API:
  - SWI-Prolog embebido no admite consultas simultaneas desde varios
    hilos de Python, por eso todas las consultas pasan por un candado.
  - Solo puede haber una base cargada por proceso.
  - El limite de tiempo lo aplica Prolog (call_with_time_limit en puente.pl).
"""

import threading
from pathlib import Path

from app.config import Configuracion
from app.prolog.adaptador_base import (RUTA_PUENTE, AdaptadorProlog, ErrorProlog,
                                       PrologNoDisponible)

_candado = threading.Lock()
_base_cargada: Path | None = None


def _atomo_prolog(texto: str) -> str:
    """Convierte un texto en un atomo Prolog entre comillas simples."""
    return "'" + texto.replace("\\", "\\\\").replace("'", "\\'") + "'"


class AdaptadorPyswip(AdaptadorProlog):
    nombre = "pyswip"

    def __init__(self, config: Configuracion):
        super().__init__(config)
        try:
            from pyswip import Prolog
        except Exception as error:  # ImportError o biblioteca nativa no encontrada
            raise PrologNoDisponible(f"pyswip no disponible: {error}") from error
        self._prolog = Prolog

    def _cargar_base(self) -> None:
        global _base_cargada
        if _base_cargada == self.ruta_kb:
            return
        if _base_cargada is not None:
            raise ErrorProlog(f"pyswip ya cargo {_base_cargada}; reinicie la API para "
                              f"usar {self.ruta_kb}")
        if not self.ruta_kb.is_file():
            raise PrologNoDisponible(f"No existe la base de conocimiento: {self.ruta_kb}")
        for ruta in (self.ruta_kb, RUTA_PUENTE):
            list(self._prolog.query(f"load_files({_atomo_prolog(ruta.as_posix())}, "
                                    "[silent(true)])"))
        _base_cargada = self.ruta_kb

    def _ejecutar(self, texto_entrada: str) -> str:
        with _candado:
            self._cargar_base()
            try:
                respuestas = list(self._prolog.query(
                    f"diagnostico_json({_atomo_prolog(texto_entrada)}, Salida)"))
            except Exception as error:  # PrologError de pyswip
                raise ErrorProlog(f"Error al consultar Prolog: {error}") from error
        if not respuestas:
            raise ErrorProlog("El puente no devolvio respuesta")
        salida = respuestas[0]["Salida"]
        return salida.decode("utf-8") if isinstance(salida, bytes) else str(salida)
