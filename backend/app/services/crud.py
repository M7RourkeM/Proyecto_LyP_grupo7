"""Operaciones comunes de los routers CRUD.

Centraliza las reglas de error para que todos los recursos respondan igual:
  404 el recurso de la URL no existe
  409 conflicto: dato duplicado o el registro tiene dependencias
  422 el cuerpo referencia un registro que no existe (ademas de los 422
      de validacion que genera Pydantic)
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.schemas.comunes import ParametrosPagina


def obtener_o_404[M: Base](sesion: Session, modelo: type[M], id_: int, nombre: str) -> M:
    registro = sesion.get(modelo, id_)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nombre} {id_} no existe")
    return registro


def verificar_referencias(sesion: Session, referencias: dict[str, tuple[type[Base], Any]]) -> None:
    """referencias: {campo: (Modelo, id)}. Los id nulos se ignoran."""
    for campo, (modelo, id_) in referencias.items():
        if id_ is not None and sesion.get(modelo, id_) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"{campo}: no existe un registro con id {id_}")


def verificar_unicos(sesion: Session, modelo: type[Base], valores: dict[str, Any],
                     excluir_id: int | None = None) -> None:
    """Devuelve 409 si otro registro ya tiene alguno de estos valores unicos."""
    for campo, valor in valores.items():
        if valor is None:
            continue
        consulta = select(modelo.id).where(getattr(modelo, campo) == valor)
        if excluir_id is not None:
            consulta = consulta.where(modelo.id != excluir_id)
        if sesion.scalar(consulta) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Ya existe un registro con {campo} = {valor}")


def verificar_sin_dependencias(sesion: Session, nombre: str,
                               dependencias: dict[str, Select]) -> None:
    """dependencias: {descripcion: consulta de conteo}. 409 si alguna es > 0."""
    encontradas = [f"{sesion.scalar(c)} {desc}" for desc, c in dependencias.items()
                   if sesion.scalar(c)]
    if encontradas:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede eliminar {nombre}: tiene {', '.join(encontradas)}. "
            "Para conservar el historial, desactivelo en su lugar.")


def guardar[M: Base](sesion: Session, registro: M) -> M:
    """Confirma la transaccion; un choque de restriccion de la BD se responde con 409."""
    sesion.add(registro)
    try:
        sesion.commit()
    except IntegrityError as error:
        sesion.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "La operacion viola una restriccion de la base de datos") from error
    sesion.refresh(registro)
    return registro


def aplicar_cambios(registro: Base, cambios: dict[str, Any]) -> None:
    """Aplica un PATCH. Un null solo se acepta en columnas que admiten nulos."""
    columnas = registro.__table__.columns
    nulos_invalidos = [c for c, v in cambios.items() if v is None and not columnas[c].nullable]
    if nulos_invalidos:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Estos campos no pueden ser nulos: {', '.join(nulos_invalidos)}")
    for campo, valor in cambios.items():
        setattr(registro, campo, valor)


def paginar(sesion: Session, consulta: Select, params: ParametrosPagina) -> dict[str, Any]:
    """Devuelve un dict con la forma de Pagina; FastAPI lo valida contra el
    response_model del endpoint (Pagina[...Respuesta])."""
    total = sesion.scalar(select(func.count()).select_from(consulta.subquery()))
    items = sesion.scalars(consulta.offset(params.desplazamiento).limit(params.tamano)).all()
    return {"items": list(items), "total": total, "pagina": params.pagina,
            "tamano": params.tamano}
