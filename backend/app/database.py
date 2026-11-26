"""Motor de base de datos, sesiones y clase base de los modelos."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obtener_configuracion


class Base(DeclarativeBase):
    """Clase base de todos los modelos SQLAlchemy."""


def crear_motor(url: str) -> Engine:
    """Crea el motor; en SQLite activa la verificacion de claves foraneas."""
    es_sqlite = url.startswith("sqlite")
    motor = create_engine(
        url,
        connect_args={"check_same_thread": False} if es_sqlite else {},
    )
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
