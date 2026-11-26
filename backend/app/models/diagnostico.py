"""Diagnostico de Prolog y pasos de solucion de cada tiquete."""

from datetime import datetime

from sqlalchemy import (JSON, Boolean, CheckConstraint, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, FechaUTC
from app.models.enums import (NIVELES, PRIORIDADES, RESULTADOS_IA, TIPOS_REGISTRO, URGENCIAS,
                              check_en)
from app.models.organizacion import ahora_utc


class Diagnostico(Base):
    """Resultado del motor de inferencia tal como se obtuvo al crear el
    tiquete. No se modifica despues: sirve como evidencia de por que se
    tomo cada decision."""

    __tablename__ = "diagnostico"
    __table_args__ = (
        CheckConstraint(check_en("tipo_registro", TIPOS_REGISTRO), name="ck_diag_tipo"),
        CheckConstraint(check_en("impacto", ("individual", "departamento", "organizacion")),
                        name="ck_diag_impacto"),
        CheckConstraint(check_en("urgencia", URGENCIAS), name="ck_diag_urgencia"),
        CheckConstraint(check_en("prioridad", PRIORIDADES), name="ck_diag_prioridad"),
        CheckConstraint(check_en("nivel", NIVELES), name="ck_diag_nivel"),
        CheckConstraint(f"resultado_ia IS NULL OR {check_en('resultado_ia', RESULTADOS_IA)}",
                        name="ck_diag_resultado_ia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tiquete_id: Mapped[int] = mapped_column(ForeignKey("tiquete.id", ondelete="CASCADE"),
                                            unique=True)

    causa_principal: Mapped[str] = mapped_column(String(60))
    otras_causas: Mapped[list] = mapped_column(JSON, default=list)
    # Lista de {"causa": ..., "motivo": ...}
    causas_descartadas: Mapped[list] = mapped_column(JSON, default=list)
    tipo_registro: Mapped[str] = mapped_column(String(30))
    impacto: Mapped[str] = mapped_column(String(20))
    urgencia: Mapped[str] = mapped_column(String(10))
    prioridad: Mapped[str] = mapped_column(String(2))
    sla_horas_respuesta: Mapped[float] = mapped_column(Float)
    sla_horas_resolucion: Mapped[float] = mapped_column(Float)
    nivel: Mapped[int] = mapped_column(Integer)
    grupo_resolutor_id: Mapped[int] = mapped_column(ForeignKey("grupo_resolutor.id"))
    motivo: Mapped[str] = mapped_column(Text)
    posible_problema_masivo: Mapped[bool] = mapped_column(Boolean, default=False)
    incidentes_relacionados: Mapped[list] = mapped_column(JSON, default=list)
    reglas_aplicadas: Mapped[list] = mapped_column(JSON, default=list)
    # Respuesta completa de Prolog, para auditoria.
    respuesta_prolog: Mapped[dict] = mapped_column(JSON)

    # Salida de la IA (o de la plantilla de respaldo)
    guia_usuario: Mapped[str | None] = mapped_column(Text)
    nota_tecnica: Mapped[str | None] = mapped_column(Text)
    resultado_ia: Mapped[str | None] = mapped_column(String(15))

    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)

    pasos: Mapped[list["PasoDiagnostico"]] = relationship(
        back_populates="diagnostico", cascade="all, delete-orphan",
        order_by="PasoDiagnostico.orden")


class PasoDiagnostico(Base):
    __tablename__ = "paso_diagnostico"
    __table_args__ = (
        UniqueConstraint("diagnostico_id", "orden", name="uq_paso_orden"),
        CheckConstraint("orden >= 1", name="ck_paso_orden"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostico_id: Mapped[int] = mapped_column(ForeignKey("diagnostico.id", ondelete="CASCADE"),
                                                index=True)
    orden: Mapped[int] = mapped_column(Integer)
    # Identificador que genera Prolog (ej. cable_desconectado_1).
    codigo: Mapped[str] = mapped_column(String(80), index=True)
    texto: Mapped[str] = mapped_column(Text)

    diagnostico: Mapped[Diagnostico] = relationship(back_populates="pasos")
