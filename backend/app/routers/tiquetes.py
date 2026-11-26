"""Tiquetes: registro con diagnostico, consulta y ciclo de vida."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Configuracion, obtener_configuracion
from app.database import obtener_sesion
from app.ia.cliente_ollama import ClienteOllama, obtener_cliente_ia
from app.models import Tiquete
from app.prolog.adaptador_base import AdaptadorProlog
from app.prolog.fabrica import obtener_adaptador
from app.routers.prolog import RESPUESTAS_MOTOR
from app.schemas.comunes import Pagina, ParametrosPagina, errores
from app.schemas.tiquetes import (AuditoriaIA, CreacionRespuesta, Estado, HistorialRespuesta,
                                  TiqueteCrear, TiqueteDetalle, TiqueteResumen,
                                  TransicionCrear)
from app.services import ciclo_vida, correlacion, crud, diagnostico_service

router = APIRouter(prefix="/tiquetes", tags=["tiquetes"])
SesionBD = Annotated[Session, Depends(obtener_sesion)]
Adaptador = Annotated[AdaptadorProlog, Depends(obtener_adaptador)]
Config = Annotated[Configuracion, Depends(obtener_configuracion)]
ClienteIA = Annotated[ClienteOllama | None, Depends(obtener_cliente_ia)]


def _error_http(error: Exception) -> HTTPException:
    """Traduce las excepciones de los servicios a respuestas HTTP."""
    codigos = {
        ciclo_vida.TransicionInvalida: status.HTTP_409_CONFLICT,
        diagnostico_service.DiagnosticoExistente: status.HTTP_409_CONFLICT,
        ciclo_vida.DatosTransicionInvalidos: status.HTTP_422_UNPROCESSABLE_CONTENT,
        diagnostico_service.ReferenciaInvalida: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
    return HTTPException(codigos[type(error)], str(error))


ERRORES_SERVICIO = (ciclo_vida.TransicionInvalida, ciclo_vida.DatosTransicionInvalidos,
                    diagnostico_service.DiagnosticoExistente,
                    diagnostico_service.ReferenciaInvalida)


@router.post("", response_model=CreacionRespuesta, status_code=status.HTTP_201_CREATED,
             responses={**errores(422), **RESPUESTAS_MOTOR},
             summary="Registrar un tiquete y diagnosticarlo")
def crear(datos: TiqueteCrear, sesion: SesionBD, adaptador: Adaptador, config: Config,
          cliente_ia: ClienteIA):
    """Busca incidentes abiertos similares, consulta al motor Prolog, guarda el
    diagnostico y genera con IA la guia para el usuario y la nota tecnica (si la
    IA no responde, se usan plantillas). Si el motor no esta disponible, el
    tiquete se registra sin diagnostico y la respuesta incluye un aviso."""
    try:
        tiquete, aviso = diagnostico_service.crear_tiquete(sesion, datos, adaptador, config,
                                                           cliente_ia)
    except ERRORES_SERVICIO as error:
        raise _error_http(error) from error
    return {"tiquete": tiquete, "aviso": aviso,
            "recurrencia": correlacion.recurrencia(sesion, config, tiquete)}


@router.get("", response_model=Pagina[TiqueteResumen], summary="Listar tiquetes")
def listar(sesion: SesionBD, params: Annotated[ParametrosPagina, Depends()],
           estado: Annotated[Estado | None, Query()] = None,
           prioridad: Annotated[str | None, Query(pattern=r"^p[1-4]$")] = None,
           departamento_id: Annotated[int | None, Query()] = None,
           grupo_resolutor_id: Annotated[int | None, Query()] = None,
           usuario_id: Annotated[int | None, Query()] = None,
           activo_id: Annotated[int | None, Query()] = None):
    filtros = {"estado": estado, "prioridad": prioridad, "departamento_id": departamento_id,
               "grupo_resolutor_id": grupo_resolutor_id, "usuario_id": usuario_id,
               "activo_id": activo_id}
    consulta = select(Tiquete).order_by(Tiquete.id.desc())
    for campo, valor in filtros.items():
        if valor is not None:
            consulta = consulta.where(getattr(Tiquete, campo) == valor)
    return crud.paginar(sesion, consulta, params)


@router.get("/{tiquete_id}", response_model=TiqueteDetalle, responses=errores(404),
            summary="Consultar un tiquete con su diagnostico e historial")
def consultar(tiquete_id: int, sesion: SesionBD):
    return crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete")


@router.post("/{tiquete_id}/transiciones", response_model=TiqueteDetalle,
             responses=errores(404, 409, 422), summary="Cambiar el estado del tiquete")
def cambiar_estado(tiquete_id: int, datos: TransicionCrear, sesion: SesionBD):
    """Transiciones permitidas: registrado -> en_atencion | escalado;
    en_atencion -> escalado | resuelto; escalado -> en_atencion | resuelto;
    resuelto -> cerrado | en_atencion (reapertura). Cerrado es final."""
    tiquete = crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete")
    try:
        ciclo_vida.transicionar(sesion, tiquete, datos.estado, agente_id=datos.agente_id,
                                comentario=datos.comentario,
                                grupo_id=datos.grupo_resolutor_id)
    except ERRORES_SERVICIO as error:
        sesion.rollback()
        raise _error_http(error) from error
    sesion.commit()
    return tiquete


@router.get("/{tiquete_id}/historial", response_model=list[HistorialRespuesta],
            responses=errores(404), summary="Historial de estados del tiquete")
def historial(tiquete_id: int, sesion: SesionBD):
    return crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete").historial


@router.post("/{tiquete_id}/diagnostico", response_model=CreacionRespuesta,
             responses={**errores(404, 409, 422), **RESPUESTAS_MOTOR},
             summary="Reintentar el diagnostico de un tiquete registrado sin el")
def reintentar(tiquete_id: int, sesion: SesionBD, adaptador: Adaptador, config: Config,
               cliente_ia: ClienteIA):
    tiquete = crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete")
    try:
        aviso = diagnostico_service.reintentar_diagnostico(sesion, tiquete, adaptador, config,
                                                           cliente_ia)
    except ERRORES_SERVICIO as error:
        raise _error_http(error) from error
    return {"tiquete": tiquete, "aviso": aviso,
            "recurrencia": correlacion.recurrencia(sesion, config, tiquete)}


@router.get("/{tiquete_id}/ia", response_model=AuditoriaIA, responses=errores(404),
            summary="Auditoria de la IA: prompt enviado y resultado")
def auditoria_ia(tiquete_id: int, sesion: SesionBD):
    """Muestra exactamente lo que se envio a la IA (ya sanitizado) y si la guia
    salio de la IA (ia_ok, ia_reintento) o de la plantilla (fallback)."""
    tiquete = crud.obtener_o_404(sesion, Tiquete, tiquete_id, "Tiquete")
    if tiquete.diagnostico is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El tiquete no tiene diagnostico")
    return tiquete.diagnostico
