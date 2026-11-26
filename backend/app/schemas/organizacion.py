"""Esquemas de entrada y salida de departamentos, grupos, usuarios, agentes y activos.

Convencion: *Crear para POST, *Actualizar para PATCH (todos los campos
opcionales) y *Respuesta para lo que devuelve la API.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import TIPOS_ACTIVO
from app.schemas.comunes import Cedula, Correo, Nombre, Telefono

TipoActivo = Literal[TIPOS_ACTIVO]  # type: ignore[valid-type]
Texto100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
CodigoInventario = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True,
                                                    pattern=r"^[A-Za-z]{3}-\d{3,6}$")]


class Respuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Catalogos (solo lectura) ----------------------------------------

class DepartamentoRespuesta(Respuesta):
    id: int
    codigo: str
    nombre: str


class GrupoRespuesta(Respuesta):
    id: int
    codigo: str
    nombre: str
    nivel: int
    descripcion: str | None


# --- Usuarios --------------------------------------------------------

class UsuarioCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "nombre": "Laura Mendez Solis", "correo": "laura.mendez@empresa-demo.test",
        "telefono": "8800-1234", "identificacion": "1-2345-6789", "departamento_id": 1}]})

    nombre: Nombre
    correo: Correo
    telefono: Telefono | None = None
    identificacion: Cedula | None = Field(None, description="Cedula fisica X-XXXX-XXXX")
    departamento_id: int


class UsuarioActualizar(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"telefono": "8800-9999"}]})

    nombre: Nombre | None = None
    correo: Correo | None = None
    telefono: Telefono | None = None
    identificacion: Cedula | None = None
    departamento_id: int | None = None
    activo: bool | None = None


class UsuarioRespuesta(Respuesta):
    id: int
    nombre: str
    correo: str
    telefono: str | None
    identificacion: str | None
    departamento_id: int
    activo: bool
    creado_en: datetime


# --- Agentes ---------------------------------------------------------

class AgenteCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "nombre": "Daniela Soto Arias", "correo": "dsoto.soporte@empresa-demo.test",
        "grupo_resolutor_id": 1}]})

    nombre: Nombre
    correo: Correo
    grupo_resolutor_id: int


class AgenteActualizar(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"grupo_resolutor_id": 2}]})

    nombre: Nombre | None = None
    correo: Correo | None = None
    grupo_resolutor_id: int | None = None
    activo: bool | None = None


class AgenteRespuesta(Respuesta):
    id: int
    nombre: str
    correo: str
    grupo_resolutor_id: int
    activo: bool
    creado_en: datetime


# --- Activos ---------------------------------------------------------

class ActivoCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "codigo_inventario": "LAP-010", "tipo": "laptop", "marca_modelo": "Dell Latitude 5440",
        "sistema_operativo": "Windows 11", "ubicacion": "Edificio A, piso 2",
        "departamento_id": 1, "usuario_id": 1}]})

    codigo_inventario: CodigoInventario = Field(description="Formato AAA-000, ej. LAP-010")
    tipo: TipoActivo
    marca_modelo: Texto100
    sistema_operativo: Texto100 | None = None
    ubicacion: Texto100
    departamento_id: int
    usuario_id: int | None = Field(None, description="Nulo si el activo es compartido")


class ActivoActualizar(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"ubicacion": "Edificio B, piso 1"}]})

    codigo_inventario: CodigoInventario | None = None
    tipo: TipoActivo | None = None
    marca_modelo: Texto100 | None = None
    sistema_operativo: Texto100 | None = None
    ubicacion: Texto100 | None = None
    departamento_id: int | None = None
    usuario_id: int | None = None


class ActivoRespuesta(Respuesta):
    id: int
    codigo_inventario: str
    tipo: str
    marca_modelo: str
    sistema_operativo: str | None
    ubicacion: str
    departamento_id: int
    usuario_id: int | None
    creado_en: datetime
