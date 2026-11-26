"""Esquemas de retroalimentacion, historial e indicadores."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tiquetes import TiqueteResumen


# --- Retroalimentacion ---------------------------------------------------

class RetroalimentacionCrear(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "funciono": True, "paso_que_resolvio": "cable_desconectado_2",
        "comentario": "Con otro cable volvio la conexion."}]})

    funciono: bool
    paso_que_resolvio: str | None = Field(
        None, description="Codigo del paso del diagnostico que resolvio (ej. cable_desconectado_2)")
    comentario: str | None = Field(None, max_length=1000)


class RetroalimentacionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tiquete_id: int
    funciono: bool
    paso_que_resolvio: str | None
    comentario: str | None
    fecha: datetime


class EfectividadCausa(BaseModel):
    causa: str
    casos: int
    funciono: int
    no_funciono: int
    efectividad: float = Field(description="Porcentaje de casos en que la solucion funciono")


class EfectividadPaso(BaseModel):
    paso: str
    veces_que_resolvio: int


class EstadisticasRetroalimentacion(BaseModel):
    total: int
    por_causa: list[EfectividadCausa]
    por_paso: list[EfectividadPaso]


# --- Historial ---------------------------------------------------------------

class RecurrenciaCategoria(BaseModel):
    categoria: str
    cantidad: int
    recurrente: bool


class Historial(BaseModel):
    total: int
    tiquetes: list[TiqueteResumen]
    recurrencias: list[RecurrenciaCategoria] = Field(
        description="Categorias con su cantidad de tiquetes en la ventana de recurrencia")
    ventana_dias: int
    minimo_recurrencia: int


# --- Indicadores -------------------------------------------------------------

class CumplimientoSLA(BaseModel):
    resueltos_con_sla: int = Field(description="Tiquetes resueltos que tienen SLA asignado")
    dentro_de_sla: int
    porcentaje: float | None = Field(description="Nulo si todavia no hay tiquetes resueltos")
    abiertos_vencidos: int = Field(description="Abiertos que ya superaron su SLA")
    promedio_horas_resolucion: float | None = Field(description="Horas habiles")


class Indicadores(BaseModel):
    total: int
    abiertos: int
    resueltos: int
    resueltos_primer_nivel: int = Field(description="Resueltos sin haber pasado por escalado")
    escalados: int = Field(description="Tiquetes que pasaron por escalado alguna vez")
    sla: CumplimientoSLA
    por_estado: dict[str, int]
    por_prioridad: dict[str, int]
    por_grupo: dict[str, int]
    por_tipo_registro: dict[str, int]
