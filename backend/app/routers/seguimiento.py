"""Retroalimentacion, historial por usuario y activo, e indicadores del panel."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Configuracion, obtener_configuracion
from app.database import obtener_sesion
from app.models import Activo, Retroalimentacion, Tiquete, Usuario
from app.schemas.comunes import errores
from app.schemas.seguimiento import (EstadisticasRetroalimentacion, Historial, Indicadores,
                                     RetroalimentacionCrear, RetroalimentacionRespuesta)
from app.services import crud, indicadores, retroalimentacion

router = APIRouter()
SesionBD = Annotated[Session, Depends(obtener_sesion)]
Config = Annotated[Configuracion, Depends(obtener_configuracion)]


# --- Retroalimentacion -------------------------------------------------------

@router.post("/tiquetes/{tiquete_id}/retroalimentacion", tags=["retroalimentacion"],
             response_model=RetroalimentacionRespuesta, status_code=status.HTTP_201_CREATED,
             responses=errores(404, 409, 422), summary="Registrar si la solucion funciono")
def registrar_retroalimentacion(tiquete_id: int, datos: RetroalimentacionCrear,
                                sesion: SesionBD):
    """Solo para tiquetes resueltos o cerrados, una vez por tiquete."""
    tiquete = crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete")
    try:
        return retroalimentacion.registrar(sesion, tiquete, datos)
    except retroalimentacion.RetroalimentacionNoPermitida as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except retroalimentacion.DatosRetroalimentacionInvalidos as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error


@router.get("/tiquetes/{tiquete_id}/retroalimentacion", tags=["retroalimentacion"],
            response_model=RetroalimentacionRespuesta, responses=errores(404),
            summary="Consultar la retroalimentacion de un tiquete")
def consultar_retroalimentacion(tiquete_id: int, sesion: SesionBD):
    crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete")
    registro = sesion.scalar(select(Retroalimentacion).where(
        Retroalimentacion.tiquete_id == tiquete_id))
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"El tiquete {tiquete_id} no tiene retroalimentacion")
    return registro


@router.get("/retroalimentacion/estadisticas", tags=["retroalimentacion"],
            response_model=EstadisticasRetroalimentacion,
            summary="Efectividad de las soluciones por causa y por paso")
def estadisticas(sesion: SesionBD):
    return retroalimentacion.estadisticas(sesion)


@router.get("/retroalimentacion/hechos.pl", tags=["retroalimentacion"],
            response_class=PlainTextResponse,
            summary="Retroalimentacion como hechos Prolog resultado_solucion/2")
def hechos_prolog(sesion: SesionBD):
    """Archivo que el Integrante 1 puede cargar en SWI-Prolog para revisar la base."""
    return PlainTextResponse(retroalimentacion.hechos_prolog(sesion),
                             media_type="text/plain; charset=utf-8")


# --- Historial ---------------------------------------------------------------

@router.get("/usuarios/{usuario_id}/historial", tags=["historial"], response_model=Historial,
            responses=errores(404), summary="Tiquetes de un usuario y sus recurrencias")
def historial_usuario(usuario_id: int, sesion: SesionBD, config: Config):
    crud.obtener_o_404(sesion, Usuario, usuario_id, "Usuario")
    return indicadores.historial(sesion, config, Tiquete.usuario_id, usuario_id)


@router.get("/activos/{activo_id}/historial", tags=["historial"], response_model=Historial,
            responses=errores(404), summary="Tiquetes de un activo y sus recurrencias")
def historial_activo(activo_id: int, sesion: SesionBD, config: Config):
    crud.obtener_o_404(sesion, Activo, activo_id, "Activo")
    return indicadores.historial(sesion, config, Tiquete.activo_id, activo_id)


# --- Indicadores -------------------------------------------------------------

@router.get("/indicadores", tags=["indicadores"], response_model=Indicadores,
            summary="Indicadores del panel de la mesa de servicios")
def obtener_indicadores(sesion: SesionBD, config: Config,
                        desde: Annotated[datetime | None, Query(
                            description="Solo tiquetes creados desde esta fecha (ISO 8601)")] = None,
                        hasta: Annotated[datetime | None, Query()] = None):
    for fecha in (desde, hasta):
        if fecha is not None and fecha.tzinfo is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "Las fechas deben incluir zona horaria, ej. 2026-11-01T00:00:00-06:00")
    return indicadores.calcular(sesion, config, desde, hasta)
