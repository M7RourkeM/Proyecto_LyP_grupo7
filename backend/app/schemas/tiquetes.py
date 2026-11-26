"""Esquemas de tiquetes, transiciones, historial y diagnostico."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import ALCANCES, ESTADOS_TIQUETE, URGENCIAS

Estado = Literal[ESTADOS_TIQUETE]  # type: ignore[valid-type]
CodigoProlog = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True,
                                                pattern=r"^[a-z][a-z0-9_]{1,59}$")]


class Respuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Entrada ---------------------------------------------------------------

class TiqueteCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "usuario_id": 3, "activo_id": 3, "servicio": "red", "componente": "red_cableada",
        "sintomas": ["sin_internet", "vpn_caida"], "alcance": "individual",
        "urgencia": "media", "descripcion": "Desde esta manana no tengo Internet ni VPN.",
        "pasos_ya_aplicados": [], "sospecha_seguridad": False}]})

    usuario_id: int
    activo_id: int | None = None
    servicio: CodigoProlog
    componente: CodigoProlog | None = None
    sintomas: list[CodigoProlog] = Field(min_length=1, max_length=15,
                                         description="Codigos de GET /prolog/catalogo")
    alcance: Literal[ALCANCES]  # type: ignore[valid-type]
    urgencia: Literal[URGENCIAS]  # type: ignore[valid-type]
    descripcion: str | None = Field(None, max_length=2000,
                                    description="Texto libre; nunca se envia a la IA sin sanitizar")
    pasos_ya_aplicados: list[str] = Field(default_factory=list)
    sospecha_seguridad: bool = False


class TransicionCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "estado": "en_atencion", "agente_id": 1, "comentario": "Tomo el caso."}]})

    estado: Estado
    agente_id: int | None = Field(None, description="Obligatorio para pasar a en_atencion")
    comentario: str | None = Field(None, max_length=1000)
    grupo_resolutor_id: int | None = Field(
        None, description="Grupo destino al escalar manualmente (nivel 2 o 3)")


# --- Salida ----------------------------------------------------------------

class DatoReporteRespuesta(Respuesta):
    codigo: str
    tipo: str


class PasoRespuesta(Respuesta):
    id: int
    orden: int
    codigo: str
    texto: str


class DiagnosticoRespuesta(Respuesta):
    causa_principal: str
    causas: list[dict] = Field(description="Causas probables en orden, con descripcion")
    causas_descartadas: list[dict]
    tipo_registro: str
    impacto: str
    urgencia: str
    prioridad: str
    sla_horas_respuesta: float
    sla_horas_resolucion: float
    nivel: int
    grupo_resolutor_id: int
    motivo: str
    posible_problema_masivo: bool
    incidentes_relacionados: list[int]
    reglas_aplicadas: list[str]
    pasos: list[PasoRespuesta]
    guia_usuario: str | None
    nota_tecnica: str | None
    resultado_ia: str | None
    creado_en: datetime


class AuditoriaIA(Respuesta):
    resultado_ia: str | None = Field(description="ia_ok | ia_reintento | fallback")
    prompt_ia: str | None = Field(description="Mensajes enviados a la IA, ya sanitizados")
    guia_usuario: str | None
    nota_tecnica: str | None


class HistorialRespuesta(Respuesta):
    id: int
    estado_anterior: str | None
    estado_nuevo: str
    agente_id: int | None
    comentario: str | None
    fecha: datetime


class TiqueteResumen(Respuesta):
    id: int
    usuario_id: int
    activo_id: int | None
    departamento_id: int
    agente_id: int | None
    grupo_resolutor_id: int | None
    servicio: str
    categoria: str | None
    estado: str
    tipo_registro: str | None
    prioridad: str | None
    nivel: int | None
    sla_horas_resolucion: float | None
    creado_en: datetime
    actualizado_en: datetime
    resuelto_en: datetime | None
    cerrado_en: datetime | None


class TiqueteDetalle(TiqueteResumen):
    componente: str | None
    descripcion: str | None
    alcance: str
    urgencia_reportada: str
    pasos_ya_aplicados: int
    sospecha_seguridad: bool
    datos_reporte: list[DatoReporteRespuesta]
    diagnostico: DiagnosticoRespuesta | None
    historial: list[HistorialRespuesta]


class Recurrencia(BaseModel):
    cantidad: int = Field(description="Tiquetes de la misma categoria en la ventana")
    recurrente: bool


class RecurrenciaTiquete(BaseModel):
    usuario: Recurrencia
    activo: Recurrencia | None
    minimo: int
    dias: int


class CreacionRespuesta(BaseModel):
    tiquete: TiqueteDetalle
    recurrencia: RecurrenciaTiquete | None = Field(
        description="Nulo si el motor no asigno categoria")
    aviso: str | None = Field(
        None, description="Presente si el diagnostico automatico no estuvo disponible")
