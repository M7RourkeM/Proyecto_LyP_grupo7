"""Esquemas reutilizables: paginacion y validaciones comunes."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field, StringConstraints

# Validaciones de formato compartidas por varios recursos.
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Correo = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=120,
                                          pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Telefono = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9+\- ]{7,20}$")]
# Cedula fisica de Costa Rica: X-XXXX-XXXX
Cedula = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[1-9]-\d{4}-\d{4}$")]


class ParametrosPagina:
    """Parametros de paginacion para usar con Depends()."""

    def __init__(
        self,
        pagina: Annotated[int, Query(ge=1, description="Numero de pagina, desde 1")] = 1,
        tamano: Annotated[int, Query(ge=1, le=100, description="Registros por pagina")] = 20,
    ):
        self.pagina = pagina
        self.tamano = tamano

    @property
    def desplazamiento(self) -> int:
        return (self.pagina - 1) * self.tamano


class Error(BaseModel):
    detail: str = Field(examples=["Usuario 99 no existe"])


def errores(*codigos: int) -> dict[int, dict]:
    """Documenta en Swagger las respuestas de error de un endpoint."""
    descripciones = {
        404: "El recurso no existe",
        409: "Conflicto: dato duplicado o registro con dependencias",
        422: "Datos invalidos o referencia a un registro inexistente",
    }
    return {c: {"model": Error, "description": descripciones[c]} for c in codigos}


class Pagina[T](BaseModel):
    items: list[T]
    total: int = Field(description="Total de registros que cumplen el filtro")
    pagina: int
    tamano: int
