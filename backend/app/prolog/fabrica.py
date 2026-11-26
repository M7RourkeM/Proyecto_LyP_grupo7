"""Elige el adaptador de Prolog segun PROLOG_ADAPTADOR en .env."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.config import Configuracion, obtener_configuracion
from app.prolog.adaptador_base import AdaptadorProlog
from app.prolog.adaptador_pyswip import AdaptadorPyswip
from app.prolog.adaptador_subprocess import AdaptadorSubprocess

ADAPTADORES: dict[str, type[AdaptadorProlog]] = {
    "subprocess": AdaptadorSubprocess,
    "pyswip": AdaptadorPyswip,
}


def crear_adaptador(config: Configuracion) -> AdaptadorProlog:
    return ADAPTADORES[config.prolog_adaptador](config)


def obtener_adaptador(
        config: Annotated[Configuracion, Depends(obtener_configuracion)]) -> AdaptadorProlog:
    """Dependencia de FastAPI; en las pruebas se reemplaza por un adaptador simulado."""
    try:
        return crear_adaptador(config)
    except KeyError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Adaptador desconocido: {config.prolog_adaptador}") from error
