"""Contrato con el motor Prolog (secciones 3.1 y 3.2 del acuerdo del equipo)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ALCANCES, PRIORIDADES, TIPOS_REGISTRO, URGENCIAS


class EntradaDiagnostico(BaseModel):
    """Contrato 3.1: lo que el backend envia al motor."""

    model_config = {"json_schema_extra": {"examples": [{
        "servicio": "red", "componente": "red_cableada",
        "sintomas": ["sin_internet", "vpn_caida"], "alcance": "individual",
        "urgencia": "media", "departamento": "ventas"}]}}

    tiquete_id: int | None = None
    servicio: str
    componente: str | None = None
    sintomas: list[str] = Field(min_length=1, description="Atomos del motor (ej. sin_internet)")
    alcance: Literal[ALCANCES]  # type: ignore[valid-type]
    urgencia: Literal[URGENCIAS]  # type: ignore[valid-type]
    departamento: str
    usuarios_afectados: int = Field(1, ge=1)
    pasos_ya_aplicados: list[str] = Field(default_factory=list)
    sospecha_seguridad: bool = False
    # El motor decide los permisos administrativos por causa
    # (requiere_permisos_admin/1); este campo se conserva por contrato.
    requiere_permisos_admin: bool = False


class IncidenteAbierto(BaseModel):
    """Tiquete abierto que se le pasa al motor para la correlacion masiva."""

    id: int
    sintomas: list[str]
    departamento: str
    estado: str


class ResultadoPrevio(BaseModel):
    """Retroalimentacion historica: ajusta el ranking de causas en el motor."""

    causa: str
    funciono: bool


class ItemCatalogo(BaseModel):
    codigo: str
    descripcion: str
    servicio: str | None = None
    grupo: str | None = None
    impacto: str | None = None


class CatalogoProlog(BaseModel):
    """Datos que reconoce el motor, agrupados por tipo."""

    sintomas: list[ItemCatalogo]
    peticiones: list[ItemCatalogo]
    contextos: list[ItemCatalogo]
    evidencias: list[ItemCatalogo]

    def tipo_de(self, codigo: str) -> str | None:
        """Tipo de dato (sintoma, peticion, contexto, evidencia) o None si no existe."""
        grupos = {"sintoma": self.sintomas, "peticion": self.peticiones,
                  "contexto": self.contextos, "evidencia": self.evidencias}
        for tipo, items in grupos.items():
            if any(item.codigo == codigo for item in items):
                return tipo
        return None


class Causa(BaseModel):
    id: str
    descripcion: str


class CausaDescartada(BaseModel):
    id: str
    motivo: str


class Paso(BaseModel):
    orden: int = Field(ge=1)
    id: str
    texto: str


class DiagnosticoProlog(BaseModel):
    """Contrato 3.2: lo que devuelve el motor."""

    causas: list[Causa]
    causas_descartadas: list[CausaDescartada]
    categoria: str
    tipo_registro: Literal[TIPOS_REGISTRO]  # type: ignore[valid-type]
    impacto: Literal[ALCANCES]  # type: ignore[valid-type]
    urgencia: Literal[URGENCIAS]  # type: ignore[valid-type]
    prioridad: Literal[PRIORIDADES]  # type: ignore[valid-type]
    sla_horas: float = Field(description="Horas habiles para resolver")
    sla_horas_respuesta: float
    pasos: list[Paso]
    escalar: bool
    nivel: Literal[1, 2, 3]
    grupo_resolutor: str
    motivo: str
    motivo_escalamiento: str | None
    posible_problema_masivo: bool
    incidentes_relacionados: list[int]
    reglas_aplicadas: list[str]
