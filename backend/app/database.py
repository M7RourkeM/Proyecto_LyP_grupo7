"""Motor de base de datos, sesiones y clase base de los modelos."""

from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Engine, TypeDecorator, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import obtener_configuracion


class Base(DeclarativeBase):
    """Clase base de todos los modelos SQLAlchemy."""


class FechaUTC(TypeDecorator):
    """Fecha y hora siempre en UTC y con zona horaria.

    SQLite no guarda la zona horaria: sin este tipo, una fecha guardada
    en UTC se leeria sin zona y el frontend la interpretaria como hora
    local. Al guardar se convierte a UTC; al leer se le agrega la zona.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor: datetime | None, _dialecto):
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise ValueError("Las fechas deben incluir zona horaria")
        return valor.astimezone(timezone.utc)

    def process_result_value(self, valor: datetime | None, _dialecto):
        if valor is None or valor.tzinfo is not None:
            return valor
        return valor.replace(tzinfo=timezone.utc)


def crear_motor(url: str) -> Engine:
    """Crea el motor; en SQLite activa la verificacion de claves foraneas.

    Una base SQLite en memoria (url "sqlite://") usa una sola conexion
    compartida; si no, cada hilo veria una base vacia distinta.
    """
    es_sqlite = url.startswith("sqlite")
    opciones = {"connect_args": {"check_same_thread": False}} if es_sqlite else {}
    if url == "sqlite://":
        opciones["poolclass"] = StaticPool
    motor = create_engine(url, **opciones)
    if es_sqlite:
        # SQLite ignora las claves foraneas si no se activan en cada conexion.
        @event.listens_for(motor, "connect")
        def _activar_claves_foraneas(conexion, _registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return motor


motor = crear_motor(obtener_configuracion().database_url)
SesionLocal = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesion por peticion y la cierra al final."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
