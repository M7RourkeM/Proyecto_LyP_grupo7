"""Punto de entrada de la API de la Mesa de Servicios."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

import app.models  # noqa: F401  (registra los modelos)
from app.config import Configuracion, obtener_configuracion
from app.database import Base, motor
from app.routers import activos, agentes, catalogos, usuarios
from app.services.salud import estado_general

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    # Crea las tablas que falten; no borra datos existentes.
    Base.metadata.create_all(motor)
    yield


app = FastAPI(
    title="Asistente de Diagnostico y Soporte de TI",
    description="Backend de la mesa de servicios: diagnostico con Prolog e IA generativa local.",
    version="0.2.0",
    lifespan=ciclo_de_vida,
)

app.include_router(usuarios.router)
app.include_router(agentes.router)
app.include_router(activos.router)
app.include_router(catalogos.router)


class EstadoSalud(BaseModel):
    api: str = Field(examples=["ok"])
    prolog: str = Field(description="ok | caido", examples=["ok"])
    ia: str = Field(description="ok | caido", examples=["ok"])


@app.get("/salud", response_model=EstadoSalud, tags=["sistema"],
         summary="Estado de la API y de sus dependencias")
async def salud(config: Configuracion = Depends(obtener_configuracion)) -> dict[str, str]:
    """Siempre responde 200; las dependencias caidas se informan como "caido"."""
    return await estado_general(config)
