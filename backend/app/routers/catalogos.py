"""Catalogos de solo lectura: departamentos y grupos resolutores.

Se administran con el seed porque sus codigos deben coincidir con los
atomos del motor Prolog. El frontend los usa para llenar listas.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.models import Departamento, GrupoResolutor
from app.schemas.organizacion import DepartamentoRespuesta, GrupoRespuesta

router = APIRouter(tags=["catalogos"])
SesionBD = Annotated[Session, Depends(obtener_sesion)]


@router.get("/departamentos", response_model=list[DepartamentoRespuesta],
            summary="Listar departamentos")
def listar_departamentos(sesion: SesionBD):
    return sesion.scalars(select(Departamento).order_by(Departamento.nombre)).all()


@router.get("/grupos", response_model=list[GrupoRespuesta],
            summary="Listar grupos resolutores")
def listar_grupos(sesion: SesionBD):
    return sesion.scalars(select(GrupoResolutor).order_by(GrupoResolutor.nivel,
                                                          GrupoResolutor.nombre)).all()
