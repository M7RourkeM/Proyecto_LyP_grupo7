"""CRUD de activos (equipos)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.models import Activo, Departamento, Tiquete, Usuario
from app.schemas.comunes import Pagina, ParametrosPagina, errores
from app.schemas.organizacion import (ActivoActualizar, ActivoCrear, ActivoRespuesta,
                                      TipoActivo)
from app.services import crud

router = APIRouter(prefix="/activos", tags=["activos"])
SesionBD = Annotated[Session, Depends(obtener_sesion)]


def verificar_usuario_activo(sesion: Session, usuario_id: int | None) -> None:
    """No se asignan equipos a usuarios desactivados."""
    if usuario_id is None:
        return
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is not None and not usuario.activo:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"El usuario {usuario_id} esta desactivado")


@router.get("", response_model=Pagina[ActivoRespuesta], summary="Listar activos")
def listar(sesion: SesionBD, params: Annotated[ParametrosPagina, Depends()],
           departamento_id: Annotated[int | None, Query()] = None,
           usuario_id: Annotated[int | None, Query()] = None,
           tipo: Annotated[TipoActivo | None, Query()] = None):
    consulta = select(Activo).order_by(Activo.id)
    if departamento_id is not None:
        consulta = consulta.where(Activo.departamento_id == departamento_id)
    if usuario_id is not None:
        consulta = consulta.where(Activo.usuario_id == usuario_id)
    if tipo is not None:
        consulta = consulta.where(Activo.tipo == tipo)
    return crud.paginar(sesion, consulta, params)


@router.get("/{activo_id}", response_model=ActivoRespuesta, responses=errores(404),
            summary="Consultar un activo")
def consultar(activo_id: int, sesion: SesionBD):
    return crud.obtener_o_404(sesion, Activo, activo_id, "Activo")


@router.post("", response_model=ActivoRespuesta, status_code=status.HTTP_201_CREATED,
             responses=errores(409, 422), summary="Registrar un activo")
def crear(datos: ActivoCrear, sesion: SesionBD):
    crud.verificar_referencias(sesion, {"departamento_id": (Departamento, datos.departamento_id),
                                        "usuario_id": (Usuario, datos.usuario_id)})
    verificar_usuario_activo(sesion, datos.usuario_id)
    crud.verificar_unicos(sesion, Activo, {"codigo_inventario": datos.codigo_inventario})
    return crud.guardar(sesion, Activo(**datos.model_dump()))


@router.patch("/{activo_id}", response_model=ActivoRespuesta,
              responses=errores(404, 409, 422), summary="Modificar o reasignar un activo")
def actualizar(activo_id: int, datos: ActivoActualizar, sesion: SesionBD):
    activo = crud.obtener_o_404(sesion, Activo, activo_id, "Activo")
    cambios = datos.model_dump(exclude_unset=True)
    crud.verificar_referencias(sesion, {
        "departamento_id": (Departamento, cambios.get("departamento_id")),
        "usuario_id": (Usuario, cambios.get("usuario_id"))})
    verificar_usuario_activo(sesion, cambios.get("usuario_id"))
    crud.verificar_unicos(sesion, Activo, {"codigo_inventario": cambios.get("codigo_inventario")},
                          excluir_id=activo_id)
    crud.aplicar_cambios(activo, cambios)
    return crud.guardar(sesion, activo)


@router.delete("/{activo_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses=errores(404, 409), summary="Dar de baja un activo")
def eliminar(activo_id: int, sesion: SesionBD):
    """Solo se elimina si ningun tiquete lo referencia (se pierde su historial)."""
    activo = crud.obtener_o_404(sesion, Activo, activo_id, "Activo")
    crud.verificar_sin_dependencias(sesion, "el activo", {
        "tiquetes": select(func.count()).where(Tiquete.activo_id == activo_id),
    })
    sesion.delete(activo)
    sesion.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
