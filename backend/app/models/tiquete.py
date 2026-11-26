"""Tiquete, datos del reporte, historial de estados y retroalimentacion."""

from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index,
                        Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (ALCANCES, ESTADOS_TIQUETE, NIVELES, PRIORIDADES,
                              TIPOS_DATO_REPORTE, TIPOS_REGISTRO, URGENCIAS, check_en)
from app.models.organizacion import ahora_utc


class Tiquete(Base):
    """Estado actual del caso. El diagnostico original de Prolog se guarda
    aparte (tabla diagnostico) y no cambia; aqui se guardan los valores
    vigentes, que pueden cambiar al escalar o reasignar."""

    __tablename__ = "tiquete"
    __table_args__ = (
        CheckConstraint(check_en("estado", ESTADOS_TIQUETE), name="ck_tiquete_estado"),
        CheckConstraint(check_en("alcance", ALCANCES), name="ck_tiquete_alcance"),
        CheckConstraint(check_en("urgencia_reportada", URGENCIAS), name="ck_tiquete_urgencia"),
        CheckConstraint(f"prioridad IS NULL OR {check_en('prioridad', PRIORIDADES)}",
                        name="ck_tiquete_prioridad"),
        CheckConstraint(f"tipo_registro IS NULL OR {check_en('tipo_registro', TIPOS_REGISTRO)}",
                        name="ck_tiquete_tipo"),
        CheckConstraint(f"nivel IS NULL OR {check_en('nivel', NIVELES)}", name="ck_tiquete_nivel"),
        CheckConstraint("pasos_ya_aplicados >= 0", name="ck_tiquete_pasos"),
        # Busqueda de incidentes abiertos similares (correlacion masiva).
        Index("ix_tiquete_depto_estado", "departamento_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    activo_id: Mapped[int | None] = mapped_column(ForeignKey("activo.id"), index=True)
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamento.id"), index=True)
    agente_id: Mapped[int | None] = mapped_column(ForeignKey("agente.id"), index=True)
    grupo_resolutor_id: Mapped[int | None] = mapped_column(ForeignKey("grupo_resolutor.id"),
                                                           index=True)

    # Datos del reporte
    servicio: Mapped[str] = mapped_column(String(50))
    componente: Mapped[str | None] = mapped_column(String(50))
    # Texto libre del usuario. Puede contener datos sensibles: nunca va
    # a la IA sin pasar por el sanitizador.
    descripcion: Mapped[str | None] = mapped_column(Text)
    alcance: Mapped[str] = mapped_column(String(20))
    urgencia_reportada: Mapped[str] = mapped_column(String(10))
    pasos_ya_aplicados: Mapped[int] = mapped_column(Integer, default=0)
    sospecha_seguridad: Mapped[bool] = mapped_column(Boolean, default=False)

    # Valores vigentes (inicialmente los del diagnostico de Prolog)
    estado: Mapped[str] = mapped_column(String(20), default="registrado", index=True)
    tipo_registro: Mapped[str | None] = mapped_column(String(30))
    prioridad: Mapped[str | None] = mapped_column(String(2), index=True)
    nivel: Mapped[int | None] = mapped_column(Integer)
    sla_horas_resolucion: Mapped[float | None] = mapped_column(Float)

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc,
                                                index=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc,
                                                     onupdate=ahora_utc)
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    datos_reporte: Mapped[list["DatoReporte"]] = relationship(
        back_populates="tiquete", cascade="all, delete-orphan")
    historial: Mapped[list["HistorialTiquete"]] = relationship(
        back_populates="tiquete", cascade="all, delete-orphan",
        order_by="HistorialTiquete.fecha")


class DatoReporte(Base):
    """Sintomas, contexto, evidencias y peticiones del tiquete (tabla
    sintoma_tiquete del enunciado). Cada codigo es un atomo de Prolog."""

    __tablename__ = "sintoma_tiquete"
    __table_args__ = (
        UniqueConstraint("tiquete_id", "codigo", name="uq_sintoma_tiquete"),
        CheckConstraint(check_en("tipo", TIPOS_DATO_REPORTE), name="ck_sintoma_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tiquete_id: Mapped[int] = mapped_column(ForeignKey("tiquete.id", ondelete="CASCADE"),
                                            index=True)
    codigo: Mapped[str] = mapped_column(String(60), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="sintoma")

    tiquete: Mapped[Tiquete] = relationship(back_populates="datos_reporte")


class HistorialTiquete(Base):
    __tablename__ = "historial_tiquete"
    __table_args__ = (
        CheckConstraint(check_en("estado_nuevo", ESTADOS_TIQUETE), name="ck_historial_nuevo"),
        CheckConstraint(f"estado_anterior IS NULL OR {check_en('estado_anterior', ESTADOS_TIQUETE)}",
                        name="ck_historial_anterior"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tiquete_id: Mapped[int] = mapped_column(ForeignKey("tiquete.id", ondelete="CASCADE"),
                                            index=True)
    # NULL en el registro inicial del tiquete.
    estado_anterior: Mapped[str | None] = mapped_column(String(20))
    estado_nuevo: Mapped[str] = mapped_column(String(20))
    # NULL cuando el cambio lo hace el sistema (ej. escalamiento automatico).
    agente_id: Mapped[int | None] = mapped_column(ForeignKey("agente.id"))
    comentario: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc,
                                            index=True)

    tiquete: Mapped[Tiquete] = relationship(back_populates="historial")


class Retroalimentacion(Base):
    __tablename__ = "retroalimentacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Una retroalimentacion por tiquete.
    tiquete_id: Mapped[int] = mapped_column(ForeignKey("tiquete.id", ondelete="CASCADE"),
                                            unique=True)
    funciono: Mapped[bool] = mapped_column(Boolean)
    paso_que_resolvio_id: Mapped[int | None] = mapped_column(ForeignKey("paso_diagnostico.id"))
    comentario: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
