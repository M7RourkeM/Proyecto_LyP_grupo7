"""Entidades de la organizacion: departamentos, grupos, usuarios, agentes y activos."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import NIVELES, TIPOS_ACTIVO, check_en


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Departamento(Base):
    __tablename__ = "departamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Codigo identico al atomo que usa Prolog (ej. finanzas).
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="departamento")


class GrupoResolutor(Base):
    __tablename__ = "grupo_resolutor"
    __table_args__ = (CheckConstraint(check_en("nivel", NIVELES), name="ck_grupo_nivel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Codigo identico al atomo de Prolog (ej. mesa_ayuda, redes).
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))
    nivel: Mapped[int] = mapped_column(Integer)
    descripcion: Mapped[str | None] = mapped_column(String(255))


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(120), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30))
    # Dato sensible: nunca se envia a la IA (ver ia/sanitizador.py).
    identificacion: Mapped[str | None] = mapped_column(String(30), unique=True)
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamento.id"), index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    departamento: Mapped[Departamento] = relationship(back_populates="usuarios")


class Agente(Base):
    __tablename__ = "agente"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(120), unique=True)
    grupo_resolutor_id: Mapped[int] = mapped_column(ForeignKey("grupo_resolutor.id"), index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    grupo: Mapped[GrupoResolutor] = relationship()


class Activo(Base):
    __tablename__ = "activo"
    __table_args__ = (CheckConstraint(check_en("tipo", TIPOS_ACTIVO), name="ck_activo_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_inventario: Mapped[str] = mapped_column(String(30), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))
    marca_modelo: Mapped[str] = mapped_column(String(100))
    sistema_operativo: Mapped[str | None] = mapped_column(String(60))
    ubicacion: Mapped[str] = mapped_column(String(100))
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamento.id"), index=True)
    # Un activo compartido (ej. impresora de red) puede no tener usuario asignado.
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    departamento: Mapped[Departamento] = relationship()
    usuario: Mapped[Usuario | None] = relationship()
