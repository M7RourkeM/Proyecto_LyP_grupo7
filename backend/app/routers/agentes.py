"""CRUD de agentes de soporte."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.models import Agente, GrupoResolutor, HistorialTiquete, Tiquete
from app.schemas.comunes import Pagina, ParametrosPagina, errores
from app.schemas.organizacion import AgenteActualizar, AgenteCrear, AgenteRespuesta
from app.services import crud

router = APIRouter(prefix="/agentes", tags=["agentes"])
SesionBD = Annotated[Session, Depends(obtener_sesion)]


@router.get("", response_model=Pagina[AgenteRespuesta], summary="Listar agentes")
def listar(sesion: SesionBD, params: Annotated[ParametrosPagina, Depends()],
           grupo_resolutor_id: Annotated[int | None, Query()] = None,
           activo: Annotated[bool | None, Query()] = None):
    consulta = select(Agente).order_by(Agente.id)
    if grupo_resolutor_id is not None:
        consulta = consulta.where(Agente.grupo_resolutor_id == grupo_resolutor_id)
    if activo is not None:
        consulta = consulta.where(Agente.activo == activo)
    return crud.paginar(sesion, consulta, params)


@router.get("/{agente_id}", response_model=AgenteRespuesta, responses=errores(404),
            summary="Consultar un agente")
def consultar(agente_id: int, sesion: SesionBD):
    return crud.obtener_o_404(sesion, Agente, agente_id, "Agente")


@router.post("", response_model=AgenteRespuesta, status_code=status.HTTP_201_CREATED,
             responses=errores(409, 422), summary="Crear un agente")
def crear(datos: AgenteCrear, sesion: SesionBD):
    crud.verificar_referencias(sesion, {"grupo_resolutor_id": (GrupoResolutor,
                                                               datos.grupo_resolutor_id)})
    crud.verificar_unicos(sesion, Agente, {"correo": datos.correo})
    return crud.guardar(sesion, Agente(**datos.model_dump()))


@router.patch("/{agente_id}", response_model=AgenteRespuesta,
              responses=errores(404, 409, 422), summary="Modificar un agente")
def actualizar(agente_id: int, datos: AgenteActualizar, sesion: SesionBD):
    agente = crud.obtener_o_404(sesion, Agente, agente_id, "Agente")
    cambios = datos.model_dump(exclude_unset=True)
    crud.verificar_referencias(sesion, {"grupo_resolutor_id": (GrupoResolutor,
                                                               cambios.get("grupo_resolutor_id"))})
    crud.verificar_unicos(sesion, Agente, {"correo": cambios.get("correo")}, excluir_id=agente_id)
    crud.aplicar_cambios(agente, cambios)
    return crud.guardar(sesion, agente)


@router.delete("/{agente_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses=errores(404, 409), summary="Eliminar un agente")
def eliminar(agente_id: int, sesion: SesionBD):
    """Solo se elimina si no tiene tiquetes asignados ni cambios en el historial."""
    agente = crud.obtener_o_404(sesion, Agente, agente_id, "Agente")
    crud.verificar_sin_dependencias(sesion, "el agente", {
        "tiquetes asignados": select(func.count()).where(Tiquete.agente_id == agente_id),
        "registros de historial": select(func.count()).where(
            HistorialTiquete.agente_id == agente_id),
    })
    sesion.delete(agente)
    sesion.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
