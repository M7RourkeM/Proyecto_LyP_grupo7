"""CRUD de usuarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.models import Activo, Departamento, Tiquete, Usuario
from app.schemas.comunes import Pagina, ParametrosPagina, errores
from app.schemas.organizacion import UsuarioActualizar, UsuarioCrear, UsuarioRespuesta
from app.services import crud

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
SesionBD = Annotated[Session, Depends(obtener_sesion)]
UNICOS = ("correo", "identificacion")


@router.get("", response_model=Pagina[UsuarioRespuesta], summary="Listar usuarios")
def listar(sesion: SesionBD, params: Annotated[ParametrosPagina, Depends()],
           departamento_id: Annotated[int | None, Query()] = None,
           activo: Annotated[bool | None, Query()] = None):
    consulta = select(Usuario).order_by(Usuario.id)
    if departamento_id is not None:
        consulta = consulta.where(Usuario.departamento_id == departamento_id)
    if activo is not None:
        consulta = consulta.where(Usuario.activo == activo)
    return crud.paginar(sesion, consulta, params)


@router.get("/{usuario_id}", response_model=UsuarioRespuesta, responses=errores(404),
            summary="Consultar un usuario")
def consultar(usuario_id: int, sesion: SesionBD):
    return crud.obtener_o_404(sesion, Usuario, usuario_id, "Usuario")


@router.post("", response_model=UsuarioRespuesta, status_code=status.HTTP_201_CREATED,
             responses=errores(409, 422), summary="Crear un usuario")
def crear(datos: UsuarioCrear, sesion: SesionBD):
    crud.verificar_referencias(sesion, {"departamento_id": (Departamento, datos.departamento_id)})
    crud.verificar_unicos(sesion, Usuario, datos.model_dump(include=set(UNICOS)))
    return crud.guardar(sesion, Usuario(**datos.model_dump()))


@router.patch("/{usuario_id}", response_model=UsuarioRespuesta,
              responses=errores(404, 409, 422), summary="Modificar un usuario")
def actualizar(usuario_id: int, datos: UsuarioActualizar, sesion: SesionBD):
    usuario = crud.obtener_o_404(sesion, Usuario, usuario_id, "Usuario")
    cambios = datos.model_dump(exclude_unset=True)
    crud.verificar_referencias(sesion, {"departamento_id": (Departamento,
                                                            cambios.get("departamento_id"))})
    crud.verificar_unicos(sesion, Usuario, {k: v for k, v in cambios.items() if k in UNICOS},
                          excluir_id=usuario_id)
    crud.aplicar_cambios(usuario, cambios)
    return crud.guardar(sesion, usuario)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses=errores(404, 409), summary="Eliminar un usuario")
def eliminar(usuario_id: int, sesion: SesionBD):
    """Solo se elimina si no tiene tiquetes ni activos asignados; si los tiene,
    se responde 409 y se recomienda desactivarlo (PATCH activo=false)."""
    usuario = crud.obtener_o_404(sesion, Usuario, usuario_id, "Usuario")
    crud.verificar_sin_dependencias(sesion, "el usuario", {
        "tiquetes": select(func.count()).where(Tiquete.usuario_id == usuario_id),
        "activos asignados": select(func.count()).where(Activo.usuario_id == usuario_id),
    })
    sesion.delete(usuario)
    sesion.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
