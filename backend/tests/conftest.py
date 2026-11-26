"""Fixtures comunes: una base SQLite en memoria por prueba."""

import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.database import Base, crear_motor
from scripts.seed import cargar_datos


@pytest.fixture
def motor_prueba():
    motor = crear_motor("sqlite://")
    Base.metadata.create_all(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def sesion(motor_prueba):
    with Session(motor_prueba, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def sesion_con_datos(sesion):
    cargar_datos(sesion)
    return sesion


@pytest.fixture
def api(sesion_con_datos):
    """Cliente HTTP contra una base en memoria con los datos de la semilla.

    No se usa `with TestClient(...)` para no ejecutar el ciclo de vida de la
    app, que crearia tablas en la base real.
    """
    from fastapi.testclient import TestClient

    from app.database import obtener_sesion
    from app.main import app

    app.dependency_overrides[obtener_sesion] = lambda: sesion_con_datos
    yield TestClient(app)
    app.dependency_overrides.clear()
