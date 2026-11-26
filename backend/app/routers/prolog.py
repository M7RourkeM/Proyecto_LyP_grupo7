"""Consulta directa al motor Prolog: diagnostico de prueba y catalogo."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.prolog.adaptador_base import (AdaptadorProlog, EntradaInvalida, ErrorProlog,
                                       PrologNoDisponible, PrologTimeout)
from app.prolog.fabrica import obtener_adaptador
from app.schemas.comunes import Error
from app.schemas.prolog import CatalogoProlog, DiagnosticoProlog, EntradaDiagnostico

router = APIRouter(prefix="/prolog", tags=["prolog"])
Adaptador = Annotated[AdaptadorProlog, Depends(obtener_adaptador)]

# Codigo HTTP de cada error del motor.
ESTADO_POR_ERROR = [
    (EntradaInvalida, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (PrologNoDisponible, status.HTTP_503_SERVICE_UNAVAILABLE),
    (PrologTimeout, status.HTTP_504_GATEWAY_TIMEOUT),
    (ErrorProlog, status.HTTP_502_BAD_GATEWAY),
]
RESPUESTAS_MOTOR = {
    502: {"model": Error, "description": "Error interno del motor"},
    503: {"model": Error, "description": "Prolog no disponible"},
    504: {"model": Error, "description": "El motor excedio el tiempo"},
}


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
                        **RESPUESTAS_MOTOR})
def diagnosticar(datos: EntradaDiagnostico, adaptador: Adaptador):
    return adaptador.diagnosticar(datos)


@router.get("/catalogo", response_model=CatalogoProlog, responses=RESPUESTAS_MOTOR,
            summary="Sintomas, peticiones, contextos y evidencias que reconoce el motor")
def catalogo(adaptador: Adaptador):
    return adaptador.catalogo()
