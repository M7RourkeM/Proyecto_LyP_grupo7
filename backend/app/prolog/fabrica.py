"""Elige el adaptador de Prolog segun PROLOG_ADAPTADOR en .env."""

from app.config import Configuracion
from app.prolog.adaptador_base import AdaptadorProlog
from app.prolog.adaptador_pyswip import AdaptadorPyswip
from app.prolog.adaptador_subprocess import AdaptadorSubprocess

ADAPTADORES: dict[str, type[AdaptadorProlog]] = {
    "subprocess": AdaptadorSubprocess,
    "pyswip": AdaptadorPyswip,
}


def crear_adaptador(config: Configuracion) -> AdaptadorProlog:
    return ADAPTADORES[config.prolog_adaptador](config)
