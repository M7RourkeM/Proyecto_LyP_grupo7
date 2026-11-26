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
