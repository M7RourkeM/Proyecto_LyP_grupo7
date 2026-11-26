"""Interfaz comun de los adaptadores de Prolog y errores del motor.

Los adaptadores no interpretan el diagnostico: envian el tiquete en JSON
a puente.pl y reciben el diagnostico en JSON. Lo unico que cambia entre
implementaciones es como se transporta ese texto (_ejecutar).
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from app.config import Configuracion
from app.schemas.prolog import (DiagnosticoProlog, EntradaDiagnostico, IncidenteAbierto,
                                ResultadoPrevio)

RUTA_PUENTE = Path(__file__).resolve().parent / "puente.pl"


class ErrorProlog(Exception):
    """Error del motor. `codigo` coincide con los errores de puente.pl."""

    codigo = "error_prolog"

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


class PrologNoDisponible(ErrorProlog):
    codigo = "no_disponible"


class PrologTimeout(ErrorProlog):
    codigo = "timeout"


class PredicadoInexistente(ErrorProlog):
    codigo = "predicado_inexistente"


class EntradaInvalida(ErrorProlog):
    codigo = "entrada_invalida"

    def __init__(self, detalle: str, desconocidos: list[str]):
        super().__init__(detalle)
        self.desconocidos = desconocidos


class AdaptadorProlog(ABC):
    nombre = "base"

    def __init__(self, config: Configuracion):
        self.config = config
        self.ruta_kb = config.ruta_kb()

    def diagnosticar(self, entrada: EntradaDiagnostico,
                     incidentes_abiertos: Sequence[IncidenteAbierto] = (),
                     resultados_previos: Sequence[ResultadoPrevio] = ()) -> DiagnosticoProlog:
        if not self.ruta_kb.is_file():
            raise PrologNoDisponible(f"No existe la base de conocimiento: {self.ruta_kb}")
        texto = self._armar_json(entrada, incidentes_abiertos, resultados_previos)
        return self._interpretar(self._ejecutar(texto))

    @abstractmethod
    def _ejecutar(self, texto_entrada: str) -> str:
        """Envia el JSON a puente.pl y devuelve el JSON de respuesta."""

    def _armar_json(self, entrada: EntradaDiagnostico,
                    incidentes: Sequence[IncidenteAbierto],
                    resultados: Sequence[ResultadoPrevio]) -> str:
        datos = entrada.model_dump()
        datos["incidentes_abiertos"] = [i.model_dump() for i in incidentes]
        datos["resultados_previos"] = [r.model_dump() for r in resultados]
        datos["timeout_s"] = self.config.prolog_timeout_s
        # ensure_ascii: el texto viaja solo con caracteres ASCII, sin depender
        # de la codificacion de la consola de Windows.
        return json.dumps(datos, ensure_ascii=True)

    @staticmethod
    def _interpretar(texto_salida: str) -> DiagnosticoProlog:
        try:
            datos = json.loads(texto_salida)
        except json.JSONDecodeError as error:
            raise ErrorProlog(f"Respuesta del motor no es JSON: {texto_salida[:200]!r}") from error
        if "error" in datos:
            raise _error_desde_json(datos)
        try:
            return DiagnosticoProlog.model_validate(datos)
        except ValidationError as error:
            raise ErrorProlog(f"Respuesta del motor no cumple el contrato 3.2: {error}") from error


def _error_desde_json(datos: dict) -> ErrorProlog:
    codigo, detalle = datos["error"], datos.get("detalle", "")
    if codigo == "entrada_invalida":
        return EntradaInvalida(detalle, datos.get("desconocidos", []))
    clases = {c.codigo: c for c in (PrologTimeout, PredicadoInexistente)}
    return clases.get(codigo, ErrorProlog)(detalle)
