"""Consulta directa al motor Prolog, sin crear tiquetes.

Sirve para que el equipo pruebe la base de conocimiento desde Swagger.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.config import Configuracion, obtener_configuracion
from app.prolog.adaptador_base import (EntradaInvalida, ErrorProlog, PrologNoDisponible,
                                       PrologTimeout)
from app.prolog.fabrica import crear_adaptador
from app.schemas.comunes import Error
from app.schemas.prolog import DiagnosticoProlog, EntradaDiagnostico

router = APIRouter(prefix="/prolog", tags=["prolog"])

# Codigo HTTP de cada error del motor.
ESTADO_POR_ERROR = [
    (EntradaInvalida, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (PrologNoDisponible, status.HTTP_503_SERVICE_UNAVAILABLE),
    (PrologTimeout, status.HTTP_504_GATEWAY_TIMEOUT),
    (ErrorProlog, status.HTTP_502_BAD_GATEWAY),
]


def respuesta_error_prolog(_peticion: Request, error: ErrorProlog) -> JSONResponse:
    """Manejador global: los errores del motor nunca se convierten en un 500."""
    codigo_http = next(c for clase, c in ESTADO_POR_ERROR if isinstance(error, clase))
    contenido = {"detail": error.detalle, "codigo": error.codigo}
    if isinstance(error, EntradaInvalida):
        contenido["desconocidos"] = error.desconocidos
    return JSONResponse(contenido, status_code=codigo_http)


@router.post("/diagnostico", response_model=DiagnosticoProlog,
             summary="Consultar el motor de inferencia sin crear un tiquete",
             responses={422: {"model": Error, "description": "Sintoma que el motor no reconoce"},
                        502: {"model": Error, "description": "Error interno del motor"},
                        503: {"model": Error, "description": "Prolog no disponible"},
                        504: {"model": Error, "description": "El motor excedio el tiempo"}})
def diagnosticar(datos: EntradaDiagnostico,
                 config: Annotated[Configuracion, Depends(obtener_configuracion)]):
    try:
        adaptador = crear_adaptador(config)
    except KeyError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Adaptador desconocido: {config.prolog_adaptador}") from error
    return adaptador.diagnosticar(datos)
